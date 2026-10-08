"""Phase 110 — a one-trade-a-day plan built only from Phase 109's EXPLORE period.

Research only. Rules fixed from 2023-04..2024 findings (Phase 109: a strong first
30 minutes tended to continue; the pullback-gap signal is the user's entry),
then judged ONLY on 2025-01..2026-10 (CONFIRM):

  1  At 10:00 NY note the first-30-minute move: direction D = sign(close 09:59 -
     open 09:30), size S = |move| / daily ATR.
  2  Take the FIRST pullback-IFVG signal (phase108b) between 10:00 and 11:00 in
     direction D. One trade per day per market.
  3  Stop beyond the 10-minute pullback extreme (+ buffer); half off at +1R, rest
     at the nearest opposite live liquidity >= 1.5R (cap 6R, none -> 3R); flat 12:00.
     Costs: bar spread + slippage.
  Variants: DAILY (every day) and STRONG (only days with S >= 0.3).
  PASS: CONFIRM mean R > 0 with the 95% CI above 0 and both CONFIRM years positive.

    python -m phase110_daily_plan
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
import phase108b_pullback_ifvg as p8

EXPLORE_END = "2024-12-31"
OUT = os.path.join(p1.CACHE, "phase110")


def trades(symbol: str) -> pd.DataFrame:
    df = p1.load(symbol, "M1")
    df = df[df.index >= pd.Timestamp("2023-04-01")]
    p4.SESSION.clear()
    p4.SESSION.update(p6.INDEX_SESSION)
    ctx = p4._daily_context(df)
    days = [d for d in ctx.index if pd.Timestamp(d).weekday() < 5]
    slip, buf = p1.SLIPPAGE[symbol], p4.BUFFER[symbol]
    rows: List[dict] = []
    for k in range(1, len(days)):
        day = pd.Timestamp(days[k])
        atr = ctx.loc[days[k], "atr"]
        if atr != atr:
            continue
        m = df.loc[day + pd.Timedelta(hours=4): day + pd.Timedelta(hours=12) - pd.Timedelta(seconds=1)]
        idx = m.index
        i930, i10, i11 = (idx.searchsorted(day + pd.Timedelta(hours=h, minutes=mi)) for h, mi in ((9, 30), (10, 0), (11, 0)))
        if i11 - i930 < 80:
            continue
        o, h, l, cl, spr = (m[x].to_numpy() for x in ("open", "high", "low", "close", "spread"))
        D = int(np.sign(cl[i10 - 1] - o[i930]))
        S = abs(cl[i10 - 1] - o[i930]) / atr
        if D == 0:
            continue
        sig = next(((i, sd) for i, sd in p8._signals(m, i10, i11) if sd == D), None)
        if sig is None:
            rows.append({"day": str(day.date()), "strong": S >= 0.3, "traded": False, "r": np.nan})
            continue
        i, side = sig
        entry = cl[i]
        ext = h[max(0, i - p8.PULLBACK_MIN): i + 1].max() if side < 0 else l[max(0, i - p8.PULLBACK_MIN): i + 1].min()
        stop = ext + buf if side < 0 else ext - buf
        risk = abs(entry - stop)
        if risk <= 0 or risk < 2 * spr[i]:
            rows.append({"day": str(day.date()), "strong": S >= 0.3, "traded": False, "r": np.nan})
            continue
        now = idx[i]
        lv = p4._levels(df, day, ctx, days[k - 1])
        seen = m.loc[:now]
        opp = [x["price"] for x in lv if x["live_from"] <= now and
               ((side > 0 and x["side"] == "H" and entry + p7.TP2_MIN_R * risk <= x["price"] <= entry + p7.TP2_MAX_R * risk and seen.loc[x["formed"]:, "high"].max() <= x["price"]) or
                (side < 0 and x["side"] == "L" and entry - p7.TP2_MAX_R * risk <= x["price"] <= entry - p7.TP2_MIN_R * risk and seen.loc[x["formed"]:, "low"].min() >= x["price"]))]
        tp2 = (min(opp) if side > 0 else max(opp)) if opp else entry + side * p7.TP2_DEFAULT_R * risk
        g, outcome, mkt = p7._manage(h, l, o, i + 1, len(m), side, entry, stop, tp2)
        r = g - (float(spr[i]) + slip + slip * mkt) / risk
        rows.append({"day": str(day.date()), "strong": S >= 0.3, "traded": True, "time": str(now), "side": side,
                     "risk": round(risk, 2), "outcome": outcome, "r": round(r, 4)})
    return pd.DataFrame(rows)


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(110)
    res: Dict = {"phase": 110, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "cells": {}}
    for s in ("NQ", "ES"):
        t = trades(s)
        t.to_csv(os.path.join(OUT, f"phase110_{s}.csv"), index=False)
        for variant, sel in (("DAILY", lambda x: x), ("STRONG", lambda x: x[x.strong])):
            for per, rng_days in (("EXPLORE", lambda x: x[x.day <= EXPLORE_END]), ("CONFIRM", lambda x: x[x.day > EXPLORE_END])):
                x = rng_days(sel(t))
                tr = x[x.traded]
                st = p1.summarize(tr["r"].to_numpy(), rng)
                years = {str(y): round(float(g["r"].mean()), 3) for y, g in tr.groupby(tr["day"].str[:4])}
                res["cells"][f"{s} | {variant} | {per}"] = {"days": int(len(x)), "trade_days": int(len(tr)),
                                                           "trade_rate": round(len(tr) / max(1, len(x)), 2), "stats": st, "by_year": years,
                                                           "dollars_at_100_risk": round(float(tr["r"].sum()) * 100)}
    for s in ("NQ", "ES"):
        for v in ("DAILY", "STRONG"):
            c = res["cells"][f"{s} | {v} | CONFIRM"]
            c["passes"] = bool(c["stats"].get("n") and c["stats"]["ci95"][0] > 0 and all(y > 0 for y in c["by_year"].values()))
    with open(os.path.join(OUT, "phase110_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    for k, v in r["cells"].items():
        s = v["stats"]
        print(f"{k:<22} trades on {v['trade_days']}/{v['days']} days ({v['trade_rate']:.0%}) win={s.get('win_rate','-')} mean={s.get('mean_r','-')} "
              f"ci={s.get('ci95')} years={v['by_year']} ${v['dollars_at_100_risk']:+,} {('PASS' if v.get('passes') else '') if 'passes' in v else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
