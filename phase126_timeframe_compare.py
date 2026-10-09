"""Phase 126 - the TradingView strategy on 1-, 5- and 15-minute charts, NQ + ES, full history.

Same gap-fade rule as tradingview/big_gap_fade_strategy.pine (gap >= thr x the 14-session RTH range, unfilled at
09:45, fade toward yesterday's close, exit 12:00), but the trade is SIMULATED ON THE CHART TIMEFRAME: stop, target and
half-off are checked against that timeframe's bar highs/lows, the time exit is the close of the bar ending 12:00.
When one bar touches both the stop and the target the STOP is taken first (conservative, as in Phases 123-125).
Everything before the entry (gap, entry price, swings) is identical on every timeframe, so a difference between the
timeframes is purely how coarse the exit simulation is. Results are in R (P&L after spread and slippage / stop
distance). EXPLORATORY: none of this is a pre-registered test.

    python -m phase126_timeframe_compare
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase124_structure_stops as p24

TFS = {"1m": None, "5m": "5min", "15m": "15min"}
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "spread": "first"}


def bars(post1: pd.DataFrame, rule):
    if rule is None:
        return post1
    return post1.resample(rule, label="left", closed="left").agg(AGG).dropna()


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
            if day.weekday() > 4 or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0].time() != dt.time(9, 30):
                continue
            pc, a = float(pcl[day]), float(atr[day])
            gap = float(g["open"].iloc[0]) - pc
            if abs(gap) / a < thr:
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
            spread = float(post["spread"].iloc[0])
            far = float(pre["high"].max()) if gup else float(pre["low"].min())
            m1 = df.loc[day + pd.Timedelta(hours=8, minutes=30): t0 - pd.Timedelta(minutes=1)]
            m5 = m1.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            m5 = m5[m5.index + pd.Timedelta(minutes=5) <= t0]
            ev1 = p24.events(*(m1[x].to_numpy() for x in ("open", "high", "low", "close")))
            ev5 = p24.events(*(m5[x].to_numpy() for x in ("open", "high", "low", "close")))
            kind = "H" if gup else "L"
            risks = {"Wide": abs(e - pc), "Tight": max(abs(far - e), 0.10 * a), "Medium": 0.25 * a, "Fixed": 0.0021 * e}
            for nm, ev in (("Struct1m", ev1), ("Struct5m", ev5)):
                sw = p24.pick(ev, kind, e, above=gup, floor=0.05 * a)
                risks[nm] = abs(sw - e) + spread if sw is not None else abs(e - pc)
            for tf, rule in TFS.items():
                pb = bars(post, rule)
                for nm, risk in risks.items():
                    stop = e - side * risk
                    for tgt, tp1 in (("Close", None), ("Half1R", e + side * risk)):
                        if tgt == "Half1R" and nm == "Wide":
                            continue  # 1R is already yesterday's close
                        pnl = p24.simulate(pb, side, e, stop, risk, pc, tp1, "PC" if tp1 is None else "HALF", spread, slip)
                        out.append({"market": mkt, "day": str(day.date()), "tf": tf, "stop": nm, "target": tgt, "risk": risk, "r": pnl / risk})
    return pd.DataFrame(out)


def summarize(d: pd.DataFrame, rng) -> pd.DataFrame:
    rows = []
    for (tf, stop, tgt), g in d.groupby(["tf", "stop", "target"], sort=False):
        r = g.r.to_numpy()
        boot = rng.choice(r, size=(2000, len(r)), replace=True).mean(axis=1)
        gp, gl = r[r > 0].sum(), -r[r < 0].sum()
        rows.append({"tf": tf, "stop": stop, "target": tgt, "n": len(r), "win%": (r > 0).mean() * 100, "avgR": r.mean(), "lo": np.quantile(boot, .025), "hi": np.quantile(boot, .975),
                     "PF": gp / gl if gl else np.nan, "totalR": r.sum()})
    return pd.DataFrame(rows)


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(126)
    for thr in (0.2, 0.7):
        d = run(thr)
        d.to_csv(p1.CACHE + f"/phase126_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range, Mar 2023 - Oct 2026, NQ + ES pooled =====")
        s = summarize(d, rng)
        print(s.round(3).to_string(index=False))
        print("\n-- per market (avgR) --")
        print(d.groupby(["market", "tf", "stop", "target"]).r.agg(["count", "mean"]).round(3).unstack("tf").to_string())
        d["year"] = d.day.str[:4]
        print("\n-- per year (avgR, pooled) --")
        print(d.groupby(["year", "tf"]).r.mean().unstack("tf").round(3).to_string())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
