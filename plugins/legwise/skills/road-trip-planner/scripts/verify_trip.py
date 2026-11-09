#!/usr/bin/env python3
"""Deterministic checker for a road trip plan. Standard library only.

    verify_trip.py trip.json                     check one plan
    verify_trip.py trip.json --json              machine-readable result
    verify_trip.py new.json --baseline old.json  accept or reject an edit

Every check has three outcomes, never two: PASS, FAIL or UNKNOWN. Missing data
is UNKNOWN, so a plan cannot pass a check nobody had the facts to run.

Exit codes: 0 PASS, 1 FAIL, 2 UNVERIFIED (no failures, some UNKNOWN),
            3 invalid plan file, 4 edit rejected by --baseline.
See references/plan-format.md for the file format.
"""
import argparse
import json
import math
import re
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FAIL, UNKNOWN, WARN = "FAIL", "UNKNOWN", "WARN"

DEFAULT_RULES = {
    "drive_buffer_pct": 10,
    "no_drive_after_sunset": True,
    "sunset_buffer_min": 30,
    "no_drive_before_sunrise": True,
    "max_continuous_drive_min": 120,
    "break_min_dwell": 15,
    "fuel_reserve_pct": 20,
    "max_fact_age_days": 30,
    "claimed_km_tolerance_pct": 10,
    "min_plausible_kmh": 65,
    "book_by_warn_days": 7,
    "departure_day_max_drive_min": 90,
    "unknown_hours_window": ["09:00", "17:00"],
}
UNNAMED_STAY = re.compile(r"\b(tbd|tba|to choose|to be (chosen|decided|confirmed)|any|anything|"
                          r"options?|or similar)\b|\?", re.I)
SCHEDULED_KINDS = {"visit", "fuel", "meal"}
BOOKING_RULES = {"none", "walk_up", "recommended", "required"}


class PlanError(Exception):
    """The plan file cannot be interpreted at all."""


