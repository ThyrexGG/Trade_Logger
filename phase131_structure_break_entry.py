"""Phase 131 - enter on a STRUCTURE BREAK instead of at a fixed 09:45.

Rules written before any result was looked at (all 16 variants are reported, none is picked afterwards):
DAYS     gap >= thr x the 14-session RTH range (thr 0.2 and 0.7), NQ + ES, Mar 2023 - 25 Sep 2026; fade toward yesterday's close.
TRIGGER  on 1-minute (S1) or 5-minute (S5) bars from the 09:30 open: gap up -> SHORT when a bar CLOSES below the latest confirmed
         swing low (two-candle swing: bearish then bullish candle, price = the lower of the two lows, known when the second candle
         closes); gap down -> LONG on the mirror image. Earliest entry = a bar ending 09:40, latest = a bar ending 11:00.
         Invalid (day skipped) if yesterday's close was touched at or before the trigger bar, or the close is not on the gap side.
ENTRY    the close of the trigger bar.
STOP     RECENT = beyond the latest confirmed swing high (short) / low (long) before the trigger (else the extreme since the open);
         EXTREME = beyond the highest high (short) / lowest low (long) since the 09:30 open. Plus the spread; risk floor 0.05 x range.
FILTER   RR>=1 (skip when the distance to yesterday's close is less than 1R) or ALL.
EXIT     PLAIN = stop or yesterday's close; H1R = half at +1R then stop to breakeven, rest to yesterday's close. No time exit,
         up to 10 sessions, stop before target inside one bar.
BASE     the fixed 09:45 entry with the wide stop (1R = distance to yesterday's close), same days, plain: the paired benchmark.
R = net P&L (spread + slippage) / stop distance. EXPLORATORY; 16 variants x 2 thresholds means chance winners are expected.

    python -m phase131_structure_break_entry
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase127_hold_no_time_exit as p27

AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}


def find_trigger(bars: pd.DataFrame, tfmin: int, gup: bool, pc: float):
    """Returns (bar position, entry time (bar end), entry price, recent_stop, extreme_stop) or None."""
    o, h, l, c = (bars[x].to_numpy() for x in ("open", "high", "low", "close"))
    ends = bars.index + pd.Timedelta(minutes=tfmin)
    open_day = bars.index[0].normalize()
    t_min, t_max = open_day + pd.Timedelta(hours=9, minutes=40), open_day + pd.Timedelta(hours=11)
    last_sw_low = last_sw_high = None
    run_hi, run_lo = h[0], l[0]
    for k in range(1, len(c)):
        run_hi, run_lo = max(run_hi, h[k]), min(run_lo, l[k])
        if (gup and l[k] <= pc) or ((not gup) and h[k] >= pc):
            return None
        if ends[k] > t_max:
            return None
        if ends[k] >= t_min and ((gup and last_sw_low is not None and c[k] < last_sw_low and c[k] > pc) or
                                 ((not gup) and last_sw_high is not None and c[k] > last_sw_high and c[k] < pc)):
            recent = (last_sw_high if last_sw_high is not None else run_hi) if gup else (last_sw_low if last_sw_low is not None else run_lo)
            return k, ends[k], float(c[k]), float(recent), float(run_hi if gup else run_lo)
        # confirm swings with bar k (known at its close)
        if c[k - 1] > o[k - 1] and c[k] < o[k]:
            last_sw_high = max(h[k - 1], h[k])
        if c[k - 1] < o[k - 1] and c[k] > o[k]:
            last_sw_low = min(l[k - 1], l[k])
    return None


def run(thr: float) -> pd.DataFrame:
    out, days = [], []
    for mkt in ("NQ", "ES"):
        df = p1.load(mkt, "M1")
        df = df[df.index >= pd.Timestamp("2023-03-01")]
        rth = df[(df.index.time >= dt.time(9, 30)) & (df.index.time < dt.time(16, 0))]
        gb = rth.groupby(rth.index.normalize())
        atr = (gb["high"].max() - gb["low"].min()).shift(1).rolling(14).mean()
        pcl = gb["close"].last().shift(1)
        slip = p1.SLIPPAGE[mkt]
        for day, g in gb:
            if day > p27.LAST_DAY or day.weekday() > 4 or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0].time() != dt.time(9, 30):
                continue
            pc, a = float(pcl[day]), float(atr[day])
            gap = float(g["open"].iloc[0]) - pc
            if abs(gap) / a < thr:
                continue
            gup = gap > 0
            side = -1 if gup else 1
            win = g[g.index < day + pd.Timedelta(hours=11)]
            if len(win) < 60:
                continue
            # --- baseline: fixed 09:45 entry, wide stop
            t0 = day + pd.Timedelta(hours=9, minutes=45)
            pre = g[g.index < t0]
            e0 = float(pre["close"].iloc[-1])
            base_ok = not (((pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)) or (gup and e0 <= pc) or ((not gup) and e0 >= pc))
            days.append({"market": mkt, "day": str(day.date()), "base_ok": base_ok})
            futall = df[(df.index >= day + pd.Timedelta(hours=9, minutes=30)) & (df.index < day + pd.Timedelta(days=p27.HOLD_DAYS))]
            base_r = np.nan
            if base_ok:
                f0 = futall[futall.index >= t0]
                risk0 = abs(e0 - pc)
                pnl, _ = p27.hold(side, e0, e0 - side * risk0, risk0, pc, None, f0["high"].to_numpy(), f0["low"].to_numpy(), f0["close"].to_numpy(), float(pre["spread"].iloc[-1]), slip)
                base_r = pnl / risk0
            for tf, mins in (("S1", 1), ("S5", 5)):
                bars = win if mins == 1 else win.resample(f"{mins}min", label="left", closed="left").agg(AGG).dropna()
                trig = find_trigger(bars, mins, gup, pc)
                if trig is None:
                    continue
                k, t_end, e, recent, extreme = trig
                spread = float(win["spread"].iloc[0])
                fut = futall[futall.index >= t_end]
                h, l, c = fut["high"].to_numpy(), fut["low"].to_numpy(), fut["close"].to_numpy()
                tdist = abs(e - pc)
                for sname, level in (("RECENT", recent), ("EXTREME", extreme)):
                    risk = max(abs(level - e) + spread, 0.05 * a)
                    if (gup and level <= e) or ((not gup) and level >= e):
                        risk = max(0.05 * a, spread)  # degenerate level: use the floor
                    stop = e - side * risk
                    for mg, tp1 in (("PLAIN", None), ("H1R", e + side * risk)):
                        pnl, hrs = p27.hold(side, e, stop, risk, pc, tp1, h, l, c, spread, slip)
                        out.append({"market": mkt, "day": str(day.date()), "tf": tf, "stop": sname, "mgmt": mg, "rr": tdist / risk, "r": pnl / risk, "hours": hrs / 60, "base_r": base_r})
    d = pd.DataFrame(out)
    d.attrs["days"] = pd.DataFrame(days)
    return d


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(131)
    for thr in (0.2, 0.7):
        d = run(thr)
        nd = len(d.attrs["days"])
        d.to_csv(p1.CACHE + f"/phase131_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range: {nd} gap days (NQ+ES); NO entry at 09:45 -> structure break =====")
        print(f"{'tf':<4}{'stop':<9}{'filter':<7}{'mgmt':<6}{'n':>5}{'trig%':>6}{'win%':>6}{'avgR':>8}{'95% interval':>18}{'PF':>6}{'totalR':>8}{'  paired vs 09:45 wide':>24}")
        for flt in ("ALL", "RR>=1"):
            sub = d if flt == "ALL" else d[d.rr >= 1]
            for (tf, st, mg), g in sub.groupby(["tf", "stop", "mgmt"], sort=False):
                r = g.r.to_numpy()
                boot = rng.choice(r, size=(2000, len(r)), replace=True).mean(axis=1)
                gl = -r[r < 0].sum()
                b = g.base_r.dropna()
                pair = f"{(g.loc[b.index, 'r'] - b).mean():+.3f}R (n={len(b)})" if len(b) else "n/a"
                print(f"{tf:<4}{st:<9}{flt:<7}{mg:<6}{len(r):>5}{len(r) / nd * 100:>5.0f}%{(r > 0).mean() * 100:>5.0f}%{r.mean():>+8.3f}   [{np.quantile(boot, .025):+.2f}, {np.quantile(boot, .975):+.2f}]{(r[r > 0].sum() / gl if gl else float('nan')):>6.2f}{r.sum():>+8.1f}{pair:>24}")
        bd = d.drop_duplicates(["market", "day"]).base_r.dropna()
        print(f"\nBaseline 09:45 wide plain on the days that ALSO had a structure break: n={len(bd)} avgR {bd.mean():+.3f}")
        d["year"] = d.day.str[:4]
        print("\n-- per year avgR (filter ALL, PLAIN) --")
        print(d[d.mgmt == "PLAIN"].groupby(["tf", "stop", "year"]).r.mean().unstack("year").round(3).to_string())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
