"""Phase 106 — FOLLOW the sweep (breakout / continuation) with a trend filter.

Research only. The user's own NQ trades mostly went WITH the sweep (a high is
taken -> long), the opposite of the fade studied in Phases 101-105. This is
that style, mirroring the TradingView indicator's "Follow the sweep" mode.
Pre-registered before any result:

  Levels    as Phase 104 (prev day/week, overnight, Asia, London, opening range,
            5m/15m swing highs/lows incl. ones formed in the session); a level
            is liquidity until first breached.
  Setup     a level is breached (high side) and, within 15 minutes, a 1-minute
            bar CLOSES above the highest level breached -> LONG at that close.
            Stop: below the lowest low of the 3 minutes before the sweep, minus
            the buffer. Mirror for lows -> SHORT. Target 2R; flat at the session
            flat time. Costs: bar spread + slippage on market fills + commission.
  Trend     three variants: NONE; H1 = 1-hour swing structure at session start
            (trade only with it; mixed -> none); DAILY = previous close vs its
            20-day average (trade only with it).
  Per day   the first qualifying setup per instrument.
  Markets   NQ, ES (NY 08:30-11:00, flat 12:00); FX pairs (USDJPY, GBPUSD,
            GBPJPY, EURUSD, EURJPY) in LONDON (02:00-05:00, flat 07:00) and
            NY (08:00-11:00, flat 12:00), pooled per session.
  Cells     {NQ, ES, FX-London, FX-NY} x {NONE, H1, DAILY} = 12.
  PASS      pooled mean R > 0 with the 95% CI above 0 (Bonferroni over 12 for a
            claim), positive in >= 3 of the 4 calendar years 2023-2026, and
            better than trading the OPPOSITE direction at the same entries
            (direction placebo, p < 0.05).

    python -m phase106_follow_sweep
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4
import phase105_fx_selection as p5

CONFIRM_MIN = 15
TARGET_R = 2.0
TRENDS = ("NONE", "H1", "DAILY")
OUT = os.path.join(p1.CACHE, "phase106")
INDEX_SESSION = {"start": (8, 30), "last_entry": (11, 0), "flat": (12, 0), "anchor": (9, 30),
                 "coverage": ((9, 30), (11, 0)), "daily": "rth"}


def _setups(symbol: str, df: pd.DataFrame) -> List[dict]:
    """Every follow-the-sweep setup (both sides) in the current p4.SESSION."""
    ctx = p4._daily_context(df)
    ctx["sma20_prev"] = ctx["close"].rolling(20).mean().shift(1)
    days = [d for d in ctx.index if pd.Timestamp(d).weekday() < 5]
    a, b = p4.SESSION["coverage"]
    need = 0.85 * (b[0] * 60 + b[1] - a[0] * 60 - a[1])
    rows: List[dict] = []
    slip, buf, com = p1.SLIPPAGE[symbol], p4.BUFFER[symbol], p4.COMMISSION.get(symbol, 0.0)
    for k in range(1, len(days)):
        day_d, prev_d = days[k], days[k - 1]
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
        if i_last - i0 < 30 or i0 < 3:
            continue
        h1 = p4._h1_bias(df, t0)
        prev_close = ctx["close"].shift(1).loc[day_d]
        dly = 0 if c["sma20_prev"] != c["sma20_prev"] else (1 if prev_close > c["sma20_prev"] else -1)
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
            for sc in ("H", "L"):
                hit = [x for x in live if x["side"] == sc and ((sc == "H" and h[i] > x["price"]) or (sc == "L" and l[i] < x["price"]))]
                if not hit:
                    continue
                for x in hit:
                    live.remove(x)
                side = 1 if sc == "H" else -1  # follow: high taken -> long
                lvl = max(x["price"] for x in hit) if side > 0 else min(x["price"] for x in hit)
                base = l[i - 3:i].min() if side > 0 else h[i - 3:i].max()
                for j in range(i, min(i + CONFIRM_MIN, i_last)):
                    if (side > 0 and cl[j] > lvl) or (side < 0 and cl[j] < lvl):
                        entry = cl[j]
                        stop = base - buf if side > 0 else base + buf
                        risk = abs(entry - stop)
                        if risk <= 0 or risk < 2 * spr[j] or (side > 0 and stop >= entry) or (side < 0 and stop <= entry):
                            break
                        res = {}
                        for sd in (side, -side):  # the trade, and the opposite trade at the same moment (placebo)
                            st = entry - sd * risk
                            tg = entry + sd * TARGET_R * risk
                            kk, px, reason = p1._simulate_exit(h, l, o, idx, j + 1, min(i_end, len(m)), sd, entry, st, tg, None)
                            cost = float(spr[j]) + slip + (slip if reason in ("stop", "time") else 0.0) + com
                            res[sd] = ((sd * (px - entry) - cost) / risk, reason)
                        rows.append({
                            "symbol": symbol, "day": str(day.date()), "time": str(idx[j]), "side": side,
                            "family": min((x["family"] for x in hit), key=lambda f: p4.RANK[f]),
                            "entry": round(entry, 6), "stop": round(stop, 6), "risk": round(risk, 6),
                            "h1": h1, "daily": dly, "r": round(res[side][0], 4), "exit": res[side][1],
                            "r_opposite": round(res[-side][0], 4),
                        })
                        break
    return rows


def _cell(c: pd.DataFrame, trend: str, rng) -> Dict:
    if trend == "H1":
        c = c[c.side == c.h1]
    elif trend == "DAILY":
        c = c[c.side == c.daily]
    first = c.sort_values("time").groupby(["day", "symbol"], as_index=False).head(1)
    rs, opp = first["r"].to_numpy(), first["r_opposite"].to_numpy()
    st = p1.summarize(rs, rng)
    if len(rs) > 1:
        lo, _ = p1._boot_ci(rs, 0.05 / 12, rng)
        st["ci_bonf_12"] = round(lo, 3)
    years = {str(y): round(float(g["r"].mean()), 3) for y, g in first.groupby(first["day"].str[:4])}
    ny = {str(y): int(len(g)) for y, g in first.groupby(first["day"].str[:4])}
    if len(rs) >= 10:
        sims = np.array([np.where(rng.integers(0, 2, len(rs)) == 1, rs, opp).mean() for _ in range(2000)])
        p = float((sims >= rs.mean()).mean())
    else:
        p = float("nan")
    passed = bool(len(rs) and st["ci95"][0] > 0 and sum(v > 0 for v in years.values()) >= 3 and p < 0.05)
    return {"stats": st, "by_year": years, "n_by_year": ny, "opposite_mean": round(float(opp.mean()), 3) if len(opp) else None,
            "placebo_p": round(p, 4), "passes": passed, "exits": first["exit"].value_counts().to_dict()}


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(106)
    res: Dict = {"phase": 106, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "cells": {}}
    saved = dict(p4.SESSION)
    groups: Dict[str, pd.DataFrame] = {}
    try:
        # indices
        p4.SESSION.clear()
        p4.SESSION.update(INDEX_SESSION)
        for s in ("NQ", "ES"):
            df = p1.load(s, "M1")
            df = df[df.index >= pd.Timestamp("2023-04-01")]
            groups[s] = pd.DataFrame(_setups(s, df))
        # FX
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
    for g, c in groups.items():
        c.to_csv(os.path.join(OUT, f"phase106_setups_{g}.csv"), index=False)
        for t in TRENDS:
            res["cells"][f"{g} | {t}"] = _cell(c, t, rng)
    res["verdict"] = "PASS_FOUND" if any(v["passes"] for v in res["cells"].values()) else "NO_EDGE"
    with open(os.path.join(OUT, "phase106_result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    print("verdict:", r["verdict"])
    for k, v in r["cells"].items():
        s = v["stats"]
        print(f"{k:<18} N={s.get('n',0):>4} win={s.get('win_rate','-')} mean={s.get('mean_r','-'):>7} ci={s.get('ci95')} "
              f"opposite={v['opposite_mean']} p={v['placebo_p']} years={v['by_year']} pass={v['passes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
