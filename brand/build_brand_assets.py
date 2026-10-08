"""Build every TradeLogger brand asset from one definition of the mark.

    python brand/build_brand_assets.py

The mark is a trade drawn the way TradeLogger draws trades (the Position
Track on Overview): a red stop below, an entry, a path that rises to a
target line, and a cyan dot where it lands. Its geometry lives ONCE, in
GLYPH below, on a 64-unit grid. This script writes:

  brand/*.svg                     vector masters (tile, glyph, mono)
  frontend/public/*               favicon (svg + png), PWA icons, Apple touch
                                  icon, link-preview card, wordmark, avatar
  desktop/build/icon.ico          Windows app icon (16-256 px)
  desktop/build/overlay-badge.png taskbar badge for triggered price alerts
  mobile/assets/*                 Expo icon, Android adaptive layers, splash,
                                  notification icon, web favicon
  favicon.png, app_icon.png, trade_logger_logo.png   (repo root, legacy copies)

Only Pillow is needed. Fonts are Geist (SIL OFL 1.1) in brand/fonts.
See docs/BRAND.md for what each file is for and the rules for using the mark.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "brand"
FONTS = BRAND / "fonts"
PUBLIC = ROOT / "frontend" / "public"
DESKTOP = ROOT / "desktop" / "build"
MOBILE = ROOT / "mobile" / "assets"

# --- Palette (mirrors frontend/src/styles/tokens.css) ------------------------
NAVY = "#0b0f17"  # --tl-background (dark)
TILE = "#111826"  # the icon tile: one step up from the page so it reads on dark taskbars
TILE_EDGE = (160, 182, 220, 46)  # --tl-border, a touch stronger for small sizes
CYAN = "#5ad1f5"  # --tl-accent-fill (dark)
CYAN_LIGHT = "#12a8d8"  # --tl-accent-fill (light)
RED = "#f87171"  # --tl-negative (dark)
RED_LIGHT = "#dc2626"
INK = "#e8edf5"  # --tl-text-primary (dark)
INK_2 = "#a4afc2"  # --tl-text-secondary (dark)
INK_3 = "#77849a"  # --tl-text-muted (dark)
GRID = (160, 182, 220, 14)  # --tl-grid-line

# --- The mark, on a 64 x 64 grid ---------------------------------------------
# Full detail (32 px and up): target line, ringed target dot.
GLYPH = {
    "target": ((13.0, 17.5), (52.0, 17.5), 2.2),  # from, to, width  (drawn at 45% alpha)
    "path": [(14.0, 42.0), (25.0, 31.0), (33.0, 37.5), (48.0, 17.5)],
    "path_w": 4.6,
    "dot": ((48.0, 17.5), 5.0, 7.4),  # centre, radius, knockout-ring radius
    "stop": ((11.5, 49.5), (23.0, 49.5), 4.0),
}
# Small sizes (16-24 px): no target line or ring, heavier strokes.
GLYPH_SMALL = {
    "target": None,
    "path": [(12.0, 43.0), (24.0, 31.0), (32.5, 38.0), (48.5, 18.0)],
    "path_w": 7.0,
    "dot": ((48.5, 18.0), 7.0, 0.0),
    "stop": ((10.5, 52.0), (24.0, 52.0), 6.5),
}
TILE_RADIUS = 14.0  # of 64

SS = 4  # supersampling factor for anti-aliasing


def _hex(c: str, a: int = 255) -> tuple[int, int, int, int]:
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a)


def mix(rgba, ground: str) -> tuple[int, int, int, int]:
    """Pre-blend a translucent colour onto a known ground. ImageDraw REPLACES
    pixels (alpha included) rather than compositing, so translucent strokes on
    an opaque image must be flattened first."""
    g = _hex(ground)
    a = rgba[3] / 255
    return tuple(round(rgba[i] * a + g[i] * (1 - a)) for i in range(3)) + (255,)


def _stroke(draw: ImageDraw.ImageDraw, pts, w: float, fill) -> None:
    """Polyline with round caps and round joins."""
    draw.line(pts, fill=fill, width=max(1, round(w)), joint="curve")
    r = w / 2
    for x, y in pts:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def draw_glyph(img: Image.Image, box: tuple[float, float, float], *, small=False, colors=None, mono=None) -> None:
    """Draw the mark into `img` (already supersampled) at box = (x0, y0, size).

    colors: dict(path, dot, stop, target) — defaults to the dark-ground palette.
    mono:   an RGBA tuple — draw everything in one colour (notification / monochrome icons).
    """
    g = GLYPH_SMALL if small else GLYPH
    x0, y0, size = box
    k = size / 64.0

    def P(p):
        return (x0 + p[0] * k, y0 + p[1] * k)

    c = colors or {"path": _hex(CYAN), "dot": _hex(CYAN), "stop": _hex(RED), "target": _hex(CYAN, 115)}
    if mono:
        c = {"path": mono, "dot": mono, "stop": mono, "target": (*mono[:3], 150)}

    (cx, cy), r, ring = g["dot"]
    cx, cy = P((cx, cy))
    if g["target"]:
        # The target line, with a ring cut out around the dot so the dot reads
        # as "landed on the line", not "blob on a line".
        a, b, w = g["target"]
        t = Image.new("RGBA", img.size, (0, 0, 0, 0))
        _stroke(ImageDraw.Draw(t), [P(a), P(b)], w * k, c["target"][:3] + (255,))
        cut = Image.new("L", img.size, 255)
        ImageDraw.Draw(cut).ellipse((cx - ring * k, cy - ring * k, cx + ring * k, cy + ring * k), fill=0)
        alpha = t.getchannel("A").point(lambda v: v * c["target"][3] // 255)
        t.putalpha(Image.composite(alpha, Image.new("L", img.size, 0), cut))
        img.alpha_composite(t)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a, b, w = g["stop"]
    _stroke(d, [P(a), P(b)], w * k, c["stop"])
    _stroke(d, [P(p) for p in g["path"]], g["path_w"] * k, c["path"])
    d.ellipse((cx - r * k, cy - r * k, cx + r * k, cy + r * k), fill=c["dot"])
    img.alpha_composite(layer)


def tile(px: int, *, rounded=True, glyph_scale=1.0, small=None, edge=True) -> Image.Image:
    """The app-icon tile: navy square (rounded, or full-bleed for OS-masked icons) with the mark."""
    S = px * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        r = TILE_RADIUS / 64 * S
        d.rounded_rectangle((0, 0, S - 1, S - 1), radius=r, fill=_hex(TILE))
        if edge:
            w = max(SS, round(S / 64))
            d.rounded_rectangle((w / 2, w / 2, S - 1 - w / 2, S - 1 - w / 2), radius=r - w / 2, outline=mix(TILE_EDGE, TILE), width=w)
    else:
        d.rectangle((0, 0, S, S), fill=_hex(TILE))
    small = (px <= 24) if small is None else small
    gs = S * glyph_scale
    draw_glyph(img, ((S - gs) / 2, (S - gs) / 2, gs), small=small)
    return img.resize((px, px), Image.LANCZOS)


def glyph_only(px: int, *, scale=1.0, small=False, colors=None, mono=None) -> Image.Image:
    S = px * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gs = S * scale
    draw_glyph(img, ((S - gs) / 2, (S - gs) / 2, gs), small=small, colors=colors, mono=mono)
    return img.resize((px, px), Image.LANCZOS)


def font(name: str, size: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), round(size))


def text_w(draw, s, f, tracking=0.0) -> float:
    return draw.textlength(s, font=f) + tracking * f.size * (len(s) - 1)


def draw_text(draw, xy, s, f, fill, tracking=0.0) -> None:
    """Text with letter-spacing (Pillow has none built in)."""
    if not tracking:
        draw.text(xy, s, font=f, fill=fill)
        return
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + tracking * f.size


# --- Composite assets --------------------------------------------------------
def lockup_square(px: int, *, ground: str | None) -> Image.Image:
    """Stacked lockup: tile above the wordmark. ground=None gives a transparent PNG."""
    S = px * SS
    img = Image.new("RGBA", (S, S), _hex(ground) if ground else (0, 0, 0, 0))
    t = tile(round(px * 0.34)).resize((round(S * 0.34),) * 2, Image.LANCZOS)
    tx = (S - t.width) // 2
    ty = round(S * 0.26)
    img.alpha_composite(t, (tx, ty))
    d = ImageDraw.Draw(img)
    f = font("Geist-SemiBold", S * 0.098)
    s = "TradeLogger"
    w = text_w(d, s, f, -0.02)
    draw_text(d, ((S - w) / 2, ty + t.height + S * 0.07), s, f, _hex(INK), -0.02)
    return img.resize((px, px), Image.LANCZOS)


def og_image() -> Image.Image:
    """1200 x 630 link-preview card: lockup, one-line promise, and a Position Track."""
    W, H = 1200 * SS, 630 * SS
    img = Image.new("RGBA", (W, H), _hex(NAVY))
    d = ImageDraw.Draw(img)
    # faint 48 px grid, like a chart pane
    step = 48 * SS
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=mix(GRID, NAVY), width=SS)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=mix(GRID, NAVY), width=SS)

    pad = 88 * SS
    t = tile(88).resize((88 * SS, 88 * SS), Image.LANCZOS)
    img.alpha_composite(t, (pad, 96 * SS))
    f_name = font("Geist-SemiBold", 50 * SS)
    draw_text(d, (pad + 88 * SS + 28 * SS, 96 * SS + 14 * SS), "TradeLogger", f_name, _hex(INK), -0.02)

    f_head = font("Geist-SemiBold", 56 * SS)
    draw_text(d, (pad, 246 * SS), "Your trading journal,", f_head, _hex(INK), -0.025)
    draw_text(d, (pad, 312 * SS), "made clear.", f_head, _hex(CYAN), -0.025)
    f_body = font("Geist-Regular", 25 * SS)
    d.text((pad, 398 * SS), "Every trade synced, every number in plain English.", font=f_body, fill=_hex(INK_2))

    # Position Track: stop - entry - now - target (an illustration, no figures)
    x0, x1, y = pad, W - pad, 520 * SS
    xs = {"STOP": x0, "ENTRY": x0 + (x1 - x0) * 0.30, "NOW": x0 + (x1 - x0) * 0.70, "TARGET": x1}
    d.line([(x0, y), (x1, y)], fill=mix((160, 182, 220, 50), NAVY), width=4 * SS)
    d.line([(xs["STOP"], y), (xs["ENTRY"], y)], fill=mix(_hex(RED, 170), NAVY), width=4 * SS)
    d.line([(xs["ENTRY"], y), (xs["NOW"], y)], fill=_hex(CYAN), width=4 * SS)
    f_lab = font("GeistMono-Medium", 15 * SS)
    for name, x in xs.items():
        if name == "NOW":
            r = 9 * SS
            d.ellipse((x - r - 5 * SS, y - r - 5 * SS, x + r + 5 * SS, y + r + 5 * SS), fill=_hex(NAVY))
            d.ellipse((x - r, y - r, x + r, y + r), fill=_hex(CYAN))
        else:
            d.line([(x, y - 12 * SS), (x, y + 12 * SS)], fill=_hex(RED) if name == "STOP" else _hex(INK_3), width=3 * SS)
        lw = text_w(d, name, f_lab, 0.12)
        lx = min(max(x - lw / 2, x0), x1 - lw)
        draw_text(d, (lx, y + 26 * SS), name, f_lab, _hex(CYAN) if name == "NOW" else _hex(INK_3), 0.12)

    f_url = font("GeistMono-Medium", 17 * SS)
    u = "tradelogger.site"
    draw_text(d, (W - pad - text_w(d, u, f_url, 0.04), 104 * SS + 22 * SS), u, f_url, _hex(INK_3), 0.04)
    return img.resize((1200, 630), Image.LANCZOS).convert("RGB")


def overlay_badge() -> Image.Image:
    """Windows taskbar overlay (shown at ~16 px): a cyan dot ringed in navy."""
    S = 64 * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2 * SS, 2 * SS, S - 2 * SS, S - 2 * SS), fill=_hex(NAVY))
    d.ellipse((10 * SS, 10 * SS, S - 10 * SS, S - 10 * SS), fill=_hex(CYAN))
    return img.resize((64, 64), Image.LANCZOS)


# --- SVG masters -------------------------------------------------------------
def _svg_glyph(g=GLYPH, *, path=CYAN, stop=RED, target=CYAN, ground=TILE, mono=False) -> str:
    pts = " ".join(f"{x:g} {y:g}" for x, y in g["path"])
    (sx0, sy0), (sx1, sy1), sw = g["stop"]
    (cx, cy), r, ring = g["dot"]
    col = "currentColor" if mono else None
    out = []
    if g["target"]:
        (tx0, ty0), (tx1, ty1), tw = g["target"]
        out.append(
            f'<path d="M{tx0:g} {ty0:g}H{tx1:g}" stroke="{col or target}" stroke-opacity="0.45" '
            f'stroke-width="{tw:g}" stroke-linecap="round"/>'
        )
        if ring and not mono:
            out.append(f'<circle cx="{cx:g}" cy="{cy:g}" r="{ring:g}" fill="{ground}"/>')
    out.append(f'<path d="M{sx0:g} {sy0:g}H{sx1:g}" stroke="{col or stop}" stroke-width="{sw:g}" stroke-linecap="round"/>')
    out.append(
        f'<path d="M{pts}" fill="none" stroke="{col or path}" stroke-width="{g["path_w"]:g}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    out.append(f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{col or path}"/>')
    return "\n  ".join(out)


def write_svgs() -> dict[str, str]:
    edge = "rgba(160,182,220,0.18)"
    tile_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">\n'
        f'  <rect x="0.5" y="0.5" width="63" height="63" rx="{TILE_RADIUS - 0.5:g}" fill="{TILE}" stroke="{edge}"/>\n'
        f"  {_svg_glyph()}\n</svg>\n"
    )
    files = {
        "logo-tile.svg": tile_svg,
        "logo-glyph-dark.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">\n  '
        + _svg_glyph(ground=NAVY)
        + "\n</svg>\n",
        "logo-glyph-light.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">\n  '
        + _svg_glyph(path=CYAN_LIGHT, stop=RED_LIGHT, target=CYAN_LIGHT, ground="#ffffff")
        + "\n</svg>\n",
        "logo-mono.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">\n  '
        + _svg_glyph(mono=True)
        + "\n</svg>\n",
    }
    for name, body in files.items():
        (BRAND / name).write_text(body, encoding="utf-8", newline="\n")
    (PUBLIC / "favicon.svg").write_text(tile_svg, encoding="utf-8", newline="\n")
    return files


def main() -> None:
    write_svgs()

    # Web / PWA
    tile(192).save(PUBLIC / "favicon.png")
    tile(192).save(PUBLIC / "icon-192.png")
    tile(512).save(PUBLIC / "icon-512.png")
    # maskable: full bleed; mark inside the central 80% safe circle
    tile(512, rounded=False, glyph_scale=0.70).save(PUBLIC / "icon-maskable-512.png")
    # iOS rounds the corners itself; it wants an opaque square
    tile(180, rounded=False, glyph_scale=0.84).convert("RGB").save(PUBLIC / "apple-touch-icon.png")
    og_image().save(PUBLIC / "og-image.png")
    lockup_square(1024, ground=NAVY).save(PUBLIC / "wordmark.png")
    lockup_square(1024, ground=None).save(PUBLIC / "wordmark-transparent.png")
    # social avatar: cropped to a circle by TikTok/Instagram, so keep the mark inside it
    tile(1024, rounded=False, glyph_scale=0.60).convert("RGB").save(PUBLIC / "avatar-tiktok.png")

    # Desktop (Windows)
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [tile(s) for s in ico_sizes]
    frames[-1].save(DESKTOP / "icon.ico", format="ICO", sizes=[(s, s) for s in ico_sizes], append_images=frames[:-1])
    overlay_badge().save(DESKTOP / "overlay-badge.png")

    # Mobile (Expo)
    tile(1024, rounded=False, glyph_scale=0.84).convert("RGB").save(MOBILE / "icon.png")
    # Android adaptive icon: 108dp canvas, 66dp safe circle -> keep the mark inside ~61%
    glyph_only(1024, scale=0.62).save(MOBILE / "android-icon-foreground.png")
    Image.new("RGB", (1024, 1024), _hex(TILE)[:3]).save(MOBILE / "android-icon-background.png")
    glyph_only(1024, scale=0.62, mono=(255, 255, 255, 255)).save(MOBILE / "android-icon-monochrome.png")
    glyph_only(1024, scale=1.0).save(MOBILE / "splash-icon.png")
    # Android status-bar icons must be white-on-transparent silhouettes
    glyph_only(96, scale=0.92, small=True, mono=(255, 255, 255, 255)).save(MOBILE / "notification-icon.png")
    tile(48).save(MOBILE / "favicon.png")

    # Repo-root legacy copies (older tooling picks these up)
    tile(192).save(ROOT / "favicon.png")
    tile(192).save(ROOT / "app_icon.png")
    lockup_square(1024, ground=None).save(ROOT / "trade_logger_logo.png")
    print("brand assets written")


if __name__ == "__main__":
    main()
