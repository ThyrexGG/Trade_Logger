"""Phase 112 — trade-management engine + overlay ("cut losers early, let winners run").

Research only. The user's own trades suggest their edge is management, not the
entry. This module simulates the same entry under several management plans on
1-minute bars, and re-scores earlier phases' entries with them.

Plans (fixed before any result):
  FIXED     stop / target only.
  HALF      half off at +1R, rest at the target (the user's stated plan).
  CUT       FIXED, but if the trade has not been +0.5R at any point in its first
            15 minutes, exit at the close of minute 15 (the user cut losers early).
  RUN       no target: once +1R, stop -> entry; then trail the stop 1R behind the
            best price; exit on the trail or at the flat time (let winners run).
  CUT_RUN   CUT's 15-minute rule, then RUN.
  HALF_CUT  HALF with CUT's 15-minute rule.
Costs: entry spread + slippage on every market exit, weighted by size.

Overlay (walk-forward): for each earlier entry set, the plan is chosen on
2023-04..2024 (EXPLORE) and only its 2025..2026-10 (CONFIRM) result counts.

    python -m phase112_manage
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, Tuple

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1

PLANS = ("FIXED", "HALF", "CUT", "RUN", "CUT_RUN", "HALF_CUT")
CUT_MIN, CUT_MFE = 15, 0.5
TRAIL_R = 1.0
EXPLORE_END = "2024-12-31"
OUT = os.path.join(p1.CACHE, "phase112")


def manage(h: np.ndarray, l: np.ndarray, c: np.ndarray, start: int, end: int, side: int,
           entry: float, stop: float, target: float, plan: str) -> Tuple[float, str, float]:
    """Gross R, outcome, fraction of size closed at market. Bars [start, end) after entry."""
    risk = abs(entry - stop)
    cut = plan in ("CUT", "CUT_RUN", "HALF_CUT")
    run = plan in ("RUN", "CUT_RUN")
    half = plan in ("HALF", "HALF_CUT")
    cur_stop, best, banked, size = stop, 0.0, 0.0, 1.0
    for n, k in enumerate(range(start, end)):
        fav = (h[k] - entry) / risk if side > 0 else (entry - l[k]) / risk
        adv_hit = (l[k] <= cur_stop) if side > 0 else (h[k] >= cur_stop)
        if adv_hit:
            r_stop = side * (cur_stop - entry) / risk
            return banked + size * r_stop, ("trail" if run and cur_stop != stop else "stop"), size
        best = max(best, fav)
        if half and size == 1.0 and best >= 1.0:
            banked, size = 0.5, 0.5
        if not run and best >= abs(target - entry) / risk:
            return banked + size * abs(target - entry) / risk, "target", 0.0
        if run and best >= 1.0:
            trail = entry + side * (best - TRAIL_R) * risk
            cur_stop = max(cur_stop, trail) if side > 0 else min(cur_stop, trail)
            if side > 0:
                cur_stop = max(cur_stop, entry)
            else:
                cur_stop = min(cur_stop, entry)
        if cut and n + 1 == CUT_MIN and best < CUT_MFE:
            return banked + size * side * (c[k] - entry) / risk, "cut", size
    last = min(end, len(c)) - 1
    return banked + size * side * (c[last] - entry) / risk, "time", size


def score(m1: pd.DataFrame, trades: pd.DataFrame, symbol: str, flat_hm=(15, 55), target_r: float = 2.0,
          time_is_bar_open: bool = True) -> pd.DataFrame:
    """Re-score entries (time, side, entry, stop) under every plan. Target = target_r unless a 'target_px' column exists.
    `time_is_bar_open`: the entry `time` is the OPEN time of the 1-minute bar whose close is the entry (phases
    106-108); False when `time` is already the bar's close time (phases 104, 111)."""
    h, l, c = m1["high"].to_numpy(), m1["low"].to_numpy(), m1["close"].to_numpy()
    spr = m1["spread"].to_numpy()
    idx = m1.index
    slip = p1.SLIPPAGE[symbol]
    rows = []
    for _, t in trades.iterrows():
        ts = pd.Timestamp(t["time"])
        i = idx.searchsorted(ts) + (1 if time_is_bar_open else 0)  # first bar AFTER the entry fill
        if i >= len(idx):
            continue
        end = idx.searchsorted(ts.normalize() + pd.Timedelta(hours=flat_hm[0], minutes=flat_hm[1]))
        side, entry, stop = int(t["side"]), float(t["entry"]), float(t["stop"])
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        tgt = float(t["target_px"]) if "target_px" in t and t["target_px"] == t["target_px"] else entry + side * target_r * risk
        sp = float(spr[max(0, i - 1)])
        rec = {"day": str(ts.date()), "time": str(ts), "side": side}
        for plan in PLANS:
            g, outc, mkt = manage(h, l, c, i, end, side, entry, stop, tgt, plan)
            rec[plan] = round(g - (sp + slip + slip * mkt) / risk, 4)
        rows.append(rec)
    return pd.DataFrame(rows)


