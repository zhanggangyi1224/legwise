#!/usr/bin/env python3
"""Render a checked plan as a traveller-facing report in a fixed section order.

    render_report.py trip.json --out trip.pdf
    render_report.py trip.json --out trip.md --lang en --detail brief
    render_report.py trip.json --out trip.html --sections overview,days,bookings

Sections, always in this order: overview, days, bookings, hotels, issues, prep,
sources. Times, distances and sunset come from verify_trip.py, so the report cannot
disagree with the checker. Everything written in words (day titles, stop notes,
tips, the checklist) comes from the plan file. Defaults come from the plan's
`report` block; command-line options override them. Formats: md, html, pdf (pdf
needs reportlab). Refuses to write a report containing an email address.

`--lang` takes any language code. Labels are built in for English; for another
language, put translations of the labels from `--print-labels` in the plan's
`report.labels`, and the renderer warns about any it leaves in English.
"""
import argparse
import copy
import html
import json
import os
import re
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_trip as vt  # noqa: E402

SECTIONS = ["overview", "days", "bookings", "hotels", "issues", "prep", "sources"]

TEXT = {
    "en": {
        "overview": "Overview", "days": "Day by day", "bookings": "Bookings and tickets",
        "hotels": "Hotels", "issues": "Open items", "prep": "Before you go",
        "sources": "Sources",
        "day_head": "Day {i} · {wd} {day} {mon}", "n_days": "{n} days",
        "date": "Date", "route": "Route", "km": "km", "drive": "Driving",
        "sunset": "Sunset", "stay": "Overnight", "time": "Time", "place": "Place",
        "leg": "Drive here", "notes": "Notes", "depart": "depart", "item": "Item",
        "status": "Status", "ref": "Ref", "book_by": "Book by", "terms": "Terms / notes",
        "hotel": "Hotel", "brand": "Brand", "room": "Room", "cost": "Cost",
        "tips": "Tips", "met_count": "{met} of {n} requirements met", "checklist": "Checklist", "packing": "Packing",
        "requirements": "Your requirements", "met": "met", "not_met": "NOT met",
        "to_confirm": "to confirm", "must_fix": "Must fix", "confirm": "To confirm",
        "note": "Worth knowing", "plans": "Backup plans", "decide_by": "decide by", "none": "Nothing open.", "not_ready": "Not prepared yet.",
        "travellers": "travellers", "total": "Total", "longest": "longest day",
        "verdict_fail": "{n} item(s) must be fixed before this plan works.",
        "verdict_unknown": "Everything checked fits. {n} details still need confirming (see Open items).",
        "verdict_pass": "Every check passes.",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                   "Nov", "Dec"],
        "hm": "{h} h {m:02d}", "m_only": "{m} min",
        "st": {"booked": "booked", "pending": "payment pending", "unbooked": "not booked",
               "held": "held", "walk_up": "buy on site", None: "?"},
    },
}

CHECKS = {
    "en": {"timing": "Departure time missing", "leg": "Drive not routed",
           "grounding": "No source yet", "daylight": "Daylight", "hours": "Opening hours",
           "be_by": "Arrive-by time", "fuel": "Fuel range", "breaks": "Long drive without a break",
           "booking": "Booking status", "check_in": "Hotel check-in time", "fact": "Facts to check",
           "lodging": "Lodging", "continuity": "Days don't connect", "dates": "Dates",
           "claimed_km": "Distance differs from source", "leg_speed": "Suspicious drive time",
           "book_by": "Book-by date", "constraints": "Requirements",
           "booking_rule": "Booking or timed entry not checked", "brand": "Non-brand night, reason missing"},
}



