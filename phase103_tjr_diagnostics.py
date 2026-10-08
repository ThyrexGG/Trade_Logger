"""Phase 103a — WHY the NY-open sweep fades lose: a diagnosis of Phase 101's trades.

Research only. Uses Phase 101's M5 trades (both entry models, all four
levels, NQ + ES) and looks at the PRICE PATH after each entry:

  * excursion: how far in our favour (in R) price got before the stop / noon
  * stop-then-target: stopped out, and price THEN reached the original 2R
    target before noon (a stop that was too tight)
  * feature buckets: when the sweep happened, how deep it went, stop size,
    the prior day's range, day of week, long vs short

Discipline: buckets are explored on the IN-SAMPLE period only (before the
Phase-101 OOS cut). A bucket is carried forward only if, in-sample, it has
N >= 40 and mean R >= +0.15. Every bucket that qualifies is then checked ONCE
on the out-of-sample period, and only that check counts.

    python -m phase103_tjr_diagnostics
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1

PROMOTE_MIN_N = 40
PROMOTE_MIN_MEAN = 0.15
RESULT_PATH = os.path.join(p1.CACHE, "phase103a_result.json")


def _paths(trades: List[p1.Trade], df: pd.DataFrame) -> pd.DataFrame:
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    idx = df.index
    rth = df[(df.index.time >= pd.Timestamp("09:30").time()) & (df.index.time < pd.Timestamp("16:00").time())]
    day_range = (rth["high"].groupby(rth.index.date).max() - rth["low"].groupby(rth.index.date).min())
    prev_range = day_range.shift(1)
    rows = []
    for t in trades:
        side = 1 if t.side == "LONG" else -1
        eb = idx.get_loc(pd.Timestamp(t.entry_time))
        i_end = idx.searchsorted(pd.Timestamp(t.day) + pd.Timedelta(hours=12))
        mfe = 0.0
        stopped_at = None
        for k in range(eb + 1, i_end):
            hit_stop = l[k] <= t.stop if side > 0 else h[k] >= t.stop
            if hit_stop:
                stopped_at = k
                break
            fav = (h[k] - t.entry) if side > 0 else (t.entry - l[k])
            mfe = max(mfe, fav / t.risk)
        then_target = False
        if stopped_at is not None:
            for k in range(stopped_at + 1, i_end):
                if (side > 0 and h[k] >= t.target) or (side < 0 and l[k] <= t.target):
                    then_target = True
                    break
        et = pd.Timestamp(t.entry_time)
        mins = (et.hour * 60 + et.minute) - (9 * 60 + 30)
        pr = prev_range.get(pd.Timestamp(t.day).date(), np.nan)
        rows.append({
            "day": t.day, "symbol": t.symbol, "level": t.level, "entry_model": t.entry_model, "side": t.side,
            "r": t.r, "mfe_r": mfe, "stopped": stopped_at is not None, "stop_then_target": then_target,
            "entry_minute": mins, "risk_vs_prev_range": t.risk / pr if pr and pr == pr else np.nan,
            "prev_range_pct": pr / t.entry if pr == pr else np.nan, "weekday": pd.Timestamp(t.day).day_name()[:3],
        })
    return pd.DataFrame(rows)


def _bucket_table(df: pd.DataFrame, col: str, bins=None, labels=None) -> pd.DataFrame:
    key = pd.cut(df[col], bins=bins, labels=labels) if bins is not None else df[col]
    g = df.groupby(key, observed=True)["r"]
    return pd.DataFrame({"n": g.size(), "mean_r": g.mean().round(3), "win": (df.assign(w=df.r > 0).groupby(key, observed=True)["w"].mean()).round(3)})


def run() -> Dict:
    frames = []
    cut = None
    for s in p1.SYMBOLS:
        df = p1.load(s, "M5")
        trades = p1.backtest(s, "M5", df)
        all_days = sorted({str(d.date()) for d in df.index.normalize() if d.weekday() < 5})
        cut = all_days[int(len(all_days) * (1 - p1.OOS_FRACTION))]
        frames.append(_paths(trades, df))
    d = pd.concat(frames, ignore_index=True)
    is_, oos = d[d.day < cut], d[d.day >= cut]

    out: Dict = {"phase": "103a", "oos_from": cut, "n_trades": int(len(d))}
    # 1. how far do trades get before they stop?
    reach = {f">={x}R": round(float((d.mfe_r >= x).mean()), 3) for x in (0.5, 1.0, 1.5, 2.0, 3.0)}
    out["reached_before_stop_or_noon"] = reach
    out["stopped_share"] = round(float(d.stopped.mean()), 3)
    out["stopped_then_hit_original_target"] = round(float(d[d.stopped].stop_then_target.mean()), 3)

    # 2. feature buckets, in-sample only
    specs = {
        "entry_minute": dict(bins=[-1, 15, 45, 90], labels=["09:30-09:45", "09:45-10:15", "10:15-11:00"]),
        "risk_vs_prev_range": dict(bins=[0, 0.1, 0.2, 10], labels=["tight stop <10% of yday range", "10-20%", "wide >20%"]),
        "prev_range_pct": dict(bins=[0, 0.01, 0.015, 1], labels=["quiet yday <1%", "1-1.5%", "volatile yday >1.5%"]),
        "weekday": {}, "side": {}, "level": {}, "entry_model": {}, "symbol": {},
    }
    tables = {}
    promoted = []
    for col, spec in specs.items():
        t = _bucket_table(is_, col, **spec)
        tables[col] = t.reset_index().astype({col: str}).to_dict(orient="records")
        for name, row in t.iterrows():
            if row["n"] >= PROMOTE_MIN_N and row["mean_r"] >= PROMOTE_MIN_MEAN:
                promoted.append((col, str(name), spec))
    out["in_sample_buckets"] = tables

    # 3. the one-time out-of-sample check of every promoted bucket
    checks = []
    for col, name, spec in promoted:
        key = pd.cut(oos[col], **spec).astype(str) if spec else oos[col].astype(str)
        sub = oos[key == name]
        rs = sub["r"].to_numpy()
        lo, hi = p1._boot_ci(rs, 0.05, np.random.default_rng(103)) if len(rs) > 1 else (float("nan"), float("nan"))
        checks.append({"feature": col, "bucket": name, "oos_n": int(len(rs)),
                       "oos_mean_r": round(float(rs.mean()), 3) if len(rs) else None, "oos_ci95": [round(lo, 3), round(hi, 3)]})
    out["promoted_oos_checks"] = checks
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    return out


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "in_sample_buckets"}, indent=1, default=str))
    for col, rows in r["in_sample_buckets"].items():
        print(f"\n[{col}] (in-sample)")
        for row in rows:
            print("  ", row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
