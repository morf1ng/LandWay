"""Исходное расписание этапа, прогноз (delayHours) и оперативная цепочка."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.risk import iso, parse_dt

TRANSFER_BUFFER_HOURS = 2.0


def ensure_schedule_fields(stage: dict) -> None:
    if not stage.get("schedulePlannedStart"):
        stage["schedulePlannedStart"] = stage.get("plannedStart")
    if not stage.get("schedulePlannedArrival"):
        stage["schedulePlannedArrival"] = stage.get("plannedArrival")
    if stage.get("shipDeparture") and not stage.get("scheduleShipDeparture"):
        stage["scheduleShipDeparture"] = stage.get("shipDeparture")


def stamp_schedule_on_create(stage: dict) -> dict:
    ensure_schedule_fields(stage)
    return stage


def schedule_baseline_arrival(stage: dict) -> datetime | None:
    ensure_schedule_fields(stage)
    return parse_dt(stage.get("schedulePlannedArrival"))


def stage_arrival(stage: dict) -> datetime | None:
    """Ожидаемое или фактическое завершение этапа."""
    if stage.get("actualArrival"):
        return parse_dt(stage["actualArrival"])
    ensure_schedule_fields(stage)
    delay = float(stage.get("delayHours") or 0)
    baseline = parse_dt(stage.get("schedulePlannedArrival"))
    if (
        baseline
        and delay > 0
        and stage.get("transportType") == "rail"
        and stage.get("status") in ("delayed", "in_progress", "pending")
    ):
        return baseline + timedelta(hours=delay)
    operational = parse_dt(stage.get("plannedArrival"))
    if operational is not None:
        return operational
    if baseline is not None:
        return baseline + timedelta(hours=delay)
    return None


def _leg_duration_hours(stage: dict) -> float:
    ensure_schedule_fields(stage)
    start = parse_dt(stage["schedulePlannedStart"])
    end = parse_dt(stage["schedulePlannedArrival"])
    if start and end:
        return max(0.0, (end - start).total_seconds() / 3600)
    return 0.0


def _sea_buffer_hours(stage: dict) -> float:
    ensure_schedule_fields(stage)
    start = parse_dt(stage["schedulePlannedStart"])
    dep = parse_dt(stage.get("scheduleShipDeparture"))
    if start and dep:
        return max(0.0, (dep - start).total_seconds() / 3600)
    return 10.0


def _sea_sail_hours(stage: dict) -> float:
    ensure_schedule_fields(stage)
    dep = parse_dt(stage.get("scheduleShipDeparture"))
    end = parse_dt(stage["schedulePlannedArrival"])
    if dep and end:
        return max(0.0, (end - dep).total_seconds() / 3600)
    return _leg_duration_hours(stage)


def sync_stage_chain(route: dict, from_index: int = 0, *, transfer_buffer: float = TRANSFER_BUFFER_HOURS) -> None:
    """Сдвигает plannedStart/plannedArrival последующих этапов от прибытия предыдущего."""
    stages = route.get("stages") or []
    if not stages or from_index >= len(stages):
        return
    for stage in stages:
        ensure_schedule_fields(stage)

    cursor: datetime | None = None
    if from_index > 0:
        cursor = stage_arrival(stages[from_index - 1])

    for i in range(from_index, len(stages)):
        stage = stages[i]
        if stage.get("status") == "completed":
            cursor = stage_arrival(stage)
            continue
        if stage.get("transportType") == "rail" and stage.get("status") in ("delayed", "in_progress"):
            cursor = stage_arrival(stage)
            continue

        if cursor is None:
            cursor = parse_dt(stage.get("schedulePlannedStart")) or parse_dt(stage.get("plannedStart"))
            if cursor is None:
                continue

        start = cursor + timedelta(hours=transfer_buffer) if i > 0 or from_index > 0 else cursor
        if stage.get("transportType") == "sea":
            ready = start + timedelta(hours=_sea_buffer_hours(stage))
            sched_dep = parse_dt(stage.get("scheduleShipDeparture"))
            ship_at = max(ready, sched_dep) if sched_dep else ready
            sail = _sea_sail_hours(stage)
            stage["plannedStart"] = iso(start)
            stage["shipDeparture"] = iso(ship_at)
            stage["plannedArrival"] = iso(ship_at + timedelta(hours=sail))
            cursor = parse_dt(stage["plannedArrival"])
        else:
            duration = _leg_duration_hours(stage)
            if duration <= 0:
                duration = max(
                    0.0,
                    (
                        (parse_dt(stage.get("plannedArrival")) - parse_dt(stage.get("plannedStart"))).total_seconds() / 3600
                    )
                    if parse_dt(stage.get("plannedArrival")) and parse_dt(stage.get("plannedStart"))
                    else 0.0,
                )
            stage["plannedStart"] = iso(start)
            stage["plannedArrival"] = iso(start + timedelta(hours=duration))
            cursor = parse_dt(stage["plannedArrival"])


def rail_expected_arrival(stage: dict) -> datetime | None:
    """Прогноз прибытия поезда от исходного расписания и абсолютного delayHours."""
    ensure_schedule_fields(stage)
    baseline = parse_dt(stage.get("schedulePlannedArrival"))
    if baseline is None:
        return None
    return baseline + timedelta(hours=float(stage.get("delayHours") or 0))
