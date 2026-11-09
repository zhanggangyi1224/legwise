# Changelog

## 1.0.0 (2026-11-09)

First public release of Legwise, the Claude Code plugin that packages the `road-trip-planner` skill.

- Multiple-choice intake in 3–5 rounds: route, travellers, drivers, licences, hotel brand, room and budget, daily distance, pace, interests, things to avoid, bookings, and report language and format.
- The traveller chooses the language. Replies follow the language they write in, and the report can be in any language: labels are built in for English, and Claude translates the labels from `render_report.py --print-labels` into the plan's `report.labels`.
- `route_legs.py`: geocoding and road distances from OpenStreetMap (Nominatim and OSRM).
- `verify_trip.py`: deterministic checker with PASS, FAIL or UNKNOWN for sunset, fuel range, opening hours, check-in times, booking rules, book-by dates, daily limits, budget, brand nights, things to avoid and no-sightseeing days. Edits are compared with the previous version and rejected if anything regresses.
- `order_stops.py`: least-driving visit order within a day, with fixed-time stops kept in place.
- `choose_nights.py`: overnight towns chosen for the most brand nights within the limits, with near misses listed.
- `render_report.py`: fixed-format report in PDF, HTML or Markdown, full or brief, with a phone layout and length limits. PDF fonts follow the script the report uses, and `report.font` can name one.
- Directory listing details in `plugin.json`, and a privacy policy in `PRIVACY.md`.
- Blind evaluation against four other travel skills and a no-skill baseline (`evaluation/`).
