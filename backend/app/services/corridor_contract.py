"""Local demo chain and deterministic pre-clearance contract rules.

The chain is stored in PostgreSQL, runs on one node, and has no external
consensus. It demonstrates immutable snapshots and contract decisions; it is
not a customs decision or a public blockchain transaction.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.documents import check_shipment_documents

GENESIS = "0" * 64
DIFFICULTY = "000"


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_hash(document: dict, uploads_dir: Path) -> str | None:
    file_info = document.get("file") or {}
    stored_name = file_info.get("storedName")
    if not stored_name:
        return None
    path = (uploads_dir / stored_name).resolve()
    if not path.is_relative_to(uploads_dir.resolve()) or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(documents: list[dict], uploads_dir: Path) -> dict:
    entries = []
    for document in sorted(documents, key=lambda item: (item["type"], item["id"])):
        entries.append({
            "id": document["id"],
            "type": document["type"],
            "number": (document.get("fields") or {}).get("number") or "",
            "issuedAt": (document.get("fields") or {}).get("issuedAt") or "",
            "fileSha256": _file_hash(document, uploads_dir),
        })
    return {"documents": entries, "digest": _hash(entries)}


def _block_hash(block: dict) -> str:
    return _hash({key: value for key, value in block.items() if key != "hash"})


def verify(chain: list[dict]) -> dict:
    previous = GENESIS
    for index, block in enumerate(chain):
        if block.get("index") != index or block.get("previousHash") != previous:
            return {"valid": False, "height": len(chain), "brokenAt": index, "reason": "Нарушена связь блоков"}
        digest = _block_hash(block)
        if block.get("hash") != digest or not digest.startswith(DIFFICULTY):
            return {"valid": False, "height": len(chain), "brokenAt": index, "reason": "Хеш блока не совпадает"}
        previous = digest
    return {"valid": True, "height": len(chain), "headHash": previous}


def status(data: dict, shipment_id: str, uploads_dir: Path) -> dict:
    shipment = next((item for item in data["shipments"] if item["id"] == shipment_id), None)
    if shipment is None:
        raise ValueError("Груз не найден")
    documents = [item for item in data["documents"] if item["shipmentId"] == shipment_id]
    # The checker mutates status/comment fields. Work on copies for read-only requests.
    checked = check_shipment_documents(json.loads(json.dumps(documents, ensure_ascii=False)))
    current = snapshot(documents, uploads_dir)
    declared_files = {item["id"] for item in documents if item.get("file")}
    unavailable_files = [item["id"] for item in current["documents"] if item["id"] in declared_files and item["fileSha256"] is None]
    problems = [*checked["problems"], *[f"Файл недоступен: {item}" for item in unavailable_files]]
    chain = data.get("corridorChain") or []
    shipment_blocks = [block for block in chain if block["shipmentId"] == shipment_id]
    latest = shipment_blocks[-1] if shipment_blocks else None
    return {
        "shipmentId": shipment_id,
        "ready": not problems,
        "problems": problems,
        "documentDigest": current["digest"],
        "documents": current["documents"],
        "latestBlock": latest,
        "shipmentBlockCount": len(shipment_blocks),
        "recentBlocks": list(reversed(shipment_blocks[-6:])),
        "snapshotMatches": latest is None or latest["documentDigest"] == current["digest"],
        "chain": verify(chain),
        "network": "Локальный демореестр · 1 узел · без внешней сети",
    }


def execute(data: dict, shipment_id: str, uploads_dir: Path, actor: str) -> dict:
    chain = data.setdefault("corridorChain", [])
    integrity = verify(chain)
    if not integrity["valid"]:
        raise ValueError("Цепочка повреждена: запись заблокирована")
    state = status(data, shipment_id, uploads_dir)
    decision = "ready_for_review" if state["ready"] else "needs_correction"
    block = {
        "index": len(chain),
        "previousHash": chain[-1]["hash"] if chain else GENESIS,
        "shipmentId": shipment_id,
        "documentDigest": state["documentDigest"],
        "decision": decision,
        "problems": state["problems"],
        "actor": actor,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "nonce": 0,
    }
    while True:
        digest = _block_hash(block)
        if digest.startswith(DIFFICULTY):
            block["hash"] = digest
            break
        block["nonce"] += 1
    chain.append(block)
    return status(data, shipment_id, uploads_dir)
