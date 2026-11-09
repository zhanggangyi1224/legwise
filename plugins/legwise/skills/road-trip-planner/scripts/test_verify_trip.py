#!/usr/bin/env python3
"""Defect-injection tests: each mutation of a clean plan must produce its finding."""
import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_trip as vt  # noqa: E402

TODAY = date(2026, 11, 4)


def clean_plan():
    source = "test fixture"
    return {
        "vehicle": {"range_km": 800},
        "places": {
            "a": {"name": "A", "tz": "Australia/Adelaide", "lat": -34.93, "lon": 138.60},
            "b": {"name": "B", "tz": "Australia/Adelaide", "lat": -32.49, "lon": 137.77},
            "c": {"name": "C", "tz": "Australia/Perth", "lat": -33.86, "lon": 121.89},
        },
        "hard_constraints": [
            {"id": "c1", "nl": "max 500 km", "type": "max_daily_km", "params": {"km": 500}},
            {"id": "c2", "nl": "visit B", "type": "must_visit", "params": {"place": "b"}},
        ],
        "facts": [{"id": "f1", "claim": "x", "status": "verified", "source": source,
                   "checked": "2026-11-01"}],
        "days": [
            {"date": "2026-11-10", "depart": "08:00",
             "stops": [
                 {"place": "a", "kind": "start"},
                 {"place": "b", "kind": "overnight", "refuel": True,
                  "leg": {"km": 300, "drive_min": 110, "source": source}}],
             "stay": {"name": "Motel", "place": "b", "status": "booked",
                      "check_in_until": "21:00", "cost": 100}},
            {"date": "2026-11-11", "depart": "08:00",
             "stops": [
                 {"place": "b", "kind": "start"},
                 {"place": "c", "kind": "airport",
                  "leg": {"km": 400, "drive_min": 115, "source": source}}]},
        ],
    }


def run(plan):
    return vt.Checker(plan, TODAY).run()


def has(result, level, check):
    return any(f["level"] == level and f["check"] == check for f in result["findings"])


class CleanPlan(unittest.TestCase):
    def test_clean_plan_passes(self):
        result = run(clean_plan())
        self.assertEqual(result["verdict"], "PASS", result["findings"])


class Injected(unittest.TestCase):
    def test_after_sunset(self):
        plan = clean_plan()
        plan["days"][0]["depart"] = "19:00"
        self.assertTrue(has(run(plan), vt.FAIL, "daylight"))

    def test_before_sunrise(self):
        plan = clean_plan()
        plan["days"][0]["depart"] = "04:00"
        self.assertTrue(has(run(plan), vt.FAIL, "daylight"))

    def test_night_ok_is_visible_not_silent(self):
        plan = clean_plan()
        plan["days"][0]["depart"] = "19:00"
        plan["days"][0]["stops"][1]["leg"]["night_ok"] = True
        result = run(plan)
        self.assertFalse(has(result, vt.FAIL, "daylight"))
        self.assertTrue(has(result, vt.WARN, "daylight"))

    def test_fuel_gap(self):
        plan = clean_plan()
        plan["days"][0]["stops"][1]["refuel"] = False
        self.assertTrue(has(run(plan), vt.FAIL, "fuel"))

    def test_broken_continuity(self):
        plan = clean_plan()
        plan["days"][1]["stops"][0]["place"] = "a"
        self.assertTrue(has(run(plan), vt.FAIL, "continuity"))

    def test_date_gap(self):
        plan = clean_plan()
        plan["days"][1]["date"] = "2026-11-13"
        self.assertTrue(has(run(plan), vt.FAIL, "dates"))

    def test_missing_lodging(self):
        plan = clean_plan()
        del plan["days"][0]["stay"]
        self.assertTrue(has(run(plan), vt.FAIL, "lodging"))

    def test_late_check_in(self):
        plan = clean_plan()
        plan["days"][0]["stay"]["check_in_until"] = "09:00"
        self.assertTrue(has(run(plan), vt.FAIL, "check_in"))

    def test_closed_on_arrival(self):
        plan = clean_plan()
        stop = plan["days"][0]["stops"][1]
        stop.update(kind="visit", dwell_min=60, hours=["08:00", "10:00"])
        self.assertTrue(has(run(plan), vt.FAIL, "hours"))

    def test_time_zone_is_applied(self):
        # 400 km west across zones: 2.5 h of clock time comes back in November.
        result = run(clean_plan())
        self.assertEqual(result["days"][1]["stops"][1]["arrive"], "07:36")

    def test_constraint_violated(self):
        plan = clean_plan()
        plan["hard_constraints"][0]["params"]["km"] = 350
        self.assertTrue(has(run(plan), vt.FAIL, "constraint"))

    def test_claimed_km_disagreement(self):
        plan = clean_plan()
        plan["days"][0]["claimed_km"] = 500
        self.assertTrue(has(run(plan), vt.WARN, "claimed_km"))


