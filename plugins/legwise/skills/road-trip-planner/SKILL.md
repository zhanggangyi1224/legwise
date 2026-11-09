---
name: road-trip-planner
description: Plan, check or repair a multi-day road trip using recorded constraints and a deterministic checker for drive times, sunset cutoffs, fuel range, opening hours, time zones, lodging and bookings. Starts with a structured intake that asks the traveller, in multiple-choice rounds, about route, drivers, hotel brand or loyalty program, room and budget, daily distance, pace, interests and things to avoid. It then keeps the plan updated as bookings are pasted in. Use this whenever the user wants to plan a road trip or self-drive holiday, sanity-check or fix an existing driving itinerary (including a PDF or spreadsheet), ask whether a driving day is realistic, compare route options, or adjust a trip already planned, even if they don't say "road trip" (self-drive, driving from X to Y over N days, campervan or rental car routes). Not for trips with no driving, or for single-journey directions.
---

# Road Trip Planner

Produce a driving plan that has been checked by a script, with every requirement and real-world fact traceable. A plausible-sounding itinerary is the failure this skill exists to prevent: on long drives, one wrong distance or closed fuel stop can strand people after dark.

## Why the workflow looks like this

The method comes from a neuro-symbolic travel planning agent, and these lessons shape the steps below:

- **Most errors start at translation.** Getting the traveller's words into exact constraints matters more than clever planning, so requirements get written down and read back first.
- **A checker that doesn't depend on the model catches what the model misses.** You judge what is worth doing. The script judges whether it fits.
- **Empty data must not count as a pass.** Checks return PASS, FAIL or UNKNOWN. Report UNKNOWN as unknown, never as fine.
- **Blind retries rarely fix anything.** Repairs target a specific failure and change as little as possible.
- **Edits must not regress.** An edit stays only if nothing got worse.
- **Passing the checker isn't the goal.** Stricter graders close loopholes, and reality is the strictest. Never tweak a number, set `night_ok` or mark a fact verified just to turn a check green.

## Workflow

Scripts are in `scripts/` next to this file (`route_legs.py`, `order_stops.py`, `choose_nights.py`, `verify_trip.py`, `render_report.py`), and need only standard Python. Read `references/plan-format.md` before writing a plan file. Keep the plan as `trip.json` in the user's trip folder, or in a scratch directory if they don't want files there.

### 1. Capture the requirements

Extract what the user has already said or provided. If they gave you an itinerary, import it as written, including its stated distances as `claimed_km`, so that its errors surface instead of being quietly corrected.

Then ask for what's still missing. Read `references/intake.md` and follow its rounds with the AskUserQuestion tool. If the destination or route isn't decided, start with its Round 0: 2–3 researched route options, each with its trade-off. The other rounds cover route and dates, drivers and licences, hotel brand, room and budget, daily distance and pace, interests and things to avoid, what is already booked, and the output language and format. Skip any question already answered. Each late answer in a real trip, such as hotel brand, seasickness or the departure day, cost a full rebuild, so asking a few more questions up front is cheaper than guessing.

Record each requirement as a typed constraint, with the user's own words in `nl`, and keep the remaining answers in `preferences`. Read the list back in plain language before planning on it. Use `manual` for anything the types can't express. Separate true requirements from preferences, since only requirements belong in `hard_constraints`.

### 2. Gather facts from sources

Don't plan from memory on anything that can change or that you can look up:

