"""Шесть тестовых грузов коридора (сценарии хакатона)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog import REQUIRED_DOCUMENT_TYPES, document_label
from app.models import ShipmentRow
from app.persistence.mapper import load_state, save_state


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
        "schedulePlannedStart": start,
        "schedulePlannedArrival": arrival,
        "actualArrival": actual,
        "status": status,
        "distanceKm": distance,
        "delayHours": delay_hours,
        "shipDeparture": ship_departure,
        "scheduleShipDeparture": ship_departure,
        "description": description,
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
    file_meta = None
    if with_file:
        file_meta = {
            "storedName": f"{document_id}.txt",
            "originalName": f"{document_label(type_id)} {shipment_id}.txt",
            "size": 120,
            "mime": "text/plain",
        }
    return {
        "id": document_id,
        "shipmentId": shipment_id,
        "name": document_label(type_id),
        "type": type_id,
        "file": file_meta,
        "status": status,
        "uploadedAt": "2026-11-09T10:00:00" if with_file else None,
        "comment": comment,
        "fields": {"number": number, "issuedAt": issued_at},
    }


def _full_docs(shipment_id: str, issued_at: str) -> list[dict]:
    return [
        _document(shipment_id, type_id, "verified", f"{type_id[:3].upper()}-{shipment_id[-4:]}", issued_at, True, "Комплект в порядке.")
        for type_id in REQUIRED_DOCUMENT_TYPES
    ]


def build_demo_payload() -> dict:
    shipments = [
        {
            "id": "SCT-1001",
            "name": "Комплект промышленного оборудования",
            "category": "Промышленное оборудование",
            "weight": 420,
            "containerCount": 18,
            "sender": "ООО «ВолгаМаш»",
            "receiver": "Anzali Industrial Co.",
            "origin": "Саратов",
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
            "origin": "Волгоград",
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
            "origin": "Каспийск",
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
            "origin": "Волгоград",
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
            "name": "Электроника коридора Север — Юг",
            "category": "Промышленная электроника",
            "weight": 210,
            "containerCount": 9,
            "sender": "ООО «МоскваТехЭкспорт»",
            "receiver": "Mumbai Hub Logistics Pvt Ltd",
            "origin": "Москва",
            "destination": "Мумбаи",
            "status": "in_transit",
            "plannedDeparture": "2026-11-09T06:00:00",
            "plannedArrival": "2026-11-22T18:00:00",
            "predictedArrival": "2026-11-23T08:00:00",
            "currentLocation": "перегон Москва — Астрахань (демо-оценка)",
            "currentPort": None,
            "currentTransport": "rail",
            "routeId": "rt-SCT-1006",
            "templateId": "moscow-mumbai-corridor",
            "transportSequence": ["rail", "sea", "road", "sea"],
            "riskScore": 0,
            "notes": "Демонстрационная сквозная схема Москва → Астрахань → Энзели → Бендер-Аббас → Мумбаи. Расстояния и сроки — оценки для хакатона, не коммерческое предложение.",
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
            "origin": "Саратов",
            "destination": "Энзели",
            "distance": 1280,
            "estimatedDuration": 0,
            "estimatedCost": 430000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1001", 1, "Саратов", "Астрахань", "rail", "2026-11-10T08:00:00", "2026-11-11T12:00:00", 520, "delayed", "Поезд следует с опозданием.", 30),
                _stage("rt-SCT-1001", 2, "Астрахань", "Энзели", "sea", "2026-11-11T12:00:00", "2026-11-14T18:00:00", 760, "pending", "Морской рейс при коротком окне пересадки.", 0, None, "2026-11-12T20:00:00"),
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
                _stage("rt-SCT-1002", 1, "Каспийск", "Махачкала", "road", "2026-11-11T06:00:00", "2026-11-11T08:00:00", 25, "completed", "Автоплечо выполнено.", 0, "2026-11-11T08:00:00"),
                _stage("rt-SCT-1002", 2, "Махачкала", "Энзели", "sea", "2026-11-11T08:00:00", "2026-11-13T18:00:00", 740, "in_progress", "Судно в море.", 0, None, "2026-11-11T16:00:00"),
            ],
        },
        {
            "id": "rt-SCT-1003",
            "shipmentId": "SCT-1003",
            "name": "Поезд до Астрахани и морской рейс в Амирабад",
            "templateId": "ast-amr-rail-sea",
            "origin": "Волгоград",
            "destination": "Амирабад",
            "distance": 1360,
            "estimatedDuration": 0,
            "estimatedCost": 490000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1003", 1, "Волгоград", "Астрахань", "rail", "2026-11-09T20:00:00", "2026-11-10T12:00:00", 380, "completed", "Поезд прибыл в порт.", 0, "2026-11-10T12:00:00"),
                _stage("rt-SCT-1003", 2, "Астрахань", "Амирабад", "sea", "2026-11-10T12:00:00", "2026-11-16T08:00:00", 980, "pending", "Ожидание погодного окна.", 0, None, "2026-11-12T22:00:00"),
            ],
        },
        {
            "id": "rt-SCT-1004",
            "shipmentId": "SCT-1004",
            "name": "Грузовик до Махачкалы и морской рейс в Амирабад",
            "templateId": "makh-amr-road-sea",
            "origin": "Каспийск",
            "destination": "Амирабад",
            "distance": 1075,
            "estimatedDuration": 0,
            "estimatedCost": 360000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1004", 1, "Каспийск", "Махачкала", "road", "2026-11-12T07:00:00", "2026-11-12T09:00:00", 25, "completed", "Груз в порту.", 0, "2026-11-12T09:00:00"),
                _stage("rt-SCT-1004", 2, "Махачкала", "Амирабад", "sea", "2026-11-12T09:00:00", "2026-11-17T12:00:00", 1050, "pending", "Ожидание документов.", 0, None, "2026-11-15T08:00:00"),
            ],
        },
        {
            "id": "rt-SCT-1005",
            "shipmentId": "SCT-1005",
            "name": "Волгоград — Астрахань — Энзели (доставлен)",
            "templateId": "ast-anz-rail-sea",
            "origin": "Волгоград",
            "destination": "Энзели",
            "distance": 1140,
            "estimatedDuration": 0,
            "estimatedCost": 410000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1005", 1, "Волгоград", "Астрахань", "rail", "2026-11-05T08:00:00", "2026-11-06T14:00:00", 380, "completed", "ЖД участок завершён.", 0, "2026-11-06T14:00:00"),
                _stage("rt-SCT-1005", 2, "Астрахань", "Энзели", "sea", "2026-11-06T14:00:00", "2026-11-10T15:00:00", 760, "completed", "Рейс завершён.", 0, "2026-11-10T15:00:00", "2026-11-07T08:00:00"),
            ],
        },
        {
            "id": "rt-SCT-1006",
            "shipmentId": "SCT-1006",
            "name": "Сквозной коридор Север — Юг: Москва → Мумбаи (демо)",
            "templateId": "moscow-mumbai-corridor",
            "origin": "Москва",
            "destination": "Мумбаи",
            "distance": 4850,
            "estimatedDuration": 0,
            "estimatedCost": 1850000,
            "carbonFootprint": 0,
            "stages": [
                _stage("rt-SCT-1006", 1, "Москва", "Астрахань", "rail", "2026-11-09T06:00:00", "2026-11-11T14:00:00", 1420, "in_progress", "Ж/д плечо до Каспия (оценка для демо).", 4),
                _stage("rt-SCT-1006", 2, "Астрахань", "Энзели", "sea", "2026-11-11T14:00:00", "2026-11-13T20:00:00", 760, "pending", "Каспийский морской участок.", 0, None, "2026-11-12T18:00:00"),
                _stage("rt-SCT-1006", 3, "Энзели", "Бендер-Аббас", "road", "2026-11-13T20:00:00", "2026-11-16T06:00:00", 1180, "pending", "Сухопутный транзит через Иран (демо-схема).", 0),
                _stage("rt-SCT-1006", 4, "Бендер-Аббас", "Мумбаи", "sea", "2026-11-16T10:00:00", "2026-11-22T18:00:00", 920, "pending", "Морское плечо в Индию (оценка для демо).", 0, None, "2026-11-16T14:00:00"),
            ],
        },
    ]

    documents: list[dict] = []
    documents += _full_docs("SCT-1001", "2026-11-09")
    documents += _full_docs("SCT-1002", "2026-11-10")
    documents += _full_docs("SCT-1003", "2026-11-09")
    documents += [
        _document("SCT-1004", "waybill", "verified", "WAY-1004", "2026-11-11", True, "Накладная приложена."),
        _document("SCT-1004", "invoice", "needs_attention", "", "", True, "Не указан номер."),
        _document("SCT-1004", "packing", "verified", "PKG-1004", "2026-11-11", True, "Упаковочный лист приложен."),
        _document("SCT-1004", "declaration", "missing", "", "", False, "Файл не загружен."),
        _document("SCT-1004", "origin", "verified", "ORG-1004", "2026-11-11", True, "Сертификат приложен."),
    ]
    documents += _full_docs("SCT-1005", "2026-11-04")
    documents += _full_docs("SCT-1006", "2026-11-08")

    journal = [
        {
            "id": "j-seed-1005",
            "shipmentId": "SCT-1005",
            "type": "preclearance",
            "title": "Предварительное оформление",
            "result": "Предварительно подготовлена",
            "details": "Комплект документов полный.",
            "at": "2026-11-04T11:30:00",
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

    return {"shipments": shipments, "routes": routes, "documents": documents, "journal": journal}


def seed_demo_if_empty(session: Session) -> bool:
    """Возвращает True, если демо-грузы были добавлены."""
    count = session.scalar(select(func.count()).select_from(ShipmentRow)) or 0
    if count > 0:
        return False

    from app.config import UPLOADS_DIR
    from app.demo_reset import apply_demo

    data = load_state(session)
    apply_demo(data, UPLOADS_DIR)
    save_state(session, data)
    session.commit()
    return True
