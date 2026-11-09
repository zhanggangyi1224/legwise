#!/usr/bin/env python3
"""Suggest the visit order within a day that needs the least driving.

    order_stops.py trip.json --day 3                     suggest, change nothing
    order_stops.py trip.json --day 3 --write new.json    save the order as a new plan
    order_stops.py trip.json --day 3 --offline           straight-line estimate, no network

Only stops between anchors move. Anchors are the first and last stop, any stop with
`be_by` or `"fixed": true`, and any `start`, `overnight` or `airport` stop. A fixed-time
tour therefore stays where it is. Drive times come from the public OSRM table service,
or from straight-line distance x 1.3 at 80 km/h with --offline. This minimises driving
only; opening hours and sunset are for verify_trip.py, so check the new plan with it.
"""
import argparse
import itertools
import json
import math
import sys
import urllib.request

from route_legs import USER_AGENT

OSRM_TABLE = "https://router.project-osrm.org/table/v1/driving/"
ANCHOR_KINDS = {"start", "overnight", "airport"}
EXACT_LIMIT = 8


def is_anchor(stop, index, count):
    return (index in (0, count - 1) or stop.get("be_by") or stop.get("fixed")
            or stop.get("kind") in ANCHOR_KINDS)


def osrm_matrix(points):
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    request = urllib.request.Request(f"{OSRM_TABLE}{coords}?annotations=duration",
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table: {data.get('code')}")
    return [[(d or 0) / 60 for d in row] for row in data["durations"]]


def straight_matrix(points):
    def minutes(a, b):
        p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
        dp, dl = p2 - p1, math.radians(b["lon"] - a["lon"])
        h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        km = 2 * 6371 * math.asin(math.sqrt(h)) * 1.3
        return km / 80 * 60
    return [[minutes(a, b) for b in points] for a in points]


def path_cost(order, m):
    return sum(m[a][b] for a, b in zip(order, order[1:]))


def best_order(m):
    """Matrix index 0 is the segment start, the last index its end; the rest move."""
    end = len(m) - 1
    middle = list(range(1, end))
    if len(middle) <= EXACT_LIMIT:
        best = min(itertools.permutations(middle),
                   key=lambda perm: path_cost([0, *perm, end], m))
        return list(best)
    order, left = [], set(middle)
    current = 0
    while left:
        current = min(left, key=lambda j: m[current][j])
        order.append(current)
        left.remove(current)
    improved = True
    while improved:
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                trial = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                if path_cost([0, *trial, end], m) < path_cost([0, *order, end], m) - 1e-9:
                    order, improved = trial, True
    return order


def reorder_day(day, places, matrix_fn):
    stops = day["stops"]
    count = len(stops)
    anchors = [i for i, s in enumerate(stops) if is_anchor(s, i, count)]
    new_stops, before, after = [stops[0]], 0.0, 0.0
    for a, b in zip(anchors, anchors[1:]):
        segment = stops[a:b + 1]
        points = [places[s["place"]] for s in segment]
        if any(p.get("lat") is None for p in points):
            raise ValueError("a place has no coordinates; run route_legs.py first")
        if len(segment) > 3:
            m = matrix_fn(points)
            order = best_order(m)
            before += path_cost(list(range(len(segment))), m)
            after += path_cost([0, *order, len(segment) - 1], m)
            new_stops.extend(segment[i] for i in order)
        else:
            new_stops.extend(segment[1:-1])
        new_stops.append(segment[-1])
    return new_stops, before, after


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan")
    parser.add_argument("--day", type=int, required=True, help="day number, 1-based")
    parser.add_argument("--write", help="save a new plan file with the suggested order")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    with open(args.plan, encoding="utf-8") as handle:
        plan = json.load(handle)
    day = plan["days"][args.day - 1]
    places = plan["places"]
    matrix_fn = straight_matrix if args.offline else osrm_matrix
    new_stops, before, after = reorder_day(day, places, matrix_fn)

    def names(stops):
        return " -> ".join(places[s["place"]].get("name", s["place"]) for s in stops)

    print(f"current:   {names(day['stops'])}")
    print(f"suggested: {names(new_stops)}")
    source = "straight-line estimate" if args.offline else "OSRM"
    print(f"movable driving: {before:.0f} min now, {after:.0f} min suggested ({source})")
    if [s["place"] for s in new_stops] == [s["place"] for s in day["stops"]]:
        print("already the shortest order")
        return 0
    if args.write:
        old_index = {id(s): i for i, s in enumerate(day["stops"])}
        for prev, stop in zip(new_stops, new_stops[1:]):
            if day["stops"][old_index[id(stop)] - 1] is not prev:
                stop.pop("leg", None)
        day["stops"] = new_stops
        with open(args.write, "w", encoding="utf-8") as handle:
            json.dump(plan, handle, ensure_ascii=False, indent=2)
        print(f"wrote {args.write}; next: route_legs.py on it, then "
              f"verify_trip.py {args.write} --baseline {args.plan}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
