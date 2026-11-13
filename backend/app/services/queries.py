"""Сборки ответов для страниц. Считают производные поля, не хранят отдельные копии."""

from __future__ import annotations

from datetime import datetime

from app.catalog import CITIES, DOCUMENT_TYPES, PORTS, ROUTE_TEMPLATES, STATUSES, TRANSPORT_TYPES, document_label
from app.services.carbon import calculate
from app.services.risk import assess, iso
from app.services.routing import materialize, options_for_shipment, point_of, template_is_valid


def _prediction(data: dict, shipment_id: str) -> dict:
    return next(item for item in data["predictions"] if item["shipmentId"] == shipment_id)


def _route(data: dict, shipment: dict) -> dict:
    return next(item for item in data["routes"] if item["id"] == shipment["routeId"])


def view_shipment(data: dict, shipment: dict) -> dict:
    prediction = _prediction(data, shipment["id"])
    route = _route(data, shipment)
    return {
        **shipment,
        "riskLevel": prediction["riskLevel"],
        "probability": prediction["probability"],
        "riskReasons": prediction["reasons"],
        "recommendation": prediction["recommendation"],
        "estimatedDelay": prediction["estimatedDelay"],
        "calculatedAt": prediction["calculatedAt"],
        "routeName": route["name"],
        "distance": route["distance"],
        "estimatedDuration": route["estimatedDuration"],
        "estimatedCost": route["estimatedCost"],
        "carbonFootprint": route["carbonFootprint"],
    }


def history_of(shipment: dict, route: dict) -> list[dict]:
    events = []
    for stage in route["stages"]:
        events.append(
            {
                "time": stage.get("actualArrival") or stage["plannedStart"],
                "location": f"{stage['location']} → {stage['nextLocation']}",
                "transport": stage["transportType"],
                "description": stage["description"],
                "status": stage["status"],
            }
        )
    events.extend(shipment.get("extraEvents") or [])
    events.sort(key=lambda item: item["time"])
    return events


def infrastructure_status(data: dict) -> dict:
    from app.services.telemetry import infrastructure_status as build_status

    return build_status(data)


def dashboard(data: dict) -> dict:
    views = [view_shipment(data, shipment) for shipment in data["shipments"]]
    def count(pred) -> int:
        return sum(1 for item in views if pred(item))

    ports = []
    for port in data["ports"]:
        waiting = count(lambda item, name=port["name"]: item["status"] != "delivered" and item.get("currentPort") == name)
        if port["weatherSeverity"] == "adverse" or port["workload"] >= 80 or port["delayRisk"] == "high":
            delay = "возможны задержки"
        elif port["workload"] >= 60:
            delay = "небольшие отклонения"
        else:
            delay = "существенных задержек не ожидается"
        ports.append({**port, "waitingShipments": waiting, "delayNote": delay})

    recent = sorted(views, key=lambda item: item["plannedDeparture"], reverse=True)[:8]
    warnings = sorted(data["notifications"], key=lambda item: {"high": 0, "medium": 1, "low": 2}.get(item["severity"], 3))
    return {
        "stats": {
            "total": len(views),
            "inTransit": count(lambda item: item["status"] in ("in_transit", "delayed")),
            "delivered": count(lambda item: item["status"] == "delivered"),
            "atRisk": count(lambda item: item["riskLevel"] in ("medium", "high")),
            "awaiting": count(lambda item: item["status"] in ("awaiting", "documents_issue")),
        },
        "recent": recent,
        "warnings": warnings,
        "ports": ports,
        "lastRecalculatedAt": data.get("lastRecalculatedAt"),
    }


def _position(shipment: dict, route: dict) -> dict:
    if shipment["status"] == "delivered":
        point = point_of(shipment["destination"])
        point["label"] = shipment["destination"]
        return point
    active = next((stage for stage in route["stages"] if stage["status"] in ("in_progress", "delayed")), None)
    if active is None:
        active = next((stage for stage in route["stages"] if stage["status"] == "pending"), route["stages"][-1])
    start = point_of(active["location"])
    end = point_of(active["nextLocation"])
    ratio = {"in_progress": 0.55, "delayed": 0.72, "completed": 1}.get(active["status"], 0)
    return {
        "name": active["location"] if ratio == 0 else f"{active['location']} → {active['nextLocation']}",
        "x": round(start["x"] + (end["x"] - start["x"]) * ratio, 2),
        "y": round(start["y"] + (end["y"] - start["y"]) * ratio, 2),
        "lat": round(start["lat"] + (end["lat"] - start["lat"]) * ratio, 4),
        "lon": round(start["lon"] + (end["lon"] - start["lon"]) * ratio, 4),
        "stageId": active["id"],
    }