def texts(plan, lang):
    """Labels for `lang` as (text, check names, missing keys). Built in for English;
    the plan's report.labels overrides any of them and supplies other languages, with
    English for whatever it leaves out."""
    custom = (plan.get("report") or {}).get("labels") or {}
    t = copy.deepcopy(TEXT.get(lang, TEXT["en"]))
    names = dict(CHECKS.get(lang, CHECKS["en"]))
    names.update(custom.get("checks") or {})
    for key, value in custom.items():
        if key == "st":
            t["st"].update(value)
        elif key != "checks":
            t[key] = value
    missing = []
    if lang not in TEXT:
        missing = [k for k in TEXT["en"] if k not in custom]
        missing += [f"checks.{k}" for k in CHECKS["en"] if k not in (custom.get("checks") or {})]
    return t, names, missing


EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


CJK = r"[\u3040-\u30ff\u4e00-\u9fff]"
THAI = r"[\u0e00-\u0e7f]"


def word_count(text):
    """Words in spaced scripts, plus CJK and kana characters at two per word and Thai
    characters at four per word, since those scripts don't put spaces between words."""
    spaced = re.sub(f"{CJK}|{THAI}", " ", text)
    return (len(re.findall(r"[^\W_]+(?:['’][^\W_]+)*", spaced))
            + len(re.findall(CJK, text)) // 2 + len(re.findall(THAI, text)) // 4)


def day_lengths(blocks):
    """Words per day section (from one h3 to the next h3 or h2)."""
    sizes, current = [], None
    for b in blocks:
        if b[0] == "h3":
            current = [b[1], 0]
            sizes.append(current)
        elif b[0] in ("h2", "h1"):
            current = None
        elif current is not None and b[0] != "break":
            current[1] += word_count(json.dumps(b[1:], ensure_ascii=False))
    return sizes


def fmt_drive(minutes, t):
    minutes = int(round(minutes))
    h, m = divmod(minutes, 60)
    return t["hm"].format(h=h, m=m) if h else t["m_only"].format(m=m)


def label(plan, pid, lang):
    place = plan["places"][pid]
    name = place.get("name", pid)
    local = (place.get("label") or {}).get(lang)
    return f"{local} {name}" if local and local != name else name


def sunset_at(plan, pid, day_date):
    place = plan["places"][pid]
    if place.get("lat") is None:
        return "--"
    _, sunset = vt.sun_times_utc(day_date, place["lat"], place["lon"])
    if sunset is None:
        return "--"
    return sunset.astimezone(vt.ZoneInfo(place["tz"])).strftime("%H:%M")


def build(plan, result, opts):
    lang = opts["lang"]
    t, names, _ = texts(plan, lang)
    full = opts["detail"] == "full"
    days, summaries = plan["days"], result["days"]
    blocks = []

    def day_ref(where):
        def repl(m):
            n = int(m.group(1))
            if not 1 <= n <= len(days):
                return m.group(0)
            dd = date.fromisoformat(days[n - 1]["date"])
            return f"{dd.month}/{dd.day}"
        return re.sub(r"\bD(\d+)\b", repl, where).replace(" stay", "")

    def day_head(i, d):
        dd = date.fromisoformat(d["date"])
        return t["day_head"].format(i=i, wd=t["weekdays"][dd.weekday()], day=dd.day,
                                    month=dd.month, mon=t["months"][dd.month - 1])

    if "overview" in opts["sections"]:
        trip = plan.get("trip", {})
        title = opts.get("title") or trip.get("name") or "Road trip"
        blocks.append(("h1", title))
        first, last = days[0]["date"], days[-1]["date"]
        km = result["metrics"]["total_km"]
        longest = fmt_drive(result["metrics"]["longest_day_drive_min"], t)
        n_trav = trip.get("travellers")
        line = f"{first} → {last} · " + t["n_days"].format(n=len(days))
        if n_trav:
            line += f" · {n_trav} {t['travellers']}"
        line += f" · {t['total']} {km:.0f} {t['km']} · {t['longest']} {longest}"
        blocks.append(("p", line))
        c = result["counts"]
        if c["FAIL"]:
            blocks.append(("p", t["verdict_fail"].format(n=c["FAIL"])))
        elif c["UNKNOWN"]:
            blocks.append(("p", t["verdict_unknown"].format(n=c["UNKNOWN"])))
        else:
            blocks.append(("p", t["verdict_pass"]))
        rows = []
        for i, (d, s) in enumerate(zip(days, summaries), 1):
            start, end = d["stops"][0]["place"], d["stops"][-1]["place"]
            route = d.get("title") or f"{label(plan, start, lang)} → {label(plan, end, lang)}"
            stay = (d.get("stay") or {}).get("name", "—")
            rows.append([day_head(i, d), route, f"{s['km']:.0f}", fmt_drive(s["drive_min"], t),
                         sunset_at(plan, end, date.fromisoformat(d["date"])), stay])
        blocks.append(("table", [t["date"], t["route"], t["km"], t["drive"], t["sunset"],
                                 t["stay"]], rows, [2.2, 4.2, 0.9, 1.6, 1.0, 2.6]))

    if "days" in opts["sections"]:
        if "overview" in opts["sections"]:
            blocks.append(("break",))
        blocks.append(("h2", t["days"]))
        for i, (d, s) in enumerate(zip(days, summaries), 1):
            if i > 1:
                blocks.append(("break",))
            head = day_head(i, d)
            if d.get("title"):
                head += " · " + d["title"]
            blocks.append(("h3", head))
            end = d["stops"][-1]["place"]
            facts = [f"{t['depart']} {d.get('depart', '--')}", f"{s['km']:.0f} {t['km']}",
                     f"{t['drive']} {fmt_drive(s['drive_min'], t)}",
                     f"{t['sunset']} {sunset_at(plan, end, date.fromisoformat(d['date']))}"]
            if d.get("stay"):
                facts.append(f"{t['stay']} {d['stay'].get('name')}")
            blocks.append(("p", " · ".join(facts)))
            if full and d.get("intro"):
                blocks.append(("p", d["intro"]))
            rows = []
            for stop, row in zip(d["stops"], s["stops"]):
                if row["arrive"] is None:
                    when = "--"
                elif stop.get("kind") == "start":
                    when = f"{row['leave']} {t['depart']}"
                elif row["leave"] and row["leave"] != row["arrive"]:
                    when = f"{row['arrive']}–{row['leave']}"
                else:
                    when = row["arrive"]
                leg = ""
                if row.get("leg_km") is not None:
                    leg = f"{row['leg_km']:.0f} {t['km']}\n{fmt_drive(row['leg_min'], t)}"
                note = (stop.get("note") or stop.get("short", "")) if full else stop.get("short", "")
                rows.append([when, label(plan, stop["place"], lang), leg, note])
            widths = [1.7, 3.2, 1.6, 7.0] if full else [1.7, 4.5, 1.6, 5.7]
            blocks.append(("table", [t["time"], t["place"], t["leg"], t["notes"]], rows, widths))
            if full and d.get("tips"):
                blocks.append(("h4", t["tips"]))
                blocks.append(("bullets", list(d["tips"])))

    if "bookings" in opts["sections"]:
        blocks.append(("break",))
        blocks.append(("h2", t["bookings"]))
        items = [dict(b) for b in plan.get("bookings") or []]
        if "hotels" not in opts["sections"]:
            items += [{"date": d["date"], "what": d["stay"].get("name", ""), **d["stay"]}
                      for d in days if d.get("stay")]
        done = ("booked", "walk_up")
        items.sort(key=lambda b: (b.get("status") in done,
                                  b.get("book_by") or b.get("date") or "", b.get("date", "")))
        rows = []
        for b in items:
            where = " · ".join(x for x in (b.get("cancel", ""), b.get("source", "")) if x)
            rows.append([b.get("book_by", ""), b.get("what", ""), b.get("date", ""),
                         t["st"].get(b.get("status"), b.get("status")), b.get("ref", ""), where])
        if rows:
            blocks.append(("table", [t["book_by"], t["item"], t["date"], t["status"], t["ref"],
                                     t["terms"]], rows, [1.6, 4.0, 1.6, 1.3, 1.6, 4.3]))
        else:
            blocks.append(("p", t["none"]))

    if "hotels" in opts["sections"]:
        blocks.append(("h2", t["hotels"]))
        rows = []
        for d in days:
            stay = d.get("stay")
            if stay:
                cost = stay.get("cost")
                cost = "" if cost is None else f"{stay.get('currency', '')} {cost:,.0f}".strip()
                terms = " · ".join(x for x in (stay.get("ref", ""), stay.get("cancel", ""),
                                               stay.get("source", "")) if x)
                rows.append([d["date"], stay.get("name", ""), stay.get("brand") or "—",
                             stay.get("room", ""), cost,
                             t["st"].get(stay.get("status"), stay.get("status")), terms])
        blocks.append(("table", [t["date"], t["hotel"], t["brand"], t["room"], t["cost"],
                                 t["status"], t["terms"]], rows,
                       [1.6, 3.6, 1.2, 2.2, 1.2, 1.2, 3.4]))

    if "issues" in opts["sections"]:
        blocks.append(("h2", t["issues"]))
        cons = result["constraints"]
        if cons:
            mark = {"PASS": t["met"], "FAIL": t["not_met"], "UNKNOWN": t["to_confirm"]}
            blocks.append(("h4", t["requirements"]))
            shown = cons if full else [c for c in cons if c["status"] != "PASS"]
            lines = [f"[{mark[c['status']]}] {c['nl']}" for c in shown]
            if not full:
                met = sum(c["status"] == "PASS" for c in cons)
                lines.insert(0, t["met_count"].format(met=met, n=len(cons)))
            blocks.append(("bullets", lines))
        plans = plan.get("contingencies") or []
        if plans:
            blocks.append(("h4", t["plans"]))
            lines = []
            for c in plans:
                head = c.get("risk", "")
                if c.get("decide_by"):
                    head += f" ({t['decide_by']} {c['decide_by']})"
                body = " · ".join(x for x in (c.get("trigger", ""), c.get("plan", ""),
                                               c.get("source", "")) if x)
                lines.append(f"{head}: {body}" if body else head)
            blocks.append(("bullets", lines))
        written = plan.get("report", {}).get("open_items")
        if written:
            blocks.append(("bullets", list(written)))
        else:
            any_item = False
            levels = (("FAIL", t["must_fix"]), ("UNKNOWN", t["confirm"]), ("WARN", t["note"]))
            for level, head in levels if full else levels[:2]:
                found = [f for f in result["findings"]
                         if f["level"] == level and f["check"] != "constraint"]
                if not found:
                    continue
                any_item = True
                groups = {}
                for f in found:
                    if level == "FAIL":
                        text = f"{day_ref(f['where'])}: {f['message']}"
                    elif f["check"] == "fact":
                        text = f["message"].split(": ", 1)[-1]
                    else:
                        text = day_ref(f["where"])
                    groups.setdefault(f["check"], []).append(text)
                blocks.append(("h4", head))
                blocks.append(("bullets", [f"{names.get(k, k)}: " + "; ".join(v)
                                           for k, v in groups.items()]))
            if not any_item and not cons:
                blocks.append(("p", t["none"]))

    if "prep" in opts["sections"]:
        blocks.append(("h2", t["prep"]))
        prep = plan.get("prep") or {}
        if not prep:
            blocks.append(("p", t["not_ready"]))
        for key in ("checklist", "packing"):
            if prep.get(key):
                blocks.append(("h4", t[key]))
                blocks.append(("bullets", list(prep[key])))

    if "sources" in opts["sections"]:
        blocks.append(("h2", t["sources"]))
        seen, lines = set(), []
        for f in plan.get("facts") or []:
            src = f.get("source")
            if src and src not in seen:
                seen.add(src)
                lines.append(f"{src} ({f.get('checked', '')})" if full else src)
        blocks.append(("bullets", lines) if lines else ("p", t["none"]))
    return blocks


def to_markdown(blocks, layout="print"):
    """layout "phone" turns every table into a list, so nothing scrolls sideways."""
    out = []
    for b in blocks:
        kind = b[0]
        if kind in ("h1", "h2", "h3", "h4"):
            out.append("#" * int(kind[1]) + " " + b[1])
        elif kind == "p":
            out.append(b[1])
        elif kind == "bullets":
            out.append("\n".join(f"- {x}" for x in b[1]))
        elif kind == "table" and layout == "phone":
            rows = []
            for r in b[2]:
                rest = [str(x).replace("\n", " ") for x in r[1:] if str(x).strip()]
                rows.append(f"- **{r[0]}** " + " · ".join(rest) if r[0] else "- " + " · ".join(rest))
            out.append("\n".join(rows))
        elif kind == "table":
            def cell(x):
                return str(x).replace("|", "/").replace("\n", " ")
            lines = ["| " + " | ".join(b[1]) + " |", "|" + "---|" * len(b[1])]
            lines += ["| " + " | ".join(cell(x) for x in r) + " |" for r in b[2]]
            out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


CSS = """
:root{--ink:#1d2430;--muted:#5b6575;--line:#d9dee6;--head:#1f4e5f;--band:#eef3f6;--bg:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--ink:#e6e9ee;--muted:#a3adbb;
--line:#3a4250;--head:#8cc7d9;--band:#222a33;--bg:#15191f;color-scheme:dark}}
:root[data-theme=dark]{--ink:#e6e9ee;--muted:#a3adbb;--line:#3a4250;--head:#8cc7d9;
--band:#222a33;--bg:#15191f;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:14px/1.55 -apple-system,"PingFang SC",
"Microsoft YaHei",sans-serif;max-width:980px;margin:0 auto;padding:24px 16px}
h1{color:var(--head);margin:.2em 0}h2{color:var(--head);border-bottom:2px solid var(--line);
padding-bottom:4px;margin-top:2em}h3{background:var(--band);padding:8px 10px;border-radius:6px}
h4{margin:1.2em 0 .3em}.t{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:.6em 0}
th,td{border:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}
th{background:var(--band)}td{white-space:pre-line}p{margin:.4em 0}
@media print{h3{break-before:page}body{max-width:none}}
"""


def to_html(blocks, title):
    esc = html.escape
    out = [f"<title>{esc(title)}</title><style>{CSS}</style>"]
    for b in blocks:
        kind = b[0]
        if kind in ("h1", "h2", "h3", "h4"):
            out.append(f"<{kind}>{esc(b[1])}</{kind}>")
        elif kind == "p":
            out.append(f"<p>{esc(b[1])}</p>")
        elif kind == "bullets":
            out.append("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in b[1]) + "</ul>")
        elif kind == "table":
            head = "".join(f"<th>{esc(h)}</th>" for h in b[1])
            body = "".join("<tr>" + "".join(f"<td>{esc(str(x))}</td>" for x in r) + "</tr>"
                           for r in b[2])
            out.append(f'<div class="t"><table><tr>{head}</tr>{body}</table></div>')
    return "<!doctype html><meta charset=utf-8>" + "\n".join(out)


ARIAL_UNICODE = ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf",) * 2 + (0,)
SD_GOTHIC = ("/System/Library/Fonts/AppleSDGothicNeo.ttc",) * 2 + (0,)
HEITI = ("/System/Library/Fonts/STHeiti Light.ttc", "/System/Library/Fonts/STHeiti Medium.ttc", 1)
NOTO_CJK = ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1)
SCRIPTS = {"kana": r"[\u3040-\u30ff]", "hangul": r"[\uac00-\ud7af]", "han": r"[\u4e00-\u9fff]"}
CID_FONTS = {"kana": "HeiseiKakuGo-W5", "hangul": "HYGothic-Medium", "han": "STSong-Light"}


def east_asian_script(text):
    """The East Asian script the text uses, if any: kana, hangul or han."""
    for name, pattern in SCRIPTS.items():
        if re.search(pattern, text):
            return name
    return None


def register_font(script=None, custom=None):
    """Register (regular, bold) fonts that cover the report's script. The plan's
    report.font ({"regular": path, "bold": path}) comes first."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = [ARIAL_UNICODE, NOTO_CJK, HEITI]
    if script == "hangul":
        candidates.insert(0, SD_GOTHIC)
    if custom and custom.get("regular"):
        candidates.insert(0, (custom["regular"], custom.get("bold") or custom["regular"],
                              custom.get("index", 0)))
    for regular, bold, index in candidates:
        if os.path.exists(regular) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont("R", regular, subfontIndex=index))
                pdfmetrics.registerFont(TTFont("B", bold, subfontIndex=index))
                return "R", "B"
            except Exception:  # noqa: BLE001 - try the next font
                continue
    if script:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont(CID_FONTS[script]))
        return CID_FONTS[script], CID_FONTS[script]
    return "Helvetica", "Helvetica-Bold"


def to_pdf(blocks, path, title, font=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)
    script = east_asian_script(json.dumps(blocks, ensure_ascii=False))
    regular, bold = register_font(script, font)
    wrap = "CJK" if script in ("han", "kana") else None
    base = dict(fontName=regular, fontSize=9, leading=12.5, wordWrap=wrap)
    st = {"p": ParagraphStyle("p", **base, spaceAfter=3),
          "cell": ParagraphStyle("c", **{**base, "fontSize": 8.3, "leading": 11}),
          "th": ParagraphStyle("th", **{**base, "fontName": bold, "fontSize": 8.3, "leading": 11}),
          "h1": ParagraphStyle("h1", **{**base, "fontName": bold, "fontSize": 18, "leading": 23,
                                        "textColor": colors.HexColor("#1f4e5f"), "spaceAfter": 6}),
          "h2": ParagraphStyle("h2", **{**base, "fontName": bold, "fontSize": 13.5, "leading": 18,
                                        "textColor": colors.HexColor("#1f4e5f"),
                                        "spaceBefore": 8, "spaceAfter": 4}),
          "h3": ParagraphStyle("h3", **{**base, "fontName": bold, "fontSize": 11.5, "leading": 15,
                                        "textColor": colors.white, "backColor": colors.HexColor("#1f4e5f"),
                                        "borderPadding": (4, 5, 4, 5), "spaceBefore": 4,
                                        "spaceAfter": 7}),
          "h4": ParagraphStyle("h4", **{**base, "fontName": bold, "fontSize": 9.5,
                                        "spaceBefore": 5, "spaceAfter": 2})}
    width = A4[0] - 30 * mm

    def para(text, style):
        return Paragraph(html.escape(str(text)).replace("\n", "<br/>"), st[style])

    story = []
    for b in blocks:
        kind = b[0]
        if kind == "break":
            story.append(PageBreak())
        elif kind in ("h1", "h2", "h3", "h4", "p"):
            story.append(para(b[1], kind))
        elif kind == "bullets":
            for x in b[1]:
                story.append(Paragraph("• " + html.escape(str(x)), st["p"]))
        elif kind == "table":
            weights = b[3]
            cols = [width * w / sum(weights) for w in weights]
            data = [[para(h, "th") for h in b[1]]] + [[para(x, "cell") for x in r] for r in b[2]]
            table = Table(data, colWidths=cols, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3edf1")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c5ced8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fa")])]))
            story += [table, Spacer(1, 5)]

    def footer(canvas, doc):
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(colors.HexColor("#7a8594"))
        canvas.drawCentredString(A4[0] / 2, 9 * mm, f"{title} · {doc.page}")

    SimpleDocTemplate(path, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                      topMargin=14 * mm, bottomMargin=16 * mm, title=title).build(
        story, onFirstPage=footer, onLaterPages=footer)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan", nargs="?")
    parser.add_argument("--out")
    parser.add_argument("--format", choices=["md", "html", "pdf"])
    parser.add_argument("--lang", help="any language code; labels are built in for "
                        + " and ".join(sorted(TEXT)) + ", others come from report.labels")
    parser.add_argument("--print-labels", action="store_true",
                        help="print the English labels as JSON, to translate into report.labels")
    parser.add_argument("--sections", help="comma list from: " + ",".join(SECTIONS))
    parser.add_argument("--detail", choices=["full", "brief"])
    parser.add_argument("--layout", choices=["phone", "print"],
                        help="md only: phone turns tables into lists (default for md)")
    parser.add_argument("--title")
    parser.add_argument("--today", help="YYYY-MM-DD, for book-by checks (default: today)")
    args = parser.parse_args()
    if args.print_labels:
        labels = {k: v for k, v in TEXT["en"].items() if k != "st"}
        labels["st"] = {k: v for k, v in TEXT["en"]["st"].items() if k}
        labels["checks"] = CHECKS["en"]
        print(json.dumps(labels, ensure_ascii=False, indent=2))
        return 0
    if not args.plan or not args.out:
        parser.error("a plan file and --out are required")
    with open(args.plan, encoding="utf-8") as handle:
        plan = json.load(handle)
    prefs = plan.get("report") or {}
    fmt = args.format or os.path.splitext(args.out)[1].lstrip(".") or prefs.get("format", "md")
    if fmt not in ("md", "html", "pdf"):
        parser.error(f"unknown format {fmt!r}")
    sections = args.sections.split(",") if args.sections else prefs.get("sections", SECTIONS)
    unknown = [s for s in sections if s not in SECTIONS]
    if unknown:
        parser.error(f"unknown sections {unknown}; choose from {SECTIONS}")
    opts = {"lang": args.lang or prefs.get("lang", "en"),
            "detail": args.detail or prefs.get("detail", "full"),
            "sections": [s for s in SECTIONS if s in sections],
            "title": args.title or prefs.get("title"),
            "layout": args.layout or prefs.get("layout") or ("phone" if fmt == "md" else "print")}
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    try:
        result = vt.Checker(plan, today).run()
    except vt.PlanError as exc:
        print(f"INVALID PLAN: {exc}", file=sys.stderr)
        return 3
    missing = texts(plan, opts["lang"])[2]
    if missing:
        print(f"WARN: no built-in labels for {opts['lang']!r}; {len(missing)} labels are in "
              f"English: {', '.join(missing[:8])}{' ...' if len(missing) > 8 else ''}. Translate "
              "the output of --print-labels into the plan's report.labels.", file=sys.stderr)
    blocks = build(plan, result, opts)
    flat = json.dumps(blocks, ensure_ascii=False)
    if EMAIL.search(flat):
        print("REFUSED: the report would contain an email address; remove it from the plan",
              file=sys.stderr)
        return 5
    if opts["layout"] == "phone":
        budget = prefs.get("max_words_per_day", 200)
        for head, words in day_lengths(blocks):
            if words > budget:
                print(f"WARN: {head} is about {words} words; phone budget is {budget}. "
                      "Shorten the notes (use `short`) rather than dropping facts.", file=sys.stderr)
        total = word_count(json.dumps(blocks, ensure_ascii=False))
        limit = prefs.get("max_words_total", 1600)
        if total > limit:
            print(f"WARN: report is about {total} words; phone budget is {limit}. Use "
                  "--detail brief, drop sections the traveller doesn't need, or set "
                  "report.open_items to a short hand-written list.", file=sys.stderr)
    title = opts["title"] or plan.get("trip", {}).get("name") or "Road trip"
    if fmt == "md":
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(to_markdown(blocks, opts["layout"]))
    elif fmt == "html":
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(to_html(blocks, title))
    else:
        to_pdf(blocks, args.out, title, prefs.get("font"))
    print(f"wrote {args.out} ({fmt}, {opts['lang']}, {opts['detail']}, "
          f"sections: {','.join(opts['sections'])}; verdict {result['verdict']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
