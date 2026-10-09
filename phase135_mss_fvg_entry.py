"""Phase 135 - the user's real entry: after an MSS, enter on a fair value gap (FVG) that is retested and RESPECTED, or on an INVERSE FVG.

Rules written before any result was looked at; every variant is reported. NQ + ES, Mar 2023 - 25 Sep 2026, 1-minute bars, fade toward yesterday's close, no time exit.
MSS      Phase 132's 1-minute market-structure shift (extension, then a close beyond the pullback level that launched it; 09:35-11:00). No entry at the break.
FVG      three-candle gap in the trade direction formed AFTER the extension (short: bar j with high[j] < low[j-2]; zone = [high[j], low[j-2]]; a long is the mirror).
IFVG     a gap AGAINST the trade formed during the run to the extension (short: bullish gap low[j] > high[j-2], zone = [high[j-2], low[j]]) that a candle then CLOSED
         THROUGH (close below the zone's bottom for a short) = inverted into resistance (support for a long).
ENTRY    on a bar after the break (and after the zone formed / inverted): the wick reaches the zone (short: high >= zone bottom), the candle closes below the zone's TOP
         and is bearish (a rejection; a long is the mirror). Entry at that candle's close. A zone is dead if a candle closes beyond its top (short) before the entry.
         The search ends (no trade) when the extension is exceeded, yesterday's close is touched, or at 12:00. First qualifying bar wins; the most recent zone is used.
STOP     ZONE = just beyond the zone's far edge (short: top) plus the spread, or EXT = just beyond the extension. Risk floor 0.05 x range.
EXIT     PLAIN = stop or yesterday's close; H1R = half at +1R, stop to breakeven, rest to yesterday's close. 10 sessions max, stop first inside a bar.
R = net P&L (spread + slippage) / stop distance. EXPLORATORY: 12 variants x 2 thresholds, so a chance winner is expected.

    python -m phase135_mss_fvg_entry
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase127_hold_no_time_exit as p27
import phase132_mss_entry as p32


def flip(o, h, l, c, sign):
    """Return arrays so that 'short logic' also covers a long (prices negated, highs and lows swapped)."""
    if sign > 0:
        return o, h, l, c
    return -o, -l, -h, -c


def find_entries(o, h, l, c, k, kh, pc, H, last_t):
    """Short logic on (possibly flipped) arrays. Returns {'FVG': (t, zone_top), 'IFVG': (t, zone_top)} for the first rejection of each kind."""
    res = {}
    # IFVG candidates: bullish gaps formed before the break, then closed through (below the bottom)
    ifvg = []
    for j in range(2, k + 1):
        if l[j] > h[j - 2]:
            bot, top = h[j - 2], l[j]
            inv = next((s for s in range(j + 1, k + 1) if c[s] < bot), None)
            if inv is not None:
                ifvg.append([inv, bot, top])
    fvg = []  # bearish gaps formed after the extension: [formed, bottom, top]
    for t in range(kh + 2, last_t):
        if h[t] < l[t - 2]:
            fvg.append([t, h[t], l[t - 2]])
    for t in range(k + 1, last_t):
        if h[t] >= H or l[t] <= pc:
            break
        for name, zones in (("FVG", fvg), ("IFVG", ifvg)):
            if name in res:
                continue
            for z in reversed(zones):
                formed, bot, top = z
                if formed >= t:
                    continue
                if np.any(c[formed + 1:t] > top):   # a candle closed through the top: the zone is dead for a short
                    continue
                if h[t] >= bot and c[t] < top and c[t] < o[t]:
                    res[name] = (t, top, bot, formed)
                    break
        if len(res) == 2:
            break
    return res


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
            w11 = g[g.index < day + pd.Timedelta(hours=11)]
            w12 = g[g.index < day + pd.Timedelta(hours=12)]
            if len(w11) < 60 or len(w12) < 100:
                continue
            m = p32.find_mss(w11, 1, gup, pc)
            if m is None:
                continue
            k = int(np.searchsorted(w11.index.to_numpy(), (m["t_end"] - pd.Timedelta(minutes=1)).to_datetime64()))
            sign = 1 if gup else -1
            o, h, l, c = flip(*(w12[x].to_numpy() for x in ("open", "high", "low", "close")), sign)
            pcs, Hs = sign * pc, (m["H"] if gup else -m["H"])
            kh = int(np.argmax(h[:k + 1]))
            ent = find_entries(o, h, l, c, k, kh, pcs, Hs, len(c))
            spread = float(w12["spread"].iloc[0])
            futall = df[(df.index >= day) & (df.index < day + pd.Timedelta(days=p27.HOLD_DAYS))]
            for kind in ("FVG", "IFVG"):
                if kind not in ent:
                    continue
                t, top_s = ent[kind][:2]
                e = sign * c[t]
                t_in = w12.index[t] + pd.Timedelta(minutes=1)
                fut = futall[futall.index >= t_in]
                hh, ll, cc = (fut[x].to_numpy() for x in ("high", "low", "close"))
                for sname, lvl in (("ZONE", sign * top_s), ("EXT", m["H"])):
                    if (gup and lvl <= e) or ((not gup) and lvl >= e):
                        continue
                    risk = max(abs(lvl - e) + spread, 0.05 * a)
                    stop = e - side * risk
                    for mg, tp1 in (("PLAIN", None), ("H1R", e + side * risk)):
                        pnl, hrs = p27.hold(side, e, stop, risk, pc, tp1, hh, ll, cc, spread, slip)
                        out.append({"market": mkt, "day": str(day.date()), "kind": kind, "stop": sname, "mgmt": mg, "risk": risk, "rr": abs(e - pc) / risk, "r": pnl / risk,
                                    "min_after_open": (t_in - day).total_seconds() / 60 - 570})
    return pd.DataFrame(out)


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(135)
    for thr in (0.2, 0.7):
        d = run(thr)
        d.to_csv(p1.CACHE + f"/phase135_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range: MSS then FVG / inverse-FVG rejection entry, NQ + ES pooled =====")
        print(f"{'zone':<6}{'stop':<6}{'mgmt':<6}{'n':>5}{'med stop':>9}{'win%':>6}{'avgR':>8}{'95% interval':>18}{'PF':>6}{'totalR':>8}")
        for (kd, st, mg), g in d.groupby(["kind", "stop", "mgmt"], sort=False):
            r = g.r.to_numpy()
            boot = rng.choice(r, size=(2000, len(r)), replace=True).mean(axis=1)
            gl = -r[r < 0].sum()
            print(f"{kd:<6}{st:<6}{mg:<6}{len(r):>5}{g.risk.median():>9.1f}{(r > 0).mean() * 100:>5.0f}%{r.mean():>+8.3f}   [{np.quantile(boot, .025):+.2f}, {np.quantile(boot, .975):+.2f}]{(r[r > 0].sum() / gl if gl else float('nan')):>6.2f}{r.sum():>+8.1f}")
        print("\n-- entry time, minutes after the 09:30 open (10th / 50th / 90th) --")
        print(d.drop_duplicates(["market", "day", "kind"]).groupby("kind").min_after_open.quantile([.1, .5, .9]).unstack().round(0).to_string())
        d["year"] = d.day.str[:4]
        print("\n-- per year avgR (ZONE stop, H1R) --")
        print(d[(d.stop == "ZONE") & (d.mgmt == "H1R")].groupby(["kind", "year"]).r.mean().unstack("year").round(3).to_string())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
