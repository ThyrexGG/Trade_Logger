"""Phase 105 — the Phase 104 sweep + learned-selection study on forex.

Research only. Same candidate builder, features, walk-forward models and pass
bar as Phase 104 (phase104_tjr_selection), run on the user's FX pairs in two
sessions. Pre-registered before any FX result:

  Pairs     USDJPY, GBPUSD, GBPJPY, EURUSD, EURJPY (FundedNext MT5, 1-minute).
  SMT       each pair is compared with its closest sibling:
            GBPUSD<->EURUSD, USDJPY<->EURJPY, GBPJPY->EURJPY, EURJPY->USDJPY.
  Sessions  LONDON  sweeps/entries 02:00-05:00 NY, flat 07:00, anchor 03:00
            NY      sweeps/entries 08:00-11:00 NY, flat 12:00, anchor 08:30
            Levels use the FX day (17:00-17:00 NY) for "previous day".
  Costs     bar spread + 0.2 pip slippage per market fill + the account's
            $5/lot commission (~0.5 pip on USD-quoted, ~0.75 pip on JPY pairs).
  Stop      sweep extreme + 0.5 pip.
  Selection walk-forward by year (2024, 2025, 2026 tested), one pick per day per pair.
  PASS      as Phase 104: pooled test mean R > 0 with CI above 0, beats a random
            pick (p < 0.05), every test year positive. Break-even is reported as such.

    python -m phase105_fx_selection [--fetch]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Dict

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4

CACHE = os.path.join(p1.ROOT, ".cache", "phase105")
PAIRS = ("USDJPY", "GBPUSD", "GBPJPY", "EURUSD", "EURJPY")
PARTNER = {"GBPUSD": "EURUSD", "EURUSD": "GBPUSD", "USDJPY": "EURJPY", "EURJPY": "USDJPY", "GBPJPY": "EURJPY"}
POINT = {"USDJPY": 0.001, "GBPJPY": 0.001, "EURJPY": 0.001, "GBPUSD": 0.00001, "EURUSD": 0.00001}
PIP = {k: (0.01 if v == 0.001 else 0.0001) for k, v in POINT.items()}
COMMISSION_PIPS = {"USDJPY": 0.75, "GBPJPY": 0.75, "EURJPY": 0.75, "GBPUSD": 0.5, "EURUSD": 0.5}
SESSIONS = {
    "LONDON": {"start": (2, 0), "last_entry": (5, 0), "flat": (7, 0), "anchor": (3, 0), "coverage": ((2, 0), (5, 0)), "daily": "fx"},
    "NY": {"start": (8, 0), "last_entry": (11, 0), "flat": (12, 0), "anchor": (8, 30), "coverage": ((8, 0), (11, 0)), "daily": "fx"},
}


def fetch() -> None:  # pragma: no cover - needs the local terminal
    import MetaTrader5 as mt5

    os.makedirs(CACHE, exist_ok=True)
    if not mt5.initialize(timeout=30000):
        raise SystemExit(f"MT5 terminal not reachable: {mt5.last_error()}")
    try:
        now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
        for sym in PAIRS:
            mt5.symbol_select(sym, True)
            frames, end = [], now
            for _ in range(90):
                start = end - dt.timedelta(days=20)
                r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, start, end)
                if r is None or len(r) == 0:
                    break
                frames.append(pd.DataFrame(r))
                end = start
            df = pd.concat(frames).drop_duplicates("time").sort_values("time")
            df.to_csv(os.path.join(CACHE, f"{sym}_M1_server.csv"), index=False)
            print(sym, len(df))
    finally:
        mt5.shutdown()


def load(sym: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(CACHE, f"{sym}_M1_server.csv"))
    server = pd.to_datetime(df["time"], unit="s")
    hours = np.where(server < p1.SERVER_CLOCK_CHANGE, p1.SERVER_MINUS_NY_HOURS_BEFORE, p1.SERVER_MINUS_NY_HOURS)
    ny = server - pd.to_timedelta(hours, unit="h")
    out = pd.DataFrame({k: df[k].to_numpy(float) for k in ("open", "high", "low", "close")}, index=pd.DatetimeIndex(ny, name="ny"))
    out["spread"] = df["spread"].to_numpy(float) * POINT[sym]
    out = out[~out.index.duplicated()].sort_index()
    return out[out.index >= pd.Timestamp("2023-04-01")]


def clock_check(df: pd.DataFrame) -> Dict[str, float]:
    """Average 1-minute range at 08:30 NY (US data releases) vs the minute before, by year."""
    rng = df["high"] - df["low"]
    out = {}
    for y, g in rng.groupby(df.index.year):
        prof = g.groupby(g.index.strftime("%H:%M")).mean()
        out[str(y)] = round(float(prof.get("08:30", np.nan) / prof.get("08:29", np.nan)), 2)
    return out


def run() -> Dict:
    data = {s: load(s) for s in PAIRS}
    for s in PAIRS:  # register per-pair execution costs with the shared engine
        p1.SLIPPAGE[s] = 0.2 * PIP[s]
        p4.BUFFER[s] = 0.5 * PIP[s]
        p4.COMMISSION[s] = COMMISSION_PIPS[s] * PIP[s]
    res: Dict = {"phase": 105, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 "clock_check_0830_jump": {s: clock_check(d) for s, d in data.items()},
                 "data": {s: [str(d.index[0]), str(d.index[-1]), int(len(d))] for s, d in data.items()}, "sessions": {}}
    saved = dict(p4.SESSION)
    try:
        for name, sess in SESSIONS.items():
            p4.SESSION.clear()
            p4.SESSION.update(sess)
            frames = [p4.candidates(s, data[s], data[PARTNER[s]]) for s in PAIRS]
            cand = pd.concat([f for f in frames if len(f)], ignore_index=True)
            cand.to_csv(os.path.join(CACHE, f"phase105_candidates_{name}.csv"), index=False)
            p4.OUT_DIR = CACHE
            wf = p4.walk_forward(cand, tag=f"phase105_{name}")
            wf["n_candidates"] = int(len(cand))
            wf["by_pair"] = cand.groupby("symbol")["r"].agg(["size", "mean"]).round(3).reset_index().to_dict(orient="records")
            wf["by_family"] = cand.groupby("family")["r"].agg(["size", "mean"]).round(3).reset_index().to_dict(orient="records")
            res["sessions"][name] = wf
    finally:
        p4.SESSION.clear()
        p4.SESSION.update(saved)
        p4.OUT_DIR = p1.CACHE
    with open(os.path.join(CACHE, "phase105_result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args(argv)
    if a.fetch:
        fetch()
    r = run()
    print("clock (08:30 jump by year):", r["clock_check_0830_jump"])
    for name, wf in r["sessions"].items():
        print(f"\n== {name} ==  candidates {wf['n_candidates']}")
        print(" reference:", wf["reference"])
        for m in ("logistic", "boosted"):
            x = wf[m]
            print(f" {m}: pooled {x['pooled']} placebo_p={x['placebo_p']} (random {x['placebo_mean']}) passes={x['passes']}")
            for f in x["folds"]:
                print(f"    {f['year']}: n={f.get('n')} mean={f.get('mean_r')} ci={f.get('ci95')}")
        print(" by pair:", wf["by_pair"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
