"""Сборка маршрутов из шаблонов и сравнение альтернатив."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.catalog import CITIES, PORTS, ROUTE_TEMPLATES, place, sea_distance, template_by_id
from app.services.carbon import calculate
from app.services.risk import assess, iso, parse_dt


def known_place(name: str) -> bool:
    if any(port["name"] == name for port in PORTS):
        return True
    return name in CITIES


def template_is_valid(template: dict) -> bool:
    stages = template.get("stages") or []
    if len(stages) < 2:
        return False
    for stage in stages:
        if stage["transport"] not in ("rail", "sea", "road"):
            return False
        if not known_place(stage["from"]) or not known_place(stage["to"]):
            return False
    return True


def materialize(template: dict, departure: datetime, route_id: str, shipment_id: str) -> dict:
    if not template_is_valid(template):
        raise ValueError("У альтернативы нет необходимых точек и этапов")
    cursor = departure
    stages = []
    for index, spec in enumerate(template["stages"], start=1):
        start = cursor
        if spec["transport"] == "sea":
            buffer_hours = float(spec.get("bufferHours") or 10)
            ship_at = start + timedelta(hours=buffer_hours)
            end = ship_at + timedelta(hours=float(spec["hours"]))
            ship_departure = iso(ship_at)
        else:
            end = start + timedelta(hours=float(spec["hours"]))
            ship_departure = None
        stages.append(
            {
                "id": f"{route_id}-{index}",
                "routeId": route_id,
                "location": spec["from"],
                "nextLocation": spec["to"],
                "transportType": spec["transport"],
                "plannedStart": iso(start),
                "plannedArrival": iso(end),
                "actualArrival": None,
                "status": "pending",
                "distanceKm": spec["distanceKm"],
                "delayHours": 0,
                "shipDeparture": ship_departure,
                "description": spec["description"],
            }
        )
        cursor = end
    distance = sum(stage["distanceKm"] for stage in stages)
    duration = round((cursor - departure).total_seconds() / 3600, 1)
    return {
        "id": route_id,
        "shipmentId": shipment_id,
        "name": template["name"],
        "templateId": template["id"],
        "origin": template["origin"],
        "destination": template["destination"],
        "stages": stages,
        "distance": distance,
        "estimatedDuration": duration,
        "estimatedCost": template["cost"],
        "carbonFootprint": 0,
    }


def generic_template(origin: str, destination: str, sequence: list[str]) -> dict:
    sail = sea_distance(origin, destination)
    sea = {
        "from": origin,
        "to": destination,
        "transport": "sea",
        "distanceKm": sail,
        "hours": 50,
        "bufferHours": 10,
        "description": f"Морской участок {origin} — {destination}",
    }
    if sequence == ["rail", "road", "sea"]:
        stages = [
            {
                "from": "Саратов",
                "to": "Волгоград",
                "transport": "rail",
                "distanceKm": 380,
                "hours": 14,
                "bufferHours": 0,
                "description": "Железнодорожный участок",
            },
            {
                "from": "Волгоград",
                "to": origin,
                "transport": "road",
                "distanceKm": 400,
                "hours": 12,
                "bufferHours": 0,
                "description": "Автомобильный подвоз к порту",
            },
            sea,
        ]
    elif sequence and sequence[0] == "rail":
        start = "Саратов" if origin == "Астрахань" else "Волгоград"
        if start == origin:
            start = "Саратов"
        stages = [
            {
                "from": start,
                "to": origin,
                "transport": "rail",
                "distanceKm": 450,
                "hours": 18,
                "bufferHours": 0,
                "description": "Железнодорожный подвод к порту",
            },
            sea,
        ]
    else:
        start = "Каспийск" if origin == "Махачкала" else "Волгоград"
        if start == origin:
            start = "Саратов"
        stages = [
            {
                "from": start,
                "to": origin,
                "transport": "road",
                "distanceKm": 180,
                "hours": 6,
                "bufferHours": 0,
                "description": "Автомобильный подвоз к порту",
            },
            sea,
        ]
    distance = sum(item["distanceKm"] for item in stages)
    return {
        "id": "generic-" + "-".join(sequence),
        "name": "Сформированный маршрут " + " + ".join(sequence),
        "origin": origin,
        "destination": destination,
        "sequence": sequence,
        "cost": int(15000 + distance * 40),
        "stages": stages,
    }


def resolve_template(origin: str, destination: str, sequence: list[str]) -> dict:
    from app.catalog import match_template

    found = match_template(origin, destination, sequence)
    if found and template_is_valid(found):
        return found
    template = generic_template(origin, destination, sequence)
    if not template_is_valid(template):
        raise ValueError("Не удалось собрать маршрут с нужными точками")
    return template


def route_duration_hours(route: dict) -> float:
    stages = route.get("stages") or []
    if not stages:
        return 0
    start = parse_dt(stages[0]["plannedStart"])
    end = parse_dt(stages[-1]["plannedArrival"])
    if not start or not end:
        return float(route.get("estimatedDuration") or 0)
    extra = sum(float(stage.get("delayHours") or 0) for stage in stages)
    return round((end - start).total_seconds() / 3600 + extra, 1)


def preview_template(data: dict, shipment: dict, template: dict, now: datetime) -> dict:
    if not template_is_valid(template):
        raise ValueError("Маршрут не содержит необходимых точек и этапов")
    departure = parse_dt(shipment["plannedDeparture"]) or now
    route = materialize(template, departure, "preview", shipment["id"])
    ghost = {
        **shipment,
        "origin": template["origin"],
        "destination": template["destination"],
        "status": "in_transit",
        "transportSequence": template["sequence"],
    }
    documents = [doc for doc in data["documents"] if doc["shipmentId"] == shipment["id"]]
    prediction = assess(ghost, route, data["ports"], documents, now)
    carbon = calculate(float(shipment["weight"]), route["stages"], data["emissionFactors"])
    return _option(template["id"], template["name"], template["sequence"], route, prediction, carbon, current=False)


def _option(template_id, name, sequence, route, prediction, carbon, current: bool) -> dict:
    return {
        "templateId": template_id,
        "name": name,
        "current": current,
        "origin": route["origin"],
        "destination": route["destination"],
        "sequence": sequence,
        "stages": route["stages"],
        "stageCount": len(route["stages"]),
        "distance": route["distance"],
        "durationHours": route_duration_hours(route) if current else route["estimatedDuration"],
        "cost": route["estimatedCost"],
        "probability": prediction["probability"],
        "riskLevel": prediction["riskLevel"],
        "estimatedDelay": prediction["estimatedDelay"],
        "reasons": prediction["reasons"],
        "recommendation": prediction["recommendation"],
        "carbonFootprint": carbon["total"],
        "carbonByTransport": carbon["byTransport"],
        "selectable": template_is_valid({"stages": [
            {
                "from": stage["location"],
                "to": stage["nextLocation"],
                "transport": stage["transportType"],
            }
            for stage in route["stages"]
        ]}) and not current,
    }


def current_option(data: dict, shipment: dict) -> dict:
    route = next(item for item in data["routes"] if item["id"] == shipment["routeId"])
    prediction = next(item for item in data["predictions"] if item["shipmentId"] == shipment["id"])
    carbon = calculate(float(shipment["weight"]), route["stages"], data["emissionFactors"])
    template = template_by_id(route.get("templateId", ""))
    sequence = template["sequence"] if template else shipment.get("transportSequence") or []
    option = _option(route.get("templateId"), route.get("name") or "Текущий маршрут", sequence, route, prediction, carbon, current=True)
    option["durationHours"] = route_duration_hours(route)
    option["selectable"] = False
    return option


def options_for_shipment(data: dict, shipment_id: str, now: datetime | None = None) -> list[dict]:
    moment = now or datetime.now().replace(microsecond=0)
    shipment = next(item for item in data["shipments"] if item["id"] == shipment_id)
    result = [current_option(data, shipment)]
    for template in ROUTE_TEMPLATES:
        if template["destination"] != shipment["destination"]:
            continue
        if template["id"] == result[0]["templateId"]:
            continue
        if not template_is_valid(template):
            continue
        result.append(preview_template(data, shipment, template, moment))
    return result


def point_of(name: str) -> dict:
    return place(name)
