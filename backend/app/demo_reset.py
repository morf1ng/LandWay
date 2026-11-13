"""Воспроизводимая подготовка демо: даты сдвигаются к текущему моменту, файлы создаются заново."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.catalog import PORTS
from app.models import (
    DocumentRow,
    JournalRow,
    NotificationRow,
    PortRow,
    RiskPredictionRow,
    RouteRow,
    RouteStageRow,
    ShipmentRow,
)

DEMO_BASE = datetime(2026, 11, 12, 10, 0, 0)
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def demo_anchor() -> datetime:
    raw = os.getenv("SCT_DEMO_ANCHOR")
    if raw:
        return datetime.fromisoformat(raw)
    return datetime.now().replace(minute=0, second=0, microsecond=0)


def _shift(value, delta: timedelta):
    if isinstance(value, dict):
        return {key: _shift(item, delta) for key, item in value.items()}
    if isinstance(value, list):
        return [_shift(item, delta) for item in value]
    if isinstance(value, str):
        if _DATETIME.match(value):
            return (datetime.fromisoformat(value) + delta).isoformat()
        if _DATE.match(value):
            return (datetime.fromisoformat(value) + delta).date().isoformat()
    return value


def shifted_demo_payload(anchor: datetime | None = None) -> dict:
    from app.demo_data import build_demo_payload

    delta = (anchor or demo_anchor()) - DEMO_BASE
    return _shift(build_demo_payload(), delta)


def write_demo_files(documents: list[dict], uploads_dir: Path) -> int:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for document in documents:
        meta = document.get("file")
        if not meta:
            continue
        path = uploads_dir / meta["storedName"]
        if path.exists():
            continue
        path.write_text(
            f"Демонстрационный документ: {document['name']}\nГруз: {document['shipmentId']}\n",
            encoding="utf-8",
        )
        written += 1
    return written


def apply_demo(data: dict, uploads_dir: Path, anchor: datetime | None = None) -> dict:
    """Заменяет грузы, маршруты, документы и оперативное состояние на демо-набор."""
    from app.data.corridor_history import synthetic_corridor_history
    from app.services.engine import recalculate

    moment = anchor or demo_anchor()
    demo = shifted_demo_payload(moment)
    data["shipments"] = demo["shipments"]
    data["routes"] = demo["routes"]
    data["documents"] = demo["documents"]
    data["journal"] = demo["journal"]
    data["notifications"] = []
    data["scenarioNotices"] = []
    data["predictions"] = []
    data["ports"] = [
        {
            "id": port["id"],
            "name": port["name"],
            "location": port["location"],
            "lat": port["lat"],
            "lon": port["lon"],
            "x": port["x"],
            "y": port["y"],
            "workload": port["workload"],
            "weather": port["weather"],
            "weatherSeverity": port["weatherSeverity"],
            "windSpeed": port["windSpeed"],
            "delayRisk": port["delayRisk"],
        }
        for port in PORTS
    ]
    data["corridorChain"] = []
    data["preliminaryReviewCache"] = {}
    data["corridorHistory"] = synthetic_corridor_history()
    data["telemetry"] = {
        "events": {},
        "portFeed": {},
        "railFeed": {},
        "externalConnected": False,
        "lastUpdatedAt": None,
    }
    write_demo_files(data["documents"], uploads_dir)
    recalculate(data, moment)
    return {"anchor": moment.isoformat(), "shipments": len(data["shipments"])}


def reset_database(session: Session, uploads_dir: Path, anchor: datetime | None = None) -> dict:
    from app.persistence.mapper import load_state, save_state

    session.execute(delete(NotificationRow))
    session.execute(delete(RiskPredictionRow))
    session.execute(delete(RouteStageRow))
    session.execute(delete(RouteRow))
    session.execute(delete(DocumentRow))
    session.execute(delete(JournalRow))
    session.execute(delete(ShipmentRow))
    session.execute(delete(PortRow))
    session.commit()

    data = load_state(session)
    result = apply_demo(data, uploads_dir, anchor)
    save_state(session, data)
    session.commit()
    return result
