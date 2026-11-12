"""Расчёт углеродного следа: масса (т) × расстояние (км) × коэффициент."""

from __future__ import annotations


def stage_emission(weight_tons: float, distance_km: float, transport: str, factors: dict) -> dict:
    factor = float(factors[transport])
    emission = round(weight_tons * distance_km * factor, 1)
    return {
        "transportType": transport,
        "distance": distance_km,
        "cargoWeight": weight_tons,
        "emissionFactor": factor,
        "co2Emission": emission,
    }


def calculate(weight_tons: float, stages: list[dict], factors: dict) -> dict:
    rows = []
    by_transport: dict[str, float] = {}
    for stage in stages:
        row = stage_emission(weight_tons, float(stage["distanceKm"]), stage["transportType"], factors)
        row["stageId"] = stage["id"]
        row["from"] = stage["location"]
        row["to"] = stage["nextLocation"]
        rows.append(row)
        by_transport[row["transportType"]] = round(by_transport.get(row["transportType"], 0) + row["co2Emission"], 1)
    total = round(sum(row["co2Emission"] for row in rows), 1)
    return {"total": total, "byTransport": by_transport, "stages": rows}