def sun_times_utc(day, lat, lon):
    """NOAA approximation of (sunrise, sunset) in UTC for a local calendar day."""
    gamma = 2 * math.pi / 365 * (day.timetuple().tm_yday - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma)
                       - 0.032077 * math.sin(gamma)
                       - 0.014615 * math.cos(2 * gamma)
                       - 0.040849 * math.sin(2 * gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    phi = math.radians(lat)
    cos_ha = (math.cos(math.radians(90.833)) / (math.cos(phi) * math.cos(decl))
              - math.tan(phi) * math.tan(decl))
    if abs(cos_ha) > 1:
        return None, None
    ha = math.degrees(math.acos(cos_ha))
    midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    sunrise = midnight + timedelta(minutes=720 - 4 * (lon + ha) - eqtime)
    sunset = midnight + timedelta(minutes=720 - 4 * (lon - ha) - eqtime)
    return sunrise, sunset


def parse_hhmm(text, where):
    try:
        hour, minute = str(text).split(":")
        return int(hour), int(minute)
    except ValueError as exc:
        raise PlanError(f"{where}: expected HH:MM, got {text!r}") from exc


def fmt_min(minutes):
    return f"{int(minutes) // 60}h{int(minutes) % 60:02d}"


class Checker:
    def __init__(self, plan, today):
        self.plan = plan
        self.today = today
        self.rules = {**DEFAULT_RULES, **plan.get("rules", {})}
        self.places = plan.get("places") or {}
        self.findings = []
        self.days = []
        self.constraints = []
        self.tz = {}

    def add(self, level, check, where, message):
        self.findings.append(
            {"level": level, "check": check, "where": where, "message": message})

    def run(self):
        self.validate()
        self.check_sequence()
        for day_no, day in enumerate(self.plan["days"], 1):
            self.days.append(self.simulate_day(day_no, day))
        self.check_fuel()
        self.check_breaks()
        self.check_stays()
        self.check_departure_day()
        self.check_entry_rules()
        self.check_facts()
        self.check_bookings()
        self.check_constraints()
        return self.result()

    def validate(self):
        plan = self.plan
        if not isinstance(plan.get("days"), list) or not plan["days"]:
            raise PlanError("plan has no days")
        for pid, place in self.places.items():
            try:
                self.tz[pid] = ZoneInfo(place.get("tz", ""))
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise PlanError(
                    f"place {pid}: invalid or missing tz {place.get('tz')!r}") from exc
        for day_no, day in enumerate(plan["days"], 1):
            try:
                date.fromisoformat(day.get("date", ""))
            except ValueError as exc:
                raise PlanError(f"D{day_no}: bad date {day.get('date')!r}") from exc
            if not day.get("stops"):
                raise PlanError(f"D{day_no}: no stops")
            for stop in day["stops"]:
                if stop.get("place") not in self.places:
                    raise PlanError(f"D{day_no}: stop uses undefined place "
                                    f"{stop.get('place')!r}")
        for item in plan.get("hard_constraints") or []:
            if not item.get("id") or not item.get("nl") or not item.get("type"):
                raise PlanError(f"constraint needs id, nl and type: {item}")

    def name(self, pid):
        return self.places[pid].get("name", pid)

    def check_sequence(self):
        days = self.plan["days"]
        for prev_no, (prev, cur) in enumerate(zip(days, days[1:]), 1):
            where = f"D{prev_no + 1}"
            gap = (date.fromisoformat(cur["date"]) - date.fromisoformat(prev["date"])).days
            if gap != 1:
                self.add(FAIL, "dates", where, f"date is {gap} days after the previous day")
            end, start = prev["stops"][-1]["place"], cur["stops"][0]["place"]
            if end != start:
                self.add(FAIL, "continuity", where,
                         f"starts at {self.name(start)} but D{prev_no} ended at "
                         f"{self.name(end)}")

    def simulate_day(self, day_no, day):
        tag = f"D{day_no}"
        local_date = date.fromisoformat(day["date"])
        summary = {"day": day_no, "date": day["date"], "km": 0.0, "drive_min": 0.0,
                   "km_complete": True, "timed": True, "stops": [],
                   "sunset_slack_min": None}
        buffer = 1 + self.rules["drive_buffer_pct"] / 100
        clock = None
        first = day["stops"][0]
        if day.get("depart"):
            hour, minute = parse_hhmm(day["depart"], f"{tag} depart")
            clock = datetime(local_date.year, local_date.month, local_date.day,
                             hour, minute, tzinfo=self.tz[first["place"]])
        else:
            summary["timed"] = False
            self.add(UNKNOWN, "timing", tag, "no departure time, so the day cannot be timed")

        for index, stop in enumerate(day["stops"]):
            pid = stop["place"]
            tz = self.tz[pid]
            where = f"{tag} {self.name(pid)}"
            row = {"place": pid, "name": self.name(pid), "kind": stop.get("kind", ""),
                   "leg_km": None, "arrive": None, "leave": None}
            if index > 0:
                clock = self.drive_leg(stop, where, summary, row, clock, buffer,
                                       tz, pid, local_date)
            if clock is not None:
                arrival = clock
                row["arrive"] = arrival.astimezone(tz).strftime("%H:%M")
                if stop.get("be_by"):
                    self.check_be_by(stop, arrival, tz, where)
                clock = self.check_hours(stop, arrival, tz, where)
                row["arrive_utc"] = arrival.astimezone(timezone.utc).isoformat()
                row["leave"] = clock.astimezone(tz).strftime("%H:%M")
            elif stop.get("kind") in SCHEDULED_KINDS and stop.get("hours") is None:
                self.add(UNKNOWN, "hours", where, "opening hours not confirmed")
            summary["stops"].append(row)

        claimed = day.get("claimed_km")
        if claimed and summary["km_complete"]:
            diff = abs(summary["km"] - claimed) / claimed * 100
            if diff > self.rules["claimed_km_tolerance_pct"]:
                self.add(WARN, "claimed_km", tag,
                         f"source itinerary says {claimed} km, routed legs total "
                         f"{summary['km']:.0f} km ({diff:.0f}% apart)")
        return summary

    def drive_leg(self, stop, where, summary, row, clock, buffer, tz, pid, local_date):
        leg = stop.get("leg") or {}
        km, minutes = leg.get("km"), leg.get("drive_min")
        if km is None or minutes is None:
            self.add(UNKNOWN, "leg", where, "leg has no distance or drive time")
            summary["km_complete"] = False
            summary["timed"] = False
            return None
        if not leg.get("source"):
            self.add(UNKNOWN, "grounding", where, "leg numbers have no source")
        if km >= 100 and minutes and km / (minutes / 60) < self.rules["min_plausible_kmh"]:
            self.add(WARN, "leg_speed", where,
                     f"{km:.0f} km in {fmt_min(minutes)} is {km / (minutes / 60):.0f} km/h, "
                     "so a map point may be off the main road")
        row["leg_km"] = km
        row["leg_min"] = minutes
        summary["km"] += km
        summary["drive_min"] += minutes
        if clock is None:
            return None
        depart = clock
        arrival = clock + timedelta(minutes=minutes * buffer)
        self.check_daylight(leg, depart, arrival, tz, pid, local_date, where, summary)
        return arrival

    def check_daylight(self, leg, depart, arrival, tz, pid, local_date, where, summary):
        place = self.places[pid]
        if place.get("lat") is None or place.get("lon") is None:
            self.add(UNKNOWN, "daylight", where, "place has no coordinates")
            return
        sunrise, sunset = sun_times_utc(local_date, place["lat"], place["lon"])
        if sunset is None:
            self.add(UNKNOWN, "daylight", where, "no sunrise or sunset at this latitude")
            return
        cutoff = sunset - timedelta(minutes=self.rules["sunset_buffer_min"])
        slack = (cutoff - arrival).total_seconds() / 60
        current = summary["sunset_slack_min"]
        summary["sunset_slack_min"] = slack if current is None else min(current, slack)
        arrive_txt = arrival.astimezone(tz).strftime("%H:%M")
        sunset_txt = sunset.astimezone(tz).strftime("%H:%M")
        if self.rules["no_drive_after_sunset"] and arrival > cutoff:
            message = (f"arrives {arrive_txt}, sunset {sunset_txt}, limit is "
                       f"{self.rules['sunset_buffer_min']} min before sunset")
            if leg.get("night_ok"):
                self.add(WARN, "daylight", where, message + " (allowed by night_ok)")
            else:
                self.add(FAIL, "daylight", where, message)
        if self.rules["no_drive_before_sunrise"] and depart < sunrise:
            message = (f"departs {depart.astimezone(tz).strftime('%H:%M')}, sunrise "
                       f"{sunrise.astimezone(tz).strftime('%H:%M')}")
            if leg.get("night_ok"):
                self.add(WARN, "daylight", where, message + " (allowed by night_ok)")
            else:
                self.add(FAIL, "daylight", where, message)

    def check_be_by(self, stop, arrival, tz, where):
        hour, minute = parse_hhmm(stop["be_by"], f"{where} be_by")
        local = arrival.astimezone(tz)
        limit = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if arrival > limit:
            self.add(FAIL, "be_by", where,
                     f"arrives {local.strftime('%H:%M')}, must be there by {stop['be_by']}")

    def check_hours(self, stop, arrival, tz, where):
        """Return the departure time, waiting for opening when needed."""
        dwell = timedelta(minutes=stop.get("dwell_min", 0))
        hours = stop.get("hours")
        if stop.get("kind") not in SCHEDULED_KINDS and hours is None:
            return arrival + dwell
        if hours is None:
            leave = arrival + dwell
            message = "opening hours not confirmed"
            if stop.get("kind") == "visit":
                local, end = arrival.astimezone(tz), leave.astimezone(tz)
                early, late = self.rules["unknown_hours_window"]
                if local.strftime("%H:%M") < early or end.strftime("%H:%M") > late:
                    message += (f", and the visit ({local.strftime('%H:%M')}–"
                                f"{end.strftime('%H:%M')}) is outside the usual {early}–{late}: "
                                "confirm the opening time or move the visit")
            self.add(UNKNOWN, "hours", where, message)
            return leave
        if hours == "always":
            return arrival + dwell
        if not (isinstance(hours, list) and len(hours) == 2):
            raise PlanError(f"{where}: hours must be 'always' or [open, close]")
        local = arrival.astimezone(tz)
        open_h, open_m = parse_hhmm(hours[0], f"{where} hours")
        close_h, close_m = parse_hhmm(hours[1], f"{where} hours")
        opens = local.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
        closes = local.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
        start = local
        if local < opens:
            start = opens
            self.add(WARN, "hours", where,
                     f"arrives {local.strftime('%H:%M')}, waits until {hours[0]} to open")
        leave = start + dwell
        if leave > closes:
            self.add(FAIL, "hours", where,
                     f"arrives {local.strftime('%H:%M')} and stays "
                     f"{stop.get('dwell_min', 0)} min, but it closes at {hours[1]}")
        return leave

    def check_fuel(self):
        vehicle = self.plan.get("vehicle") or {}
        range_km = vehicle.get("range_km")
        if not range_km:
            self.add(UNKNOWN, "fuel", "trip", "vehicle range_km is not set")
            return
        usable = range_km * (1 - self.rules["fuel_reserve_pct"] / 100)
        since = 0.0
        last = "start"
        for day_no, day in enumerate(self.plan["days"], 1):
            for stop in day["stops"]:
                km = (stop.get("leg") or {}).get("km")
                if km is None:
                    if stop is not day["stops"][0]:
                        self.add(UNKNOWN, "fuel", f"D{day_no}",
                                 "cannot track fuel across a leg with no distance")
                        return
                    km = 0
                since += km
                where = f"D{day_no} {self.name(stop['place'])}"
                if since > usable:
                    self.add(FAIL, "fuel", where,
                             f"{since:.0f} km since {last}, usable range is {usable:.0f} km")
                if stop.get("refuel"):
                    since = 0.0
                    last = self.name(stop["place"])

    def check_breaks(self):
        limit = self.rules["max_continuous_drive_min"]
        for day_no, day in enumerate(self.plan["days"], 1):
            run = 0.0
            for stop in day["stops"][1:]:
                run += (stop.get("leg") or {}).get("drive_min") or 0
                if run > limit:
                    self.add(WARN, "breaks", f"D{day_no} {self.name(stop['place'])}",
                             f"{fmt_min(run)} of driving without a "
                             f"{self.rules['break_min_dwell']} min break")
                if stop.get("dwell_min", 0) >= self.rules["break_min_dwell"]:
                    run = 0.0

    def check_stays(self):
        days = self.plan["days"]
        start = date.fromisoformat(days[0]["date"])
        for day_no, day in enumerate(days, 1):
            stay = day.get("stay")
            where = f"D{day_no} stay"
            if not stay:
                if day_no < len(days):
                    self.add(FAIL, "lodging", where, "no lodging for this night")
                continue
            last_stop = day["stops"][-1]["place"]
            if stay.get("place") != last_stop:
                self.add(FAIL, "lodging", where,
                         f"lodging is at {stay.get('place')}, but the day ends at {last_stop}")
            status = stay.get("status")
            if status is None:
                self.add(UNKNOWN, "booking", where, f"{stay.get('name')}: status not recorded")
            elif status != "booked":
                self.add(WARN, "booking", where,
                         f"{stay.get('name')}: {status}, "
                         f"{(start - self.today).days} days before the trip starts")
            name = stay.get("name") or ""
            if not name.strip() or UNNAMED_STAY.search(name):
                self.add(UNKNOWN, "stay_name", where,
                         f"no specific lodging named ({name or 'blank'}): name one or two real "
                         "places from a source")
            if not stay.get("source") and status != "booked":
                self.add(UNKNOWN, "grounding", where,
                         f"{stay.get('name')}: existence not confirmed by a source")
            brands = (self.plan.get("preferences") or {}).get("hotel_brands") or []
            if brands and stay.get("brand") not in brands and not stay.get("brand_note"):
                self.add(UNKNOWN, "brand", where,
                         f"{stay.get('name')}: not {'/'.join(brands)}, and no brand_note says why")
            arrive_utc = self.days[day_no - 1]["stops"][-1].get("arrive_utc")
            until = stay.get("check_in_until")
            if until is None:
                self.add(UNKNOWN, "check_in", where,
                         f"{stay.get('name')}: latest check-in not confirmed")
            elif arrive_utc:
                tz = self.tz[last_stop]
                local = datetime.fromisoformat(arrive_utc).astimezone(tz)
                hour, minute = parse_hhmm(until, f"{where} check_in_until")
                if local > local.replace(hour=hour, minute=minute, second=0, microsecond=0):
                    self.add(FAIL, "check_in", where,
                             f"arrives {local.strftime('%H:%M')}, check-in closes {until}")

        sources = {}
        for day_no, day in enumerate(days, 1):
            stay = day.get("stay") or {}
            if stay.get("source", "").startswith("http"):
                sources.setdefault(stay["source"], set()).add(stay.get("name"))
        for url, names in sources.items():
            if len(names) > 1:
                self.add(WARN, "grounding", "stays",
                         f"{', '.join(sorted(n or '?' for n in names))} share one source link "
                         f"({url}); give each lodging its own page")

    def check_departure_day(self):
        """The night before a flight should be close to the airport."""
        last = self.plan["days"][-1]
        if last["stops"][-1].get("kind") != "airport":
            return
        minutes = self.days[-1]["drive_min"]
        limit = self.rules["departure_day_max_drive_min"]
        if minutes > limit:
            self.add(WARN, "departure_day", f"D{len(self.plan['days'])}",
                     f"{minutes:.0f} min of driving on the day you fly (more than {limit}); "
                     "sleep closer to the airport the night before unless the traveller "
                     "agreed to this")

    def check_entry_rules(self):
        booked = {b.get("place") for b in self.plan.get("bookings") or []}
        for day_no, day in enumerate(self.plan["days"], 1):
            for stop in day["stops"]:
                if stop.get("kind") != "visit":
                    continue
                where = f"D{day_no} {self.name(stop['place'])}"
                rule = stop.get("booking")
                if rule is None:
                    self.add(UNKNOWN, "booking_rule", where,
                             "not checked whether booking or timed entry is needed")
                elif rule not in BOOKING_RULES:
                    raise PlanError(f"{where}: booking must be one of {sorted(BOOKING_RULES)}")
                elif rule == "required" and stop["place"] not in booked:
                    self.add(FAIL, "booking_rule", where,
                             "booking is required but the place is not in the bookings list")

    def check_facts(self):
        for fact in self.plan.get("facts") or []:
            where = fact.get("id", "fact")
            if fact.get("status") != "verified" or not fact.get("source"):
                self.add(UNKNOWN, "fact", where, f"not verified: {fact.get('claim')}")
                continue
            if not fact.get("checked"):
                self.add(UNKNOWN, "fact", where, f"no check date: {fact.get('claim')}")
                continue
            age = (self.today - date.fromisoformat(fact["checked"])).days
            if age > self.rules["max_fact_age_days"]:
                self.add(WARN, "fact", where, f"checked {age} days ago: {fact.get('claim')}")

    def check_bookings(self):
        for item in self.plan.get("bookings") or []:
            where = item.get("id", "booking")
            what = item.get("what", where)
            status = item.get("status")
            if status in ("booked", "walk_up"):
                continue
            if status == "pending":
                self.add(WARN, "booking", where, f"{what}: ordered but payment not confirmed")
                continue
            try:
                due = date.fromisoformat(item.get("book_by") or "")
            except ValueError:
                self.add(UNKNOWN, "book_by", where, f"{what}: no book-by date")
                continue
            left = (due - self.today).days
            if left < 0:
                self.add(FAIL, "book_by", where, f"{what}: not booked and book-by date {due} has passed")
            elif left <= self.rules["book_by_warn_days"]:
                self.add(WARN, "book_by", where, f"{what}: book by {due}, {left} days left")

    def check_constraints(self):
        items = self.plan.get("hard_constraints") or []
        if not items:
            self.add(UNKNOWN, "constraints", "trip",
                     "no hard constraints recorded, so nothing was checked against "
                     "the traveller's requirements")
        for item in items:
            handler = getattr(self, f"c_{item['type']}", None)
            if handler is None:
                status, detail = FAIL, (f"unsupported type {item['type']!r}; rewrite it "
                                        "with a supported type or as manual")
            else:
                status, detail = handler(item.get("params") or {}, item)
            self.constraints.append({"id": item["id"], "nl": item["nl"],
                                     "status": status, "detail": detail})
            if status in (FAIL, UNKNOWN):
                self.add(status, "constraint", item["id"], f"{item['nl']}: {detail}")

    def all_stops(self):
        for day, summary in zip(self.plan["days"], self.days):
            for stop, row in zip(day["stops"], summary["stops"]):
                yield day, stop, row

    def c_manual(self, params, item):
        if item.get("confirmed"):
            return "PASS", f"confirmed: {item['confirmed']}"
        return UNKNOWN, "needs a person to confirm it"

    def c_must_visit(self, params, item):
        hit = any(stop["place"] == params["place"] for _, stop, _ in self.all_stops())
        return ("PASS", "on the route") if hit else (FAIL, "not on the route")

    def c_must_stay(self, params, item):
        for day in self.plan["days"]:
            stay = day.get("stay") or {}
            if stay.get("place") == params["place"] and (
                    "date" not in params or day["date"] == params["date"]):
                return "PASS", f"{stay.get('name')} on {day['date']}"
        return FAIL, "no matching night"

    def daily_limit(self, field, limit, is_bad, unit):
        bad, incomplete = [], []
        for summary in self.days:
            if not summary["km_complete"]:
                incomplete.append(f"D{summary['day']}")
            elif is_bad(summary[field], limit):
                bad.append(f"D{summary['day']} {summary[field]:.0f}")
        if bad:
            return FAIL, f"limit {limit} {unit}: " + ", ".join(bad)
        if incomplete:
            return UNKNOWN, "missing legs on " + ", ".join(incomplete)
        return "PASS", f"all days within {limit} {unit}"

    def c_max_daily_km(self, params, item):
        return self.daily_limit("km", params["km"], lambda v, l: v > l, "km")

    def c_min_daily_km(self, params, item):
        return self.daily_limit("km", params["km"], lambda v, l: v < l, "km")

    def c_max_daily_drive_min(self, params, item):
        return self.daily_limit("drive_min", params["minutes"], lambda v, l: v > l, "min")

    def c_arrive_between(self, params, item):
        rows = [(s, r) for _, s, r in self.all_stops() if s["place"] == params["place"]]
        if not rows:
            return FAIL, "place is not on the route"
        arrive = rows[0][1].get("arrive")
        if arrive is None:
            return UNKNOWN, "arrival time could not be computed"
        if params["from"] <= arrive <= params["to"]:
            return "PASS", f"arrives {arrive}"
        return FAIL, f"arrives {arrive}, wanted {params['from']}-{params['to']}"

    def c_min_dwell(self, params, item):
        spent = sum(s.get("dwell_min", 0) for _, s, _ in self.all_stops()
                    if s["place"] == params["place"])
        if spent >= params["minutes"]:
            return "PASS", f"{spent} min"
        return FAIL, f"{spent} min, wanted {params['minutes']}"

    def c_min_nights_brand(self, params, item):
        brands = params["brand"]
        brands = {brands} if isinstance(brands, str) else set(brands)
        nights = sum(1 for d in self.plan["days"]
                     if (d.get("stay") or {}).get("brand") in brands)
        if nights >= params["nights"]:
            return "PASS", f"{nights} nights"
        return FAIL, f"{nights} nights, wanted {params['nights']}"

    def c_max_nightly_cost(self, params, item):
        over, missing = [], []
        for day_no, day in enumerate(self.plan["days"], 1):
            stay = day.get("stay")
            if not stay:
                continue
            if stay.get("cost") is None:
                missing.append(f"D{day_no} {stay.get('name')}")
            elif stay["cost"] > params["amount"]:
                over.append(f"D{day_no} {stay.get('name')} {stay['cost']:.0f}")
        if over:
            return FAIL, f"over {params['amount']} a night: " + ", ".join(over)
        if missing:
            return UNKNOWN, "no cost for " + ", ".join(missing)
        return "PASS", f"every night within {params['amount']}"

    def c_avoid_tag(self, params, item):
        tag, hits, untagged = params["tag"], [], []
        for day, stop, _ in self.all_stops():
            if stop.get("kind") != "visit":
                continue
            tags = self.places[stop["place"]].get("tags")
            if tags is None:
                untagged.append(f"{day['date']} {self.name(stop['place'])}")
            elif tag in tags:
                hits.append(f"{day['date']} {self.name(stop['place'])}")
        if hits:
            return FAIL, f"tagged {tag!r}: " + ", ".join(hits)
        if untagged:
            return UNKNOWN, "places without tags: " + ", ".join(untagged)
        return "PASS", f"no stop tagged {tag!r}"

    def c_no_visits_on(self, params, item):
        hits = [self.name(stop["place"]) for day, stop, _ in self.all_stops()
                if day["date"] == params["date"] and stop.get("kind") == "visit"]
        if hits:
            return FAIL, f"visits on {params['date']}: " + ", ".join(hits)
        return "PASS", f"no visits on {params['date']}"

    def c_max_budget(self, params, item):
        total, missing = 0.0, []
        for day_no, day in enumerate(self.plan["days"], 1):
            stay = day.get("stay")
            if stay:
                if stay.get("cost") is None:
                    missing.append(f"D{day_no} {stay.get('name')}")
                else:
                    total += stay["cost"]
        total += sum(extra.get("cost", 0) for extra in self.plan.get("extra_costs") or [])
        if total > params["amount"]:
            return FAIL, f"{total:.0f} is over {params['amount']}"
        if missing:
            return UNKNOWN, "no cost for " + ", ".join(missing)
        return "PASS", f"{total:.0f} of {params['amount']}"

    def result(self):
        counts = {level: sum(1 for f in self.findings if f["level"] == level)
                  for level in (FAIL, UNKNOWN, WARN)}
        verdict = "FAIL" if counts[FAIL] else "UNVERIFIED" if counts[UNKNOWN] else "PASS"
        slacks = [d["sunset_slack_min"] for d in self.days if d["sunset_slack_min"] is not None]
        metrics = {
            "total_km": round(sum(d["km"] for d in self.days), 1),
            "longest_day_drive_min": round(max(d["drive_min"] for d in self.days), 1),
            "min_sunset_slack_min": round(min(slacks), 1) if slacks else None,
        }
        return {"verdict": verdict, "counts": counts, "metrics": metrics,
                "days": self.days, "constraints": self.constraints,
                "findings": self.findings}


def evaluate(path, today):
    try:
        with open(path, encoding="utf-8") as handle:
            plan = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"cannot read {path}: {exc}") from exc
    try:
        return Checker(plan, today).run()
    except (KeyError, TypeError, AttributeError) as exc:
        raise PlanError(f"malformed plan: {exc!r}") from exc


