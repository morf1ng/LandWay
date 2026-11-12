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


def init_db() -> None:
    Base.metadata.create_all(ENGINE)
    from app.bootstrap import ensure_bootstrap

    with SessionLocal() as session:
        ensure_bootstrap(session)


def get_session():
    return SessionLocal()
