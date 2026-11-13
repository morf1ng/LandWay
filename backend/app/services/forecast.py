"""Единый прогноз груза: эвристика + история коридора + ETA.

Используется и пересчётом груза, и предпросмотром альтернативных маршрутов,
чтобы сравнение и применение давали одинаковый результат.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.historical_forecast import enrich_assessment
from app.services.risk import assess, iso, parse_dt, stage_arrival
from app.services.stage_schedule import ensure_schedule_fields


def schedule_end(shipment: dict, route: dict) -> datetime | None:
    stages = route.get("stages") or []
    route_end = None
    if stages:
        last = stages[-1]
        ensure_schedule_fields(last)
        route_end = parse_dt(last.get("schedulePlannedArrival") or last.get("plannedArrival"))
    contract = parse_dt(shipment.get("plannedArrival"))
    candidates = [value for value in (route_end, contract) if value is not None]
    return max(candidates) if candidates else None


def forecast(
    shipment: dict,
    route: dict,
    ports: list[dict],
    documents: list[dict],
    history: list[dict] | None,
    moment: datetime,
    *,
    port_feeds: dict | None = None,
) -> dict:
    heuristic = assess(shipment, route, ports, documents, moment)
    result = enrich_assessment(heuristic, shipment, route, ports, history, moment)
    if port_feeds:
        from app.services.port_restrictions import enrich_assessment_with_ports

        result = enrich_assessment_with_ports(result, route, port_feeds, moment)
    if shipment.get("status") == "delivered":
        result["predictedArrival"] = shipment.get("predictedArrival") or shipment.get("plannedArrival")
        return result
    if result.get("etaUnknown"):
        result["predictedArrival"] = None
        result["estimatedDelay"] = None
        return result

    residual = float(result["estimatedDelay"])
    base = schedule_end(shipment, route)
    contract = parse_dt(shipment.get("plannedArrival"))
    if base is None:
        result["predictedArrival"] = shipment.get("plannedArrival")
        return result
    eta = base + timedelta(hours=residual)
    stages = route.get("stages") or []
    if stages:
        chain = stage_arrival(stages[-1])
        if chain and chain > eta:
            eta = chain
    result["predictedArrival"] = iso(eta)
    result["scheduleDelayHours"] = int(round(residual))
    if contract is not None:
        result["estimatedDelay"] = int(round(max(0.0, (eta - contract).total_seconds() / 3600)))
    return result