def finding_keys(result, levels):
    return {(f["level"], f["check"], f["where"]) for f in result["findings"]
            if f["level"] in levels}


def compare(old, new, user_requested=False, allow_new_unknowns=False):
    """Decide whether new may replace old. Returns (accepted, reasons)."""
    reasons = []
    notes = []
    introduced = finding_keys(new, {FAIL, UNKNOWN}) - finding_keys(old, {FAIL, UNKNOWN})
    for key in sorted(introduced):
        message = f"introduces {key[0]} {key[1]} at {key[2]}"
        if key[0] == UNKNOWN and allow_new_unknowns:
            notes.append(message + " (allowed; research this next)")
        else:
            reasons.append(message)
    old_status = {c["id"]: c["status"] for c in old["constraints"]}
    new_status = {c["id"]: c["status"] for c in new["constraints"]}
    for cid, status in old_status.items():
        if status == "PASS" and new_status.get(cid) != "PASS":
            reasons.append(f"constraint {cid} was PASS, now {new_status.get(cid, 'removed')}")
    if reasons:
        return False, reasons
    if user_requested:
        return True, ["requested by the traveller, and nothing regressed"] + notes
    improved = []
    for level in (FAIL, UNKNOWN, WARN):
        if new["counts"][level] < old["counts"][level]:
            improved.append(f"{level} {old['counts'][level]} -> {new['counts'][level]}")
    old_m, new_m = old["metrics"], new["metrics"]
    if new_m["longest_day_drive_min"] < old_m["longest_day_drive_min"]:
        improved.append("shorter longest driving day")
    if (old_m["min_sunset_slack_min"] is not None
            and new_m["min_sunset_slack_min"] is not None
            and new_m["min_sunset_slack_min"] > old_m["min_sunset_slack_min"]):
        improved.append("more margin before sunset")
    if allow_new_unknowns:
        # A new stop's facts are unresearched, so compare only what is known.
        improved = [item for item in improved if not item.startswith(UNKNOWN)]
    if improved:
        return True, improved + notes
    return False, ["nothing regressed, but nothing measurably improved"] + notes


