"""Прогноз по похожим историческим рейсам коридора ж/д → паром."""

from __future__ import annotations

import statistics
from datetime import datetime

from app.data.corridor_history import CORRIDOR_ID, CORRIDOR_LABEL, DATA_SOURCE, synthetic_corridor_history
from app.services.risk import assess, iso, parse_dt, risk_level, stage_arrival

MIN_SIMILAR = 3
WIND_TOL = 5.0
WORKLOAD_TOL = 18.0
BUFFER_TOL = 3.5
HISTORY_WEIGHT = 0.55
HOLDOUT_SHARE = 0.3

FACTOR_LABELS = {
    "direction": "то же направление (порт отправления → порт назначения)",
    "bufferHours": f"запас на стыковку ±{BUFFER_TOL:g} ч с учётом известного опоздания поезда",
    "windSpeedMs": f"ветер ±{WIND_TOL:g} м/с",
    "portWorkload": f"загрузка порта ±{WORKLOAD_TOL:g} п.п.",
}


def prediction_extras(result: dict) -> dict:
    return {key: value for key, value in result.items() if key.startswith("history")}


def default_history() -> list[dict]:
    return synthetic_corridor_history()


def corridor_applicable(shipment: dict, route: dict) -> bool:
    if shipment.get("destination") != "Энзели":
        return False
    stages = route.get("stages") or []
    open_stages = [stage for stage in stages if stage.get("status") != "completed"]
    has_rail = any(stage.get("transportType") == "rail" for stage in open_stages)
    has_sea = any(stage.get("transportType") == "sea" for stage in open_stages)
    return has_rail and has_sea


def current_features(shipment: dict, route: dict, ports: list[dict], moment: datetime) -> dict | None:
    stages = route.get("stages") or []
    sea = next((s for s in stages if s["transportType"] == "sea" and s["status"] == "pending"), None)
    rail = next(
        (s for s in stages if s["transportType"] == "rail" and s["status"] in ("pending", "in_progress", "delayed")),
        None,
    )
    if not sea or not rail:
        return None
    port = next((p for p in ports if p["name"] == sea["location"]), None)
    arrival = stage_arrival(rail)
    ship_at = parse_dt(sea.get("shipDeparture"))
    buffer = (ship_at - arrival).total_seconds() / 3600 if arrival and ship_at else None
    return {
        "corridorId": CORRIDOR_ID,
        "direction": f"{sea['location']} → {shipment['destination']}",
        "seaPort": sea["location"],
        "destination": shipment["destination"],
        "bufferHoursAtForecast": round(buffer, 1) if buffer is not None else None,
        "railDelayHoursKnown": float(rail.get("delayHours") or 0),
        "portWorkload": float(port["workload"]) if port else 55.0,
        "windSpeedMs": float(port["windSpeed"]) if port else 8.0,
        "weatherSeverity": port.get("weatherSeverity") if port else "clear",
        "forecastAt": iso(moment),
    }


def _outcome_known(obs: dict, before: str | None) -> bool:
    if not before:
        return True
    return obs.get("actualShipDeparture", "") < before


def _similar(obs: dict, features: dict, before: str | None) -> bool:
    if obs.get("corridorId") != features.get("corridorId"):
        return False
    if obs.get("seaPort") != features.get("seaPort") or obs.get("destination") != features.get("destination"):
        return False
    if not _outcome_known(obs, before):
        return False
    if features.get("bufferHoursAtForecast") is None or obs.get("bufferHoursAtForecast") is None:
        return False
    if abs(float(obs["bufferHoursAtForecast"]) - float(features["bufferHoursAtForecast"])) > BUFFER_TOL:
        return False
    if abs(float(obs["windSpeedMs"]) - float(features["windSpeedMs"])) > WIND_TOL:
        return False
    return abs(float(obs["portWorkload"]) - float(features["portWorkload"])) <= WORKLOAD_TOL


def find_similar(history: list[dict], features: dict, *, before: str | None = None) -> list[dict]:
    return [obs for obs in history if _similar(obs, features, before)]


def _summary(similar: list[dict]) -> dict:
    missed = sum(1 for obs in similar if obs.get("missedFerry"))
    return {
        "missed": missed,
        "missRate": missed / len(similar),
        "medianDelay": statistics.median(float(obs["actualDelayHours"]) for obs in similar),
    }


