#!/usr/bin/env python3
"""Fill missing coordinates and leg distances in a plan from OpenStreetMap services.

    route_legs.py trip.json                  fill what is missing, in place
    route_legs.py trip.json --force          re-route every leg
    route_legs.py trip.json --dry-run        print results, write nothing

Coordinates come from Nominatim and legs from the public OSRM demo server. Both
receive only place names and coordinates. Treat OSRM as a good distance figure
and a rough time figure: it does not know about roadworks or closures.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

# Nominatim's usage policy asks for an identifying User-Agent. Set ROAD_TRIP_UA to
# something that identifies you, such as "road-trip-planner/1.0 (you@example.com)".
USER_AGENT = os.environ.get("ROAD_TRIP_UA", "road-trip-planner-skill/1.0 (personal trip planning)")
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org/route/v1/driving/"


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def geocode(query):
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    results = get_json(f"{NOMINATIM}?{params}")
    time.sleep(1.1)
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"]), results[0]["display_name"]


def route(start, end):
    coords = f"{start['lon']},{start['lat']};{end['lon']},{end['lat']}"
    data = get_json(f"{OSRM}{coords}?overview=false")
    time.sleep(0.3)
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    best = data["routes"][0]
    return round(best["distance"] / 1000, 1), round(best["duration"] / 60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("--force", action="store_true", help="re-route legs that have data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    with open(args.plan, encoding="utf-8") as handle:
        plan = json.load(handle)
    places = plan["places"]
    problems = 0

    for pid, place in places.items():
        if place.get("lat") is not None and place.get("lon") is not None:
            continue
        found = geocode(place.get("query") or place.get("name") or pid)
        if not found:
            print(f"NOT FOUND  {pid}: add a better 'query' or coordinates")
            problems += 1
            continue
        place["lat"], place["lon"] = found[0], found[1]
        print(f"geocoded   {pid}: {found[2]}")

    stamp = f"OSRM demo server (OSM data), {date.today().isoformat()}"
    for day_no, day in enumerate(plan["days"], 1):
        stops = day["stops"]
        for prev, stop in zip(stops, stops[1:]):
            leg = stop.setdefault("leg", {})
            if leg.get("km") is not None and leg.get("drive_min") is not None and not args.force:
                continue
            start, end = places[prev["place"]], places[stop["place"]]
            if start.get("lat") is None or end.get("lat") is None:
                problems += 1
                continue
            result = route(start, end)
            label = f"D{day_no} {prev['place']} -> {stop['place']}"
            if result is None:
                print(f"NO ROUTE   {label}")
                problems += 1
                continue
            leg["km"], leg["drive_min"] = result
            leg["source"] = stamp
            print(f"routed     {label}: {result[0]} km, {result[1]} min")

    if not args.dry_run:
        with open(args.plan, "w", encoding="utf-8") as handle:
            json.dump(plan, handle, ensure_ascii=False, indent=2)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
