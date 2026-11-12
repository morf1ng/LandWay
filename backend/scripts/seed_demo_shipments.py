"""Загрузить 6 тестовых грузов в БД (даже если таблица не пустая — осторожно)."""

from __future__ import annotations

import sys

from sqlalchemy import delete

from app.database import SessionLocal, init_db
from app.demo_data import build_demo_payload
from app.models import (
    DocumentRow,
    JournalRow,
    NotificationRow,
    RiskPredictionRow,
    RouteRow,
    RouteStageRow,
    ShipmentRow,
)
from app.persistence.mapper import load_state, save_state
from app.services.engine import recalculate


def replace_all() -> None:
    from app.database import ENGINE
    from app.models import Base

    Base.metadata.create_all(ENGINE)
    with SessionLocal() as session:
        session.execute(delete(NotificationRow))
        session.execute(delete(RiskPredictionRow))
        session.execute(delete(RouteStageRow))
        session.execute(delete(RouteRow))
        session.execute(delete(DocumentRow))
        session.execute(
            delete(JournalRow).where(JournalRow.type != "auth")
        )
        session.execute(delete(ShipmentRow))
        session.commit()

        data = load_state(session)
        demo = build_demo_payload()
        data["shipments"] = demo["shipments"]
        data["routes"] = demo["routes"]
        data["documents"] = demo["documents"]
        data["journal"] = demo["journal"] + [j for j in data.get("journal", []) if j.get("type") == "auth"]
        recalculate(data)
        save_state(session, data)
        session.commit()
        print("Добавлено грузов:", len(demo["shipments"]))


if __name__ == "__main__":
    replace_all()
