"""Phase 103b — TJR's model as written in public breakdowns, on 1-minute bars.

Research only. Pre-registered before running (see docs/PHASE_103_TJR_DIAGNOSIS.md):

  Bias      1-hour swing structure from bars closed before 08:30 NY: the last two
            1H swing highs AND lows (2-left/2-right fractals over the prior 5
            days) both rising -> longs only; both falling -> shorts only; else no trade.
  Liquidity previous day high/low (09:30-16:00), previous week high/low, Asia
            (20:00-00:00) and London (02:00-05:00) highs/lows, and 1H swing
            highs/lows from the prior 48h not yet traded through by 08:30.
            Longs need a sweep of a LOW, shorts of a HIGH.
  Window    sweeps and entries 08:30-11:00 NY; flat at 12:00.
  Sweep     a 1-minute bar trades through the level and a bar closes back
            inside within 2 bars.
  Shift     within 5 bars of the sweep extreme, a close beyond the high (longs)
            / low (shorts) of the 3 bars before the extreme.
  Entry     limit at the displacement origin: the last opposite-colour candle
            between the extreme and the shift bar (longs: its high). Valid 15
            bars; cancelled if the sweep extreme breaks first.
  Stop      beyond the sweep extreme by NQ 1.00 / ES 0.25.
  Exits     50% at +1R; rest at the nearest opposite liquidity level that is at
            least 2R away (cap 5R; none -> 3R). Stop is never moved. Flat 12:00.
  Costs     bar spread at entry + slippage on market exits (NQ 0.50, ES 0.10);
            stops tighter than 2x spread are skipped.
  Per day   first valid setup per instrument.

Data: whatever 1-minute history the MT5 terminal holds (100k-bar cap -> ~3 months).
    python -m phase103b_tjr_m1
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1

BUFFER = {"NQ": 1.00, "ES": 0.25}
SWEEP_CLOSE_BARS = 2
SHIFT_BARS = 5
FILL_BARS = 15
TP1_R, TP1_SIZE = 1.0, 0.5
TP2_MIN_R, TP2_MAX_R, TP2_DEFAULT_R = 2.0, 5.0, 3.0
RESULT_PATH = os.path.join(p1.CACHE, "phase103b_result.json")


@dataclass
class M1Trade:
    day: str
    symbol: str
    side: str
    level: str
    entry_time: str
    entry: float
    stop: float
    risk: float
    tp2: float
    outcome: str
    r: float
    r_gross: float


def _fractals(h: pd.Series, l: pd.Series) -> Tuple[pd.Series, pd.Series]:
    hi = h[(h > h.shift(1)) & (h > h.shift(2)) & (h >= h.shift(-1)) & (h >= h.shift(-2))]
    lo = l[(l < l.shift(1)) & (l < l.shift(2)) & (l <= l.shift(-1)) & (l <= l.shift(-2))]
    return hi, lo


def day_context(df: pd.DataFrame, day: pd.Timestamp) -> Optional[dict]:
    t830 = day + pd.Timedelta(hours=8, minutes=30)
    hist = df.loc[day - pd.Timedelta(days=7): t830 - pd.Timedelta(seconds=1)]
    if len(hist) < 500:
        return None
    h1 = hist.resample("1h").agg({"high": "max", "low": "min"}).dropna()
    # a fractal needs 2 bars after it, all closed before 08:30
    shi, slo = _fractals(h1["high"], h1["low"])
    shi, slo = shi.iloc[:-0 or None], slo
    recent_hi = shi[shi.index >= day - pd.Timedelta(days=5)]
    recent_lo = slo[slo.index >= day - pd.Timedelta(days=5)]
    bias = 0
    if len(recent_hi) >= 2 and len(recent_lo) >= 2:
        if recent_hi.iloc[-1] > recent_hi.iloc[-2] and recent_lo.iloc[-1] > recent_lo.iloc[-2]:
            bias = 1
        elif recent_hi.iloc[-1] < recent_hi.iloc[-2] and recent_lo.iloc[-1] < recent_lo.iloc[-2]:
            bias = -1
    # liquidity
    highs: Dict[str, float] = {}
    lows: Dict[str, float] = {}
    formed: Dict[str, pd.Timestamp] = {}
    rth = df[(df.index.time >= dt.time(9, 30)) & (df.index.time < dt.time(16, 0))]
    prev_days = sorted({d for d in rth.index.normalize() if d < day})
    if not prev_days:
        return None
    pd_bars = rth.loc[prev_days[-1]: prev_days[-1] + pd.Timedelta(hours=16)]
    highs["PDH"], lows["PDL"] = pd_bars["high"].max(), pd_bars["low"].min()
    formed["PDH"] = formed["PDL"] = prev_days[-1] + pd.Timedelta(hours=16)
    wk_start = day - pd.Timedelta(days=day.weekday() + 7)
    pw = df.loc[wk_start: wk_start + pd.Timedelta(days=5)]
    if len(pw):
        highs["PWH"], lows["PWL"] = pw["high"].max(), pw["low"].min()
        formed["PWH"] = formed["PWL"] = pw.index[-1]
    asia = df.loc[day - pd.Timedelta(hours=4): day - pd.Timedelta(seconds=1)]
    if len(asia):
        highs["ASIA_H"], lows["ASIA_L"] = asia["high"].max(), asia["low"].min()
        formed["ASIA_H"] = formed["ASIA_L"] = day
    ldn = df.loc[day + pd.Timedelta(hours=2): day + pd.Timedelta(hours=5) - pd.Timedelta(seconds=1)]
    if len(ldn):
        highs["LDN_H"], lows["LDN_L"] = ldn["high"].max(), ldn["low"].min()
        formed["LDN_H"] = formed["LDN_L"] = day + pd.Timedelta(hours=5)
    for ts, v in shi[shi.index >= day - pd.Timedelta(hours=48)].items():
        after = hist.loc[ts + pd.Timedelta(hours=1):]
        if not len(after) or after["high"].max() <= v:
            highs[f"H1_SH_{ts:%d%H}"] = v
    for ts, v in slo[slo.index >= day - pd.Timedelta(hours=48)].items():
        after = hist.loc[ts + pd.Timedelta(hours=1):]
        if not len(after) or after["low"].min() >= v:
            lows[f"H1_SL_{ts:%d%H}"] = v
    # liquidity is only liquidity while untouched: drop session/day/week levels
    # already traded through between their formation and 08:30
    for name in list(highs):
        if name in formed:
            after = hist.loc[formed[name]:]
            if len(after) and after["high"].max() > highs[name]:
                del highs[name]
    for name in list(lows):
        if name in formed:
            after = hist.loc[formed[name]:]
            if len(after) and after["low"].min() < lows[name]:
                del lows[name]
    return {"bias": bias, "highs": highs, "lows": lows}


def trade_day(symbol: str, df: pd.DataFrame, day: pd.Timestamp, ctx: dict) -> Optional[M1Trade]:
    if ctx["bias"] == 0:
        return None
    side = ctx["bias"]
    levels = ctx["lows"] if side > 0 else ctx["highs"]
    opp = ctx["highs"] if side > 0 else ctx["lows"]
    win = df.loc[day + pd.Timedelta(hours=8, minutes=30): day + pd.Timedelta(hours=12) - pd.Timedelta(seconds=1)]
    if len(win) < 60:
        return None
    o, h, l, c, spr = (win[k].to_numpy() for k in ("open", "high", "low", "close", "spread"))
    idx = win.index
    i_last = idx.searchsorted(day + pd.Timedelta(hours=11))
    n = len(win)
    spent: set = set()
    for i in range(i_last):
        swept = [name for name, v in levels.items() if name not in spent and ((side > 0 and l[i] < v) or (side < 0 and h[i] > v))]
        if not swept:
            continue
        spent.update(swept)  # the first breach of a level is its sweep; it is not liquidity afterwards
        lvl_name = swept[0]
        lvl = levels[lvl_name]
        # close back inside within 2 bars
        rec = next((j for j in range(i, min(i + SWEEP_CLOSE_BARS + 1, n)) if (side > 0 and c[j] > lvl) or (side < 0 and c[j] < lvl)), None)
        if rec is None:
            continue
        ext = int(i + np.argmin(l[i:rec + 1])) if side > 0 else int(i + np.argmax(h[i:rec + 1]))
        lead = range(max(0, ext - 3), ext)
        if not lead:
            continue
        ref = max(h[k] for k in lead) if side > 0 else min(l[k] for k in lead)
        shift = next((j for j in range(ext + 1, min(ext + 1 + SHIFT_BARS, n)) if (side > 0 and c[j] > ref) or (side < 0 and c[j] < ref)), None)
        if shift is None:
            continue
        origin = None
        for k in range(shift - 1, ext - 1, -1):
            if (side > 0 and c[k] < o[k]) or (side < 0 and c[k] > o[k]):
                origin = k
                break
        if origin is None:
            origin = ext
        entry = h[origin] if side > 0 else l[origin]
        if (side > 0 and not entry < c[shift]) or (side < 0 and not entry > c[shift]):
            continue  # the "limit" would already be through the market: that's a chase, not a retrace entry
        stop = (l[ext] - BUFFER[symbol]) if side > 0 else (h[ext] + BUFFER[symbol])
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        fill = None
        for f in range(shift + 1, min(shift + 1 + FILL_BARS, i_last)):
            if (side > 0 and l[f] <= stop) or (side < 0 and h[f] >= stop):
                break
            if (side > 0 and l[f] <= entry) or (side < 0 and h[f] >= entry):
                fill = f
                break
        if fill is None or risk < 2 * spr[fill]:
            continue
        tp1 = entry + side * TP1_R * risk
        cand = [v for v in opp.values() if (side > 0 and entry + TP2_MIN_R * risk <= v <= entry + TP2_MAX_R * risk)
                or (side < 0 and entry - TP2_MAX_R * risk <= v <= entry - TP2_MIN_R * risk)]
        tp2 = (min(cand) if side > 0 else max(cand)) if cand else entry + side * TP2_DEFAULT_R * risk
        return _manage(symbol, day, side, lvl_name, idx, o, h, l, spr, fill, entry, stop, risk, tp1, tp2, n)
    return None


def _manage(symbol, day, side, lvl_name, idx, o, h, l, spr, fill, entry, stop, risk, tp1, tp2, n) -> M1Trade:
    def thru(k, px, fav):
        if fav:
            return h[k] >= px if side > 0 else l[k] <= px
        return l[k] <= px if side > 0 else h[k] >= px

    slip = p1.SLIPPAGE[symbol]
    cost = float(spr[fill])
    r1 = None
    outcome = None
    gross = 0.0
    if thru(fill, stop, False):
        outcome, gross, cost = "stop", -risk, cost + slip
    else:
        for k in range(fill + 1, n):
            if thru(k, stop, False):
                if r1 is None:
                    outcome, gross, cost = "stop", -risk, cost + slip
                else:
                    outcome, gross, cost = "tp1+stop", TP1_SIZE * TP1_R * risk - (1 - TP1_SIZE) * risk, cost + (1 - TP1_SIZE) * slip
                break
            if r1 is None and thru(k, tp1, True):
                r1 = True
            if r1 and thru(k, tp2, True):
                outcome = "tp1+tp2"
                gross = TP1_SIZE * TP1_R * risk + (1 - TP1_SIZE) * abs(tp2 - entry)
                break
        if outcome is None:
            px = o[-1] if n else entry
            rem = side * (px - entry)
            if r1:
                outcome, gross = "tp1+time", TP1_SIZE * TP1_R * risk + (1 - TP1_SIZE) * rem
                cost += (1 - TP1_SIZE) * slip
            else:
                outcome, gross = "time", rem
                cost += slip
    return M1Trade(day=str(day.date()), symbol=symbol, side="LONG" if side > 0 else "SHORT", level=lvl_name,
                   entry_time=str(idx[fill]), entry=round(entry, 2), stop=round(stop, 2), risk=round(risk, 2),
                   tp2=round(tp2, 2), outcome=outcome, r=round((gross - cost) / risk, 4), r_gross=round(gross / risk, 4))


def run() -> Dict:
    rng = np.random.default_rng(1032)
    out: Dict = {"phase": "103b", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "symbols": {}}
    all_trades: List[M1Trade] = []
    for s in p1.SYMBOLS:
        df = p1.load(s, "M1")
        days = sorted({d for d in df.index.normalize() if d.weekday() < 5})
        trades, bias_days, tested = [], {1: 0, -1: 0, 0: 0}, 0
        for day in days:
            ctx = day_context(df, day)
            if ctx is None:
                continue
            tested += 1
            bias_days[ctx["bias"]] += 1
            t = trade_day(s, df, day, ctx)
            if t:
                trades.append(t)
        rs = np.array([t.r for t in trades])
        out["symbols"][s] = {
            "data_from": str(df.index[0]), "data_to": str(df.index[-1]), "days_tested": tested, "bias_days": bias_days,
            "stats": p1.summarize(rs, rng),
            "gross_mean_r": round(float(np.mean([t.r_gross for t in trades])), 3) if trades else None,
            "outcomes": {k: sum(1 for t in trades if t.outcome == k) for k in sorted({t.outcome for t in trades})},
        }
        all_trades += trades
    rs = np.array([t.r for t in all_trades])
    out["pooled"] = p1.summarize(rs, rng)
    out["trades"] = [asdict(t) for t in all_trades]
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    return out


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    for s, v in r["symbols"].items():
        print(s, json.dumps({k: v[k] for k in v if k != "trades"}, default=str))
    print("pooled", r["pooled"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
