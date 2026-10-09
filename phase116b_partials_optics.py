"""Phase 116b — can a ~64% win rate and ~1.2-1.4 win/loss ratio appear WITHOUT an edge?

Research only. TJR reports a ~64% daily win rate and an average win/loss of ~1.23-1.38
(video + TradeZella). He also takes partial profits at nearby draws on liquidity and moves
the stop to breakeven. Taking half off early and protecting the rest turns many trades into
small "wins", which lifts the win rate without any change in entry quality (Phase 101b saw
37% -> 49-50% with unchanged expectancy). This phase tests that on the Phase 115 entries
(EITHER sweep, stop beyond the 2nd high/low, window 09:30-11:30, one per day, NQ and ES):
re-score the SAME entries with scale-out ladders and report win rate (net R > 0, as
TradeZella counts it), average win / loss, payoff and mean R after costs.

Ladders (fraction of size at each R multiple; stop to breakeven after the first fill; the
rest is flat 15:55):
  REF   Phase 115 PARTIALS (half at first draw >= 1R, rest at the next)
  H1_2  half at 1R, rest at 2R          H1_3  half at 1R, rest at 3R
  H05_2 half at 0.5R, rest at 2R        T123  thirds at 1R, 2R, 3R
  Q1    quarter at 0.5R, quarter at 1R, half at 2R

Question answered: is there a ladder whose win rate / payoff matches TJR's fingerprint, and
what is its expectancy? (If it is still negative, the fingerprint is a management style, not
proof of entry edge.)

    python -m phase116b_partials_optics
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase115_tjr_strategy as p15

OUT = os.path.join(p1.CACHE, "phase116")
EXPLORE_END = "2024-12-31"
LADDERS: Dict[str, List[Tuple[float, float]]] = {
    "H1_2": [(0.5, 1.0), (0.5, 2.0)],
    "H1_3": [(0.5, 1.0), (0.5, 3.0)],
    "H05_2": [(0.5, 0.5), (0.5, 2.0)],
    "T123": [(1 / 3, 1.0), (1 / 3, 2.0), (1 / 3, 3.0)],
    "Q1": [(0.25, 0.5), (0.25, 1.0), (0.5, 2.0)],
}


def ladder(seg: pd.DataFrame, side: int, e: float, risk: float, stop: float, legs) -> Tuple[float, float]:
    """Gross R and the fraction of size closed at market (stop / time). Stop checked first (conservative)."""
    h, l, c = seg["high"].to_numpy(), seg["low"].to_numpy(), seg["close"].to_numpy()
    banked, size, filled = 0.0, 1.0, 0
    cur = stop
    for k in range(len(seg)):
        if (side > 0 and l[k] <= cur) or (side < 0 and h[k] >= cur):
            return banked + size * side * (cur - e) / risk, size
        while filled < len(legs):
            frac, rm = legs[filled]
            px = e + side * rm * risk
            if (side > 0 and h[k] >= px) or (side < 0 and l[k] <= px):
                banked += frac * rm
                size -= frac
                filled += 1
                cur = e if filled >= 1 else cur
                if size <= 1e-9:
                    return banked, 0.0
            else:
                break
    last = side * (c[-1] - e) / risk if len(c) else 0.0
    return banked + size * last, size


def _stats(r: np.ndarray, g: np.ndarray) -> dict:
    wins, losses = r[r > 0], r[r <= 0]
    return {
        "n": int(len(r)), "win_rate": round(float((r > 0).mean()), 3),
        "avg_win_R": round(float(wins.mean()), 2) if len(wins) else None,
        "avg_loss_R": round(float(losses.mean()), 2) if len(losses) else None,
        "payoff": round(float(wins.mean() / -losses.mean()), 2) if len(wins) and len(losses) and losses.mean() < 0 else None,
        "mean_r": round(float(r.mean()), 3), "gross_mean_r": round(float(g.mean()), 3),
        "flat_or_small_share": round(float((np.abs(r) < 0.15).mean()), 3),
    }


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    res: Dict = {"phase": "116b", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "markets": {}}
    for mkt in ("NQ", "ES"):
        m1 = p1.load(mkt, "M1")
        m1 = m1[m1.index >= pd.Timestamp("2023-04-01")]
        csv = pd.read_csv(os.path.join(p15.OUT, f"phase115_{mkt}.csv"))
        base = csv[(csv.either == True) & (csv.stop_kind == "SECOND") & (csv.exit_mode == "LIQ1") & (csv.fill_hhmm >= "09:30") & (csv.fill_hhmm <= "11:30")]  # noqa: E712
        base = base.sort_values("time").groupby("day").head(1).reset_index(drop=True)
        slip = p1.SLIPPAGE[mkt]
        rows = {name: [] for name in list(LADDERS) + ["REF"]}
        ref = csv[(csv.either == True) & (csv.stop_kind == "SECOND") & (csv.exit_mode == "PARTIALS") & (csv.fill_hhmm >= "09:30") & (csv.fill_hhmm <= "11:30")]  # noqa: E712
        ref = ref.sort_values("time").groupby("day").head(1)
        for _, t in ref.iterrows():
            rows["REF"].append({"day": t["day"], "r": t["r"], "g": t["r_gross"]})
        for _, t in base.iterrows():
            seg = m1.loc[pd.Timestamp(t["time"]): pd.Timestamp(t["day"]) + pd.Timedelta(hours=15, minutes=55)]
            side, e, risk, stop = int(t["side"]), float(t["entry"]), float(t["risk"]), float(t["stop"])
            for name, legs in LADDERS.items():
                g, mkt_frac = ladder(seg, side, e, risk, stop, legs)
                r = g - (t["spread"] + slip + slip * mkt_frac) / risk
                rows[name].append({"day": t["day"], "r": r, "g": g})
        res["markets"][mkt] = {}
        for name, lst in rows.items():
            d = pd.DataFrame(lst)
            ex, co = d[d.day <= EXPLORE_END], d[d.day > EXPLORE_END]
            res["markets"][mkt][name] = {
                "all": _stats(d.r.to_numpy(), d.g.to_numpy()),
                "explore": _stats(ex.r.to_numpy(), ex.g.to_numpy()) if len(ex) else None,
                "confirm": _stats(co.r.to_numpy(), co.g.to_numpy()) if len(co) else None,
                "jan_may_2026": _stats(*(lambda z: (z.r.to_numpy(), z.g.to_numpy()))(d[(d.day >= "2026-01-01") & (d.day < "2026-06-01")])) if len(d[(d.day >= "2026-01-01") & (d.day < "2026-06-01")]) else None,
            }
    with open(os.path.join(OUT, "phase116b_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    res = run()
    for mkt, v in res["markets"].items():
        print(f"\n===== {mkt}  (TJR claims: win ~64%, payoff ~1.2-1.4) =====")
        print(f"{'ladder':<7}{'n':>5}{'win%':>7}{'avgW':>7}{'avgL':>7}{'payoff':>8}{'mean R':>8}{'gross':>7}{'~flat':>7} | {'2023-24':>8}{'2025-26':>8}{'Jan-May26':>10}")
        for name, s in v.items():
            a = s["all"]
            print(f"{name:<7}{a['n']:>5}{a['win_rate']*100:>6.0f}%{(a['avg_win_R'] or 0):>7.2f}{(a['avg_loss_R'] or 0):>7.2f}{(a['payoff'] or 0):>8.2f}{a['mean_r']:>8.3f}{a['gross_mean_r']:>7.3f}{a['flat_or_small_share']*100:>6.0f}% | "
                  f"{(s['explore'] or {}).get('mean_r', float('nan')):>8.3f}{(s['confirm'] or {}).get('mean_r', float('nan')):>8.3f}{(s['jan_may_2026'] or {}).get('mean_r', float('nan')):>10.3f}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
