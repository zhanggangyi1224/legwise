# Bookings, meals and preparation

Read this once the route has passed the checker. These are the parts of a trip that aren't about driving, but they can still go wrong because of the drive.

## 1. Booking tracker with book-by dates

List everything that needs action in the plan's `bookings` block. The checker fails an item whose book-by date has passed and isn't booked, warns 7 days ahead, and warns on a payment that isn't confirmed.

```json
"bookings": [
  {"id": "k_caves", "what": "Cave tour 12:00 + second cave 13:30, 2 adults", "place": "caves",
   "date": "2027-03-08", "book_by": "2027-02-20", "status": "booked", "ref": "#EXAMPLE1",
   "source": "https://example.com/caves", "cancel": "changes until 24 h before"},
  {"id": "k_tour", "what": "Guided tour 15:00", "place": "tour", "date": "2027-03-10",
   "book_by": "2027-03-01", "status": "pending", "ref": "#EXAMPLE2"},
  {"id": "k_park", "what": "Thermal park entry", "date": "2026-11-30", "status": "walk_up",
   "source": "official site says tickets at the gate"}
]
```

`status` is one of `unbooked`, `pending` (ordered, payment not confirmed), `booked` or `walk_up` (sold on the day, with a source saying so).

Work out each `book_by` from evidence, not a general rule:

- **Rental car:** the free-cancellation deadline and the price trend. One-way fees decide the route, so quote early.
- **Hotels:** the date free cancellation ends. For non-refundable rates, book only once the route is settled.
- **Fixed-session tours:** how far ahead slots sell out in that season (from the operator, or the booking page showing slots already gone). Also the operator's change and cancel window.
- **Ferries and permits:** the operator's release date and peak-season notes.
- **Anything sold on site:** mark it `walk_up` and cite the source. If online is cheaper or the queue is long, say so. One tower was A$5 cheaper online, and one thermal park had a long queue at 10am.

In the report, list open items by `book_by`, earliest first, with the official link. Never book or pay yourself.

## 2. Meals on driving days

- **Long days (5 h or more of driving):** name a real lunch stop on the route for each day, with its hours from a source. Remote stretches can have 200 km or more without food, and places shut early or close on certain weekdays, so check the actual weekday.
- **Breakfast before early starts:** if the hotel breakfast opens after departure time, say so and suggest buying food the night before.
- **Dinner on late arrivals:** check that something near the hotel is still open at arrival time. Small towns close kitchens around 20:00.
- **Dietary needs from intake:** filter by them, and name the place rather than "find a café".
- Name places only from sources you have read. If you can't verify one, write the town and "buy food here" instead of a made-up name.

## 3. Pre-departure checklist (self-drive)

Tailor this to the trip, dropping lines that don't apply and adding the trip's own:

- **Licence:** full or provisional, whether it's in English, and whether an international permit or translation is needed. Every driver must be named on the rental contract.
- **Rental:** pick-up branch hours against the arrival time, the credit card in the driver's name, the excess level and what's excluded (unsealed roads, ferries, between islands). The fuel policy and return time.
- **Roads:** toll roads and how to pay them, the official road-closure service for the route, seasonal closures and chains. Offline maps downloaded for areas with no signal.
- **Insurance:** whether each traveller's policy covers the whole trip, including different start and end countries, the rental excess and activities like caving. Give a factual comparison only.
- **Money:** places that take cards only, and fuel stations that are pay-at-pump or unattended at night.
- **Phone:** eSIM or roaming plan, and a car charger and mount.
- **Documents:** booking references in one offline list, without personal ID numbers.
- **Emergency:** the local emergency number, each insurer's emergency line and the rental company's breakdown line.

## 4. Packing for the route

Pack for what the itinerary actually contains, not a generic list. For example: shoes with grip for caves and wet tracks, a warm layer for caves and alpine passes, sun protection where UV is high, a swimsuit only if a hot pool is on the plan, and motion-sickness tablets if anyone gets carsick on winding roads. A cooler bag and water are useful on remote stretches. Note any rules on where you are going, such as no tripods or backpacks inside some caves, or biosecurity rules on food at borders.