def map_payload(data: dict) -> dict:
    shipments = []
    for shipment in data["shipments"]:
        route = _route(data, shipment)
        view = view_shipment(data, shipment)
        points = []
        for stage in route["stages"]:
            points.append({**point_of(stage["location"]), "role": "from", "stage": stage})
        last = route["stages"][-1]
        points.append({**point_of(last["nextLocation"]), "role": "to", "stage": last})
        shipments.append(
            {
                "id": shipment["id"],
                "name": shipment["name"],
                "status": shipment["status"],
                "origin": shipment["origin"],
                "destination": shipment["destination"],
                "riskLevel": view["riskLevel"],
                "probability": view["probability"],
                "currentTransport": shipment["currentTransport"],
                "position": _position(shipment, route),
                "points": points,
                "stages": route["stages"],
            }
        )
    places = []
    for port in data["ports"]:
        waiting = sum(1 for shipment in data["shipments"] if shipment["status"] != "delivered" and shipment.get("currentPort") == port["name"])
        places.append({**port, "kind": "port", "waitingShipments": waiting})
    for name, city in CITIES.items():
        places.append({"name": name, "kind": "city", **city, "waitingShipments": 0})
    return {
        "places": places,
        "shipments": shipments,
        "corridor": {
            "label": "МТК «Север — Юг»: транскаспийская ветвь до Индии",
            "source": "https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1892221",
            "sourceName": "Министерство портов и судоходства Индии, 2023",
            "note": "Обзорная схема узлов; линии между городами не являются точным путём судна, дороги или ЖД. Демо SCT-1006 показывает сквозную схему до Мумбаи.",
            "nodes": [
                {"name": "Санкт-Петербург", "lat": 59.9343, "lon": 30.3351, "kind": "city"},
                {"name": "Москва", "lat": 55.7558, "lon": 37.6173, "kind": "city"},
                {"name": "Астрахань", "lat": 46.35, "lon": 48.04, "kind": "port"},
                {"name": "Энзели", "lat": 37.47, "lon": 49.46, "kind": "port"},
                {"name": "Бендер-Аббас", "lat": 27.1865, "lon": 56.2808, "kind": "port"},
                {"name": "Мумбаи", "lat": 19.0760, "lon": 72.8777, "kind": "port"},
            ],
            "segments": [
                {"from": "Санкт-Петербург", "to": "Москва", "mode": "land"},
                {"from": "Москва", "to": "Астрахань", "mode": "land"},
                {"from": "Астрахань", "to": "Энзели", "mode": "sea"},
                {"from": "Энзели", "to": "Бендер-Аббас", "mode": "land"},
                {"from": "Бендер-Аббас", "to": "Мумбаи", "mode": "sea"},
            ],
        },
    }


def shipment_detail(data: dict, shipment_id: str) -> dict:
    shipment = next((item for item in data["shipments"] if item["id"] == shipment_id), None)
    if shipment is None:
        return {}
    route = _route(data, shipment)
    from app.services.telemetry import stage_sources

    carbon = calculate(float(shipment["weight"]), route["stages"], data["emissionFactors"])
    from app.services.corridor_contract import signature_of

    return {
        "shipment": view_shipment(data, shipment),
        "route": route,
        "stageSources": stage_sources(data, route),
        "prediction": _prediction(data, shipment_id),
        "documents": [item for item in data["documents"] if item["shipmentId"] == shipment_id],
        "history": history_of(shipment, route),
        "carbon": carbon,
        "contract": signature_of(data, shipment_id) or {"signed": False},
    }


def analytics(data: dict) -> dict:
    from app.services.action_playbook import build_action_plans
    from app.services.historical_forecast import CORRIDOR_LABEL, backtest_report

    rows = []
    for shipment in data["shipments"]:
        prediction = _prediction(data, shipment["id"])
        row = {
            "id": shipment["id"],
            "name": shipment["name"],
            "route": f"{shipment['origin']} → {shipment['destination']}",
            "probability": prediction["probability"],
            "riskLevel": prediction["riskLevel"],
            "reasons": prediction["reasons"],
            "estimatedDelay": prediction["estimatedDelay"],
            "predictedArrival": shipment["predictedArrival"],
            "recommendation": prediction["recommendation"],
            "calculatedAt": prediction["calculatedAt"],
        }
        for key, value in prediction.items():
            if key.startswith("history"):
                row[key] = value
        row["actionPlans"] = build_action_plans(row)
        rows.append(row)
    history_rows = data.get("corridorHistory") or []
    return {
        "disclaimer": (
            "Вероятность — это риск сорвать стыковку «поезд → паром»; задержка — на сколько часов "
            "прибытие позже контрактного срока. Для коридора ж/д → паром (Энзели) при трёх и более похожих "
            "рейсах в синтетической истории оценка задержки смешивается с эвристикой (55/45), иначе — только "
            "эвристика. История демонстрационная, не статистика перевозчика."
        ),
        "calculatedAt": data.get("lastRecalculatedAt"),
        "corridorHistory": {
            "source": "synthetic",
            "corridor": CORRIDOR_LABEL,
            "observationCount": len(history_rows),
        },
        "historyBacktest": backtest_report(data.get("corridorHistory")),
        "rows": rows,
    }


