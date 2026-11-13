"""Подключение PostgreSQL."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://sct:sct@localhost:5432/smart_caspian_transit",
)

ENGINE = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)
DB_ENABLED = True


def _migrate_shipment_predicted_arrival_nullable() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(ENGINE)
    columns = {item["name"]: item for item in inspector.get_columns("shipments")}
    col = columns.get("predicted_arrival")
    if col and col.get("nullable") is False:
        with ENGINE.begin() as conn:
            conn.execute(text("ALTER TABLE shipments ALTER COLUMN predicted_arrival DROP NOT NULL"))


def _migrate_route_stage_schedule() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(ENGINE)
    columns = {item["name"] for item in inspector.get_columns("route_stages")}
    statements = []
    if "schedule_planned_start" not in columns:
        statements.append("ALTER TABLE route_stages ADD COLUMN schedule_planned_start VARCHAR(40)")
    if "schedule_planned_arrival" not in columns:
        statements.append("ALTER TABLE route_stages ADD COLUMN schedule_planned_arrival VARCHAR(40)")
    if "schedule_ship_departure" not in columns:
        statements.append("ALTER TABLE route_stages ADD COLUMN schedule_ship_departure VARCHAR(40)")
    if not statements:
        return
    with ENGINE.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def init_db() -> None:
    Base.metadata.create_all(ENGINE)
    _migrate_route_stage_schedule()
    _migrate_shipment_predicted_arrival_nullable()
    from app.bootstrap import ensure_bootstrap

    with SessionLocal() as session:
        ensure_bootstrap(session)


def get_session():
    return SessionLocal()
