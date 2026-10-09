"""Phase 133 - the user's stop: the INTERNAL 1-minute swing (not the whole extension, not the wide mirror stop).

Same MSS entry as Phase 132 (1-minute structure, entry at the close of the break candle, no fixed time, NQ + ES, Mar 2023 - 25 Sep 2026):
  EXT   stop just beyond the extension (the high / low of the move; Phase 132).
  INT   stop just beyond the latest confirmed 1-minute swing of the same side at the moment of the break (the internal high for a short /
        internal low for a long; equal to the extension when no lower high / higher low formed yet). Risk floor 0.05 x range.
  WIDE  the old mirror stop (same distance as the target), for reference.
Management: PLAIN (stop or yesterday's close), H1R (half at +1R then breakeven), LADDER (Phase 129/130 ladder + runner is NOT used here; thirds at the
two nearest 1m/5m swings, stop to BE then behind L1, rest to yesterday's close). No time exit, 10 sessions max. R = net P&L / stop distance. EXPLORATORY.

    python -m phase133_internal_stop
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase124_structure_stops as p24
import phase127_hold_no_time_exit as p27
import phase129_structure_ladder as p29
import phase132_mss_entry as p32


def run(thr: float) -> pd.DataFrame:
    out = []
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
            gup, side = gap > 0, (-1 if gap > 0 else 1)
            win = g[g.index < day + pd.Timedelta(hours=11)]
            if len(win) < 60:
                continue
            m = p32.find_mss(win, 1, gup, pc)
            if m is None:
                continue
            e, t_in, spread = m["e"], m["t_end"], float(win["spread"].iloc[0])
            futall = df[(df.index >= t_in) & (df.index < day + pd.Timedelta(days=p27.HOLD_DAYS))]
            h, l, c = (futall[x].to_numpy() for x in ("high", "low", "close"))
            tdist = abs(e - pc)
            m1 = df.loc[day + pd.Timedelta(hours=8, minutes=30): t_in - pd.Timedelta(minutes=1)]
            m5 = m1.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            ev1 = p24.events(*(m1[x].to_numpy() for x in ("open", "high", "low", "close")))
            ev5 = p24.events(*(m5[x].to_numpy() for x in ("open", "high", "low", "close")))
            pk = "L" if gup else "H"
            cands = [x for evx in (ev1, ev5) for x in [q[2] for q in evx if q[1] == pk][-3:] if ((x < e) if gup else (x > e))]
            for nm, level in (("EXT", m["H"]), ("INT", m["internal"]), ("WIDE", None)):
                if level is None:
                    risk = tdist
                else:
                    if (gup and level <= e) or ((not gup) and level >= e):
                        continue
                    risk = max(abs(level - e) + spread, 0.05 * a)
                stop = e - side * risk
                lv = p29.make_levels(side, e, risk, tdist, cands)
                res = {
                    "PLAIN": p27.hold(side, e, stop, risk, pc, None, h, l, c, spread, slip)[0] / risk,
                    "H1R": p27.hold(side, e, stop, risk, pc, e + side * risk, h, l, c, spread, slip)[0] / risk,
                }
                res["LADDER"] = (p29.ladder_sim(side, e, stop, risk, pc, lv, True, h, l, c, spread, slip) / risk) if lv else res["PLAIN"]
                for mg, r in res.items():
                    out.append({"market": mkt, "day": str(day.date()), "stop": nm, "mgmt": mg, "risk": risk, "rr": tdist / risk, "r": r})
    return pd.DataFrame(out)


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(133)
    for thr in (0.2, 0.7):
        d = run(thr)
        d.to_csv(p1.CACHE + f"/phase133_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range, MSS 1-minute break entry, NQ + ES pooled =====")
        print(f"{'stop':<6}{'filter':<7}{'mgmt':<8}{'n':>5}{'med stop':>10}{'win%':>6}{'avgR':>8}{'95% interval':>18}{'PF':>6}{'totalR':>8}")
        for flt in ("ALL", "RR>=1"):
            sub = d if flt == "ALL" else d[d.rr >= 1]
            for (st, mg), g in sub.groupby(["stop", "mgmt"], sort=False):
                r = g.r.to_numpy()
                boot = rng.choice(r, size=(2000, len(r)), replace=True).mean(axis=1)
                gl = -r[r < 0].sum()
                print(f"{st:<6}{flt:<7}{mg:<8}{len(r):>5}{g.risk.median():>10.1f}{(r > 0).mean() * 100:>5.0f}%{r.mean():>+8.3f}   [{np.quantile(boot, .025):+.2f}, {np.quantile(boot, .975):+.2f}]{(r[r > 0].sum() / gl if gl else float('nan')):>6.2f}{r.sum():>+8.1f}")
        d["year"] = d.day.str[:4]
        print("\n-- per year avgR (INT stop, filter ALL) --")
        print(d[d.stop == "INT"].groupby(["mgmt", "year"]).r.mean().unstack("year").round(3).to_string())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
