"""Phase 118 — combine the big-gap fade (Phase 117) with TJR's setup pieces (Phase 115).

Research only. The user likes the big-gap fade and asked to combine it with TJR's strategy and
refine it. Phase 117's effect exists in 2025-26 and not in 2023-24, and the 2025-26 half is no
longer a clean holdout, so the bar for a refinement is stricter than before:

  A refinement counts only if it is positive in BOTH halves (2023-24 and 2025-26) AND beats the
  plain gap fade (R0) in both halves. A change that only helps 2025-26 is fitting the regime.

Population: days with a 09:30 gap >= T x the prior-14-day mean RTH range (T = 0.5 and 0.7),
direction F = toward the previous RTH close (fade the gap). All variants exit flat at 12:00.

  R0  plain fade, entry 09:45 if the gap is still unfilled (Phase 117), stops A (1:1 to the
      previous close) and B (beyond the 09:30-to-entry extreme)
  R1  R0 only if a TJR liquidity level on the gap side (Asia / London / 1h / 4h high for a gap
      up, low for a gap down; untaken at 09:30) was swept between 09:30 and 09:45
  R2  TJR's full 4-step sequence (Phase 115, EITHER sweep rule), entries 09:45-10:30, only when
      the setup points in F; stop = beyond the 2nd high/low (SECOND) or beyond the sweep (SWEEP);
      exits G1 = all out at the previous close, G2 = half at 1R, stop to breakeven, rest at the
      previous close. Skipped when the previous close is closer than 1R.
  CTRL  the same TJR sequences pointing AGAINST F (with the gap), same exits against the
      previous close mirrored as 2R, to show the gap direction is doing the work

    python -m phase118_gap_plus_tjr
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
import phase113_tjr_liquidity as p13
import phase115_tjr_strategy as p15

OUT = os.path.join(p1.CACHE, "phase118")
EXPLORE_END = "2024-12-31"
THRESH = (0.5, 0.7)
FLAT = (12, 0)


def _cost(mkt, spread, mkt_frac, risk):
    slip = p1.SLIPPAGE[mkt]
    return (spread + slip + slip * mkt_frac) / risk


def _gap_exit(seg: pd.DataFrame, side: int, e: float, risk: float, stop: float, pc: float, mode: str):
    """G1: all out at pc. G2: half at 1R then stop to breakeven, rest at pc. CTRL: all out at 2R. Stop first in a bar."""
    h, l, c = seg["high"].to_numpy(), seg["low"].to_numpy(), seg["close"].to_numpy()
    tgt = e + side * 2 * risk if mode == "CTRL" else pc
    tp1 = e + side * risk
    cur, half = stop, False
    for k in range(len(seg)):
        if (side > 0 and l[k] <= cur) or (side < 0 and h[k] >= cur):
            r_stop = side * (cur - e) / risk
            return (0.5 + 0.5 * r_stop if half else r_stop), (0.5 if half else 1.0), "be" if half else "stop"
        if mode == "G2" and not half and ((side > 0 and h[k] >= tp1) or (side < 0 and l[k] <= tp1)):
            half, cur = True, e
        if (side > 0 and h[k] >= tgt) or (side < 0 and l[k] <= tgt):
            rr = abs(tgt - e) / risk
            return ((0.5 + 0.5 * rr) if half else rr), 0.0, "target"
    last = side * (c[-1] - e) / risk if len(c) else 0.0
    return ((0.5 + 0.5 * last) if half else last), (0.5 if half else 1.0), "time"


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(118)
    rows: List[dict] = []
    for mkt in ("NQ", "ES"):
        df = p1.load(mkt, "M1")
        df = df[df.index >= pd.Timestamp("2023-03-01")]
        sib = p1.load("ES" if mkt == "NQ" else "NQ", "M1")
        sib = sib[sib.index >= pd.Timestamp("2023-03-01")]
        rth = df[(df.index.time >= dt.time(9, 30)) & (df.index.time < dt.time(16, 0))]
        gb = rth.groupby(rth.index.normalize())
        atr = (gb["high"].max() - gb["low"].min()).shift(1).rolling(14).mean()
        pcl = gb["close"].last().shift(1)
        days = sorted({d for d in df.index.normalize() if d.weekday() < 5})
        for i in range(3, len(days)):
            day, prev = days[i], days[i - 1]
            if day not in pcl.index or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)):
                continue
            g = df.loc[day + pd.Timedelta(hours=9, minutes=30): day + pd.Timedelta(hours=11, minutes=59, seconds=59)]
            if len(g) < 150 or g.index[0].time() != dt.time(9, 30):
                continue
            pc, a = float(pcl[day]), float(atr[day])
            gap = float(g["open"].iloc[0]) - pc
            size = abs(gap) / a
            if size < min(THRESH):
                continue
            gup = gap > 0
            F = -1 if gup else 1
            flat = day + pd.Timedelta(hours=FLAT[0], minutes=FLAT[1])
            # ---- R0 / R1
            t0 = day + pd.Timedelta(hours=9, minutes=45)
            pre, post = g[g.index < t0], g[(g.index >= t0) & (g.index < flat)]
            if len(pre) >= 10 and len(post) >= 10:
                touched = (pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)
                e = float(pre["close"].iloc[-1])
                if not (touched or (gup and e <= pc) or ((not gup) and e >= pc)):
                    lv = [x for x in p13.levels(df, day, prev) if x["fam"] in p15.FAMS and x["side"] == ("H" if gup else "L")]
                    swept = any((gup and pre["high"].max() > x["price"]) or ((not gup) and pre["low"].min() < x["price"]) for x in lv)
                    dist = abs(e - pc)
                    far = float(pre["high"].max()) if gup else float(pre["low"].min())
                    spread = float(post["spread"].iloc[0])
                    for sname in ("A", "B"):
                        risk = dist if sname == "A" else max(abs(far - e), 0.10 * a)
                        stop = e - F * risk
                        res, mf, oc = _gap_exit(post, F, e, risk, stop, pc, "G1")
                        r = res - _cost(mkt, spread, mf, risk)
                        for th in THRESH:
                            if size >= th:
                                rows.append({"market": mkt, "day": str(day.date()), "thresh": th, "variant": f"R0 plain | stop {sname}", "r": r, "outcome": oc})
                                if swept:
                                    rows.append({"market": mkt, "day": str(day.date()), "thresh": th, "variant": f"R1 +sweep filter | stop {sname}", "r": r, "outcome": oc})
            # ---- R2 / CTRL: TJR sequences (EITHER rule) on this day
            for st in p15.day_setups(mkt, df, sib, day, prev):
                if not st.get("either"):
                    continue
                if not ("09:45" <= st["fill_hhmm"] <= "10:30"):
                    continue
                side, e, risk, stop = int(st["side"]), float(st["entry"]), float(st["risk"]), float(st["stop"])
                ts = pd.Timestamp(st["time"])
                seg = df.loc[ts: flat - pd.Timedelta(seconds=1)]
                if len(seg) < 5:
                    continue
                ctrl = side != F
                if not ctrl and abs(pc - e) < risk:
                    continue  # previous close nearer than 1R: skipped
                for mode in (("CTRL",) if ctrl else ("G1", "G2")):
                    res, mf, oc = _gap_exit(seg, side, e, risk, stop, pc, mode)
                    r = res - _cost(mkt, st["spread"], mf, risk)
                    name = f"CTRL TJR with the gap | {st['stop_kind']} | 2R" if ctrl else f"R2 TJR toward fill | {st['stop_kind']} | {mode}"
                    for th in THRESH:
                        if size >= th:
                            rows.append({"market": mkt, "day": str(day.date()), "thresh": th, "variant": name, "r": r, "outcome": oc})
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(OUT, "phase118_trades.csv"), index=False)
    groups = list(d.groupby(["thresh", "variant", "market"]))
    K = len(groups)
    res: Dict = {"phase": 118, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "cells": [], "n_cells": K}
    base = {}
    for (th, var, mkt), g in groups:
        ex, co = g[g.day <= EXPLORE_END], g[g.day > EXPLORE_END]
        if var.startswith("R0"):
            base[(th, var.split("| ")[1], mkt)] = (float(ex.r.mean()) if len(ex) else np.nan, float(co.r.mean()) if len(co) else np.nan)
    for (th, var, mkt), g in groups:
        ex, co = g[g.day <= EXPLORE_END], g[g.day > EXPLORE_END]
        lo, hi = p1._boot_ci(g.r.to_numpy(), 0.05 / K, rng) if len(g) > 5 else (np.nan, np.nan)
        r = g.r.to_numpy()
        res["cells"].append({
            "thresh": th, "variant": var, "market": mkt, "n": int(len(g)), "n_explore": int(len(ex)), "n_confirm": int(len(co)),
            "win_rate": round(float((r > 0).mean()), 3), "mean_r": round(float(r.mean()), 3), "total_r": round(float(r.sum()), 1),
            "explore": round(float(ex.r.mean()), 3) if len(ex) else None, "confirm": round(float(co.r.mean()), 3) if len(co) else None,
            "pooled_ci_bonf": [round(lo, 3), round(hi, 3)],
        })
    for c in res["cells"]:
        stop_key = c["variant"].split("| ")[1] if c["variant"][:2] in ("R0", "R1") else None
        b = base.get((c["thresh"], stop_key, c["market"])) if stop_key else None
        c["beats_plain_both_halves"] = bool(b and c["explore"] is not None and c["confirm"] is not None and c["variant"][:2] == "R1"
                                            and c["explore"] > b[0] and c["confirm"] > b[1])
        c["credited"] = bool(c["explore"] is not None and c["confirm"] is not None and c["explore"] > 0 and c["confirm"] > 0
                             and c["pooled_ci_bonf"][0] > 0 and c["n_explore"] >= 20 and c["n_confirm"] >= 20
                             and (c["beats_plain_both_halves"] or c["variant"][:2] == "R2"))
    res["credited"] = [c for c in res["cells"] if c["credited"]]
    with open(os.path.join(OUT, "phase118_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    res = run()
    print(f"cells: {res['n_cells']}   credited: {len(res['credited'])}")
    print(f"{'gap>=':<6}{'mkt':<4}{'variant':<40}{'n':>4}{'win':>6}{'mean R':>8}{'total':>7}{'2023-24':>9}{'(n)':>5}{'2025-26':>9}{'(n)':>5}  pooled CI(Bonf)")
    for c in sorted(res["cells"], key=lambda c: (c["thresh"], c["market"], c["variant"])):
        ex = f"{c['explore']:+.3f}" if c["explore"] is not None else "   n/a"
        co = f"{c['confirm']:+.3f}" if c["confirm"] is not None else "   n/a"
        print(f"{c['thresh']:<6}{c['market']:<4}{c['variant']:<40}{c['n']:>4}{c['win_rate']*100:>5.0f}%{c['mean_r']:>+8.3f}{c['total_r']:>+7.1f}{ex:>9}{c['n_explore']:>5}{co:>9}{c['n_confirm']:>5}  {c['pooled_ci_bonf']}{'  <== CREDITED' if c['credited'] else ''}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
