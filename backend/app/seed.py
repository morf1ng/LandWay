"""Демонстрационные грузы коридора Север — Юг. Файлы документов пишутся на диск."""

from __future__ import annotations

import json
from pathlib import Path

from app.catalog import DEFAULT_EMISSION_FACTORS, PORTS, document_label
from app.services.auth import default_users

UPLOADS = Path(__file__).resolve().parents[1] / "uploads"


def _stage(
    route_id: str,
    index: int,
    location: str,
    next_location: str,
    transport: str,
    start: str,
    arrival: str,
    distance: float,
    status: str,
    description: str,
    delay_hours: float = 0,
    actual: str | None = None,
    ship_departure: str | None = None,
) -> dict:
    return {
        "id": f"{route_id}-{index}",
        "routeId": route_id,
        "location": location,
        "nextLocation": next_location,
        "transportType": transport,
        "plannedStart": start,
        "plannedArrival": arrival,
        "actualArrival": actual,
        "status": status,
        "distanceKm": distance,
        "delayHours": delay_hours,
        "shipDeparture": ship_departure,
        "description": description,
    }


def _write_file(document_id: str, shipment_id: str, type_id: str, number: str, issued_at: str) -> dict:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    stored = f"{document_id}.txt"
    text = (
        f"Документ: {document_label(type_id)}\n"
        f"Груз: {shipment_id}\n"
        f"Номер: {number}\n"
        f"Дата: {issued_at}\n"
        "Демонстрационный файл прототипа Smart Caspian Transit.\n"
        "Файл не является таможенным или юридическим документом.\n"
    )
    path = UPLOADS / stored
    path.write_text(text, encoding="utf-8")
    return {
        "storedName": stored,
        "originalName": f"{document_label(type_id)} {shipment_id}.txt",
        "size": path.stat().st_size,
        "mime": "text/plain",
    }


def _document(
    shipment_id: str,
    type_id: str,
    status: str,
    number: str,
    issued_at: str,
    with_file: bool,
    comment: str,
) -> dict:
    document_id = f"doc-{shipment_id}-{type_id}"
    fields = {"number": number, "issuedAt": issued_at}
    return {
        "id": document_id,
        "shipmentId": shipment_id,
        "name": document_label(type_id),
        "type": type_id,
        "file": _write_file(document_id, shipment_id, type_id, number or "—", issued_at or "—") if with_file else None,
        "status": status,
        "uploadedAt": "2026-11-09T10:00:00" if with_file else None,
        "comment": comment,
        "fields": fields,
    }


def _full_docs(shipment_id: str, issued_at: str) -> list[dict]:
    return [
        _document(shipment_id, type_id, "verified", f"{type_id[:3].upper()}-{shipment_id[-4:]}", issued_at, True, "Комплект в порядке.")
        for type_id in ("waybill", "invoice", "packing", "declaration", "origin")
    ]


