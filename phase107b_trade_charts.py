"""Phase 107b — draw the user's own NQ/ES trades on 1-minute charts so they can
point at the levels and gaps they used. Research/learning aid only (Pillow, no
plotting dependency).

Each chart: 1-minute candles 08:30-11:00 NY, the user's entries (▲ long / ▼
short, with time and P&L), their stop (red tick) and exit (x), the liquidity
levels live at 08:30 (Phase 104 levels), and every 1-minute fair value gap
(green box = bullish gap, red box = bearish gap).

    python -m phase107b_trade_charts 2026-09-28 2026-10-07
Writes PNGs to exports/my_trade_charts/ (git-ignored).
"""
from __future__ import annotations

import os
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4
import phase104b_my_trades as mt
import phase106_follow_sweep as p6

OUT = os.path.join(p1.ROOT, "exports", "my_trade_charts")
FONT = os.path.join(p1.ROOT, "brand", "fonts", "Geist-Regular.ttf")
NAMES = {"PD": "prev day", "PW": "prev week", "ON": "overnight", "ASIA": "Asia", "LDN": "London", "OR": "open range", "S5": "5m swing", "S15": "15m swing"}
W, H, L, R, T, B = 1800, 900, 70, 230, 60, 50
BG, GRID, TXT = (250, 250, 252), (225, 228, 235), (60, 66, 80)
UP, DN, YOU, STOP = (42, 157, 143), (231, 111, 81), (29, 53, 87), (214, 40, 40)


def chart(day: str, symbol: str, mine: pd.DataFrame) -> str:
    df = p1.load(symbol, "M1")
    d = pd.Timestamp(day)
    w = df.loc[d + pd.Timedelta(hours=8, minutes=30): d + pd.Timedelta(hours=11)]
    p4.SESSION.clear()
    p4.SESSION.update(p6.INDEX_SESSION)
    ctx = p4._daily_context(df[df.index < d + pd.Timedelta(days=1)])
    prev = [x for x in ctx.index if pd.Timestamp(x) < d][-1]
    levels = p4._levels(df, d, ctx, prev)
    t0 = d + pd.Timedelta(hours=8, minutes=30)
    lo, hi = w["low"].min(), w["high"].max()
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad
    live = [x for x in levels if x["live_from"] <= t0 and lo <= x["price"] <= hi]

    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 13)
    fs = ImageFont.truetype(FONT, 11)
    n = len(w)
    cw = (W - L - R) / max(n, 1)
    X = lambda i: L + (i + 0.5) * cw  # noqa: E731
    Y = lambda p: T + (hi - p) / (hi - lo) * (H - T - B)  # noqa: E731

    for k in range(6):  # price grid
        p = lo + (hi - lo) * k / 5
        dr.line([(L, Y(p)), (W - R, Y(p))], fill=GRID)
        dr.text((5, Y(p) - 7), f"{p:,.2f}", font=fs, fill=TXT)
    for i in range(0, n, 10):  # time axis
        dr.line([(X(i), T), (X(i), H - B)], fill=GRID)
        dr.text((X(i) - 15, H - B + 8), w.index[i].strftime("%H:%M"), font=fs, fill=TXT)
    i930 = w.index.searchsorted(d + pd.Timedelta(hours=9, minutes=30))
    dr.line([(X(i930), T), (X(i930), H - B)], fill=(150, 150, 160), width=2)
    dr.text((X(i930) + 4, T - 18), "09:30 open", font=fs, fill=TXT)

    h, l = w["high"].to_numpy(), w["low"].to_numpy()
    for k in range(2, n):  # fair value gaps
        if h[k - 2] < l[k]:
            dr.rectangle([X(k - 2), Y(l[k]), X(min(k + 4, n - 1)), Y(h[k - 2])], fill=(205, 235, 230))
        if l[k - 2] > h[k]:
            dr.rectangle([X(k - 2), Y(l[k - 2]), X(min(k + 4, n - 1)), Y(h[k])], fill=(248, 220, 212))
    for x in live:  # liquidity levels
        yy = Y(x["price"])
        for xx in range(L, W - R, 8):
            dr.line([(xx, yy), (xx + 4, yy)], fill=(120, 125, 140))
        dr.text((W - R + 6, yy - 7), f"{NAMES.get(x['family'], x['family'])} {'high' if x['side'] == 'H' else 'low'}", font=fs, fill=TXT)
    for i, (_, r) in enumerate(w.iterrows()):  # candles
        col = UP if r["close"] >= r["open"] else DN
        dr.line([(X(i), Y(r["high"])), (X(i), Y(r["low"]))], fill=col)
        top, bot = Y(max(r["open"], r["close"])), Y(min(r["open"], r["close"]))
        dr.rectangle([X(i) - cw * 0.35, top, X(i) + cw * 0.35, max(bot, top + 1)], fill=col)
    for _, t in mine.iterrows():  # the user's trades
        et = pd.Timestamp(t["entry_time"])
        if et.date() != d.date() or t["symbol"] != symbol:
            continue
        xi = min(w.index.searchsorted(et), n - 1)
        x0, y0 = X(xi), Y(t["entry"])
        tri = [(x0, y0 - 10), (x0 - 8, y0 + 6), (x0 + 8, y0 + 6)] if t["side"] > 0 else [(x0, y0 + 10), (x0 - 8, y0 - 6), (x0 + 8, y0 - 6)]
        dr.polygon(tri, fill=YOU)
        lab = f"you {'LONG' if t['side'] > 0 else 'SHORT'} {et:%H:%M}  {t['profit']:+.0f}$"
        dr.text((x0 + 10, y0 + (8 if t["side"] > 0 else -22)), lab, font=f, fill=YOU)
        if t["sl"] == t["sl"]:
            dr.line([(x0 - 6, Y(t["sl"])), (x0 + 40, Y(t["sl"]))], fill=STOP, width=3)
            dr.text((x0 + 42, Y(t["sl"]) - 7), "your stop", font=fs, fill=STOP)
        xo = min(w.index.searchsorted(pd.Timestamp(t["exit_time"])), n - 1)
        xe, ye = X(xo), Y(t["exit"])
        dr.line([(xe - 6, ye - 6), (xe + 6, ye + 6)], fill=YOU, width=3)
        dr.line([(xe - 6, ye + 6), (xe + 6, ye - 6)], fill=YOU, width=3)
    dr.text((L, 15), f"{symbol} 1-minute, {day} (New York time) — ▲▼ your entries · red tick = your stop · x = exit · "
                     "green/red boxes = bullish/bearish fair value gaps · dotted = liquidity levels", font=f, fill=TXT)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{symbol}_{day}.png")
    img.save(path)
    return path


def main(argv=None) -> int:  # pragma: no cover
    days = (argv if argv is not None else sys.argv[1:]) or ["2026-09-28", "2026-10-07"]
    mine = mt.my_positions()
    for day in days:
        syms = sorted(set(mine[pd.to_datetime(mine["entry_time"]).dt.strftime("%Y-%m-%d") == day]["symbol"])) or ["NQ"]
        for s in syms:
            print(chart(day, s, mine))
    return 0


if __name__ == "__main__":
    sys.exit(main())
