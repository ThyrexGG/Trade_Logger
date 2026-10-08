"""Phase 103c — a fresh holdout for every Phase 101 / 102 cell.

Phases 101-102 were designed and judged on 5-minute data from 2025-05-13 on.
Raising the MT5 bar cap later exposed 5-minute history back to 2023-04 that
none of those phases ever saw. This re-runs the EXACT Phase 101 grid and
Phase 102 filter cells, unchanged, on that unseen window only:

    HOLDOUT = 2023-04-19 .. 2025-05-12

A cell would only deserve attention if its holdout mean R is > 0 with the
95% bootstrap interval above 0 (and Bonferroni across all 32 cells for a claim).

    python -m phase103c_holdout
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict

import numpy as np

import phase101_ny_open_sweep as p1
import phase102_tjr_filters as p2

HOLDOUT_FROM, HOLDOUT_TO = "2023-04-19", "2025-05-12"
RESULT_PATH = os.path.join(p1.CACHE, "phase103c_result.json")


def run() -> Dict:
    rng = np.random.default_rng(1033)
    out: Dict = {"phase": "103c", "holdout": [HOLDOUT_FROM, HOLDOUT_TO], "p101": [], "p102": []}
    in_ho = lambda day: HOLDOUT_FROM <= day <= HOLDOUT_TO  # noqa: E731
    # Phase 101 grid
    for s in p1.SYMBOLS:
        df = p1.load(s, "M5")
        trades = [t for t in p1.backtest(s, "M5", df) if in_ho(t.day)]
        for level in p1.LEVELS:
            for model in p1.ENTRIES:
                rs = np.array([t.r for t in trades if t.level == level and t.entry_model == model])
                st = p1.summarize(rs, rng)
                out["p101"].append({"symbol": s, "level": level, "entry": model, **st})
    # Phase 102 filter cells (same code path as phase102.run, holdout days only)
    data = {s: p1.load(s, p2.TF) for s in p1.SYMBOLS}
    cands = {s: p2.candidates(s, data[s]) for s in p1.SYMBOLS}
    bias = {s: p2.daily_bias(data[s]) for s in p1.SYMBOLS}
    for s in p1.SYMBOLS:
        lv_s, lv_o = cands[s]["_levels"], cands[p2.OTHER[s]]["_levels"]
        for model in p1.ENTRIES:
            for variant in (p2.REFERENCE,) + p2.VARIANTS:
                rs = []
                for day, rows in cands[s].items():
                    if day == "_levels" or not in_ho(day):
                        continue
                    ok = []
                    for row in rows:
                        t = row["trade"]
                        if t.entry_model != model:
                            continue
                        side = 1 if t.side == "LONG" else -1
                        if variant in ("SMT", "SMT_BIAS", "FULL_TJR") and (
                                day not in lv_o or not p2.smt_ok(t, row["swept"], row["allowed_from"], data[p2.OTHER[s]], lv_o[day])):
                            continue
                        if variant in ("BIAS", "SMT_BIAS", "FULL_TJR") and bias[s].get(day, 0) != side:
                            continue
                        ok.append(t)
                    if ok:
                        t = min(ok, key=lambda x: x.entry_time)
                        if variant == "FULL_TJR":
                            t = p2.with_liquidity_target(t, data[s], lv_s[day])
                        rs.append(t.r)
                st = p1.summarize(np.array(rs), rng)
                out["p102"].append({"symbol": s, "entry": model, "variant": variant, **st})
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    return out


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    for row in r["p101"]:
        print(f"P101 {row['symbol']} {row['level']:<4} {row['entry']:<8} N={row.get('n',0):>4} win={row.get('win_rate','-')} mean={row.get('mean_r','-')} ci={row.get('ci95')}")
    for row in r["p102"]:
        print(f"P102 {row['symbol']} {row['entry']:<8} {row['variant']:<9} N={row.get('n',0):>4} win={row.get('win_rate','-')} mean={row.get('mean_r','-')} ci={row.get('ci95')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
