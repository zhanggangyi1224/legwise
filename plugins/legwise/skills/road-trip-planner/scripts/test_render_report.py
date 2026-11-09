#!/usr/bin/env python3
"""Tests for render_report.py: fixed order, user-chosen options, privacy guard."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_report as rr  # noqa: E402
import verify_trip as vt  # noqa: E402
from test_verify_trip import clean_plan  # noqa: E402

TODAY = date(2026, 11, 4)
HERE = os.path.dirname(os.path.abspath(__file__))


def blocks(plan, **opts):
    base = {"lang": "en", "detail": "full", "sections": rr.SECTIONS, "title": None}
    base.update(opts)
    return rr.build(plan, vt.Checker(plan, TODAY).run(), base)


def headings(bl, level="h2"):
    return [b[1] for b in bl if b[0] == level]


class Report(unittest.TestCase):
    def test_fixed_section_order(self):
        t = rr.TEXT["en"]
        self.assertEqual(headings(blocks(clean_plan())),
                         [t[s] for s in rr.SECTIONS if s != "overview"])

    def test_sections_can_be_chosen(self):
        bl = blocks(clean_plan(), sections=["bookings", "issues"])
        self.assertEqual(headings(bl), ["Bookings and tickets", "Open items"])
        self.assertEqual(headings(bl, "h1"), [])

    def test_place_labels_in_the_report_language(self):
        plan = clean_plan()
        plan["places"]["b"]["label"] = {"fr": "Lieu B"}
        self.assertIn("Lieu B B", rr.to_markdown(blocks(plan, lang="fr")))
        self.assertNotIn("Lieu B", rr.to_markdown(blocks(plan)))

    def test_brief_drops_long_notes(self):
        plan = clean_plan()
        plan["days"][0]["stops"][1]["note"] = "LONGNOTE"
        plan["days"][0]["stops"][1]["short"] = "SHORT"
        self.assertIn("LONGNOTE", rr.to_markdown(blocks(plan)))
        brief = rr.to_markdown(blocks(plan, detail="brief"))
        self.assertNotIn("LONGNOTE", brief)
        self.assertIn("SHORT", brief)

    def test_times_come_from_checker(self):
        md = rr.to_markdown(blocks(clean_plan()))
        self.assertIn("10:01", md)  # 08:00 + 110 min + 10 % buffer = 121 min

    def test_open_bookings_listed_by_book_by(self):
        plan = clean_plan()
        plan["bookings"] = [{"id": "x", "what": "Late", "date": "2026-11-10",
                             "book_by": "2026-11-09"},
                            {"id": "y", "what": "Early", "date": "2026-11-10",
                             "book_by": "2026-11-06"}]
        plan["bookings"].append({"id": "z", "what": "Done", "date": "2026-11-10",
                                 "status": "booked"})
        bl = blocks(plan, sections=["bookings"])
        rows = [b for b in bl if b[0] == "table"][0][2]
        self.assertEqual([r[1] for r in rows][:2], ["Early", "Late"])
        self.assertEqual({r[1] for r in rows[-2:]}, {"Done", "Motel"})

    def test_hotels_not_repeated_in_bookings(self):
        plan = clean_plan()
        bl = blocks(plan, sections=["bookings", "hotels"])
        tables = [b for b in bl if b[0] == "table"]
        self.assertEqual(len(tables), 1)
        self.assertNotIn("bullets", [b[0] for b in bl])
        bl = blocks(plan, sections=["bookings"])
        self.assertIn("Motel", rr.to_markdown(bl))

    def test_booking_link_shown(self):
        plan = clean_plan()
        plan["bookings"] = [{"id": "x", "what": "Tour", "date": "2026-11-10",
                             "book_by": "2026-11-09", "source": "https://example.org/tour"}]
        self.assertIn("https://example.org/tour",
                      rr.to_markdown(blocks(plan, sections=["bookings"])))

    def test_plan_report_block_sets_defaults(self):
        plan = clean_plan()
        plan["report"] = {"lang": "fr", "sections": ["overview", "hotels"],
                          "labels": {"hotels": "Hôtels", "days": "Jour après jour"}}
        with tempfile.TemporaryDirectory() as tmp:
            path, out = os.path.join(tmp, "p.json"), os.path.join(tmp, "r.md")
            with open(path, "w", encoding="utf-8") as h:
                json.dump(plan, h)
            subprocess.run([sys.executable, os.path.join(HERE, "render_report.py"), path,
                            "--out", out, "--today", "2026-11-04"], check=True,
                           capture_output=True)
            with open(out, encoding="utf-8") as h:
                text = h.read()
        self.assertIn("## Hôtels", text)
        self.assertNotIn("Jour après jour", text)

    def test_contingencies_shown(self):
        plan = clean_plan()
        plan["contingencies"] = [{"risk": "Pass closed", "decide_by": "2027-02-20",
                                  "trigger": "convoys still running",
                                  "plan": "inland route, trip_v3_B.json"}]
        md = rr.to_markdown(blocks(plan, sections=["issues"]))
        self.assertIn("Backup plans", md)
        self.assertIn("Pass closed (decide by 2027-02-20)", md)

    def test_phone_layout_has_no_tables(self):
        md = rr.to_markdown(blocks(clean_plan()), layout="phone")
        self.assertNotIn("|---", md)
        self.assertIn("- **", md)

    def test_long_day_warns_in_phone_layout(self):
        plan = clean_plan()
        plan["report"] = {"max_words_per_day": 20}
        plan["days"][0]["stops"][1]["note"] = "word " * 60
        with tempfile.TemporaryDirectory() as tmp:
            path, out = os.path.join(tmp, "p.json"), os.path.join(tmp, "r.md")
            with open(path, "w", encoding="utf-8") as h:
                json.dump(plan, h)
            done = subprocess.run([sys.executable, os.path.join(HERE, "render_report.py"), path,
                                   "--out", out, "--today", "2026-11-04"], capture_output=True,
                                  text=True)
        self.assertEqual(done.returncode, 0)
        self.assertIn("phone budget", done.stderr)

    def test_brief_keeps_only_open_requirements(self):
        md = rr.to_markdown(blocks(clean_plan(), detail="brief", sections=["issues"]))
        self.assertIn("2 of 2 requirements met", md)
        self.assertNotIn("[met]", md)

    def test_full_falls_back_to_short(self):
        plan = clean_plan()
        plan["days"][0]["stops"][1]["short"] = "ONLYSHORT"
        self.assertIn("ONLYSHORT", rr.to_markdown(blocks(plan)))

    def test_refuses_email(self):
        plan = clean_plan()
        plan["days"][0]["stops"][1]["note"] = "mail me at someone@example.com"
        with tempfile.TemporaryDirectory() as tmp:
            path, out = os.path.join(tmp, "p.json"), os.path.join(tmp, "r.md")
            with open(path, "w", encoding="utf-8") as h:
                json.dump(plan, h)
            done = subprocess.run([sys.executable, os.path.join(HERE, "render_report.py"),
                                   path, "--out", out], capture_output=True)
        self.assertEqual(done.returncode, 5)
        self.assertFalse(os.path.exists(out))

    def test_all_formats_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "p.json")
            with open(path, "w", encoding="utf-8") as h:
                json.dump(clean_plan(), h)
            for ext in ("md", "html", "pdf"):
                out = os.path.join(tmp, f"r.{ext}")
                subprocess.run([sys.executable, os.path.join(HERE, "render_report.py"), path,
                                "--out", out], check=True, capture_output=True)
                self.assertGreater(os.path.getsize(out), 300)


def run_cli(plan, *args):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "p.json")
        with open(path, "w", encoding="utf-8") as h:
            json.dump(plan, h)
        out = os.path.join(tmp, "r.md")
        done = subprocess.run([sys.executable, os.path.join(HERE, "render_report.py"), path,
                               "--out", out, *args], capture_output=True, text=True)
        text = ""
        if os.path.exists(out):
            with open(out, encoding="utf-8") as h:
                text = h.read()
        return done, text


class Languages(unittest.TestCase):
    def labels(self, **changes):
        done = subprocess.run([sys.executable, os.path.join(HERE, "render_report.py"),
                               "--print-labels"], check=True, capture_output=True, text=True)
        labels = json.loads(done.stdout)
        labels.update(changes)
        return labels

    def french_labels(self):
        labels = self.labels(days="Jour après jour", day_head="Jour {i} · {wd} {day} {mon}",
                             weekdays=["lun", "mar", "mer", "jeu", "ven", "sam", "dim"])
        labels["checks"]["daylight"] = "Arrivée avant la nuit"
        return labels

    def test_day_headings_keep_their_format(self):
        self.assertTrue(headings(blocks(clean_plan()), "h3")[0].startswith("Day 1 · "))

    def test_any_language_from_plan_labels(self):
        plan = clean_plan()
        plan["report"] = {"labels": self.french_labels()}
        bl = blocks(plan, lang="fr")
        self.assertIn("Jour après jour", headings(bl))
        self.assertTrue(headings(bl, "h3")[0].startswith("Jour 1 · "))
        self.assertEqual(rr.texts(plan, "fr")[2], [])

    def test_labels_override_a_built_in_language(self):
        plan = clean_plan()
        plan["report"] = {"labels": {"days": "Itinerary"}}
        self.assertIn("Itinerary", headings(blocks(plan)))
        self.assertEqual(rr.texts(plan, "en")[2], [])

    def test_missing_labels_fall_back_to_english_with_warning(self):
        done, text = run_cli(clean_plan(), "--lang", "fr")
        self.assertEqual(done.returncode, 0)
        self.assertIn("no built-in labels for 'fr'", done.stderr)
        self.assertIn("Day by day", text)

    def test_language_comes_from_the_plan(self):
        plan = clean_plan()
        plan["report"] = {"lang": "fr", "labels": self.french_labels()}
        done, text = run_cli(plan)
        self.assertNotIn("WARN: no built-in labels", done.stderr)
        self.assertIn("Jour après jour", text)

    def test_word_count_for_unspaced_scripts(self):
        self.assertEqual(rr.word_count("Don't stop here"), 3)
        self.assertEqual(rr.word_count("こんにちは"), 2)
        self.assertEqual(rr.word_count("สวัสดีครับ"), 2)

    def test_non_latin_pdf_writes(self):
        plan = clean_plan()
        plan["report"] = {"labels": self.labels(days="일정", overview="개요")}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "p.json")
            with open(path, "w", encoding="utf-8") as h:
                json.dump(plan, h)
            out = os.path.join(tmp, "r.pdf")
            subprocess.run([sys.executable, os.path.join(HERE, "render_report.py"), path,
                            "--out", out, "--lang", "ko"], check=True, capture_output=True)
            self.assertGreater(os.path.getsize(out), 300)


if __name__ == "__main__":
    unittest.main()
