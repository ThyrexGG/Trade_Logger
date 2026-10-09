"""Phase 119 — draw every recent big-gap-fade setup on a chart (learning aid, Pillow only).

Same idea as phase107b (the user's own trades): one picture per day, 5-minute candles
09:00-13:00 New York, with yesterday's close (the target), the entry, the stop and where the
trade ended. The rule is exactly Phase 117/118: gap at 09:30 >= 0.7 x the 14-session average
daily range, entry at 09:45 only if the gap is still unfilled, TOWARD yesterday's close, target =
yesterday's close, wide stop (1:1 with the target; the tight alternative is drawn as a dashed
line), exit at target / stop / 12:00. Results are in R before costs.

    python -m phase119_gap_charts            # the 12 latest setups on ES and NQ
    python -m phase119_gap_charts ES 20      # one market, the 20 latest
Writes PNGs to exports/gap_fade_charts/ and an INDEX.md (git-ignored).
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from typing import Dict, List

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

import phase101_ny_open_sweep as p1

OUT = os.path.join(p1.ROOT, "exports", "gap_fade_charts")
F_REG = os.path.join(p1.ROOT, "brand", "fonts", "Geist-Regular.ttf")
F_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
W, H, L, R, T, B = 1700, 860, 80, 290, 150, 70
BG, GRID, TXT, MUTE = (250, 250, 252), (228, 231, 238), (38, 44, 58), (110, 116, 130)
UP, DN = (42, 157, 143), (231, 111, 81)
GREEN, RED, ORANGE, NAVY = (34, 139, 34), (200, 40, 40), (230, 126, 34), (29, 53, 87)
THR = 0.7


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def setups(mkt: str, df: pd.DataFrame) -> List[dict]:
    rth = df[(df.index.time >= dt.time(9, 30)) & (df.index.time < dt.time(16, 0))]
    gb = rth.groupby(rth.index.normalize())
    atr = (gb["high"].max() - gb["low"].min()).shift(1).rolling(14).mean()
    pcl = gb["close"].last().shift(1)
    slip = p1.SLIPPAGE[mkt]
    out = []
    for day, g in gb:
        if day.weekday() > 4 or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0].time() != dt.time(9, 30):
            continue
        pc, a = float(pcl[day]), float(atr[day])
        gap = float(g["open"].iloc[0]) - pc
        size = abs(gap) / a
        if size < THR:
            continue
        gup = gap > 0
        t0 = day + pd.Timedelta(hours=9, minutes=45)
        noon = day + pd.Timedelta(hours=12)
        pre, post = g[g.index < t0], g[(g.index >= t0) & (g.index < noon)]
        if len(pre) < 10 or len(post) < 10:
            continue
        touched = (pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)
        e = float(pre["close"].iloc[-1])
        if touched or (gup and e <= pc) or ((not gup) and e >= pc):
            continue
        side = -1 if gup else 1
        dist = abs(e - pc)
        risk = dist
        stop = e - side * risk
        far = float(pre["high"].max()) if gup else float(pre["low"].min())
        tight = e - side * max(abs(far - e), 0.10 * a)
        h, l, c = post["high"].to_numpy(), post["low"].to_numpy(), post["close"].to_numpy()
        res, how, k_exit, px_exit = None, "time exit (12:00)", len(post) - 1, float(c[-1])
        for k in range(len(post)):
            if (side > 0 and l[k] <= stop) or (side < 0 and h[k] >= stop):
                res, how, k_exit, px_exit = -1.0, "stop hit", k, stop
                break
            if (side > 0 and h[k] >= pc) or (side < 0 and l[k] <= pc):
                res, how, k_exit, px_exit = dist / risk, "target hit", k, pc
                break
        if res is None:
            res = side * (c[-1] - e) / risk
        out.append({"market": mkt, "day": day, "pc": pc, "open": float(g["open"].iloc[0]), "gap": gap, "size": size, "avg": a, "side": side,
                    "entry": e, "stop": stop, "tight": tight, "target": pc, "exit_t": post.index[k_exit], "exit_px": px_exit,
                    "r": float(res), "how": how})
    return out


def chart(s: dict, df: pd.DataFrame) -> str:
    d = s["day"]
    w5 = df.loc[d + pd.Timedelta(hours=9): d + pd.Timedelta(hours=13)].resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    lo = min(w5["low"].min(), s["stop"], s["target"], s["tight"])
    hi = max(w5["high"].max(), s["stop"], s["target"], s["tight"], s["pc"], s["open"])
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    f, fs, fb, fh = _font(F_REG, 14), _font(F_REG, 12), _font(F_BOLD, 15), _font(F_BOLD, 24)
    n = len(w5)
    cw = (W - L - R) / max(n, 1)
    X = lambda i: L + (i + 0.5) * cw  # noqa: E731
    Y = lambda p: T + (hi - p) / (hi - lo) * (H - T - B)  # noqa: E731
    xt = lambda t: min(max(w5.index.searchsorted(t), 0), n - 1)  # noqa: E731
    for k in range(7):
        p = lo + (hi - lo) * k / 6
        dr.line([(L, Y(p)), (W - R, Y(p))], fill=GRID)
        dr.text((6, Y(p) - 7), f"{p:,.1f}", font=fs, fill=MUTE)
    for i in range(0, n, 6):
        dr.line([(X(i), T), (X(i), H - B)], fill=GRID)
        dr.text((X(i) - 16, H - B + 8), w5.index[i].strftime("%H:%M"), font=fs, fill=MUTE)
    i0, i1 = xt(d + pd.Timedelta(hours=9, minutes=30)), xt(d + pd.Timedelta(hours=9, minutes=45))
    dr.rectangle([X(i0) - cw / 2, T, X(i1) - cw / 2, H - B], fill=(244, 240, 232))
    dr.text((X(i0), T + 4), "09:30-09:45: watch only", font=fs, fill=MUTE)
    ie = xt(d + pd.Timedelta(hours=9, minutes=45))
    ix = xt(s["exit_t"])
    # target and stop zones (from the entry to the exit)
    x_a, x_b = X(ie) - cw / 2, X(ix) + cw / 2
    dr.rectangle([x_a, Y(max(s["entry"], s["target"])), x_b, Y(min(s["entry"], s["target"]))], fill=(214, 238, 214), outline=GREEN)
    dr.rectangle([x_a, Y(max(s["entry"], s["stop"])), x_b, Y(min(s["entry"], s["stop"]))], fill=(248, 218, 218), outline=RED)
    # lines
    for xx in range(L, W - R, 10):
        dr.line([(xx, Y(s["pc"])), (xx + 5, Y(s["pc"]))], fill=ORANGE, width=2)
        dr.line([(xx, Y(s["tight"])), (xx + 3, Y(s["tight"]))], fill=(200, 120, 120))
    dr.text((W - R + 8, Y(s["pc"]) - 9), "TARGET (yesterday's close)", font=fb, fill=ORANGE)
    dr.text((W - R + 8, Y(s["pc"]) + 8), f"{s['pc']:,.1f}", font=f, fill=ORANGE)
    dr.text((W - R + 8, Y(s["stop"]) - 9), "STOP (wide)", font=fb, fill=RED)
    dr.text((W - R + 8, Y(s["stop"]) + 8), f"{s['stop']:,.1f}", font=f, fill=RED)
    dr.text((W - R + 8, Y(s["tight"]) - 7), "tight stop (alt.)", font=fs, fill=(170, 100, 100))
    dr.text((W - R + 8, Y(s["open"]) - 7), f"09:30 open {s['open']:,.1f}", font=fs, fill=NAVY)
    # candles
    for i, (_, r) in enumerate(w5.iterrows()):
        col = UP if r["close"] >= r["open"] else DN
        dr.line([(X(i), Y(r["high"])), (X(i), Y(r["low"]))], fill=col)
        top, bot = Y(max(r["open"], r["close"])), Y(min(r["open"], r["close"]))
        dr.rectangle([X(i) - cw * 0.33, top, X(i) + cw * 0.33, max(bot, top + 1)], fill=col)
    # entry and exit
    x0, y0 = X(ie), Y(s["entry"])
    tri = [(x0, y0 + 12), (x0 - 9, y0 - 6), (x0 + 9, y0 - 6)] if s["side"] < 0 else [(x0, y0 - 12), (x0 - 9, y0 + 6), (x0 + 9, y0 + 6)]
    dr.polygon(tri, fill=NAVY)
    dr.text((x0 + 12, y0 + (6 if s["side"] < 0 else -22)), f"ENTRY 09:45  {'SHORT' if s['side'] < 0 else 'LONG'}  {s['entry']:,.1f}", font=fb, fill=NAVY)
    xe, ye = X(ix), Y(s["exit_px"])
    dr.line([(xe - 7, ye - 7), (xe + 7, ye + 7)], fill=NAVY, width=4)
    dr.line([(xe - 7, ye + 7), (xe + 7, ye - 7)], fill=NAVY, width=4)
    dr.text((xe + 10, ye - 8), f"EXIT {s['exit_t']:%H:%M} ({s['how']})", font=fb, fill=NAVY)
    # header + verdict
    dow = d.strftime("%a %Y-%m-%d")
    dr.text((L, 14), f"{s['market']} · {dow} · BIG GAP {'UP' if s['gap'] > 0 else 'DOWN'} {abs(s['gap']):,.1f} points = {s['size']:.2f}x the normal daily range", font=fh, fill=TXT)
    plan = f"Rule: gap is {s['size']:.2f}x (needs 0.70x) and still unfilled at 09:45, so fade it: {'SHORT' if s['side'] < 0 else 'LONG'} toward yesterday's close {s['pc']:,.1f}."
    dr.text((L, 52), plan, font=f, fill=MUTE)
    win = s["r"] > 0
    verdict = f"RESULT: {'WIN' if win else 'LOSS'} {s['r']:+.2f}R  ·  {s['how']}  ·  stopped out would have been -1.00R, full target {abs(s['target'] - s['entry']) / abs(s['entry'] - s['stop']):+.2f}R"
    dr.rectangle([L, 84, W - R, 118], fill=(222, 242, 222) if win else (250, 222, 222))
    dr.text((L + 10, 91), verdict, font=fb, fill=GREEN if win else RED)
    dr.text((L, H - 28), "5-minute candles, New York time. Orange dashed = yesterday's 16:00 close (the target). Green box = target zone, red box = stop zone, "
                         "x = where the trade ended. Before spread and commission.", font=fs, fill=MUTE)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{s['market']}_{d:%Y-%m-%d}.png")
    img.save(path)
    return path


def main(argv=None) -> int:  # pragma: no cover
    args = argv if argv is not None else sys.argv[1:]
    mkts = [args[0].upper()] if args else ["ES", "NQ"]
    count = int(args[1]) if len(args) > 1 else 12
    p1_syms = {"ES": "ES", "NQ": "NQ"}
    rows: List[str] = []
    for m in mkts:
        df = p1.load(p1_syms[m], "M1")
        df = df[df.index >= pd.Timestamp("2023-03-01")]
        sl = setups(m, df)[-count:]
        for s in sl:
            path = chart(s, df)
            rows.append(f"| {m} | {s['day']:%a %Y-%m-%d} | {'up' if s['gap'] > 0 else 'down'} {abs(s['gap']):,.1f} ({s['size']:.2f}x) | {'SHORT' if s['side'] < 0 else 'LONG'} toward {s['pc']:,.1f} | "
                        f"{'WIN' if s['r'] > 0 else 'LOSS'} {s['r']:+.2f}R | {s['how']} | [{os.path.basename(path)}]({os.path.basename(path)}) |")
            print(path)
    with open(os.path.join(OUT, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write("# Big-gap fade: recent setups\n\n| Market | Day | Gap | Trade | Result | Ended by | Chart |\n|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
