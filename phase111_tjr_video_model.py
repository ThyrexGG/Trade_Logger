"""Phase 111 — TJR's "Once You Learn Price Action..." model, exactly as taught.

Research only. Source: TJR, "Once You Learn Price Action, Trading Becomes
Embarrassingly Simple" (YouTube Xdu6j2E1DEI; transcript supplied by the user).
Three concepts: manipulation (a swing high/low is taken) -> break of structure (a
CLOSE beyond the most recent swing on the other side) -> trade; and, if late, a
continuation entry where the higher-timeframe retrace is a lower-timeframe mini
trend that breaks back (15-minute trend, 5-minute entry). Rules fixed before
any result:

  Swings    2-left/2-right fractals; a swing is known only once the 2 bars after
            it have closed (no look-ahead).
  A REVERSAL (15-minute bars)
            a 15m bar trades above the latest confirmed swing high (manipulation);
            within the next 4 bars (1 hour) a 15m bar CLOSES below the most recent
            confirmed swing low (break of structure) -> SHORT at that close. Stop
            above the highest high since the sweep (+ buffer). Mirror for longs.
  B CONTINUATION (15m trend, 5m entry)
            after an A break of structure, on 5-minute bars: a 5m close above the
            latest 5m swing high (the retrace's mini uptrend), then a 5m close below
            the latest 5m swing low (break back down) -> SHORT at that close. Stop
            above the highest high since that 5m retrace began (+ buffer). Within
            2 hours of the A break. Mirror for longs.
  Targets   2R, or LIQ = the nearest confirmed swing on the trade's side that is
            >= 1R away (15m swings for A, 5m swings for B), capped at 4R (none -> 2R).
  Time      entries 09:30-12:00 New York, flat 15:55; first trade per day per model.
  Markets   NQ, ES, 1-minute data resampled to 5m/15m, 2023-04 -> 2026-10.
  Costs     bar spread + slippage on market fills.
  Cells     2 markets x 2 models x 2 targets = 8.
  PASS      mean R > 0 with 95% CI above 0, positive in >= 3 of 4 years (incl.
            2025 and 2026), better than the mirrored opposite trade (p < 0.05).

    python -m phase111_tjr_video_model
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4

OUT = os.path.join(p1.CACHE, "phase111")
SL = 2  # fractal strength


def _bars(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    b = df.resample(f"{minutes}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "spread": "max"}).dropna()
    b["end"] = b.index + pd.Timedelta(minutes=minutes)
    return b


def _swings(b: pd.DataFrame):
    """Arrays: price of the latest CONFIRMED swing high / low as known at the close of each bar."""
    h, l = b["high"].to_numpy(), b["low"].to_numpy()
    n = len(b)
    last_hi = np.full(n, np.nan)
    last_lo = np.full(n, np.nan)
    hi_list: List[tuple] = []  # (confirm bar, price)
    lo_list: List[tuple] = []
    cur_hi = cur_lo = np.nan
    for k in range(n):
        j = k - SL  # candidate pivot confirmed at bar k
        if j >= SL:
            if h[j] > h[j - 1] and h[j] > h[j - 2] and h[j] >= h[j + 1] and h[j] >= h[j + 2]:
                cur_hi = h[j]
                hi_list.append((k, h[j]))
            if l[j] < l[j - 1] and l[j] < l[j - 2] and l[j] <= l[j + 1] and l[j] <= l[j + 2]:
                cur_lo = l[j]
                lo_list.append((k, l[j]))
        last_hi[k], last_lo[k] = cur_hi, cur_lo
    return last_hi, last_lo, hi_list, lo_list


def _exit(m1: pd.DataFrame, t_entry: pd.Timestamp, t_flat: pd.Timestamp, side: int, entry: float, stop: float, target: float):
    seg = m1.loc[t_entry: t_flat - pd.Timedelta(seconds=1)]
    h, l = seg["high"].to_numpy(), seg["low"].to_numpy()
    for k in range(len(seg)):
        if (side > 0 and l[k] <= stop) or (side < 0 and h[k] >= stop):
            return stop, "stop"
        if (side > 0 and h[k] >= target) or (side < 0 and l[k] <= target):
            return target, "target"
    return (seg["open"].iloc[-1] if len(seg) else entry), "time"


def _target(side, entry, risk, swings_list, upto_bar, mode):
    if mode == "2R":
        return entry + side * 2 * risk
    prices = [p for (k, p) in swings_list if k <= upto_bar]
    cand = [p for p in prices if (side < 0 and entry - 4 * risk <= p <= entry - risk) or (side > 0 and entry + risk <= p <= entry + 4 * risk)]
    return (max(cand) if side < 0 else min(cand)) if cand else entry + side * 2 * risk


def _trade(symbol, m1, t_entry, t_flat, side, entry, stop, spread, mode_target, swings_list, upto_bar, model, extra):
    risk = abs(entry - stop)
    if risk <= 0 or risk < 2 * spread:
        return None
    slip = p1.SLIPPAGE[symbol]
    tgt = _target(side, entry, risk, swings_list, upto_bar, mode_target)
    res = {}
    for sd in (side, -side):
        st = entry - sd * risk
        tg = entry + sd * abs(tgt - entry)
        px, reason = _exit(m1, t_entry, t_flat, sd, entry, st, tg)
        cost = spread + slip + (slip if reason in ("stop", "time") else 0.0)
        res[sd] = ((sd * (px - entry) - cost) / risk, reason)
    return {"symbol": symbol, "model": model, "target": mode_target, "time": str(t_entry), "day": str(t_entry.date()),
            "side": side, "entry": round(entry, 2), "stop": round(stop, 2), "risk": round(risk, 2),
            "target_r": round(abs(tgt - entry) / risk, 2), "exit": res[side][1], "r": round(res[side][0], 4),
            "r_opposite": round(res[-side][0], 4), **extra}


def run_symbol(symbol: str) -> pd.DataFrame:
    m1 = p1.load(symbol, "M1")
    m1 = m1[m1.index >= pd.Timestamp("2023-04-01")]
    b15, b5 = _bars(m1, 15), _bars(m1, 5)
    hi15, lo15, hl15, ll15 = _swings(b15)
    hi5, lo5, hl5, ll5 = _swings(b5)
    buf = p4.BUFFER[symbol]
    h15, l15, c15, e15 = b15["high"].to_numpy(), b15["low"].to_numpy(), b15["close"].to_numpy(), pd.DatetimeIndex(b15["end"])
    h5, l5, c5, e5 = b5["high"].to_numpy(), b5["low"].to_numpy(), b5["close"].to_numpy(), pd.DatetimeIndex(b5["end"])
    rows: List[dict] = []
    done = set()
    for k in range(SL * 2 + 1, len(b15)):
        day = b15.index[k].normalize()
        if day.weekday() >= 5:
            continue
        t_start, t_last, t_flat = day + pd.Timedelta(hours=9, minutes=30), day + pd.Timedelta(hours=12), day + pd.Timedelta(hours=15, minutes=55)
        if b15.index[k] < t_start or e15[k] > t_last:
            continue
        for side in (-1, 1):  # -1: a HIGH swept -> short; +1: a LOW swept -> long
            key = (str(day.date()), side)
            if key in done:
                continue
            ref = hi15[k - 1] if side < 0 else lo15[k - 1]
            if ref != ref or not ((side < 0 and h15[k] > ref) or (side > 0 and l15[k] < ref)):
                continue
            # break of structure within the next 4 bars: close beyond the most recent opposite swing
            for j in range(k, min(k + 5, len(b15))):
                if e15[j] > t_last:
                    break
                opp = lo15[j - 1] if side < 0 else hi15[j - 1]
                if opp == opp and ((side < 0 and c15[j] < opp) or (side > 0 and c15[j] > opp)):
                    ext = h15[k:j + 1].max() if side < 0 else l15[k:j + 1].min()
                    stop = ext + buf if side < 0 else ext - buf
                    t_entry = e15[j]
                    spread = float(m1.loc[: t_entry - pd.Timedelta(seconds=1), "spread"].iloc[-1])
                    for tm in ("2R", "LIQ"):
                        t = _trade(symbol, m1, t_entry, t_flat, side, c15[j], stop, spread, tm, ll15 if side < 0 else hl15, j, "A_REVERSAL", {})
                        if t:
                            rows.append(t)
                    rows += _continuation(symbol, m1, b5, h5, l5, c5, e5, hi5, lo5, hl5, ll5, t_entry, t_last, t_flat, side, buf)
                    done.add(key)
                    break
    return pd.DataFrame(rows)


def _continuation(symbol, m1, b5, h5, l5, c5, e5, hi5, lo5, hl5, ll5, t_bos, t_last, t_flat, side, buf) -> List[dict]:
    """After a 15m break of structure: 5m counter-break (retrace), then a 5m break back -> entry."""
    i0 = b5.index.searchsorted(t_bos)
    retrace_start = None
    for i in range(i0, len(b5)):
        if e5[i] > min(t_last, t_bos + pd.Timedelta(hours=2)):
            return []
        if retrace_start is None:
            ref = hi5[i - 1] if side < 0 else lo5[i - 1]
            if ref == ref and ((side < 0 and c5[i] > ref) or (side > 0 and c5[i] < ref)):
                retrace_start = i  # the retrace's mini trend has broken against the 15m trend
            continue
        ref = lo5[i - 1] if side < 0 else hi5[i - 1]
        if ref == ref and ((side < 0 and c5[i] < ref) or (side > 0 and c5[i] > ref)):
            ext = h5[retrace_start - 3: i + 1].max() if side < 0 else l5[retrace_start - 3: i + 1].min()
            stop = ext + buf if side < 0 else ext - buf
            t_entry = e5[i]
            spread = float(m1.loc[: t_entry - pd.Timedelta(seconds=1), "spread"].iloc[-1])
            out = []
            for tm in ("2R", "LIQ"):
                t = _trade(symbol, m1, t_entry, t_flat, side, c5[i], stop, spread, tm, ll5 if side < 0 else hl5, i, "B_CONTINUATION", {})
                if t:
                    out.append(t)
            return out
    return []


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(111)
    res: Dict = {"phase": 111, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "cells": {}}
    for s in ("NQ", "ES"):
        t = run_symbol(s)
        t.to_csv(os.path.join(OUT, f"phase111_{s}.csv"), index=False)
        for model in ("A_REVERSAL", "B_CONTINUATION"):
            for tm in ("2R", "LIQ"):
                x = t[(t.model == model) & (t.target == tm)].sort_values("time").groupby("day", as_index=False).head(1)
                rs, opp = x["r"].to_numpy(), x["r_opposite"].to_numpy()
                st = p1.summarize(rs, rng)
                years = {str(y): round(float(g["r"].mean()), 3) for y, g in x.groupby(x["day"].str[:4])}
                n_years = {str(y): int(len(g)) for y, g in x.groupby(x["day"].str[:4])}
                p = float((np.array([np.where(rng.integers(0, 2, len(rs)) == 1, rs, opp).mean() for _ in range(2000)]) >= rs.mean()).mean()) if len(rs) >= 10 else float("nan")
                passed = bool(len(rs) and st["ci95"][0] > 0 and sum(v > 0 for v in years.values()) >= 3
                              and years.get("2025", -1) > 0 and years.get("2026", -1) > 0 and p < 0.05)
                res["cells"][f"{s} | {model} | {tm}"] = {"stats": st, "by_year": years, "n_by_year": n_years,
                                                          "opposite_mean": round(float(opp.mean()), 3) if len(opp) else None,
                                                          "placebo_p": round(p, 4), "exits": x["exit"].value_counts().to_dict(),
                                                          "dollars_at_100_risk": round(float(rs.sum()) * 100), "passes": passed}
    res["verdict"] = "PASS_FOUND" if any(v["passes"] for v in res["cells"].values()) else "NO_EDGE"
    with open(os.path.join(OUT, "phase111_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    print("verdict:", r["verdict"])
    for k, v in r["cells"].items():
        s = v["stats"]
        print(f"{k:<28} N={s.get('n',0):>4} win={s.get('win_rate','-')} mean={s.get('mean_r','-'):>7} ci={s.get('ci95')} opp={v['opposite_mean']} "
              f"p={v['placebo_p']} years={v['by_year']} n={v['n_by_year']} ${v['dollars_at_100_risk']:+,} pass={v['passes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