def build_seed() -> dict:
    shipments = [
        {
            "id": "SCT-1001",
            "name": "Комплект промышленного оборудования",
            "category": "Промышленное оборудование",
            "weight": 420,
            "containerCount": 18,
            "sender": "ООО «ВолгаМаш»",
            "receiver": "Anzali Industrial Co.",
            "origin": "Астрахань",
            "destination": "Энзели",
            "status": "delayed",
            "plannedDeparture": "2026-11-10T08:00:00",
            "plannedArrival": "2026-11-14T18:00:00",
            "predictedArrival": "2026-11-14T18:00:00",
            "currentLocation": "перегон Саратов — Астрахань",
            "currentPort": None,
            "currentTransport": "rail",
            "routeId": "rt-SCT-1001",
            "templateId": "ast-anz-rail-sea",
            "transportSequence": ["rail", "sea"],
            "riskScore": 0,
            "notes": "Поезд потерял нитку графика, окно морского рейса из Астрахани короткое.",
            "preclearanceStatus": None,
            "preclearanceAt": None,
            "extraEvents": [],
            "createdAt": "2026-11-08T09:00:00",
            "updatedAt": "2026-11-12T10:00:00",
        },
        {
            "id": "SCT-1002",
            "name": "Партия продовольственных товаров",
            "category": "Продовольственные товары",
            "weight": 180,
            "containerCount": 8,
            "sender": "ООО «ДагФуд»",
            "receiver": "Enzeli Food Import",
            "origin": "Махачкала",
            "destination": "Энзели",
            "status": "in_transit",
            "plannedDeparture": "2026-11-11T06:00:00",
            "plannedArrival": "2026-11-13T18:00:00",
            "predictedArrival": "2026-11-13T18:00:00",
            "currentLocation": "Каспийское море, рейс Махачкала — Энзели",
            "currentPort": None,
            "currentTransport": "sea",
            "routeId": "rt-SCT-1002",
            "templateId": "makh-anz-road-sea",
            "transportSequence": ["road", "sea"],
            "riskScore": 0,
            "notes": "Судно вышло по расписанию.",
            "preclearanceStatus": "Предварительно подготовлена",
            "preclearanceAt": "2026-11-10T15:00:00",
            "extraEvents": [],
            "createdAt": "2026-11-09T11:00:00",
            "updatedAt": "2026-11-12T10:00:00",
        },
        {
            "id": "SCT-1003",
            "name": "Металлопрокат в рулонах",
            "category": "Металлопрокат",
            "weight": 560,
            "containerCount": 24,
            "sender": "ПАО «СтальЮг»",
            "receiver": "Amirabad Steel Terminal",
            "origin": "Астрахань",
            "destination": "Амирабад",
            "status": "in_transit",
            "plannedDeparture": "2026-11-09T20:00:00",
            "plannedArrival": "2026-11-16T08:00:00",
            "predictedArrival": "2026-11-16T08:00:00",
            "currentLocation": "порт Астрахань, ожидание погодного окна",
            "currentPort": "Астрахань",
            "currentTransport": "sea",
            "routeId": "rt-SCT-1003",
            "templateId": "ast-amr-rail-sea",
            "transportSequence": ["rail", "sea"],
            "riskScore": 0,
            "notes": "Поезд прибыл вовремя, выход судна зависит от ветра.",
            "preclearanceStatus": "Предварительно подготовлена",
            "preclearanceAt": "2026-11-09T12:00:00",
            "extraEvents": [],
            "createdAt": "2026-11-08T12:00:00",
            "updatedAt": "2026-11-12T10:00:00",
        },
        {
            "id": "SCT-1004",
            "name": "Текстиль и ткани",
            "category": "Текстиль",
            "weight": 95,
            "containerCount": 4,
            "sender": "ООО «КаспийТекстиль»",
            "receiver": "Amirabad Textile LLC",
            "origin": "Махачкала",
            "destination": "Амирабад",
            "status": "documents_issue",
            "plannedDeparture": "2026-11-12T07:00:00",
            "plannedArrival": "2026-11-17T12:00:00",
            "predictedArrival": "2026-11-17T12:00:00",
            "currentLocation": "порт Махачкала",
            "currentPort": "Махачкала",
            "currentTransport": "road",
            "routeId": "rt-SCT-1004",
            "templateId": "makh-amr-road-sea",
            "transportSequence": ["road", "sea"],
            "riskScore": 0,
            "notes": "Инвойс без номера, таможенная декларация не загружена.",
            "preclearanceStatus": None,
            "preclearanceAt": None,
            "extraEvents": [],
            "createdAt": "2026-11-11T09:30:00",
            "updatedAt": "2026-11-12T10:00:00",
        },
        {
            "id": "SCT-1005",
            "name": "Строительные материалы",
            "category": "Строительные материалы",
            "weight": 260,
            "containerCount": 12,
            "sender": "ООО «ЮгСтройСнаб»",
            "receiver": "Bandar Anzali Construction",
            "origin": "Астрахань",
            "destination": "Энзели",
            "status": "delivered",
            "plannedDeparture": "2026-11-05T08:00:00",
            "plannedArrival": "2026-11-10T16:00:00",
            "predictedArrival": "2026-11-10T15:00:00",
            "currentLocation": "порт Энзели",
            "currentPort": "Энзели",
            "currentTransport": "none",
            "routeId": "rt-SCT-1005",
            "templateId": "ast-anz-rail-sea",
            "transportSequence": ["rail", "sea"],
            "riskScore": 0,
            "notes": "Доставка завершена 10 ноября.",
            "preclearanceStatus": "Предварительно подготовлена",
            "preclearanceAt": "2026-11-04T11:30:00",
            "extraEvents": [
                {
                    "time": "2026-11-10T15:00:00",
                    "location": "Энзели",
                    "transport": "sea",
                    "description": "Груз передан получателю",
                    "status": "delivered",
                }
            ],
            "createdAt": "2026-11-03T10:00:00",
            "updatedAt": "2026-11-10T15:00:00",
        },
        {
            "id": "SCT-1006",
            "name": "Автозапчасти",
            "category": "Автозапчасти",
            "weight": 140,
            "containerCount": 6,
            "sender": "ООО «АвтоКаспий»",
            "receiver": "Enzeli Motors",
            "origin": "Махачкала",
            "destination": "Энзели",
            "status": "awaiting",
            "plannedDeparture": "2026-11-13T09:00:00",
            "plannedArrival": "2026-11-17T15:00:00",
            "predictedArrival": "2026-11-17T15:00:00",
            "currentLocation": "терминал Махачкала",
            "currentPort": "Махачкала",
            "currentTransport": "road",
            "routeId": "rt-SCT-1006",
            "templateId": "makh-anz-road-sea",
            "transportSequence": ["road", "sea"],
            "riskScore": 0,
            "notes": "Отправление запланировано на 13 ноября. Сертификат происхождения ещё не проверен.",
            "preclearanceStatus": None,
            "preclearanceAt": None,
            "extraEvents": [],
            "createdAt": "2026-11-11T16:00:00",
            "updatedAt": "2026-11-12T10:00:00",
        },
    ]

    routes = [
        {
            "id": "rt-SCT-1001",
            "shipmentId": "SCT-1001",
            "name": "Поезд до Астрахани и морской рейс в Энзели",
            "templateId": "ast-anz-rail-sea",
            "origin": "Астрахань",
            "destination": "Энзели",
            "distance": 1280,
            "estimatedDuration": 0,
            "estimatedCost": 430000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1001", 1, "Саратов", "Астрахань", "rail", "2026-11-10T08:00:00", "2026-11-11T12:00:00", 520, "delayed", "Поезд следует с опозданием относительно нитки графика.", 30),
                _stage("rt-SCT-1001", 2, "Астрахань", "Энзели", "sea", "2026-11-11T12:00:00", "2026-11-14T18:00:00", 760, "pending", "Морской рейс назначен раньше, чем прогноз прибытия поезда с запасом.", 0, None, "2026-11-12T20:00:00"),
            ],
        },
        {
            "id": "rt-SCT-1002",
            "shipmentId": "SCT-1002",
            "name": "Грузовик до Махачкалы и морской рейс в Энзели",
            "templateId": "makh-anz-road-sea",
            "origin": "Махачкала",
            "destination": "Энзели",
            "distance": 765,
            "estimatedDuration": 0,
            "estimatedCost": 310000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1002", 1, "Каспийск", "Махачкала", "road", "2026-11-11T06:00:00", "2026-11-11T08:00:00", 25, "completed", "Автомобильное плечо выполнено по графику.", 0, "2026-11-11T08:00:00"),
                _stage("rt-SCT-1002", 2, "Махачкала", "Энзели", "sea", "2026-11-11T08:00:00", "2026-11-13T18:00:00", 740, "in_progress", "Судно в море, расписание соблюдается.", 0, None, "2026-11-11T16:00:00"),
            ],
        },
        {
            "id": "rt-SCT-1003",
            "shipmentId": "SCT-1003",
            "name": "Поезд до Астрахани и морской рейс в Амирабад",
            "templateId": "ast-amr-rail-sea",
            "origin": "Астрахань",
            "destination": "Амирабад",
            "distance": 1360,
            "estimatedDuration": 0,
            "estimatedCost": 490000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1003", 1, "Волгоград", "Астрахань", "rail", "2026-11-09T20:00:00", "2026-11-10T12:00:00", 380, "completed", "Поезд прибыл в порт по расписанию.", 0, "2026-11-10T12:00:00"),
                _stage("rt-SCT-1003", 2, "Астрахань", "Амирабад", "sea", "2026-11-10T12:00:00", "2026-11-16T08:00:00", 980, "pending", "Выход судна зависит от ветра и волнения.", 0, None, "2026-11-12T22:00:00"),
            ],
        },
        {
            "id": "rt-SCT-1004",
            "shipmentId": "SCT-1004",
            "name": "Грузовик до Махачкалы и морской рейс в Амирабад",
            "templateId": "makh-amr-road-sea",
            "origin": "Махачкала",
            "destination": "Амирабад",
            "distance": 1075,
            "estimatedDuration": 0,
            "estimatedCost": 360000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1004", 1, "Каспийск", "Махачкала", "road", "2026-11-12T07:00:00", "2026-11-12T09:00:00", 25, "completed", "Груз доставлен в порт автотранспортом.", 0, "2026-11-12T09:00:00"),
                _stage("rt-SCT-1004", 2, "Махачкала", "Амирабад", "sea", "2026-11-12T09:00:00", "2026-11-17T12:00:00", 1050, "pending", "Погрузка ожидает комплект документов.", 0, None, "2026-11-15T08:00:00"),
            ],
        },
        {
            "id": "rt-SCT-1005",
            "shipmentId": "SCT-1005",
            "name": "Поезд до Астрахани и морской рейс в Энзели",
            "templateId": "ast-anz-rail-sea",
            "origin": "Астрахань",
            "destination": "Энзели",
            "distance": 1280,
            "estimatedDuration": 0,
            "estimatedCost": 430000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1005", 1, "Саратов", "Астрахань", "rail", "2026-11-05T08:00:00", "2026-11-06T14:00:00", 520, "completed", "Железнодорожный участок завершён.", 0, "2026-11-06T14:00:00"),
                _stage("rt-SCT-1005", 2, "Астрахань", "Энзели", "sea", "2026-11-06T14:00:00", "2026-11-10T15:00:00", 760, "completed", "Морской рейс завершён, груз в порту Энзели.", 0, "2026-11-10T15:00:00", "2026-11-07T08:00:00"),
            ],
        },
        {
            "id": "rt-SCT-1006",
            "shipmentId": "SCT-1006",
            "name": "Грузовик до Махачкалы и морской рейс в Энзели",
            "templateId": "makh-anz-road-sea",
            "origin": "Махачкала",
            "destination": "Энзели",
            "distance": 770,
            "estimatedDuration": 0,
            "estimatedCost": 310000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1006", 1, "Каспийск", "Махачкала", "road", "2026-11-13T09:00:00", "2026-11-13T12:00:00", 30, "pending", "Отправление автотранспортом запланировано на 13 ноября.", 0),
                _stage("rt-SCT-1006", 2, "Махачкала", "Энзели", "sea", "2026-11-13T12:00:00", "2026-11-17T15:00:00", 740, "pending", "Морской рейс после подвоза в порт.", 0, None, "2026-11-13T20:00:00"),
            ],
        },
    ]

    documents: list[dict] = []
    documents += _full_docs("SCT-1001", "2026-11-09")
    documents += _full_docs("SCT-1002", "2026-11-10")
    documents += _full_docs("SCT-1003", "2026-11-09")
    documents += [
        _document("SCT-1004", "waybill", "verified", "WAY-1004", "2026-11-11", True, "Накладная приложена."),
        _document("SCT-1004", "invoice", "needs_attention", "", "", True, "Не указан номер документа."),
        _document("SCT-1004", "packing", "verified", "PKG-1004", "2026-11-11", True, "Упаковочный лист приложен."),
        _document("SCT-1004", "declaration", "missing", "", "", False, "Файл не загружен."),
        _document("SCT-1004", "origin", "verified", "ORG-1004", "2026-11-11", True, "Сертификат приложен."),
    ]
    documents += _full_docs("SCT-1005", "2026-11-04")
    documents += [
        _document("SCT-1006", "waybill", "verified", "WAY-1006", "2026-11-11", True, "Накладная приложена."),
        _document("SCT-1006", "invoice", "verified", "INV-1006", "2026-11-11", True, "Инвойс приложен."),
        _document("SCT-1006", "packing", "verified", "PKG-1006", "2026-11-11", True, "Упаковочный лист приложен."),
        _document("SCT-1006", "declaration", "verified", "DEC-1006", "2026-11-11", True, "Декларация приложена."),
        _document("SCT-1006", "origin", "pending", "ORG-1006", "2026-11-11", True, "Ожидает проверки."),
    ]

    journal = [
        {
            "id": "j-seed-1005",
            "shipmentId": "SCT-1005",
            "type": "preclearance",
            "title": "Предварительное оформление",
            "result": "Предварительно подготовлена",
            "details": "Комплект из пяти документов был полным. Запись демонстрационного журнала, не блокчейн.",
            "at": "2026-11-04T11:30:00",
        },
        {
            "id": "j-seed-1002",
            "shipmentId": "SCT-1002",
            "type": "preclearance",
            "title": "Предварительное оформление",
            "result": "Предварительно подготовлена",
            "details": "Заявка принята в демонстрационный журнал до выхода судна.",
            "at": "2026-11-10T15:00:00",
        },
        {
            "id": "j-seed-1004",
            "shipmentId": "SCT-1004",
            "type": "documents",
            "title": "Проверка комплекта",
            "result": "есть замечания",
            "details": "Нет таможенной декларации, в инвойсе не заполнен номер.",
            "at": "2026-11-11T18:00:00",
        },
    ]

    return {
        "shipments": shipments,
        "routes": routes,
        "predictions": [],
        "documents": documents,
        "notifications": [],
        "journal": journal,
        "ports": json.loads(json.dumps(PORTS)),
        "emissionFactors": dict(DEFAULT_EMISSION_FACTORS),
        "users": default_users(),
        "sessions": [],
        "profile": {
            "name": "Демо-логист",
            "role": "Логист коридора Север — Юг",
            "organization": "Smart Caspian Transit",
            "userId": "user-logist",
        },
        "lastRecalculatedAt": None,
    }
