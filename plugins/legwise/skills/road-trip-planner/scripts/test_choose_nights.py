#!/usr/bin/env python3
"""Tests for choose_nights.py on a straight east-west line, offline only.

One degree of longitude at the equator is about 144 km here (111 km x 1.3)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import choose_nights as cn  # noqa: E402


def place(lon, name):
    return {"name": name, "tz": "UTC", "lat": 0.0, "lon": lon}


def plan(max_km=350):
    return {
        "places": {"s": place(0, "Start"), "v1": place(1, "Sight 1"), "t1": place(2, "Town 1"),
                   "v2": place(3, "Sight 2"), "t2": place(4, "Town 2"),
                   "v3": place(5, "Sight 3"), "e": place(6, "End"),
                   "b1": place(2.2, "Brand 1"), "b2": place(4.3, "Brand 2")},
        "preferences": {"hotel_brands": ["IHG"]},
        "hard_constraints": [{"id": "c", "nl": "km", "type": "max_daily_km",
                              "params": {"km": max_km}}],
        "overnight_candidates": [{"place": "b1", "after": "t1", "brand": "IHG", "refuel": True},
                                 {"place": "b2", "after": "t2", "brand": "IHG"}],
        "days": [
            {"date": "2026-11-10", "depart": "08:00",
             "stops": [{"place": "s", "kind": "start"},
                       {"place": "v1", "kind": "visit", "dwell_min": 30, "leg": {"km": 1}},
                       {"place": "t1", "kind": "overnight", "leg": {"km": 2}}],
             "stay": {"name": "Motel 1", "place": "t1", "status": "unbooked"}},
            {"date": "2026-11-11", "depart": "08:00",
             "stops": [{"place": "t1", "kind": "start"},
                       {"place": "v2", "kind": "visit", "dwell_min": 30, "leg": {"km": 3}},
                       {"place": "t2", "kind": "overnight", "leg": {"km": 4}}],
             "stay": {"name": "Motel 2", "place": "t2", "status": "unbooked"}},
            {"date": "2026-11-12", "depart": "08:00",
             "stops": [{"place": "t2", "kind": "start"},
                       {"place": "v3", "kind": "visit", "dwell_min": 30, "leg": {"km": 5}},
                       {"place": "e", "kind": "airport", "be_by": "16:00", "leg": {"km": 6}}]},
        ],
    }


def solve(p, **kw):
    line = cn.build_line(p)
    km, mins = cn.straight_matrices([p["places"][i["place"]] for i in line])
    max_km = kw.get("max_km", p["hard_constraints"][0]["params"]["km"])
    return cn.solve(p, line, km, mins, max_km, None)[:2]


class Nights(unittest.TestCase):
    def test_most_brand_nights_within_limit(self):
        options, _ = solve(plan())
        self.assertEqual(options[0]["towns"], ["b1", "b2"])
        self.assertEqual(options[0]["brand_nights"], 2)

    def test_limit_rules_out_brand(self):
        options, _ = solve(plan(max_km=300))
        self.assertEqual(options[0]["towns"], ["t1", "t2"])
        self.assertEqual(options[0]["brand_nights"], 0)

    def test_booked_night_is_kept(self):
        p = plan()
        p["days"][0]["stay"]["status"] = "booked"
        options, _ = solve(p)
        self.assertTrue(all(o["towns"][0] == "t1" for o in options))
        self.assertEqual(options[0]["towns"], ["t1", "b2"])

    def test_booked_sight_stays_on_its_day(self):
        p = plan(max_km=1000)
        p["bookings"] = [{"id": "k", "what": "v2 tour", "place": "v2", "date": "2026-11-10",
                          "status": "booked"}]
        options, _ = solve(p)
        self.assertTrue(options)
        for o in options:
            self.assertGreater(o["ends"][1], 3)  # night 1 is beyond v2 (line index 3)

    def test_quiet_day_has_no_sights(self):
        p = plan(max_km=1000)
        p["hard_constraints"].append({"id": "q", "nl": "no sights last day",
                                      "type": "no_visits_on", "params": {"date": "2026-11-12"}})
        options, _ = solve(p)
        for o in options:
            self.assertGreater(o["ends"][2], 6)  # night 2 is beyond v3

    def test_near_miss_reported_not_chosen(self):
        p = plan(max_km=300)   # b1 night needs 317 km on day 1: about 6% over
        line = cn.build_line(p)
        km, mins = cn.straight_matrices([p["places"][i["place"]] for i in line])
        options, _, near = cn.solve(p, line, km, mins, 300, None)
        self.assertEqual(options[0]["brand_nights"], 0)
        self.assertTrue(near)
        self.assertGreater(near[0]["brand_nights"], 0)
        self.assertLessEqual(near[0]["over"], 0.10)

    def test_written_plan_is_consistent(self):
        p = plan()
        options, _ = solve(p)
        line = cn.build_line(p)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "new.json")
            cn.write_plan(p, line, options[0], out)
            with open(out, encoding="utf-8") as handle:
                new = json.load(handle)
        days = new["days"]
        self.assertEqual([d["stops"][-1]["place"] for d in days], ["b1", "b2", "e"])
        self.assertEqual(days[0]["stay"]["place"], "b1")
        self.assertEqual(days[0]["stay"]["brand"], "IHG")
        self.assertTrue(days[0]["stops"][-1].get("refuel"))
        self.assertEqual(days[1]["stops"][0], {"place": "b1", "kind": "start"})
        self.assertEqual(days[2]["stops"][-1]["kind"], "airport")
        self.assertEqual(days[2]["stops"][-1]["be_by"], "16:00")
        self.assertIn("leg", days[0]["stops"][1])      # s -> v1 unchanged
        self.assertNotIn("leg", days[0]["stops"][2])   # v1 -> b1 is new
        self.assertNotIn("leg", days[2]["stops"][1])   # b2 -> v3 is new
        for d in days:
            for st in d["stops"]:
                self.assertIn(st["place"], p["places"])

    def test_less_flight_day_driving_ranks_first(self):
        p = plan(max_km=1000)
        del p["preferences"]
        p["rules"] = {"departure_day_max_drive_min": 60}
        options, _ = solve(p)
        self.assertEqual(options[0]["towns"][-1], "b2")  # closest to the airport
        self.assertGreater(options[0]["depart_over"], 0)

    def test_towns_without_brand_candidate_listed(self):
        p = plan()
        self.assertEqual(cn.towns_without_brand(p, cn.build_line(p)), ["Town 1", "Town 2"])
        del p["preferences"]
        self.assertEqual(cn.towns_without_brand(p, cn.build_line(p)), [])


if __name__ == "__main__":
    unittest.main()
