from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.catalog import REQUIRED_DOCUMENT_TYPES
from app.services.corridor_contract import execute, status, verify


class CorridorContractTests(TestCase):
    def make_data(self, directory: Path, missing: str | None = None) -> dict:
        documents = []
        for type_id in REQUIRED_DOCUMENT_TYPES:
            file_name = f"{type_id}.txt"
            if type_id != missing:
                (directory / file_name).write_text(f"demo-{type_id}", encoding="utf-8")
            documents.append({
                "id": f"doc-1-{type_id}", "shipmentId": "SCT-1", "name": type_id,
                "type": type_id, "file": None if type_id == missing else {"storedName": file_name},
                "fields": {"number": "1", "issuedAt": "2026-11-12"},
            })
        return {"shipments": [{"id": "SCT-1"}], "documents": documents, "corridorChain": []}

    def test_ready_block_and_change_detection(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            data = self.make_data(directory)
            first = execute(data, "SCT-1", directory, "Логист")
            self.assertEqual(first["latestBlock"]["decision"], "ready_for_review")
            self.assertTrue(first["chain"]["valid"])
            self.assertTrue(first["snapshotMatches"])
            (directory / "invoice.txt").write_text("changed", encoding="utf-8")
            self.assertFalse(status(data, "SCT-1", directory)["snapshotMatches"])
            second = execute(data, "SCT-1", directory, "Логист")
            self.assertEqual(second["chain"]["height"], 2)
            self.assertTrue(second["snapshotMatches"])
            self.assertEqual(data["corridorChain"][1]["previousHash"], data["corridorChain"][0]["hash"])

    def test_incomplete_package_is_not_ready(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            data = self.make_data(directory, missing="origin")
            result = execute(data, "SCT-1", directory, "Логист")
            self.assertFalse(result["ready"])
            self.assertEqual(result["latestBlock"]["decision"], "needs_correction")
            self.assertFalse(any(problem.startswith("Файл недоступен") for problem in result["problems"]))

    def test_tamper_blocks_new_writes(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            data = self.make_data(directory)
            execute(data, "SCT-1", directory, "Логист")
            data["corridorChain"][0]["decision"] = "needs_correction"
            self.assertFalse(verify(data["corridorChain"])["valid"])
            with self.assertRaisesRegex(ValueError, "Цепочка повреждена"):
                execute(data, "SCT-1", directory, "Логист")

    def test_history_and_count_belong_to_selected_shipment(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            data = self.make_data(directory)
            data["shipments"].append({"id": "SCT-2"})
            execute(data, "SCT-1", directory, "Логист")
            execute(data, "SCT-2", directory, "Логист")
            first = status(data, "SCT-1", directory)
            second = status(data, "SCT-2", directory)
            self.assertEqual(first["shipmentBlockCount"], 1)
            self.assertEqual(second["shipmentBlockCount"], 1)
            self.assertEqual(first["chain"]["height"], 2)
            self.assertEqual([block["shipmentId"] for block in first["recentBlocks"]], ["SCT-1"])
            self.assertEqual([block["shipmentId"] for block in second["recentBlocks"]], ["SCT-2"])