def print_report(result):
    print(f"VERDICT: {result['verdict']}  "
          f"(FAIL {result['counts'][FAIL]}, UNKNOWN {result['counts'][UNKNOWN]}, "
          f"WARN {result['counts'][WARN]})")
    metrics = result["metrics"]
    print(f"Total {metrics['total_km']} km; longest day "
          f"{fmt_min(metrics['longest_day_drive_min'])} driving before buffer; "
          f"tightest sunset margin {metrics['min_sunset_slack_min']} min\n")
    for day in result["days"]:
        print(f"D{day['day']} {day['date']}: {day['km']:.0f} km, "
              f"{fmt_min(day['drive_min'])} driving")
        for row in day["stops"]:
            leg = f"+{row['leg_km']:.0f} km" if row["leg_km"] is not None else ""
            print(f"   {row['arrive'] or '--:--'}-{row['leave'] or '--:--'}  "
                  f"{row['name']}  {leg}")
    if result["constraints"]:
        print("\nConstraints")
        for item in result["constraints"]:
            print(f"   [{item['status']}] {item['id']}: {item['nl']} ({item['detail']})")
    for level in (FAIL, UNKNOWN, WARN):
        rows = [f for f in result["findings"] if f["level"] == level and f["check"] != "constraint"]
        if rows:
            print(f"\n{level}")
            for row in rows:
                print(f"   [{row['check']}] {row['where']}: {row['message']}")


