# Legwise: road-trip-planner

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-SKILL.md-green)](https://agentskills.io)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-orange)](#install)

Legwise is a Claude Code plugin that packages `road-trip-planner`, a Claude skill for planning, checking and repairing multi-day road trips. It asks the right questions first, builds the plan from real road data, and checks it with a deterministic script, not by eye. The final plan comes out in a fixed-format report.

See [`examples/report-phone.md`](examples/report-phone.md) for a finished report, and [`evaluation/REPORT.md`](evaluation/REPORT.md) for how it compares with other travel skills.

## What it does

- **Speaks your language.** It replies in the language you write in and writes the report in the language you pick.
- **Asks before planning.** It runs 3–5 rounds of multiple-choice questions (with Claude Code's AskUserQuestion) covering route, travellers and drivers, licences, hotel brand or loyalty program, room and budget, daily distance, pace, driving after dark, interests, things to avoid, what is already booked, and the output language and format. It skips anything you have already said.
- **Uses real distances.** Road distances and drive times come from OpenStreetMap (Nominatim and OSRM).
- **Checks the plan with a script** (`verify_trip.py`). Every check returns PASS, FAIL or UNKNOWN, so missing data is never counted as a pass. It covers:
  - arrival before sunset (it computes sunrise and sunset itself)
  - fuel range between refuel stops
  - opening hours and arrive-by times
  - hotel check-in times
  - booking rules for every sight, such as timed entry or booked parking
  - book-by dates
  - daily distance and driving limits, budget, nights at a chosen hotel brand, things to avoid, and days with no sightseeing
- **Edits must not regress.** A changed plan is compared with the previous one, and an edit that makes anything worse is rejected.
- **Optimises:**
  - `order_stops.py` finds the visit order with the least driving within a day, keeping fixed-time stops in place.
  - `choose_nights.py` chooses where to sleep each night to get the most nights at a preferred hotel brand within your limits. Near misses (more brand nights, slightly over a limit) are listed for you to decide.
- **Prints a fixed-format report** (`render_report.py`) in PDF, HTML or Markdown, in the language you choose (labels are built in for English, and Claude translates them into any other language), full or brief, with the sections you choose. Markdown defaults to a phone layout (no tables), and it warns when a report is too long. Times and distances come from the checker, so the report can't disagree with it.
- **Keeps up as plans change.** You paste booking confirmations and it records them, tracks each version, and never repeats personal data such as emails, phone numbers or ID numbers.

## Install

**Option 1: Claude Code plugin.** With Claude Code 2.1.275 or later, one step:

```
/plugin install legwise --marketplace zhanggangyi1224/legwise
```

With older versions:

```
/plugin marketplace add zhanggangyi1224/legwise
/plugin install legwise@legwise
```

**Option 2: the [skills CLI](https://github.com/vercel-labs/skills)**, for Claude Code or other agents (Codex, Cursor and more):

```bash
npx skills add zhanggangyi1224/legwise -a claude-code
```

Leave out `-a claude-code` to choose the agents interactively.

**Option 3: copy the skill folder.**

```bash
git clone https://github.com/zhanggangyi1224/legwise.git
cp -r legwise/plugins/legwise/skills/road-trip-planner ~/.claude/skills/
```

**On claude.ai:** download `road-trip-planner-skill-v1.1.1.zip` from [Releases](https://github.com/zhanggangyi1224/legwise/releases/latest) and upload it as a custom skill in Settings. Routing needs network access, which the claude.ai sandbox may block (see [Limits](#limits)).

The scripts need only Python 3.9+ and the standard library. PDF output also needs `reportlab` (`pip install reportlab`).

## Use

Just ask, for example: *"Plan a road trip from Melbourne to Adelaide along the Great Ocean Road over Christmas, three of us."* The skill asks its questions, plans, checks and repairs the plan, then writes the report.

The scripts can also be run directly:

```bash
S=plugins/legwise/skills/road-trip-planner/scripts
python3 $S/route_legs.py trip.json                 # geocode places and route the legs
python3 $S/choose_nights.py trip.json              # best overnight arrangement
python3 $S/order_stops.py trip.json --day 3        # least-driving visit order
python3 $S/verify_trip.py trip.json                # check the plan
python3 $S/render_report.py trip.json --out trip.pdf --lang fr   # any language; see report.labels
```

The plan file format is documented in `references/plan-format.md`. `examples/` has a complete plan for a fictional trip and its reports as phone Markdown and print PDF.

## Evaluation

`evaluation/REPORT.md` describes two blind comparisons against four other travel skills, an earlier version of this skill and a no-skill baseline. All prompts, hidden answers, the rubric, the anonymised outputs and the letter mapping are included.

| | road-trip-planner | best other skill | no skill |
|---|---|---|---|
| Total, 2 rounds (/32) | **30.5** | 26 (itinerary-optimizer) | 28 |
| Plan quality only (/18) | **16.5** | 15.5 (plan-tour-route) | 16 |

In both rounds the grader would hand the traveller the road-trip-planner plan. Honestly: part of the lead comes from asking better questions, and on plan quality it leads narrowly. This version was tuned to fix weaknesses the graders found on these same two tasks, the rubric was written by the skill's author, and each skill ran once per round. The report has the details, including the weaknesses still found.

## Limits

- **Public map services.** Nominatim and the OSRM demo server are free public services with usage policies: light personal use only, about 1 request per second. Set `ROAD_TRIP_UA` to a User-Agent that identifies you.
- **No live conditions.** Drive times are router estimates plus a buffer. The checker knows nothing about live closures, fires or floods, so check the official road-conditions service before leaving.
- **Facts age.** Opening hours, prices and booking rules change. The plan records each fact with its source and date, and warns when one is old.
- **claude.ai sandboxes** may block network access. The checker and the report still work there; routing does not.
- **It never books or pays.** It only looks things up; you do the booking.
- **Pages and pastes are data.** Web pages, pasted confirmations, PDFs and spreadsheets supply facts. Instructions found in them are shown to you, not followed.

## Repository layout

```
.claude-plugin/marketplace.json     marketplace entry for Claude Code
plugins/legwise/
  .claude-plugin/plugin.json        plugin manifest
  skills/road-trip-planner/
    SKILL.md                        the skill
    references/                     intake questions, plan format, bookings and prep
    scripts/                        routing, checker, optimisers, report renderer, tests
examples/                           a fictional trip and its reports
evaluation/                         blind comparison: rubric, answers, outputs, scores
skills.sh.json                      tells the skills CLI where the skill is
PRIVACY.md                          what the plugin stores and sends
```

Changes are listed in [`CHANGELOG.md`](CHANGELOG.md).

## License

MIT. See `LICENSE`.