- **Distances and times:** run `route_legs.py trip.json`. It uses OpenStreetMap services and sends only place names and coordinates. If the router's path isn't the intended road, add the waypoint as a stop. A `leg_speed` warning usually means a bad map point, so fix the coordinates and re-route with `--force` rather than accepting the time.
- **Visit order:** for any day with three or more sights, run `order_stops.py trip.json --day N`. It suggests the order with the least driving and keeps fixed points in place: start, hotel, and any stop with `be_by` or `"fixed": true`. If the order changes, save it with `--write trip_vN.json`, re-route, and test it with the checker against the previous version. Driving time isn't the only cost, since opening hours, a geyser at 10:15 or sunset can outweigh a few minutes. Keep the checker's verdict over the shorter order.
- **Fuel:** list every fuel stop on remote stretches, with hours, and mark stops with `refuel`. Get the real range for the vehicle class.
- **Hours and closures:** search for opening hours, seasonal closures, road conditions and permits, and record each with its source and date. For every headline sight, also search for new booking rules in the travel year, such as timed entry, booked parking or new fees. Search for "<sight> booking required <year>", not just its hours. Such rules change without notice: one major coastal lookout started requiring bookings only a month before a test trip. Don't schedule a sight whose hours you couldn't confirm before 09:00 or after 17:00: summit roads, gardens and visitor centres often open at 10:00. The checker points out such visits.
- **These exact dates:** search for what is happening on the route on the travel dates, not just in general: events that fill towns, fuel or supply disruptions, roadworks, and school or public holidays. If an imported itinerary was framed around a season or month, retest its climate and seasonal claims against the real dates.
- **Fixed times:** don't invent flight or ferry times. Use the traveller's ticket, or a cited schedule marked as an assumption. After an international landing, allow 60–90 minutes for immigration, biosecurity and the rental counter before the car moves. Before a departure, allow the airline's check-in time plus the car return.
- **Road risks and backup plans:** for every key road on the route, check its official closure page or bulletins for current problems, such as slips, convoys or roadworks, and for seasonal risks like snow, flooding or fire. When one could break the plan, build a backup route as its own plan file (`trip_vN_B.json`) and check it with the checker like the main plan. Add a plan C if the road could close mid-trip. Record each backup in `contingencies` with the risk, the trigger to watch, a `decide_by` date, the plan and the source. Advise holding cancellable rooms on the backup route until that date. A dated A/B choice is worth more than a warning to "check before you go".
- **Brand hotels and overnight towns:** when the traveller wants a brand, list every one of its hotels within about 30 km of any reasonable route, using the chain's own site. Search the start and end cities as well as every town in between, and record a town with no brand hotel as a fact with its source. A test run claimed a brand had only one hotel on the route and so missed one in the end city. Add each one to the plan's `overnight_candidates`, along with the other towns that could work for a night (with `refuel: true` where there's fuel). Then run `choose_nights.py trip.json`. It tries every arrangement of nights and ranks those within the daily limits by brand nights, then by the least driving on a flight day, then by the shortest longest day. It lists the towns that have no brand candidate: look each one up before accepting the result. Save the best with `--write`, re-route it, and check it. Never rule out a brand hotel by guessing. The script also lists **near misses**: arrangements with more brand nights that break a limit by up to 10%. Offer the best near miss to the traveller as a choice (for example, "a second IHG night if one day is 4 h 04 instead of 4 h"), and don't pick it for them.
- **Name every night's lodging:** each `stay` names a real place (or two alternatives) from a source you read, with that place's own page as `source`. Never leave a night as "motel or apartment" or "to choose". A brand's search page isn't a source for a non-brand motel. The checker flags unnamed stays and two stays sharing one link.
- **The night before a flight:** sleep within about 90 minutes' drive of the airport, so the flight day has little driving. The checker warns when a flight day has more; change the overnight town unless the traveller has agreed to the drive.
- **Local rules:** check rental restrictions on the route, one-way fees, border and quarantine rules, and local clock time. Record each in `facts`.

- **Bookings, meals and preparation:** read `references/prep-and-bookings.md`. Put every item that needs booking in the plan's `bookings` block with an evidence-based `book_by` date, so the checker flags anything overdue or with payment not yet confirmed. Name a real lunch stop for each long driving day. Build the pre-departure checklist and packing list from what this itinerary actually contains.

If you can't verify something, leave it unverified. The plan can still go ahead, with the gap visible.

### 3. Check the plan

```bash
python3 scripts/verify_trip.py trip.json
```

Exit code 0 is PASS, 1 FAIL, 2 UNVERIFIED and 3 an invalid file. Read every finding. The script supplies sunrise and sunset for each stop's date and location, so don't estimate them.

### 4. Repair one failure at a time

For each FAIL, work out why it fails and pick the smallest real-world change: leave earlier, cut or move a stop, change the overnight town. Save it as a new file and test it against the previous one:

```bash
python3 scripts/verify_trip.py trip_v2.json --baseline trip.json
```

Keep the edit only if it's accepted. A rejection names what regressed, so use that to choose a different fix, not to retry the same one. When the user asked for a change, add `--user-requested`: it needn't improve a metric, but it still can't regress anything. When an edit adds a new stop or hotel, add `--allow-new-unknowns`, then research the unknowns it lists.

If no edit fixes a failure, the trip doesn't fit as specified. Say so and offer the real trade-offs, such as adding a day or dropping a stop, rather than loosening the rule yourself.

### 5. Report

The written plan always comes from `render_report.py`, so every version has the same sections in the same order, and its times and distances can't drift from the checker:

```bash
python3 scripts/render_report.py trip.json --out trip_v3_<Label>.pdf
```

The fixed order is: overview → day by day → bookings and tickets → hotels → open items → before you go → sources. What changes with the traveller's wishes is set in the plan's `report` block, from intake Round 5, or with command-line options:

- `lang`: any language code, set to the traveller's choice. Labels are built in for English (`en`). For any other language, run `render_report.py --print-labels`, translate the values (keep the `{placeholders}`), and save them as `report.labels`; the renderer warns about any label it had to leave in English, so don't deliver while that warning remains. `report.labels` can also override single English labels. Place names show the local label plus the map name. If a PDF in a non-Latin script shows empty boxes, set `report.font` to a font that covers it (`{"regular": path, "bold": path}`); right-to-left scripts render better as HTML or Markdown.
- `format`: `pdf`, `html` or `md`. It's also read from the `--out` file extension.
- `detail`: `full` uses each stop's `note`, the day's `intro` and its `tips`; `brief` uses `short`. A detailed report needs real content: for each main stop, a `note` of two to four sentences saying what to do there, how long it takes, any booking or cost, and one practical tip; an `intro` and two or three `tips` for each day.
- `layout` (Markdown only): `phone`, the default for Markdown, turns tables into lists so nothing scrolls sideways. `print` keeps tables.

When the traveller asks for something short, set `detail: brief` and `layout: phone`, drop sections they don't need, and keep `report.open_items` to at most 6 one-line items. The renderer's length warnings (`max_words_per_day`, default 200; `max_words_total`, default 1600) are then hard limits: shorten the `short` notes and open items, re-render, and don't deliver while any length warning remains. Cut text, not facts. A long report fails a traveller who asked for a short one, however good its content.
- `sections`: any subset of the seven, still in the fixed order.

Write the words yourself in the plan, in the traveller's language: day `title`, `intro` and `tips`, stop `note` and `short`, place `label`, `prep.checklist`, `prep.packing`, and optionally `report.open_items` to replace the auto-grouped open items. The script refuses to write a report containing an email address. Keep phone numbers, ID numbers and dates of birth out of the plan too. If the traveller asks for something the fixed sections can't hold, add it to the plan's text fields rather than hand-building a separate document. If they want a different look, change the renderer once so every later version keeps it.

In chat, lead with the verdict and what the user needs to decide or do next. Then include:

1. **Verdict** in plain words, with the counts. "Unverified" means checked as far as the known facts allow.
2. **Problems found**, most serious first, each with the fix made or the choice they need to make.
3. **Timeline** per day: depart, stops, arrive, sunset, km and hours, plus the lunch stop on long days.
4. **Book or confirm next**, ordered by `book_by` date, each with its official link. Also note which items are sold on site.
5. **Still unknown**, and how to find out each item.
6. **Before you go:** the tailored pre-departure checklist and packing notes, in the full document. Keep them short in chat.

The reader is a traveller, so translate the checker's output: say what is wrong and what to do, and leave out finding counts, check names and terms like "UNKNOWN" or "baseline". Show `claimed_km` disagreements as a comparison of the two figures. Write in the language the traveller chose, keeping place names recognisable for navigation (add the local name when writing in another language).

## What the checker can't tell you

Say so when it matters. It doesn't know live road closures, bushfire or flood conditions, whether a place is actually worth visiting, or how tired the driver will be. Its drive times come from a router plus a buffer, and sunset times are computed estimates. For remote routes, tell the user to check the official road conditions service shortly before leaving.

## Working with the traveller over many changes

Real trips go through dozens of versions: routes change, bookings arrive one by one, sights come and go. These habits kept one such trip (40+ versions) safe:

- **Version, never overwrite.** Save each change as a new plan, such as `trip_v12_<Label>.json`, and a new document whose name says what changed. Keep every earlier file, since the traveller may want to go back.
- **Change only what was asked.** "Remove the boat trip" means remove that one stop and re-time the day. It does not mean redesign the day. If the change leaves a gap, offer fillers as a question, and don't add them unasked.
- **Offer choices as questions.** When there are alternatives, such as a replacement sight, an overnight town or a non-brand night, use AskUserQuestion with 2–4 concrete options. Give each option its time and distance effect, with your recommendation first.
- **Bookings are fixed points.** When the traveller pastes a confirmation, record the reference number, date and time, room and beds, price and currency, whether it's paid or due on arrival, the cancellation terms, and check-in or check-out times. Then check it against the plan (date, place, time) and rebuild the document. Point out anything not final, such as payment marked "Pending", a missing hotel name or a time that clashes. Once something is booked, don't question it again.
- **Fixed-time tours:** use the real slot list from the booking page, and set `be_by` to the check-in time, not the tour start. Say whether walk-up tickets exist and cite the source.
- **Don't over-cut.** A must-avoid rule removes only what breaks it. Keep the part of a sight that fits, such as a short out-and-back section of a longer walk, rather than dropping the whole sight.
- **Never invent names.** Every sight, cave, lookout or venue you name needs a source you have actually read. A plausible made-up name is worse than "unknown".
- **Respect scope and dismissals.** If the traveller says to leave something out, such as flights before the trip or a transit question, stop listing it. Don't raise again a question they've answered or waved away.
- **Read-only on money.** Look up prices and availability, but never book, pay or enter personal details for the traveller. They book, and paste the result back. For insurance, give a factual comparison of what policies cover, and say you're not a licensed adviser.
- **Privacy.** Booking pastes and tickets often contain email addresses, phone numbers, home addresses, ID or passport numbers and dates of birth. Never repeat these in replies or documents. A booking reference, a name and a price are enough.
- **Language is the traveller's choice.** Reply in the language they write in, and switch only when they ask. Write documents in the language they chose at intake, which can be any language; never pick one for them. When the document's language isn't the local one, keep each place name in its local form too, so it works in a navigation app.
