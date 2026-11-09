# Evaluation report

Two blind comparisons of `road-trip-planner` (this release) against four other travel skills, an earlier version of itself, and a no-skill baseline. Everything needed to check the scores is in this folder.

**Short version:** `road-trip-planner` scored highest in both rounds, and in both the grader said it would hand the traveller this plan. Part of the lead comes from the questions it asks before planning. On plan quality alone it also came first, but narrowly. Version 1.1.0 was tuned to fix weaknesses found on these same two tasks, so read the results as "fixed what the graders found", not as proof of a general lead.

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
| **road-trip-planner** | **7** | **9** | **16** |
| no skill | 5.5 | 8.5 | 14 |
| road-trip-planner (earlier version) | 5 | 8.5 | 13.5 |
| itinerary-optimizer | 5 | 7.5 | 12.5 |
| travel-agent | 4.5 | 8 | 12.5 |
| plan-tour-route | 3.5 | 8 | 11.5 |
| trip-planner | 4 | 7.5 | 11.5 |

The grader would hand the traveller the road-trip-planner plan. It was the only plan to meet every hard rule and also give a booking list with links, book-by dates and buy-on-site items, and its facts checked out where others were wrong. Its weak spot: about 200 km of backtracking over Lindis Pass to win a fifth Accor night. The plan offered a checked alternative without it.

### Round 2: Melbourne → Adelaide over Christmas (short Markdown)

| Skill | Questions /7 | Plan /9 | Total /16 |
|---|---|---|---|
| **road-trip-planner** | **7** | **7.5** | **14.5** |
| no skill | 6.5 | **7.5** | 14 |
| itinerary-optimizer | 6 | **7.5** | 13.5 |
| road-trip-planner (earlier version) | 4.5 | **7.5** | 12 |
| travel-agent | 5 | 7 | 12 |
| trip-planner | 4 | 7 | 11 |
| plan-tour-route | 3.5 | **7.5** | 11 |

The grader would hand the traveller the road-trip-planner plan: the shortest, two IHG nights within every limit, and the only one to catch the new Twelve Apostles booking, with real links and book-by dates. Before sending it, the grader would add the second driver to the rental, warn about fuel on Christmas Day and drop a beach that is closed.

### Combined

| Skill | Total /32 | Plan only /18 |
|---|---|---|
| **road-trip-planner** | **30.5** | **16.5** |
| no skill | 28 | 16 |
| itinerary-optimizer | 26 | 15 |
| road-trip-planner (earlier version) | 25.5 | 16 |
| travel-agent | 24.5 | 15 |
| plan-tour-route | 22.5 | 15.5 |
| trip-planner | 22.5 | 14.5 |

### Weaknesses the graders still found in road-trip-planner

- **Round 1:** about 200 km of backtracking for a fifth Accor night, and a booking table that repeats the same note on every hotel row.
- **Round 2:**
  - The rental item doesn't say to add the second driver.
  - Christmas Day fuel isn't tied to closures.
  - The non-IHG nights aren't explained.
  - It chose an IHG hotel 15 km north of the city without checking the city one fits three.
  - The overview lines had no labels. This has been fixed since: phone lines now read "78 km · Driving 1 h 07 · Sunset 20:45".

### Cost (both phases)

| Skill | Minutes, round 1 / round 2 | Subagent tokens, round 1 / round 2 |
|---|---|---|
| road-trip-planner | 30.4 / 15.8 | 339k / 256k |
| road-trip-planner (earlier version) | 15.2 / 8.7 | 238k / 181k |
| travel-agent | 18.9 / 9.0 | 305k / 182k |
| plan-tour-route | 20.8 / 14.2 | 232k / 170k |
| trip-planner | 11.1 / 5.2 | 194k / 138k |
| itinerary-optimizer | 11.5 / 5.1 | 180k / 130k |
| no skill | 13.0 / 7.4 | 192k / 147k |

road-trip-planner is the slowest and most expensive run. Its intake has more questions, it runs scripts, and it now researches every night's lodging.

## How this version was reached

- **1.0.0 runs** scored 15.5 (round 1) and 14.5 (round 2), the highest totals. But both graders would have handed the traveller a different plan. They found:
  - hotels left as "to choose";
  - a 14-page PDF with a lot of white space;
  - a sight scheduled before its road opened;
  - a last night that gave up an available IHG hotel in the end city;
  - a wrong claim about which towns have IHG;
  - 195 km of driving on the flight day;
  - a confusing "5 of 8 requirements met".
- **1.1.0** fixes each of these (see `CHANGELOG.md`). Then both road-trip-planner runs were repeated, and all seven submissions in each round were graded again from scratch. The tables above are from that second grading.
- **Language question.** Before 1.0.0 was graded, its first round-1 run offered a language the traveller had never used. The intake was changed so the options only offer the traveller's own language plus "Other", and that run was repeated.

## Caveats

- **Tuned on the test.** The 1.1.0 fixes target weaknesses found on these two tasks. Improvement on the same tasks overstates how much it would help on a new trip.
- **The rubric was written by the skill's author.** 7 of its 16 items grade the questions, which is where this skill was built to be strong. Read the plan-only column for a fairer view of plan quality.
- **Grading noise.** Between the two gradings, the six submissions that didn't change moved by up to 1 point. Differences of 1 point or less are noise.
- **One run per skill.** Each other skill was run once per round. The road-trip-planner runs in the tables are its third attempt in each round.
- **Some runs couldn't write their report file.** In round 2, six runs had their write of `report.md` refused by the tool. They returned the report as text, which was saved unchanged. One submission's template heading was replaced with "Trip plan" before grading so it couldn't be identified: in round 1 it was covered on the first PDF page, and in round 2 replaced in the text. PDF metadata was cleared in the blind copies.
- **Several runs reached their web-search limit** partway through, and marked the facts they couldn't check.
- **The task's facts were current in November 2026.** Opening hours, road status and booking rules will change.

## Re-running

Use the prompts in `prompts.md`, and grade blind with `rubric.md`. The road-trip-planner unit tests run with:

```bash
cd plugins/legwise/skills/road-trip-planner/scripts
python3 -m unittest test_verify_trip test_order_stops test_render_report test_choose_nights
```