def walk_forward(scored: pd.DataFrame, rng) -> Dict:
    ex, cf = scored[scored.day <= EXPLORE_END], scored[scored.day > EXPLORE_END]
    table = {p: {"explore": round(float(ex[p].mean()), 3) if len(ex) else None,
                 "confirm": round(float(cf[p].mean()), 3) if len(cf) else None,
                 "2025": round(float(cf[cf.day < "2026"][p].mean()), 3) if len(cf) else None,
                 "2026": round(float(cf[cf.day >= "2026"][p].mean()), 3) if len(cf) else None} for p in PLANS}
    best = max(PLANS, key=lambda p: table[p]["explore"] if table[p]["explore"] is not None else -9)
    st = p1.summarize(cf[best].to_numpy(), rng) if len(cf) else {}
    return {"plans": table, "chosen_on_explore": best, "confirm_stats": st,
            "confirm_passes": bool(st and st.get("ci95", [-1])[0] > 0 and table[best]["2025"] > 0 and table[best]["2026"] > 0)}


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(112)
    C = p1.CACHE
    sets = {
        "pullback IFVG, with morning (Ph108b)": {s: pd.read_csv(os.path.join(C, "phase108", f"phase108b_{s}_MORNING_ALL.csv")) for s in ("NQ", "ES")},
        "IFVG model, next gap / 2nd low (Ph107)": {s: pd.read_csv(os.path.join(C, "phase107", f"phase107_setups_{s}.csv")).query("entry_kind == 'GAP' and stop_kind == '2ND'").sort_values("time").groupby("day").head(1) for s in ("NQ", "ES")},
        "follow sweep + 1h trend (Ph106)": {s: (lambda f: f[f.side == f.h1].sort_values("time").groupby("day").head(1))(pd.read_csv(os.path.join(C, "phase106", f"phase106_setups_{s}.csv"))) for s in ("NQ", "ES")},
        "fade the sweep, first each day (Ph104)": {s: (lambda f: f[f.symbol == s].sort_values("time").groupby("day").head(1))(pd.read_csv(os.path.join(C, "phase104_candidates.csv"))) for s in ("NQ", "ES")},
    }
    p111 = os.path.join(C, "phase111")
    for s in ("NQ", "ES"):
        f = os.path.join(p111, f"phase111_{s}.csv")
        if os.path.exists(f):
            d = pd.read_csv(f)
            for model in ("A_REVERSAL", "B_CONTINUATION"):
                sets.setdefault(f"TJR video: {model} (Ph111)", {})[s] = d[(d.model == model) & (d.target == "2R")].sort_values("time").groupby("day").head(1)
    res: Dict = {"phase": 112, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "sets": {}}
    m1 = {s: p1.load(s, "M1") for s in ("NQ", "ES")}
    for name, by_sym in sets.items():
        for s, tr in by_sym.items():
            if tr is None or not len(tr):
                continue
            sc = score(m1[s], tr, s, time_is_bar_open=not ("Ph104" in name or "Ph111" in name))
            sc.to_csv(os.path.join(OUT, f"phase112_{s}_{abs(hash(name)) % 10**6}.csv"), index=False)
            res["sets"][f"{name} | {s}"] = {"n": int(len(sc)), **walk_forward(sc, rng)}
    with open(os.path.join(OUT, "phase112_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    for k, v in r["sets"].items():
        pl = v["plans"]
        line = "  ".join(f"{p}:{pl[p]['explore']:+.2f}/{pl[p]['confirm']:+.2f}" for p in PLANS if pl[p]["explore"] is not None)
        st = v["confirm_stats"]
        print(f"{k:<48} n={v['n']:>4} | explore/confirm  {line}\n    -> chosen on 2023-24: {v['chosen_on_explore']}  2025-26 = {st.get('mean_r')} ci={st.get('ci95')} "
              f"(2025 {pl[v['chosen_on_explore']]['2025']}, 2026 {pl[v['chosen_on_explore']]['2026']}) pass={v['confirm_passes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
