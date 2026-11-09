# Plan file format

A plan is one JSON file. `scripts/verify_trip.py` reads it and `scripts/route_legs.py` fills in coordinates and leg numbers.

## Example

```json
{
  "trip": {"name": "Coast run", "travellers": 2},
  "vehicle": {"type": "2WD rental", "range_km": 650},
  "rules": {"sunset_buffer_min": 30},
  "places": {
    "adl": {"name": "Adelaide", "query": "Adelaide, South Australia", "tz": "Australia/Adelaide"},
    "pta": {"name": "Port Augusta", "query": "Port Augusta, South Australia", "tz": "Australia/Adelaide"}
  },
  "hard_constraints": [
    {"id": "c1", "nl": "No more than 700 km on any day", "type": "max_daily_km", "params": {"km": 700}},
    {"id": "c2", "nl": "Rental allows the unsealed section", "type": "manual"}
  ],
  "facts": [
    {"id": "f1", "claim": "Fruit is not allowed across the border", "status": "verified",
     "source": "https://example.gov/quarantine", "checked": "2026-11-04"}
  ],
  "days": [
    {
      "date": "2026-11-10",
      "depart": "09:00",
      "claimed_km": 310,
      "stops": [
        {"place": "adl", "kind": "start"},
        {"place": "pta", "kind": "overnight", "refuel": true,
         "leg": {"km": 305, "drive_min": 215, "source": "OSRM demo server, 2026-11-04"}}
      ],
      "stay": {"name": "Example Motel", "place": "pta", "brand": null, "status": "unbooked",
               "source": "https://example.com", "check_in_until": "20:00", "cost": 180}
    }
  ]
}
```

## Fields

**`vehicle.range_km`** is the real range on a full tank. The fuel check assumes a full tank at the start and resets only at stops with `"refuel": true`.

**`rules`** overrides these defaults:

| Rule | Default | Meaning |
|---|---|---|
| `drive_buffer_pct` | 10 | Added to every leg's drive time when building the timeline |
| `no_drive_after_sunset` | true | A leg must arrive before the sunset limit |
| `sunset_buffer_min` | 30 | Minutes before sunset that count as the limit |
| `no_drive_before_sunrise` | true | A leg must not depart before sunrise |
| `max_continuous_drive_min` | 120 | Warns if driving runs longer without a break |
| `break_min_dwell` | 15 | A stop this long counts as a break |
| `fuel_reserve_pct` | 20 | Share of the range held back |
| `max_fact_age_days` | 30 | Warns when a verified fact is older |
| `claimed_km_tolerance_pct` | 10 | Warns if `claimed_km` differs from the routed total by more |
| `min_plausible_kmh` | 65 | Warns if a leg of 100 km or more averages below this |
| `book_by_warn_days` | 7 | Warns when an unbooked item's `book_by` is this close |

**`places`** maps an id to `name`, `tz`, and `lat`/`lon`. `tz` must be an IANA zone name and is required. Use `query` to give the geocoder a precise search string. In remote areas, name the roadhouse or business rather than the locality, because a locality's map point can sit away from the highway.

Choose `tz` from what clocks do at that place, not from the state. Some remote areas keep unofficial local time, so check.

`tags` is an optional list describing a place, used by `avoid_tag`. Use a small shared vocabulary such as `beach`, `boat`, `ferry`, `long_walk`, `heights`, `paid_tour`, `cave`, `geothermal`, `museum`, `city`, `wildlife` and `unsealed_road`. When any `avoid_tag` constraint exists, give every visited place a `tags` list, even an empty one, because an untagged visit stays UNKNOWN.

**`preferences`** (optional, not checked) records the intake answers that aren't hard limits, so later versions keep them. For example: `{"language": "fr", "output": "detailed PDF", "hotel_brands": ["Accor"], "brand_rule": "as many as possible", "room": "two beds", "pace": "max sights", "interests": [...], "avoid": ["boat", "beach"], "drivers": 1, "scope": "driving part only"}`.

**`days[].stops[]`**

| Field | Meaning |
|---|---|
| `place` | Place id |
| `kind` | `start`, `visit`, `fuel`, `meal`, `overnight`, `airport` or `pass` |
| `dwell_min` | Time spent at the stop |
| `hours` | `"always"` or `["09:00", "17:00"]`. `visit`, `fuel` and `meal` stops are UNKNOWN without it |
| `refuel` | True if the tank gets filled here |
| `be_by` | Latest local arrival time, such as a flight check-in |
| `fixed` | True keeps the stop in place when `order_stops.py` reorders the day |
| `booking` | For `visit` stops: `none`, `walk_up`, `recommended` or `required`, from a source checked for the travel year. A missing value is UNKNOWN. `required` FAILs unless a `bookings` item has the same `place` |
| `note` / `short` | Report text for this stop: full and brief detail. Written in the traveller's language |
| `leg` | How you got here from the previous stop. `km`, `drive_min`, `source`. Optional `night_ok: true` downgrades a daylight failure to a warning, for lit urban driving only |

