"""Регрессия главного сценария: опоздание поезда, пересчёт, объезд, история, CO₂."""

import copy
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from app.services import telemetry
from app.services.carbon import calculate
from app.services.engine import recalculate
from app.services.historical_forecast import backtest_report, current_features, find_similar
from app.services.risk import iso, parse_dt
from app.services.routing import StaleRouteState, apply_route_alternative, options_for_shipment, state_version
from app.services.stage_schedule import rail_expected_arrival, schedule_baseline_arrival

from helpers import ANCHOR, demo_state, prediction, route, shipment

NOW = ANCHOR + timedelta(minutes=20)


def rail_event(event_id: str, delay: float, observed=NOW) -> dict:
    return {
        "eventId": event_id,
        "eventType": "rail.eta",
        "sourceName": "РЖД (тест)",
        "sourceKind": "simulation",
        "observedAt": iso(observed),
        "shipmentId": "SCT-1001",
        "stageId": "rt-SCT-1001-1",
        "delayHours": delay,
    }


class ScenarioBase(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.data = demo_state(Path(self.tmp.name))
        patcher = mock.patch.object(telemetry, "_now", return_value=NOW)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)


class RailEventTests(ScenarioBase):
    def test_rail_event_changes_risk_and_eta_once(self):
        before_eta = shipment(self.data, "SCT-1001")["predictedArrival"]
        before_delay = prediction(self.data, "SCT-1001")["estimatedDelay"]

        first = telemetry.ingest_event(self.data, rail_event("rzd-1", 52))
        self.assertEqual(first["status"], "applied")
        after_eta = shipment(self.data, "SCT-1001")["predictedArrival"]
        self.assertGreater(after_eta, before_eta)
        self.assertGreater(prediction(self.data, "SCT-1001")["estimatedDelay"], before_delay)
        events_after_first = len(shipment(self.data, "SCT-1001")["extraEvents"])
        notes = [item for item in self.data["notifications"] if item["id"] == "SCT-1001:train_delay"]
        self.assertEqual(len(notes), 1)
        eta = datetime.fromisoformat(after_eta).strftime("%d.%m.%Y, %H:%M")
        self.assertIn(eta, notes[0]["description"])
        self.assertFalse(notes[0]["read"])

        second = telemetry.ingest_event(self.data, rail_event("rzd-1", 52))
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(len(shipment(self.data, "SCT-1001")["extraEvents"]), events_after_first)
        self.assertEqual(shipment(self.data, "SCT-1001")["predictedArrival"], after_eta)

    def test_late_old_observation_does_not_overwrite(self):
        telemetry.ingest_event(self.data, rail_event("rzd-new", 40))
        result = telemetry.ingest_event(self.data, rail_event("rzd-old", 2, observed=NOW - timedelta(hours=6)))
        self.assertEqual(result["status"], "stale")
        self.assertEqual(route(self.data, "SCT-1001")["stages"][0]["delayHours"], 40)

    def test_invalid_events_rejected(self):
        bad = [
            {**rail_event("e1", 5), "shipmentId": "SCT-0000"},
            {**rail_event("e2", 5), "stageId": "rt-SCT-1001-2"},
            {**rail_event("e3", 5), "delayHours": "много"},
            {**rail_event("e4", 5), "delayHours": -3},
            {**rail_event("e5", 5), "observedAt": iso(NOW + timedelta(days=2))},
        ]
        for payload in bad:
            with self.subTest(payload=payload["eventId"]), self.assertRaises(ValueError):
                telemetry.ingest_event(self.data, payload)
        self.assertEqual(telemetry.ensure_telemetry(self.data)["events"], {})


