"""Демонстрационная эвристика риска задержки.

Это не обученная модель. Баллы факторов суммируются и переводятся
в вероятность 0–100% насыщаемой функцией.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from app.catalog import REQUIRED_DOCUMENT_TYPES

RAIL_DELAY_POINTS = 24
MISS_POINTS = 20
TIGHT_POINTS = 8
WORKLOAD_HIGH_POINTS = 24
WORKLOAD_MID_POINTS = 10
WEATHER_POINTS = 20
WIND_POINTS = 14
DOCS_PROBLEM_POINTS = 16
DOCS_PENDING_POINTS = 6
AWAITING_POINTS = 12
SATURATION = 70


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def stage_arrival(stage: dict) -> datetime | None:
    from app.services.stage_schedule import stage_arrival as _arrival

    return _arrival(stage)


def risk_level(probability: int, delivered: bool) -> str:
    if delivered:
        return "none"
    if probability <= 30:
        return "low"
    if probability <= 60:
        return "medium"
    return "high"


def to_probability(raw: float) -> int:
    if raw <= 0:
        return 0
    value = 100 * (1 - math.exp(-raw / SATURATION))
    return max(0, min(100, int(round(value))))


def _port(ports: list[dict], name: str) -> dict | None:
    for port in ports:
        if port["name"] == name:
            return port
    return None


def _docs_flags(documents: list[dict]) -> dict:
    by_type: dict[str, list[dict]] = {}
    for document in documents:
        by_type.setdefault(document["type"], []).append(document)
    missing: list[str] = []
    attention: list[str] = []
    pending: list[str] = []
    for type_id in REQUIRED_DOCUMENT_TYPES:
        items = by_type.get(type_id, [])
        if not items or all(item.get("status") == "missing" or not item.get("file") for item in items):
            missing.append(type_id)
        elif any(item.get("status") == "needs_attention" for item in items):
            attention.append(type_id)
        elif any(item.get("status") == "pending" for item in items):
            pending.append(type_id)
    return {"missing": missing, "attention": attention, "pending": pending}


FERRY_INTERVAL_HOURS = 24


def _hours(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _connection(stages: list[dict], sea: dict | None, ports: list[dict], moment: datetime) -> dict | None:
    """Стыковка «поезд/авто → паром»: та же модель, что в синтетической истории коридора."""
    if not sea or sea["status"] != "pending" or not sea.get("shipDeparture"):
        return None
    index = stages.index(sea)
    if index == 0:
        return None
    arrival = stage_arrival(stages[index - 1])
    ship_at = parse_dt(sea["shipDeparture"])
    if arrival is None or ship_at is None:
        return None
    port = _port(ports, sea["location"])
    workload = float(port["workload"]) if port else 60.0
    wind = float(port["windSpeed"]) if port else 8.0
    handling = 1.5 + max(0.0, workload - 60) / 12
    wind_hold = max(0.0, wind - 14) * 0.9
    crossing = max(0.0, wind - 12) * 0.6
    buffer_hours = (ship_at + timedelta(hours=wind_hold) - arrival - timedelta(hours=handling)).total_seconds() / 3600
    wait = 0.0
    if buffer_hours < 0:
        wait = FERRY_INTERVAL_HOURS * math.ceil(-buffer_hours / FERRY_INTERVAL_HOURS)
        hours = wait + wind_hold + crossing
    elif buffer_hours < 4:
        hours = FERRY_INTERVAL_HOURS / 3 + wind_hold + crossing
    else:
        hours = wind_hold + crossing
    return {
        "port": sea["location"],
        "bufferHours": round(buffer_hours, 1),
        "missed": buffer_hours < 0,
        "waitHours": wait,
        "hours": hours,
    }


def assess(
    shipment: dict,
    route: dict,
    ports: list[dict],
    documents: list[dict],
    now: datetime | None = None,
) -> dict:
    """Оценивает один груз по текущим этапам, портам и документам."""
    moment = now or datetime.now().replace(microsecond=0)
    delivered = shipment.get("status") == "delivered"
    if delivered:
        return {
            "probability": 0,
            "riskLevel": "none",
            "reasons": ["доставка завершена"],
            "estimatedDelay": 0,
            "recommendation": "Перевозка завершена.",
            "calculatedAt": iso(moment),
            "rawScore": 0,
        }

    stages = route.get("stages") or []
    reasons: list[str] = []
    raw = 5.0
    delay = 0.0

    sea = next(
        (stage for stage in stages if stage["transportType"] == "sea" and stage["status"] in ("pending", "in_progress")),
        None,
    )
    sea_port_name = sea["location"] if sea else shipment["origin"]
    dest_name = shipment["destination"]
    active_name = dest_name if sea and sea["status"] == "in_progress" else sea_port_name
    active_port = _port(ports, active_name)

    connection = _connection(stages, sea, ports, moment)
    generic_hours = 0.0

    if active_port:
        workload = float(active_port["workload"])
        if workload >= 80:
            raw += WORKLOAD_HIGH_POINTS
            reasons.append(f"высокая загруженность порта {active_port['name']}")
            generic_hours += 8
        elif workload >= 60:
            raw += WORKLOAD_MID_POINTS
            reasons.append(f"повышенная загруженность порта {active_port['name']}")
            generic_hours += 4

    weather_names = []
    for name in (sea_port_name, dest_name):
        if name not in weather_names:
            weather_names.append(name)
    weather_ports = [port for port in (_port(ports, name) for name in weather_names) if port]
    adverse = [port for port in weather_ports if port.get("weatherSeverity") == "adverse"]
    wind_port = max(weather_ports, key=lambda port: float(port["windSpeed"]), default=None)

    factor = 1.0
    if sea and sea["status"] == "pending" and sea.get("shipDeparture"):
        departure = parse_dt(sea["shipDeparture"])
        if departure is not None:
            hours_left = (departure - moment).total_seconds() / 3600
            if hours_left <= 24:
                factor = 1.0
            elif hours_left <= 72:
                factor = 0.35
            else:
                factor = 0.2
    elif sea and sea["status"] == "in_progress":
        factor = 0.5

    if adverse:
        raw += round(WEATHER_POINTS * factor) * len(adverse)
        names = ", ".join(port["name"] for port in adverse)
        reasons.append(f"неблагоприятная погода ({names})")
        generic_hours += round(10 * factor) * len(adverse)

    if wind_port and float(wind_port["windSpeed"]) >= 16:
        raw += round(WIND_POINTS * factor)
        reasons.append(f"сильный ветер, {float(wind_port['windSpeed']):g} м/с ({wind_port['name']})")
        generic_hours += round(6 * factor)

    rail_delay = 0.0
    for stage in stages:
        if stage["transportType"] == "rail" and stage["status"] in ("delayed", "in_progress", "pending"):
            rail_delay += float(stage.get("delayHours") or 0)
    if rail_delay >= 8:
        raw += RAIL_DELAY_POINTS
        reasons.append("поезд прибывает позже расписания")
    elif rail_delay >= 2:
        raw += 10
        reasons.append("небольшое отставание поезда от расписания")

    if connection is None:
        delay += generic_hours + (rail_delay if rail_delay >= 2 else 0)
    else:
        delay += connection["hours"]
        buffer_hours = connection["bufferHours"]
        if connection["missed"]:
            raw += MISS_POINTS
            reasons.append(
                f"существует риск пропустить морской рейс: груз будет в порту {connection['port']} "
                f"на {abs(buffer_hours):.0f} ч позже отхода, ожидание следующего рейса ≈ {connection['waitHours']:.0f} ч"
            )
        elif buffer_hours < 4:
            raw += MISS_POINTS
            reasons.append(
                f"существует риск пропустить морской рейс: запас на пересадку {_hours(buffer_hours)} ч"
            )
        elif buffer_hours < 7:
            raw += TIGHT_POINTS
            reasons.append(f"короткое окно пересадки на морской рейс ({_hours(buffer_hours)} ч)")

    flags = _docs_flags(documents)
    if flags["missing"] or flags["attention"]:
        raw += DOCS_PROBLEM_POINTS
        reasons.append("проблемы с документами")
        if flags["attention"]:
            reasons.append("документы требуют проверки")
        delay += 8
    elif flags["pending"]:
        raw += DOCS_PENDING_POINTS
        reasons.append("документы ожидают проверки")
        delay += 3

    if shipment.get("status") == "awaiting":
        raw += AWAITING_POINTS
        reasons.append("груз ожидает отправления, резерв времени ограничен")
        delay += 4

    if not reasons:
        reasons.append("критичных факторов задержки не выявлено")

    probability = to_probability(raw)
    level = risk_level(probability, False)
    recommendation = _recommendation(shipment, reasons, level, factor)

    return {
        "probability": probability,
        "riskLevel": level,
        "reasons": reasons,
        "estimatedDelay": int(round(delay)),
        "recommendation": recommendation,
        "calculatedAt": iso(moment),
        "rawScore": raw,
    }


def _recommendation(shipment: dict, reasons: list[str], level: str, factor: float) -> str:
    text = " ".join(reasons)
    if shipment.get("status") == "documents_issue" or "проблемы с документами" in text or "требуют проверки" in text:
        return "Завершить проверку и доукомплектовать документы до отправки."
    if "пропустить морской рейс" in text or "поезд прибывает позже" in text:
        return "Рассмотреть альтернативный порт отправления."
    if "неблагоприятная погода" in text and factor >= 1:
        return "Учесть погодное окно и при необходимости перенести выход судна."
    if "высокая загруженность порта" in text:
        return "Рассмотреть альтернативный порт отправления."
    if level == "low":
        return "Сохранять текущий маршрут и контролировать расписание."
    return "Сравнить альтернативные маршруты в разделе «Маршруты»."
