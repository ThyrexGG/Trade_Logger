"""Phase 132 - a real market-structure shift (MSS) entry, with an optional retest, instead of a fixed time (and instead of
Phase 131's "close below the latest swing low", which is true almost every day and so is just a rushed entry).

Rules fixed before any result was looked at; all 16 variants x 2 thresholds are reported, none picked afterwards.
DAYS     gap >= thr x the 14-session range (0.2, 0.7), NQ + ES, Mar 2023 - 25 Sep 2026; fade toward yesterday's close.
SWINGS   two-candle swings on the chosen bars (1m = S1, 5m = S5), confirmed when the second candle closes.
MSS      gap up -> SHORT. (1) H = a confirmed swing high that is still the highest price since the 09:30 open (the extension /
         liquidity high). (2) L = the pullback low that LAUNCHED that final push (the latest confirmed swing low before H formed;
         else the lowest low before H). (3) the first bar after H whose CLOSE is below L = the structure break. Gap down -> mirrored.
         Valid only if yesterday's close is untouched, the close is still on the gap side, the bar ends between 09:35 and 11:00.
ENTRY    BREAK  = the close of the break bar.
         RETEST = wait for price to retrace to the 50% level of the leg from H down to the break leg's low; fills as a limit at that
                  price; cancelled if H is exceeded or yesterday's close is touched first, or by 12:00.
STOP     beyond H (plus the spread); risk floor 0.05 x range.
FILTER   ALL, or RR>=1 (distance to yesterday's close at least 1R).
EXIT     PLAIN = stop or yesterday's close; H1R = half at +1R, stop to breakeven, rest to yesterday's close. No time exit,
         10 sessions max, stop first inside one bar.
BASE     the fixed 09:45 entry, wide stop, plain, on the same days (paired benchmark).
Entry-time distribution is reported (the point of the exercise: not one fixed time). EXPLORATORY.

    python -m phase132_mss_entry
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase127_hold_no_time_exit as p27

AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}


def find_mss(bars: pd.DataFrame, tfmin: int, gup: bool, pc: float):
    """Returns dict(k, t_end, e, H, leg_extreme) or None. H = the extension extreme (high for a short)."""
    o, h, l, c = (bars[x].to_numpy() for x in ("open", "high", "low", "close"))
    ends = bars.index + pd.Timedelta(minutes=tfmin)
    day0 = bars.index[0].normalize()
    t_min, t_max = day0 + pd.Timedelta(hours=9, minutes=35), day0 + pd.Timedelta(hours=11)
    sw = []  # (confirmed index k, formed-from index k-1, kind 'H'|'L', level)
    run_hi, run_lo = h[0], l[0]
    for k in range(1, len(c)):
        run_hi, run_lo = max(run_hi, h[k]), min(run_lo, l[k])
        if (gup and l[k] <= pc) or ((not gup) and h[k] >= pc):
            return None
        if ends[k] > t_max:
            return None
        ext_kind, ext_run = ("H", run_hi) if gup else ("L", run_lo)
        cands = [s for s in sw if s[2] == ext_kind and abs(s[3] - ext_run) < 1e-9 and s[0] < k]
        if cands and ends[k] >= t_min:
            kH, fH, _, H = cands[-1]
            other = "L" if gup else "H"
            prior = [s for s in sw if s[2] == other and s[0] < fH]
            if prior:
                L = prior[-1][3]
            else:
                L = float(np.min(l[:fH + 1])) if gup else float(np.max(h[:fH + 1]))
            broke = (c[k] < L and c[k] > pc) if gup else (c[k] > L and c[k] < pc)
            if broke:
                leg = float(np.min(l[kH:k + 1])) if gup else float(np.max(h[kH:k + 1]))
                same = [x[3] for x in sw if x[2] == ext_kind]
                return {"k": k, "t_end": ends[k], "e": float(c[k]), "H": float(H), "leg": leg, "internal": float(same[-1]) if same else float(H)}
        if c[k - 1] > o[k - 1] and c[k] < o[k]:
            sw.append((k, k - 1, "H", max(h[k - 1], h[k])))
        if c[k - 1] < o[k - 1] and c[k] > o[k]:
            sw.append((k, k - 1, "L", min(l[k - 1], l[k])))
    return None


def run(thr: float) -> pd.DataFrame:
    out, ndays = [], 0
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
            win = g[g.index < day + pd.Timedelta(hours=12)]
            if len(win) < 60:
                continue
            ndays += 1
            t0 = day + pd.Timedelta(hours=9, minutes=45)
            pre = g[g.index < t0]
            e0 = float(pre["close"].iloc[-1])
            base_ok = not (((pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)) or (gup and e0 <= pc) or ((not gup) and e0 >= pc))
            futall = df[(df.index >= day + pd.Timedelta(hours=9, minutes=30)) & (df.index < day + pd.Timedelta(days=p27.HOLD_DAYS))]
            base_r = np.nan
            if base_ok:
                f0 = futall[futall.index >= t0]
                risk0 = abs(e0 - pc)
                pnl, _ = p27.hold(side, e0, e0 - side * risk0, risk0, pc, None, f0["high"].to_numpy(), f0["low"].to_numpy(), f0["close"].to_numpy(), float(pre["spread"].iloc[-1]), slip)
                base_r = pnl / risk0
            spread = float(win["spread"].iloc[0])
            for tf, mins in (("S1", 1), ("S5", 5)):
                bars = win[win.index < day + pd.Timedelta(hours=11)] if mins == 1 else win[win.index < day + pd.Timedelta(hours=11)].resample(f"{mins}min", label="left", closed="left").agg(AGG).dropna()
                m = find_mss(bars, mins, gup, pc)
                if m is None:
                    continue
                H, floor_r = m["H"], 0.05 * a
                for ent in ("BREAK", "RETEST"):
                    if ent == "BREAK":
                        e, t_in = m["e"], m["t_end"]
                        fut = futall[futall.index >= t_in]
                    else:
                        lvl = H + (m["leg"] - H) * 0.5
                        scan = futall[(futall.index >= m["t_end"]) & (futall.index < day + pd.Timedelta(hours=12))]
                        sh, sl_ = scan["high"].to_numpy(), scan["low"].to_numpy()
                        fill = None
                        for i in range(len(scan)):
                            if (gup and sh[i] >= H) or ((not gup) and sl_[i] <= H):
                                break  # structure invalidated
                            if (gup and sl_[i] <= pc) or ((not gup) and sh[i] >= pc):
                                break
                            if (gup and sh[i] >= lvl) or ((not gup) and sl_[i] <= lvl):
                                fill = i
                                break
                        if fill is None:
                            continue
                        e, t_in = float(lvl), scan.index[fill]
                        fut = futall[futall.index > t_in]
                    risk = max(abs(H - e) + spread, floor_r)
                    if (gup and H <= e) or ((not gup) and H >= e):
                        continue
                    stop, tdist = e - side * risk, abs(e - pc)
                    h, l, c = fut["high"].to_numpy(), fut["low"].to_numpy(), fut["close"].to_numpy()
                    mins_after = (t_in - day).total_seconds() / 60 - 570
                    for mg, tp1 in (("PLAIN", None), ("H1R", e + side * risk)):
                        pnl, hrs = p27.hold(side, e, stop, risk, pc, tp1, h, l, c, spread, slip)
                        out.append({"market": mkt, "day": str(day.date()), "tf": tf, "entry": ent, "mgmt": mg, "rr": tdist / risk, "r": pnl / risk, "hours": hrs / 60,
                                    "min_after_open": mins_after, "base_r": base_r})
    d = pd.DataFrame(out)
    d.attrs["ndays"] = ndays
    return d


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(132)
    for thr in (0.2, 0.7):
        d = run(thr)
        nd = d.attrs["ndays"]
        d.to_csv(p1.CACHE + f"/phase132_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range: {nd} gap days (NQ+ES); entry on a structure shift =====")
        print(f"{'tf':<4}{'entry':<7}{'filter':<7}{'mgmt':<6}{'n':>5}{'trig%':>6}{'win%':>6}{'avgR':>8}{'95% interval':>18}{'PF':>6}{'totalR':>8}{'  paired vs 09:45':>20}")
        for flt in ("ALL", "RR>=1"):
            sub = d if flt == "ALL" else d[d.rr >= 1]
            for (tf, en, mg), g in sub.groupby(["tf", "entry", "mgmt"], sort=False):
                r = g.r.to_numpy()
                boot = rng.choice(r, size=(2000, len(r)), replace=True).mean(axis=1)
                gl = -r[r < 0].sum()
                b = g.base_r.dropna()
                pair = f"{(g.loc[b.index, 'r'] - b).mean():+.3f}R" if len(b) else "n/a"
                print(f"{tf:<4}{en:<7}{flt:<7}{mg:<6}{len(r):>5}{len(r) / nd * 100:>5.0f}%{(r > 0).mean() * 100:>5.0f}%{r.mean():>+8.3f}   [{np.quantile(boot, .025):+.2f}, {np.quantile(boot, .975):+.2f}]{(r[r > 0].sum() / gl if gl else float('nan')):>6.2f}{r.sum():>+8.1f}{pair:>20}")
        print("\n-- entry time (minutes after 09:30 open): 10th / 50th / 90th percentile --")
        print(d.drop_duplicates(["market", "day", "tf", "entry"]).groupby(["tf", "entry"]).min_after_open.quantile([.1, .5, .9]).unstack().round(0).to_string())
        d["year"] = d.day.str[:4]
        print("\n-- per year avgR (filter ALL, PLAIN) --")
        print(d[d.mgmt == "PLAIN"].groupby(["tf", "entry", "year"]).r.mean().unstack("year").round(3).to_string())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
