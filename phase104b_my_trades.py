"""Phase 104b — line your own NQ/ES trades up against Phase 104's setups.

Read-only: pulls your closed NDX100 / SPX500 positions from the local MT5
terminal (history only, never an order), converts them to New York time,
and for each one finds the Phase 104 candidate setup on the same index and
side whose entry is within MATCH_MIN minutes. For a match it shows the level
that was swept, the checklist items present, the walk-forward model scores
(models trained only on years BEFORE the trade) and the setup's mechanical
result next to yours.

    python -m phase104b_my_trades
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4

MATCH_MIN = 10
SYM = {"NDX100": "NQ", "SPX500": "ES"}
OUT_CSV = os.path.join(p1.CACHE, "phase104b_my_trades.csv")


def _server_to_ny(ts: int) -> pd.Timestamp:
    server = pd.Timestamp(ts, unit="s")
    hours = p1.SERVER_MINUS_NY_HOURS_BEFORE if server < p1.SERVER_CLOCK_CHANGE else p1.SERVER_MINUS_NY_HOURS
    return server - pd.Timedelta(hours=hours)


def my_positions() -> pd.DataFrame:  # pragma: no cover - needs the local terminal
    import MetaTrader5 as mt5

    if not mt5.initialize(timeout=30000):
        raise SystemExit(f"MT5 terminal not reachable: {mt5.last_error()}")
    try:
        frm, to = dt.datetime(2020, 1, 1), dt.datetime.now() + dt.timedelta(days=2)
        deals = [d for d in (mt5.history_deals_get(frm, to) or []) if d.symbol in SYM]
        orders = {o.position_id: o for o in (mt5.history_orders_get(frm, to) or []) if o.symbol in SYM and o.sl}
    finally:
        mt5.shutdown()
    rows: Dict[int, dict] = {}
    for d in sorted(deals, key=lambda x: x.time):
        p = rows.setdefault(d.position_id, {"position": d.position_id, "symbol": SYM[d.symbol], "volume": 0.0,
                                            "profit": 0.0, "exit_time": None, "exit": None})
        if d.entry == 0:  # IN
            p.update(entry_time=_server_to_ny(d.time), side=1 if d.type == 0 else -1, entry=d.price, volume=d.volume)
        else:
            p["exit_time"], p["exit"] = _server_to_ny(d.time), d.price
        p["profit"] += d.profit + d.commission + d.swap
    out = pd.DataFrame([r for r in rows.values() if "entry_time" in r and r["exit_time"] is not None])
    if out.empty:
        return out
    out["sl"] = [orders[p].sl if p in orders else np.nan for p in out["position"]]
    risk = (out["entry"] - out["sl"]).abs()
    out["my_r"] = np.where(risk > 0, out["side"] * (out["exit"] - out["entry"]) / risk, np.nan)
    return out.sort_values("entry_time").reset_index(drop=True)


def scored_candidates() -> pd.DataFrame:
    """Phase 104 candidates with out-of-sample scores: each year scored by models trained on earlier years only."""
    cand = pd.read_csv(os.path.join(p1.CACHE, "phase104_candidates.csv"))
    cand["year"] = cand["day"].str[:4].astype(int)
    cand["y"] = (cand["r"] > 0).astype(int)
    cand["time"] = pd.to_datetime(cand["time"])
    for name, make in p4._models().items():
        cand[f"score_{name}"] = np.nan
        cand[f"top25_{name}"] = False
        for yr in sorted(cand["year"].unique()):
            train, test = cand[cand.year < yr], cand[cand.year == yr]
            if len(train) < 200:
                continue
            mdl = make().fit(train[p4.FEATURES], train["y"])
            thr = float(np.quantile(mdl.predict_proba(train[p4.FEATURES])[:, 1], 1 - p4.TOP_FRACTION))
            s = mdl.predict_proba(test[p4.FEATURES])[:, 1]
            cand.loc[test.index, f"score_{name}"] = s
            cand.loc[test.index, f"top25_{name}"] = s >= thr
    return cand


def checklist(c: pd.Series, med: pd.Series) -> List[str]:
    ticks = []
    if c["equal"]:
        ticks.append("equal highs/lows")
    if c["family"] in ("PD", "PW"):
        ticks.append("prev day/week level")
    if c["disp_atr"] >= med["disp_atr"]:
        ticks.append("strong reversal")
    if c["smt"]:
        ticks.append("SMT")
    if c["fvg"]:
        ticks.append("FVG")
    if c["room_r"] >= 2:
        ticks.append("room to target")
    if c["stop_atr"] >= med["stop_atr"]:
        ticks.append("not a tight stop")
    return ticks


def match() -> pd.DataFrame:
    mine = my_positions()
    cand = scored_candidates()
    med = cand[["disp_atr", "stop_atr"]].median()
    rows = []
    for _, t in mine.iterrows():
        et = pd.Timestamp(t["entry_time"])
        day = str(et.date())
        same = cand[(cand.day == day) & (cand.symbol == t["symbol"])]
        in_window = dt.time(8, 30) <= et.time() < dt.time(11, 0)
        near = same[(same.side == t["side"])].assign(gap=lambda d: (d["time"] - et).abs().dt.total_seconds() / 60)
        near = near[near.gap <= MATCH_MIN].sort_values("gap")
        row = {"date": day, "time_ny": et.strftime("%H:%M"), "symbol": t["symbol"], "side": "LONG" if t["side"] > 0 else "SHORT",
               "entry": t["entry"], "your_profit": round(t["profit"], 2), "your_r": round(t["my_r"], 2) if t["my_r"] == t["my_r"] else None,
               "in_setup_window": in_window, "setups_that_morning": int(len(same))}
        if len(near):
            c = near.iloc[0]
            row.update({"match": True, "minutes_apart": round(c["gap"], 1), "level_swept": c["family"],
                        "checklist": ", ".join(checklist(c, med)) or "-", "checklist_count": len(checklist(c, med)),
                        "model_score": round(c["score_boosted"], 3) if c["score_boosted"] == c["score_boosted"] else None,
                        "model_would_take": bool(c["top25_boosted"]), "setup_result_r": c["r"]})
        else:
            row.update({"match": False})
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    return out


def main(argv=None) -> int:  # pragma: no cover
    out = match()
    if out.empty:
        print("No closed NDX100/SPX500 positions in this MT5 account.")
        return 0
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    print(out.to_string(index=False))
    m = out[out["match"]]
    print(f"\n{len(out)} trades · {int(out.in_setup_window.sum())} inside 08:30-11:00 · {len(m)} match a scanner setup "
          f"(same index + side, within {MATCH_MIN} min) · model would take {int(m.model_would_take.sum()) if len(m) else 0}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
