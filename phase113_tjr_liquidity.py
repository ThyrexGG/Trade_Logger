"""Phase 113 — TJR's "Liquidity Explained" model, walk-forward optimised, + his London claim.

Research only. Source: TJR, "Liquidity Explained" (transcript supplied by the user).
Definitions as taught:
  sessions (New York time)  Asia 18:00 (prev day) -> 03:00; London 03:00 -> 08:30;
                            New York trades from 09:30.
  a high / low              a 2-candle pattern: an up candle then a down candle (high =
                            the higher wick of the two); a down then an up candle (low).
  significant liquidity     session highs/lows (Asia, London), previous day high/low,
                            1-hour and 4-hour highs/lows (2-candle definition), untaken.
  confirmation              after the sweep, a new trend on the 5-minute chart: the low,
                            a high, a higher low, then a close above that high -> enter.
  targets                   draws on liquidity: the nearest untaken significant level on
                            the other side.

PART 1 — his claim, measured: "New York sweeps the London high or low, then makes the
  day's move." (a) how often NY (09:30-10:30) trades through a London extreme;
  (b) after NY takes the London LOW first (by 11:00) and closes back above it within
  15 min: P(price reaches the London HIGH before breaking the sweep low, by 16:00) vs
  random-walk odds, and P(the 16:00 close is above the 09:30 open) vs all days. Mirror
  for the London HIGH.

PART 2 — the model, as a menu (fixed before any result) and a walk-forward choice:
  levels   ALL (sessions + previous day + 1h/4h) | SESSION (Asia, London, prev day) |
           LONDON (London high/low only) | HTF (1h/4h only)
  stop     SWEEP (below the sweep low) | HL (below the higher low)
  target   LIQ (nearest untaken level on the other side, >= 1R, cap 6R, none -> 3R) | 2R
  manage   FIXED | HALF | CUT | RUN | CUT_RUN | HALF_CUT  (phase112.manage)
  Sweeps 09:30-11:00, entry within 90 minutes and before 12:00, flat 15:55, first
  trade per day per market. The configuration with the best 2023-04..2024 mean R
  (N >= 80) is chosen; only its 2025..2026-10 result counts.
  PASS: chosen config's 2025-26 mean R > 0 with 95% CI above 0 and both years positive.

    python -m phase113_tjr_liquidity
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from itertools import product
from typing import Dict, List

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4
import phase112_manage as p12

EXPLORE_END = "2024-12-31"
OUT = os.path.join(p1.CACHE, "phase113")
LEVEL_SETS = {"ALL": {"ASIA", "LDN", "PD", "H1", "H4"}, "SESSION": {"ASIA", "LDN", "PD"}, "LONDON": {"LDN"}, "HTF": {"H1", "H4"}}


def _t(day, h, m=0):
    return day + pd.Timedelta(hours=h, minutes=m)


def _two_candle(b: pd.DataFrame, kind: str, tag: str) -> List[dict]:
    o, c, h, l = (b[x].to_numpy() for x in ("open", "close", "high", "low"))
    out = []
    for k in range(len(b) - 1):
        if c[k] > o[k] and c[k + 1] < o[k + 1]:
            out.append({"price": max(h[k], h[k + 1]), "side": "H", "fam": tag, "formed": b.index[k + 1] + (b.index[1] - b.index[0])})
        if c[k] < o[k] and c[k + 1] > o[k + 1]:
            out.append({"price": min(l[k], l[k + 1]), "side": "L", "fam": tag, "formed": b.index[k + 1] + (b.index[1] - b.index[0])})
    return out


def levels(df: pd.DataFrame, day: pd.Timestamp, prev_day: pd.Timestamp) -> List[dict]:
    t930 = _t(day, 9, 30)
    lv: List[dict] = []
    asia = df.loc[_t(day, -6): _t(day, 3) - pd.Timedelta(seconds=1)]
    ldn = df.loc[_t(day, 3): _t(day, 8, 30) - pd.Timedelta(seconds=1)]
    pdr = df.loc[_t(prev_day, 9, 30): _t(prev_day, 16) - pd.Timedelta(seconds=1)]
    for seg, fam, formed in ((asia, "ASIA", _t(day, 3)), (ldn, "LDN", _t(day, 8, 30)), (pdr, "PD", _t(prev_day, 16))):
        if len(seg):
            lv += [{"price": seg["high"].max(), "side": "H", "fam": fam, "formed": formed},
                   {"price": seg["low"].min(), "side": "L", "fam": fam, "formed": formed}]
    hist = df.loc[_t(day, -48): t930 - pd.Timedelta(seconds=1)]
    for rule, tag in (("1h", "H1"), ("4h", "H4")):
        b = hist.resample(rule, label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        lv += _two_candle(b, rule, tag)
    keep = []
    pre = df.loc[: t930 - pd.Timedelta(seconds=1)]
    for x in lv:
        seg = pre.loc[x["formed"]:]
        if len(seg) and ((x["side"] == "H" and seg["high"].max() > x["price"]) or (x["side"] == "L" and seg["low"].min() < x["price"])):
            continue  # already taken before New York opens
        keep.append(x)
    return keep


def claim_rows(df: pd.DataFrame, symbol: str) -> List[dict]:
    days = sorted({d for d in df.index.normalize() if d.weekday() < 5})
    rows = []
    for i in range(1, len(days)):
        day, prev = days[i], days[i - 1]
        rth = df.loc[_t(day, 9, 30): _t(day, 16) - pd.Timedelta(seconds=1)]
        ldn = df.loc[_t(day, 3): _t(day, 8, 30) - pd.Timedelta(seconds=1)]
        if len(rth) < 300 or len(ldn) < 200:
            continue
        lh, ll = ldn["high"].max(), ldn["low"].min()
        h, l, c = rth["high"].to_numpy(), rth["low"].to_numpy(), rth["close"].to_numpy()
        i1030, i11 = rth.index.searchsorted(_t(day, 10, 30)), rth.index.searchsorted(_t(day, 11))
        rec = {"day": str(day.date()), "took_ldn_h_by_1030": bool(h[:i1030].max() > lh), "took_ldn_l_by_1030": bool(l[:i1030].min() < ll),
               "up_day": bool(c[-1] > rth["open"].iloc[0]), "first": None, "reach_other": None, "rw": None}
        # first London extreme taken by 11:00, and a close back inside within 15 min
        for k in range(i11):
            side = "L" if l[k] < ll else "H" if h[k] > lh else None
            if side is None:
                continue
            lvl = ll if side == "L" else lh
            for j in range(k, min(k + 15, len(rth))):
                if (side == "L" and c[j] > lvl) or (side == "H" and c[j] < lvl):
                    ext = l[k:j + 1].min() if side == "L" else h[k:j + 1].max()
                    tgt = lh if side == "L" else ll
                    d_ext, d_tgt = abs(c[j] - ext), abs(tgt - c[j])
                    res = None
                    for q in range(j + 1, len(rth)):
                        if (side == "L" and l[q] < ext) or (side == "H" and h[q] > ext):
                            res = False
                            break
                        if (side == "L" and h[q] >= tgt) or (side == "H" and l[q] <= tgt):
                            res = True
                            break
                    rec.update({"first": side, "reach_other": res, "rw": d_ext / (d_ext + d_tgt) if d_ext + d_tgt > 0 else None})
                    break
            break
        rows.append(rec)
    return rows


def setups(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    days = sorted({d for d in df.index.normalize() if d.weekday() < 5})
    buf = p4.BUFFER[symbol]
    out = []
    for i in range(3, len(days)):
        day, prev = days[i], days[i - 1]
        m = df.loc[_t(day, 9, 30): _t(day, 16) - pd.Timedelta(seconds=1)]
        if len(m) < 300:
            continue
        lv_all = levels(df, day, prev)
        b5 = m.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        o5, h5, l5, c5 = (b5[x].to_numpy() for x in ("open", "high", "low", "close"))
        end5 = b5.index + pd.Timedelta(minutes=5)
        for set_name, fams in LEVEL_SETS.items():
            live = [x for x in lv_all if x["fam"] in fams]
            hm, lm, im = m["high"].to_numpy(), m["low"].to_numpy(), m.index
            i11 = im.searchsorted(_t(day, 11))
            taken = set()
            found = False
            for k in range(i11):
                for side_char in ("L", "H"):
                    hit = [n for n, x in enumerate(live) if n not in taken and x["side"] == side_char and
                           ((side_char == "L" and lm[k] < x["price"]) or (side_char == "H" and hm[k] > x["price"]))]
                    if not hit:
                        continue
                    taken.update(hit)
                    st = _confirm(side_char, im[k], b5, o5, h5, l5, c5, end5, day, buf)
                    if st is None:
                        continue
                    side, t_entry, entry, stop_sweep, stop_hl = st
                    # draw on liquidity: nearest untaken level on the other side (any family), >= 1R from the entry
                    others = [x["price"] for n, x in enumerate(lv_all) if x["side"] != side_char and
                              not ((x["side"] == "H" and m.loc[:t_entry, "high"].max() > x["price"]) or (x["side"] == "L" and m.loc[:t_entry, "low"].min() < x["price"]))]
                    for stop_kind, stop in (("SWEEP", stop_sweep), ("HL", stop_hl)):
                        risk = abs(entry - stop)
                        if risk <= 0 or (side > 0 and stop >= entry) or (side < 0 and stop <= entry):
                            continue
                        cand = [p for p in others if (side > 0 and entry + risk <= p <= entry + 6 * risk) or (side < 0 and entry - 6 * risk <= p <= entry - risk)]
                        liq = (min(cand) if side > 0 else max(cand)) if cand else entry + side * 3 * risk
                        for tk, tpx in (("LIQ", liq), ("2R", entry + side * 2 * risk)):
                            out.append({"day": str(day.date()), "set": set_name, "stop_kind": stop_kind, "target_kind": tk,
                                        "time": str(t_entry), "side": side, "entry": entry, "stop": stop, "target_px": tpx})
                    found = True
                    break
                if found:
                    break
    return pd.DataFrame(out)


def _confirm(side_char, t_sweep, b5, o5, h5, l5, c5, end5, day, buf):
    """5-minute new trend after a LOW sweep: low L0, a high H1 (up then down candle), a higher low L1 (down then up
    candle, above L0), then a close above H1 -> long. Mirror for a HIGH sweep. Within 90 min, entry before 12:00."""
    long_ = side_char == "L"
    k0 = b5.index.searchsorted(t_sweep, side="right") - 1
    if k0 < 0:
        return None
    ext = l5[k0] if long_ else h5[k0]
    h1 = l1 = None
    deadline = min(t_sweep + pd.Timedelta(minutes=90), _t(day, 12))
    for k in range(k0 + 1, len(b5)):
        if end5[k] > deadline:
            return None
        if h1 is None:
            ext = min(ext, l5[k]) if long_ else max(ext, h5[k])
            # a high (long case): up candle at k-1, down candle at k
            if (long_ and c5[k - 1] > o5[k - 1] and c5[k] < o5[k]) or (not long_ and c5[k - 1] < o5[k - 1] and c5[k] > o5[k]):
                h1 = max(h5[k - 1], h5[k]) if long_ else min(l5[k - 1], l5[k])
            continue
        if (long_ and l5[k] < ext) or (not long_ and h5[k] > ext):
            return None  # the sweep extreme broke: no new trend
        if l1 is None:
            if (long_ and c5[k - 1] < o5[k - 1] and c5[k] > o5[k]) or (not long_ and c5[k - 1] > o5[k - 1] and c5[k] < o5[k]):
                cand = min(l5[k - 1], l5[k]) if long_ else max(h5[k - 1], h5[k])
                if (long_ and cand > ext) or (not long_ and cand < ext):
                    l1 = cand
            if l1 is None:
                continue
        if (long_ and c5[k] > h1) or (not long_ and c5[k] < h1):
            side = 1 if long_ else -1
            return side, end5[k], float(c5[k]), (ext - buf if long_ else ext + buf), (l1 - buf if long_ else l1 + buf)
    return None


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(113)
    res: Dict = {"phase": 113, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "claim": {}, "model": {}}
    for s in ("NQ", "ES"):
        df = p1.load(s, "M1")
        df = df[df.index >= pd.Timestamp("2023-04-01")]
        cl = pd.DataFrame(claim_rows(df, s))
        cl.to_csv(os.path.join(OUT, f"phase113_claim_{s}.csv"), index=False)
        claim = {}
        for per, x in (("EXPLORE", cl[cl.day <= EXPLORE_END]), ("CONFIRM", cl[cl.day > EXPLORE_END])):
            fl, fh = x[(x["first"] == "L") & x.reach_other.notna()], x[(x["first"] == "H") & x.reach_other.notna()]
            claim[per] = {
                "days": int(len(x)), "ny_takes_a_london_extreme_by_1030": round(float((x.took_ldn_h_by_1030 | x.took_ldn_l_by_1030).mean()), 3),
                "london_low_first": {"n": int(len(fl)), "reaches_london_high_first": round(float(fl.reach_other.astype(float).mean()), 3) if len(fl) else None,
                                     "chance": round(float(fl.rw.mean()), 3) if len(fl) else None,
                                     "up_day": round(float(x[x["first"] == "L"].up_day.mean()), 3) if (x["first"] == "L").any() else None},
                "london_high_first": {"n": int(len(fh)), "reaches_london_low_first": round(float(fh.reach_other.astype(float).mean()), 3) if len(fh) else None,
                                      "chance": round(float(fh.rw.mean()), 3) if len(fh) else None,
                                      "down_day": round(float(1 - x[x["first"] == "H"].up_day.mean()), 3) if (x["first"] == "H").any() else None},
                "all_days_up": round(float(x.up_day.mean()), 3)}
        res["claim"][s] = claim
        st = setups(df, s)
        st.to_csv(os.path.join(OUT, f"phase113_setups_{s}.csv"), index=False)
        configs = []
        for set_name, sk, tk in product(LEVEL_SETS, ("SWEEP", "HL"), ("LIQ", "2R")):
            sub = st[(st.set == set_name) & (st.stop_kind == sk) & (st.target_kind == tk)]
            if not len(sub):
                continue
            sc = p12.score(df, sub, s, time_is_bar_open=False)
            for plan in p12.PLANS:
                ex, cf = sc[sc.day <= EXPLORE_END][plan], sc[sc.day > EXPLORE_END][plan]
                configs.append({"config": f"{set_name} | stop {sk} | target {tk} | {plan}", "n_explore": int(len(ex)), "explore": float(ex.mean()) if len(ex) else -9,
                                "n_confirm": int(len(cf)), "confirm": float(cf.mean()) if len(cf) else None,
                                "c2025": float(sc[(sc.day > EXPLORE_END) & (sc.day < "2026")][plan].mean()) if len(cf) else None,
                                "c2026": float(sc[sc.day >= "2026"][plan].mean()) if len(cf) else None, "_r": cf.to_numpy()})
        ok = [c for c in configs if c["n_explore"] >= 80]
        ok.sort(key=lambda c: -c["explore"])
        best = ok[0] if ok else None
        stats = p1.summarize(best["_r"], rng) if best else {}
        res["model"][s] = {
            "configs_tested": len(configs),
            "chosen_on_2023_24": best["config"] if best else None,
            "chosen_explore_mean": round(best["explore"], 3) if best else None,
            "chosen_2025_26": stats, "chosen_2025": round(best["c2025"], 3) if best else None, "chosen_2026": round(best["c2026"], 3) if best else None,
            "passes": bool(best and stats.get("ci95", [-1])[0] > 0 and best["c2025"] > 0 and best["c2026"] > 0),
            "top10_on_explore": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in c.items() if k != "_r"} for c in ok[:10]],
            "share_of_configs_positive_in_2025_26": round(float(np.mean([c["confirm"] > 0 for c in configs if c["confirm"] is not None])), 3),
        }
    with open(os.path.join(OUT, "phase113_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    print(json.dumps(r["claim"], indent=1))
    for s, v in r["model"].items():
        print(f"\n== {s} model: {v['configs_tested']} configs; chosen on 2023-24: {v['chosen_on_2023_24']} (explore {v['chosen_explore_mean']})")
        print(f"   2025-26: {v['chosen_2025_26']}  2025={v['chosen_2025']} 2026={v['chosen_2026']} pass={v['passes']}")
        print(f"   share of all configs positive in 2025-26: {v['share_of_configs_positive_in_2025_26']}")
        for c in v["top10_on_explore"]:
            print("    ", c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
