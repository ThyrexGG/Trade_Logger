# -*- coding: utf-8 -*-
"""
Phase 99 -- FX / Rate-Differential Carry (G10).

The second candidate sleeve for the Phase-97 allocation. Phase 97 found a
usable edge in delta-neutral crypto funding carry but capped it at ~25%
of capital because of the exchange-collapse tail. FX carry is the
intended diversifier: a different return driver (G10 short-rate
differentials), no crypto-exchange counterparty tail, and historically
near-uncorrelated with crypto.

Pre-registered, zero-fitting question:

    Rank the G10 currencies each month by their 3-month interbank rate;
    go long an equal-weight basket of the 3 highest-yielders, short an
    equal-weight basket of the 3 lowest-yielders (dollar-neutral). Each
    currency position is measured in USD terms and accrues its own
    short-rate minus the USD rate. After realistic G10 spot costs, does
    this classic carry basket earn a positive out-of-sample return -- and
    does adding it to the Phase-97 book help?

Frozen design (fixed before any result; never tuned / per-currency /
best-of):

  * Universe: USD, EUR, GBP, JPY, CAD, AUD, NZD, CHF (8 currencies).
  * Rates: FRED 3-month interbank series `IR3TIB01<CCY>M156N`
    (OECD-sourced, monthly), fetched once and cached as an artifact.
    Last available rate is carried forward for any month it lags.
  * Monthly total return for holding currency i (vs USD) =
        spot_return(i / USD)  +  (rate_i - rate_USD) / 12
    (USD itself: spot_return 0, so its total return is 0 by construction
    -- being "long USD" is just holding cash at the US rate, which nets
    to zero against the USD funding leg).
  * Signal: sort by rate; long top 3, short bottom 3; equal weight each
    leg; the basket return = mean(top 3 total returns) - mean(bottom 3).
  * Rebalance monthly. Cost: 1.5 bps one-way per currency leg on
    turnover, ladder ZERO/BASE/ADVERSE/SEVERE = 0/1/2/4x.

Read-only research. FRED fetch is free authorised macro data (the
project's Phase-65 provider path). No execution, no broker transmission,
no account mutation, no order/position/risk module import. Frozen
Phase-74 Gold holdout never read.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import gold_strategy_baseline as gsb
import historical_data_store as store          # importing this loads .env (database.load_dotenv)
import os

import phase96_funding_carry as p96

SCHEMA_VERSION = "phase99.1"
ARTIFACT_KEY = "phase99_fx_carry"
_RATES_ARTIFACT = "phase99_g10_rates"

# ==========================================================================
# Frozen universe / parameters
# ==========================================================================
G10: Tuple[str, ...] = ("USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF")
# FRED OECD 3-month interbank series use 2-letter AREA codes, not currency codes
_FRED_AREA: Dict[str, str] = {"USD": "US", "EUR": "EZ", "GBP": "GB", "JPY": "JP",
                              "CAD": "CA", "AUD": "AU", "NZD": "NZ", "CHF": "CH"}
_FRED_SERIES: Dict[str, str] = {c: f"IR3TIB01{a}M156N" for c, a in _FRED_AREA.items()}
# how to get each currency's price vs USD from the stored daily FX bars
_VS_USD: Dict[str, Tuple[str, bool]] = {
    "EUR": ("EURUSD", False), "GBP": ("GBPUSD", False), "AUD": ("AUDUSD", False),
    "NZD": ("NZDUSD", False), "JPY": ("USDJPY", True), "CHF": ("USDCHF", True),
    "CAD": ("USDCAD", True),   # True = invert (stored as USDxxx, want xxx/USD)
}
_N_LONG = 3
_N_SHORT = 3
_MONTHS_PER_YEAR = 12.0
_WARMUP_MONTHS = 6
_FX_COST_BPS = 1.5                                   # one-way, per currency leg
_COST_LADDER: Dict[str, float] = {"ZERO": 0.0, "BASE": 1.0, "ADVERSE": 2.0, "SEVERE": 4.0}

_FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
_PLACEBO_REPS = 500
_RAND_CCY_SEED = 99001
_RANK_SHUFFLE_SEED = 99501

DESIGN_NOTE: Dict[str, Any] = {
    "question": "Does a frozen G10 long-top-3 / short-bottom-3 rate-differential carry basket earn a "
                "positive OOS return after costs, and does adding it to the Phase-97 book help?",
    "universe": list(G10),
    "rates": "FRED IR3TIB01<CCY>M156N 3-month interbank (monthly, OECD); last value carried forward",
    "monthly_return": "spot_return(ccy/USD) + (rate_ccy - rate_USD)/12; USD leg = 0",
    "signal": "sort by rate; long top 3 equal-weight, short bottom 3 equal-weight; dollar-neutral",
    "rebalance": "monthly",
    "costs": "1.5 bps one-way per currency leg on turnover; ladder 0/1/2/4x",
    "no_fitting": "every parameter frozen before results",
    "sample_caveat": "EURUSD daily bars start 2018-08 -> ~97 monthly observations; a thin sample that "
                     "limits verdict strength",
    "holdout": "frozen Phase-74 Gold holdout never read",
}


def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


# ==========================================================================
# FRED rate ingestion (fetch once, cache as artifact)
# ==========================================================================
def fetch_g10_rates(force: bool = False) -> Dict[str, Any]:
    if not force:
        cached = store.load_artifact(_RATES_ARTIFACT)
        if cached:
            return cached["payload"]
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY not set (.env). Cannot fetch G10 rates.")
    series: Dict[str, List[List[Any]]] = {}
    for ccy, sid in _FRED_SERIES.items():
        url = (f"{_FRED_BASE}?series_id={sid}&api_key={key}&file_type=json"
               f"&observation_start=2010-01-01")
        d = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TradeLogger research"})
                with urllib.request.urlopen(req, timeout=25) as r:
                    d = json.loads(r.read().decode("utf-8"))
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                if attempt == 3:
                    raise RuntimeError(f"FRED fetch failed for {ccy} ({sid}): {e!r}")
                time.sleep(1.5 * (attempt + 1))
        obs = [[o["date"], float(o["value"])] for o in (d or {}).get("observations", [])
               if o.get("value") not in (".", "", None)]
        if not obs:
            raise RuntimeError(f"FRED returned no observations for {ccy} ({sid})")
        series[ccy] = obs
        time.sleep(0.2)
    payload = {"schema_version": SCHEMA_VERSION, "fetched_at": datetime.now(timezone.utc).isoformat(),
               "fred_series": _FRED_SERIES, "series": series,
               "coverage": {c: [v[0][0], v[-1][0], len(v)] for c, v in series.items()}}
    store.save_artifact(_RATES_ARTIFACT, "phase99_g10_rates", payload)
    return payload


def get_g10_rates() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(_RATES_ARTIFACT)
    return art["payload"] if art else None


# ==========================================================================
# Monthly panels
# ==========================================================================
def _monthly_rate_frame(rates_payload: Dict[str, Any]) -> pd.DataFrame:
    cols = {}
    for ccy, obs in rates_payload["series"].items():
        idx = pd.to_datetime([o[0] for o in obs], utc=True)
        s = pd.Series([o[1] for o in obs], index=idx).sort_index()
        cols[ccy] = s
    df = pd.DataFrame(cols).resample("ME").last().ffill()
    return df


def _ccy_usd_monthly_close() -> pd.DataFrame:
    """Each non-USD currency's month-end price vs USD (invert the USDxxx pairs)."""
    cols = {"USD": None}
    for ccy, (pair, invert) in _VS_USD.items():
        candles = store.get_candles(pair, "1d")
        if not candles:
            continue
        idx = pd.to_datetime([c["time"] for c in candles], unit="s", utc=True)
        s = pd.Series([float(c["close"]) for c in candles], index=idx).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        s = s[s > 0].resample("ME").last()
        cols[ccy] = (1.0 / s) if invert else s
    df = pd.DataFrame({k: v for k, v in cols.items() if v is not None})
    df["USD"] = 1.0
    return df.sort_index()


