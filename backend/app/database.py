"""Подключение PostgreSQL подготовлено, но в прототипе не включается.

Хранилище сейчас — файл backend/data/store.json.
Когда появится база, создайте движок от DATABASE_URL и замените JsonStore
на репозиторий поверх моделей из app.models. Схема таблиц уже описана.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://sct:sct@localhost:5432/smart_caspian_transit",
)

# Прототип работает на тестовых данных. Движок не создаём, чтобы
# отсутствие PostgreSQL и драйвера не мешало запуску.
ENGINE = None
SessionLocal = None
DB_ENABLED = False


def connect_later() -> None:
    """Точка включения базы. Не вызывается в демонстрационном режиме."""
    global ENGINE, SessionLocal, DB_ENABLED
    ENGINE = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)
    Base.metadata.create_all(ENGINE)
    DB_ENABLED = True
