#!/usr/bin/env python3
"""Choose where to sleep each night so the trip gets the most brand nights within the limits.

    choose_nights.py trip.json                         list the best options, change nothing
    choose_nights.py trip.json --write trip_v4.json    save option 1 as a new plan
    choose_nights.py trip.json --write new.json --pick 2
    choose_nights.py trip.json --offline               straight-line estimate, no network

The route is treated as one line: every stop of every day, in order. Candidate
overnight towns come from the current stays plus `overnight_candidates` in the plan,
each inserted after a place on that line (set `refuel: true` on a candidate
town with fuel, so the fuel check still has its stops). Sights stay in order and are assigned to
whichever day passes them. Limits come from the plan's `max_daily_km` and
`max_daily_drive_min` constraints, or `--max-km` / `--max-drive-min`. Kept fixed:
booked stays, booked or pending `bookings` that name a `place` and `date` (that sight
must fall on that day), and `no_visits_on` dates. Options are ranked by brand nights
(`preferences.hotel_brands`), then the longest driving day, then total driving.
Sunset and opening hours are for verify_trip.py: always check the written plan.
"""
import argparse
import copy
import itertools
import json
import math
import sys
import urllib.request

from route_legs import USER_AGENT

OSRM_TABLE = "https://router.project-osrm.org/table/v1/driving/"
OVERNIGHT_KINDS = {"start", "overnight", "airport"}


