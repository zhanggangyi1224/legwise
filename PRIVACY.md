# Privacy policy

Last updated: 9 November 2026

Legwise is an open-source plugin that packages the `road-trip-planner` skill. It has no server, no account and no analytics. This policy covers what its files do. It does not cover Claude or the app you use it in, which have their own policies.

## What it stores

- **Your trip plan.** The plan is a JSON file saved in a folder you choose, and reports (PDF, HTML or Markdown) are written next to it. They stay on your device or in your Claude workspace, and you can delete them at any time.
- **Nothing else.** The plugin keeps no logs, caches or copies of your data.

## What it sends

Only the routing scripts make network requests, and only when you route a plan:

| Service | What it receives | Why |
|---|---|---|
| `nominatim.openstreetmap.org` | Place names from the plan | To look up coordinates |
| `router.project-osrm.org` | Coordinates of the places | To get road distances and drive times |

Each request carries a User-Agent: the value of the `ROAD_TRIP_UA` environment variable, or a generic one if it is unset. Traveller names, booking references, contact details and the rest of the plan are never sent. These services are run by third parties under their own policies:

- [OpenStreetMap Foundation privacy policy](https://osmfoundation.org/wiki/Privacy_Policy) (Nominatim)
- [OSRM demo server](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server)

The checker and the report renderer work offline, and `order_stops.py` and `choose_nights.py` have an `--offline` mode that makes no requests.

## Personal data in your plan

You may paste booking confirmations into the conversation so the plan can record them. The skill tells Claude to record only what the plan needs, such as booking references, and not to repeat emails, phone numbers, addresses or ID numbers. The report renderer refuses to write a report that contains an email address.

## Children

The plugin is not intended for people under 18.

## Contact

Questions or concerns: open an issue at https://github.com/zhanggangyi1224/legwise/issues.
