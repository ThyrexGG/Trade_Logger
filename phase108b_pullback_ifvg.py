"""Phase 108b — the user's measured pattern as a bot: pullback IFVG, re-entries.

Research only. Rules come from what the user's own 18 NQ/ES trades share
(phase108_my_pattern) and their stated management, fixed before any result:

  Window    entries 09:40-10:30 New York (user: 11-53 min after the open); flat 12:00.
  Signal    a 1-minute fair value gap whose third bar formed within the last 4
            minutes is CLOSED THROUGH (bullish gap: close below its bottom ->
            SHORT; bearish gap: close above its top -> LONG); entry at that close.
  Stop      beyond the pullback extreme: highest high (short) / lowest low (long)
            of the last 10 minutes, plus the buffer.
  Exits     half at +1R; rest at the nearest opposite live liquidity level
            >= 1.5R (cap 6R; none -> 3R); flat 12:00. One position at a time,
            max 3 trades per day per market.
  Direction ANY, or MORNING = only in the direction of (price now - 09:30 open).
  Attempts  ALL signals, or REENTRY = only a signal that comes after an earlier
            same-direction signal that morning (taken or not) which lost.
  Markets   NQ, ES (1-minute, 2023-04 -> 2026-10), bar spread + slippage.
  Cells     2 markets x 2 directions x 2 attempt rules = 8.
  PASS      mean R > 0 with 95% CI above 0 (Bonferroni over 8 for a claim), >= 3 of
            4 years positive, better than the mirrored opposite trade (p < 0.05).

    python -m phase108b_pullback_ifvg
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
import phase106_follow_sweep as p6
import phase107_ifvg_model as p7

INV_WITHIN = 4
PULLBACK_MIN = 10
MAX_TRADES = 3
OUT = os.path.join(p1.CACHE, "phase108")


def _signals(m: pd.DataFrame, i0: int, i_last: int) -> List[tuple]:
    """(bar, direction) for every pullback-gap inversion in [i0, i_last)."""
    h, l, c = m["high"].to_numpy(), m["low"].to_numpy(), m["close"].to_numpy()
    out = []
    for i in range(i0, i_last):
        for k in range(max(2, i - INV_WITHIN), i):
            if h[k - 2] < l[k]:  # bullish gap (bottom h[k-2]) closed below -> short
                bottom = h[k - 2]
                if c[i] < bottom and all(c[q] >= bottom for q in range(k + 1, i)):
                    out.append((i, -1))
                    break
            if l[k - 2] > h[k]:  # bearish gap (top l[k-2]) closed above -> long
                top = l[k - 2]
                if c[i] > top and all(c[q] <= top for q in range(k + 1, i)):
                    out.append((i, 1))
                    break
    return out


def _day(symbol: str, df: pd.DataFrame, day: pd.Timestamp, ctx, prev_d, dir_mode: str, attempt_mode: str) -> List[dict]:
    t930 = day + pd.Timedelta(hours=9, minutes=30)
    m = df.loc[day + pd.Timedelta(hours=4): day + pd.Timedelta(hours=12) - pd.Timedelta(seconds=1)]
    idx = m.index
    if idx.searchsorted(t930) >= len(m):
        return []
    o, h, l, cl, spr = (m[x].to_numpy() for x in ("open", "high", "low", "close", "spread"))
    i930 = idx.searchsorted(t930)
    i0, i_last, i_end = idx.searchsorted(day + pd.Timedelta(hours=9, minutes=40)), idx.searchsorted(day + pd.Timedelta(hours=10, minutes=30)), len(m)
    if i_last - i0 < 40:
        return []
    open930 = o[i930]
    levels = p4._levels(df, day, ctx, prev_d)
    slip, buf = p1.SLIPPAGE[symbol], p4.BUFFER[symbol]
    trades: List[dict] = []
    busy_until = -1
    # earlier signals today (taken or not): (direction, bar at which its LOSS became known).
    # A loss only counts once the stop has actually been hit -- never before.
    losses_known: List[tuple] = []
    for i, side in _signals(m, i0, i_last):
        entry = cl[i]
        ext = h[max(0, i - PULLBACK_MIN): i + 1].max() if side < 0 else l[max(0, i - PULLBACK_MIN): i + 1].min()
        stop = ext + buf if side < 0 else ext - buf
        risk = abs(entry - stop)
        if risk <= 0 or risk < 2 * spr[i]:
            continue
        now = idx[i]
        opp = [x["price"] for x in levels if x["live_from"] <= now and
               ((side > 0 and x["side"] == "H" and entry + p7.TP2_MIN_R * risk <= x["price"] <= entry + p7.TP2_MAX_R * risk) or
                (side < 0 and x["side"] == "L" and entry - p7.TP2_MAX_R * risk <= x["price"] <= entry - p7.TP2_MIN_R * risk))]
        # a level only counts if not already traded through since it formed
        opp = [p for p in opp if not ((side > 0 and m.loc[:now, "high"].iloc[-60:].max() > p) or (side < 0 and m.loc[:now, "low"].iloc[-60:].min() < p))]
        tp2 = (min(opp) if side > 0 else max(opp)) if opp else entry + side * p7.TP2_DEFAULT_R * risk
        g, outcome, mkt = p7._manage(h, l, o, i + 1, i_end, side, entry, stop if side > 0 else stop, tp2)
        cost = float(spr[i]) + slip + slip * mkt
        r = g - cost / risk
        # outcome of the mirrored opposite trade (placebo)
        g2, _, mkt2 = p7._manage(h, l, o, i + 1, i_end, -side, entry, entry + side * risk, entry - side * abs(tp2 - entry))
        r_opp = g2 - (float(spr[i]) + slip + slip * mkt2) / risk
        # bar at which this signal's stop is hit (if it is), i.e. when its loss becomes known
        stop_bar = None
        for k in range(i + 1, i_end):
            if (side > 0 and l[k] <= stop) or (side < 0 and h[k] >= stop):
                stop_bar = k
                break
        eligible = True
        if dir_mode == "MORNING" and np.sign(entry - open930) != side:
            eligible = False
        if attempt_mode == "REENTRY" and not any(d == side and kb < i for d, kb in losses_known):
            eligible = False
        if r < 0 and stop_bar is not None:
            losses_known.append((side, stop_bar))
        taken = eligible and i > busy_until and len(trades) < MAX_TRADES
        if not taken:
            continue
        # exit bar, to keep one position at a time
        exit_bar = stop_bar if stop_bar is not None else i_end - 1
        busy_until = exit_bar
        trades.append({"symbol": symbol, "day": str(day.date()), "time": str(now), "side": side, "entry": round(entry, 2),
                       "stop": round(stop, 2), "risk": round(risk, 2), "tp2_r": round(abs(tp2 - entry) / risk, 2),
                       "outcome": outcome, "r": round(r, 4), "r_opposite": round(r_opp, 4), "attempt": len(trades) + 1})
    return trades


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(108)
    saved = dict(p4.SESSION)
    p4.SESSION.clear()
    p4.SESSION.update(p6.INDEX_SESSION)
    res: Dict = {"phase": "108b", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "cells": {}}
    try:
        for s in ("NQ", "ES"):
            df = p1.load(s, "M1")
            df = df[df.index >= pd.Timestamp("2023-04-01")]
            ctx = p4._daily_context(df)
            days = [d for d in ctx.index if pd.Timestamp(d).weekday() < 5]
            for dmode in ("ANY", "MORNING"):
                for amode in ("ALL", "REENTRY"):
                    rows = []
                    for k in range(1, len(days)):
                        day = pd.Timestamp(days[k])
                        if ctx.loc[days[k], "atr"] != ctx.loc[days[k], "atr"]:
                            continue
                        rows += _day(s, df, day, ctx, days[k - 1], dmode, amode)
                    t = pd.DataFrame(rows)
                    t.to_csv(os.path.join(OUT, f"phase108b_{s}_{dmode}_{amode}.csv"), index=False)
                    rs, opp = t["r"].to_numpy(), t["r_opposite"].to_numpy()
                    st = p1.summarize(rs, rng)
                    st["ci_bonf"] = round(p1._boot_ci(rs, 0.05 / 8, rng)[0], 3) if len(rs) > 1 else None
                    years = {str(y): round(float(g["r"].mean()), 3) for y, g in t.groupby(t["day"].str[:4])} if len(t) else {}
                    p = float((np.array([np.where(rng.integers(0, 2, len(rs)) == 1, rs, opp).mean() for _ in range(2000)]) >= rs.mean()).mean()) if len(rs) >= 10 else float("nan")
                    res["cells"][f"{s} | {dmode} | {amode}"] = {
                        "stats": st, "by_year": years, "opposite_mean": round(float(opp.mean()), 3) if len(opp) else None,
                        "placebo_p": round(p, 4), "trades_per_day": round(len(t) / max(1, t["day"].nunique()), 2) if len(t) else 0,
                        "by_attempt": t.groupby("attempt")["r"].agg(["size", "mean"]).round(3).to_dict() if len(t) else {},
                        "passes": bool(len(rs) and st["ci95"][0] > 0 and sum(v > 0 for v in years.values()) >= 3 and p < 0.05),
                    }
    finally:
        p4.SESSION.clear()
        p4.SESSION.update(saved)
    res["verdict"] = "PASS_FOUND" if any(v["passes"] for v in res["cells"].values()) else "NO_EDGE"
    with open(os.path.join(OUT, "phase108b_result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    print("verdict:", r["verdict"])
    for k, v in r["cells"].items():
        s = v["stats"]
        print(f"{k:<24} N={s.get('n',0):>4} win={s.get('win_rate','-')} mean={s.get('mean_r','-'):>7} ci={s.get('ci95')} opp={v['opposite_mean']} "
              f"p={v['placebo_p']} yrs={v['by_year']} per-day={v['trades_per_day']} attempts={v['by_attempt']} pass={v['passes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
