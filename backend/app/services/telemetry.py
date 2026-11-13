"""Приём оперативных событий (ЖД, порт, перевозчик) и обновление прогноза."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from app.catalog import PORT_NAMES
from app.services.engine import recalculate, route_of
from app.services.risk import iso, parse_dt
from app.services.port_restrictions import (
    DEPARTURE_CLOSED,
    DEPARTURE_OPEN,
    apply_stage_restrictions,
    feed_departure_view,
    merge_port_feed,
    parse_departure_payload,
)
from app.services.stage_schedule import ensure_schedule_fields, rail_expected_arrival, sync_stage_chain


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


MAX_FUTURE_SKEW = timedelta(hours=1)
MAX_DELAY_HOURS = 240.0


class StaleEvent(Exception):
    pass


def ensure_telemetry(data: dict) -> dict:
    if not data.get("telemetry"):
        data["telemetry"] = {
            "events": {},
            "portFeed": {},
            "railFeed": {},
            "externalConnected": False,
            "lastUpdatedAt": None,
        }
    data["telemetry"].setdefault("stageObservedAt", {})
    data["telemetry"].setdefault("stageSource", {})
    return data["telemetry"]


def _guard_stage(telemetry: dict, stage: dict, observed: datetime) -> None:
    previous = parse_dt(telemetry["stageObservedAt"].get(stage["id"]))
    if previous and previous > observed:
        raise StaleEvent(f"Для этапа {stage['location']} → {stage['nextLocation']} уже есть более свежее наблюдение")


def _mark_stage(telemetry: dict, stage: dict, observed: datetime, event_id: str, source_name: str, source_kind: str) -> None:
    telemetry["stageObservedAt"][stage["id"]] = iso(observed)
    telemetry["stageSource"][stage["id"]] = {
        "eventId": event_id,
        "sourceName": source_name,
        "sourceKind": source_kind,
        "observedAt": iso(observed),
    }


def stage_sources(data: dict, route: dict) -> dict:
    sources = (data.get("telemetry") or {}).get("stageSource") or {}
    return {stage["id"]: sources[stage["id"]] for stage in route["stages"] if stage["id"] in sources}


def _number(payload: dict, key: str, low: float, high: float) -> float | None:
    if payload.get(key) is None:
        return None
    try:
        value = float(payload[key])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Поле {key} должно быть числом") from exc
    if not low <= value <= high:
        raise ValueError(f"Поле {key} должно быть в диапазоне {low:g}–{high:g}")
    return value


def _timestamp(payload: dict, key: str) -> datetime | None:
    if not payload.get(key):
        return None
    try:
        value = parse_dt(str(payload[key]))
    except ValueError:
        value = None
    if value is None:
        raise ValueError(f"Некорректная дата в поле {key}: ожидается ISO 8601, например 2026-11-12T14:30:00+03:00")
    return value


def _find_shipment(data: dict, shipment_id: str) -> dict:
    for shipment in data["shipments"]:
        if shipment["id"] == shipment_id:
            return shipment
    raise ValueError("Груз не найден")


def _find_route(data: dict, shipment: dict) -> dict:
    return route_of(data, shipment)


def _find_stage(route: dict, stage_id: str | None, transport: str | None = None) -> dict:
    if stage_id:
        for stage in route["stages"]:
            if stage["id"] == stage_id:
                return stage
        raise ValueError("Этап маршрута не найден")
    if transport:
        for stage in route["stages"]:
            if stage["transportType"] == transport:
                return stage
        raise ValueError(f"Этап с транспортом «{transport}» не найден")
    raise ValueError("Укажите stageId или transportType")


def _port(data: dict, name: str) -> dict:
    for port in data["ports"]:
        if port["name"] == name:
            return port
    raise ValueError("Порт не найден")


def _observed(payload: dict) -> datetime:
    raw = payload.get("observedAt")
    if not raw:
        raise ValueError("Нужно поле observedAt")
    return _timestamp(payload, "observedAt")


def _feed_is_stale(feed: dict, observed: datetime) -> bool:
    previous = feed.get("observedAt")
    if not previous:
        return False
    prev = parse_dt(previous)
    return prev is not None and prev > observed


def _record_feed(feed_bucket: dict, key: str, payload: dict, observed: datetime) -> None:
    existing = feed_bucket.get(key, {})
    if _feed_is_stale(existing, observed):
        raise StaleEvent("Сообщение устарело: есть более свежие данные")
    feed_bucket[key] = {
        **{k: v for k, v in payload.items() if k not in ("eventId", "eventType", "shipmentId", "stageId", "portName")},
        "observedAt": iso(observed),
    }


def _append_history(
    shipment: dict,
    *,
    observed: datetime,
    location: str,
    transport: str,
    description: str,
    status: str,
    source_name: str,
    source_kind: str,
    event_id: str,
) -> None:
    shipment.setdefault("extraEvents", []).append(
        {
            "time": iso(observed),
            "location": location,
            "transport": transport,
            "description": description,
            "status": status,
            "sourceName": source_name,
            "sourceKind": source_kind,
            "eventId": event_id,
            "telemetry": True,
        }
    )


def _journal(data: dict, shipment_id: str | None, title: str, details: str, at: datetime) -> None:
    data.setdefault("journal", []).insert(
        0,
        {
            "id": f"j-{uuid.uuid4().hex[:10]}",
            "shipmentId": shipment_id,
            "type": "telemetry",
            "title": title,
            "result": "принято",
            "details": details,
            "at": iso(at),
        },
    )


def _shipments_at_port(data: dict, port_name: str) -> list[tuple[dict, dict, dict | None]]:
    hits: list[tuple[dict, dict, dict | None]] = []
    for shipment in data["shipments"]:
        if shipment["status"] == "delivered":
            continue
        route = _find_route(data, shipment)
        for stage in route["stages"]:
            touches = stage["location"] == port_name or stage["nextLocation"] == port_name
            if touches:
                hits.append((shipment, route, stage))
    return hits


def _require_open_stage(stage: dict, transport: str) -> None:
    if stage["transportType"] != transport:
        raise ValueError(
            f"Этап {stage['location']} → {stage['nextLocation']} не подходит: ожидался транспорт «{transport}»"
        )
    if stage["status"] == "completed":
        raise ValueError(f"Этап {stage['location']} → {stage['nextLocation']} уже завершён")


def _record_event(telemetry: dict, event_id: str, event_type: str, source_name: str, source_kind: str,
                  observed: datetime, moment: datetime, shipment_ids: list[str], status: str) -> None:
    telemetry["events"][event_id] = {
        "eventId": event_id,
        "eventType": event_type,
        "sourceName": source_name,
        "sourceKind": source_kind,
        "observedAt": iso(observed),
        "appliedAt": iso(moment),
        "shipmentIds": sorted(set(shipment_ids)),
        "status": status,
    }


def ingest_event(data: dict, payload: dict) -> dict:
    for key in ("eventId", "eventType", "sourceName", "observedAt"):
        if not payload.get(key):
            raise ValueError(f"Нужно поле: {key}")

    event_id = str(payload["eventId"]).strip()
    event_type = str(payload["eventType"]).strip()
    source_name = str(payload["sourceName"]).strip()
    source_kind = str(payload.get("sourceKind") or "live").strip()
    observed = _observed(payload)
    moment = _now()
    if observed - moment > MAX_FUTURE_SKEW:
        raise ValueError("observedAt в будущем: наблюдение ещё не могло произойти")

    telemetry = ensure_telemetry(data)
    if event_id in telemetry["events"]:
        return {
            "status": "duplicate",
            "eventId": event_id,
            "message": "Событие уже учтено",
            "record": telemetry["events"][event_id],
        }

    applied_shipments: list[str] = []
    try:
        if event_type in ("rail.delay", "rail.eta"):
            applied_shipments = _apply_rail(data, telemetry, payload, observed, event_id, source_name, source_kind)
        elif event_type in ("port.status", "port.departure", "port.restriction"):
            applied_shipments = _apply_port(
                data, telemetry, payload, observed, event_id, source_name, source_kind, event_type=event_type
            )
        elif event_type == "carrier.stage_completed":
            applied_shipments = _apply_stage_completed(data, telemetry, payload, observed, event_id, source_name, source_kind)
        else:
            raise ValueError(f"Неизвестный тип события: {event_type}")
    except StaleEvent as exc:
        _record_event(telemetry, event_id, event_type, source_name, source_kind, observed, moment, [], "stale")
        _journal(data, payload.get("shipmentId"), "Оперативное сообщение отклонено как устаревшее",
                 f"{source_name} · {event_type} · id={event_id}: {exc}", moment)
        return {
            "status": "stale",
            "eventId": event_id,
            "eventType": event_type,
            "message": str(exc),
            "observedAt": iso(observed),
        }

    telemetry["externalConnected"] = source_kind == "live"
    telemetry["lastUpdatedAt"] = iso(observed)
    _record_event(telemetry, event_id, event_type, source_name, source_kind, observed, moment, applied_shipments, "applied")

    _journal(
        data,
        applied_shipments[0] if len(applied_shipments) == 1 else None,
        "Оперативное сообщение",
        f"{source_name} · {event_type} · id={event_id}",
        moment,
    )
    recalculate(data, moment)

    return {
        "status": "applied",
        "eventId": event_id,
        "eventType": event_type,
        "shipmentIds": sorted(set(applied_shipments)),
        "observedAt": iso(observed),
        "sourceName": source_name,
        "sourceKind": source_kind,
        "externalConnected": telemetry["externalConnected"],
    }


def _apply_rail(data, telemetry, payload, observed, event_id, source_name, source_kind) -> list[str]:
    shipment_id = payload.get("shipmentId")
    if not shipment_id:
        raise ValueError("Для ЖД-события нужен shipmentId")
    shipment = _find_shipment(data, str(shipment_id))
    route = _find_route(data, shipment)
    stage = _find_stage(route, payload.get("stageId"), payload.get("transportType") or "rail")
    _require_open_stage(stage, "rail")

    delay_hours = _number(payload, "delayHours", 0, MAX_DELAY_HOURS)
    eta = _timestamp(payload, "estimatedArrivalAt")
    if eta is None and delay_hours is None:
        raise ValueError("Укажите estimatedArrivalAt или delayHours")
    ensure_schedule_fields(stage)
    if eta is not None:
        planned = parse_dt(stage["schedulePlannedArrival"] or stage["plannedArrival"])
        delay_hours = max(0.0, (eta - planned).total_seconds() / 3600) if planned else 0.0
        if delay_hours > MAX_DELAY_HOURS:
            raise ValueError("Уточнённое прибытие слишком далеко от плана")

    rail_key = f"{stage['location']}|{stage['nextLocation']}"
    if _feed_is_stale(telemetry["railFeed"].get(rail_key, {}), observed):
        raise StaleEvent("Сообщение устарело: по участку уже есть более свежие данные")
    _guard_stage(telemetry, stage, observed)

    _record_feed(
        telemetry["railFeed"],
        rail_key,
        {
            "sourceName": source_name,
            "sourceKind": source_kind,
            "delayHours": round(delay_hours, 2),
            "delayMinutes": int(round(delay_hours * 60)),
            "estimatedArrivalAt": iso(eta) if eta else None,
        },
        observed,
    )
    stage["delayHours"] = round(delay_hours, 2)
    stage["status"] = "delayed" if delay_hours > 0 else "in_progress"
    sync_stage_chain(route, route["stages"].index(stage) + 1)
    shipment["status"] = "delayed" if delay_hours > 0 else "in_transit"
    shipment["currentLocation"] = f"перегон {stage['location']} — {stage['nextLocation']}"
    shipment["currentTransport"] = "rail"
    shipment["currentPort"] = None
    _mark_stage(telemetry, stage, observed, event_id, source_name, source_kind)

    expected = rail_expected_arrival(stage)
    arrival_text = iso(expected) if expected else "—"
    note = payload.get("note") or payload.get("message") or "Уточнено время прибытия поезда"
    _append_history(
        shipment,
        observed=observed,
        location=f"{stage['location']} → {stage['nextLocation']}",
        transport="rail",
        description=f"{source_name}: {note}. Прибытие {arrival_text}, отставание {delay_hours:g} ч",
        status="delayed" if delay_hours > 0 else "in_progress",
        source_name=source_name,
        source_kind=source_kind,
        event_id=event_id,
    )
    return [shipment["id"]]


def _apply_port(
    data,
    telemetry,
    payload,
    observed,
    event_id,
    source_name,
    source_kind,
    *,
    event_type: str,
) -> list[str]:
    port_name = payload.get("portName")
    if not port_name or port_name not in PORT_NAMES:
        raise ValueError("Укажите существующий portName")
    port = _port(data, str(port_name))
    workload = _number(payload, "workload", 0, 100) if payload.get("workload") is not None else None
    wind = _number(payload, "windSpeed", 0, 60) if payload.get("windSpeed") is not None else None
    ship_departure = _timestamp(payload, "shipDeparture") if payload.get("shipDeparture") else None
    if payload.get("shipmentId"):
        _find_shipment(data, str(payload["shipmentId"]))

    existing = telemetry["portFeed"].get(str(port_name), {})
    if _feed_is_stale(existing, observed):
        raise StaleEvent("Сообщение устарело: по порту уже есть более свежие данные")

    targets = _shipments_at_port(data, str(port_name))
    if payload.get("shipmentId"):
        targets = [t for t in targets if t[0]["id"] == payload["shipmentId"]]
    sea_targets: list[tuple[dict, dict, dict]] = []
    if ship_departure:
        for shipment, route, stage in targets:
            if stage.get("transportType") == "sea" and stage["location"] == port_name and stage["status"] == "pending":
                _guard_stage(telemetry, stage, observed)
                sea_targets.append((shipment, route, stage))
        if payload.get("shipmentId") and not sea_targets:
            raise ValueError("У груза нет ожидающего морского этапа из этого порта")

    note = payload.get("delayNote") or payload.get("restrictionNote") or payload.get("message")
    incoming: dict = {
        "sourceName": source_name,
        "sourceKind": source_kind,
    }
    if workload is not None:
        incoming["workload"] = workload
    if wind is not None:
        incoming["windSpeed"] = wind
    if note:
        incoming["delayNote"] = note
    if ship_departure:
        incoming["shipDeparture"] = iso(ship_departure)

    departure_fields = parse_departure_payload(payload, event_type)
    if departure_fields:
        incoming.update(departure_fields)
        if departure_fields.get("departureStatus") == DEPARTURE_CLOSED and "restrictionEndsAt" not in payload and not payload.get("restrictionEndsAt"):
            incoming["restrictionEndsAt"] = None
    elif event_type == "port.restriction" and note:
        incoming.update(
            {
                "departureStatus": DEPARTURE_CLOSED,
                "restrictionNote": note,
            }
        )

    telemetry["portFeed"][str(port_name)] = merge_port_feed(existing, incoming, observed)
    feed = telemetry["portFeed"][str(port_name)]

    if workload is not None:
        port["workload"] = workload
    if wind is not None:
        port["windSpeed"] = wind
        port["weatherSeverity"] = "adverse" if wind >= 15 else "clear"

    moment = observed
    applied: list[str] = []
    for shipment, route, _stage in targets:
        if apply_stage_restrictions(route, feed, str(port_name), moment):
            pass
        if shipment["id"] not in applied:
            applied.append(shipment["id"])

    for shipment, route, stage in sea_targets:
        stage["shipDeparture"] = iso(ship_departure)
        _mark_stage(telemetry, stage, observed, event_id, source_name, source_kind)

    view = feed_departure_view(feed, moment=moment)
    if view["departureStatus"] == DEPARTURE_CLOSED:
        description = view.get("restrictionNote") or note or "Выход судов из порта закрыт"
        if view.get("restrictionEndsAt"):
            description += f" до {view['restrictionEndsAt']}"
        else:
            description += " (срок открытия не указан)"
    elif view["departureStatus"] == DEPARTURE_OPEN and departure_fields:
        description = view.get("restrictionNote") or note or "Выход судов из порта открыт"
    else:
        description = note or "Обновление статуса порта"
        if workload is not None:
            description += f", загрузка {workload:g}%"
        if ship_departure:
            description += f", отправление судна {iso(ship_departure)}"

    for shipment_id in applied:
        shipment = _find_shipment(data, shipment_id)
        _append_history(
            shipment,
            observed=observed,
            location=str(port_name),
            transport="sea",
            description=f"{source_name}: {description}",
            status=shipment["status"],
            source_name=source_name,
            source_kind=source_kind,
            event_id=event_id,
        )
    return applied


def _apply_stage_completed(data, telemetry, payload, observed, event_id, source_name, source_kind) -> list[str]:
    shipment_id = payload.get("shipmentId")
    if not shipment_id:
        raise ValueError("Нужен shipmentId")
    shipment = _find_shipment(data, str(shipment_id))
    route = _find_route(data, shipment)
    stage = _find_stage(route, payload.get("stageId"), payload.get("transportType"))
    if stage["status"] == "completed":
        raise ValueError("Этап уже завершён")
    idx = route["stages"].index(stage)
    if any(previous["status"] != "completed" for previous in route["stages"][:idx]):
        raise ValueError("Нельзя завершить этап, пока не завершены предыдущие")
    _guard_stage(telemetry, stage, observed)

    ensure_schedule_fields(stage)
    stage["status"] = "completed"
    stage["actualArrival"] = iso(observed)
    planned = parse_dt(stage["schedulePlannedArrival"] or stage["plannedArrival"])
    stage["delayHours"] = round(max(0.0, (observed - planned).total_seconds() / 3600), 2) if planned else 0
    sync_stage_chain(route, idx + 1)
    _mark_stage(telemetry, stage, observed, event_id, source_name, source_kind)

    if idx + 1 < len(route["stages"]):
        nxt = route["stages"][idx + 1]
        nxt["status"] = "in_progress" if nxt["transportType"] != "sea" else "pending"
        shipment["status"] = "in_transit"
        shipment["currentTransport"] = nxt["transportType"]
        shipment["currentLocation"] = nxt["location"]
        shipment["currentPort"] = nxt["location"] if nxt["location"] in PORT_NAMES else None
    else:
        shipment["status"] = "delivered"
        shipment["currentTransport"] = "none"
        shipment["currentLocation"] = stage["nextLocation"]
        shipment["currentPort"] = stage["nextLocation"] if stage["nextLocation"] in PORT_NAMES else None

    _append_history(
        shipment,
        observed=observed,
        location=f"{stage['location']} → {stage['nextLocation']}",
        transport=stage["transportType"],
        description=f"{source_name}: этап завершён",
        status="completed",
        source_name=source_name,
        source_kind=source_kind,
        event_id=event_id,
    )
    return [shipment["id"]]


def simulate_port_departure_closed(
    data: dict,
    *,
    port_name: str,
    restriction_ends_at: str | None = None,
    note: str = "Порт закрыт для выхода судов",
) -> dict:
    event_id = f"sim-port-close-{port_name}-{iso(_now()).replace(':', '')}"
    payload = {
        "eventId": event_id,
        "eventType": "port.restriction",
        "sourceName": "Порт (симуляция для защиты)",
        "sourceKind": "simulation",
        "observedAt": iso(_now()),
        "portName": port_name,
        "departureStatus": DEPARTURE_CLOSED,
        "restrictionNote": note,
        "restrictionStartsAt": iso(_now()),
    }
    if restriction_ends_at:
        payload["restrictionEndsAt"] = restriction_ends_at
    return ingest_event(data, payload)


def simulate_port_departure_open(data: dict, *, port_name: str) -> dict:
    event_id = f"sim-port-open-{port_name}-{iso(_now()).replace(':', '')}"
    return ingest_event(
        data,
        {
            "eventId": event_id,
            "eventType": "port.restriction",
            "sourceName": "Порт (симуляция для защиты)",
            "sourceKind": "simulation",
            "observedAt": iso(_now()),
            "portName": port_name,
            "departureStatus": DEPARTURE_OPEN,
            "restrictionNote": "Выход судов из порта открыт",
        },
    )


def simulate_rail_miss_ferry(data: dict, shipment_id: str) -> dict:
    """Демо для защиты: поезд не успевает на паром."""
    shipment = _find_shipment(data, shipment_id)
    route = _find_route(data, shipment)
    rail = _find_stage(route, None, "rail")
    event_id = f"sim-rail-{shipment_id}-{rail['id']}-52h"
    return ingest_event(
        data,
        {
            "eventId": event_id,
            "eventType": "rail.delay",
            "sourceName": "РЖД (симуляция для защиты)",
            "sourceKind": "simulation",
            "observedAt": iso(_now()),
            "shipmentId": shipment_id,
            "stageId": rail["id"],
            "delayHours": 52,
            "note": "Поезд прибудет после отправления парома; окно пересадки потеряно",
        },
    )


def infrastructure_status(data: dict) -> dict:
    telemetry = ensure_telemetry(data)
    port_feed = telemetry.get("portFeed") or {}
    rail_feed = telemetry.get("railFeed") or {}

    ports: list[dict] = []
    for name, feed in port_feed.items():
        base = _port(data, name)
        view = feed_departure_view(feed)
        ports.append(
            {
                "name": name,
                "workload": feed.get("workload", base.get("workload")),
                "waitingShipments": None,
                "delayNote": feed.get("delayNote") or base.get("delayNote"),
                "departureStatus": view.get("departureStatus"),
                "restrictionStartsAt": view.get("restrictionStartsAt"),
                "restrictionEndsAt": view.get("restrictionEndsAt"),
                "restrictionNote": view.get("restrictionNote"),
                "sourceKind": feed.get("sourceKind") or "live",
                "sourceName": feed.get("sourceName") or "Оперативный источник",
                "observedAt": feed.get("observedAt"),
            }
        )

    rail: list[dict] = []
    for key, feed in rail_feed.items():
        from_name, to_name = key.split("|", 1)
        delay_hours = feed.get("delayHours")
        delay_minutes = feed.get("delayMinutes")
        if delay_minutes is None and delay_hours is not None:
            delay_minutes = int(round(float(delay_hours) * 60))
        rail.append(
            {
                "from": from_name,
                "to": to_name,
                "workload": feed.get("workload"),
                "delayMinutes": delay_minutes,
                "sourceName": feed.get("sourceName") or "Оперативный источник",
                "observedAt": feed.get("observedAt"),
                "sourceKind": feed.get("sourceKind") or "live",
            }
        )

    return {
        "ports": ports,
        "rail": rail,
        "externalConnected": bool(telemetry.get("externalConnected")),
        "lastUpdatedAt": telemetry.get("lastUpdatedAt"),
    }
