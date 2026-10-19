# -*- coding: utf-8 -*-
"""
Guard: the web and phone apps decide "what day is it" on the viewer's own clock.

2026-10-19 the Analytics calendar highlighted Sunday on a Monday morning in Manila: it took "today"
from `new Date().toISOString().slice(0, 10)` (the UTC date, still yesterday until 08:00 at UTC+8),
froze it in a module constant (the desktop app stays open for days, so it never moved on), and the
server bucketed the calendar's days in UTC too. The fix routes everything through
`frontend/src/lib/dates.ts` and sends the viewer's timezone (`tz`) to the analytics API. These tests
fail if any of the three mistakes comes back.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = [ROOT / "frontend" / "src", ROOT / "mobile" / "src"]
ALLOWED = {ROOT / "frontend" / "src" / "lib" / "dates.ts"}

UTC_DAY = re.compile(r"toISOString\(\)\s*\.\s*(slice\(\s*0\s*,\s*10\s*\)|substring\(\s*0\s*,\s*10\s*\)|split\(\s*['\"]T['\"]\s*\)\s*\[\s*0\s*\])")
FROZEN_TODAY = re.compile(r"^(export\s+)?const\s+TODAY\w*\s*=", re.MULTILINE)


def _files():
    for base in SOURCES:
        for p in base.rglob("*"):
            if p.suffix in (".ts", ".tsx") and "node_modules" not in p.parts and p not in ALLOWED:
                yield p


def test_no_utc_date_string_used_as_a_day():
    hits = [f"{p.relative_to(ROOT)}:{i}" for p in _files()
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if UTC_DAY.search(line)]
    assert not hits, (
        "toISOString().slice(0, 10) is the UTC date (yesterday until 08:00 in Manila). "
        "Use localDayIso()/todayIso() from frontend/src/lib/dates.ts: " + ", ".join(hits)
    )


def test_no_today_frozen_in_a_module_constant():
    hits = [str(p.relative_to(ROOT)) for p in _files() if FROZEN_TODAY.search(p.read_text(encoding="utf-8"))]
    assert not hits, (
        "A module-level TODAY constant never changes while the app stays open (the desktop app runs for days). "
        "Use useTodayIso() from frontend/src/lib/dates.ts: " + ", ".join(hits)
    )


def test_every_analytics_day_call_sends_the_viewers_timezone():
    missing = []
    for p in _files():
        text = p.read_text(encoding="utf-8")
        calls = re.search(r"\bapi(Get|Post)\b", text) and re.search(r"['\"`]/api/analytics/(performance|day)", text)
        if calls and "p.set('tz'" not in text:
            missing.append(str(p.relative_to(ROOT)))
    assert not missing, "These call /api/analytics without tz, so their days would be UTC days: " + ", ".join(missing)
