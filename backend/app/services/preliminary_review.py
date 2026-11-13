"""Единая демонстрационная предварительная проверка комплекта документов.

Имитирует сторону проверяющего (не реальная таможня). Согласованно обновляет
статус груза, журнал и локальный реестр блоков.
"""

from __future__ import annotations

from datetime import datetime

from app.services.corridor_contract import execute, status
from app.services.documents import check_shipment_documents
from app.services.engine import recalculate
from app.services.risk import iso

STATUS_READY = "Готов к рассмотрению"
STATUS_NEEDS = "Требуется исправление"
ACTOR_LABEL = "Имитация проверяющей стороны (демо)"
DEMO_NOTE = (
    "Демонстрационная предварительная проверка комплекта. "
    "Не является решением таможенного органа и не выполняет выпуск."
)


def decision_to_status(decision: str) -> str:
    return STATUS_READY if decision == "ready_for_review" else STATUS_NEEDS


def _find_shipment(data: dict, shipment_id: str) -> dict:
    for shipment in data["shipments"]:
        if shipment["id"] == shipment_id:
            return shipment
    raise ValueError("Груз не найден")


def _cache_key(shipment_id: str, idempotency_key: str) -> str:
    return f"{shipment_id}:{idempotency_key}"


def _get_cached(data: dict, shipment_id: str, idempotency_key: str | None) -> dict | None:
    if not idempotency_key:
        return None
    cache = data.get("preliminaryReviewCache") or {}
    return cache.get(_cache_key(shipment_id, idempotency_key))


def _put_cache(data: dict, shipment_id: str, idempotency_key: str | None, payload: dict) -> None:
    if not idempotency_key:
        return
    cache = data.setdefault("preliminaryReviewCache", {})
    cache[_cache_key(shipment_id, idempotency_key)] = payload


def _should_skip_new_block(state: dict) -> bool:
    latest = state.get("latestBlock")
    if not latest:
        return False
    decision = "ready_for_review" if state["ready"] else "needs_correction"
    if latest["documentDigest"] != state["documentDigest"]:
        return False
    if latest["decision"] != decision:
        return False
    return list(latest.get("problems") or []) == list(state.get("problems") or [])


def _journal(data: dict, shipment_id: str, result: str, details: str, moment: datetime) -> None:
    import uuid

    data["journal"].insert(
        0,
        {
            "id": f"j-{uuid.uuid4().hex[:10]}",
            "shipmentId": shipment_id,
            "type": "preliminary_review",
            "title": "Предварительная проверка комплекта",
            "result": result,
            "details": details,
            "at": iso(moment),
        },
    )


def _sync_shipment(shipment: dict, decision: str, submitted_at: str, problems: list[str]) -> None:
    shipment["preclearanceStatus"] = decision_to_status(decision)
    shipment["preclearanceAt"] = submitted_at
    if problems:
        if shipment["status"] not in ("delivered", "in_transit", "delayed"):
            shipment["status"] = "documents_issue"
    elif shipment["status"] == "documents_issue":
        shipment["status"] = "awaiting"


def _response_from_state(
    data: dict,
    shipment_id: str,
    state: dict,
    *,
    deduplicated: bool = False,
    created_block: bool = True,
) -> dict:
    shipment = _find_shipment(data, shipment_id)
    latest = state.get("latestBlock")
    decision = latest["decision"] if latest else ("ready_for_review" if state["ready"] else "needs_correction")
    return {
        "shipmentId": shipment_id,
        "ok": state["ready"],
        "decision": decision,
        "statusLabel": decision_to_status(decision),
        "preclearanceStatus": shipment.get("preclearanceStatus"),
        "submittedAt": shipment.get("preclearanceAt"),
        "problems": state["problems"],
        "documentDigest": state["documentDigest"],
        "problemsDigest": state.get("problems"),
        "latestBlock": latest,
        "recentBlocks": state.get("recentBlocks") or [],
        "shipmentBlockCount": state.get("shipmentBlockCount") or 0,
        "snapshotMatches": state.get("snapshotMatches", True),
        "staleDecision": bool(latest and not state.get("snapshotMatches")),
        "staleMessage": (
            "Решение относится к предыдущей версии комплекта — изменились файлы или поля. "
            "Нужна повторная подача."
            if latest and not state.get("snapshotMatches")
            else None
        ),
        "deduplicated": deduplicated,
        "createdBlock": created_block,
        "verifier": ACTOR_LABEL,
        "note": DEMO_NOTE,
        "shipmentStatus": shipment["status"],
    }