**`days[].stay`** needs `name`, `place`, `status` (`booked`, `held` or `unbooked`), `check_in_until`, and `source` unless booked. `brand` and `cost` are used by constraints. Set `brand` to the chain or loyalty program the traveller named, such as "Accor" (not "Novotel"), so that `min_nights_brand` counts it. For a booked stay, also keep `ref`, `room`, `paid` (true, false or "pending") and `cancel` (the terms as stated). When `preferences.hotel_brands` is set, a night at another brand needs `brand_note` saying why, ideally naming the checked plan that tried the brand hotel. Otherwise it is UNKNOWN. Every night except the last day needs one, and its place must match the day's last stop.

**`days[].claimed_km`** is the distance a source itinerary states. Add it when importing an existing plan, so that disagreements surface.

**Report text** (used only by `render_report.py`): `days[].title`, `days[].intro` and `days[].tips` (a list); `places[].label` (keyed by language code, such as `{"fr": "Cap Reinga"}`, shown before `name`); `prep` (`{"checklist": [...], "packing": [...]}`); and `report` (`{"lang": "fr", "format": "pdf", "detail": "full", "layout": "phone", "max_words_per_day": 200, "sections": [...], "title": "...", "open_items": [...], "labels": {...}, "font": {...}}`). `lang` is any language code: labels are built in for English, and `labels` holds translations for any other language (the keys printed by `render_report.py --print-labels`, with check names under `checks`) or overrides single English labels. `font` (`{"regular": path, "bold": path}`) picks the PDF font when the system fonts don't cover the script. In the phone layout, the renderer warns when a day goes over `max_words_per_day`. `stay` can also carry `currency` for the hotel table.

**`overnight_candidates`** (optional, used by `choose_nights.py`) lists towns or hotels that could host a night: `place` (a place id with coordinates), `after` (the place on the current route it sits after), and optionally `brand`, `name`, `cost`, `source`, `check_in_until` and `refuel`. The current stays are always candidates too.

**`contingencies`** (optional) lists backup plans for road or weather risks: `risk`, `trigger` (what to watch), `decide_by` (date), `plan` (what changes, and the backup plan file), and `source`. The report shows them under open items.

**`bookings`** (optional) lists what needs booking. Each item has `id`, `what`, `date`, `status` (`unbooked`, `pending`, `booked` or `walk_up`), and `book_by` unless booked or walk-up. Optional fields are `place` (links it to a visit stop's `booking: required`), `ref`, `source` and `cancel`. The checker FAILs an unbooked item past `book_by`, WARNs within `rules.book_by_warn_days` (default 7) and on `pending`, and reports a missing `book_by` as UNKNOWN. See `prep-and-bookings.md`.

**`facts`** holds real-world claims that the scripts cannot compute. Each needs `claim`, `status`, `source` and `checked`. Anything not marked `verified` with a source is UNKNOWN.

## Constraint types

| Type | Params | Checks |
|---|---|---|
| `must_visit` | `place` | The place is a stop |
| `must_stay` | `place`, optional `date` | A night is spent there |
| `max_daily_km` / `min_daily_km` | `km` | Every day's total |
| `max_daily_drive_min` | `minutes` | Every day's drive time before buffer |
| `arrive_between` | `place`, `from`, `to` | First arrival, local time |
| `min_dwell` | `place`, `minutes` | Total time at the place |
| `min_nights_brand` | `brand` (a name or a list), `nights` | Nights at any of the brands |
| `max_budget` | `amount` | Sum of stay costs plus `extra_costs[].cost` |
| `max_nightly_cost` | `amount` | Every stay's `cost`; a missing cost is UNKNOWN |
| `avoid_tag` | `tag` | No `visit` stop's place carries the tag; an untagged visit is UNKNOWN |
| `no_visits_on` | `date` | No `visit` stops on that date, such as the day someone flies out |
| `manual` | none | UNKNOWN until the item has a `confirmed` string saying who confirmed it and how |

An unrecognised type is a FAIL, so a requirement can't pass by being misspelt.
