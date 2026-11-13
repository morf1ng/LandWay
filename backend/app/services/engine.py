"""Единая точка пересчёта: прогноз, срок, углеродный след, предупреждения."""

from __future__ import annotations

from datetime import datetime

from app.services.alerts import sync_notifications
from app.services.carbon import calculate
from app.services.risk import iso
from app.services.routing import route_duration_hours


def route_of(data: dict, shipment: dict) -> dict:
    return next(item for item in data["routes"] if item["id"] == shipment["routeId"])


def documents_of(data: dict, shipment_id: str) -> list[dict]:
    return [item for item in data["documents"] if item["shipmentId"] == shipment_id]


def recalculate(data: dict, now: datetime | None = None) -> dict:
    moment = now or datetime.now().replace(microsecond=0)
    factors = data["emissionFactors"]
    predictions = []
    from app.services.forecast import forecast
    from app.services.historical_forecast import prediction_extras

    for shipment in data["shipments"]:
        route = route_of(data, shipment)
        port_feeds = (data.get("telemetry") or {}).get("portFeed") or {}
        result = forecast(
            shipment,
            route,
            data["ports"],
            documents_of(data, shipment["id"]),
            data.get("corridorHistory"),
            moment,
            port_feeds=port_feeds,
        )
        carbon = calculate(float(shipment["weight"]), route["stages"], factors)
        route["carbonFootprint"] = carbon["total"]
        route["distance"] = round(sum(float(stage["distanceKm"]) for stage in route["stages"]), 1)
        route["estimatedDuration"] = route_duration_hours(route)
        shipment["riskScore"] = result["probability"]
        shipment["predictedArrival"] = result.get("predictedArrival")
        prediction_row = {
            "id": f"pred-{shipment['id']}",
            "shipmentId": shipment["id"],
            "probability": result["probability"],
            "riskLevel": result["riskLevel"],
            "reasons": result["reasons"],
            "estimatedDelay": result.get("estimatedDelay"),
            "recommendation": result["recommendation"],
            "calculatedAt": result["calculatedAt"],
        }
        prediction_row.update(prediction_extras(result))
        if result.get("etaUnknown"):
            prediction_row["etaUnknown"] = True
        if result.get("portRestrictions"):
            prediction_row["portRestrictions"] = result["portRestrictions"]
        predictions.append(prediction_row)
        shipment["updatedAt"] = iso(moment)
    data["predictions"] = predictions
    data["lastRecalculatedAt"] = iso(moment)
    sync_notifications(data, moment)
    return data
