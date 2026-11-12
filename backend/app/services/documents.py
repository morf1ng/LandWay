"""Демонстрационная проверка комплекта документов. Это не таможенная экспертиза."""

from __future__ import annotations

from datetime import datetime

from app.catalog import REQUIRED_DOCUMENT_TYPES, document_label
from app.services.risk import iso


def evaluate_status(document: dict) -> str:
    if not document.get("file"):
        return "missing"
    if document.get("type") not in REQUIRED_DOCUMENT_TYPES:
        return "needs_attention"
    fields = document.get("fields") or {}
    if not fields.get("number") or not fields.get("issuedAt"):
        return "needs_attention"
    return "verified"


def check_shipment_documents(documents: list[dict]) -> dict:
    checked = []
    for document in documents:
        status = evaluate_status(document)
        document["status"] = status
        if status == "verified":
            document["comment"] = "Файл приложен, тип указан, обязательные поля заполнены. Демонстрационная проверка, не юридическая экспертиза."
        elif status == "needs_attention":
            document["comment"] = "Документ требует внимания: проверьте тип и обязательные поля (номер и дата)."
        else:
            document["comment"] = "Файл отсутствует."
        checked.append(document)

    present_types = {document["type"] for document in documents if document.get("file")}
    missing_types = [type_id for type_id in REQUIRED_DOCUMENT_TYPES if type_id not in present_types]
    problems = []
    for type_id in missing_types:
        problems.append(f"Отсутствует: {document_label(type_id)}")
    for document in documents:
        if document["status"] == "needs_attention":
            problems.append(f"Требует внимания: {document['name']}")
        elif document["status"] == "missing":
            label = f"Отсутствует файл: {document['name']}"
            if label not in problems and document["type"] not in missing_types:
                problems.append(label)
    ready = not problems and not missing_types
    return {
        "ready": ready,
        "problems": problems,
        "missingTypes": missing_types,
        "documents": checked,
        "checkedAt": iso(datetime.now()),
    }


def required_labels() -> list[str]:
    return [document_label(type_id) for type_id in REQUIRED_DOCUMENT_TYPES]
