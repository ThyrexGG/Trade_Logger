"""Phase 109 — a manual-trading playbook: what usually happens next around the NY open.

Research only. Instead of "can a bot make money", this asks fixed questions a
discretionary TJR-style trader can use, answers them on 2023-04..2024 (EXPLORE),
then checks them on 2025..2026-10 (CONFIRM), each against a chance baseline.
A finding is USEFUL only if it beats the baseline by >= 5 percentage points in
BOTH periods, in the same direction, with N >= 100 in each. Questions fixed
before any answer (NQ primary, ES cross-check):

 Q1 Judas swing     first 30 min (09:30-10:00) trade through a key level (prev day,
                    overnight, London, Asia high/low) and the 10:00 close is back
                    inside -> P(that side's 30-min extreme still holds at 12:00 / 16:00).
                    Baseline: the same probability on all days.
 Q2 Draw on         first key-level breach after 09:30 that closes back inside within
    liquidity       15 min -> P(price reaches the nearest untaken OPPOSITE key level before
                    taking out the sweep extreme, by 16:00).
                    Baseline: random-walk odds d_extreme / (d_extreme + d_target).
 Q3 Morning dir     P(10:00->12:00 moves the same way as 09:30->10:00). Baseline 50%;
                    also for a strong first 30 minutes (|move| >= 0.3 daily ATR).
 Q4 Pullback IFVG   the user's signal (phase108b): P(+1R before -1R, stop at the
                    10-min pullback extreme), split by with/against the morning move,
                    time bucket, and 2nd attempt (an earlier same-direction signal
                    already stopped out). Baseline 50%.
 Q5 News days       Q1 on days with a big 08:30 spike (08:30-08:35 range >= 0.15 ATR).
 Q6 Gap fill        |09:30 open - previous close| >= 0.1 ATR -> P(price trades back to
                    the previous close by 12:00 / 16:00). Reported (no chance baseline).

    python -m phase109_playbook_stats
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4
import phase106_follow_sweep as p6
import phase108b_pullback_ifvg as p8

EXPLORE_END = "2024-12-31"
KEY = ("PD", "ON", "LDN", "ASIA")
OUT = os.path.join(p1.CACHE, "phase109")


def _t(day, h, m=0):
    return day + pd.Timedelta(hours=h, minutes=m)


def day_rows(symbol: str) -> pd.DataFrame:
    df = p1.load(symbol, "M1")
    df = df[df.index >= pd.Timestamp("2023-04-01")]
    p4.SESSION.clear()
    p4.SESSION.update(p6.INDEX_SESSION)
    ctx = p4._daily_context(df)
    days = [d for d in ctx.index if pd.Timestamp(d).weekday() < 5]
    rows: List[dict] = []
    for k in range(1, len(days)):
        day = pd.Timestamp(days[k])
        c = ctx.loc[days[k]]
        atr = c["atr"]
        rth = df.loc[_t(day, 9, 30): _t(day, 16) - pd.Timedelta(seconds=1)]
        if atr != atr or len(rth) < 300:
            continue
        o, h, l, cl = (rth[x].to_numpy() for x in ("open", "high", "low", "close"))
        idx = rth.index
        i10, i12 = idx.searchsorted(_t(day, 10)), idx.searchsorted(_t(day, 12))
        if i10 < 25 or i12 - i10 < 100:
            continue
        lv = [x for x in p4._levels(df, day, ctx, days[k - 1]) if x["family"] in KEY and x["live_from"] <= _t(day, 9, 30)]
        h30, l30 = h[:i10].max(), l[:i10].min()
        c10 = cl[i10 - 1]
        took_hi = [x for x in lv if x["side"] == "H" and h30 > x["price"]]
        took_lo = [x for x in lv if x["side"] == "L" and l30 < x["price"]]
        judas_hi = bool(took_hi) and c10 < min(x["price"] for x in took_hi)
        judas_lo = bool(took_lo) and c10 > max(x["price"] for x in took_lo)
        news = df.loc[_t(day, 8, 30): _t(day, 8, 35) - pd.Timedelta(seconds=1)]
        news_big = len(news) > 0 and (news["high"].max() - news["low"].min()) / atr >= 0.15
        prev_close = float(c["prev_close"]) if c["prev_close"] == c["prev_close"] else np.nan
        gap = (o[0] - prev_close) / atr if prev_close == prev_close else np.nan
        fill12 = fill16 = None
        if gap == gap and abs(gap) >= 0.1:
            touch = (l <= prev_close) if gap > 0 else (h >= prev_close)
            fill12, fill16 = bool(touch[:i12].any()), bool(touch.any())
        q2 = _q2(lv, idx, h, l, cl, day)
        rows.append({
            "day": str(day.date()), "period": "EXPLORE" if str(day.date()) <= EXPLORE_END else "CONFIRM",
            "hi_holds_12": bool(h[i10:i12].max() <= h30), "lo_holds_12": bool(l[i10:i12].min() >= l30),
            "hi_holds_16": bool(h[i10:].max() <= h30), "lo_holds_16": bool(l[i10:].min() >= l30),
            "judas_hi": judas_hi, "judas_lo": judas_lo, "news_big": bool(news_big),
            "m30": np.sign(c10 - o[0]), "m30_size": abs(c10 - o[0]) / atr, "m12": np.sign(cl[i12 - 1] - c10),
            "gap_atr": gap, "fill12": fill12, "fill16": fill16, **q2,
        })
    return pd.DataFrame(rows)


def _q2(lv, idx, h, l, cl, day) -> dict:
    """First key-level breach after 09:30 that closes back inside within 15 minutes."""
    n = len(idx)
    i_last = idx.searchsorted(_t(day, 11))
    for i in range(min(i_last, n)):
        for side in ("H", "L"):
            hit = [x for x in lv if x["side"] == side and ((side == "H" and h[i] > x["price"]) or (side == "L" and l[i] < x["price"]))]
            if not hit:
                continue
            lvl = min(x["price"] for x in hit) if side == "H" else max(x["price"] for x in hit)
            for j in range(i, min(i + 15, n)):
                if (side == "H" and cl[j] < lvl) or (side == "L" and cl[j] > lvl):
                    ext = h[i:j + 1].max() if side == "H" else l[i:j + 1].min()
                    entry = cl[j]
                    opp = [x["price"] for x in lv if x["side"] != side and ((side == "H" and x["price"] < entry) or (side == "L" and x["price"] > entry))]
                    if not opp:
                        return {"q2_side": side, "q2_result": None, "q2_rw": None}
                    tgt = max(opp) if side == "H" else min(opp)
                    d_ext, d_tgt = abs(ext - entry), abs(entry - tgt)
                    res = None
                    for k in range(j + 1, n):
                        hit_ext = h[k] > ext if side == "H" else l[k] < ext
                        hit_tgt = l[k] <= tgt if side == "H" else h[k] >= tgt
                        if hit_ext:
                            res = False
                            break
                        if hit_tgt:
                            res = True
                            break
                    return {"q2_side": side, "q2_result": res, "q2_rw": d_ext / (d_ext + d_tgt)}
            return {"q2_side": side, "q2_result": None, "q2_rw": None}
    return {"q2_side": None, "q2_result": None, "q2_rw": None}


def ifvg_rows(symbol: str) -> pd.DataFrame:
    """Every pullback-IFVG signal 09:40-11:00 with its +1R-before--1R outcome (pre-cost)."""
    df = p1.load(symbol, "M1")
    df = df[df.index >= pd.Timestamp("2023-04-01")]
    out = []
    for day in sorted({d for d in df.index.normalize() if d.weekday() < 5}):
        m = df.loc[_t(day, 9, 20): _t(day, 12) - pd.Timedelta(seconds=1)]
        if len(m) < 120:
            continue
        idx = m.index
        h, l, cl, o = (m[x].to_numpy() for x in ("high", "low", "close", "open"))
        i930 = idx.searchsorted(_t(day, 9, 30))
        i0, i_last = idx.searchsorted(_t(day, 9, 40)), idx.searchsorted(_t(day, 11))
        stops_known: List[tuple] = []
        for i, side in p8._signals(m, i0, i_last):
            entry = cl[i]
            ext = h[max(0, i - p8.PULLBACK_MIN): i + 1].max() if side < 0 else l[max(0, i - p8.PULLBACK_MIN): i + 1].min()
            risk = abs(entry - ext)
            if risk <= 0:
                continue
            up, dn = entry + risk, entry - risk
            res, stop_bar = None, None
            for k in range(i + 1, len(m)):
                hs, ls = h[k], l[k]
                if side > 0:
                    if ls <= dn:
                        res, stop_bar = False, k
                        break
                    if hs >= up:
                        res = True
                        break
                else:
                    if hs >= up:
                        res, stop_bar = False, k
                        break
                    if ls <= dn:
                        res = True
                        break
            second = any(d == side and kb < i for d, kb in stops_known)
            if stop_bar is not None:
                stops_known.append((side, stop_bar))
            mins = (idx[i] - _t(day, 9, 30)).total_seconds() / 60
            out.append({"day": str(day.date()), "period": "EXPLORE" if str(day.date()) <= EXPLORE_END else "CONFIRM",
                        "with_morning": bool(np.sign(entry - o[i930]) == side), "second": second,
                        "bucket": "09:40-10:00" if mins < 30 else "10:00-10:20" if mins < 50 else "10:20-11:00", "win": res})
    return pd.DataFrame(out)


def _rate(s: pd.Series):
    s = s.dropna()
    return (round(float(s.mean()), 3), int(len(s))) if len(s) else (None, 0)


def questions(d: pd.DataFrame, f: pd.DataFrame) -> List[dict]:
    res = []

    def add(q, label, period_vals, base_vals):
        row = {"q": q, "finding": label}
        ok = []
        for per in ("EXPLORE", "CONFIRM"):
            (v, n), (b, _) = period_vals[per], base_vals[per]
            row[f"{per}"] = f"{v} (n={n}) vs {b}" if v is not None else "-"
            ok.append(v is not None and b is not None and n >= 100 and v - b)
        diffs = [x for x in ok if x not in (False, None)]
        row["useful"] = bool(len(diffs) == 2 and all(abs(x) >= 0.05 for x in diffs) and np.sign(diffs[0]) == np.sign(diffs[1]))
        row["edge_vs_chance_pp"] = [round(100 * x, 1) if x not in (False, None) else None for x in ok]
        res.append(row)

    P = {per: d[d.period == per] for per in ("EXPLORE", "CONFIRM")}
    F = {per: f[f.period == per] for per in ("EXPLORE", "CONFIRM")}
    for hz in ("12", "16"):
        add("Q1", f"Judas up (took a key high, back inside at 10:00): 30-min HIGH holds to {hz}:00",
            {p: _rate(P[p][P[p].judas_hi][f"hi_holds_{hz}"]) for p in P}, {p: _rate(P[p][f"hi_holds_{hz}"]) for p in P})
        add("Q1", f"Judas down (took a key low, back inside at 10:00): 30-min LOW holds to {hz}:00",
            {p: _rate(P[p][P[p].judas_lo][f"lo_holds_{hz}"]) for p in P}, {p: _rate(P[p][f"lo_holds_{hz}"]) for p in P})
        add("Q5", f"Judas up on a big 08:30 news day: 30-min HIGH holds to {hz}:00",
            {p: _rate(P[p][P[p].judas_hi & P[p].news_big][f"hi_holds_{hz}"]) for p in P}, {p: _rate(P[p][f"hi_holds_{hz}"]) for p in P})
        add("Q5", f"Judas down on a big 08:30 news day: 30-min LOW holds to {hz}:00",
            {p: _rate(P[p][P[p].judas_lo & P[p].news_big][f"lo_holds_{hz}"]) for p in P}, {p: _rate(P[p][f"lo_holds_{hz}"]) for p in P})
    q2 = {p: P[p][P[p].q2_result.notna()] for p in P}
    add("Q2", "After the first key-level sweep + reclaim: opposite key level reached before the sweep extreme breaks",
        {p: _rate(q2[p].q2_result.astype(float)) for p in P}, {p: (round(float(q2[p].q2_rw.mean()), 3), len(q2[p])) for p in P})
    add("Q3", "10:00->12:00 continues the 09:30->10:00 direction",
        {p: _rate((P[p].m12 == P[p].m30).astype(float)[P[p].m30 != 0]) for p in P}, {p: (0.5, 0) for p in P})
    strong = {p: P[p][(P[p].m30_size >= 0.3) & (P[p].m30 != 0)] for p in P}
    add("Q3", "...when the first 30 min moved >= 0.3 daily ATR",
        {p: _rate((strong[p].m12 == strong[p].m30).astype(float)) for p in P}, {p: (0.5, 0) for p in P})
    for label, sel in (("all signals", lambda x: x), ("WITH the morning move", lambda x: x[x.with_morning]),
                       ("AGAINST the morning move", lambda x: x[~x.with_morning]),
                       ("2nd attempt (earlier same-direction signal stopped out)", lambda x: x[x.second]),
                       ("09:40-10:00", lambda x: x[x.bucket == "09:40-10:00"]), ("10:00-10:20", lambda x: x[x.bucket == "10:00-10:20"]),
                       ("10:20-11:00", lambda x: x[x.bucket == "10:20-11:00"]),
                       ("WITH morning move, 2nd attempt", lambda x: x[x.with_morning & x.second])):
        add("Q4", f"Pullback IFVG hits +1R before -1R: {label}",
            {p: _rate(sel(F[p]).win.astype(float)) for p in F}, {p: (0.5, 0) for p in F})
    for hz in ("12", "16"):
        for lab, cond in (("small gap 0.1-0.3 ATR", lambda x: x.gap_atr.abs() < 0.3), ("big gap >= 0.3 ATR", lambda x: x.gap_atr.abs() >= 0.3)):
            g = {p: P[p][P[p][f"fill{hz}"].notna()] for p in P}
            res.append({"q": "Q6", "finding": f"Gap fill by {hz}:00, {lab}",
                        **{p: f"{_rate(g[p][cond(g[p])][f'fill{hz}'].astype(float))}" for p in P}, "useful": None, "edge_vs_chance_pp": None})
    return res


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    out: Dict = {"phase": 109, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "markets": {}}
    for s in ("NQ", "ES"):
        d, f = day_rows(s), ifvg_rows(s)
        d.to_csv(os.path.join(OUT, f"phase109_days_{s}.csv"), index=False)
        f.to_csv(os.path.join(OUT, f"phase109_ifvg_{s}.csv"), index=False)
        out["markets"][s] = questions(d, f)
    with open(os.path.join(OUT, "phase109_result.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    return out


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    for s, rows in r["markets"].items():
        print(f"\n===== {s} =====")
        for row in rows:
            flag = "USEFUL" if row["useful"] else ""
            print(f"{row['q']} {row['finding'][:95]:<95} | EXPLORE {row['EXPLORE']:<26} | CONFIRM {row['CONFIRM']:<26} | pp {row['edge_vs_chance_pp']} {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