class LegSpeed(unittest.TestCase):
    def test_implausibly_slow_long_leg(self):
        plan = clean_plan()
        plan["days"][0]["stops"][1]["leg"]["drive_min"] = 330
        self.assertTrue(has(run(plan), vt.WARN, "leg_speed"))


class NoVacuousPass(unittest.TestCase):
    """Missing data must never read as PASS."""

    def assert_unknown(self, plan, check):
        result = run(plan)
        self.assertNotEqual(result["verdict"], "PASS")
        self.assertTrue(has(result, vt.UNKNOWN, check), result["findings"])

    def test_no_constraints(self):
        plan = clean_plan()
        plan["hard_constraints"] = []
        self.assert_unknown(plan, "constraints")

    def test_leg_without_numbers(self):
        plan = clean_plan()
        plan["days"][0]["stops"][1]["leg"] = {}
        self.assert_unknown(plan, "leg")

    def test_leg_without_source(self):
        plan = clean_plan()
        del plan["days"][0]["stops"][1]["leg"]["source"]
        self.assert_unknown(plan, "grounding")

    def test_no_vehicle_range(self):
        plan = clean_plan()
        plan["vehicle"] = {}
        self.assert_unknown(plan, "fuel")

    def test_unverified_fact(self):
        plan = clean_plan()
        plan["facts"][0]["status"] = "unverified"
        self.assert_unknown(plan, "fact")

    def test_visit_without_hours(self):
        plan = clean_plan()
        plan["days"][0]["stops"][1]["kind"] = "visit"
        self.assert_unknown(plan, "hours")

    def test_check_in_unknown(self):
        plan = clean_plan()
        del plan["days"][0]["stay"]["check_in_until"]
        self.assert_unknown(plan, "check_in")

    def test_manual_constraint_needs_confirmation(self):
        plan = clean_plan()
        plan["hard_constraints"].append({"id": "m", "nl": "y", "type": "manual"})
        self.assert_unknown(plan, "constraint")

    def test_unsupported_type_fails(self):
        plan = clean_plan()
        plan["hard_constraints"].append({"id": "t", "nl": "y", "type": "max_dialy_km"})
        self.assertTrue(has(run(plan), vt.FAIL, "constraint"))

    def test_budget_with_missing_cost(self):
        plan = clean_plan()
        del plan["days"][0]["stay"]["cost"]
        plan["hard_constraints"].append(
            {"id": "b", "nl": "y", "type": "max_budget", "params": {"amount": 500}})
        self.assert_unknown(plan, "constraint")


class Preferences(unittest.TestCase):
    def constraint(self, plan, ctype, params):
        plan["hard_constraints"].append({"id": "p1", "nl": ctype, "type": ctype,
                                         "params": params})
        return next(c for c in run(plan)["constraints"] if c["id"] == "p1")

    def with_visit(self, tags):
        plan = clean_plan()
        if tags is not None:
            plan["places"]["b"]["tags"] = tags
        plan["days"][1]["stops"].insert(1, {"place": "b", "kind": "visit",
                                            "dwell_min": 30, "hours": "always"})
        return plan

    def test_avoid_tag_hit(self):
        c = self.constraint(self.with_visit(["boat"]), "avoid_tag", {"tag": "boat"})
        self.assertEqual(c["status"], vt.FAIL)

    def test_avoid_tag_clear(self):
        c = self.constraint(self.with_visit(["cave"]), "avoid_tag", {"tag": "boat"})
        self.assertEqual(c["status"], "PASS")

    def test_avoid_tag_untagged_is_unknown(self):
        c = self.constraint(self.with_visit(None), "avoid_tag", {"tag": "boat"})
        self.assertEqual(c["status"], vt.UNKNOWN)

    def test_nightly_cost_over(self):
        c = self.constraint(clean_plan(), "max_nightly_cost", {"amount": 90})
        self.assertEqual(c["status"], vt.FAIL)

    def test_nightly_cost_missing(self):
        plan = clean_plan()
        del plan["days"][0]["stay"]["cost"]
        c = self.constraint(plan, "max_nightly_cost", {"amount": 200})
        self.assertEqual(c["status"], vt.UNKNOWN)

    def test_no_visits_on(self):
        c = self.constraint(self.with_visit(["cave"]), "no_visits_on",
                            {"date": "2026-11-11"})
        self.assertEqual(c["status"], vt.FAIL)
        c = self.constraint(clean_plan(), "no_visits_on", {"date": "2026-11-11"})
        self.assertEqual(c["status"], "PASS")

    def test_brand_list(self):
        plan = clean_plan()
        plan["days"][0]["stay"]["brand"] = "Novotel"
        c = self.constraint(plan, "min_nights_brand",
                            {"brand": ["Novotel", "Mercure"], "nights": 1})
        self.assertEqual(c["status"], "PASS")


