# Evaluation report

Two blind comparisons of `road-trip-planner` (this release) against four other travel skills, an earlier version of itself, and a no-skill baseline. Everything needed to check the scores is in this folder.

**Short version:** `road-trip-planner` scored highest overall in both rounds. Most of the lead comes from the questions it asks before planning. On plan quality alone it tied for first with plan-tour-route. In both rounds the grader said it would hand the traveller a different plan.

## Method

Each run was a fresh Claude subagent that followed exactly one skill, or no skill. The exact prompts are in `prompts.md`.

1. **Phase 1: questions.** The run got only a short first message from a traveller and wrote the questions it would ask before planning (`questions-*.md`). It couldn't talk to anyone.
2. **Phase 2: plan.** The run then got the same hidden answers as every other run (`answers.md`) and produced the deliverable the traveller asked for (`report-*`).
3. **Blind grading.** Outputs were copied under random letters, with any text naming a skill removed. A separate grader scored them against `rubric.md`: 16 items, each scored 1, 0.5 or 0. Items 1–7 grade the questions and items 8–16 grade the plan. The grader checked drive times against sunset by arithmetic and was allowed web searches only to settle factual disagreements. `mapping.json` reveals the letters.

The hidden answers carried deliberate traps:
- **Round 1:** one seasick driver (most Milford Sound visits involve a boat), no beaches, ≤500 km a day, Accor where possible (not available in every town), no sightseeing on the departure day, and a detailed PDF.
- **Round 2:** Christmas Day closures, a 6-year-old who needs a child seat, IHG where possible (sparse on the route), off the road 1 hour before sunset because of kangaroos, no unsealed roads, and a short Markdown file to read on a phone.

## Results

### Round 1: Christchurch → Queenstown, NZ (detailed PDF)

| Skill | Questions /7 | Plan /9 | Total /16 |
|---|---|---|---|
| **road-trip-planner** | **7** | **8.5** | **15.5** |
| no skill | 5.5 | **8.5** | 14 |
| road-trip-planner (earlier version) | 4.5 | **8.5** | 13 |
| travel-agent | 4 | **8.5** | 12.5 |
| itinerary-optimizer | 4.5 | 7.5 | 12 |
| plan-tour-route | 3.5 | 8 | 11.5 |
| trip-planner | 3.5 | 8 | 11.5 |

The grader said it would hand the traveller the no-skill plan, for its complete route with weather-buffer nights, named hotels with prices, and dated bookings. It said road-trip-planner scored highest because its questions were the best, but its PDF left four hotels unnamed and read thin for a "detailed" plan.

### Round 2: Melbourne → Adelaide over Christmas (short Markdown)

| Skill | Questions /7 | Plan /9 | Total /16 |
|---|---|---|---|
| **road-trip-planner** | **7** | 7.5 | **14.5** |
| no skill | 6.5 | 7 | 13.5 |
| itinerary-optimizer | 6 | 7 | 13 |
| road-trip-planner (earlier version) | 4.5 | 7 | 11.5 |
| travel-agent | 5 | 6.5 | 11.5 |
| plan-tour-route | 3.5 | **8** | 11.5 |
| trip-planner | 4 | 7 | 11 |

The grader said it would hand the traveller itinerary-optimizer's plan: it stays within every limit, gets two IHG nights, ends in Adelaide with an hour's buffer, and fits on a phone. road-trip-planner was the only plan to catch the new Twelve Apostles parking booking, but it ended the trip in Meningie instead of Adelaide.

### Combined

| Skill | Total /32 | Plan only /18 |
|---|---|---|
| **road-trip-planner** | **30** | **16** |
| no skill | 27.5 | 15.5 |
| itinerary-optimizer | 25 | 14.5 |
| road-trip-planner (earlier version) | 24.5 | 15.5 |
| travel-agent | 24 | 15 |
| plan-tour-route | 23 | **16** |
| trip-planner | 22.5 | 15 |

### Weaknesses the graders found in road-trip-planner

- **Round 1:** four non-Accor hotels left as "to choose", a 14-page PDF with a lot of white space, and the Mount John summit scheduled before its road opens (marked unverified in the plan).
- **Round 2:**
  - The last night was in Meningie, which gave up an available IHG night in Adelaide.
  - It stated wrongly that only Geelong has IHG on the route.
  - It put 195 km of driving on the day of the flight.
  - "5 of 8 requirements met" was confusing.

### Cost (both phases)

| Skill | Minutes, round 1 / round 2 | Subagent tokens, round 1 / round 2 |
|---|---|---|
| road-trip-planner | 19.7 / 13.6 | 257k / 224k |
| road-trip-planner (earlier version) | 15.2 / 8.7 | 238k / 181k |
| travel-agent | 18.9 / 9.0 | 305k / 182k |
| plan-tour-route | 20.8 / 14.2 | 232k / 170k |
| trip-planner | 11.1 / 5.2 | 194k / 138k |
| itinerary-optimizer | 11.5 / 5.1 | 180k / 130k |
| no skill | 13.0 / 7.4 | 192k / 147k |

road-trip-planner is among the slowest and most expensive runs. Its intake has more questions, and it runs scripts.

## Caveats

- **The rubric was written by the skill's author.** 7 of its 16 items grade the questions, which is where this skill was built to be strong. Read the plan-only column for a fairer view of plan quality.
- **One run per skill per round.** Differences of 1–2 points could be noise.
- **road-trip-planner was run twice.** In its first round-1 run, the language question listed a second language the traveller had never used. The intake was changed so the options only offer the traveller's own language, plus "Other". Both road-trip-planner runs were then repeated with this release, and only those runs were graded. The other skills were run once. A grading of round 2 that had started before the repeat was stopped and discarded.
- **Some runs couldn't write their report file.** In round 2, six runs had their write of `report.md` refused by the tool. They returned the report as text, which was saved unchanged. One submission's template heading was replaced with "Trip plan" before grading so it couldn't be identified, in round 1 (covered on the first PDF page) and round 2. PDF metadata was cleared in the blind copies.
- **Several runs reached their web-search limit** partway through, and marked the facts they couldn't check.
- **The task's facts were current in November 2026.** Opening hours, road status and booking rules will change.

## Re-running

Use the prompts in `prompts.md`, and grade blind with `rubric.md`. The road-trip-planner unit tests run with:

```bash
cd plugins/legwise/skills/road-trip-planner/scripts
python3 -m unittest test_verify_trip test_order_stops test_render_report test_choose_nights
```
