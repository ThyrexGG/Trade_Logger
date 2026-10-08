"""Phase 104 — TJR-style discretion modelled as LEARNED SELECTION, walk-forward.

Research only. Phases 101-103 found that loose sweep-fades trade daily and lose,
and strict rule sets are rare and break-even. A discretionary trader sees many
possible setups a day and picks some. This phase builds that wide candidate set
and asks whether *which* candidate to take can be learned from past years and
still work on years the model never saw.

Pre-registered (written before any result):

Candidates (1-minute bars, NY time, 08:30-11:00 entries, flat 12:00):
  Levels   previous day + week high/low, overnight (18:00-08:30), Asia (20:00-00:00),
           London (02:00-05:00), opening range (09:30-09:35, live from 09:35), and
           5-minute + 15-minute swing highs/lows (2/2 fractals) from the previous
           09:30 onward, INCLUDING swings that form during the morning. A level is
           liquidity only until first breached; nearby equal swings are flagged.
  Sweep    the first breach of one or more live levels in a minute = one event.
  Trigger  the reversal must CLOSE beyond the low (for a high sweep) / high of the
           3 bars before the sweep, on the 1-, 3- or 5-minute chart, within 15
           minutes; the earliest timeframe to confirm wins.
  Trade    market entry at that close; stop beyond the extreme (NQ 1.00 / ES 0.25);
           target 2R; flat 12:00; costs = bar spread + slippage on market fills.
Features (no hard filters): level family, level count, equal-level flag, sweep
  depth, minutes from 09:30, trigger timeframe, minutes to confirm, displacement
  size, fair value gap left, NQ/ES SMT, 1-hour structure agreement, morning-trend
  agreement, stop size, room to the next opposite level, opening gap, volatility
  regime, 08:30 news spike, weekday, instrument.

Selection, walk-forward by calendar year (train on everything before the year):
  model     logistic regression (primary) and a shallow gradient-boosted tree
            (secondary), predicting P(trade ends positive).
  rule      per day and instrument, the single highest-scoring candidate, taken
            only if its score is in the top 25% of that fold's TRAINING scores.
  test      2024, 2025, 2026 (to 2026-10-08).

PASS (primary model): pooled test-year mean R > 0 with the 95% CI above 0,
beats a random pick among the same days' candidates (placebo p < 0.05), and
every test year is positive. Anything less is reported as it is.

    python -m phase104_tjr_selection
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase103b_tjr_m1 as p3

BUFFER = p3.BUFFER
TARGET_R = 2.0
CONFIRM_MIN = 15
TRIG_TFS = (1, 3, 5)
TOP_FRACTION = 0.25
TEST_YEARS = (2024, 2025, 2026)
EQ_TOL = 0.0003  # swings within 0.03% count as "equal"
FAMILIES = ("PW", "PD", "ON", "ASIA", "LDN", "OR", "S15", "S5")
RANK = {f: i for i, f in enumerate(FAMILIES)}
OUT_DIR = p1.CACHE
COMMISSION: Dict[str, float] = {}  # per-trade commission in PRICE units (FX prop accounts charge per lot)
FEATURES = [f"fam_{f}" for f in FAMILIES] + [
    "n_levels", "equal", "depth_atr", "minutes_anchor", "trig_tf", "confirm_min", "disp_atr", "fvg", "smt",
    "h1_agree", "morning_agree", "stop_atr", "room_r", "gap_side_atr", "atr_regime", "open_spike_atr", "weekday", "is_nq",
]

# The trading session the candidates are built for. The default is the NY
# equity open used for NQ/ES; Phase 105 swaps in London / NY sessions for FX.
#   start       sweeps may start here          last_entry  no entries after
#   flat        everything closed              anchor      "minutes_anchor" counts from here
#   coverage    a day needs ~complete bars in this span to be used
#   daily       "rth" = previous day 09:30-16:00; "fx" = previous 17:00-17:00 FX day
SESSION = {"start": (8, 30), "last_entry": (11, 0), "flat": (12, 0), "anchor": (9, 30),
           "coverage": ((9, 30), (11, 0)), "daily": "rth"}


def _t(day: pd.Timestamp, hm) -> pd.Timestamp:
    return day + pd.Timedelta(hours=hm[0], minutes=hm[1])


def _h1_bias(df: pd.DataFrame, cutoff: pd.Timestamp) -> int:
    """1-hour swing structure from bars CLOSED before `cutoff`: rising swing highs
    and lows -> +1, falling -> -1, else 0 (same rule as phase103b, any cutoff)."""
    hist = df.loc[cutoff - pd.Timedelta(days=7): cutoff - pd.Timedelta(seconds=1)]
    if len(hist) < 500:
        return 0
    h1 = hist.resample("1h").agg({"high": "max", "low": "min"}).dropna()
    hi, lo = p3._fractals(h1["high"], h1["low"])
    hi = hi[hi.index >= cutoff - pd.Timedelta(days=5)]
    lo = lo[lo.index >= cutoff - pd.Timedelta(days=5)]
    if len(hi) < 2 or len(lo) < 2:
        return 0
    if hi.iloc[-1] > hi.iloc[-2] and lo.iloc[-1] > lo.iloc[-2]:
        return 1
    if hi.iloc[-1] < hi.iloc[-2] and lo.iloc[-1] < lo.iloc[-2]:
        return -1
    return 0


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def _daily_context(df: pd.DataFrame) -> pd.DataFrame:
    if SESSION["daily"] == "fx":
        key = (df.index + pd.Timedelta(hours=7)).date  # FX day = 17:00 NY (previous day) -> 17:00
        g = df.groupby(key)
    else:
        rth = df[(df.index.time >= dt.time(9, 30)) & (df.index.time < dt.time(16, 0))]
        g = rth.groupby(rth.index.date)
    d = pd.DataFrame({"hi": g["high"].max(), "lo": g["low"].min(), "close": g["close"].last(), "open": g["open"].first()})
    d["range"] = d["hi"] - d["lo"]
    d["atr"] = d["range"].shift(1).rolling(14).mean()
    d["atr_regime"] = d["atr"] / d["atr"].rolling(60, min_periods=20).median()
    d["prev_close"] = d["close"].shift(1)
    return d


def _fractal_points(bars: pd.DataFrame, tf_min: int, fam: str) -> List[dict]:
    h, l = bars["high"], bars["low"]
    out = []
    hi = (h > h.shift(1)) & (h > h.shift(2)) & (h >= h.shift(-1)) & (h >= h.shift(-2))
    lo = (l < l.shift(1)) & (l < l.shift(2)) & (l <= l.shift(-1)) & (l <= l.shift(-2))
    for ts in bars.index[hi.fillna(False).to_numpy()]:
        out.append({"price": float(h[ts]), "side": "H", "family": fam, "formed": ts, "live_from": ts + pd.Timedelta(minutes=3 * tf_min)})
    for ts in bars.index[lo.fillna(False).to_numpy()]:
        out.append({"price": float(l[ts]), "side": "L", "family": fam, "formed": ts, "live_from": ts + pd.Timedelta(minutes=3 * tf_min)})
    return out


def _levels(df: pd.DataFrame, day: pd.Timestamp, ctx: pd.DataFrame, prev_day) -> List[dict]:
    lv: List[dict] = []
    t830 = _t(day, SESSION["start"])  # liquidity cut-off: the session start

    def add(price, side, fam, formed, live_from=None):
        if price == price:
            lv.append({"price": float(price), "side": side, "family": fam, "formed": formed, "live_from": live_from or formed})

    pr = ctx.loc[prev_day]
    pd_end = pd.Timestamp(prev_day) + pd.Timedelta(hours=17 if SESSION["daily"] == "fx" else 16)
    add(pr["hi"], "H", "PD", pd_end)
    add(pr["lo"], "L", "PD", pd_end)
    wk0 = day - pd.Timedelta(days=day.weekday() + 7)
    pw = df.loc[wk0: wk0 + pd.Timedelta(days=5)]
    if len(pw):
        add(pw["high"].max(), "H", "PW", pw.index[-1])
        add(pw["low"].min(), "L", "PW", pw.index[-1])
    for fam, a, b in (("ON", -6, 8.5), ("ASIA", -4, 0), ("LDN", 2, 5)):
        seg = df.loc[day + pd.Timedelta(hours=a): day + pd.Timedelta(hours=b) - pd.Timedelta(seconds=1)]
        if len(seg):
            add(seg["high"].max(), "H", fam, day + pd.Timedelta(hours=b))
            add(seg["low"].min(), "L", fam, day + pd.Timedelta(hours=b))
    orb = df.loc[day + pd.Timedelta(hours=9, minutes=30): day + pd.Timedelta(hours=9, minutes=35) - pd.Timedelta(seconds=1)]
    if len(orb):
        t935 = day + pd.Timedelta(hours=9, minutes=35)
        add(orb["high"].max(), "H", "OR", t935, t935)
        add(orb["low"].min(), "L", "OR", t935, t935)
    swing_src = df.loc[pd.Timestamp(prev_day) + pd.Timedelta(hours=9, minutes=30): _t(day, SESSION["flat"])]
    for tf, fam in ((5, "S5"), (15, "S15")):
        bars = swing_src.resample(f"{tf}min", label="left", closed="left").agg({"high": "max", "low": "min"}).dropna()
        lv += _fractal_points(bars, tf, fam)
    # liquidity only while untouched: drop anything breached between its formation and 08:30
    pre = df.loc[: t830 - pd.Timedelta(seconds=1)]
    keep = []
    for x in lv:
        if x["live_from"] <= t830:
            seg = pre.loc[x["formed"]:]
            if len(seg) and ((x["side"] == "H" and seg["high"].max() > x["price"]) or (x["side"] == "L" and seg["low"].min() < x["price"])):
                continue
        keep.append(x)
    # equal highs / lows among swing points
    for side in ("H", "L"):
        sw = [x for x in keep if x["side"] == side and x["family"] in ("S5", "S15")]
        for a in sw:
            a["equal"] = any(b is not a and abs(b["price"] - a["price"]) <= EQ_TOL * a["price"] for b in sw)
    return keep


def _tf_bars(day_min: pd.DataFrame, tf: int):
    if tf == 1:
        b = day_min[["open", "high", "low", "close"]].copy()
    else:
        b = day_min.resample(f"{tf}min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    end = b.index + pd.Timedelta(minutes=tf)  # bar close time
    return b, end


# ----------------------------------------------------------------------------
# candidates
# ----------------------------------------------------------------------------
def candidates(symbol: str, df: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    ctx = _daily_context(df)
    days = [d for d in ctx.index if pd.Timestamp(d).weekday() < 5]
    rows = []
    for k in range(1, len(days)):
        day_d, prev_d = days[k], days[k - 1]
        day = pd.Timestamp(day_d)
        c = ctx.loc[day_d]
        if c["atr"] != c["atr"]:
            continue
        a, b = SESSION["coverage"]
        win = df.loc[_t(day, a): _t(day, b) - pd.Timedelta(seconds=1)]
        if len(win) < 0.85 * (b[0] * 60 + b[1] - a[0] * 60 - a[1]):
            continue
        rows += _day_candidates(symbol, df, other, day, prev_d, ctx, c)
    return pd.DataFrame(rows)


def _day_candidates(symbol, df, other, day, prev_d, ctx, c) -> List[dict]:
    atr = float(c["atr"])
    t830, t1100, t930, t_flat = (_t(day, SESSION[k]) for k in ("start", "last_entry", "anchor", "flat"))
    m = df.loc[t830 - pd.Timedelta(hours=4, minutes=30): t_flat - pd.Timedelta(seconds=1)]
    om = other.loc[t830 - pd.Timedelta(hours=4, minutes=30): t_flat - pd.Timedelta(seconds=1)]
    idx = m.index
    o, h, l, cl, spr = (m[k].to_numpy() for k in ("open", "high", "low", "close", "spread"))
    i0, i_last, n = idx.searchsorted(t830), idx.searchsorted(t1100), len(m)
    if i_last - i0 < 60:
        return []
    levels = _levels(df, day, ctx, prev_d)
    tfb = {tf: _tf_bars(m, tf) for tf in TRIG_TFS}
    try:
        h1_bias = _h1_bias(df, t830)
    except Exception:  # noqa: BLE001
        h1_bias = 0
    open830 = o[i0]
    # gap from the previous close to the SESSION START price (known at entry time)
    gap = (open830 - float(c["prev_close"])) / atr if c["prev_close"] == c["prev_close"] else 0.0
    news_atr = (m, t830)  # the opening spike is measured per candidate, up to the sweep only
    oh, ol = om["high"], om["low"]

    live = [x for x in levels if x["live_from"] <= t830]
    pending = sorted([x for x in levels if x["live_from"] > t830], key=lambda x: x["live_from"])
    out = []
    for i in range(i0, i_last):
        now = idx[i]
        while pending and pending[0]["live_from"] <= now:
            x = pending.pop(0)
            seg = m.loc[x["formed"]: now - pd.Timedelta(seconds=1)]
            if not (len(seg) and ((x["side"] == "H" and seg["high"].max() > x["price"]) or (x["side"] == "L" and seg["low"].min() < x["price"]))):
                live.append(x)
        for side_char in ("H", "L"):
            hit = [x for x in live if x["side"] == side_char and ((side_char == "H" and h[i] > x["price"]) or (side_char == "L" and l[i] < x["price"]))]
            if not hit:
                continue
            for x in hit:
                live.remove(x)
            cand = _trigger(symbol, side_char, hit, i, idx, o, h, l, cl, spr, tfb, t1100, n, atr, live, oh, ol,
                            h1_bias, open830, gap, news_atr, c, t930, t_flat)
            if cand:
                cand["day"] = str(day.date())
                out.append(cand)
    return out


def _trigger(symbol, side_char, hit, i, idx, o, h, l, cl, spr, tfb, t1100, n, atr, live, oh, ol,
             h1_bias, open830, gap, news_atr, c, t930, t_flat) -> Optional[dict]:
    side = -1 if side_char == "H" else 1  # fade the sweep
    t_sweep = idx[i]
    best = None
    for tf in TRIG_TFS:
        b, end = tfb[tf]
        k_s = b.index.searchsorted(t_sweep, side="right") - 1
        if k_s < 3:
            continue
        ref = b["low"].iloc[k_s - 3:k_s].min() if side < 0 else b["high"].iloc[k_s - 3:k_s].max()
        for k in range(k_s, len(b)):
            if end[k] > t_sweep + pd.Timedelta(minutes=CONFIRM_MIN) or end[k] > t1100:
                break
            close = b["close"].iloc[k]
            if (side < 0 and close < ref) or (side > 0 and close > ref):
                if best is None or end[k] < best[1]:
                    best = (tf, end[k], close)
                break
    if best is None:
        return None
    tf, t_conf, entry = best
    j = idx.searchsorted(t_conf) - 1  # last minute inside the confirming bar
    if j <= i:
        j = i
    ext = h[i:j + 1].max() if side < 0 else l[i:j + 1].min()
    stop = ext + BUFFER[symbol] if side < 0 else ext - BUFFER[symbol]
    risk = abs(entry - stop)
    if risk <= 0 or risk < 2 * spr[j] or (side < 0 and entry >= stop) or (side > 0 and entry <= stop):
        return None
    target = entry + side * TARGET_R * risk
    i_end = idx.searchsorted(t_flat)
    k, px, reason = p1._simulate_exit(h, l, o, idx, j + 1, min(i_end, n), side, entry, stop, target, None)
    slip = p1.SLIPPAGE[symbol]
    cost = float(spr[j]) + slip + (slip if reason in ("stop", "time") else 0.0) + COMMISSION.get(symbol, 0.0)
    m_day, t_start = news_atr
    spike = m_day.loc[t_start: min(t_start + pd.Timedelta(minutes=5), t_sweep) - pd.Timedelta(seconds=1)]
    spike_atr = float((spike["high"].max() - spike["low"].min()) / atr) if len(spike) else 0.0
    r = (side * (px - entry) - cost) / risk
    # features
    lvl_prices = [x["price"] for x in hit]
    level_px = max(lvl_prices) if side < 0 else min(lvl_prices)
    fam = min((x["family"] for x in hit), key=lambda f: RANK[f])
    fvg = any((side < 0 and l[q - 2] > h[q]) or (side > 0 and h[q - 2] < l[q]) for q in range(max(i, 2), j + 1))
    # SMT: did the OTHER index also make a new 60-minute extreme between our sweep and confirmation?
    pre_h = oh.loc[t_sweep - pd.Timedelta(minutes=60): t_sweep - pd.Timedelta(seconds=1)]
    pre_l = ol.loc[t_sweep - pd.Timedelta(minutes=60): t_sweep - pd.Timedelta(seconds=1)]
    if side < 0:
        other_new = bool(oh.loc[t_sweep: t_conf].max() > pre_h.max()) if len(pre_h) else True
    else:
        other_new = bool(ol.loc[t_sweep: t_conf].min() < pre_l.min()) if len(pre_l) else True
    opp = [x["price"] for x in live if (side > 0 and x["side"] == "H" and x["price"] > entry) or (side < 0 and x["side"] == "L" and x["price"] < entry)]
    room = (min(opp) - entry if side > 0 else entry - max(opp)) / risk if opp else 6.0
    row = {f"fam_{f}": int(f == fam) for f in FAMILIES}
    row.update({
        "symbol": symbol, "time": str(t_conf), "side": side, "entry": round(entry, 6), "stop": round(stop, 6), "risk": round(risk, 6),
        "family": fam, "n_levels": len(hit), "equal": int(any(x.get("equal") for x in hit)),
        "depth_atr": abs(ext - level_px) / atr, "minutes_anchor": (t_sweep - t930).total_seconds() / 60, "trig_tf": tf,
        "confirm_min": (t_conf - t_sweep).total_seconds() / 60, "disp_atr": abs(entry - ext) / atr, "fvg": int(fvg),
        "smt": int(not other_new), "h1_agree": h1_bias * side, "morning_agree": int(np.sign(entry - open830) == side),
        "stop_atr": risk / atr, "room_r": min(room, 6.0), "gap_side_atr": gap * side,
        "atr_regime": float(c["atr_regime"]) if c["atr_regime"] == c["atr_regime"] else 1.0,
        "open_spike_atr": spike_atr, "weekday": t_sweep.weekday(), "is_nq": int(symbol == "NQ"),
        "exit": reason, "r": round(r, 4),
    })
    return row


# ----------------------------------------------------------------------------
# walk-forward selection
# ----------------------------------------------------------------------------
def _models():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {
        "logistic": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)),
        "boosted": lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=50, random_state=104),
    }


def _pick(test: pd.DataFrame, scores: np.ndarray, thr: float) -> pd.DataFrame:
    t = test.assign(score=scores)
    top = t.sort_values("score", ascending=False).groupby(["day", "symbol"], as_index=False).head(1)
    return top[top.score >= thr]


def walk_forward(cand: pd.DataFrame, tag: str = "phase104") -> Dict:
    rng = np.random.default_rng(1040)
    cand = cand.copy()
    cand["year"] = cand["day"].str[:4].astype(int)
    cand["y"] = (cand["r"] > 0).astype(int)
    out: Dict = {}
    for name, make in _models().items():
        picks = []
        folds = []
        for yr in TEST_YEARS:
            train, test = cand[cand.year < yr], cand[cand.year == yr]
            if len(train) < 200 or not len(test):
                continue
            mdl = make().fit(train[FEATURES], train["y"])
            thr = float(np.quantile(mdl.predict_proba(train[FEATURES])[:, 1], 1 - TOP_FRACTION))
            sel = _pick(test, mdl.predict_proba(test[FEATURES])[:, 1], thr)
            picks.append(sel)
            folds.append({"year": yr, "train_n": int(len(train)), "test_candidates": int(len(test)), **p1.summarize(sel["r"].to_numpy(), rng)})
            if name == "logistic" and yr == TEST_YEARS[-1]:
                coefs = mdl[-1].coef_[0]
                out["logistic_coefficients_last_fold"] = dict(sorted(zip(FEATURES, np.round(coefs, 3)), key=lambda kv: -abs(kv[1])))
        allp = pd.concat(picks) if picks else pd.DataFrame(columns=["r"])
        rs = allp["r"].to_numpy()
        # placebo: same days, random candidate of that day/instrument
        test_all = cand[cand.year.isin(TEST_YEARS)]
        groups = {k: g["r"].to_numpy() for k, g in test_all.groupby(["day", "symbol"])}
        keys = list(zip(allp["day"], allp["symbol"]))
        sims = np.array([np.mean([rng.choice(groups[k]) for k in keys]) for _ in range(1000)]) if keys else np.array([np.nan])
        p = float((sims >= rs.mean()).mean()) if len(rs) else float("nan")
        st = p1.summarize(rs, rng)
        passed = bool(len(rs) and st["ci95"][0] > 0 and p < 0.05 and all(f.get("mean_r", -1) > 0 for f in folds))
        out[name] = {"folds": folds, "pooled": st, "placebo_p": round(p, 4), "placebo_mean": round(float(np.nanmean(sims)), 3), "passes": passed}
        allp.to_csv(os.path.join(OUT_DIR, f"{tag}_picks_{name}.csv"), index=False)
    # reference rows (no model)
    test_all = cand[cand.year.isin(TEST_YEARS)]
    first = test_all.sort_values("time").groupby(["day", "symbol"], as_index=False).head(1)
    out["reference"] = {
        "all_candidates": p1.summarize(test_all["r"].to_numpy(), rng),
        "first_candidate_each_day": p1.summarize(first["r"].to_numpy(), rng),
        "candidates_per_day": round(float(test_all.groupby(["day", "symbol"]).size().mean()), 1),
    }
    return out


def run() -> Dict:
    data = {s: p1.load(s, "M1") for s in p1.SYMBOLS}
    data = {s: d[d.index >= pd.Timestamp("2023-04-01")] for s, d in data.items()}
    path = os.path.join(OUT_DIR, "phase104_candidates.csv")
    frames = [candidates(s, data[s], data["ES" if s == "NQ" else "NQ"]) for s in p1.SYMBOLS]
    cand = pd.concat(frames, ignore_index=True)
    cand.to_csv(path, index=False)
    res = {"phase": 104, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "n_candidates": int(len(cand)), "days": int(cand["day"].nunique()),
           "by_family": cand.groupby("family")["r"].agg(["size", "mean"]).round(3).reset_index().to_dict(orient="records")}
    res.update(walk_forward(cand))
    with open(os.path.join(OUT_DIR, "phase104_result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k not in ("by_family",)}, indent=1, default=str))
    print("by family:", r["by_family"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