def main():
    parser = argparse.ArgumentParser(description="Check a road trip plan.")
    parser.add_argument("plan")
    parser.add_argument("--baseline", help="previous plan; accept or reject this edit")
    parser.add_argument("--user-requested", action="store_true",
                        help="with --baseline: the traveller asked for this change, so "
                             "it need not improve a metric, but it may not regress")
    parser.add_argument("--allow-new-unknowns", action="store_true",
                        help="with --baseline: the edit adds a new stop or hotel whose "
                             "facts are not researched yet. New UNKNOWNs are listed "
                             "instead of rejecting the edit. New FAILs still reject it")
    parser.add_argument("--today", help="YYYY-MM-DD, defaults to the system date")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()
    try:
        result = evaluate(args.plan, today)
        baseline = evaluate(args.baseline, today) if args.baseline else None
    except PlanError as exc:
        print(f"INVALID PLAN: {exc}", file=sys.stderr)
        return 3
    if baseline is not None:
        accepted, reasons = compare(baseline, result, args.user_requested,
                                   args.allow_new_unknowns)
        if args.json:
            print(json.dumps({"accepted": accepted, "reasons": reasons}, indent=2))
        else:
            print("ACCEPTED" if accepted else "REJECTED")
            for reason in reasons:
                print(f"   {reason}")
        return 0 if accepted else 4
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result)
    return {"PASS": 0, "FAIL": 1, "UNVERIFIED": 2}[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
