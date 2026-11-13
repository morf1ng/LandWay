"""Пути и параметры окружения backend."""

from __future__ import annotations

import os
from pathlib import Path

UPLOADS_DIR = Path(os.getenv("SCT_UPLOADS_DIR") or Path(__file__).resolve().parents[1] / "uploads")
