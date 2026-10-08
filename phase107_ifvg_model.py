"""Phase 107 — the user's IFVG model: sweep -> inverted FVG -> respected gap entry.

Research only. Rules as the user described them (2026-10-09), fixed before any
result. Long example; shorts are the mirror image.

  1 Sweep       a live liquidity low is breached (Phase 104 levels: previous
                day/week, overnight, Asia, London, opening range, 5m/15m swings).
  2 Inversion   a BEARISH 1-minute FVG formed in the 30 minutes before the sweep
                (up to the sweep low) is CLOSED THROUGH (a close above its top)
                within 30 minutes of the sweep -> the inverted FVG (IFVG).
  3 Entry       GAP:  the next BULLISH 1-minute FVG formed after the sweep low;
                      price trades back into it and the bar closes at/above its
                      bottom (respected) -> buy at that close.
                IFVG: the same, but on the inverted gap itself.
                A close below the zone's bottom, a new low below the sweep low, or
                30 minutes without a touch cancels the setup.
  4 Stop        SWEEP: below the sweep low.  2ND: below the "2nd low", the lowest
                low between the sweep low and the inversion bar (a higher low).
  5 Exits       half at +1R; the rest at the nearest opposite live liquidity
                level >= 1.5R away (cap 6R; none -> 3R); stop unchanged; flat at
                the session's flat time.
  6 Equilibrium dealing range = sweep low .. highest high of the 60 minutes before
                the sweep; "aligned" = longs entered at/below its 50%, shorts at/above.
Costs: bar spread + slippage per market fill + commission (FX $5/lot).
Markets/sessions: NQ, ES (08:30-11:00, flat 12:00); FX pairs London (02:00-05:00,
flat 07:00) and NY (08:00-11:00, flat 12:00), pooled per session.
Cells: 4 market groups x 2 entries x 2 stops x {ALL, EQ-ALIGNED} = 32.
PASS: pooled mean R > 0 with 95% CI above 0 (Bonferroni over 32 for a claim),
>= 3 of 4 years positive, and better than the opposite direction at the same
entries with the same stop/targets mirrored (placebo p < 0.05).

    python -m phase107_ifvg_model
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4
import phase105_fx_selection as p5
import phase106_follow_sweep as p6

LOOKBACK_MIN = 30      # bearish FVGs formed this long before the sweep can be inverted
INVERT_MIN = 30        # inversion must happen within this many minutes of the sweep
TOUCH_MIN = 30         # entry must come within this many minutes of the inversion
TP1_R, TP1_SIZE = 1.0, 0.5
TP2_MIN_R, TP2_MAX_R, TP2_DEFAULT_R = 1.5, 6.0, 3.0
ENTRIES = ("GAP", "IFVG")
STOPS = ("SWEEP", "2ND")
OUT = os.path.join(p1.CACHE, "phase107")


def _manage(h, l, o, start, end, side, entry, stop, tp2) -> tuple:
    """Half at +1R, rest at tp2, stop fixed, flat at `end`. Returns (gross R, outcome, market-exit fraction)."""
    risk = abs(entry - stop)
    tp1 = entry + side * TP1_R * risk

    def thru(k, px, fav):
        if fav:
            return h[k] >= px if side > 0 else l[k] <= px
        return l[k] <= px if side > 0 else h[k] >= px

    took = False
    for k in range(start, end):
        if thru(k, stop, False):
            return (TP1_SIZE * TP1_R - (1 - TP1_SIZE)) if took else -1.0, ("tp1+stop" if took else "stop"), (1 - TP1_SIZE) if took else 1.0
        if not took and thru(k, tp1, True):
            took = True
        if took and thru(k, tp2, True):
            return TP1_SIZE * TP1_R + (1 - TP1_SIZE) * abs(tp2 - entry) / risk, "tp1+tp2", 0.0
    px = o[end] if end < len(o) else o[end - 1]
    rem = side * (px - entry) / risk
    if took:
        return TP1_SIZE * TP1_R + (1 - TP1_SIZE) * rem, "tp1+time", 1 - TP1_SIZE
    return rem, "time", 1.0


def _setups(symbol: str, df: pd.DataFrame) -> List[dict]:
    ctx = p4._daily_context(df)
    days = [d for d in ctx.index if pd.Timestamp(d).weekday() < 5]
    a, b = p4.SESSION["coverage"]
    need = 0.85 * (b[0] * 60 + b[1] - a[0] * 60 - a[1])
    slip, buf, com = p1.SLIPPAGE[symbol], p4.BUFFER[symbol], p4.COMMISSION.get(symbol, 0.0)
    rows: List[dict] = []
    for kd in range(1, len(days)):
        day_d, prev_d = days[kd], days[kd - 1]
        day = pd.Timestamp(day_d)
        c = ctx.loc[day_d]
        if c["atr"] != c["atr"]:
            continue
        if len(df.loc[p4._t(day, a): p4._t(day, b) - pd.Timedelta(seconds=1)]) < need:
            continue
        t0, tl, tf = (p4._t(day, p4.SESSION[x]) for x in ("start", "last_entry", "flat"))
        m = df.loc[t0 - pd.Timedelta(hours=4, minutes=30): tf - pd.Timedelta(seconds=1)]
        idx = m.index
        o, h, l, cl, spr = (m[x].to_numpy() for x in ("open", "high", "low", "close", "spread"))
        i0, i_last, i_end = idx.searchsorted(t0), idx.searchsorted(tl), idx.searchsorted(tf)
        if i_last - i0 < 30 or i0 < LOOKBACK_MIN + 3:
            continue
        h1 = p4._h1_bias(df, t0)
        levels = p4._levels(df, day, ctx, prev_d)
        live = [x for x in levels if x["live_from"] <= t0]
        pending = sorted([x for x in levels if x["live_from"] > t0], key=lambda x: x["live_from"])
        for i in range(i0, i_last):
            now = idx[i]
            while pending and pending[0]["live_from"] <= now:
                x = pending.pop(0)
                seg = m.loc[x["formed"]: now - pd.Timedelta(seconds=1)]
                if not (len(seg) and ((x["side"] == "H" and seg["high"].max() > x["price"]) or (x["side"] == "L" and seg["low"].min() < x["price"]))):
                    live.append(x)
            for sc in ("L", "H"):
                hit = [x for x in live if x["side"] == sc and ((sc == "L" and l[i] < x["price"]) or (sc == "H" and h[i] > x["price"]))]
                if not hit:
                    continue
                for x in hit:
                    live.remove(x)
                side = 1 if sc == "L" else -1  # a LOW swept -> look for a long
                for setup in _after_sweep(symbol, side, i, idx, o, h, l, cl, spr, i_last, i_end, live, slip, buf, com):
                    setup.update({"symbol": symbol, "day": str(day.date()), "h1": h1,
                                  "family": min((x["family"] for x in hit), key=lambda f: p4.RANK[f])})
                    rows.append(setup)
    return rows


def _after_sweep(symbol, side, i, idx, o, h, l, cl, spr, i_last, i_end, live, slip, buf, com) -> List[dict]:
    n = len(idx)
    # sweep extreme: keep extending while price keeps making new lows, up to the inversion
    # opposing FVGs formed in the LOOKBACK before the sweep (bearish for a long)
    zones = []
    for k in range(max(2, i - LOOKBACK_MIN), i + 1):
        if side > 0 and l[k - 2] > h[k]:
            zones.append((h[k], l[k - 2]))      # (bottom, top)
        if side < 0 and h[k - 2] < l[k]:
            zones.append((h[k - 2], l[k]))      # (bottom, top) of a bullish gap, inverted by a close BELOW its bottom
    if not zones:
        return []
    ext_i = i
    inv = None
    for j in range(i, min(i + INVERT_MIN + 1, i_last)):
        if (side > 0 and l[j] < l[ext_i]) or (side < 0 and h[j] > h[ext_i]):
            ext_i = j
        hitz = [z for z in zones if (side > 0 and cl[j] > z[1]) or (side < 0 and cl[j] < z[0])]
        if hitz and j > ext_i - 1:
            inv = (j, min(hitz, key=lambda z: z[1]) if side > 0 else max(hitz, key=lambda z: z[0]))
            break
    if inv is None:
        return []
    v, ifvg = inv
    ext = l[ext_i] if side > 0 else h[ext_i]
    second = (l[ext_i + 1: v + 1].min() if side > 0 else h[ext_i + 1: v + 1].max()) if v > ext_i else ext
    pre = slice(max(0, i - 60), i)
    eq_mid = (ext + h[pre].max()) / 2 if side > 0 else (ext + l[pre].min()) / 2
    out = []
    for entry_kind in ("GAP", "IFVG"):
        hit = _entry(side, entry_kind, ext_i, v, ifvg, ext, h, l, cl, i_last)
        if hit is None:
            continue
        j, entry = hit
        for stop_kind in ("SWEEP", "2ND"):
            base = ext if stop_kind == "SWEEP" else second
            stop = base - buf if side > 0 else base + buf
            risk = abs(entry - stop)
            if risk <= 0 or risk < 2 * spr[j] or (side > 0 and stop >= entry) or (side < 0 and stop <= entry):
                continue
            opp = [x["price"] for x in live if (side > 0 and x["side"] == "H" and entry + TP2_MIN_R * risk <= x["price"] <= entry + TP2_MAX_R * risk)
                   or (side < 0 and x["side"] == "L" and entry - TP2_MAX_R * risk <= x["price"] <= entry - TP2_MIN_R * risk)]
            tp2 = (min(opp) if side > 0 else max(opp)) if opp else entry + side * TP2_DEFAULT_R * risk
            res = {}
            for sd in (side, -side):  # the trade, and the mirrored opposite trade (placebo)
                st = entry - sd * risk
                t2 = entry + sd * abs(tp2 - entry)
                g, outc, mkt = _manage(h, l, o, j + 1, min(i_end, n), sd, entry, st, t2)
                cost = float(spr[j]) + slip + slip * mkt + com
                res[sd] = (g - cost / risk, outc)
            out.append({"time": str(idx[j]), "side": side, "entry_kind": entry_kind, "stop_kind": stop_kind,
                        "entry": round(entry, 6), "stop": round(stop, 6), "risk": round(risk, 6), "tp2_r": round(abs(tp2 - entry) / risk, 2),
                        "eq_aligned": int((side > 0 and entry <= eq_mid) or (side < 0 and entry >= eq_mid)),
                        "r": round(res[side][0], 4), "exit": res[side][1], "r_opposite": round(res[-side][0], 4)})
    return out


def _entry(side, kind, ext_i, v, ifvg, ext, h, l, cl, i_last) -> Optional[tuple]:
    """First bar after the inversion that trades into the zone and closes respecting it."""
    for j in range(v + 1, min(v + 1 + TOUCH_MIN, i_last)):
        if (side > 0 and l[j] < ext) or (side < 0 and h[j] > ext):
            return None  # the sweep extreme broke: idea invalid
        if kind == "IFVG":
            zone = ifvg
        else:
            gaps = [(h[k - 2], l[k]) for k in range(ext_i + 2, j) if side > 0 and h[k - 2] < l[k]] + \
                   [(h[k], l[k - 2]) for k in range(ext_i + 2, j) if side < 0 and l[k - 2] > h[k]]
            if not gaps:
                continue
            zone = gaps[-1]  # the most recent gap in the new direction
        bottom, top = zone
        if side > 0 and l[j] <= top:
            if cl[j] < bottom:
                return None  # not respected
            return j, cl[j]
        if side < 0 and h[j] >= bottom:
            if cl[j] > top:
                return None
            return j, cl[j]
    return None


def _cell(c: pd.DataFrame, rng, n_cells: int) -> Dict:
    first = c.sort_values("time").groupby(["day", "symbol"], as_index=False).head(1)
    rs, opp = first["r"].to_numpy(), first["r_opposite"].to_numpy()
    st = p1.summarize(rs, rng)
    if len(rs) > 1:
        st["ci_bonf"] = round(p1._boot_ci(rs, 0.05 / n_cells, rng)[0], 3)
    years = {str(y): round(float(g["r"].mean()), 3) for y, g in first.groupby(first["day"].str[:4])}
    p = float((np.array([np.where(rng.integers(0, 2, len(rs)) == 1, rs, opp).mean() for _ in range(2000)]) >= rs.mean()).mean()) if len(rs) >= 10 else float("nan")
    passed = bool(len(rs) and st["ci95"][0] > 0 and sum(v > 0 for v in years.values()) >= 3 and p < 0.05)
    return {"stats": st, "by_year": years, "opposite_mean": round(float(opp.mean()), 3) if len(opp) else None,
            "placebo_p": round(p, 4), "passes": passed, "exits": first["exit"].value_counts().to_dict(),
            "h1_aligned_mean": round(float(first[first.side == first.h1]["r"].mean()), 3) if (first.side == first.h1).any() else None}


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(107)
    groups: Dict[str, pd.DataFrame] = {}
    saved = dict(p4.SESSION)
    try:
        p4.SESSION.clear()
        p4.SESSION.update(p6.INDEX_SESSION)
        for s in ("NQ", "ES"):
            df = p1.load(s, "M1")
            groups[s] = pd.DataFrame(_setups(s, df[df.index >= pd.Timestamp("2023-04-01")]))
        fx = {s: p5.load(s) for s in p5.PAIRS}
        for s in p5.PAIRS:
            p1.SLIPPAGE[s] = 0.2 * p5.PIP[s]
            p4.BUFFER[s] = 0.5 * p5.PIP[s]
            p4.COMMISSION[s] = p5.COMMISSION_PIPS[s] * p5.PIP[s]
        for sess in ("LONDON", "NY"):
            p4.SESSION.clear()
            p4.SESSION.update(p5.SESSIONS[sess])
            groups[f"FX-{sess}"] = pd.DataFrame([r for s in p5.PAIRS for r in _setups(s, fx[s])])
    finally:
        p4.SESSION.clear()
        p4.SESSION.update(saved)
    res: Dict = {"phase": 107, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "cells": {}}
    n_cells = len(groups) * len(ENTRIES) * len(STOPS) * 2
    for g, c in groups.items():
        c.to_csv(os.path.join(OUT, f"phase107_setups_{g}.csv"), index=False)
        if c.empty:
            continue
        for e in ENTRIES:
            for s in STOPS:
                sub = c[(c.entry_kind == e) & (c.stop_kind == s)]
                res["cells"][f"{g} | {e} | stop {s} | ALL"] = _cell(sub, rng, n_cells)
                res["cells"][f"{g} | {e} | stop {s} | EQ"] = _cell(sub[sub.eq_aligned == 1], rng, n_cells)
    res["verdict"] = "PASS_FOUND" if any(v["passes"] for v in res["cells"].values()) else "NO_EDGE"
    with open(os.path.join(OUT, "phase107_result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    print("verdict:", r["verdict"])
    for k, v in r["cells"].items():
        s = v["stats"]
        print(f"{k:<34} N={s.get('n',0):>4} win={s.get('win_rate','-')} mean={s.get('mean_r','-'):>7} ci={s.get('ci95')} "
              f"opp={v['opposite_mean']} p={v['placebo_p']} yrs={v['by_year']} h1={v['h1_aligned_mean']} pass={v['passes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
