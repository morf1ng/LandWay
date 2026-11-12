"""Файловое хранилище прототипа. Переживает перезагрузку страницы и сервера."""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

from app.seed import build_seed
from app.services.auth import ensure_auth_fields, prune_sessions
from app.services.engine import recalculate

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "store.json"


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            ensure_auth_fields(data)
            prune_sessions(data)
            return data
        data = build_seed()
        ensure_auth_fields(data)
        recalculate(data)
        self._flush(data)
        return data

    def _flush(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def read(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)

    def update(self, mutator) -> dict:
        with self._lock:
            draft = copy.deepcopy(self._data)
            mutator(draft)
            self._flush(draft)
            self._data = draft
            return copy.deepcopy(draft)


store = JsonStore(DATA_PATH)