class RailDetourScheduleRegression(ScenarioBase):
    def test_absolute_rail_delay_after_detour(self):
        telemetry.ingest_event(self.data, rail_event("rzd-a", 52))
        options = options_for_shipment(self.data, "SCT-1001", NOW)
        chosen = next(item for item in options if item["templateId"] == "ast-anz-road-makh")
        apply_route_alternative(self.data, "SCT-1001", "ast-anz-road-makh", NOW, chosen["stateVersion"])
        recalculate(self.data, NOW)

        rail = route(self.data, "SCT-1001")["stages"][0]
        schedule_rail = rail["schedulePlannedArrival"]
        expected_52 = rail_expected_arrival(rail)
        self.assertEqual(rail["delayHours"], 52)
        self.assertEqual(schedule_baseline_arrival(rail), parse_dt(schedule_rail))

        telemetry.ingest_event(self.data, rail_event("rzd-b", 52, observed=NOW + timedelta(minutes=5)))
        recalculate(self.data, NOW)
        rail_repeat = route(self.data, "SCT-1001")["stages"][0]
        self.assertEqual(rail_expected_arrival(rail_repeat), expected_52)
        self.assertEqual(rail_repeat["schedulePlannedArrival"], schedule_rail)

        telemetry.ingest_event(self.data, rail_event("rzd-c", 60, observed=NOW + timedelta(minutes=10)))
        recalculate(self.data, NOW)
        rail_60 = route(self.data, "SCT-1001")["stages"][0]
        expected_60 = parse_dt(schedule_rail) + timedelta(hours=60)
        self.assertEqual(rail_expected_arrival(rail_60), expected_60)
        road = route(self.data, "SCT-1001")["stages"][1]
        self.assertGreaterEqual(parse_dt(road["plannedStart"]), expected_60 + timedelta(hours=2))

        arrival_fact = expected_60 + timedelta(hours=1)
        with mock.patch.object(telemetry, "_now", return_value=arrival_fact):
            telemetry.ingest_event(
                self.data,
                {
                    "eventId": "carrier-done",
                    "eventType": "carrier.stage_completed",
                    "observedAt": iso(arrival_fact),
                    "shipmentId": "SCT-1001",
                    "stageId": rail["id"],
                    "sourceName": "Перевозчик (тест)",
                    "sourceKind": "simulation",
                },
            )
        recalculate(self.data, NOW)
        stages = route(self.data, "SCT-1001")["stages"]
        self.assertEqual(stages[0]["actualArrival"], iso(arrival_fact))
        self.assertEqual(stages[0]["schedulePlannedArrival"], schedule_rail)
        self.assertGreaterEqual(parse_dt(stages[1]["plannedStart"]), arrival_fact + timedelta(hours=2))


class DetourTests(ScenarioBase):
    def test_detour_keeps_active_leg_and_matches_preview(self):
        telemetry.ingest_event(self.data, rail_event("rzd-1", 52))
        options = options_for_shipment(self.data, "SCT-1001", NOW)
        chosen = next(item for item in options if item["templateId"] == "ast-anz-road-makh")
        self.assertTrue(chosen["selectable"])
        rail_before = copy.deepcopy(route(self.data, "SCT-1001")["stages"][0])

        apply_route_alternative(self.data, "SCT-1001", "ast-anz-road-makh", NOW, chosen["stateVersion"])
        recalculate(self.data, NOW)

        stages = route(self.data, "SCT-1001")["stages"]
        self.assertEqual(stages[0]["id"], rail_before["id"])
        self.assertEqual((stages[0]["location"], stages[0]["nextLocation"]), ("Саратов", "Астрахань"))
        self.assertEqual(stages[0]["status"], rail_before["status"])
        self.assertEqual(stages[0]["plannedStart"], rail_before["plannedStart"])
        self.assertEqual(stages[0]["schedulePlannedArrival"], rail_before["schedulePlannedArrival"])
        self.assertEqual(stages[0]["delayHours"], 52)
        self.assertEqual(stages[1]["location"], "Астрахань")
        self.assertEqual(stages[-1]["nextLocation"], "Энзели")
        self.assertEqual(shipment(self.data, "SCT-1001")["currentLocation"], "перегон Саратов — Астрахань")
        self.assertEqual(shipment(self.data, "SCT-1001")["predictedArrival"], chosen["predictedArrival"])
        applied = next(item for item in options_for_shipment(self.data, "SCT-1001", NOW) if item["current"])
        for key in ("predictedArrival", "estimatedDelay", "probability", "cost", "carbonFootprint", "distance"):
            self.assertEqual(applied[key], chosen[key], key)

    def test_stale_comparison_is_rejected(self):
        version = state_version(self.data, shipment(self.data, "SCT-1001"))
        telemetry.ingest_event(self.data, rail_event("rzd-1", 52))
        with self.assertRaises(StaleRouteState):
            apply_route_alternative(self.data, "SCT-1001", "ast-anz-road-makh", NOW, version)

    def test_awaiting_and_no_alternative_cases(self):
        selectable = options_for_shipment(self.data, "SCT-1001", NOW)
        self.assertTrue(any(item["selectable"] for item in selectable))
        unavailable = next(item for item in options_for_shipment(self.data, "SCT-1001", NOW) if item["templateId"] == "makh-anz-road-sea")
        self.assertFalse(unavailable["selectable"])
        self.assertIn("не стыкуется", unavailable["unavailableReason"])


