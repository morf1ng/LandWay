"""Единая точка пересчёта: прогноз, срок, углеродный след, предупреждения."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.alerts import sync_notifications
from app.services.carbon import calculate
from app.services.risk import assess, iso, parse_dt
from app.services.routing import route_duration_hours


def route_of(data: dict, shipment: dict) -> dict:
    return next(item for item in data["routes"] if item["id"] == shipment["routeId"])


def documents_of(data: dict, shipment_id: str) -> list[dict]:
    return [item for item in data["documents"] if item["shipmentId"] == shipment_id]


def recalculate(data: dict, now: datetime | None = None) -> dict:
    moment = now or datetime.now().replace(microsecond=0)
    factors = data["emissionFactors"]
    predictions = []
    for shipment in data["shipments"]:
        route = route_of(data, shipment)
        result = assess(shipment, route, data["ports"], documents_of(data, shipment["id"]), moment)
        carbon = calculate(float(shipment["weight"]), route["stages"], factors)
        route["carbonFootprint"] = carbon["total"]
        route["distance"] = round(sum(float(stage["distanceKm"]) for stage in route["stages"]), 1)
        route["estimatedDuration"] = route_duration_hours(route)
        shipment["riskScore"] = result["probability"]
        if shipment["status"] == "delivered":
            shipment["predictedArrival"] = shipment.get("predictedArrival") or shipment["plannedArrival"]
        else:
            planned = parse_dt(shipment["plannedArrival"])
            if planned is None:
                shipment["predictedArrival"] = shipment["plannedArrival"]
            else:
                shipment["predictedArrival"] = iso(planned + timedelta(hours=result["estimatedDelay"]))
        predictions.append(
            {
                "id": f"pred-{shipment['id']}",
                "shipmentId": shipment["id"],
                "probability": result["probability"],
                "riskLevel": result["riskLevel"],
                "reasons": result["reasons"],
                "estimatedDelay": result["estimatedDelay"],
                "recommendation": result["recommendation"],
                "calculatedAt": result["calculatedAt"],
            }
        )
        shipment["updatedAt"] = iso(moment)
    data["predictions"] = predictions
    data["lastRecalculatedAt"] = iso(moment)
    sync_notifications(data, moment)
    return data
