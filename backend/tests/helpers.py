from datetime import datetime
from pathlib import Path

from app.catalog import DEFAULT_EMISSION_FACTORS
from app.demo_reset import apply_demo

ANCHOR = datetime(2026, 11, 12, 10, 0, 0)


def demo_state(uploads_dir: Path) -> dict:
    data = {
        "shipments": [],
        "routes": [],
        "documents": [],
        "journal": [],
        "notifications": [],
        "predictions": [],
        "ports": [],
        "emissionFactors": dict(DEFAULT_EMISSION_FACTORS),
    }
    apply_demo(data, uploads_dir, ANCHOR)
    return data


def shipment(data: dict, shipment_id: str) -> dict:
    return next(item for item in data["shipments"] if item["id"] == shipment_id)


def route(data: dict, shipment_id: str) -> dict:
    found = shipment(data, shipment_id)
    return next(item for item in data["routes"] if item["id"] == found["routeId"])


def prediction(data: dict, shipment_id: str) -> dict:
    return next(item for item in data["predictions"] if item["shipmentId"] == shipment_id)
