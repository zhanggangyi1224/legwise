# Legwise

Legwise packages the `road-trip-planner` skill. Plan, check and repair multi-day road trips with Claude. The skill asks multiple-choice questions before planning (route, travellers, drivers, hotel brand, room and budget, daily distance, pace, things to avoid, output format). It then builds the plan from OpenStreetMap road data and checks it with a deterministic script: sunset, fuel range, opening hours, check-in times, booking rules, book-by dates, and daily and budget limits. It can choose overnight towns to get the most nights at a preferred hotel brand, order each day's stops, and print a fixed-format report in PDF, HTML or Markdown, in any language you choose.

Setup: Python 3.9+ (PDF output also needs `reportlab`). Set `ROAD_TRIP_UA` to an identifying User-Agent for the public map services, which are for light personal use only. It never books or pays for anything.

Install (Claude Code 2.1.275 or later):

```
/plugin install legwise --marketplace zhanggangyi1224/legwise
```

## What it sends and stores

- **Network:** the scripts contact only two public OpenStreetMap services, and only when routing:
  - `nominatim.openstreetmap.org` receives place names and returns their coordinates (`route_legs.py`).
  - `router.project-osrm.org` receives coordinates and returns distances and drive times (`route_legs.py`, `order_stops.py`, `choose_nights.py`).

  Requests carry the User-Agent in `ROAD_TRIP_UA`, or a generic one if it is unset. Nothing else is sent: no traveller names, bookings or contact details. The checker and the report renderer work offline, and `order_stops.py` and `choose_nights.py` have an `--offline` mode that makes no requests.
- **Storage:** the plan is a JSON file in a folder you choose, and reports are written next to it. The plugin keeps no other data and has no server of its own.
- **Personal data:** the plan may hold booking references you paste in. The skill is told not to repeat emails, phone numbers or ID numbers, and the report renderer refuses to write a report that contains an email address.

See the repository README for usage, examples and the evaluation report.
