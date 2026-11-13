"""Закрытие выхода из порта: прогноз, маршруты, устаревание."""

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from app.services import telemetry
from app.services.engine import recalculate
from app.services.routing import StaleRouteState, apply_route_alternative, options_for_shipment, state_version
from app.services.stage_schedule import rail_expected_arrival
from app.services.risk import iso, parse_dt

from helpers import ANCHOR, demo_state, prediction, route, shipment

NOW = ANCHOR + timedelta(minutes=20)
SEA_DEPARTURE = "2026-11-12T20:00:00"
CLOSE_END = "2026-11-13T08:00:00"


def port_event(event_id: str, *, status: str, observed=NOW, ends: str | None = None, note: str = "Порт закрыт для выхода судов"):
    payload = {
        "eventId": event_id,
        "eventType": "port.restriction",
        "sourceName": "Порт (тест)",
        "sourceKind": "simulation",
        "observedAt": iso(observed),
        "portName": "Астрахань",
        "departureStatus": status,
        "restrictionNote": note,
        "restrictionStartsAt": iso(NOW - timedelta(hours=2)),
    }
    if ends:
        payload["restrictionEndsAt"] = ends
    return payload


class PortRestrictionBase(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.data = demo_state(Path(self.tmp.name))
        patcher = mock.patch.object(telemetry, "_now", return_value=NOW)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def sea_stage(self):
        return route(self.data, "SCT-1001")["stages"][1]


class PortRestrictionTests(PortRestrictionBase):
    def test_close_with_end_delays_eta(self):
        telemetry.ingest_event(self.data, port_event("port-close-1", status="departure_closed", ends=CLOSE_END))
        recalculate(self.data, NOW)
        after = shipment(self.data, "SCT-1001")
        sea = self.sea_stage()
        self.assertEqual(sea.get("shipDeparture"), CLOSE_END)
        self.assertIsNotNone(after["predictedArrival"])
        reasons = prediction(self.data, "SCT-1001")["reasons"]
        self.assertTrue(any("Астрахань" in item for item in reasons))

    def test_close_without_end_blocks_eta(self):
        telemetry.ingest_event(
            self.data,
            port_event("port-close-open-ended", status="departure_closed", note="Порт закрыт для выхода судов"),
        )
        recalculate(self.data, NOW)
        pred = prediction(self.data, "SCT-1001")
        self.assertTrue(pred.get("etaUnknown"))
        self.assertIsNone(shipment(self.data, "SCT-1001")["predictedArrival"])

    def test_open_after_close(self):
        telemetry.ingest_event(self.data, port_event("c1", status="departure_closed", ends=CLOSE_END))
        telemetry.ingest_event(self.data, port_event("o1", status="open", observed=NOW + timedelta(minutes=3)))
        recalculate(self.data, NOW)
        feed = self.data["telemetry"]["portFeed"]["Астрахань"]
        self.assertEqual(feed["departureStatus"], "open")
        self.assertIsNotNone(shipment(self.data, "SCT-1001")["predictedArrival"])

    def test_stale_close_after_open(self):
        telemetry.ingest_event(self.data, port_event("o2", status="open", observed=NOW + timedelta(minutes=5)))
        result = telemetry.ingest_event(
            self.data,
            port_event("old-close", status="departure_closed", observed=NOW - timedelta(hours=1), ends=CLOSE_END),
        )
        self.assertEqual(result["status"], "stale")
        self.assertEqual(self.data["telemetry"]["portFeed"]["Астрахань"]["departureStatus"], "open")

    def test_workload_does_not_clear_closure(self):
        telemetry.ingest_event(self.data, port_event("c2", status="departure_closed", ends=CLOSE_END))
        telemetry.ingest_event(
            self.data,
            {
                "eventId": "wl-1",
                "eventType": "port.status",
                "sourceName": "Порт",
                "sourceKind": "simulation",
                "observedAt": iso(NOW + timedelta(minutes=1)),
                "portName": "Астрахань",
                "workload": 88,
            },
        )
        self.assertEqual(self.data["telemetry"]["portFeed"]["Астрахань"]["departureStatus"], "departure_closed")
        self.assertEqual(self.data["telemetry"]["portFeed"]["Астрахань"]["workload"], 88)

    def test_makhachkala_detour_stays_available_when_astrakhan_closed(self):
        telemetry.ingest_event(
            self.data,
            port_event("c3", status="departure_closed", note="Порт закрыт для выхода судов"),
        )
        recalculate(self.data, NOW)
        options = options_for_shipment(self.data, "SCT-1001", NOW)
        current = next(item for item in options if item["current"])
        makh = next(item for item in options if item["templateId"] == "ast-anz-road-makh")
        self.assertTrue(current.get("portRestriction", {}).get("blocked"))
        self.assertTrue(makh["selectable"])

    def test_stale_route_after_port_close(self):
        version = state_version(self.data, shipment(self.data, "SCT-1001"))
        telemetry.ingest_event(self.data, port_event("c4", status="departure_closed", ends=CLOSE_END))
        options = options_for_shipment(self.data, "SCT-1001", NOW)
        chosen = next(item for item in options if item["templateId"] == "ast-anz-road-makh")
        with self.assertRaises(StaleRouteState):
            apply_route_alternative(self.data, "SCT-1001", "ast-anz-road-makh", NOW, version)