def _verified_docs() -> list[dict]:
    return [
        {"type": item["id"], "status": "verified", "file": {"storedName": "demo"}, "fields": {"number": "1", "issuedAt": "2026-11-01"}}
        for item in DOCUMENT_TYPES
    ]


def route_catalog(data: dict) -> list[dict]:
    moment = datetime(2026, 11, 12, 8, 0, 0)
    rows = []
    docs = _verified_docs()
    for template in ROUTE_TEMPLATES:
        if not template_is_valid(template):
            continue
        route = materialize(template, moment, f"cat-{template['id']}", "catalog")
        ghost = {
            "status": "in_transit",
            "origin": template["origin"],
            "destination": template["destination"],
            "weight": 1,
        }
        prediction = assess(ghost, route, data["ports"], docs, moment)
        carbon = calculate(1, route["stages"], data["emissionFactors"])
        rows.append(
            {
                "templateId": template["id"],
                "name": template["name"],
                "origin": template["origin"],
                "destination": template["destination"],
                "sequence": template["sequence"],
                "stageCount": len(template["stages"]),
                "distance": route["distance"],
                "durationHours": route["estimatedDuration"],
                "cost": template["cost"],
                "probability": prediction["probability"],
                "riskLevel": prediction["riskLevel"],
                "reasons": prediction["reasons"],
                "carbonPerTon": carbon["total"],
                "stages": [{"from": stage["from"], "to": stage["to"], "transport": stage["transport"]} for stage in template["stages"]],
            }
        )
    return rows


def ecology(data: dict, shipment_id: str | None = None, route_id: str | None = None) -> dict:
    rows = []
    for shipment in data["shipments"]:
        if shipment_id and shipment["id"] != shipment_id:
            continue
        route = _route(data, shipment)
        if route_id and route["id"] != route_id and route.get("templateId") != route_id:
            continue
        carbon = calculate(float(shipment["weight"]), route["stages"], data["emissionFactors"])
        for stage in carbon["stages"]:
            rows.append({"shipmentId": shipment["id"], "routeId": route["id"], "routeName": route["name"], **stage})
    by_transport: dict[str, float] = {}
    for row in rows:
        by_transport[row["transportType"]] = round(by_transport.get(row["transportType"], 0) + row["co2Emission"], 1)
    total = round(sum(row["co2Emission"] for row in rows), 1)
    shipment_ids = {row["shipmentId"] for row in rows}
    comparison = options_for_shipment(data, shipment_id) if shipment_id else []
    return {
        "disclaimer": "Расчёты демонстрационные и основаны на условных коэффициентах выбросов, а не на сертифицированной методике.",
        "formula": "CO₂ = масса груза в тоннах × расстояние в километрах × коэффициент транспорта",
        "factors": data["emissionFactors"],
        "factorUnit": "кг CO₂ / (т·км)",
        "total": total,
        "byTransport": by_transport,
        "shipmentCount": len(shipment_ids),
        "rows": rows,
        "comparison": comparison,
    }


def meta(data: dict) -> dict:
    return {
        "ports": [{"id": port["id"], "name": port["name"]} for port in PORTS],
        "documentTypes": DOCUMENT_TYPES,
        "transportTypes": TRANSPORT_TYPES,
        "statuses": STATUSES,
        "sequences": [
            {"id": "rail,sea", "value": ["rail", "sea"], "label": "поезд + корабль"},
            {"id": "road,sea", "value": ["road", "sea"], "label": "грузовик + корабль"},
            {"id": "rail,road,sea", "value": ["rail", "road", "sea"], "label": "поезд + грузовик + корабль"},
        ],
        "emissionFactors": data["emissionFactors"],
        "storage": "Данные хранятся в PostgreSQL. Стартовые грузы не подставляются — создавайте перевозки вручную.",
    }


def journal(data: dict) -> list[dict]:
    return list(data["journal"])