def osrm_matrices(points):
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    request = urllib.request.Request(f"{OSRM_TABLE}{coords}?annotations=duration,distance",
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.load(response)
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table: {data.get('code')}")
    minutes = [[(d or 0) / 60 for d in row] for row in data["durations"]]
    km = [[(d or 0) / 1000 for d in row] for row in data["distances"]]
    return km, minutes


def straight_matrices(points):
    def km(a, b):
        p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
        dp, dl = p2 - p1, math.radians(b["lon"] - a["lon"])
        h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * 6371 * math.asin(math.sqrt(h)) * 1.3
    dist = [[km(a, b) for b in points] for a in points]
    return dist, [[d / 80 * 60 for d in row] for row in dist]


def build_line(plan):
    """Return line items: dicts with place, stop (original dict or None), role."""
    line = []
    for day in plan["days"]:
        for stop in day["stops"]:
            if line and line[-1]["place"] == stop["place"]:
                continue
            role = "town" if stop.get("kind") in OVERNIGHT_KINDS else "sight"
            line.append({"place": stop["place"], "stop": stop, "role": role})
    line[0]["role"] = line[-1]["role"] = "end"
    for cand in plan.get("overnight_candidates") or []:
        after = [i for i, item in enumerate(line) if item["place"] == cand["after"]]
        if not after:
            raise ValueError(f"candidate {cand['place']}: 'after' place {cand['after']} "
                             "is not on the route")
        line.insert(after[0] + 1, {"place": cand["place"], "stop": None, "role": "town",
                                   "brand": cand.get("brand"), "cost": cand.get("cost"),
                                   "refuel": cand.get("refuel", False)})
    return line


def town_info(plan):
    """Brand and stay details per place, from current stays and candidates."""
    info = {}
    for day in plan["days"]:
        stay = day.get("stay")
        if stay:
            info[stay["place"]] = stay
    for cand in plan.get("overnight_candidates") or []:
        info.setdefault(cand["place"], {
            "name": cand.get("name") or plan["places"][cand["place"]].get("name", cand["place"]),
            "place": cand["place"], "brand": cand.get("brand"), "status": "unbooked",
            "cost": cand.get("cost"), "source": cand.get("source"),
            "check_in_until": cand.get("check_in_until")})
    return info


def limits_from(plan, args):
    max_km, max_min = args.max_km, args.max_drive_min
    for c in plan.get("hard_constraints") or []:
        if c.get("type") == "max_daily_km" and max_km is None:
            max_km = c["params"]["km"]
        if c.get("type") == "max_daily_drive_min" and max_min is None:
            max_min = c["params"]["minutes"]
    return max_km, max_min


def solve(plan, line, km, mins, max_km, max_min, top=5, slack=0.10):
    """Return (options within limits, count, near misses). A near miss breaks only the
    km or driving limit, by at most `slack`, and has more brand nights than the best
    option; it is for the traveller to weigh, never chosen automatically."""
    days = plan["days"]
    nights = len(days) - 1
    info = town_info(plan)
    brands = set((plan.get("preferences") or {}).get("hotel_brands") or [])
    towns = [i for i, item in enumerate(line) if item["role"] == "town"]
    sights = [i for i, item in enumerate(line) if item["role"] == "sight"]
    fixed = {}
    for n, day in enumerate(days[:-1]):
        stay = day.get("stay") or {}
        if stay.get("status") == "booked":
            fixed[n] = stay["place"]
    sight_day = {}
    for b in plan.get("bookings") or []:
        if b.get("place") and b.get("date") and b.get("status") in ("booked", "pending"):
            sight_day[b["place"]] = b["date"]
    quiet = {c["params"]["date"] for c in plan.get("hard_constraints") or []
             if c.get("type") == "no_visits_on"}

    def day_cost(a, b):
        path = [a] + [s for s in sights if a < s < b] + [b]
        return (sum(km[x][y] for x, y in zip(path, path[1:])),
                sum(mins[x][y] for x, y in zip(path, path[1:])), path[1:-1])

    options, near = [], []
    for combo in itertools.combinations(towns, nights):
        if any(line[combo[n]]["place"] != p for n, p in fixed.items()):
            continue
        ends = [0, *combo, len(line) - 1]
        ok, rows, over = True, [], 0.0
        for n, (a, b) in enumerate(zip(ends, ends[1:])):
            dkm, dmin, visited = day_cost(a, b)
            date = days[n]["date"]
            if ((date in quiet and visited)
                    or any(sight_day.get(line[s]["place"], date) != date for s in visited)):
                ok = False
                break
            if max_km is not None and dkm > max_km:
                over = max(over, dkm / max_km - 1)
            if max_min is not None and dmin > max_min:
                over = max(over, dmin / max_min - 1)
            rows.append((dkm, dmin))
        if not ok or over > slack:
            continue
        brand_nights = sum(1 for i in combo if (info.get(line[i]["place"]) or {}).get("brand")
                           in brands or line[i].get("brand") in brands) if brands else 0
        option = {"towns": [line[i]["place"] for i in combo], "ends": ends,
                  "brand_nights": brand_nights, "days": rows, "over": over,
                  "longest_min": max(r[1] for r in rows), "total_min": sum(r[1] for r in rows)}
        (near if over > 0 else options).append(option)
    options.sort(key=lambda o: (-o["brand_nights"], o["longest_min"], o["total_min"]))
    best = options[0]["brand_nights"] if options else -1
    near = [o for o in near if o["brand_nights"] > best]
    near.sort(key=lambda o: (-o["brand_nights"], o["over"], o["total_min"]))
    return options[:top], len(options), near[:3]


def write_plan(plan, line, option, path):
    """Rebuild the days around the chosen nights. A leg is kept only where the stop
    before it is unchanged; route_legs.py fills the rest."""
    new = copy.deepcopy(plan)
    info = town_info(plan)
    prev_place = {}
    for day in plan["days"]:
        for prev, stop in zip(day["stops"], day["stops"][1:]):
            prev_place[id(stop)] = prev["place"]
    ends = option["ends"]
    last_day = len(ends) - 2
    for n, (a, b) in enumerate(zip(ends, ends[1:])):
        day = new["days"][n]
        stops = [{"place": line[a]["place"], "kind": "start"}]
        for i in range(a + 1, b + 1):
            item = line[i]
            if i < b and item["role"] != "sight":
                continue
            orig = item["stop"]
            stop = copy.deepcopy(orig) if orig else {"place": item["place"]}
            if not orig and item.get("refuel"):
                stop["refuel"] = True
            if i == b and n < last_day:
                stop["kind"] = "overnight"
                stop.pop("dwell_min", None)
            if not orig or prev_place.get(id(orig)) != stops[-1]["place"]:
                stop.pop("leg", None)
            stops.append(stop)
        day["stops"] = stops
        if n < last_day:
            place = line[b]["place"]
            if (day.get("stay") or {}).get("place") != place:
                stay = copy.deepcopy(info.get(place) or {
                    "name": new["places"][place].get("name", place), "place": place,
                    "status": "unbooked"})
                stay.pop("brand_note", None)
                day["stay"] = stay
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(new, handle, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan")
    parser.add_argument("--write", help="save the chosen option as a new plan file")
    parser.add_argument("--pick", type=int, default=1, help="which option to write (1-based)")
    parser.add_argument("--max-km", type=float)
    parser.add_argument("--max-drive-min", type=float)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    with open(args.plan, encoding="utf-8") as handle:
        plan = json.load(handle)
    line = build_line(plan)
    points = [plan["places"][item["place"]] for item in line]
    if any(p.get("lat") is None for p in points):
        print("a place has no coordinates; run route_legs.py first", file=sys.stderr)
        return 3
    km, mins = (straight_matrices if args.offline else osrm_matrices)(points)
    max_km, max_min = limits_from(plan, args)
    options, count, near = solve(plan, line, km, mins, max_km, max_min)
    print(f"{count} night arrangements fit (max {max_km} km, {max_min} min driving a day)")
    names = {pid: p.get("name", pid) for pid, p in plan["places"].items()}

    def show(label, o):
        days = ", ".join(f"{d[0]:.0f} km/{d[1] / 60:.1f} h" for d in o["days"])
        print(f"{label} brand nights {o['brand_nights']}: "
              + " | ".join(names[t] for t in o["towns"]) + f"\n   days: {days}")

    for k, o in enumerate(options, 1):
        show(f"{k}.", o)
    if near:
        print("\nNear misses: more brand nights, but a day goes over a limit (traveller decides):")
        for o in near:
            worst = max(o["days"], key=lambda d: d[1])
            show(f"   +{o['over'] * 100:.0f}% over;", o)
            print(f"   longest day {worst[0]:.0f} km / {worst[1]:.0f} min")
    if not options:
        print("none fit; relax a limit, add candidate towns, or add a day")
        return 1
    if args.write:
        write_plan(plan, line, options[args.pick - 1], args.write)
        print(f"wrote {args.write}; next: route_legs.py on it, then verify_trip.py "
              f"{args.write} --baseline {args.plan} --allow-new-unknowns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