def enrich_assessment(
    heuristic: dict,
    shipment: dict,
    route: dict,
    ports: list[dict],
    history: list[dict] | None,
    moment: datetime,
) -> dict:
    base_meta = {"historySource": DATA_SOURCE, "historyMatchCount": 0, "historyMinMatches": MIN_SIMILAR}
    if shipment.get("status") == "delivered" or not corridor_applicable(shipment, route):
        return {
            **heuristic,
            **base_meta,
            "historyMode": "not_applicable",
            "historyCorridor": None,
            "historyNote": "История ведётся только для коридора ж/д → паром в Энзели",
        }

    features = current_features(shipment, route, ports, moment)
    if not features:
        return {
            **heuristic,
            **base_meta,
            "historyMode": "heuristic_fallback",
            "historyCorridor": CORRIDOR_LABEL,
            "historyNote": "Нет ожидающей пары этапов «поезд → паром» для сравнения",
        }

    pool = history or default_history()
    similar = find_similar(pool, features, before=features["forecastAt"])
    count = len(similar)
    meta = {
        **base_meta,
        "historyCorridor": CORRIDOR_LABEL,
        "historyMatchCount": count,
        "historyPoolSize": len(pool),
        "historyFeatures": features,
        "historyFactors": list(FACTOR_LABELS.values()),
        "historyMatchIds": [obs["id"] for obs in similar][:12],
    }

    if count < MIN_SIMILAR:
        reasons = list(heuristic.get("reasons") or [])
        reasons.append(
            f"похожих рейсов в синтетической истории {count} из {len(pool)} — меньше {MIN_SIMILAR}, расчёт по эвристике"
        )
        return {
            **heuristic,
            **meta,
            "reasons": reasons,
            "historyMode": "heuristic_fallback",
            "historyNote": f"Недостаточно похожих рейсов: {count} < {MIN_SIMILAR}. Используется эвристика правил.",
        }

    stats = _summary(similar)
    delay = round(HISTORY_WEIGHT * stats["medianDelay"] + (1 - HISTORY_WEIGHT) * float(heuristic["estimatedDelay"]))
    probability = int(round(HISTORY_WEIGHT * stats["missRate"] * 100 + (1 - HISTORY_WEIGHT) * float(heuristic["probability"])))
    reasons = [
        (
            f"в {stats['missed']} из {count} похожих рейсов паром был пропущен; "
            f"медианная задержка доставки {stats['medianDelay']:.0f} ч (синтетическая история)"
        ),
        *(heuristic.get("reasons") or []),
    ]
    return {
        **heuristic,
        **meta,
        "estimatedDelay": int(delay),
        "probability": probability,
        "riskLevel": risk_level(probability, False),
        "reasons": reasons,
        "historyMode": "history_blend",
        "historyMissRate": round(stats["missRate"], 3),
        "historyMissedCount": stats["missed"],
        "historyMedianDelayHours": round(stats["medianDelay"], 1),
        "historyHeuristicDelayHours": heuristic["estimatedDelay"],
        "historyNote": (
            f"Задержка = {round(HISTORY_WEIGHT * 100)}% медианы похожих рейсов + "
            f"{round((1 - HISTORY_WEIGHT) * 100)}% эвристики правил"
        ),
    }


def _replay_inputs(obs: dict) -> tuple[dict, dict, list[dict], list[dict], datetime]:
    """Состояние на момент прогноза прошлого рейса (без исхода)."""
    from datetime import timedelta

    from app.catalog import REQUIRED_DOCUMENT_TYPES

    train_planned = parse_dt(obs["plannedTrainArrival"])
    ship_planned = parse_dt(obs["plannedShipDeparture"])
    forecast_at = parse_dt(obs["forecastAt"])
    shipment = {"id": obs["id"], "status": "delayed", "origin": obs["seaPort"], "destination": obs["destination"], "plannedArrival": iso(ship_planned)}
    route = {
        "id": f"rt-{obs['id']}",
        "stages": [
            {
                "id": f"{obs['id']}-1", "transportType": "rail", "status": "delayed" if obs["railDelayHoursKnown"] else "in_progress",
                "location": "Саратов", "nextLocation": obs["seaPort"],
                "plannedStart": iso(train_planned - timedelta(hours=26)), "plannedArrival": iso(train_planned),
                "delayHours": obs["railDelayHoursKnown"], "actualArrival": None, "distanceKm": 520,
            },
            {
                "id": f"{obs['id']}-2", "transportType": "sea", "status": "pending",
                "location": obs["seaPort"], "nextLocation": obs["destination"],
                "plannedStart": iso(train_planned), "plannedArrival": iso(ship_planned + timedelta(hours=48)),
                "shipDeparture": iso(ship_planned), "delayHours": 0, "actualArrival": None, "distanceKm": 760,
            },
        ],
    }
    ports = [{
        "name": obs["seaPort"], "workload": obs["portWorkload"], "windSpeed": obs["windSpeedMs"],
        "weatherSeverity": obs["weatherSeverity"],
    }, {"name": obs["destination"], "workload": 50, "windSpeed": 6, "weatherSeverity": "clear"}]
    documents = [
        {"type": type_id, "status": "verified", "file": {"storedName": "x"}, "fields": {"number": "1", "issuedAt": "2025-01-01"}}
        for type_id in REQUIRED_DOCUMENT_TYPES
    ]
    return shipment, route, ports, documents, forecast_at


def backtest_report(history: list[dict] | None = None) -> dict:
    """Проверка на более поздних рейсах: для каждого используется только история с известным исходом."""
    pool = sorted(history or default_history(), key=lambda item: item["forecastAt"])
    split = int(len(pool) * (1 - HOLDOUT_SHARE))
    test = pool[split:]

    model_errors: list[float] = []
    heuristic_errors: list[float] = []
    history_used = 0
    for obs in test:
        shipment, route, ports, documents, moment = _replay_inputs(obs)
        heuristic = assess(shipment, route, ports, documents, moment)
        model = enrich_assessment(heuristic, shipment, route, ports, pool, moment)
        actual = float(obs["actualDelayHours"])
        heuristic_errors.append(abs(float(heuristic["estimatedDelay"]) - actual))
        model_errors.append(abs(float(model["estimatedDelay"]) - actual))
        if model["historyMode"] == "history_blend":
            history_used += 1

    def mae(values: list[float]) -> float | None:
        return round(statistics.mean(values), 1) if values else None

    return {
        "dataSource": DATA_SOURCE,
        "corridor": CORRIDOR_LABEL,
        "trainTrips": split,
        "evaluatedTrips": len(test),
        "historySamplesUsed": history_used,
        "modelMaeHours": mae(model_errors),
        "historyMaeHours": mae(model_errors),
        "heuristicMaeHours": mae(heuristic_errors),
        "note": (
            f"Демонстрационная проверка на синтетических данных: последние {len(test)} рейсов по хронологии. "
            "Для каждого используются только более ранние рейсы, исход которых уже был известен."
        ),
    }