class Bookings(unittest.TestCase):
    def finding(self, item):
        plan = clean_plan()
        plan["bookings"] = [dict(id="k1", what="tour", **item)]
        return [f for f in run(plan)["findings"] if f["where"] == "k1"]

    def test_overdue_fails(self):
        self.assertEqual(self.finding({"book_by": "2026-11-01"})[0]["level"], vt.FAIL)

    def test_close_warns(self):
        self.assertEqual(self.finding({"book_by": "2026-11-08"})[0]["level"], vt.WARN)

    def test_far_is_quiet(self):
        self.assertEqual(self.finding({"book_by": "2026-12-30"}), [])

    def test_no_date_is_unknown(self):
        self.assertEqual(self.finding({})[0]["level"], vt.UNKNOWN)

    def test_booked_and_walk_up_are_quiet(self):
        self.assertEqual(self.finding({"status": "booked", "book_by": "2026-11-01"}), [])
        self.assertEqual(self.finding({"status": "walk_up"}), [])

    def test_pending_payment_warns(self):
        self.assertEqual(self.finding({"status": "pending"})[0]["level"], vt.WARN)


class EntryRulesAndBrand(unittest.TestCase):
    def with_visit(self, **stop):
        plan = clean_plan()
        plan["days"][1]["stops"].insert(1, {"place": "b", "kind": "visit", "dwell_min": 30,
                                            "hours": "always", **stop})
        return plan

    def levels(self, plan, check):
        return [f["level"] for f in run(plan)["findings"] if f["check"] == check]

    def test_unchecked_rule_is_unknown(self):
        self.assertEqual(self.levels(self.with_visit(), "booking_rule"), [vt.UNKNOWN])

    def test_required_but_not_listed_fails(self):
        self.assertEqual(self.levels(self.with_visit(booking="required"), "booking_rule"),
                         [vt.FAIL])

    def test_required_and_listed_passes(self):
        plan = self.with_visit(booking="required")
        plan["bookings"] = [{"id": "k", "what": "B entry", "place": "b", "status": "booked"}]
        self.assertEqual(self.levels(plan, "booking_rule"), [])

    def test_walk_up_is_fine(self):
        self.assertEqual(self.levels(self.with_visit(booking="walk_up"), "booking_rule"), [])

    def test_non_brand_night_needs_reason(self):
        plan = clean_plan()
        plan["preferences"] = {"hotel_brands": ["IHG"]}
        self.assertEqual(self.levels(plan, "brand"), [vt.UNKNOWN])
        plan["days"][0]["stay"]["brand_note"] = "no IHG within 30 km; checked trip_v2_ihg.json"
        self.assertEqual(self.levels(plan, "brand"), [])


class TestFindings(unittest.TestCase):
    """Problems a blind grader found in a test trip."""

    def findings(self, plan, check):
        return [f for f in run(plan)["findings"] if f["check"] == check]

    def test_long_drive_on_flight_day_warns(self):
        plan = clean_plan()  # day 2 drives 115 min to the airport
        self.assertEqual([f["level"] for f in self.findings(plan, "departure_day")], [vt.WARN])
        plan["rules"] = {"departure_day_max_drive_min": 150}
        self.assertEqual(self.findings(plan, "departure_day"), [])

    def test_no_flight_no_departure_check(self):
        plan = clean_plan()
        plan["days"][1]["stops"][1]["kind"] = "overnight"
        self.assertEqual(self.findings(plan, "departure_day"), [])

    def test_unnamed_stay_is_unknown(self):
        plan = clean_plan()
        plan["days"][0]["stay"]["name"] = "Motel or apartment (to choose)"
        self.assertEqual([f["level"] for f in self.findings(plan, "stay_name")], [vt.UNKNOWN])
        plan["days"][0]["stay"]["name"] = "Seaview Motel"
        self.assertEqual(self.findings(plan, "stay_name"), [])

    def test_stays_sharing_a_link_warn(self):
        plan = clean_plan()
        plan["days"].insert(1, json.loads(json.dumps(plan["days"][0])))
        plan["days"][1]["date"] = "2026-11-11"
        plan["days"][1]["stops"] = [{"place": "b", "kind": "start"},
                                    {"place": "b", "kind": "overnight"}]
        plan["days"][2]["date"] = "2026-11-12"
        for n, day in enumerate(plan["days"][:2]):
            day["stay"].update(name=f"Hotel {n}", source="https://example.com/brand-search")
        self.assertIn("share one source link",
                      " ".join(f["message"] for f in self.findings(plan, "grounding")))

    def test_early_visit_with_unknown_hours_is_called_out(self):
        plan = clean_plan()
        plan["days"][1]["stops"].insert(1, {"place": "b", "kind": "visit", "dwell_min": 30,
                                            "leg": {"km": 1, "drive_min": 2, "source": "x"}})
        message = " ".join(f["message"] for f in self.findings(plan, "hours"))
        self.assertIn("outside the usual 09:00–17:00", message)  # visit starts about 08:02


