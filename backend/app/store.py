"""Хранилище приложения в PostgreSQL."""

from __future__ import annotations

import copy
import threading

from app.database import SessionLocal
from app.persistence.mapper import load_state, save_state
from app.services.auth import ensure_auth_fields, prune_sessions


class PostgresStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def read(self) -> dict:
        with self._lock:
            with SessionLocal() as session:
                data = load_state(session)
                ensure_auth_fields(data)
                prune_sessions(data)
                return data

    def update(self, mutator) -> dict:
        with self._lock:
            with SessionLocal() as session:
                draft = load_state(session)
                ensure_auth_fields(draft)
                mutator(draft)
                prune_sessions(draft)
                save_state(session, draft)
                session.commit()
                return copy.deepcopy(draft)


store = PostgresStore()
