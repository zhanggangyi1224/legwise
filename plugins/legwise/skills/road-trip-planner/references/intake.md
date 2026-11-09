# Intake: asking enough before planning

Every question here is one a traveller once had to volunteer after a plan was already built. Asking up front prevents a week of rebuilds. Late answers about hotel brand, daily distance, the number of drivers, seasickness, beaches, a sightseeing-free departure day and output language each forced a new version.

## How to ask

- Use the AskUserQuestion tool. Each call takes 1–4 questions, and each question takes 2–4 options. "Other" is added automatically, so never add your own "Other" option. Headers can be at most 12 characters.
- Write the questions and options in the language the traveller writes in. When that isn't the destination's language, add the place name as local maps show it in brackets.
- Before each round, cross out anything the traveller already said or provided, such as a pasted itinerary, a booking or a ticket. Ask only what is still open. A round with nothing left is skipped.
- Build options from what you know about this trip: real cities on their route, the local currency, sensible distances for the country. Put the option you'd recommend first and mark it "(Recommended)" in the traveller's language. Use `multiSelect: true` only where answers combine, such as interests or things to avoid.
- For a free-form answer like the exact start and end cities, still offer 2–4 likely choices from context. The traveller can type the real answer under "Other". If there is no context to build options from, ask in plain text instead.
- Normally 3–4 rounds, never more than 5. Once the plan exists, ask only about the change at hand.
- After the last round, read back a short summary of the requirements before routing anything. List hard limits separately from preferences. Record the answers in the plan's `preferences` block and its `hard_constraints`.

## Round 0: choosing the destination or route (only if undecided)

Skip this if the traveller already named a route. If they only gave a region, a time window or a feeling ("somewhere scenic for 10 days in December"), shape 2–3 real route options first. One real trip only settled after switching between three routes (Adelaide→Perth, Christchurch→Auckland, Wellington→Auckland). It switched because of a one-way rental fee and a fixed flight, both of which could have been checked before any day-by-day planning.

For each option, research:

- **One-way rental:** cost for those dates, from a real quote. Often the deciding number.
- **Flights:** into the start and out of the end, from where the travellers actually come from and go to. A single daily flight can fix the first day's timing.
- **Total km and longest day:** at the traveller's pace, from a rough route_legs run.
- **Season on these dates:** weather, closures, school holidays, events that fill towns.
- **Hotel brand coverage:** whether the traveller's chosen brand has hotels along the way.
- **Signature sights:** what matches their interests.

Then ask one AskUserQuestion with each route as an option. Each option's `description` gives its position and trade-off in one line, for example "cheapest rental, fewer brand hotels, two 550 km days". Put your recommendation first. Use `preview` to show a short day-by-day outline of each route so the traveller can compare them side by side. Once they pick, continue with Round 1, skipping what the choice already settled.

## Round 1: trip skeleton

| Header | Question | Options to adapt |
|---|---|---|
| Route | Where do you start and finish the drive? | One-way A→B (name real cities) · Loop from A · Not sure yet, suggest one |
| Dates | Which dates, and does the first night start at the arrival city? | Exact dates from context · "Flexible ±1 day" |
| Travellers | Who is travelling? | Adults only · Family with children (ask ages: car seats, walk length, child pricing) · Group of friends · Older travellers or limited mobility |
| Drivers | How many people will drive? | Only one driver · Two sharing · More |
| Licence | What licence does each driver hold? | Full local licence · Full overseas licence in English · Not in English (needs a permit or translation) · Provisional or learner |

This round has five questions, so split it across two AskUserQuestion calls (each call takes four at most). Also ask in this round, or the next if this one is full: do all travellers fly in and out together? Options: same flights both ways · same in, different out · different both ways. Different departures change the last day, car return times and who is in the car.

## Round 2: hotels

| Header | Question | Options to adapt |
|---|---|---|
| Hotel brand | Which hotel brands or loyalty programs should I favour? (multiSelect) | Accor (ALL: Novotel, Mercure, ibis, Pullman…) · Marriott Bonvoy · IHG / Hilton / Hyatt · No preference, motels are fine |
| Brand rule | How strict is that? | As many brand nights as possible, others where the brand has no hotel (Recommended) · Brand only, change the route to fit · Price first |
| Room | What room do you need? | Two beds (twin or 2 queens) · One bed · Two rooms or family room |
| Budget | Hotel budget per night, in the local currency? | Three tiers sized to the country · No limit |

Save the chosen brands as `preferences.hotel_brands`, and record each stay's chain in `stay.brand`. Before promising brand nights, check where the brand really has hotels along the route, using the chain's own site. Where it has none, offer the trade-off as a question, such as one non-brand night that reaches a must-see versus staying on brand.

## Round 3: driving rhythm

| Header | Question | Options to adapt |
|---|---|---|
| Daily km | The most you want to drive in a day? | Values sized to the route, such as ≤300 · ≤400 · ~500 · 500–600 km |
| Pace | How full should the days be? | As many sights as possible, early starts · Balanced · Relaxed, with rest days |
| Base | Move every night, or stay put? | New hotel most nights · Bases of 2–3 nights with day trips · Mix |
| Dark | Driving after dark? | Never after sunset (Recommended) · Short lit town stretches are fine |

With one driver, say so in every long-day warning, and suggest a break every 2 hours.

## Round 4: interests and things to avoid

| Header | Question | Options to adapt |
|---|---|---|
| Interests | What do you most want to see? (multiSelect) | Pick 4 that fit the region: landscapes and lookouts · geothermal, caves or wildlife · culture, history and museums · cities and food |
| Avoid | Anything to avoid? (multiSelect) | Boats or ferries (seasickness) · Beaches · Long or steep walks · Expensive guided tours |
| Tours | Fixed-time tours: | Book ahead for a fixed slot · Decide on the day where walk-up works · Show me the list first |
| Last day | On the day you fly out: | No sightseeing (Recommended) · Sights only if there's time before the flight |

Turn each "avoid" into an `avoid_tag` constraint, and tag every visit place. A "last day" answer of no sightseeing becomes `no_visits_on`.

## Round 5: what's booked and what you deliver

| Header | Question | Options to adapt |
|---|---|---|
| Booked | What's already booked? (multiSelect) | Flights · Rental car · Some hotels · Nothing yet |
| Language | Language for the document? (Replies follow the language they write in.) | The language they're writing in, with local place names (Recommended) · English, if that's different · Other (they type any language). Don't add a language they haven't used: "Other" covers the rest |
| Output | What should the final plan be? | Short phone-friendly Markdown · Detailed PDF · Web page · Summary in chat. Recommend from context: reading on the road suggests phone Markdown, printing or sharing suggests a PDF. Never default to PDF |
| Scope | Which parts should the plan cover? | Only the driving part · Also flights and transfers around it |

Also ask, or infer from earlier answers, whether they want a short or detailed document, and whether any of the seven fixed sections should be left out. Save all of these output choices in the plan's `report` block, which `render_report.py` reads.

Ask for anything booked to be pasted or attached. Booked items are fixed points, so plan around them instead of re-deciding them.

## Questions to ask at the right moment

These aren't intake questions, but ask them when they come up, because each one went wrong once:

- **Before detailed routing:** a real one-way rental quote. One-way fees can make a whole route unaffordable, and one route was abandoned for that reason. Also check the pick-up branch's hours against the flight's arrival time.
- **Before fixing a tour time:** the real slot list. Ask the traveller to paste the booking page's available times rather than assuming a schedule.
- **Before offering alternatives:** ask as an AskUserQuestion with 2–4 concrete options, each with its time and distance effect. Don't write a lettered list in chat.
