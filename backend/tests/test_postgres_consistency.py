"""Сбой при сохранении не должен оставлять статус без записи решения (и наоборот).

Запускается только с отдельной тестовой БД:
SCT_TEST_DATABASE_URL=postgresql+psycopg2://.../smart_caspian_transit_test
"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

TEST_URL = os.getenv("SCT_TEST_DATABASE_URL", "")


@skipUnless(TEST_URL and "test" in TEST_URL.rsplit("/", 1)[-1], "нужна SCT_TEST_DATABASE_URL с тестовой БД")
class SaveFailureTests(TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.demo_reset import reset_database
        from app.models import Base

        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.uploads = Path(self.tmp.name)
        engine = create_engine(TEST_URL)
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False)
        with self.Session() as session:
            reset_database(session, self.uploads, None)

    def snapshot(self):
        from app.persistence.mapper import load_state

        with self.Session() as session:
            data = load_state(session)
        shipment = next(item for item in data["shipments"] if item["id"] == "SCT-1004")
        blocks = [item for item in data.get("corridorChain", []) if item.get("shipmentId") == "SCT-1004"]
        return shipment.get("preclearanceStatus"), len(blocks)

    def test_failed_commit_keeps_previous_state(self):
        from app.persistence.mapper import load_state, save_state
        from app.services.preliminary_review import submit

        before = self.snapshot()
        with self.Session() as session:
            data = load_state(session)
            submit(data, "SCT-1004", self.uploads, "тест")
            save_state(session, data)
            session.rollback()
        self.assertEqual(self.snapshot(), before)

        with self.Session() as session:
            data = load_state(session)
            submit(data, "SCT-1004", self.uploads, "тест")
            save_state(session, data)
            session.commit()
        status, blocks = self.snapshot()
        self.assertEqual(blocks, before[1] + 1)
        self.assertIsNotNone(status)
