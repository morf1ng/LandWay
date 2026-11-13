"""Справочники демонстрационного коридора. Не зависят от базы."""

from __future__ import annotations

DOCUMENT_TYPES = [
    {"id": "waybill", "label": "Транспортная накладная"},
    {"id": "invoice", "label": "Инвойс"},
    {"id": "packing", "label": "Упаковочный лист"},
    {"id": "declaration", "label": "Таможенная декларация"},
    {"id": "origin", "label": "Сертификат происхождения"},
]

REQUIRED_DOCUMENT_TYPES = [item["id"] for item in DOCUMENT_TYPES]

TRANSPORT_TYPES = [
    {"id": "rail", "label": "поезд"},
    {"id": "sea", "label": "корабль"},
    {"id": "road", "label": "грузовик"},
    {"id": "none", "label": "не в пути"},
]

STATUSES = [
    {"id": "awaiting", "label": "Ожидает отправления"},
    {"id": "in_transit", "label": "В пути"},
    {"id": "delayed", "label": "Задерживается"},
    {"id": "documents_issue", "label": "Проверка документов"},
    {"id": "delivered", "label": "Доставлен"},
]

# кг CO₂ на тонно-километр. Меняются из раздела экологии.
DEFAULT_EMISSION_FACTORS = {
    "rail": 0.028,
    "sea": 0.015,
    "road": 0.095,
}

PORTS = [
    {
        "id": "astrakhan",
        "name": "Астрахань",
        "location": "Россия, дельта Волги",
        "lat": 46.35,
        "lon": 48.04,
        "x": 48,
        "y": 18,
        "workload": 88,
        "weather": "штормовой ветер, ограничение лоцманской проводки",
        "weatherSeverity": "adverse",
        "windSpeed": 18,
        "delayRisk": "high",
    },
    {
        "id": "makhachkala",
        "name": "Махачкала",
        "location": "Россия, западный берег Каспия",
        "lat": 42.98,
        "lon": 47.50,
        "x": 40,
        "y": 42,
        "workload": 64,
        "weather": "ясно, слабый ветер",
        "weatherSeverity": "clear",
        "windSpeed": 5,
        "delayRisk": "low",
    },
    {
        "id": "anzali",
        "name": "Энзели",
        "location": "Иран, юго-запад Каспия",
        "lat": 37.47,
        "lon": 49.46,
        "x": 56,
        "y": 76,
        "workload": 48,
        "weather": "ясно, слабое волнение",
        "weatherSeverity": "clear",
        "windSpeed": 7,
        "delayRisk": "low",
    },
    {
        "id": "amirabad",
        "name": "Амирабад",
        "location": "Иран, юго-восток Каспия",
        "lat": 36.85,
        "lon": 53.37,
        "x": 82,
        "y": 82,
        "workload": 44,
        "weather": "неблагоприятная погода, сильный ветер",
        "weatherSeverity": "adverse",
        "windSpeed": 19,
        "delayRisk": "high",
    },
]

CITIES = {
    "Москва": {"lat": 55.7558, "lon": 37.6173, "x": 8, "y": 3},
    "Саратов": {"lat": 51.53, "lon": 46.03, "x": 46, "y": 7},
    "Волгоград": {"lat": 48.71, "lon": 44.51, "x": 30, "y": 12},
    "Каспийск": {"lat": 42.88, "lon": 47.64, "x": 37, "y": 46},
    "Бендер-Аббас": {"lat": 27.1865, "lon": 56.2808, "x": 90, "y": 88},
    "Мумбаи": {"lat": 19.076, "lon": 72.8777, "x": 98, "y": 95},
}

PORT_NAMES = [port["name"] for port in PORTS]

SEA_DISTANCE = {
    frozenset({"Астрахань", "Энзели"}): 760,
    frozenset({"Астрахань", "Амирабад"}): 980,
    frozenset({"Астрахань", "Махачкала"}): 520,
    frozenset({"Махачкала", "Энзели"}): 740,
    frozenset({"Махачкала", "Амирабад"}): 1050,
    frozenset({"Энзели", "Амирабад"}): 420,
    frozenset({"Энзели", "Бендер-Аббас"}): 1180,
    frozenset({"Бендер-Аббас", "Мумбаи"}): 920,
    frozenset({"Москва", "Астрахань"}): 1420,
}


def sea_distance(origin: str, destination: str) -> float:
    return float(SEA_DISTANCE.get(frozenset({origin, destination}), 800))


def place(name: str) -> dict:
    for port in PORTS:
        if port["name"] == name:
            return {"name": name, "lat": port["lat"], "lon": port["lon"], "x": port["x"], "y": port["y"]}
    city = CITIES[name]
    return {"name": name, **city}


def port_by_name(name: str) -> dict | None:
    for port in PORTS:
        if port["name"] == name:
            return port
    return None


def document_label(type_id: str) -> str:
    for item in DOCUMENT_TYPES:
        if item["id"] == type_id:
            return item["label"]
    return type_id


def _stage(
    origin: str,
    destination: str,
    transport: str,
    distance_km: float,
    hours: float,
    description: str,
    buffer_hours: float = 0,
) -> dict:
    return {
        "from": origin,
        "to": destination,
        "transport": transport,
        "distanceKm": distance_km,
        "hours": hours,
        "bufferHours": buffer_hours,
        "description": description,
    }