class HistoryForecastTests(ScenarioBase):
    def test_history_used_when_enough_similar_trips(self):
        pred = prediction(self.data, "SCT-1001")
        self.assertEqual(pred["historyMode"], "history_blend")
        self.assertGreaterEqual(pred["historyMatchCount"], 3)

    def test_changing_matching_history_changes_forecast(self):
        before = prediction(self.data, "SCT-1001")
        matched = set(before["historyMatchIds"])
        for obs in self.data["corridorHistory"]:
            if obs["id"] in matched:
                obs["actualDelayHours"] += 30
        recalculate(self.data, NOW)
        self.assertGreater(prediction(self.data, "SCT-1001")["estimatedDelay"], before["estimatedDelay"])

        self.data["corridorHistory"] = [obs for obs in self.data["corridorHistory"] if obs["id"] not in matched]
        recalculate(self.data, NOW)
        fallback = prediction(self.data, "SCT-1001")
        self.assertEqual(fallback["historyMode"], "heuristic_fallback")
        self.assertTrue(any("эвристик" in reason for reason in fallback["reasons"]))

    def test_conditions_change_similar_set(self):
        sct = shipment(self.data, "SCT-1001")
        rt = route(self.data, "SCT-1001")
        base = current_features(sct, rt, self.data["ports"], NOW)
        history = self.data["corridorHistory"]
        baseline = {obs["id"] for obs in find_similar(history, base)}
        for change in ({"windSpeedMs": 6.0}, {"portWorkload": 50.0}, {"bufferHoursAtForecast": 12.0}):
            with self.subTest(change=change):
                changed = {obs["id"] for obs in find_similar(history, {**base, **change})}
                self.assertNotEqual(changed, baseline)

    def test_backtest_uses_later_trips(self):
        report = backtest_report(self.data["corridorHistory"])
        self.assertEqual(report["dataSource"], "synthetic")
        self.assertEqual(report["trainTrips"] + report["evaluatedTrips"], len(self.data["corridorHistory"]))
        self.assertIsNotNone(report["modelMaeHours"])
        self.assertIsNotNone(report["heuristicMaeHours"])


class CarbonTests(TestCase):
    def test_sum_by_stage_in_kg(self):
        stages = [
            {"id": "a", "location": "Саратов", "nextLocation": "Астрахань", "transportType": "rail", "distanceKm": 520},
            {"id": "b", "location": "Астрахань", "nextLocation": "Энзели", "transportType": "sea", "distanceKm": 760},
        ]
        factors = {"rail": 0.028, "sea": 0.015, "road": 0.095}
        result = calculate(420, stages, factors)
        self.assertEqual([row["co2Emission"] for row in result["stages"]], [6115.2, 4788.0])
        self.assertEqual(result["total"], 10903.2)
        self.assertEqual(result["byTransport"], {"rail": 6115.2, "sea": 4788.0})
