#!/usr/bin/env python3
"""Tests for order_stops.py, offline only."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import order_stops as osp  # noqa: E402

PLACES = {
    "s": {"name": "Start", "lat": 0.0, "lon": 0.0},
    "a": {"name": "A", "lat": 0.0, "lon": 1.0},
    "b": {"name": "B", "lat": 0.0, "lon": 2.0},
    "c": {"name": "C", "lat": 0.0, "lon": 3.0},
    "e": {"name": "End", "lat": 0.0, "lon": 4.0},
}


def day(order, fixed=None):
    stops = [{"place": "s", "kind": "start"}]
    for pid in order:
        stop = {"place": pid, "kind": "visit"}
        if pid == fixed:
            stop["be_by"] = "12:00"
        stops.append(stop)
    stops.append({"place": "e", "kind": "overnight"})
    return {"stops": stops}


def places_of(stops):
    return [s["place"] for s in stops]


class Ordering(unittest.TestCase):
    def test_zigzag_is_straightened(self):
        stops, before, after = osp.reorder_day(day(["c", "a", "b"]), PLACES,
                                               osp.straight_matrix)
        self.assertEqual(places_of(stops), ["s", "a", "b", "c", "e"])
        self.assertLess(after, before)

    def test_fixed_stop_stays_put(self):
        stops, _, _ = osp.reorder_day(day(["c", "a", "b"], fixed="a"), PLACES,
                                      osp.straight_matrix)
        self.assertEqual(stops[2]["place"], "a")

    def test_already_best(self):
        stops, before, after = osp.reorder_day(day(["a", "b", "c"]), PLACES,
                                               osp.straight_matrix)
        self.assertEqual(places_of(stops), ["s", "a", "b", "c", "e"])
        self.assertAlmostEqual(before, after)

    def test_heuristic_for_many_stops(self):
        places = {"s": {"lat": 0.0, "lon": 0.0}, "e": {"lat": 0.0, "lon": 11.0}}
        ids = [f"p{i}" for i in range(1, 11)]
        for i, pid in enumerate(ids, 1):
            places[pid] = {"lat": 0.0, "lon": float(i)}
        shuffled = ids[::2] + ids[1::2]
        d = {"stops": [{"place": "s", "kind": "start"}]
             + [{"place": p, "kind": "visit"} for p in shuffled]
             + [{"place": "e", "kind": "overnight"}]}
        stops, _, _ = osp.reorder_day(d, places, osp.straight_matrix)
        self.assertEqual(places_of(stops)[1:-1], ids)


if __name__ == "__main__":
    unittest.main()
