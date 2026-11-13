"""Согласованность шести демо-маршрутов хакатона."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from helpers import ANCHOR, demo_state, route, shipment


class DemoRouteDiversityTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.data = demo_state(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_six_distinct_corridor_labels(self):
        labels = {f"{item['origin']} → {item['destination']}" for item in self.data["shipments"]}
        self.assertEqual(len(labels), 6)

    def test_moscow_mumbai_chain(self):
        row = shipment(self.data, "SCT-1006")
        rt = route(self.data, "SCT-1006")
        self.assertEqual(row["origin"], "Москва")
        self.assertEqual(row["destination"], "Мумбаи")
        stages = rt["stages"]
        self.assertEqual(len(stages), 4)
        for left, right in zip(stages, stages[1:]):
            self.assertEqual(left["nextLocation"], right["location"])
        self.assertEqual(stages[0]["location"], "Москва")
        self.assertEqual(stages[-1]["nextLocation"], "Мумбаи")