class Gate(unittest.TestCase):
    def test_rejects_new_failure(self):
        old = run(clean_plan())
        plan = clean_plan()
        plan["days"][0]["depart"] = "19:00"
        accepted, reasons = vt.compare(old, run(plan))
        self.assertFalse(accepted)
        self.assertTrue(any("daylight" in r for r in reasons))

    def test_rejects_no_improvement(self):
        accepted, _ = vt.compare(run(clean_plan()), run(clean_plan()))
        self.assertFalse(accepted)

    def test_user_request_skips_improvement_only(self):
        accepted, _ = vt.compare(run(clean_plan()), run(clean_plan()), user_requested=True)
        self.assertTrue(accepted)
        plan = clean_plan()
        plan["days"][0]["depart"] = "19:00"
        accepted, _ = vt.compare(run(clean_plan()), run(plan), user_requested=True)
        self.assertFalse(accepted)

    def test_accepts_real_fix(self):
        bad = clean_plan()
        bad["days"][0]["depart"] = "19:00"
        accepted, _ = vt.compare(run(bad), run(clean_plan()))
        self.assertTrue(accepted)

    def test_rejects_dropped_constraint(self):
        plan = clean_plan()
        plan["hard_constraints"] = plan["hard_constraints"][:1]
        accepted, reasons = vt.compare(run(clean_plan()), run(plan))
        self.assertFalse(accepted)
        self.assertTrue(any("c2" in r for r in reasons))


class GateNewStops(unittest.TestCase):
    def fixed_with_new_unknown(self):
        plan = clean_plan()
        del plan["days"][0]["stay"]["check_in_until"]
        return plan

    def broken(self):
        plan = clean_plan()
        plan["days"][0]["depart"] = "19:00"
        return plan

    def test_new_unknown_rejected_by_default(self):
        accepted, _ = vt.compare(run(self.broken()), run(self.fixed_with_new_unknown()))
        self.assertFalse(accepted)

    def test_new_unknown_allowed_and_listed(self):
        accepted, reasons = vt.compare(run(self.broken()), run(self.fixed_with_new_unknown()),
                                       allow_new_unknowns=True)
        self.assertTrue(accepted)
        self.assertTrue(any("check_in" in r for r in reasons))

    def test_new_failure_still_rejected(self):
        accepted, _ = vt.compare(run(clean_plan()), run(self.broken()),
                                 allow_new_unknowns=True)
        self.assertFalse(accepted)


class InvalidPlans(unittest.TestCase):
    def check_invalid(self, plan):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(plan, handle)
        self.addCleanup(os.unlink, handle.name)
        with self.assertRaises(vt.PlanError):
            vt.evaluate(handle.name, TODAY)

    def test_no_days(self):
        self.check_invalid({"places": {}, "days": []})

    def test_undefined_place(self):
        plan = clean_plan()
        plan["days"][0]["stops"][0]["place"] = "nowhere"
        self.check_invalid(plan)

    def test_bad_time_zone(self):
        plan = clean_plan()
        plan["places"]["a"]["tz"] = "Mars/Olympus"
        self.check_invalid(plan)


class Sun(unittest.TestCase):
    """Expected values from api.sunrise-sunset.org, checked 2026-11-04."""

    def assert_sunset(self, day, lat, lon, tz, expected):
        from zoneinfo import ZoneInfo
        _, sunset = vt.sun_times_utc(day, lat, lon)
        local = sunset.astimezone(ZoneInfo(tz))
        minutes = local.hour * 60 + local.minute
        hour, minute = expected
        self.assertLessEqual(abs(minutes - (hour * 60 + minute)), 2, local)

    def test_adelaide(self):
        self.assert_sunset(date(2026, 11, 27), -34.93, 138.60, "Australia/Adelaide", (20, 10))

    def test_caiguna_on_eucla_time(self):
        self.assert_sunset(date(2026, 11, 29), -32.27, 125.49, "Australia/Eucla", (19, 13))

    def test_perth(self):
        self.assert_sunset(date(2026, 12, 4), -31.95, 115.86, "Australia/Perth", (19, 10))


if __name__ == "__main__":
    unittest.main(verbosity=1)
