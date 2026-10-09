"""Phase 117b — raw drift after the open on gap days (no stop/target/cost), robustness of Phase 117.

For each day with an unfilled gap at the entry time, drift = (price at EXIT - price at ENTRY) *
(direction toward the previous close) / prior-14d mean RTH range. Reported by gap threshold,
entry time, exit time, year; with t-stat. Exploratory (flagged): it checks whether the 2025-26
big-gap result in Phase 117 is a plateau across reasonable settings or a single lucky cell.

    python -m phase117b_gap_drift
"""
from __future__ import annotations
import datetime as dt, json, os, sys
import numpy as np, pandas as pd
import phase101_ny_open_sweep as p1

OUT = os.path.join(p1.CACHE, "phase117")
THRESH = (0.5, 0.7, 1.0)
ENTRIES = {"0945": (9, 45), "1000": (10, 0)}
EXITS = {"11:00": (11, 0), "12:00": (12, 0), "13:30": (13, 30), "15:55": (15, 55)}
MARKETS = ("NQ", "ES")
TAG = ""  # file-name suffix, so a replication on other markets never overwrites the NQ/ES result


def run():
    rows = []
    for mkt in MARKETS:
        m1 = p1.load(mkt, "M1"); m1 = m1[m1.index >= pd.Timestamp("2023-03-01")]
        rth = m1[(m1.index.time >= dt.time(9, 30)) & (m1.index.time < dt.time(16, 0))]
        gb = rth.groupby(rth.index.normalize())
        atr = (gb["high"].max() - gb["low"].min()).shift(1).rolling(14).mean()
        pcl = gb["close"].last().shift(1)
        for day, g in gb:
            if day.weekday() > 4 or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0].time() != dt.time(9, 30):
                continue
            pc, a = float(pcl[day]), float(atr[day]); o = float(g["open"].iloc[0]); gap = o - pc
            for en, (hh, mm) in ENTRIES.items():
                t0 = day + pd.Timedelta(hours=hh, minutes=mm); pre = g[g.index < t0]
                if len(pre) < 10: continue
                gup = gap > 0
                touched = (pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)
                e = float(pre["close"].iloc[-1])
                if touched or (gup and e <= pc) or ((not gup) and e >= pc): continue
                side = -1 if gup else 1
                for xn, (xh, xm) in EXITS.items():
                    tx = day + pd.Timedelta(hours=xh, minutes=xm); seg = g[g.index < tx]
                    if len(seg) < 20 or seg.index[-1] < t0: continue
                    rows.append({"market": mkt, "day": str(day.date()), "gap_atr": abs(gap) / a, "entry": en, "exit": xn,
                                 "drift": side * (float(seg["close"].iloc[-1]) - e) / a})
    d = pd.DataFrame(rows); d["yr"] = d.day.str[:4]
    d.to_csv(os.path.join(OUT, f"phase117b_drift{TAG}.csv"), index=False)
    out = []
    for th in THRESH:
        for (mkt, en, xn), g in d[d.gap_atr >= th].groupby(["market", "entry", "exit"]):
            for per, sel in (("2023-24", g.yr <= "2024"), ("2025-26", g.yr >= "2025")):
                x = g[sel].drift.to_numpy()
                if len(x) < 15: continue
                out.append({"thresh": th, "market": mkt, "entry": en, "exit": xn, "period": per, "n": len(x),
                            "mean_drift_atr": round(float(x.mean()), 4), "t": round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2),
                            "toward_fill_share": round(float((x > 0).mean()), 3)})
    json.dump(out, open(os.path.join(OUT, f"phase117b_result{TAG}.json"), "w"), indent=1)
    return out


def main(argv=None):
    out = run()
    print(f"{'gap>=':<6}{'mkt':<4}{'entry':<6}{'exit':<6}{'period':<8}{'n':>4}{'drift/ATR':>10}{'t':>6}{'toward%':>8}")
    for r in out:
        print(f"{r['thresh']:<6}{r['market']:<4}{r['entry']:<6}{r['exit']:<6}{r['period']:<8}{r['n']:>4}{r['mean_drift_atr']:>+10.3f}{r['t']:>6.1f}{r['toward_fill_share']*100:>7.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
