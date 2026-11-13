"""Изменения общих данных. После каждой операции прогноз и след пересчитываются."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.catalog import PORT_NAMES, REQUIRED_DOCUMENT_TYPES, document_label, template_by_id
from app.services.documents import check_shipment_documents
from app.services.engine import recalculate
from app.services.risk import iso
from app.services.routing import materialize, resolve_template, template_is_valid

UPLOADS_NAME = "uploads"


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _find_shipment(data: dict, shipment_id: str) -> dict:
    for shipment in data["shipments"]:
        if shipment["id"] == shipment_id:
            return shipment
    raise ValueError("Груз не найден")


def _next_shipment_id(data: dict) -> str:
    numbers = []
    for shipment in data["shipments"]:
        if shipment["id"].startswith("SCT-"):
            try:
                numbers.append(int(shipment["id"].split("-")[1]))
            except ValueError:
                continue
    return f"SCT-{max(numbers, default=1000) + 1}"


def _journal(data: dict, shipment_id: str, type_: str, title: str, result: str, details: str, at: datetime) -> None:
    data["journal"].insert(
        0,
        {
            "id": f"j-{uuid.uuid4().hex[:10]}",
            "shipmentId": shipment_id,
            "type": type_,
            "title": title,
            "result": result,
            "details": details,
            "at": iso(at),
        },
    )


def _parse_sequence(value) -> list[str]:
    if isinstance(value, str):
        parts = [item.strip() for item in value.replace("+", ",").split(",") if item.strip()]
    else:
        parts = list(value or [])
    allowed = (["rail", "sea"], ["road", "sea"], ["rail", "road", "sea"])
    if parts not in allowed:
        raise ValueError("Последовательность транспорта: поезд + корабль, грузовик + корабль или поезд + грузовик + корабль")
    return parts


def _validate_payload(payload: dict, partial: bool = False) -> dict:
    required = [
        "name",
        "category",
        "weight",
        "containerCount",
        "sender",
        "receiver",
        "origin",
        "destination",
        "plannedDeparture",
        "plannedArrival",
        "transportSequence",
    ]
    if not partial:
        for key in required:
            if payload.get(key) in (None, ""):
                raise ValueError(f"Заполните поле: {key}")
    result = dict(payload)
    if "transportSequence" in payload and payload["transportSequence"] not in (None, ""):
        result["transportSequence"] = _parse_sequence(payload["transportSequence"])
    if "origin" in result and result["origin"] not in PORT_NAMES:
        raise ValueError("Пункт отправления должен быть одним из портов коридора")
    if "destination" in result and result["destination"] not in PORT_NAMES:
        raise ValueError("Пункт назначения должен быть одним из портов коридора")
    if result.get("origin") and result.get("destination") and result["origin"] == result["destination"]:
        raise ValueError("Пункт отправления и назначения не могут совпадать")
    if "weight" in payload and payload["weight"] not in (None, ""):
        weight = float(payload["weight"])
        if weight <= 0:
            raise ValueError("Вес должен быть больше нуля")
        result["weight"] = weight
    if "containerCount" in payload and payload["containerCount"] not in (None, ""):
        count = int(payload["containerCount"])
        if count < 1:
            raise ValueError("Количество контейнеров должно быть не меньше 1")
        result["containerCount"] = count
    for key in ("plannedDeparture", "plannedArrival"):
        if result.get(key):
            try:
                datetime.fromisoformat(result[key])
            except ValueError as exc:
                raise ValueError("Некорректная дата") from exc
    if result.get("plannedDeparture") and result.get("plannedArrival"):
        if result["plannedDeparture"] >= result["plannedArrival"]:
            raise ValueError("Дата доставки должна быть позже даты отправления")
    return result


def _empty_documents(shipment_id: str) -> list[dict]:
    documents = []
    for type_id in REQUIRED_DOCUMENT_TYPES:
        documents.append(
            {
                "id": f"doc-{shipment_id}-{type_id}",
                "shipmentId": shipment_id,
                "name": document_label(type_id),
                "type": type_id,
                "file": None,
                "status": "missing",
                "uploadedAt": None,
                "comment": "Документ ещё не загружен",
                "fields": {"number": "", "issuedAt": ""},
            }
        )
    return documents


def _sync_doc_status(shipment: dict, problems: list[str]) -> None:
    if shipment["status"] in ("delivered", "in_transit", "delayed"):
        return
    if problems:
        shipment["status"] = "documents_issue"
    elif shipment["status"] == "documents_issue":
        shipment["status"] = "awaiting"


def create_shipment(data: dict, payload: dict, actor: str = "Логист") -> dict:
    fields = _validate_payload(payload)
    if payload.get("contractSigned") is not True:
        raise ValueError("Подпишите смарт-контракт, чтобы создать груз")
    moment = _now()
    shipment_id = _next_shipment_id(data)
    template = resolve_template(fields["origin"], fields["destination"], fields["transportSequence"])
    route = materialize(template, datetime.fromisoformat(fields["plannedDeparture"]), f"rt-{shipment_id}", shipment_id)
    shipment = {
        "id": shipment_id,
        "name": fields["name"].strip(),
        "category": fields["category"].strip(),
        "weight": fields["weight"],
        "containerCount": fields["containerCount"],
        "sender": fields["sender"].strip(),
        "receiver": fields["receiver"].strip(),
        "origin": fields["origin"],
        "destination": fields["destination"],
        "status": "awaiting",
        "plannedDeparture": fields["plannedDeparture"],
        "plannedArrival": fields["plannedArrival"],
        "predictedArrival": fields["plannedArrival"],
        "currentLocation": route["stages"][0]["location"],
        "currentPort": route["stages"][0]["location"] if route["stages"][0]["location"] in PORT_NAMES else None,
        "currentTransport": route["stages"][0]["transportType"],
        "routeId": route["id"],
        "templateId": template["id"],
        "transportSequence": fields["transportSequence"],
        "riskScore": 0,
        "notes": (fields.get("notes") or "").strip(),
        "preclearanceStatus": None,
        "preclearanceAt": None,
        "extraEvents": [
            {
                "time": iso(moment),
                "location": route["stages"][0]["location"],
                "transport": route["stages"][0]["transportType"],
                "description": "Груз создан и поставлен на маршрут",
                "status": "awaiting",
            }
        ],
        "createdAt": iso(moment),
        "updatedAt": iso(moment),
    }
    data["shipments"].append(shipment)
    data["routes"].append(route)
    data["documents"].extend(_empty_documents(shipment_id))
    from app.services.corridor_contract import sign_shipment

    signed = sign_shipment(data, shipment, actor)
    _journal(
        data,
        shipment_id,
        "shipment",
        "Создание груза",
        shipment_id,
        f"Смарт-контракт подписан ({signed['hash'][:12]}). Груз добавлен в общую базу, маршрут и предварительный риск рассчитаны.",
        moment,
    )
    recalculate(data, moment)
    return shipment


def update_shipment(data: dict, shipment_id: str, payload: dict) -> dict:
    shipment = _find_shipment(data, shipment_id)
    if shipment["status"] == "delivered":
        raise ValueError("Доставленный груз нельзя изменить")
    fields = _validate_payload({**shipment, **payload})
    moment = _now()
    rebuild = any(
        fields.get(key) != shipment.get(key)
        for key in ("origin", "destination", "transportSequence", "plannedDeparture")
    )
    for key in (
        "name",
        "category",
        "weight",
        "containerCount",
        "sender",
        "receiver",
        "origin",
        "destination",
        "plannedDeparture",
        "plannedArrival",
        "notes",
        "transportSequence",
    ):
        if key in fields:
            shipment[key] = fields[key]
    if rebuild:
        template = resolve_template(shipment["origin"], shipment["destination"], shipment["transportSequence"])
        route = materialize(template, datetime.fromisoformat(shipment["plannedDeparture"]), shipment["routeId"], shipment["id"])
        for index, item in enumerate(data["routes"]):
            if item["id"] == shipment["routeId"]:
                data["routes"][index] = route
                break
        shipment["templateId"] = template["id"]
        shipment["currentLocation"] = route["stages"][0]["location"]
        shipment["currentTransport"] = route["stages"][0]["transportType"]
        shipment["currentPort"] = route["stages"][0]["location"] if route["stages"][0]["location"] in PORT_NAMES else None
        if shipment["status"] == "delayed":
            shipment["status"] = "awaiting"
        shipment["extraEvents"].append(
            {
                "time": iso(moment),
                "location": shipment["currentLocation"],
                "transport": shipment["currentTransport"],
                "description": f"Маршрут пересобран: {template['name']}",
                "status": shipment["status"],
            }
        )
    recalculate(data, moment)
    return shipment


def select_route(data: dict, shipment_id: str, template_id: str, expected_version: str | None = None) -> dict:
    from app.services.routing import apply_route_alternative

    moment = _now()
    template = template_by_id(template_id)
    shipment = apply_route_alternative(data, shipment_id, template_id, moment, expected_version)
    _journal(
        data,
        shipment_id,
        "route",
        "Смена маршрута",
        template["name"] if template else template_id,
        "Маршрут пересобран от узла стыковки. Прогноз и углеродный след пересчитаны.",
        moment,
    )
    recalculate(data, moment)
    return shipment


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def save_upload(data: dict, shipment_id: str, type_id: str, original_name: str, content: bytes, uploads_dir) -> dict:
    _find_shipment(data, shipment_id)
    if type_id not in REQUIRED_DOCUMENT_TYPES:
        raise ValueError("Неизвестный тип документа")
    if not content:
        raise ValueError("Файл пустой")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Файл больше {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ")
    original_name = original_name.replace("\\", "/").rsplit("/", 1)[-1].strip() or "file"
    moment = _now()
    document = next((item for item in data["documents"] if item["shipmentId"] == shipment_id and item["type"] == type_id), None)
    if document is None:
        document = {
            "id": f"doc-{shipment_id}-{type_id}-{uuid.uuid4().hex[:4]}",
            "shipmentId": shipment_id,
            "name": document_label(type_id),
            "type": type_id,
            "fields": {},
        }
        data["documents"].append(document)
    stored = f"{document['id']}-{uuid.uuid4().hex[:6]}"
    extension = "".join(ch for ch in original_name.rsplit(".", 1)[1] if ch.isascii() and ch.isalnum())[:8] if "." in original_name else ""
    stored += f".{extension}" if extension else ""
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / stored).write_bytes(content)
    document["file"] = {
        "storedName": stored,
        "originalName": original_name,
        "size": len(content),
        "mime": "application/octet-stream",
    }
    document["status"] = "pending"
    document["uploadedAt"] = iso(moment)
    document["fields"] = {"number": f"DOC-{document['id'][-6:]}", "issuedAt": iso(moment)[:10]}
    document["comment"] = "Файл загружен и ожидает проверки."
    document["name"] = document_label(type_id)
    _journal(data, shipment_id, "documents", "Загрузка документа", document_label(type_id), original_name, moment)
    recalculate(data, moment)
    return document


def update_document_fields(data: dict, document_id: str, payload: dict) -> dict:
    document = next((item for item in data["documents"] if item["id"] == document_id), None)
    if document is None:
        raise ValueError("Документ не найден")
    fields = document.setdefault("fields", {})
    if "number" in payload:
        fields["number"] = str(payload["number"]).strip()
    if "issuedAt" in payload:
        fields["issuedAt"] = str(payload["issuedAt"]).strip()
    if "comment" in payload:
        document["comment"] = str(payload["comment"]).strip()
    if document["status"] == "needs_attention":
        document["status"] = "pending"
    recalculate(data, _now())
    return document


def check_documents(data: dict, shipment_id: str) -> dict:
    shipment = _find_shipment(data, shipment_id)
    moment = _now()
    documents = [item for item in data["documents"] if item["shipmentId"] == shipment_id]
    result = check_shipment_documents(documents)
    _sync_doc_status(shipment, result["problems"])
    _journal(
        data,
        shipment_id,
        "documents",
        "Проверка документов",
        "комплект полный" if result["ready"] else "есть замечания",
        "; ".join(result["problems"]) if result["problems"] else "Все обязательные типы найдены, статусы обновлены.",
        moment,
    )
    recalculate(data, moment)
    result["shipmentStatus"] = shipment["status"]
    return result


def preclear(data: dict, shipment_id: str, uploads_dir, actor: str = "Демо-логист") -> dict:
    from app.services.preliminary_review import submit

    return submit(data, shipment_id, uploads_dir, actor)


def submit_preliminary_review(
    data: dict,
    shipment_id: str,
    uploads_dir,
    actor: str,
    *,
    idempotency_key: str | None = None,
) -> dict:
    from app.services.preliminary_review import submit

    return submit(data, shipment_id, uploads_dir, actor, idempotency_key=idempotency_key)


def update_factors(data: dict, payload: dict) -> dict:
    factors = dict(data["emissionFactors"])
    for key in ("rail", "sea", "road"):
        if key not in payload:
            continue
        value = float(payload[key])
        if value < 0:
            raise ValueError("Коэффициент не может быть отрицательным")
        factors[key] = value
    data["emissionFactors"] = factors
    recalculate(data, _now())
    return factors


def update_profile(data: dict, payload: dict, user_id: str | None = None) -> dict:
    uid = user_id or (data.get("profile") or {}).get("userId")
    if uid:
        from app.services.auth import update_user_profile

        return update_user_profile(data, uid, payload)
    profile = data["profile"]
    for key in ("name", "role", "organization"):
        if payload.get(key):
            profile[key] = str(payload[key]).strip()
    return profile


def ingest_event(data: dict, payload: dict) -> dict:
    from app.services.telemetry import ingest_event as apply_event

    return apply_event(data, payload)


def simulate_rail_event(data: dict, shipment_id: str) -> dict:
    from app.services.telemetry import simulate_rail_miss_ferry

    return simulate_rail_miss_ferry(data, shipment_id)


def _pending_sea_port(data: dict, shipment_id: str) -> str:
    shipment = _find_shipment(data, shipment_id)
    route = next(item for item in data["routes"] if item["id"] == shipment["routeId"])
    for stage in route["stages"]:
        if stage.get("transportType") == "sea" and stage.get("status") == "pending":
            return stage["location"]
    raise ValueError("У груза нет ожидающего морского этапа")


def simulate_port_close(data: dict, shipment_id: str, restriction_ends_at: str | None = None) -> dict:
    from app.services.telemetry import simulate_port_departure_closed

    port = _pending_sea_port(data, shipment_id)
    result = simulate_port_departure_closed(data, port_name=port, restriction_ends_at=restriction_ends_at)
    recalculate(data, _now())
    return result


def simulate_port_open(data: dict, shipment_id: str) -> dict:
    from app.services.telemetry import simulate_port_departure_open

    port = _pending_sea_port(data, shipment_id)
    result = simulate_port_departure_open(data, port_name=port)
    recalculate(data, _now())
    return result


def mark_notification(data: dict, notification_id: str, read: bool = True) -> dict:
    for item in data["notifications"]:
        if item["id"] == notification_id:
            item["read"] = read
            return item
    raise ValueError("Уведомление не найдено")


def mark_all_notifications(data: dict) -> int:
    for item in data["notifications"]:
        item["read"] = True
    return len(data["notifications"])
