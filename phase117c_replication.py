"""Phase 117c — does the big-gap fade replicate on OTHER US indices? (US30 Dow, US2000 Russell 2000)

Research only. Phase 117's effect (fade a 09:30 gap >= 0.7x the prior-14-day range toward the
previous close, from 09:45, exit 12:00) exists in NQ/ES in 2025-26 and not in 2023-24, and the
2025-26 data is no longer a clean holdout. A different instrument is a cleaner test than another
time split: it shares the regime but not the instrument's own noise.

Pre-registered: same rules and costs logic as Phase 117 (US30 slippage 1.0 pt, US2000 0.1 pt;
spread from the bars, scaled by each symbol's point size: US30 0.01, US2000 0.1).
REPLICATES = in BOTH US30 and US2000 the 2025-26 mean R after costs is > 0 for stop A and the raw
drift toward the previous close (gap >= 0.7, 09:45 -> 12:00) has t > 2. What 2023-24 does is
reported, not required.

    python -m phase117c_replication
"""
from __future__ import annotations
import json, os, sys
import numpy as np
import pandas as pd
import phase101_ny_open_sweep as p1
import phase117_gap_fill as g17
import phase117b_gap_drift as d17

p1.SYMBOLS.update({"DJ": "US30", "RUT": "US2000"})
p1.SLIPPAGE.update({"DJ": 1.0, "RUT": 0.1})
POINTS = {"DJ": 0.01, "RUT": 0.1}
MARKETS = ("DJ", "RUT")
_orig_load = p1.load


def _load(symbol, tf):
    p1.POINT = POINTS.get(symbol, 0.01)
    try:
        return _orig_load(symbol, tf)
    finally:
        p1.POINT = 0.01


p1.load = _load
g17.MARKETS = d17.MARKETS = MARKETS
g17.TAG = d17.TAG = "_replication"


def main(argv=None) -> int:
    res = g17.run()
    drift = d17.run()
    df = pd.read_csv(os.path.join(g17.OUT, "phase117_trades_replication.csv"), dtype={"entry": str})
    df["yr"] = df.day.str[:4]
    out = {"cells": res["cells"], "drift": drift, "by_year": {}}
    print("== big gap (>=0.7), entry 09:45 ==")
    for m in MARKETS:
        for stop in ("A", "B"):
            x = df[(df.market == m) & (df.bucket == "big") & (df.entry == "0945") & (df.stop == stop)]
            ex, co = x[x.day <= "2024-12-31"], x[x.day > "2024-12-31"]
            yrs = {y: (len(g), round(float(g.r.mean()), 3)) for y, g in x.groupby("yr")}
            out["by_year"][f"{m}|{stop}"] = yrs
            print(f"{m} stop {stop}: n={len(x)} win={float((x.r > 0).mean()):.0%} mean={x.r.mean():+.3f}R total={x.r.sum():+.1f}R | 2023-24 {ex.r.mean():+.3f} (n={len(ex)}) | 2025-26 {co.r.mean():+.3f} (n={len(co)}) | by year {yrs}")
    print("\n== raw drift toward the previous close, entry 09:45 ==")
    ok = []
    for r in drift:
        if r["entry"] == "0945" and r["exit"] in ("12:00", "13:30") and r["thresh"] in (0.5, 0.7, 1.0):
            print(f"gap>={r['thresh']} {r['market']:<4}{r['exit']} {r['period']}  n={r['n']:<4} drift={r['mean_drift_atr']:+.3f} ATR  t={r['t']:+.1f}  toward {r['toward_fill_share']:.0%}")
    for m in MARKETS:
        a = df[(df.market == m) & (df.bucket == "big") & (df.entry == "0945") & (df.stop == "A") & (df.day > "2024-12-31")].r.mean()
        t = next((r["t"] for r in drift if r["market"] == m and r["thresh"] == 0.7 and r["entry"] == "0945" and r["exit"] == "12:00" and r["period"] == "2025-26"), 0)
        ok.append(bool(a > 0 and t > 2))
        print(f"{m}: 2025-26 stop-A mean {a:+.3f}R, drift t={t:+.1f} -> {'ok' if ok[-1] else 'no'}")
    out["replicates"] = bool(all(ok))
    print("\nREPLICATES:", out["replicates"])
    with open(os.path.join(g17.OUT, "phase117c_result.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
