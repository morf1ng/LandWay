from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.catalog import REQUIRED_DOCUMENT_TYPES
from app.services.corridor_contract import status
from app.services.preliminary_review import STATUS_NEEDS, STATUS_READY, submit


class PreliminaryReviewTests(TestCase):
    def make_data(self, directory: Path, missing: str | None = None) -> dict:
        documents = []
        for type_id in REQUIRED_DOCUMENT_TYPES:
            file_name = f"{type_id}.txt"
            if type_id != missing:
                (directory / file_name).write_text(f"demo-{type_id}", encoding="utf-8")
            documents.append({
                "id": f"doc-1-{type_id}",
                "shipmentId": "SCT-1",
                "name": type_id,
                "type": type_id,
                "file": None if type_id == missing else {"storedName": file_name},
                "fields": {"number": "1", "issuedAt": "2026-11-12"},
            })
        return {
            "shipments": [
                {
                    "id": "SCT-1",
                    "status": "awaiting",
                    "routeId": "rt-1",
                    "origin": "Астрахань",
                    "destination": "Энзели",
                    "weight": 1,
                    "plannedArrival": "2026-11-20T12:00:00",
                    "plannedDeparture": "2026-11-10T08:00:00",
                }
            ],
            "documents": documents,
            "corridorChain": [],
            "journal": [],
            "predictions": [],
            "routes": [
                {
                    "id": "rt-1",
                    "shipmentId": "SCT-1",
                    "stages": [
                        {
                            "id": "st-1",
                            "transportType": "sea",
                            "status": "pending",
                            "location": "Астрахань",
                            "nextLocation": "Энзели",
                            "distanceKm": 100,
                            "delayHours": 0,
                            "plannedStart": "2026-11-10T08:00:00",
                            "plannedEnd": "2026-11-12T18:00:00",
                            "plannedArrival": "2026-11-12T18:00:00",
                        }
                    ],
                }
            ],
            "ports": [
                {
                    "name": "Астрахань",
                    "workload": 50,
                    "weatherSeverity": "clear",
                    "windSpeed": 8,
                }
            ],
            "notifications": [],
            "emissionFactors": {"rail": 0.02, "sea": 0.015, "road": 0.1},
        }

    def test_submit_sets_ready_status(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            data = self.make_data(directory)
            result = submit(data, "SCT-1", directory, "Имитатор", idempotency_key="k1")
            self.assertEqual(data["shipments"][0]["preclearanceStatus"], STATUS_READY)
            self.assertEqual(result["statusLabel"], STATUS_READY)
            self.assertTrue(result["createdBlock"])
            self.assertEqual(data["corridorChain"][0]["decision"], "ready_for_review")

    def test_incomplete_gets_correction_status(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            data = self.make_data(directory, missing="declaration")
            result = submit(data, "SCT-1", directory, "Имитатор")
            self.assertEqual(data["shipments"][0]["preclearanceStatus"], STATUS_NEEDS)
            self.assertEqual(result["statusLabel"], STATUS_NEEDS)
            self.assertGreater(len(result["problems"]), 0)

    def test_idempotency_and_duplicate_click(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            data = self.make_data(directory)
            first = submit(data, "SCT-1", directory, "Имитатор", idempotency_key="same-key")
            second = submit(data, "SCT-1", directory, "Имитатор", idempotency_key="same-key")
            self.assertEqual(len(data["corridorChain"]), 1)
            self.assertTrue(second["deduplicated"])
            self.assertEqual(first["documentDigest"], second["documentDigest"])
            again = submit(data, "SCT-1", directory, "Имитатор")
            self.assertEqual(len(data["corridorChain"]), 1)
            self.assertTrue(again["deduplicated"])

    def test_resubmit_after_fix_and_stale_detection(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            data = self.make_data(directory, missing="declaration")
            submit(data, "SCT-1", directory, "Имитатор")
            self.assertEqual(len(data["corridorChain"]), 1)
            decl = next(d for d in data["documents"] if d["type"] == "declaration")
            (directory / "declaration.txt").write_text("new", encoding="utf-8")
            decl["file"] = {"storedName": "declaration.txt"}
            submit(data, "SCT-1", directory, "Имитатор")
            self.assertEqual(len(data["corridorChain"]), 2)
            self.assertEqual(data["shipments"][0]["preclearanceStatus"], STATUS_READY)
            (directory / "declaration.txt").write_text("changed-again", encoding="utf-8")
            st = status(data, "SCT-1", directory)
            self.assertFalse(st["snapshotMatches"])
