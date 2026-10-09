"""Phase 120 — the big-gap fade at OTHER markets' own opens (more setups, fresh markets).

Research only. The NQ/ES gap fade (Phases 116-118) is slow (~45 setups a year per index) and its
edge is tiny and was only visible in 2025-26. More setups come from index CFDs that open at other
times, each with its own opening gap: Europe (DAX, FTSE, CAC, Euro Stoxx, SMI, AEX) and Asia-Pacific
(Nikkei, Hang Seng, ASX 200). Same rule at each market's own cash open, fixed before running:

  Gap       local cash open vs the previous local cash close (last bar before the close);
            size = |gap| / mean cash-session range of the previous 14 sessions; BIG >= 0.7
            (0.5 reported too, for frequency).
  Entry     15 minutes after the open (the US 09:45 equivalent), only if the gap is still unfilled
            and price is on the gap side: trade TOWARD the previous close. Target = previous close.
  Stop      A = 1:1 with the target (wide);  B = beyond the open-to-entry extreme (tight; min 0.10 x range)
  Exit      target / stop / 2.5 hours after the open (the US 12:00 equivalent). Stop first in a bar.
  Costs     bar spread + slippage of 0.002% of price on entry and on stop/time exits.
  Counting  markets in a region trade the same day (correlation 0.65-0.9 in the US test), so each
            REGION counts once per day: the day's average R over the region's markets that qualified.
  PASS      a region (stop A) is positive in 2023-24 AND 2025-26 with the day-level 95% bootstrap
            interval (Bonferroni over 2 regions x 2 stops) above zero.
Server clock: NY+6/+7h (measured earlier); converted to each market's local clock through New York ->
UTC -> local (so US/EU/AU daylight-saving mismatches are handled).

    python -m phase120_global_gaps
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

OUT = os.path.join(p1.CACHE, "phase120")
INFO = os.path.join(p1.CACHE, "global_symbol_info.json")
EXPLORE_END = "2024-12-31"
SLIP_FRAC = 0.00002
# name: (tz, open (h, m), close (h, m), region)
MARKETS = {
    "GER30": ("Europe/Berlin", (9, 0), (17, 30), "EUROPE"),
    "FRA40": ("Europe/Paris", (9, 0), (17, 30), "EUROPE"),
    "EUSTX50": ("Europe/Paris", (9, 0), (17, 30), "EUROPE"),
    "SWI20": ("Europe/Zurich", (9, 0), (17, 20), "EUROPE"),
    "NTH25": ("Europe/Amsterdam", (9, 0), (17, 30), "EUROPE"),
    "UK100": ("Europe/London", (8, 0), (16, 30), "EUROPE"),
    "JP225": ("Asia/Tokyo", (9, 0), (15, 0), "ASIA"),
    "HK50": ("Asia/Hong_Kong", (9, 30), (16, 0), "ASIA"),
    "AUS200": ("Australia/Sydney", (10, 0), (16, 0), "ASIA"),
}
ENTRY_MIN, EXIT_MIN, THRESH = 15, 150, (0.7, 0.5)


def load_local(sym: str, tz: str, point: float) -> pd.DataFrame:
    p1.SYMBOLS[sym] = sym
    p1.POINT = point
    try:
        df = p1.load(sym, "M1")
    finally:
        p1.POINT = 0.01
    idx = df.index.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
    keep = ~idx.isna()
    df = df[keep]
    df.index = idx[keep].tz_convert(tz).tz_localize(None)
    return df[~df.index.duplicated()].sort_index()


def clock_check(df: pd.DataFrame, open_hm) -> str:
    """Local time of the biggest jump in average bar range between 06:00 and 12:00 - should equal the cash open."""
    rng = (df["high"] - df["low"])
    m = rng[(df.index.hour >= 6) & (df.index.hour < 12) & (df.index.weekday < 5)]
    mm = m.groupby(m.index.hour * 60 + m.index.minute).mean()
    jump = (mm - mm.shift(1)).dropna()
    best = int(jump.idxmax())
    return f"{best // 60:02d}:{best % 60:02d}"


def setups(mkt: str, df: pd.DataFrame, cfg) -> List[dict]:
    tz, (oh, om), (ch, cm), region = cfg
    tmin = df.index.hour * 60 + df.index.minute
    o_min, c_min = oh * 60 + om, ch * 60 + cm
    ses = df[(tmin >= o_min) & (tmin < c_min) & (df.index.weekday < 5)]
    gb = ses.groupby(ses.index.normalize())
    rng = gb["high"].max() - gb["low"].min()
    atr = rng.shift(1).rolling(14).mean()
    pcl = gb["close"].last().shift(1)
    rows = []
    for day, g in gb:
        if np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0] != day + pd.Timedelta(hours=oh, minutes=om):
            continue
        pc, a = float(pcl[day]), float(atr[day])
        gap = float(g["open"].iloc[0]) - pc
        size = abs(gap) / a
        if size < min(THRESH):
            continue
        gup = gap > 0
        t0 = day + pd.Timedelta(hours=oh, minutes=om + ENTRY_MIN)
        t1 = day + pd.Timedelta(hours=oh, minutes=om + EXIT_MIN)
        pre, post = g[g.index < t0], g[(g.index >= t0) & (g.index < t1)]
        if len(pre) < 5 or len(post) < 20:
            continue
        touched = (pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)
        e = float(pre["close"].iloc[-1])
        if touched or (gup and e <= pc) or ((not gup) and e >= pc):
            continue
        side = -1 if gup else 1
        dist = abs(e - pc)
        far = float(pre["high"].max()) if gup else float(pre["low"].min())
        spread = float(post["spread"].iloc[0])
        slip = SLIP_FRAC * e
        h, l, c = post["high"].to_numpy(), post["low"].to_numpy(), post["close"].to_numpy()
        for sname in ("A", "B"):
            risk = dist if sname == "A" else max(abs(far - e), 0.10 * a)
            stop = e - side * risk
            res, mf = None, 1.0
            for k in range(len(post)):
                if (side > 0 and l[k] <= stop) or (side < 0 and h[k] >= stop):
                    res, mf = -1.0, 1.0
                    break
                if (side > 0 and h[k] >= pc) or (side < 0 and l[k] <= pc):
                    res, mf = dist / risk, 0.0
                    break
            if res is None:
                res = side * (c[-1] - e) / risk
            r = res - (spread + slip + slip * mf) / risk
            for th in THRESH:
                if size >= th:
                    rows.append({"market": mkt, "region": region, "day": str(day.date()), "thresh": th, "stop": sname, "r": round(float(r), 4)})
    return rows


def _stats(x: np.ndarray, rng) -> dict:
    if len(x) < 2:
        return {"n": int(len(x))}
    boot = rng.choice(x, size=(5000, len(x)), replace=True).mean(axis=1)
    return {"n": int(len(x)), "mean_r": round(float(x.mean()), 3), "win_rate": round(float((x > 0).mean()), 3),
            "ci95": [round(float(np.quantile(boot, 0.025)), 3), round(float(np.quantile(boot, 0.975)), 3)],
            "ci_bonf": [round(float(np.quantile(boot, 0.05 / 4 / 2)), 3), round(float(np.quantile(boot, 1 - 0.05 / 4 / 2)), 3)]}


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(120)
    info = json.load(open(INFO))
    rows: List[dict] = []
    clocks = {}
    for mkt, cfg in MARKETS.items():
        df = load_local(mkt, cfg[0], info[mkt]["point"])
        clocks[mkt] = {"expected": f"{cfg[1][0]:02d}:{cfg[1][1]:02d}", "measured": clock_check(df, cfg[1])}
        rows += setups(mkt, df, cfg)
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(OUT, "phase120_trades.csv"), index=False)
    res: Dict = {"phase": 120, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "clock_check": clocks, "markets": {}, "regions": {}}
    for (th, st, m), g in d.groupby(["thresh", "stop", "market"]):
        yrs = {y: round(float(x.r.mean()), 3) for y, x in g.groupby(g.day.str[:4])}
        span = (pd.Timestamp(g.day.max()) - pd.Timestamp(g.day.min())).days / 365.25
        res["markets"][f"{m}|{th}|{st}"] = {"n": int(len(g)), "per_year": round(len(g) / max(span, 0.5), 1), "mean_r": round(float(g.r.mean()), 3),
                                          "win_rate": round(float((g.r > 0).mean()), 3), "by_year": yrs}
    for (th, st, reg), g in d.groupby(["thresh", "stop", "region"]):
        day = g.groupby("day").r.mean()  # one position per region per day
        ex, co = day[day.index <= EXPLORE_END], day[day.index > EXPLORE_END]
        span = (pd.Timestamp(day.index.max()) - pd.Timestamp(day.index.min())).days / 365.25
        yrs = {y: round(float(x.mean()), 3) for y, x in day.groupby(day.index.str[:4])}
        s_all, s_ex, s_co = _stats(day.to_numpy(), rng), _stats(ex.to_numpy(), rng), _stats(co.to_numpy(), rng)
        res["regions"][f"{reg}|{th}|{st}"] = {"days": int(len(day)), "days_per_year": round(len(day) / max(span, 0.5), 1), "all": s_all, "explore": s_ex, "confirm": s_co, "by_year": yrs,
                                              "pass": bool(th == 0.7 and st == "A" and s_ex.get("mean_r", -1) > 0 and s_co.get("mean_r", -1) > 0 and s_all.get("ci_bonf", [-1])[0] > 0)}
    with open(os.path.join(OUT, "phase120_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    res = run()
    print("clock check (local time of the biggest jump vs expected open):")
    for m, v in res["clock_check"].items():
        print(f"  {m:<8} expected {v['expected']}  measured {v['measured']}{'' if v['expected'] == v['measured'] else '   <== CHECK'}")
    for th in (0.7, 0.5):
        print(f"\n===== gap >= {th} : per market =====")
        print(f"{'market':<9}{'stop':<5}{'n':>5}{'/yr':>6}{'win':>6}{'mean R':>8}   by year")
        for k, v in res["markets"].items():
            m, t, st = k.split("|")
            if float(t) == th:
                print(f"{m:<9}{st:<5}{v['n']:>5}{v['per_year']:>6.0f}{v['win_rate']*100:>5.0f}%{v['mean_r']:>+8.3f}   {v['by_year']}")
        print(f"----- by region (each day counted once: average over the region's markets that qualified) -----")
        for k, v in res["regions"].items():
            reg, t, st = k.split("|")
            if float(t) == th:
                a, e, c = v["all"], v["explore"], v["confirm"]
                print(f"{reg:<7} stop {st}: {v['days']} days ({v['days_per_year']:.0f}/yr)  mean {a.get('mean_r', float('nan')):+.3f}R  95% {a.get('ci95')}  |  2023-24 {e.get('mean_r', float('nan')):+.3f} (n={e.get('n')})  2025-26 {c.get('mean_r', float('nan')):+.3f} (n={c.get('n')})  {v['by_year']}{'  <== PASS' if v['pass'] else ''}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