def review_status(data: dict, shipment_id: str, uploads_dir) -> dict:
    state = status(data, shipment_id, uploads_dir)
    shipment = _find_shipment(data, shipment_id)
    base = _response_from_state(data, shipment_id, state, deduplicated=False, created_block=False)
    base["preclearance"] = enrich_shipment_preclearance(data, shipment, uploads_dir)
    return base


def enrich_shipment_preclearance(data: dict, shipment: dict, uploads_dir) -> dict:
    state = status(data, shipment["id"], uploads_dir)
    latest = state.get("latestBlock")
    stale = bool(latest and not state.get("snapshotMatches"))
    return {
        "preclearanceStatus": shipment.get("preclearanceStatus"),
        "preclearanceAt": shipment.get("preclearanceAt"),
        "preclearanceStale": stale,
        "preclearanceStaleMessage": (
            "Решение относится к предыдущей версии комплекта — нужна повторная подача."
            if stale
            else None
        ),
        "preclearanceDigest": latest["documentDigest"] if latest else None,
        "documentDigestCurrent": state["documentDigest"],
    }


def submit(
    data: dict,
    shipment_id: str,
    uploads_dir,
    actor: str,
    *,
    idempotency_key: str | None = None,
) -> dict:
    shipment = _find_shipment(data, shipment_id)
    if shipment["status"] == "delivered":
        raise ValueError("Груз уже доставлен")

    cached = _get_cached(data, shipment_id, idempotency_key)
    if cached:
        fresh = status(data, shipment_id, uploads_dir)
        merged = {**cached, **fresh, "deduplicated": True, "createdBlock": False}
        merged["staleDecision"] = bool(fresh.get("latestBlock") and not fresh.get("snapshotMatches"))
        merged["staleMessage"] = (
            "Решение относится к предыдущей версии комплекта — изменились файлы или поля. "
            "Нужна повторная подача."
            if merged["staleDecision"]
            else None
        )
        return merged

    moment = datetime.now().replace(microsecond=0)
    documents = [item for item in data["documents"] if item["shipmentId"] == shipment_id]
    check_shipment_documents(documents)

    preview = status(data, shipment_id, uploads_dir)
    created_block = True
    if _should_skip_new_block(preview):
        state = preview
        created_block = False
        deduplicated = True
    else:
        state = execute(data, shipment_id, uploads_dir, actor or ACTOR_LABEL)
        deduplicated = False

    latest = state["latestBlock"]
    if latest is None:
        raise ValueError("Не удалось зафиксировать попытку проверки")

    _sync_shipment(shipment, latest["decision"], latest["createdAt"], state["problems"])

    result_label = decision_to_status(latest["decision"])
    details = (
        f"{DEMO_NOTE} Отпечаток комплекта {state['documentDigest'][:16]}…. "
        f"Проверяющий: {ACTOR_LABEL}."
    )
    if state["problems"]:
        details += " Замечания: " + "; ".join(state["problems"])
    elif created_block:
        details += " Замечаний нет."

    if created_block:
        _journal(data, shipment_id, result_label, details, moment)

    recalculate(data, moment)
    response = _response_from_state(data, shipment_id, state, deduplicated=deduplicated, created_block=created_block)
    _put_cache(data, shipment_id, idempotency_key, response)
    return response
