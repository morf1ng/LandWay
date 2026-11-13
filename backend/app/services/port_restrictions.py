"""Статус выхода судов из порта: хранение, влияние на этапы, прогноз и маршруты."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.services.risk import iso, parse_dt, stage_arrival
from app.services.stage_schedule import ensure_schedule_fields, sync_stage_chain

DEPARTURE_OPEN = "open"
DEPARTURE_CLOSED = "departure_closed"


@dataclass
class StageImpact:
    port: str
    blocked: bool = False
    eta_unknown: bool = False
    extra_hours: float = 0.0
    reason: str = ""
    adjusted_departure: datetime | None = None

    def as_dict(self) -> dict:
        return {
            "port": self.port,
            "blocked": self.blocked,
            "etaUnknown": self.eta_unknown,
            "extraHours": round(self.extra_hours, 1),
            "reason": self.reason,
            "adjustedDeparture": iso(self.adjusted_departure) if self.adjusted_departure else None,
        }


def _note(payload: dict) -> str:
    return str(
        payload.get("restrictionNote")
        or payload.get("delayNote")
        or payload.get("message")
        or ""
    ).strip()


def parse_departure_payload(payload: dict, event_type: str) -> dict | None:
    """Структурированные поля для portFeed (без None, если обновление не про статус)."""
    status = payload.get("departureStatus")
    if status:
        status = str(status).strip().lower()
        if status not in (DEPARTURE_OPEN, DEPARTURE_CLOSED):
            raise ValueError("departureStatus должен быть open или departure_closed")
    elif event_type == "port.restriction":
        note = _note(payload).lower()
        if "открыт" in note and "закрыт" not in note:
            status = DEPARTURE_OPEN
        else:
            status = DEPARTURE_CLOSED
    elif event_type == "port.departure" and payload.get("departureStatus") is None:
        return None
    else:
        return None

    starts = payload.get("restrictionStartsAt")
    ends = payload.get("restrictionEndsAt")
    fields: dict = {
        "departureStatus": status,
        "restrictionNote": _note(payload) or None,
    }
    if starts:
        fields["restrictionStartsAt"] = iso(parse_dt(str(starts)))
    if ends:
        fields["restrictionEndsAt"] = iso(parse_dt(str(ends)))
    elif status == DEPARTURE_CLOSED:
        fields["restrictionEndsAt"] = None
    if status == DEPARTURE_OPEN:
        fields["restrictionEndsAt"] = None
        fields["restrictionStartsAt"] = None
    return fields


def merge_port_feed(existing: dict, incoming: dict, observed: datetime) -> dict:
    """Новые workload/wind не сбрасывают действующее ограничение."""
    merged = dict(existing or {})
    nullable_keys = {"restrictionEndsAt", "restrictionStartsAt", "restrictionNote"}
    for key, value in incoming.items():
        if value is not None or key in nullable_keys:
            merged[key] = value
    merged["observedAt"] = iso(observed)
    return merged


def feed_departure_view(feed: dict | None, *, moment: datetime | None = None) -> dict:
    if not feed:
        return {"departureStatus": DEPARTURE_OPEN}
    now = moment or datetime.now().replace(microsecond=0)
    status = str(feed.get("departureStatus") or DEPARTURE_OPEN)
    starts = parse_dt(feed.get("restrictionStartsAt")) or parse_dt(feed.get("observedAt"))
    ends = parse_dt(feed.get("restrictionEndsAt"))
    note = feed.get("restrictionNote") or feed.get("delayNote")
    if status == DEPARTURE_CLOSED:
        if ends and now >= ends:
            status = DEPARTURE_OPEN
        elif starts and now < starts:
            status = DEPARTURE_OPEN
    return {
        "departureStatus": status,
        "restrictionStartsAt": feed.get("restrictionStartsAt"),
        "restrictionEndsAt": feed.get("restrictionEndsAt"),
        "restrictionNote": note,
        "sourceName": feed.get("sourceName"),
        "sourceKind": feed.get("sourceKind"),
        "observedAt": feed.get("observedAt"),
    }


def _scheduled_sea_departure(stage: dict) -> datetime | None:
    ensure_schedule_fields(stage)
    return parse_dt(stage.get("scheduleShipDeparture") or stage.get("shipDeparture"))


def _expected_sea_departure(stage: dict, route: dict, moment: datetime) -> datetime | None:
    scheduled = _scheduled_sea_departure(stage)
    if scheduled:
        return scheduled
    idx = route["stages"].index(stage)
    if idx > 0:
        prev = stage_arrival(route["stages"][idx - 1])
        if prev:
            return prev + timedelta(hours=10)
    return parse_dt(stage.get("plannedStart"))


def _in_closure_window(departure: datetime, starts: datetime | None, ends: datetime | None) -> bool:
    if starts and departure < starts:
        return False
    if ends and departure >= ends:
        return False
    if starts or not ends:
        return True
    return False


def stage_departure_impact(stage: dict, route: dict, feed: dict | None, moment: datetime) -> StageImpact:
    if stage.get("transportType") != "sea" or stage.get("status") != "pending":
        return StageImpact(port=stage.get("location", ""))
    port = stage["location"]
    view = feed_departure_view(feed, moment=moment)
    if view["departureStatus"] != DEPARTURE_CLOSED:
        return StageImpact(port=port)

    starts = parse_dt(view.get("restrictionStartsAt")) or parse_dt(feed.get("observedAt") if feed else None)
    ends = parse_dt(view.get("restrictionEndsAt"))
    note = view.get("restrictionNote") or "Выход судов из порта ограничен"
    departure = _expected_sea_departure(stage, route, moment)
    if departure is None:
        return StageImpact(port=port, blocked=True, eta_unknown=True, reason=note)

    operational = parse_dt(stage.get("shipDeparture"))
    check_time = operational if operational and operational > departure else departure
    if not _in_closure_window(check_time, starts, ends) and not _in_closure_window(departure, starts, ends):
        return StageImpact(port=port)

    if ends is None:
        return StageImpact(
            port=port,
            blocked=True,
            eta_unknown=True,
            reason=f"{port}: {note} (срок открытия неизвестен, ETA не определён)",
        )

    first_open = ends
    adjusted = max(check_time, departure, first_open)
    extra = max(0.0, (adjusted - departure).total_seconds() / 3600)
    reason = f"{port}: {note} — ожидание до {iso(first_open)}"
    if extra > 0:
        reason += f" (≈ {extra:g} ч)"
    return StageImpact(
        port=port,
        extra_hours=extra,
        reason=reason,
        adjusted_departure=adjusted if adjusted > departure else None,
    )


def apply_stage_restrictions(route: dict, feed: dict | None, port_name: str, moment: datetime) -> bool:
    changed = False
    for stage in route.get("stages") or []:
        if stage.get("transportType") != "sea" or stage.get("status") != "pending" or stage["location"] != port_name:
            continue
        impact = stage_departure_impact(stage, route, feed, moment)
        stage["portRestriction"] = impact.as_dict()
        if impact.adjusted_departure:
            stage["shipDeparture"] = iso(impact.adjusted_departure)
            sync_stage_chain(route, route["stages"].index(stage) + 1)
            changed = True
        elif impact.blocked or impact.extra_hours:
            changed = True
        elif stage.get("portRestriction"):
            changed = True
    return changed


def route_restriction_summary(route: dict, port_feeds: dict, moment: datetime) -> dict:
    blocked = False
    eta_unknown = False
    delayed = False
    reasons: list[str] = []
    extra = 0.0
    for stage in route.get("stages") or []:
        feed = port_feeds.get(stage.get("location"))
        impact = stage_departure_impact(stage, route, feed, moment)
        if not impact.reason and not impact.blocked:
            continue
        if impact.blocked:
            blocked = True
        if impact.eta_unknown:
            eta_unknown = True
        if impact.extra_hours > 0:
            delayed = True
            extra += impact.extra_hours
        if impact.reason and impact.reason not in reasons:
            reasons.append(impact.reason)
    return {
        "blocked": blocked,
        "etaUnknown": eta_unknown,
        "delayed": delayed or extra > 0,
        "extraHours": round(extra, 1),
        "reasons": reasons,
        "reason": "; ".join(reasons),
    }


def enrich_assessment_with_ports(result: dict, route: dict, port_feeds: dict, moment: datetime) -> dict:
    summary = route_restriction_summary(route, port_feeds, moment)
    if not summary["reasons"]:
        return result
    if summary["etaUnknown"]:
        result["etaUnknown"] = True
        result["predictedArrival"] = None
    if summary["blocked"] and not summary["etaUnknown"]:
        result["etaUnknown"] = True
        result["predictedArrival"] = None
    extra = float(summary["extraHours"])
    if extra > 0:
        result["estimatedDelay"] = int(round(float(result.get("estimatedDelay") or 0) + extra))
        result["rawScore"] = float(result.get("rawScore") or 0) + min(24, extra)
        result["probability"] = min(100, int(result.get("probability") or 0) + 12)
    for reason in summary["reasons"]:
        if reason not in result.get("reasons", []):
            result.setdefault("reasons", []).append(reason)
    result["portRestrictions"] = summary
    return result


def block_apply_reason(route: dict, port_feeds: dict, moment: datetime) -> str | None:
    summary = route_restriction_summary(route, port_feeds, moment)
    if summary["blocked"] and summary["etaUnknown"]:
        return summary["reason"] or "Маршрут затронут ограничением порта без срока открытия"
    return None
