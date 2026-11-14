# -*- coding: utf-8 -*-
"""
Guard: the phone app stays on the "Precision" design system (docs/DESIGN_SYSTEM.md, "Phone app").

2026-11-14 every phone screen was rebuilt on one kit (mobile/src/components/ui.tsx) with Geist type. Before
that each screen carried its own copy of the card / button / chip styles, weights up to 800 and the system
font, and they had drifted apart. These checks fail if a screen goes back to doing its own thing:

  * text comes from components/Text (Geist, weight-to-file mapping), never straight from 'react-native'
  * colours come from theme.ts, never a literal in a screen
  * nothing asks for a weight above 600
  * no emoji or arrow glyphs standing in for icons (they render differently on every phone)
"""
import pathlib
import re

MOBILE = pathlib.Path(__file__).resolve().parents[1] / "mobile"
SRC = MOBILE / "src"
FILES = sorted(SRC.rglob("*.tsx")) + [MOBILE / "App.tsx"]

# data-coloured drawings: chart series and the calendar heat tint are computed colours, not UI chrome
COLOUR_EXEMPT = {"components/scanner/KillzoneChart.tsx", "components/analytics/MonthCalendar.tsx"}


def _rel(p: pathlib.Path) -> str:
    return p.relative_to(SRC).as_posix() if SRC in p.parents else p.name


def _code(p: pathlib.Path) -> str:
    """source without comments, so a rule explained in a comment is not a violation"""
    text = p.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(line.split("//")[0] if "://" not in line else line for line in text.splitlines())


def test_there_are_screens_to_check():
    assert len(FILES) > 30


def test_text_always_comes_from_the_geist_wrapper():
    bad = []
    for p in FILES:
        if _rel(p) == "components/Text.tsx":
            continue
        for m in re.finditer(r"import\s*\{([^}]*)\}\s*from 'react-native'", p.read_text(encoding="utf-8")):
            names = {n.strip().split(" as ")[0].replace("type ", "") for n in m.group(1).split(",")}
            if names & {"Text", "TextInput"}:
                bad.append(_rel(p))
    assert not bad, f"import Text / TextInput from components/Text, not 'react-native': {bad}"


def test_no_colour_literals_outside_the_theme():
    bad = []
    for p in FILES:
        if _rel(p) in COLOUR_EXEMPT:
            continue
        for n, line in enumerate(_code(p).splitlines(), 1):
            if re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", line):
                bad.append(f"{_rel(p)}:{n}: {line.strip()[:80]}")
    assert not bad, "use colors.* from theme.ts:\n" + "\n".join(bad)


def test_nothing_is_heavier_than_600():
    bad = []
    for p in FILES + [SRC / "theme.ts"]:
        for n, line in enumerate(_code(p).splitlines(), 1):
            if re.search(r"fontWeight:\s*'?(700|800|900|bold)'?", line):
                bad.append(f"{_rel(p)}:{n}")
    assert not bad, f"the heaviest weight is 600 (semibold): {bad}"


def test_icons_are_icons_not_glyphs():
    glyphs = re.compile("[\U0001F300-\U0001FAFF☀-➿←-⇿■-◿★☆]")
    bad = []
    for p in FILES:
        # the plan-note text (saved to the journal as plain text) may keep its check marks
        for n, line in enumerate(_code(p).splitlines(), 1):
            if glyphs.search(line) and "label}`" not in line:
                bad.append(f"{_rel(p)}:{n}: {line.strip()[:70]}")
    assert not bad, "use an Ionicons icon instead of an emoji / arrow / star glyph:\n" + "\n".join(bad)


def test_the_fonts_the_theme_names_are_loaded():
    theme = (SRC / "theme.ts").read_text(encoding="utf-8")
    app = (MOBILE / "App.tsx").read_text(encoding="utf-8")
    families = set(re.findall(r"'(Geist(?:Mono)?_\d{3}\w+)'", theme))
    assert len(families) == 6
    missing = [f for f in families if f not in app]
    assert not missing, f"theme.ts names fonts App.tsx never loads: {missing}"