# Шаблоны маршрутов между портами коридора. У каждого есть точки и этапы.
ROUTE_TEMPLATES = [
    {
        "id": "ast-anz-rail-sea",
        "name": "Поезд до Астрахани и морской рейс в Энзели",
        "origin": "Астрахань",
        "destination": "Энзели",
        "sequence": ["rail", "sea"],
        "cost": 430000,
        "stages": [
            _stage("Саратов", "Астрахань", "rail", 520, 26, "Железнодорожный подвод к порту Астрахань"),
            _stage("Астрахань", "Энзели", "sea", 760, 48, "Морской рейс Астрахань — Энзели", 12),
        ],
    },
    {
        "id": "ast-anz-road-makh",
        "name": "Автотранспорт в Махачкалу и морской рейс в Энзели",
        "origin": "Астрахань",
        "destination": "Энзели",
        "sequence": ["road", "sea"],
        "cost": 545000,
        "stages": [
            _stage("Астрахань", "Махачкала", "road", 480, 16, "Автомобильное плечо в порт Махачкала"),
            _stage("Махачкала", "Энзели", "sea", 740, 42, "Морской рейс Махачкала — Энзели", 10),
        ],
    },
    {
        "id": "ast-anz-rail-road-sea",
        "name": "Поезд, грузовик до Астрахани и море в Энзели",
        "origin": "Астрахань",
        "destination": "Энзели",
        "sequence": ["rail", "road", "sea"],
        "cost": 470000,
        "stages": [
            _stage("Саратов", "Волгоград", "rail", 380, 14, "Железнодорожный участок Саратов — Волгоград"),
            _stage("Волгоград", "Астрахань", "road", 380, 12, "Автомобильный подвоз в порт Астрахань"),
            _stage("Астрахань", "Энзели", "sea", 760, 48, "Морской рейс Астрахань — Энзели", 10),
        ],
    },
    {
        "id": "makh-anz-road-sea",
        "name": "Грузовик до Махачкалы и морской рейс в Энзели",
        "origin": "Махачкала",
        "destination": "Энзели",
        "sequence": ["road", "sea"],
        "cost": 310000,
        "stages": [
            _stage("Каспийск", "Махачкала", "road", 25, 2, "Короткое автомобильное плечо до порта"),
            _stage("Махачкала", "Энзели", "sea", 740, 42, "Морской рейс Махачкала — Энзели", 8),
        ],
    },
    {
        "id": "makh-anz-via-ast",
        "name": "Поезд в Астрахань и морской рейс в Энзели",
        "origin": "Махачкала",
        "destination": "Энзели",
        "sequence": ["rail", "sea"],
        "cost": 610000,
        "stages": [
            _stage("Махачкала", "Астрахань", "rail", 490, 18, "Железнодорожный перевод груза в Астрахань"),
            _stage("Астрахань", "Энзели", "sea", 760, 48, "Морской рейс Астрахань — Энзели", 12),
        ],
    },
    {
        "id": "ast-amr-rail-sea",
        "name": "Поезд до Астрахани и морской рейс в Амирабад",
        "origin": "Астрахань",
        "destination": "Амирабад",
        "sequence": ["rail", "sea"],
        "cost": 490000,
        "stages": [
            _stage("Волгоград", "Астрахань", "rail", 380, 16, "Железнодорожный подвод к порту Астрахань"),
            _stage("Астрахань", "Амирабад", "sea", 980, 60, "Морской рейс Астрахань — Амирабад", 12),
        ],
    },
    {
        "id": "ast-amr-via-makh",
        "name": "Автотранспорт в Махачкалу и море в Амирабад",
        "origin": "Астрахань",
        "destination": "Амирабад",
        "sequence": ["road", "sea"],
        "cost": 600000,
        "stages": [
            _stage("Астрахань", "Махачкала", "road", 480, 16, "Автомобильное плечо в порт Махачкала"),
            _stage("Махачкала", "Амирабад", "sea", 1050, 64, "Морской рейс Махачкала — Амирабад", 10),
        ],
    },
    {
        "id": "makh-amr-road-sea",
        "name": "Грузовик до Махачкалы и морской рейс в Амирабад",
        "origin": "Махачкала",
        "destination": "Амирабад",
        "sequence": ["road", "sea"],
        "cost": 360000,
        "stages": [
            _stage("Каспийск", "Махачкала", "road", 25, 2, "Короткое автомобильное плечо до порта"),
            _stage("Махачкала", "Амирабад", "sea", 1050, 64, "Морской рейс Махачкала — Амирабад", 10),
        ],
    },
    {
        "id": "makh-amr-via-ast",
        "name": "Поезд в Астрахань и морской рейс в Амирабад",
        "origin": "Махачкала",
        "destination": "Амирабад",
        "sequence": ["rail", "sea"],
        "cost": 640000,
        "stages": [
            _stage("Махачкала", "Астрахань", "rail", 490, 18, "Железнодорожный перевод груза в Астрахань"),
            _stage("Астрахань", "Амирабад", "sea", 980, 60, "Морской рейс Астрахань — Амирабад", 12),
        ],
    },
]


def template_by_id(template_id: str) -> dict | None:
    for template in ROUTE_TEMPLATES:
        if template["id"] == template_id:
            return template
    return None


def match_template(origin: str, destination: str, sequence: list[str]) -> dict | None:
    for template in ROUTE_TEMPLATES:
        if (
            template["origin"] == origin
            and template["destination"] == destination
            and template["sequence"] == sequence
        ):
            return template
    return None
