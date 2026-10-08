"""Phase 115 — TJR's own step-by-step strategy (his 2026 "updated strategy" video).

Research only. Source: transcript of TJR's updated strategy video (supplied by the
user). His stated rules, coded as literally as possible; fixed before any result:

  1 LIQUIDITY     draws on liquidity = Asia (18:00-03:00) and London (03:00-08:30)
                  session highs/lows and 1-hour / 4-hour highs/lows (2-candle
                  highs/lows, phase113), untaken at 09:30. Manipulation = New York
                  trades through one. "As long as one of the indexes is doing it":
                  variant EITHER lets the sibling index's sweep count.
  2 REVERSAL      within 60 min of the sweep, a 5-minute BREAK OF STRUCTURE (a close
                  beyond the most recent 5m swing low/high, 2-candle swings) or a
                  5-minute INVERSE FVG (a 5m gap in the old direction closed through).
  3 RETRACE       then a 1-minute break of structure AGAINST the new direction (the
                  5-minute retrace).
  4 ENTRY         then a 1-minute break of structure (or 1-minute inverse FVG) BACK in
                  the new direction -> enter at that close. Within 60 min of step 2.
  STOP            SECOND = beyond the retrace extreme ("the second high/low"), or
                  SWEEP = beyond the sweep extreme. A new extreme beyond the sweep before
                  entry cancels the setup.
  EXITS           LIQ1 = all out at the first untaken draw on liquidity >= 1R (cap 4R,
                  none -> 2R); PARTIALS = half at that level, stop to breakeven, rest at
                  the next level beyond it (cap 6R, none -> 3R); 2R. Flat 15:55.
  WINDOW          TJR = entries 09:30-11:30; USER = 09:45-10:30.
  One trade per day per market; costs = bar spread + slippage.

Reported: the TJR-faithful configuration (EITHER, SECOND, PARTIALS, TJR window) per
year and for Jan-Jun 2026 (the months TJR shows), win rate and average win/loss in R
(TJR claims ~64% and ~1.33); and a walk-forward choice over all 48 configurations
(chosen on 2023-04..2024, judged on 2025..2026-10).

    python -m phase115_tjr_strategy
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from itertools import product
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4
import phase113_tjr_liquidity as p13

EXPLORE_END = "2024-12-31"
OUT = os.path.join(p1.CACHE, "phase115")
FAMS = {"ASIA", "LDN", "H1", "H4"}
WINDOWS = {"TJR": ("09:30", "11:30"), "USER": ("09:45", "10:30")}


def _t(day, h, m=0):
    return day + pd.Timedelta(hours=h, minutes=m)


class Swings:
    """2-candle swing highs/lows (TJR's definition), each known once its 2nd candle has closed."""

    def __init__(self, o, h, l, c):
        n = len(c)
        self.hi = np.full(n, np.nan)  # latest swing high known at the close of bar k
        self.lo = np.full(n, np.nan)
        hi = lo = np.nan
        for k in range(1, n):
            if c[k - 1] > o[k - 1] and c[k] < o[k]:
                hi = max(h[k - 1], h[k])
            if c[k - 1] < o[k - 1] and c[k] > o[k]:
                lo = min(l[k - 1], l[k])
            self.hi[k], self.lo[k] = hi, lo


def _ifvg(o, h, l, c, k, side, lookback):
    """At bar k, did a close invert a gap of the OLD direction formed in the last `lookback` bars?
    side = new trade direction (-1: a bullish gap closed below its bottom; +1: a bearish gap closed above its top)."""
    for j in range(max(2, k - lookback), k):
        if side < 0 and h[j - 2] < l[j] and c[k] < h[j - 2] and all(c[q] >= h[j - 2] for q in range(j + 1, k)):
            return True
        if side > 0 and l[j - 2] > h[j] and c[k] > l[j - 2] and all(c[q] <= l[j - 2] for q in range(j + 1, k)):
            return True
    return False


def day_setups(symbol: str, df: pd.DataFrame, sib: pd.DataFrame, day: pd.Timestamp, prev: pd.Timestamp) -> List[dict]:
    m = df.loc[_t(day, 9, 30): _t(day, 16) - pd.Timedelta(seconds=1)]
    ms = sib.loc[_t(day, 9, 30): _t(day, 16) - pd.Timedelta(seconds=1)]
    if len(m) < 300:
        return []
    lv = [x for x in p13.levels(df, day, prev) if x["fam"] in FAMS]
    lvs = [x for x in p13.levels(sib, day, prev) if x["fam"] in FAMS] if len(ms) > 300 else []
    o1, h1, l1, c1 = (m[x].to_numpy() for x in ("open", "high", "low", "close"))
    sp1 = m["spread"].to_numpy()
    idx1 = m.index
    sw1 = Swings(o1, h1, l1, c1)
    b5 = m.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    o5, h5, l5, c5 = (b5[x].to_numpy() for x in ("open", "high", "low", "close"))
    end5 = b5.index + pd.Timedelta(minutes=5)
    sw5 = Swings(o5, h5, l5, c5)
    buf = p4.BUFFER[symbol]
    i_last_sweep = idx1.searchsorted(_t(day, 11, 30))
    out: List[dict] = []
    for either in (False, True):
        taken, taken_s = set(), set()
        sweeps = []  # (minute index, side_char, extreme so far)
        for i in range(min(i_last_sweep, len(m))):
            for sc in ("H", "L"):
                own = [n for n, x in enumerate(lv) if n not in taken and x["side"] == sc and ((sc == "H" and h1[i] > x["price"]) or (sc == "L" and l1[i] < x["price"]))]
                sib_hit = []
                if either and len(ms):
                    ts = idx1[i]
                    if ts in ms.index:
                        hs, ls_ = ms.at[ts, "high"], ms.at[ts, "low"]
                        sib_hit = [n for n, x in enumerate(lvs) if n not in taken_s and x["side"] == sc and ((sc == "H" and hs > x["price"]) or (sc == "L" and ls_ < x["price"]))]
                taken.update(own)
                taken_s.update(sib_hit)
                if own or sib_hit:
                    sweeps.append((i, sc))
        for i, sc in sweeps:
            st = _sequence(symbol, sc, i, idx1, o1, h1, l1, c1, sp1, sw1, b5, o5, h5, l5, c5, end5, sw5, day, buf, lv)
            if st:
                for row in st:
                    row["either"] = either
                out += st
                break  # first complete setup of the day for this sweep rule
    return out


def _sequence(symbol, sc, i, idx1, o1, h1, l1, c1, sp1, sw1, b5, o5, h5, l5, c5, end5, sw5, day, buf, lv) -> List[dict]:
    side = -1 if sc == "H" else 1  # a high swept -> look for shorts
    t_sweep = idx1[i]
    ext = h1[i] if side < 0 else l1[i]
    # step 2: 5-minute BOS or IFVG within 60 minutes
    k0 = b5.index.searchsorted(t_sweep, side="right") - 1
    t2 = None
    for k in range(max(k0, 1), len(b5)):
        if end5[k] > t_sweep + pd.Timedelta(minutes=60):
            return []
        ext = max(ext, h5[k]) if side < 0 else min(ext, l5[k])
        ref = sw5.lo[k - 1] if side < 0 else sw5.hi[k - 1]
        bos = ref == ref and ((side < 0 and c5[k] < ref) or (side > 0 and c5[k] > ref))
        if bos or _ifvg(o5, h5, l5, c5, k, side, 12):
            t2 = end5[k]
            break
    if t2 is None:
        return []
    # steps 3-4 on 1-minute bars
    j0 = idx1.searchsorted(t2)
    retr = None
    for j in range(max(j0, 1), len(idx1)):
        if idx1[j] > t2 + pd.Timedelta(minutes=60):
            return []
        if (side < 0 and h1[j] > ext) or (side > 0 and l1[j] < ext):
            return []  # new extreme beyond the sweep: idea invalid
        if retr is None:
            ref = sw1.hi[j - 1] if side < 0 else sw1.lo[j - 1]
            if ref == ref and ((side < 0 and c1[j] > ref) or (side > 0 and c1[j] < ref)):
                retr = j  # 1-minute break of structure AGAINST: the 5-minute retrace
            continue
        ref = sw1.lo[j - 1] if side < 0 else sw1.hi[j - 1]
        bos = ref == ref and ((side < 0 and c1[j] < ref) or (side > 0 and c1[j] > ref))
        if bos or _ifvg(o1, h1, l1, c1, j, side, max(3, j - retr + 2)):
            entry = float(c1[j])
            second = h1[retr: j + 1].max() if side < 0 else l1[retr: j + 1].min()
            t_fill = idx1[j] + pd.Timedelta(minutes=1)  # the entry bar's close
            seen = (h1[: j + 1].max(), l1[: j + 1].min())
            others = sorted({x["price"] for x in lv if x["side"] != sc and
                             ((side < 0 and x["price"] < entry and seen[1] > x["price"]) or (side > 0 and x["price"] > entry and seen[0] < x["price"]))},
                            reverse=side < 0)
            rows = []
            for stop_kind, base in (("SECOND", second), ("SWEEP", ext)):
                stop = base + buf if side < 0 else base - buf
                risk = abs(entry - stop)
                if risk <= 0 or risk < 2 * sp1[j] or (side < 0 and stop <= entry) or (side > 0 and stop >= entry):
                    continue
                lv1 = [p for p in others if abs(p - entry) >= risk]
                tp1 = lv1[0] if lv1 and abs(lv1[0] - entry) <= 4 * risk else entry + side * 2 * risk
                beyond = [p for p in others if abs(p - entry) > abs(tp1 - entry)]
                tp2 = beyond[0] if beyond and abs(beyond[0] - entry) <= 6 * risk else entry + side * max(3 * risk, abs(tp1 - entry) + risk)
                rows.append({"symbol": symbol, "day": str(day.date()), "time": str(t_fill), "side": side, "stop_kind": stop_kind,
                             "entry": entry, "stop": stop, "risk": risk, "tp1": tp1, "tp2": tp2, "spread": float(sp1[j]),
                             "fill_hhmm": t_fill.strftime("%H:%M")})
            return rows
    return []


def _exit(m1: pd.DataFrame, t: pd.Series, mode: str) -> tuple:
    seg = m1.loc[pd.Timestamp(t["time"]): pd.Timestamp(t["day"]) + pd.Timedelta(hours=15, minutes=55)]
    h, l, c = seg["high"].to_numpy(), seg["low"].to_numpy(), seg["close"].to_numpy()
    side, e, risk = int(t["side"]), float(t["entry"]), float(t["risk"])
    stop = float(t["stop"])
    tp1 = float(t["tp1"]) if mode in ("LIQ1", "PARTIALS") else e + side * 2 * risk
    tp2 = float(t["tp2"])
    half_done = False
    for k in range(len(seg)):
        if (side > 0 and l[k] <= stop) or (side < 0 and h[k] >= stop):
            r_stop = side * (stop - e) / risk
            return (0.5 * abs(tp1 - e) / risk + 0.5 * r_stop, "tp1+be" if half_done else "stop", 0.5 if half_done else 1.0) if half_done else (r_stop, "stop", 1.0)
        if not half_done and ((side > 0 and h[k] >= tp1) or (side < 0 and l[k] <= tp1)):
            if mode != "PARTIALS":
                return abs(tp1 - e) / risk, "target", 0.0
            half_done, stop = True, e
        if half_done and ((side > 0 and h[k] >= tp2) or (side < 0 and l[k] <= tp2)):
            return 0.5 * abs(tp1 - e) / risk + 0.5 * abs(tp2 - e) / risk, "tp1+tp2", 0.0
    last = side * (c[-1] - e) / risk if len(c) else 0.0
    return ((0.5 * abs(tp1 - e) / risk + 0.5 * last) if half_done else last), "time", (0.5 if half_done else 1.0)


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(115)
    data = {s: p1.load(s, "M1") for s in ("NQ", "ES")}
    data = {s: d[d.index >= pd.Timestamp("2023-04-01")] for s, d in data.items()}
    res: Dict = {"phase": 115, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "markets": {}}
    for s in ("NQ", "ES"):
        df, sib = data[s], data["ES" if s == "NQ" else "NQ"]
        days = sorted({d for d in df.index.normalize() if d.weekday() < 5})
        rows = []
        for i in range(3, len(days)):
            rows += day_setups(s, df, sib, days[i], days[i - 1])
        st = pd.DataFrame(rows)
        recs = []
        for _, t in st.iterrows():
            for mode in ("LIQ1", "PARTIALS", "2R"):
                g, outc, mkt = _exit(df, t, mode)
                slip = p1.SLIPPAGE[s]
                r = g - (t["spread"] + slip + slip * mkt) / t["risk"]
                recs.append({**t.to_dict(), "exit_mode": mode, "outcome": outc, "r": round(r, 4), "r_gross": round(g, 4)})
        allr = pd.DataFrame(recs)
        allr.to_csv(os.path.join(OUT, f"phase115_{s}.csv"), index=False)
        cells = []
        for either, sk, mode, (wn, (a, b)) in product((True, False), ("SECOND", "SWEEP"), ("PARTIALS", "LIQ1", "2R"), WINDOWS.items()):
            x = allr[(allr.either == either) & (allr.stop_kind == sk) & (allr.exit_mode == mode) & (allr.fill_hhmm >= a) & (allr.fill_hhmm <= b)]
            x = x.sort_values("time").groupby("day").head(1)
            if not len(x):
                continue
            yr = x["day"].str[:4]
            wins, losses = x[x.r > 0].r, x[x.r <= 0].r
            cells.append({
                "config": f"{'EITHER' if either else 'OWN'} sweep | stop {sk} | {mode} | window {wn}", "n": int(len(x)),
                "explore": float(x[x.day <= EXPLORE_END].r.mean()) if (x.day <= EXPLORE_END).any() else -9,
                "n_explore": int((x.day <= EXPLORE_END).sum()),
                "confirm": float(x[x.day > EXPLORE_END].r.mean()) if (x.day > EXPLORE_END).any() else None,
                "by_year": {y: round(float(g.r.mean()), 3) for y, g in x.groupby(yr)},
                "n_by_year": {y: int(len(g)) for y, g in x.groupby(yr)},
                "jan_jun_2026": round(float(x[(x.day >= "2026-01-01") & (x.day < "2026-07-01")].r.mean()), 3),
                "n_jan_jun_2026": int(((x.day >= "2026-01-01") & (x.day < "2026-07-01")).sum()),
                "win_rate": round(float((x.r > 0).mean()), 3), "avg_win_R": round(float(wins.mean()), 2) if len(wins) else None,
                "avg_loss_R": round(float(losses.mean()), 2) if len(losses) else None, "mean_r": round(float(x.r.mean()), 3),
                "gross_mean_r": round(float(x.r_gross.mean()), 3), "_cf": x[x.day > EXPLORE_END].r.to_numpy(),
            })
        faithful = next(c for c in cells if c["config"] == "EITHER sweep | stop SECOND | PARTIALS | window TJR")
        ok = sorted([c for c in cells if c["n_explore"] >= 80], key=lambda c: -c["explore"])
        best = ok[0] if ok else None
        bstats = p1.summarize(best["_cf"], rng) if best else {}
        res["markets"][s] = {
            "tjr_faithful": {k: v for k, v in faithful.items() if k != "_cf"},
            "chosen_on_2023_24": best["config"] if best else None, "chosen_explore": round(best["explore"], 3) if best else None,
            "chosen_2025_26": bstats, "chosen_by_year": best["by_year"] if best else None,
            "passes": bool(best and bstats.get("ci95", [-1])[0] > 0 and best["by_year"].get("2025", -1) > 0 and best["by_year"].get("2026", -1) > 0),
            "all_configs": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in c.items() if k != "_cf"} for c in cells],
        }
    with open(os.path.join(OUT, "phase115_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    for s, v in r["markets"].items():
        f = v["tjr_faithful"]
        print(f"\n===== {s} =====\nTJR-faithful: n={f['n']} win {f['win_rate']:.0%} avg win {f['avg_win_R']}R avg loss {f['avg_loss_R']}R mean {f['mean_r']}R (gross {f['gross_mean_r']}) "
              f"by year {f['by_year']} | Jan-Jun 2026 {f['jan_jun_2026']}R (n={f['n_jan_jun_2026']})")
        print(f"walk-forward: chosen {v['chosen_on_2023_24']} (2023-24 {v['chosen_explore']}) -> 2025-26 {v['chosen_2025_26'].get('mean_r')} "
              f"ci {v['chosen_2025_26'].get('ci95')} by year {v['chosen_by_year']} pass={v['passes']}")
        for c in sorted(v["all_configs"], key=lambda c: -(c["confirm"] or -9))[:8]:
            print(f"   {c['config']:<55} n={c['n']:>3} win {c['win_rate']:.0%} mean {c['mean_r']:+.3f} yrs {c['by_year']} H1-2026 {c['jan_jun_2026']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
