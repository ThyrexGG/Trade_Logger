"""Phase 134 - after a stop-out, look for a FRESH structure shift and enter again (up to 3 attempts a day).

Same MSS 1-minute entry as Phases 132/133 (close of the break candle, NQ + ES, Mar 2023 - 25 Sep 2026, no time exit, 10 sessions max, hunting window
09:35-11:00). Attempt 1 is exactly Phase 133's trade. If it is STOPPED OUT (closed at a loss) before 11:00 and yesterday's close is still untouched, the
search for a new shift starts after the stop time (a new extension has to confirm and a new close beyond the pullback level launching it has to print);
up to 2 more attempts. Stops: INT (internal 1-minute swing, the user's) and EXT (beyond the extension). Management PLAIN and H1R (half at +1R, then BE).
Reported: attempt-1 only vs ALL attempts (per trade and per day), and the attempts 2 and 3 on their own. R = net P&L / stop distance. EXPLORATORY.

    python -m phase134_reentry
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase127_hold_no_time_exit as p27
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
            spread = float(win["spread"].iloc[0])
            for stp in ("INT", "EXT"):
                after, attempt = None, 0
                while attempt < 3:
                    m = p32.find_mss(win, 1, gup, pc, after)
                    if m is None:
                        break
                    attempt += 1
                    e, t_in = m["e"], m["t_end"]
                    level = m["internal"] if stp == "INT" else m["H"]
                    if (gup and level <= e) or ((not gup) and level >= e):
                        break
                    risk = max(abs(level - e) + spread, 0.05 * a)
                    futall = df[(df.index >= t_in) & (df.index < day + pd.Timedelta(days=p27.HOLD_DAYS))]
                    h, l, c = (futall[x].to_numpy() for x in ("high", "low", "close"))
                    stop = e - side * risk
                    p_pl, k_pl = p27.hold(side, e, stop, risk, pc, None, h, l, c, spread, slip)
                    p_h1, k_h1 = p27.hold(side, e, stop, risk, pc, e + side * risk, h, l, c, spread, slip)
                    out.append({"market": mkt, "day": str(day.date()), "stop": stp, "attempt": attempt, "PLAIN": p_pl / risk, "H1R": p_h1 / risk})
                    # re-entry rule follows the PLAIN trade: stopped out (a loss) and still in the window
                    if p_pl / risk < -0.5 and k_pl < len(futall):
                        after = t_in + pd.Timedelta(minutes=k_pl)
                        if after >= day + pd.Timedelta(hours=11):
                            break
                    else:
                        break
    return pd.DataFrame(out)


def stats(x: np.ndarray, rng) -> str:
    boot = rng.choice(x, size=(2000, len(x)), replace=True).mean(axis=1)
    return f"n={len(x):>4}  win {100 * (x > 0).mean():>3.0f}%  avgR {x.mean():+.3f}  [{np.quantile(boot, .025):+.2f}, {np.quantile(boot, .975):+.2f}]  totalR {x.sum():+.1f}"


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(134)
    for thr in (0.2, 0.7):
        d = run(thr)
        d.to_csv(p1.CACHE + f"/phase134_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range, MSS 1-minute break, re-entry after a stop-out (max 3 attempts) =====")
        for stp in ("INT", "EXT"):
            for mg in ("PLAIN", "H1R"):
                s = d[d.stop == stp]
                print(f"\n{stp} stop, {mg}:")
                print("  attempt 1 only :", stats(s[s.attempt == 1][mg].to_numpy(), rng))
                print("  all attempts   :", stats(s[mg].to_numpy(), rng))
                for k in (2, 3):
                    x = s[s.attempt == k][mg].to_numpy()
                    if len(x) > 5:
                        print(f"  attempt {k} only :", stats(x, rng))
        s = d[d.stop == "INT"]
        print("\nattempts per day (INT):", s.groupby(["market", "day"]).attempt.max().value_counts().sort_index().to_dict())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
