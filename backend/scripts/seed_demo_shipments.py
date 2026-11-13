"""Полный сброс демо: 6 грузов, порты, документы, реестр и телеметрия.

Даты сдвигаются так, чтобы сценарий начинался «сейчас» (или в SCT_DEMO_ANCHOR).
Внимание: удаляет все грузы и журнал в БД из DATABASE_URL.
"""

from __future__ import annotations

from app.config import UPLOADS_DIR
from app.database import ENGINE, SessionLocal
from app.demo_reset import reset_database
from app.models import Base


def replace_all() -> None:
    Base.metadata.create_all(ENGINE)
    with SessionLocal() as session:
        result = reset_database(session, UPLOADS_DIR)
    print(f"Демо подготовлено: грузов {result['shipments']}, точка отсчёта {result['anchor']}")


if __name__ == "__main__":
    replace_all()
