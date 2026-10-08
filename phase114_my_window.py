"""Phase 114 — every strategy so far, restricted to the user's own trading window.

Research only. The user watches the 09:30 open without trading and mostly stops
taking trades after 10:30-11:00. That window is their stated practice, fixed
before this run:
  PRIMARY   entries 09:45-10:30 New York
  SECONDARY entries 09:45-11:00 New York
Each strategy's first in-window entry per day is re-scored with every management
plan (phase112.manage); results per year, and the plan choice made on 2023-24
judged on 2025-26 (same pass bar as Phase 112).

    python -m phase114_my_window
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase112_manage as p12

WINDOWS = {"09:45-10:30": ("09:45", "10:30"), "09:45-11:00": ("09:45", "11:00")}
OUT = os.path.join(p1.CACHE, "phase114")


def _sets() -> Dict[str, Dict[str, tuple]]:
    C = p1.CACHE
    def rd(*a):
        return pd.read_csv(os.path.join(C, *a))
    s: Dict[str, Dict[str, tuple]] = {}
    for sym in ("NQ", "ES"):
        s.setdefault("Fade the sweep (Ph104)", {})[sym] = (rd("phase104_candidates.csv").query("symbol == @sym"), False)
        f = rd("phase106", f"phase106_setups_{sym}.csv")
        s.setdefault("Follow the sweep + 1h trend (Ph106)", {})[sym] = (f[f.side == f.h1], True)
        g = rd("phase107", f"phase107_setups_{sym}.csv")
        s.setdefault("IFVG model: next gap, 2nd-low stop (Ph107)", {})[sym] = (g[(g.entry_kind == "GAP") & (g.stop_kind == "2ND")], True)
        s.setdefault("Pullback IFVG with the morning move (Ph108b)", {})[sym] = (rd("phase108", f"phase108b_{sym}_MORNING_ALL.csv"), True)
        h = rd("phase111", f"phase111_{sym}.csv")
        s.setdefault("TJR video: 15m reversal (Ph111)", {})[sym] = (h[(h.model == "A_REVERSAL") & (h.target == "2R")], False)
        k = rd("phase113", f"phase113_setups_{sym}.csv")
        s.setdefault("TJR liquidity model, all levels, sweep stop (Ph113)", {})[sym] = (k[(k.set == "ALL") & (k.stop_kind == "SWEEP") & (k.target_kind == "2R")], False)
    return s


def _in_window(df: pd.DataFrame, a: str, b: str, bar_open: bool) -> pd.DataFrame:
    t = pd.to_datetime(df["time"])
    fill = t + pd.Timedelta(minutes=1) if bar_open else t  # when the entry actually happens
    hhmm = fill.dt.strftime("%H:%M")
    x = df[(hhmm >= a) & (hhmm <= b)].copy()
    return x.sort_values("time").groupby(x["time"].str[:10]).head(1)


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(114)
    m1 = {s: p1.load(s, "M1") for s in ("NQ", "ES")}
    res: Dict = {"phase": 114, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "rows": []}
    for name, by_sym in _sets().items():
        for sym, (df, bar_open) in by_sym.items():
            for wname, (a, b) in WINDOWS.items():
                x = _in_window(df, a, b, bar_open)
                if not len(x):
                    continue
                sc = p12.score(m1[sym], x, sym, time_is_bar_open=bar_open)
                sc["yr"] = sc["day"].str[:4]
                wf = p12.walk_forward(sc, rng)
                plan = wf["chosen_on_explore"]
                res["rows"].append({
                    "strategy": name, "market": sym, "window": wname, "n": int(len(sc)),
                    "trades_per_year": {y: int(len(g)) for y, g in sc.groupby("yr")},
                    "fixed_by_year": {y: round(float(g["FIXED"].mean()), 3) for y, g in sc.groupby("yr")},
                    "best_plan_by_year": {y: round(float(g[plan].mean()), 3) for y, g in sc.groupby("yr")},
                    "plan_chosen_on_2023_24": plan, "plan_2025_26": wf["confirm_stats"], "passes": wf["confirm_passes"],
                    "all_plans_2025_26": {p: wf["plans"][p]["confirm"] for p in p12.PLANS},
                })
    with open(os.path.join(OUT, "phase114_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    for row in r["rows"]:
        st = row["plan_2025_26"]
        print(f"{row['strategy'][:46]:<46} {row['market']} {row['window']} n={row['n']:>3} FIXED by yr {row['fixed_by_year']} | "
              f"plan {row['plan_chosen_on_2023_24']}: by yr {row['best_plan_by_year']} 2025-26 {st.get('mean_r')} ci {st.get('ci95')} pass={row['passes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
