"""Случайное оперативное событие по грузу и короткий текст уведомления."""

from __future__ import annotations

import json
import random
import uuid
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.engine import route_of
from app.services.openrouter import AIUnavailable, _key
from app.services.risk import iso
from app.services.telegram_bridge import push_notice
from app.services.telemetry import _now, ingest_event, simulate_port_departure_closed


def _shipment(data: dict, shipment_id: str) -> dict:
    for item in data["shipments"]:
        if item["id"] == shipment_id:
            return item
    raise ValueError("Груз не найден")


def _ai_notice(shipment: dict, title: str, facts: str) -> str:
    fallback = (
        f"{shipment['id']}, {shipment.get('origin')} → {shipment.get('destination')}. {title}. {facts}"
    )
    try:
        key = _key()
    except AIUnavailable:
        return fallback
    payload = {
        "model": "nvidia/nemotron-3.5-lightning:free",
        "temperature": 0.3,
        "max_tokens": 220,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты диспетчер LANDWAY. Напиши по-русски одно уведомление логисту: 2 коротких предложения. "
                    "Не выдумывай брони, GPS и подтверждения. Не меняй числа из фактов. Без markdown."
                ),
            },
            {"role": "user", "content": json.dumps({"событие": title, "факты": facts}, ensure_ascii=False)},
        ],
    }
    request = Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return fallback
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        return fallback
    return " ".join(content.strip().split())[:700]


def _rail_payload(shipment_id: str, stage: dict) -> tuple[str, dict]:
    hours = random.choice((8, 14, 24, 36, 52))
    return (
        f"Поезд задерживается на {hours} ч",
        {
            "eventId": f"sim-rand-{uuid.uuid4().hex}",
            "eventType": "rail.delay",
            "sourceName": "РЖД (случайное событие)",
            "sourceKind": "simulation",
            "observedAt": iso(_now()),
            "shipmentId": shipment_id,
            "stageId": stage["id"],
            "delayHours": hours,
            "note": f"Случайная задержка поезда на {hours} ч",
        },
    )


def _weather_payload(port_name: str) -> tuple[str, dict]:
    wind = random.choice((16, 18, 21))
    workload = random.choice((78, 86, 92))
    return (
        f"В порту {port_name} ветер {wind} м/с и загрузка {workload}%",
        {
            "eventId": f"sim-rand-{uuid.uuid4().hex}",
            "eventType": "port.status",
            "sourceName": "Порт (случайное событие)",
            "sourceKind": "simulation",
            "observedAt": iso(_now()),
            "portName": port_name,
            "windSpeed": wind,
            "workload": workload,
            "delayNote": f"Сильный ветер {wind} м/с, неблагоприятная погода, загрузка порта {workload}%",
        },
    )


def _candidates(data: dict, shipment: dict) -> list[tuple[str, dict]]:
    route = route_of(data, shipment)
    options: list[tuple[str, dict]] = []
    sea_port = None
    for stage in route["stages"]:
        if stage.get("status") == "completed":
            continue
        if stage.get("transportType") == "rail":
            options.append(_rail_payload(shipment["id"], stage))
        if stage.get("transportType") == "sea" and stage.get("location"):
            sea_port = stage["location"]
            ends = iso(_now() + timedelta(hours=random.choice((8, 14, 24))))
            options.append(
                (
                    f"Порт {sea_port} закрыт для выхода судов",
                    {"_port_close": sea_port, "_ends": ends},
                )
            )
    port_name = sea_port or shipment.get("currentPort") or shipment.get("origin")
    if port_name:
        options.append(_weather_payload(str(port_name)))
    if not options and shipment.get("destination"):
        options.append(_weather_payload(str(shipment["destination"])))
    return options


def trigger_random_event(data: dict, shipment_id: str) -> dict:
    shipment = _shipment(data, shipment_id)
    options = _candidates(data, shipment)
    random.shuffle(options)
    title = "Оперативное обновление"
    applied = None
    error = "Для этого груза сейчас нет участка, к которому можно применить событие"
    for label, payload in options:
        try:
            if payload.get("_port_close"):
                applied = simulate_port_departure_closed(
                    data,
                    port_name=payload["_port_close"],
                    restriction_ends_at=payload["_ends"],
                    note="Случайное закрытие выхода судов",
                )
            else:
                applied = ingest_event(data, payload)
            title = label
            if applied.get("status") == "stale":
                error = applied.get("message") or "Событие устарело"
                applied = None
                continue
            break
        except ValueError as exc:
            error = str(exc)
            applied = None
    if applied is None:
        raise ValueError(error)

    prediction = next((item for item in data["predictions"] if item["shipmentId"] == shipment_id), {})
    reasons = "; ".join(prediction.get("reasons") or []) or title
    facts = (
        f"{shipment.get('origin')} → {shipment.get('destination')}. {reasons}. "
        f"Рекомендация: {prediction.get('recommendation') or 'следить за расписанием'}."
    )
    message = _ai_notice(shipment, title, facts)
    notice = {
        "id": f"{shipment_id}:scenario",
        "shipmentId": shipment_id,
        "type": "scenario",
        "title": title,
        "description": message,
        "severity": prediction.get("riskLevel") if prediction.get("riskLevel") in ("low", "medium", "high") else "medium",
        "createdAt": iso(_now()),
        "read": False,
        "href": f"/shipments/{shipment_id}",
    }
    others = [item for item in data.get("scenarioNotices") or [] if item.get("shipmentId") != shipment_id]
    data["scenarioNotices"] = [notice, *others][:12]
    seen = {item["id"] for item in data["notifications"]}
    if notice["id"] in seen:
        for item in data["notifications"]:
            if item["id"] == notice["id"]:
                item.update(notice)
    else:
        data["notifications"].insert(0, notice)

    telegram_text = f"LANDWAY · {shipment_id}\n{title}\n{shipment.get('origin')} → {shipment.get('destination')}\n\n{message}"
    delivery = push_notice(data, telegram_text)
    return {
        "shipmentId": shipment_id,
        "title": title,
        "message": message,
        "telegram": delivery,
        "event": applied,
    }
