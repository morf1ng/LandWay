"""Синтетическая история рейсов ж/д → паром по коридору Астрахань/Махачкала → Энзели.

Данные воспроизводимы (seed=42) и не являются реальными перевозками.
Для каждого рейса хранится снимок признаков на момент прогноза (forecastAt, за 12 ч
до планового прибытия поезда) и исход, который стал известен только после рейса.

Модель генерации:
- запас на стыковку на момент прогноза = плановый запас − уже известное опоздание поезда;
- после прогноза поезд может опоздать ещё (неизвестно в момент прогноза);
- перевалка в загруженном порту занимает больше времени;
- сильный ветер задерживает выход судна и переход.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

CORRIDOR_ID = "ast-enzeli-rail-sea"
CORRIDOR_LABEL = "Астрахань / Махачкала → Энзели (ж/д + паром)"
DATA_SOURCE = "synthetic"
HISTORY_VERSION = 2
TRIPS = 60
FERRY_INTERVAL_HOURS = 24


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def synthetic_corridor_history() -> list[dict]:
    rng = random.Random(42)
    base = datetime(2025, 3, 1, 8, 0, 0)
    rows: list[dict] = []
    for i in range(TRIPS):
        train_planned = base + timedelta(days=4 * i, hours=rng.choice([0, 6, 12]))
        sea_port = rng.choice(["Астрахань", "Астрахань", "Махачкала"])
        planned_buffer = rng.choice([4.0, 6.0, 8.0, 10.0, 12.0, 14.0])
        known_delay = rng.choice([0, 0, 2, 4, 6, 8, 12, 18, 24, 30])
        workload = rng.randint(45, 95)
        wind = round(rng.uniform(5, 22), 1)
        weather = "adverse" if wind >= 15 else "clear"

        later_delay = rng.choice([0, 0, 1, 2, 3, 5, 8])
        handling = 1.5 + max(0, workload - 60) / 12
        wind_hold = max(0.0, wind - 14) * 0.9

        train_actual = train_planned + timedelta(hours=known_delay + later_delay)
        ship_planned = train_planned + timedelta(hours=planned_buffer)
        ship_actual = ship_planned + timedelta(hours=wind_hold)
        missed = train_actual + timedelta(hours=handling) > ship_actual
        if missed:
            waits = 1
            while train_actual + timedelta(hours=handling) > ship_actual + timedelta(hours=FERRY_INTERVAL_HOURS * waits):
                waits += 1
            ship_actual = ship_actual + timedelta(hours=FERRY_INTERVAL_HOURS * waits)

        crossing_extra = max(0.0, wind - 12) * 0.6 + rng.uniform(0, 3)
        delivery_delay = (ship_actual - ship_planned).total_seconds() / 3600 + crossing_extra
        forecast_at = train_planned - timedelta(hours=12)

        rows.append(
            {
                "id": f"hist-{i + 1:03d}",
                "corridorId": CORRIDOR_ID,
                "direction": f"{sea_port} → Энзели",
                "seaPort": sea_port,
                "destination": "Энзели",
                "dataSource": DATA_SOURCE,
                "forecastAt": _iso(forecast_at),
                "departedAt": _iso(forecast_at),
                "plannedTrainArrival": _iso(train_planned),
                "plannedShipDeparture": _iso(ship_planned),
                "railDelayHoursKnown": float(known_delay),
                "bufferHoursAtForecast": round(planned_buffer - known_delay, 1),
                "portWorkload": float(workload),
                "windSpeedMs": wind,
                "weatherSeverity": weather,
                "actualTrainArrival": _iso(train_actual),
                "actualShipDeparture": _iso(ship_actual),
                "missedFerry": missed,
                "actualDelayHours": round(max(0.0, delivery_delay), 1),
            }
        )
    rows.sort(key=lambda item: item["forecastAt"])
    return rows