def build_monthly_total_returns(rates_payload: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """(months x 8) total monthly return for holding each currency vs USD:
    spot_return + (rate_ccy - rate_USD)/12."""
    rates_payload = rates_payload or get_g10_rates() or fetch_g10_rates()
    rate_m = _monthly_rate_frame(rates_payload)
    px_m = _ccy_usd_monthly_close()
    idx = rate_m.index.intersection(px_m.index)
    rate_m, px_m = rate_m.reindex(idx), px_m.reindex(idx)
    spot_ret = px_m.pct_change()
    spot_ret["USD"] = 0.0
    carry = (rate_m.sub(rate_m["USD"], axis=0)) / 100.0 / _MONTHS_PER_YEAR   # rates are in percent
    tot = spot_ret + carry
    tot = tot[[c for c in G10 if c in tot.columns]].dropna(how="all")
    return tot


# ==========================================================================
# The frozen carry basket
# ==========================================================================
def run_fx_carry(cost_key: str = "BASE", n_long: int = _N_LONG, n_short: int = _N_SHORT,
                 rates_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rates_payload = rates_payload or get_g10_rates() or fetch_g10_rates()
    rate_m = _monthly_rate_frame(rates_payload)
    tot = build_monthly_total_returns(rates_payload)
    ccys = list(tot.columns)
    rate_m = rate_m.reindex(tot.index)[ccys]
    R = tot.to_numpy(float)
    RATE = rate_m.to_numpy(float)
    T, N = R.shape
    cost = _FX_COST_BPS * 1e-4 * _COST_LADDER[cost_key]

    prev_w = np.zeros(N)
    net, gross, cost_c, turnover = [], [], [], []
    fwd = np.vstack([R[1:], np.full((1, N), np.nan)])
    for t in range(T):
        rr = RATE[t]
        w = np.zeros(N)
        if np.isfinite(rr).sum() >= (n_long + n_short):
            order = np.argsort(np.where(np.isfinite(rr), rr, -np.inf))
            longs = order[-n_long:]
            shorts = order[np.isfinite(rr[order])][:n_short]
            w[longs] = 1.0 / n_long
            w[shorts] = -1.0 / n_short
        step = fwd[t]
        ok = np.isfinite(step)
        g = float(np.sum(w[ok] * step[ok]))
        c = float(np.sum(np.abs(w - prev_w) * cost))
        net.append(g - c); gross.append(g); cost_c.append(-c)
        turnover.append(float(np.sum(np.abs(w - prev_w))))
        prev_w = w
    return {"index": tot.index, "net": np.array(net), "gross": np.array(gross),
            "cost": np.array(cost_c), "turnover": np.array(turnover), "cost_key": cost_key}


def _metrics(net: np.ndarray, index: pd.DatetimeIndex, warmup: int = _WARMUP_MONTHS) -> Dict[str, Any]:
    n = np.asarray(net, float)[warmup:]
    ix = index[warmup:]
    m = np.isfinite(n)
    n, ix = n[m], ix[m]
    if n.size < 12:
        return {"state": "INSUFFICIENT_SAMPLE", "n_months": int(n.size)}
    eq = np.cumprod(1.0 + n)
    years = n.size / _MONTHS_PER_YEAR
    sd = float(n.std(ddof=1))
    rmax = np.maximum.accumulate(eq)
    dd = float((eq / rmax - 1.0).min())
    yearly = (1.0 + pd.Series(n, index=ix)).resample("YE").prod() - 1.0
    return {
        "state": "OK", "n_months": int(n.size), "start": ix[0].date().isoformat(),
        "end": ix[-1].date().isoformat(),
        "cagr": round(float(eq[-1] ** (1.0 / years) - 1.0) if eq[-1] > 0 else -1.0, 4),
        "ann_vol": round(sd * np.sqrt(_MONTHS_PER_YEAR), 4),
        "sharpe": round(float(n.mean() / sd * np.sqrt(_MONTHS_PER_YEAR)), 3) if sd > 0 else None,
        "max_drawdown": round(dd, 4), "total_return": round(float(eq[-1] - 1.0), 4),
        "monthly_hit_rate": round(float((n > 0).mean()), 3),
        "per_year_return": {str(k.year): round(float(v), 4) for k, v in yearly.items()},
        "positive_years": int((yearly > 0).sum()), "n_years": int(yearly.size),
    }


def _half_split(net: np.ndarray, index: pd.DatetimeIndex) -> Dict[str, Any]:
    n = np.asarray(net, float)
    live = np.arange(_WARMUP_MONTHS, n.size)
    if live.size < 36:
        return {"state": "INSUFFICIENT_SAMPLE"}
    mid = _WARMUP_MONTHS + live.size // 2
    a = np.full_like(n, np.nan); a[_WARMUP_MONTHS:mid] = n[_WARMUP_MONTHS:mid]
    b = np.full_like(n, np.nan); b[mid:] = n[mid:]
    return {"first_half": _metrics(a, index, warmup=_WARMUP_MONTHS),
            "second_half": _metrics(b, index, warmup=mid)}


# ==========================================================================
# Controls
# ==========================================================================
def random_currency_placebo(reps: int = _PLACEBO_REPS, seed: int = _RAND_CCY_SEED,
                            cost_key: str = "BASE") -> Dict[str, Any]:
    tot = build_monthly_total_returns()
    R = tot.to_numpy(float)
    T, N = R.shape
    fwd = np.vstack([R[1:], np.full((1, N), np.nan)])
    real = _metrics(run_fx_carry(cost_key=cost_key)["net"], tot.index).get("sharpe")
    cost = _FX_COST_BPS * 1e-4 * _COST_LADDER[cost_key]
    rng = np.random.default_rng(seed)
    sharpes = []
    for _ in range(reps):
        prev_w = np.zeros(N)
        net = []
        for t in range(T):
            w = np.zeros(N)
            pick = rng.permutation(N)
            w[pick[:_N_LONG]] = 1.0 / _N_LONG
            w[pick[_N_LONG:_N_LONG + _N_SHORT]] = -1.0 / _N_SHORT
            step = fwd[t]; ok = np.isfinite(step)
            net.append(float(np.sum(w[ok] * step[ok]) - np.sum(np.abs(w - prev_w) * cost)))
            prev_w = w
        s = _metrics(np.array(net), tot.index).get("sharpe")
        if s is not None:
            sharpes.append(s)
    arr = np.array(sharpes)
    if real is None or arr.size == 0:
        return {"state": "INSUFFICIENT_SAMPLE"}
    return {"real_sharpe": round(real, 3), "placebo_mean_sharpe": round(float(arr.mean()), 3),
            "placebo_p95_sharpe": round(float(np.percentile(arr, 95)), 3),
            "real_percentile": round(float((arr <= real).mean()), 4),
            "empirical_p_one_sided": round(float((arr >= real).mean()), 4), "n_reps": int(arr.size)}


def g10_basket_benchmark() -> Dict[str, Any]:
    """Equal-weight long all non-USD G10 vs USD -- 'does carry beat just
    owning the basket?'"""
    tot = build_monthly_total_returns()
    non_usd = [c for c in tot.columns if c != "USD"]
    net = tot[non_usd].mean(axis=1).to_numpy(float)
    return {"metrics": _metrics(net, tot.index)}


def cost_ladder() -> Dict[str, Any]:
    return {k: _metrics(run_fx_carry(cost_key=k)["net"], build_monthly_total_returns().index).get("sharpe")
            for k in _COST_LADDER}


# ==========================================================================
# Does FX carry help the Phase-97 book? (monthly-aligned with crypto carry)
# ==========================================================================
def combine_with_crypto_carry(cost_key: str = "BASE") -> Dict[str, Any]:
    fx = run_fx_carry(cost_key=cost_key)
    fx_m = pd.Series(fx["net"], index=fx["index"])
    cr = p96.run_carry(cost_key="BASE")
    cr_w = pd.Series(cr["net"], index=cr["index"])
    cr_m = (1.0 + cr_w).resample("ME").prod() - 1.0        # weekly carry -> monthly
    df = pd.concat({"fx_carry": fx_m, "crypto_carry": cr_m}, axis=1, sort=True).dropna()
    if len(df) < 24:
        return {"state": "INSUFFICIENT_SAMPLE"}
    corr = float(df["fx_carry"].corr(df["crypto_carry"]))
    # equalise to the same monthly vol, then 50/50 blend
    fv, cv = df["fx_carry"].std(), df["crypto_carry"].std()
    if fv <= 0 or cv <= 0:
        return {"state": "INSUFFICIENT_SAMPLE"}
    blend = 0.5 * df["fx_carry"] / fv + 0.5 * df["crypto_carry"] / cv
    blend = blend * df["crypto_carry"].std()               # rescale to crypto-carry vol

    def _mm(x):
        x = np.asarray(x, float); sd = x.std(ddof=1)
        return {"sharpe": round(float(x.mean() / sd * np.sqrt(12)), 3) if sd > 0 else None,
                "ann_return": round(float((1 + x).prod() ** (12 / len(x)) - 1), 4),
                "max_dd": round(float((np.cumprod(1 + x) / np.maximum.accumulate(np.cumprod(1 + x)) - 1).min()), 4)}

    # decision-relevant framing: the Phase-97 book (25% crypto carry + 75% cash)
    # vs adding a 15% FX-carry sleeve funded from cash (25/15/60)
    cash_m = (1.0 + p97_cash_annual()) ** (1.0 / 12.0) - 1.0
    p97_book = 0.25 * df["crypto_carry"] + 0.75 * cash_m
    p97_plus_fx = 0.25 * df["crypto_carry"] + 0.15 * df["fx_carry"] + 0.60 * cash_m
    fx_helps_book = bool((_mm(p97_plus_fx)["sharpe"] or -9) > (_mm(p97_book)["sharpe"] or 9)
                         and _mm(p97_plus_fx)["ann_return"] > _mm(p97_book)["ann_return"])

    return {"n_months": int(len(df)), "correlation": round(corr, 3),
            "fx_carry_alone": _mm(df["fx_carry"].to_numpy(float)),
            "crypto_carry_alone": _mm(df["crypto_carry"].to_numpy(float)),
            "vol_parity_blend": _mm(blend.to_numpy(float)),
            "blend_improves_sharpe": bool((_mm(blend.to_numpy(float))["sharpe"] or -9)
                                          > (_mm(df["crypto_carry"].to_numpy(float))["sharpe"] or 9)),
            "phase97_book_25_75": _mm(p97_book.to_numpy(float)),
            "phase97_book_plus_15pct_fx": _mm(p97_plus_fx.to_numpy(float)),
            "fx_sleeve_helps_phase97_book": fx_helps_book}


def p97_cash_annual() -> float:
    try:
        import phase97_portfolio_construction as p97
        return float(p97._CASH_ANNUAL)
    except Exception:
        return 0.02


# ==========================================================================
# Verdict
# ==========================================================================
_VALID = ("FX_CARRY_EDGE_CONFIRMED", "FX_CARRY_EDGE_PROMISING",
          "FX_CARRY_EDGE_NOT_ESTABLISHED", "FX_CARRY_EDGE_NEGATIVE")


def classify_fx_carry(base_m: Dict[str, Any], adverse_m: Dict[str, Any], placebo: Dict[str, Any],
                      benchmark: Dict[str, Any], combine: Dict[str, Any]) -> Tuple[str, str]:
    if base_m.get("state") != "OK":
        return "FX_CARRY_EDGE_NOT_ESTABLISHED", "Insufficient sample."
    sharpe = base_m.get("sharpe") or 0.0
    adv = adverse_m.get("sharpe") if adverse_m.get("state") == "OK" else None
    pctl = placebo.get("real_percentile")
    yr = base_m.get("positive_years", 0) / max(base_m.get("n_years", 1), 1)
    bench = (benchmark.get("metrics", {}) or {}).get("sharpe")
    beats_basket = bench is None or sharpe > bench
    diversifies = (combine.get("fx_sleeve_helps_phase97_book")
                   or combine.get("blend_improves_sharpe")
                   or (abs(combine.get("correlation", 1.0)) < 0.3))

    if sharpe < 0.0:
        return "FX_CARRY_EDGE_NEGATIVE", f"Net Sharpe {sharpe} negative after BASE costs over a thin sample."
    if (sharpe >= 0.5 and pctl is not None and pctl >= 0.90 and adv is not None and adv > 0.2
            and yr >= 0.6 and beats_basket):
        return "FX_CARRY_EDGE_PROMISING", (
            f"Net Sharpe {sharpe} (BASE) / {adv} (ADVERSE), above the 90th pct of the random-currency "
            f"placebo ({pctl}), beats the naive G10 basket ({bench}), positive in a majority of years "
            f"-- but on only ~{base_m.get('n_months')} monthly observations, so 'promising' not "
            f"'confirmed'." + (" It also diversifies the crypto carry." if diversifies else ""))
    if sharpe >= 0.2 and diversifies:
        return "FX_CARRY_EDGE_NOT_ESTABLISHED", (
            f"Net Sharpe {sharpe} (BASE) is weakly positive and it is near-uncorrelated with the crypto "
            f"carry ({combine.get('correlation')}), so it is a mild diversifier -- but it does not clear "
            f"a standalone edge bar (thin sample, placebo pct {pctl}).")
    return "FX_CARRY_EDGE_NOT_ESTABLISHED", (
        f"Net Sharpe {sharpe} (BASE), placebo pct {pctl} -- G10 rate-differential carry does not show a "
        f"usable standalone edge on this 2018-2026 sample (a poor decade for FX carry).")


# ==========================================================================
# Result container
# ==========================================================================
@dataclass
class Phase99Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    design_note: Dict[str, Any]
    rates_coverage: Dict[str, Any]
    headline_base: Dict[str, Any]
    headline_adverse: Dict[str, Any]
    halves: Dict[str, Any]
    controls: Dict[str, Any]
    combine_with_crypto_carry: Dict[str, Any]
    verdict: str
    verdict_reason: str
    determinism: Dict[str, Any]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True
    live_automation_enabled: bool = False
    live_broker_transmission: str = "BLOCKED"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def run(force_fetch: bool = False) -> Phase99Result:
    t0 = datetime.now(timezone.utc)
    rates = fetch_g10_rates(force=force_fetch)
    base = run_fx_carry(cost_key="BASE", rates_payload=rates)
    adverse = run_fx_carry(cost_key="ADVERSE", rates_payload=rates)
    idx = base["index"]
    hb = _metrics(base["net"], idx)
    ha = _metrics(adverse["net"], idx)
    halves = _half_split(base["net"], idx)
    placebo = random_currency_placebo()
    bench = g10_basket_benchmark()
    ladder = cost_ladder()
    combine = combine_with_crypto_carry()
    controls = {"random_currency_placebo": placebo, "g10_basket_benchmark": bench, "cost_ladder": ladder}
    verdict, reason = classify_fx_carry(hb, ha, placebo, bench, combine)

    d1 = _metrics(run_fx_carry(cost_key="BASE", rates_payload=rates)["net"], idx)
    d2 = _metrics(run_fx_carry(cost_key="BASE", rates_payload=rates)["net"], idx)
    determinism_match = (json.dumps(d1, sort_keys=True, default=str) == json.dumps(d2, sort_keys=True, default=str))

    payload = {"headline_base": hb, "headline_adverse": ha, "controls": controls,
               "combine": combine, "verdict": verdict}
    chash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase99Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=_git_commit(),
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash, design_note=DESIGN_NOTE,
        rates_coverage=rates.get("coverage", {}), headline_base=hb, headline_adverse=ha, halves=halves,
        controls=controls, combine_with_crypto_carry=combine, verdict=verdict, verdict_reason=reason,
        determinism={"match": determinism_match}, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase99Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase99_fx_carry", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    import argparse
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Phase 99 FX / rate-differential carry (G10)")
    ap.add_argument("--refresh-rates", action="store_true", help="force re-fetch G10 rates from FRED")
    args = ap.parse_args(_argv)
    print("Phase 99 - FX / rate-differential carry (G10) ...", flush=True)
    res = run(force_fetch=args.refresh_rates)
    h = persist(res)
    print(f"\n=== PHASE 99 ({res.runtime_seconds}s) ===")
    m = res.headline_base
    if m.get("state") == "OK":
        print(f"\n[HEADLINE BASE] {m['start']}..{m['end']} ({m['n_months']} mo)")
        print(f"  Sharpe {m['sharpe']}  CAGR {m['cagr']:+.2%}  vol {m['ann_vol']:.2%}  maxDD {m['max_drawdown']:+.2%}  "
              f"hit {m['monthly_hit_rate']:.0%}  positive yrs {m['positive_years']}/{m['n_years']}")
        print(f"  ADVERSE Sharpe {res.headline_adverse.get('sharpe')}")
        print(f"  per year: {m['per_year_return']}")
    h1, h2 = res.halves.get("first_half", {}), res.halves.get("second_half", {})
    print(f"  halves Sharpe: {h1.get('sharpe')} -> {h2.get('sharpe')}")
    c = res.controls
    print(f"\nrandom-currency placebo: real pct {c['random_currency_placebo'].get('real_percentile')}")
    print(f"g10 basket benchmark Sharpe: {c['g10_basket_benchmark']['metrics'].get('sharpe')}")
    print(f"cost ladder: {c['cost_ladder']}")
    cb = res.combine_with_crypto_carry
    print(f"\ncombine w/ crypto carry: corr {cb.get('correlation')}  "
          f"crypto alone Sharpe {cb.get('crypto_carry_alone', {}).get('sharpe')}  "
          f"blend Sharpe {cb.get('vol_parity_blend', {}).get('sharpe')}  improves={cb.get('blend_improves_sharpe')}")
    print(f"\nVERDICT: {res.verdict}\n  {res.verdict_reason}")
    print(f"determinism match: {res.determinism['match']}")
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "DESIGN_NOTE", "G10", "fetch_g10_rates", "get_g10_rates",
    "build_monthly_total_returns", "run_fx_carry", "random_currency_placebo", "g10_basket_benchmark",
    "cost_ladder", "combine_with_crypto_carry", "classify_fx_carry", "run", "persist", "get_result", "main",
]
