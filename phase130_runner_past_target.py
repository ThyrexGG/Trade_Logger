"""Phase 130 - do NOT cap the winner at yesterday's close: keep a runner and trail it behind 5-minute swings.

The user showed trades that closed at yesterday's close (+0.9R) while price kept going. Same entries as Phases 127-129
(NQ + ES, Mar 2023 - 25 Sep 2026, no time exit, 10 sessions max).
BASE    half at the structure near +1R (L1), stop to breakeven, rest at yesterday's close (Phase 127/129 "HALF_L1").
RUNNER  identical until yesterday's close is reached; then the rest is NOT closed: its stop moves to yesterday's close and
        ratchets behind the latest confirmed 5-minute swing (swing low for a long, swing high for a short) until hit.
LADDER_RUN the user's full description (Phase 129 ladder, thirds at L1/L2, last third runs past yesterday's close)
RUNNER_ALL  no half at L1 at all: the whole position goes to yesterday's close, then the whole position trails.
Stop before target inside one 1-minute bar. R = net P&L / stop distance. EXPLORATORY.

    python -m phase130_runner_past_target
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase129_structure_ladder as p29


def trail_levels(fut: pd.DataFrame, side: int) -> np.ndarray:
    """Per 1-minute bar: latest CONFIRMED 5-minute swing (low for a long, high for a short) known at that minute; nan if none."""
    m5 = fut.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    o, h, l, c = (m5[x].to_numpy() for x in ("open", "high", "low", "close"))
    known, lvl = [], []
    for k in range(1, len(c)):
        if side > 0 and c[k - 1] < o[k - 1] and c[k] > o[k]:
            known.append(m5.index[k] + pd.Timedelta(minutes=5)); lvl.append(min(l[k - 1], l[k]))
        if side < 0 and c[k - 1] > o[k - 1] and c[k] < o[k]:
            known.append(m5.index[k] + pd.Timedelta(minutes=5)); lvl.append(max(h[k - 1], h[k]))
    out = np.full(len(fut), np.nan)
    if not known:
        return out
    known = np.array(known, dtype="datetime64[ns]")
    lvl = np.array(lvl)
    idx = np.searchsorted(known, fut.index.to_numpy().astype("datetime64[ns]"), side="right") - 1
    ok = idx >= 0
    out[ok] = lvl[idx[ok]]
    return out


def runner_sim(side, e, stop, risk, pc, l1, trail, h, l, c, spread, slip):
    """l1: distance of the first partial (half) or None. Returns pnl in points."""
    tdist = abs(pc - e)
    size, banked, cur, tgt_hit = 1.0, 0.0, stop, False
    half_done = l1 is None
    for k in range(len(c)):
        if (side > 0 and l[k] <= cur) or (side < 0 and h[k] >= cur):
            return banked + size * side * (cur - e) - spread - slip * (1 + size)
        if not half_done and ((side > 0 and h[k] >= e + l1) or (side < 0 and l[k] <= e - l1)):
            half_done, banked, size, cur = True, 0.5 * l1, 0.5, e
        if not tgt_hit and ((side > 0 and h[k] >= pc) or (side < 0 and l[k] <= pc)):
            tgt_hit, cur = True, pc  # stop jumps to yesterday's close, the rest keeps running
        if tgt_hit:
            t = trail[k]
            if not np.isnan(t) and ((side > 0 and t > cur) or (side < 0 and t < cur)):
                cur = t
    return banked + size * side * (c[-1] - e) - spread - slip * (1 + size)


def ladder_run_sim(side, e, stop, risk, pc, levels, trail, h, l, c, spread, slip):
    """The user's full description: a third at each of two structure levels (stop to BE after the first, behind L1 after the
    second), the last third runs PAST yesterday's close with the stop at yesterday's close, ratcheting behind 5m swings."""
    tdist = abs(pc - e)
    done = [False, False]
    size, banked, cur, tgt_hit = 1.0, 0.0, stop, False
    for k in range(len(c)):
        if (side > 0 and l[k] <= cur) or (side < 0 and h[k] >= cur):
            return banked + size * side * (cur - e) - spread - slip * (1 + size)
        for j, d in enumerate(levels):
            if not done[j] and ((side > 0 and h[k] >= e + d) or (side < 0 and l[k] <= e - d)):
                done[j], banked, size = True, banked + d / 3.0, size - 1.0 / 3.0
                cur = e if j == 0 else (e + side * levels[0] if not tgt_hit else cur)
        if not tgt_hit and ((side > 0 and h[k] >= pc) or (side < 0 and l[k] <= pc)):
            tgt_hit = True
            # anything not yet scaled out is sold at yesterday's close; one third keeps running
            if size > 1.0 / 3.0 + 1e-9:
                sell = size - 1.0 / 3.0
                banked, size = banked + sell * tdist, 1.0 / 3.0
            cur = max(cur, pc) if side > 0 else min(cur, pc)
        if tgt_hit:
            t = trail[k]
            if not np.isnan(t) and ((side > 0 and t > cur) or (side < 0 and t < cur)):
                cur = t
    return banked + size * side * (c[-1] - e) - spread - slip * (1 + size)


def extra(ctx):
    side, e, pc, risk = ctx["side"], ctx["e"], ctx["pc"], ctx["risk"]
    trail = trail_levels(ctx["fut"], side)
    lv = ctx["lv"]
    args = (side, e, ctx["stop"], risk, pc)
    tail = (trail, ctx["h"], ctx["l"], ctx["c"], ctx["spread"], ctx["slip"])
    return {
        "RUNNER": runner_sim(*args, lv[0] if lv else None, *tail) / risk,
        "RUNNER_ALL": runner_sim(*args, None, *tail) / risk,
        "LADDER_RUN": (ladder_run_sim(*args, lv, *tail) / risk) if lv else runner_sim(*args, None, *tail) / risk,
    }


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(130)
    for thr in (0.2, 0.7):
        d = p29.run(thr, extra)
        d = d[d["mode"].isin(["PLAIN", "HALF_L1", "RUNNER", "RUNNER_ALL", "LADDER", "LADDER_RUN"])]
        d.to_csv(p1.CACHE + f"/phase130_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range, NQ + ES pooled =====")
        print(f"{'stop':<9}{'mode':<11}{'n':>5}{'win%':>6}{'avgR':>8}{'95% interval':>18}{'PF':>6}{'totalR':>8}{'max win R':>10}")
        for (s, m), g in d.groupby(["stop", "mode"], sort=False):
            r = g.r.to_numpy()
            boot = rng.choice(r, size=(2000, len(r)), replace=True).mean(axis=1)
            gl = -r[r < 0].sum()
            print(f"{s:<9}{m:<11}{len(r):>5}{(r > 0).mean() * 100:>5.0f}%{r.mean():>+8.3f}   [{np.quantile(boot, .025):+.2f}, {np.quantile(boot, .975):+.2f}]{(r[r > 0].sum() / gl if gl else float('nan')):>6.2f}{r.sum():>+8.1f}{r.max():>10.1f}")
        d["year"] = d.day.str[:4]
        print("\n-- per year avgR: RUNNER vs HALF_L1 --")
        print(d[d["mode"].isin(["RUNNER", "HALF_L1"])].groupby(["stop", "mode", "year"]).r.mean().unstack("year").round(3).to_string())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
