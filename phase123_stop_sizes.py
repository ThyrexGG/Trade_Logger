"""Phase 123 - how big are the gap-fade stops, and what do other stop placements do?

The Phase 117-122 'wide' stop is as far from the entry as the target (yesterday's close) is: 1:1 by
construction, so its size is whatever is left of the gap at 09:45 (hundreds of points on NQ). This lists
the real stop sizes and compares other placements on the same setups (gap >= 0.2 x the 14-session range,
unfilled at 09:45, fade toward yesterday's close, target = yesterday's close, exit 12:00, NQ + ES,
2023-04..2026-10). Every option is judged by points made per trade as a % of the average daily range
(R is not comparable between stop sizes). EXPLORATORY: nothing here is a tested edge.

  WIDE   stop as far as the target (the indicator's default)
  TIGHT  just beyond the 09:30-09:45 extreme on the far side (min 0.10 x range)
  A25    0.25 x the average daily range      A50   0.5 x the average daily range
  FIX    0.21% of the entry price (about 64 NQ points, the user's usual stop)

    python -m phase123_stop_sizes
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1

THR = 0.2


def run() -> pd.DataFrame:
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
            if day.weekday() > 4 or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0].time() != dt.time(9, 30):
                continue
            pc, a = float(pcl[day]), float(atr[day])
            gap = float(g["open"].iloc[0]) - pc
            if abs(gap) / a < THR:
                continue
            gup = gap > 0
            t0, noon = day + pd.Timedelta(hours=9, minutes=45), day + pd.Timedelta(hours=12)
            pre, post = g[g.index < t0], g[(g.index >= t0) & (g.index < noon)]
            if len(pre) < 10 or len(post) < 10:
                continue
            e = float(pre["close"].iloc[-1])
            if ((pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)) or (gup and e <= pc) or ((not gup) and e >= pc):
                continue
            side = -1 if gup else 1
            dist = abs(e - pc)
            far = float(pre["high"].max()) if gup else float(pre["low"].min())
            opts = {"WIDE": dist, "TIGHT": max(abs(far - e), 0.10 * a), "A25": 0.25 * a, "A50": 0.5 * a, "FIX": 0.0021 * e}
            h, l, c = post["high"].to_numpy(), post["low"].to_numpy(), post["close"].to_numpy()
            cost = float(post["spread"].iloc[0]) + slip
            for name, risk in opts.items():
                stop = e - side * risk
                pnl, hit = None, "time"
                for k in range(len(post)):
                    if (side > 0 and l[k] <= stop) or (side < 0 and h[k] >= stop):
                        pnl, hit = -risk - slip, "stop"
                        break
                    if (side > 0 and h[k] >= pc) or (side < 0 and l[k] <= pc):
                        pnl, hit = dist, "target"
                        break
                if pnl is None:
                    pnl = side * (c[-1] - e)
                pnl -= cost
                out.append({"market": mkt, "day": str(day.date()), "stop": name, "risk": risk, "risk_pct": risk / e * 100, "risk_atr": risk / a, "pnl_atr": pnl / a, "hit": hit})
    return pd.DataFrame(out)


def main(argv=None) -> int:  # pragma: no cover
    d = run()
    d.to_csv(p1.CACHE + "/phase123_rows.csv", index=False)
    print(f"{'mkt':<4}{'stop':<6}{'n':>5}{'median stop':>13}{'% of price':>11}{'x range':>9}{'stopped':>9}{'target':>8}{'win':>6}{'avg P&L (% of range)':>22}")
    for (m, s), g in d.groupby(["market", "stop"], sort=False):
        print(f"{m:<4}{s:<6}{len(g):>5}{g.risk.median():>12.1f}p{g.risk_pct.median():>10.2f}%{g.risk_atr.median():>9.2f}{(g.hit == 'stop').mean() * 100:>8.0f}%{(g.hit == 'target').mean() * 100:>7.0f}%{(g.pnl_atr > 0).mean() * 100:>5.0f}%{g.pnl_atr.mean() * 100:>+21.1f}%")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
