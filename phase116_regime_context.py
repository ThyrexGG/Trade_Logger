"""Phase 116 — what context makes TJR's setup work? (regime, weekday, stop size, gap, trend)

Research only. Phases 101-115 tested rules; none made money as fixed rules, and
TJR says his edge is in *which* setups he takes. This phase slices the Phase 115
trades (TJR-faithful set and the better SWEEP-stop set, NQ and ES, one trade per
day) by context that is known BEFORE entry, and asks which slices are positive in
BOTH the 2023-24 explore half and the 2025-26 confirm half.

Pre-registered (before running):
  Sets      A = EITHER | stop SECOND | PARTIALS | window TJR (TJR-faithful)
            B = EITHER | stop SWEEP  | PARTIALS | window TJR
  Features  vol_regime  prior-14d mean RTH range / prior-60d median (terciles, cut at the
                        explore-period 33/67 percentiles)
            weekday     Mon..Fri
            risk_atr    stop distance / prior-14d mean RTH range (terciles, same rule)
            gap_atr     |09:30 open - prior RTH close| / prior-14d range (terciles)
            trend       trade side vs prior close above/below its 20-day mean close
            prev_day    trade side vs yesterday's RTH direction (with / against)
            after_loss  previous trade day's result was a loss / win
            side        long / short
            hour        entry in 09:30-09:45 / 09:45-10:30 / 10:30-11:30
  A slice is CONSISTENT when n >= 30 in both halves and mean R > 0 in both. With K slices
  tested, chance alone gives about K/4 consistent slices; a slice is only credited when its
  confirm-half 95% bootstrap CI (Bonferroni over K) is above 0.
  Also: month-by-month strategy R vs the month's volatility, and what NQ/ES did Jan-May 2026.

    python -m phase116_regime_context
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

EXPLORE_END = "2024-12-31"
SRC = os.path.join(p1.CACHE, "phase115")
OUT = os.path.join(p1.CACHE, "phase116")
SETS = {
    "A faithful (SECOND stop)": "SECOND",
    "B SWEEP stop": "SWEEP",
}


def _daily(df: pd.DataFrame) -> pd.DataFrame:
    rth = df[(df.index.time >= dt.time(9, 30)) & (df.index.time < dt.time(16, 0))]
    g = rth.groupby(rth.index.normalize())
    d = pd.DataFrame({"open": g["open"].first(), "hi": g["high"].max(), "lo": g["low"].min(), "close": g["close"].last()})
    d["range"] = d["hi"] - d["lo"]
    d["atr"] = d["range"].shift(1).rolling(14).mean()               # known before the day starts
    d["atr_regime"] = d["atr"] / d["range"].shift(1).rolling(60, min_periods=30).median()
    d["prev_close"] = d["close"].shift(1)
    d["ma20"] = d["close"].shift(1).rolling(20).mean()
    d["prev_dir"] = np.sign(d["close"] - d["open"]).shift(1)
    return d


def _terciles(x: pd.Series, explore: pd.Series) -> pd.Series:
    lo, hi = np.nanpercentile(x[explore], [33.3, 66.7])
    return pd.Series(np.where(x.isna(), None, np.where(x <= lo, "low", np.where(x <= hi, "mid", "high"))), index=x.index)


def _features(trades: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    x = trades.copy()
    x["dayts"] = pd.to_datetime(x["day"])
    x = x.join(d[["atr", "atr_regime", "prev_close", "ma20", "prev_dir", "open"]], on="dayts")
    ex = x["day"] <= EXPLORE_END
    x["vol_regime"] = _terciles(x["atr_regime"], ex)
    x["risk_atr"] = x["risk"] / x["atr"]
    x["risk_atr_t"] = _terciles(x["risk_atr"], ex)
    x["gap_atr"] = (x["open"] - x["prev_close"]).abs() / x["atr"]
    x["gap_t"] = _terciles(x["gap_atr"], ex)
    x["weekday"] = x["dayts"].dt.day_name().str[:3]
    x["trend"] = np.where(x["ma20"].isna(), None, np.where((x["prev_close"] > x["ma20"]) == (x["side"] > 0), "with", "against"))
    x["prev_day"] = np.where(x["prev_dir"].isna() | (x["prev_dir"] == 0), None, np.where(x["prev_dir"] == x["side"], "with", "against"))
    x["side_name"] = np.where(x["side"] > 0, "long", "short")
    h = x["fill_hhmm"]
    x["hour"] = np.where(h < "09:45", "0930-0945", np.where(h <= "10:30", "0945-1030", "1030-1130"))
    x = x.sort_values("day")
    x["after_loss"] = np.where(x["r"].shift(1).isna(), None, np.where(x["r"].shift(1) <= 0, "after loss", "after win"))
    return x


FEATS = ["vol_regime", "weekday", "risk_atr_t", "gap_t", "trend", "prev_day", "after_loss", "side_name", "hour"]


def _slice_rows(x: pd.DataFrame, label: str, mkt: str, rng) -> List[dict]:
    rows = []
    for f in FEATS:
        for v, g in x.dropna(subset=[f]).groupby(f):
            e, c = g[g.day <= EXPLORE_END].r.to_numpy(), g[g.day > EXPLORE_END].r.to_numpy()
            rows.append({
                "market": mkt, "set": label, "feature": f, "bucket": str(v), "n": int(len(g)),
                "n_explore": int(len(e)), "n_confirm": int(len(c)),
                "explore": round(float(e.mean()), 3) if len(e) else None,
                "confirm": round(float(c.mean()), 3) if len(c) else None,
                "win_rate": round(float((g.r > 0).mean()), 3),
                "mean_r": round(float(g.r.mean()), 3),
                "_c": c,
            })
    return rows


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(116)
    res: Dict = {"phase": 116, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "markets": {}}
    all_rows: List[dict] = []
    monthly: Dict[str, list] = {}
    context: Dict[str, dict] = {}
    for mkt in ("NQ", "ES"):
        df = p1.load(mkt, "M1")
        df = df[df.index >= pd.Timestamp("2023-03-01")]
        d = _daily(df)
        csv = pd.read_csv(os.path.join(SRC, f"phase115_{mkt}.csv"))
        base = csv[(csv.either == True) & (csv.exit_mode == "PARTIALS") & (csv.fill_hhmm >= "09:30") & (csv.fill_hhmm <= "11:30")]  # noqa: E712
        for label, sk in SETS.items():
            t = base[base.stop_kind == sk].sort_values("time").groupby("day").head(1).reset_index(drop=True)
            x = _features(t, d)
            all_rows += _slice_rows(x, label, mkt, rng)
            if sk == "SECOND":
                x["month"] = x["day"].str[:7]
                m = x.groupby("month").agg(n=("r", "size"), mean_r=("r", "mean"))
                dm = d.copy()
                dm["month"] = dm.index.strftime("%Y-%m")
                dm["range_pct"] = dm["range"] / dm["open"] * 100
                mm = dm.groupby("month").agg(range_pct=("range_pct", "mean"), first=("open", "first"), last=("close", "last"))
                mm["ret_pct"] = (mm["last"] / mm["first"] - 1) * 100
                j = m.join(mm[["range_pct", "ret_pct"]])
                monthly[mkt] = [{"month": k, "n": int(r.n), "mean_r": round(float(r.mean_r), 3), "range_pct": round(float(r.range_pct), 2), "ret_pct": round(float(r.ret_pct), 1)} for k, r in j.iterrows()]
                jj = j.dropna()
                res["markets"].setdefault(mkt, {})["corr_month_r_vs_range"] = round(float(np.corrcoef(jj.mean_r, jj.range_pct)[0, 1]), 3)
                res["markets"][mkt]["corr_month_r_vs_abs_ret"] = round(float(np.corrcoef(jj.mean_r, jj.ret_pct.abs())[0, 1]), 3)
                context[mkt] = {
                    "avg_daily_range_pct_2023_25": round(float(dm.loc[(dm.index >= "2023-04-01") & (dm.index < "2026-01-01"), "range_pct"].mean()), 2),
                    "avg_daily_range_pct_jan_may_2026": round(float(dm.loc[(dm.index >= "2026-01-01") & (dm.index < "2026-06-01"), "range_pct"].mean()), 2),
                    "ret_jan_may_2026_pct": round(float((dm.loc[dm.index < "2026-06-01"].close.iloc[-1] / dm.loc[dm.index >= "2026-01-01"].open.iloc[0] - 1) * 100), 1),
                }
    K = sum(1 for r in all_rows if r["n_explore"] >= 30 and r["n_confirm"] >= 30) or 1
    cons = []
    for r in all_rows:
        c = r.pop("_c")
        r["consistent"] = bool(r["n_explore"] >= 30 and r["n_confirm"] >= 30 and (r["explore"] or -1) > 0 and (r["confirm"] or -1) > 0)
        if r["consistent"]:
            lo, hi = p1._boot_ci(c, 0.05 / K, rng)
            r["confirm_ci_bonf"] = [round(lo, 3), round(hi, 3)]
            r["credited"] = bool(lo > 0)
            cons.append(r)
    res["n_slices_tested"] = K
    res["slices"] = all_rows
    res["consistent"] = cons
    res["credited"] = [c for c in cons if c["credited"]]
    res["monthly"] = monthly
    res["context"] = context
    with open(os.path.join(OUT, "phase116_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    res = run()
    print(f"slices tested (n>=30 both halves): {res['n_slices_tested']}   consistent: {len(res['consistent'])}   credited: {len(res['credited'])}")
    print("context:", res["context"])
    for mkt, v in res["markets"].items():
        print(mkt, {k: v[k] for k in v})
    for mkt in ("NQ", "ES"):
        print(f"\n== {mkt} slices (set, feature=bucket: n, explore, confirm) ==")
        for r in res["slices"]:
            if r["market"] == mkt and r["n_explore"] >= 30 and r["n_confirm"] >= 30:
                flag = "  <== CONSISTENT" + (" + CREDITED" if r.get("credited") else "") if r["consistent"] else ""
                print(f"  {r['set'][:1]} {r['feature']}={r['bucket']:<11} n={r['n']:<4} explore {r['explore']:+.3f}  confirm {r['confirm']:+.3f}  win {r['win_rate']:.0%}{flag}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
