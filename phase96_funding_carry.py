# -*- coding: utf-8 -*-
"""
Phase 96 -- Crypto Perpetual Funding-Rate Carry (delta-neutral).

The second strategy phase of the swing pivot. Phase 95 found no confirmed
momentum edge (FX/metals momentum negative; crypto momentum decayed and
does not separate from a random-sign placebo). Its ONE positive
by-product was that the short-perp legs kept *collecting* funding -- which
is the thesis of this phase, tested directly and pre-registered, with no
parameter fitting:

    Long 1 unit of crypto SPOT, short 1 unit of the same coin's
    PERPETUAL future. The two price legs cancel (delta-neutral); the
    position earns the funding rate that longs pay shorts. In crypto's
    normal (contango / bullish) regime funding is positive ~85% of the
    time. Does harvesting it produce a positive, cost-surviving,
    out-of-sample return -- AND does it still look attractive once the
    real risk (an exchange-collapse / counterparty tail, FTX-style) is
    priced in?

Frozen design, fixed BEFORE any result and never tuned / per-coin
optimised / best-of selected:

  * Weekly bars (Friday-anchored). Universe: the 27-coin Phase-94 crypto
    set that has BOTH a Binance spot pair and a Binance USD-M perpetual.
  * Per coin per week, the carry P&L on allocated capital is
        gross = (spot_ret - perp_ret) + funding_received
    where ``spot_ret - perp_ret`` is the basis-convergence term (measured
    from REAL perp prices ingested here, not assumed zero) and
    ``funding_received`` is the actual weekly-summed Binance funding rate
    (short receives it when funding > 0). Costs are charged on both legs
    on entry and exit.
  * Signal: trailing 4-week mean funding, annualised. Enter a coin's
    carry when that exceeds +3% annualised; exit when it falls to <= 0.
    Positive-carry only -- the reverse trade (short spot / long perp on
    persistently NEGATIVE funding) needs spot borrow and is NOT
    retail-accessible, so it is excluded and disclosed.
  * Sizing: equal weight across eligible coins, each capped at 15% of the
    book, at most 15 concurrent positions (a capacity cap, predeclared);
    if more coins qualify, the 15 with the highest trailing funding are
    taken. No leverage. Unallocated capital earns 0.
  * Weekly rebalance.
  * Costs: per-coin one-way spread/slippage in bps of notional traded,
    per leg (spot + perp), on turnover; ladder ZERO/BASE/ADVERSE/SEVERE
    = 0/1/2/4x.

Tail treatment (the centrepiece, not an afterthought): an
exchange-collapse Monte-Carlo. With annual probability p the ENTIRE
deployed carry notional takes a one-off -sev haircut in a random week;
the strategy's return / Sharpe / drawdown distribution is recomputed over
a (p, sev) grid, plus a deterministic worst-case (collapse at the single
worst week). A carry book that only looks good if the exchange never
fails is reported as such.

Read-only research. Perp OHLCV ingestion is free Binance data, the same
provenance discipline as Phase 74/94. No execution, no broker
transmission, no account mutation, no risk-engine import. Frozen Phase-74
Gold holdout never read -- ``frozen_contract_hash`` cites the hard-coded
canonical constant.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase94_swing_data_foundation as p94

SCHEMA_VERSION = "phase96.1"
ARTIFACT_KEY = "phase96_funding_carry"

# ==========================================================================
# Universe (from Phase 94's completed data foundation)
# ==========================================================================
CRYPTO_BASES: Tuple[str, ...] = p94.CRYPTO_UNIVERSE                       # 27
SPOT_ASSET = lambda b: f"{b}USD"                                          # Phase-94 spot key
PERP_ASSET = lambda b: f"{b}PERP"                                        # ingested here


# ==========================================================================
# Frozen strategy parameters -- chosen from standard carry practice BEFORE
# any result; never tuned, never per-coin, never "best-of".
# ==========================================================================
_FUNDING_LOOKBACK_WEEKS = 4                 # trailing signal window
_ENTRY_THRESHOLD_ANN = 0.03                 # enter carry when trailing ann. funding > +3%
_EXIT_THRESHOLD_ANN = 0.0                   # exit when it falls to <= 0
_MAX_POSITIONS = 15                         # capacity cap (predeclared)
_MAX_WEIGHT = 0.15                          # per-coin cap of the book
_REBALANCE_WEEKS = 1
_WARMUP_WEEKS = 8                           # need the trailing-4w signal + a little history
_WEEKS_PER_YEAR = 52.0

# one-way transaction cost, bps of notional traded, PER LEG (spot and perp each)
_SPOT_COST_BPS: Dict[str, float] = {}
_PERP_COST_BPS: Dict[str, float] = {}
for _b in CRYPTO_BASES:
    major = _b in ("BTC", "ETH")
    _SPOT_COST_BPS[_b] = 5.0 if major else 10.0
    _PERP_COST_BPS[_b] = 3.0 if major else 6.0      # perps are typically tighter than spot
_COST_LADDER: Dict[str, float] = {"ZERO": 0.0, "BASE": 1.0, "ADVERSE": 2.0, "SEVERE": 4.0}

# predeclared sensitivity neighbourhood (reported, never selected from)
_THRESHOLD_NEIGHBOURHOOD_ANN: Tuple[float, ...] = (0.02, 0.03, 0.05)

# exchange-collapse Monte-Carlo grid
_TAIL_ANNUAL_PROB: Tuple[float, ...] = (0.01, 0.02, 0.05, 0.10)
_TAIL_SEVERITY: Tuple[float, ...] = (0.30, 0.50, 1.00)
_TAIL_MC_PATHS = 4000
_TAIL_MC_SEED = 96001
_ELIG_PLACEBO_REPS = 300
_ELIG_PLACEBO_SEED = 96501

DESIGN_NOTE: Dict[str, Any] = {
    "question": "Does delta-neutral crypto funding carry (long spot / short perp) earn a positive "
                "cost-surviving OOS return, and does it survive an exchange-collapse tail?",
    "position": "long 1u spot + short 1u perp per eligible coin; delta-neutral; no leverage",
    "weekly_pnl": "(spot_ret - perp_ret) + weekly_summed_funding_received - costs; "
                  "spot_ret-perp_ret is the REAL measured basis term (perp prices ingested here)",
    "signal": "trailing 4-week mean funding, annualised (weekly_sum * 52)",
    "entry": "trailing annualised funding > +0.03; exit when <= 0.0; positive-carry only",
    "sizing": "equal weight eligible, per-coin cap 15% of book, <=15 concurrent (highest-funding "
              "coins if more qualify); no leverage; idle capital earns 0",
    "rebalance": "weekly",
    "costs": "per-coin one-way bps PER LEG (spot 5/10, perp 3/6) on turnover; ladder 0/1/2/4x",
    "excluded": "reverse carry (short spot / long perp on negative funding) -- needs spot borrow, "
                "not retail-accessible",
    "tail": "exchange-collapse Monte-Carlo over annual-prob x severity grid + deterministic worst week",
    "no_fitting": "every parameter frozen before results; threshold neighbourhood reported, never selected",
    "holdout": "frozen Phase-74 Gold holdout never read; frozen_contract_hash cites the canonical constant",
}


def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


# ==========================================================================
# Perp OHLCV ingestion (free Binance USD-M data; Phase-74/94 discipline)
# ==========================================================================
@dataclass
class IngestOutcome:
    asset: str
    ok: bool
    detail: str = ""
    received: int = 0
    stored: int = 0
    first_iso: Optional[str] = None
    last_iso: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def ingest_perp_ohlcv(bases: Tuple[str, ...] = CRYPTO_BASES) -> List[IngestOutcome]:
    """Binance USD-M perpetual daily klines -> stored as ``<BASE>PERP`` / 1d.
    Reuses Phase 94's paginated kline fetcher (``spot=False``). Idempotent."""
    out: List[IngestOutcome] = []
    for b in bases:
        asset = PERP_ASSET(b)
        try:
            candles = p94._binance_daily_klines(b, spot=False)
            if not candles:
                out.append(IngestOutcome(asset, False, "NO_DATA_RETURNED"))
                continue
            rep = store.upsert_candles(asset, "1d", candles, source="binance_fapi",
                                       source_revision="fapi/v1/klines interval=1d")
            cov = store.get_coverage(asset, "1d")
            out.append(IngestOutcome(
                asset, True, f"rejected={rep.rejected}", received=rep.received,
                stored=rep.inserted + rep.updated,
                first_iso=(datetime.fromtimestamp(cov.first_open_time, tz=timezone.utc).isoformat()
                           if cov.first_open_time else None),
                last_iso=(datetime.fromtimestamp(cov.last_open_time, tz=timezone.utc).isoformat()
                          if cov.last_open_time else None)))
        except Exception as e:  # pragma: no cover - network dependent
            out.append(IngestOutcome(asset, False, f"ERROR: {e!r}"[:300]))
    return out


def perp_data_ready(bases: Tuple[str, ...] = CRYPTO_BASES) -> Dict[str, Any]:
    ready, missing = [], []
    for b in bases:
        cov = store.get_coverage(PERP_ASSET(b), "1d")
        (ready if (cov.count or 0) >= 200 else missing).append(b)
    return {"n_ready": len(ready), "n_missing": len(missing), "missing": missing}


# ==========================================================================
# Weekly panels: spot close, perp close, weekly-summed funding
# ==========================================================================
_PANEL_CACHE: Dict[str, pd.DataFrame] = {}


def _weekly_close(asset: str) -> pd.Series:
    candles = store.get_candles(asset, "1d")
    if not candles:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([c["time"] for c in candles], unit="s", utc=True)
    s = pd.Series([float(c["close"]) for c in candles], index=idx).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s[s > 0].resample("W-FRI").last()


def _weekly_funding(base: str) -> pd.Series:
    fd = p94.get_funding_daily(SPOT_ASSET(base))
    if not fd or not fd.get("daily_summed_funding_rate"):
        return pd.Series(dtype=float)
    rows = fd["daily_summed_funding_rate"]
    idx = pd.to_datetime([int(r[0]) for r in rows], unit="s", utc=True)
    s = pd.Series([float(r[1]) for r in rows], index=idx).sort_index()
    return s.resample("W-FRI").sum()


def build_panels(bases: Tuple[str, ...] = CRYPTO_BASES) -> Dict[str, pd.DataFrame]:
    """{'spot','perp','funding'} weekly DataFrames, columns = bases, common
    Friday index. Cached for the process life (read-only daily store)."""
    key = "|".join(bases)
    if key in _PANEL_CACHE:
        return _PANEL_CACHE[key]
    spot = pd.DataFrame({b: _weekly_close(SPOT_ASSET(b)) for b in bases}).sort_index()
    perp = pd.DataFrame({b: _weekly_close(PERP_ASSET(b)) for b in bases}).sort_index()
    funding = pd.DataFrame({b: _weekly_funding(b) for b in bases}).sort_index()
    idx = spot.index.union(perp.index).union(funding.index)
    out = {"spot": spot.reindex(idx), "perp": perp.reindex(idx),
           "funding": funding.reindex(idx)}
    _PANEL_CACHE[key] = out
    return out


# ==========================================================================
# Core: the frozen carry backtest
# ==========================================================================
def _signal_matrix(funding: pd.DataFrame) -> np.ndarray:
    """Trailing 4-week mean weekly funding, annualised (x52). Causal:
    row t uses funding[t-3..t]. NaN until the window is full."""
    f = funding.to_numpy(float)
    T, N = f.shape
    sig = np.full((T, N), np.nan)
    for t in range(_FUNDING_LOOKBACK_WEEKS - 1, T):
        win = f[t - _FUNDING_LOOKBACK_WEEKS + 1: t + 1]
        cnt = np.isfinite(win).sum(axis=0)
        with np.errstate(invalid="ignore"):
            mean = np.where(cnt > 0, np.nansum(win, axis=0) / np.maximum(cnt, 1), np.nan)
        sig[t] = mean * _WEEKS_PER_YEAR
    return sig


def _eligibility(signal_row: np.ndarray, held_prev: np.ndarray,
                 entry_thr: float = _ENTRY_THRESHOLD_ANN) -> np.ndarray:
    """Enter when trailing ann. funding > entry threshold; once in, stay in
    until it drops to <= exit threshold (hysteresis). NaN signal -> not eligible."""
    enter = np.isfinite(signal_row) & (signal_row > entry_thr)
    stay = held_prev & np.isfinite(signal_row) & (signal_row > _EXIT_THRESHOLD_ANN)
    elig = enter | stay
    if elig.sum() > _MAX_POSITIONS:
        # capacity cap: keep the highest-trailing-funding names
        order = np.argsort(np.where(elig, -signal_row, np.inf))
        keep = np.zeros_like(elig)
        keep[order[:_MAX_POSITIONS]] = True
        elig = elig & keep
    return elig


def _target_weights(elig: np.ndarray) -> np.ndarray:
    n = int(elig.sum())
    if n == 0:
        return np.zeros_like(elig, dtype=float)
    w = min(1.0 / n, _MAX_WEIGHT)
    return elig.astype(float) * w


def run_carry(bases: Tuple[str, ...] = CRYPTO_BASES, cost_key: str = "BASE",
              entry_threshold_ann: float = _ENTRY_THRESHOLD_ANN,
              rebalance_weeks: int = _REBALANCE_WEEKS) -> Dict[str, Any]:
    """The frozen weekly carry book. Returns the weekly net-return series
    and a full decomposition (funding vs basis vs cost)."""
    panels = build_panels(bases)
    spot, perp, funding = panels["spot"], panels["perp"], panels["funding"]
    S, P, F = spot.to_numpy(float), perp.to_numpy(float), funding.to_numpy(float)
    T, N = S.shape
    idx = spot.index

    spot_bps = np.array([_SPOT_COST_BPS[b] for b in bases]) * 1e-4 * _COST_LADDER[cost_key]
    perp_bps = np.array([_PERP_COST_BPS[b] for b in bases]) * 1e-4 * _COST_LADDER[cost_key]

    sig = _signal_matrix(funding)
    spot_ret = np.full((T, N), np.nan)
    perp_ret = np.full((T, N), np.nan)
    spot_ret[:-1] = S[1:] / S[:-1] - 1.0
    perp_ret[:-1] = P[1:] / P[:-1] - 1.0
    fwd_funding = np.full((T, N), np.nan)
    fwd_funding[:-1] = F[1:]

    held = np.zeros(N, dtype=bool)
    prev_w = np.zeros(N)
    net, fund_c, basis_c, cost_c, n_pos, deployed = [], [], [], [], [], []
    for t in range(T):
        if t % rebalance_weeks == 0:
            elig = _eligibility(sig[t], held, entry_threshold_ann)
            w = _target_weights(elig)
            held = elig
        else:
            w = prev_w
        ok = np.isfinite(spot_ret[t]) & np.isfinite(perp_ret[t])
        w_eff = np.where(ok, w, 0.0)

        basis = np.sum(w_eff * (np.nan_to_num(spot_ret[t]) - np.nan_to_num(perp_ret[t])))
        fnd = np.sum(w_eff * np.where(np.isfinite(fwd_funding[t]), fwd_funding[t], 0.0))
        dspot = np.abs(w_eff - prev_w)   # both legs move together; charge per leg
        cost = float(np.sum(dspot * spot_bps) + np.sum(dspot * perp_bps))

        net.append(float(basis + fnd - cost))
        fund_c.append(float(fnd)); basis_c.append(float(basis)); cost_c.append(float(-cost))
        n_pos.append(int((w_eff > 0).sum())); deployed.append(float(np.sum(w_eff)))
        prev_w = w_eff
    return {
        "index": idx, "net": np.array(net), "funding": np.array(fund_c),
        "basis": np.array(basis_c), "cost": np.array(cost_c),
        "n_positions": np.array(n_pos), "deployed": np.array(deployed),
        "signal": sig, "spot_ret": spot_ret, "perp_ret": perp_ret, "fwd_funding": fwd_funding,
        "cost_key": cost_key,
    }


# ==========================================================================
# Metrics
# ==========================================================================
def _metrics(net: np.ndarray, index: pd.DatetimeIndex, warmup: int = _WARMUP_WEEKS,
             extra: Optional[Dict[str, np.ndarray]] = None) -> Dict[str, Any]:
    n = np.asarray(net, float)[warmup:]
    ix = index[warmup:]
    keep = np.isfinite(n)
    n, ix = n[keep], ix[keep]
    if n.size < 26:
        return {"state": "INSUFFICIENT_SAMPLE", "n_weeks": int(n.size)}
    equity = np.cumprod(1.0 + n)
    years = n.size / _WEEKS_PER_YEAR
    cagr = float(equity[-1] ** (1.0 / years) - 1.0) if equity[-1] > 0 else -1.0
    sd = float(n.std(ddof=1))
    vol = sd * np.sqrt(_WEEKS_PER_YEAR)
    sharpe = float(n.mean() / sd * np.sqrt(_WEEKS_PER_YEAR)) if sd > 0 else 0.0
    rmax = np.maximum.accumulate(equity)
    dd = equity / rmax - 1.0
    max_dd = float(dd.min())
    md = cur = 0
    for u in (dd < 0):
        cur = cur + 1 if u else 0
        md = max(md, cur)
    ser = pd.Series(n, index=ix)
    monthly = (1.0 + ser).resample("ME").prod() - 1.0
    yearly = (1.0 + ser).resample("YE").prod() - 1.0
    out = {
        "state": "OK", "n_weeks": int(n.size), "start": ix[0].date().isoformat(),
        "end": ix[-1].date().isoformat(),
        "cagr": round(cagr, 4), "ann_vol": round(vol, 4), "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd, 4), "max_dd_weeks": int(md),
        "calmar": round(cagr / abs(max_dd), 3) if max_dd < 0 else None,
        "monthly_hit_rate": round(float((monthly > 0).mean()), 3) if monthly.size else None,
        "weekly_skew": round(float(pd.Series(n).skew()), 3),
        "weekly_kurtosis": round(float(pd.Series(n).kurtosis()), 3),
        "worst_week": round(float(n.min()), 4), "best_week": round(float(n.max()), 4),
        "p01_week": round(float(np.percentile(n, 1)), 4),
        "total_return": round(float(equity[-1] - 1.0), 4),
        "per_year_return": {str(k.year): round(float(v), 4) for k, v in yearly.items()},
        "positive_years": int((yearly > 0).sum()), "n_years": int(yearly.size),
    }
    if extra is not None:
        for k in ("funding", "basis", "cost"):
            arr = np.asarray(extra.get(k, []), float)[warmup:]
            arr = arr[np.isfinite(arr)]
            out[f"ann_{k}"] = round(float(arr.sum() / years), 4) if arr.size else None
        npos = np.asarray(extra.get("n_positions", []), float)[warmup:]
        dep = np.asarray(extra.get("deployed", []), float)[warmup:]
        out["avg_n_positions"] = round(float(np.nanmean(npos)), 1) if npos.size else None
        out["avg_capital_deployed"] = round(float(np.nanmean(dep)), 3) if dep.size else None
    return out


def _half_split(net: np.ndarray, index: pd.DatetimeIndex, warmup: int = _WARMUP_WEEKS) -> Dict[str, Any]:
    n = np.asarray(net, float)
    live = np.arange(warmup, n.size)
    if live.size < 104:
        return {"state": "INSUFFICIENT_SAMPLE"}
    mid = warmup + live.size // 2
    a = np.full_like(n, np.nan); a[warmup:mid] = n[warmup:mid]
    b = np.full_like(n, np.nan); b[mid:] = n[mid:]
    return {"first_half": _metrics(a, index, warmup=warmup),
            "second_half": _metrics(b, index, warmup=mid)}


# ==========================================================================
# Controls
# ==========================================================================
def random_eligibility_placebo(reps: int = _ELIG_PLACEBO_REPS, seed: int = _ELIG_PLACEBO_SEED,
                               cost_key: str = "BASE") -> Dict[str, Any]:
    """Each week, pick the SAME NUMBER of coins as the real strategy holds,
    but at random from those with valid data. Collect their realised
    funding - basis - cost. Does signal-based selection beat random
    selection?"""
    real = run_carry(cost_key=cost_key)
    real_sharpe = _metrics(real["net"], real["index"]).get("sharpe")
    panels = build_panels()
    spot_ret, perp_ret, fwd_funding = real["spot_ret"], real["perp_ret"], real["fwd_funding"]
    T, N = spot_ret.shape
    real_npos = real["n_positions"]
    spot_bps = np.array([_SPOT_COST_BPS[b] for b in CRYPTO_BASES]) * 1e-4 * _COST_LADDER[cost_key]
    perp_bps = np.array([_PERP_COST_BPS[b] for b in CRYPTO_BASES]) * 1e-4 * _COST_LADDER[cost_key]
    leg = spot_bps + perp_bps
    rng = np.random.default_rng(seed)
    sharpes = []
    for _ in range(reps):
        prev_w = np.zeros(N)
        net = []
        for t in range(T):
            ok = np.isfinite(spot_ret[t]) & np.isfinite(perp_ret[t])
            avail = np.where(ok)[0]
            k = min(int(real_npos[t]), avail.size)
            w = np.zeros(N)
            if k > 0:
                pick = rng.choice(avail, size=k, replace=False)
                w[pick] = min(1.0 / k, _MAX_WEIGHT)
            basis = np.sum(w * (np.nan_to_num(spot_ret[t]) - np.nan_to_num(perp_ret[t])))
            fnd = np.sum(w * np.where(np.isfinite(fwd_funding[t]), fwd_funding[t], 0.0))
            cost = float(np.sum(np.abs(w - prev_w) * leg))
            net.append(basis + fnd - cost)
            prev_w = w
        s = _metrics(np.array(net), panels["spot"].index).get("sharpe")
        if s is not None:
            sharpes.append(s)
    arr = np.array(sharpes)
    if real_sharpe is None or arr.size == 0:
        return {"state": "INSUFFICIENT_SAMPLE"}
    return {"real_sharpe": round(real_sharpe, 3), "placebo_mean_sharpe": round(float(arr.mean()), 3),
            "placebo_p95_sharpe": round(float(np.percentile(arr, 95)), 3),
            "real_percentile": round(float((arr <= real_sharpe).mean()), 4),
            "empirical_p_one_sided": round(float((arr >= real_sharpe).mean()), 4),
            "n_reps": int(arr.size), "seed": seed}


def funding_persistence() -> Dict[str, Any]:
    """Does trailing 4-week funding predict next-week funding? The core
    assumption. Pooled and per-coin lag-1 correlation of the annualised
    trailing signal with the realised forward weekly funding (annualised)."""
    panels = build_panels()
    funding = panels["funding"]
    sig = _signal_matrix(funding)
    fwd = np.full_like(sig, np.nan)
    fwd[:-1] = funding.to_numpy(float)[1:] * _WEEKS_PER_YEAR
    per_coin = {}
    all_x, all_y = [], []
    for j, b in enumerate(CRYPTO_BASES):
        x, y = sig[:, j], fwd[:, j]
        m = np.isfinite(x) & np.isfinite(y)
        if m.sum() >= 52:
            c = float(np.corrcoef(x[m], y[m])[0, 1])
            per_coin[b] = round(c, 3)
            all_x.append(x[m]); all_y.append(y[m])
    pooled = None
    if all_x:
        X, Y = np.concatenate(all_x), np.concatenate(all_y)
        pooled = float(np.corrcoef(X, Y)[0, 1])
    return {"pooled_corr": round(pooled, 3) if pooled is not None else None,
            "per_coin_corr": per_coin,
            "median_per_coin": round(float(np.median(list(per_coin.values()))), 3) if per_coin else None,
            "n_coin_positive": int(sum(1 for v in per_coin.values() if v > 0))}


def basis_attribution(cost_key: str = "BASE") -> Dict[str, Any]:
    """Decompose the realised carry return into the funding component and
    the basis-convergence component (spot_ret - perp_ret), pooled and
    annualised. If basis is a big negative drag, the headline funding
    number overstates the edge."""
    r = run_carry(cost_key=cost_key)
    w = _WARMUP_WEEKS
    yrs = (len(r["net"]) - w) / _WEEKS_PER_YEAR
    tot = float(np.nansum(r["net"][w:]))
    fnd = float(np.nansum(r["funding"][w:]))
    bas = float(np.nansum(r["basis"][w:]))
    cst = float(np.nansum(r["cost"][w:]))
    return {"ann_total_return": round(tot / yrs, 4), "ann_funding": round(fnd / yrs, 4),
            "ann_basis": round(bas / yrs, 4), "ann_cost": round(cst / yrs, 4),
            "funding_share_of_gross": round(fnd / (fnd + bas), 3) if (fnd + bas) != 0 else None,
            "basis_is_net_drag": bas < 0}


def delta_neutrality_check(cost_key: str = "BASE") -> Dict[str, Any]:
    """Regress weekly carry P&L on (a) the equal-weight crypto basket
    weekly return and (b) BTC weekly return. Betas should be ~0 for a
    genuinely delta-neutral book."""
    r = run_carry(cost_key=cost_key)
    panels = build_panels()
    spot = panels["spot"]
    basket_ret = spot.pct_change().mean(axis=1).to_numpy(float)
    btc_ret = spot["BTC"].pct_change().to_numpy(float)
    y = r["net"]
    fwd_basket = np.r_[basket_ret[1:], np.nan]
    fwd_btc = np.r_[btc_ret[1:], np.nan]
    out = {}
    for name, x in (("crypto_basket", fwd_basket), ("btc", fwd_btc)):
        m = np.isfinite(x) & np.isfinite(y)
        m[:_WARMUP_WEEKS] = False
        if m.sum() < 52:
            out[name] = {"state": "INSUFFICIENT_SAMPLE"}
            continue
        beta, alpha = np.polyfit(x[m], y[m], 1)
        corr = float(np.corrcoef(x[m], y[m])[0, 1])
        out[name] = {"beta": round(float(beta), 4), "weekly_alpha": round(float(alpha), 5),
                     "corr": round(corr, 3)}
    out["interpretation"] = "|beta| well under ~0.15 and |corr| under ~0.2 is consistent with a "
    out["interpretation"] += "delta-neutral book; larger values mean residual directional exposure."
    return out


def cost_ladder() -> Dict[str, Any]:
    out = {}
    for k in _COST_LADDER:
        m = _metrics(run_carry(cost_key=k)["net"], build_panels()["spot"].index)
        out[k] = {"sharpe": m.get("sharpe"), "cagr": m.get("cagr")}
    return out


def threshold_neighbourhood() -> Dict[str, Any]:
    out = {}
    for thr in _THRESHOLD_NEIGHBOURHOOD_ANN:
        r = run_carry(cost_key="BASE", entry_threshold_ann=thr)
        m = _metrics(r["net"], r["index"], extra=r)
        out[f"ann_{thr:.2f}"] = {"threshold_ann": thr, "sharpe": m.get("sharpe"), "cagr": m.get("cagr"),
                                 "avg_n_positions": m.get("avg_n_positions")}
    return {"by_threshold": out, "note": "ann_0.03 is the pre-registered design; the others are "
            "reported for sensitivity only and are never selected from."}


# ==========================================================================
# The tail: exchange-collapse Monte-Carlo
# ==========================================================================
def exchange_collapse_stress(cost_key: str = "BASE", paths: int = _TAIL_MC_PATHS,
                             seed: int = _TAIL_MC_SEED) -> Dict[str, Any]:
    """With annual probability p, the capital DEPLOYED in the carry book at
    the moment of an exchange failure suffers a one-off -sev haircut in a
    uniformly-random week (sev=1.0 = total loss of deployed capital;
    sev=0.5 = half). Recompute the return / Sharpe / total-return
    distribution over the (p, sev) grid; plus a deterministic worst case
    (collapse on the single most damaging week). The MEDIAN is not the
    headline -- a rare catastrophe leaves the median path untouched by
    construction; the p05 / p01 / prob-of-ending-negative columns are the
    point."""
    r = run_carry(cost_key=cost_key)
    w = _WARMUP_WEEKS
    net = r["net"][w:]
    exposure = r["deployed"][w:]                # capital committed to carry at the venue
    idx = r["index"][w:]
    T = net.size
    base_metrics = _metrics(r["net"], r["index"], extra=r)
    rng = np.random.default_rng(seed)

    grid = {}
    for p in _TAIL_ANNUAL_PROB:
        hazard = p / _WEEKS_PER_YEAR
        for sev in _TAIL_SEVERITY:
            sharpes = np.empty(paths)
            totrets = np.empty(paths)
            n_hits = np.empty(paths)
            for k in range(paths):
                hit = rng.random(T) < hazard
                n_hits[k] = hit.sum()
                shocked = net.copy()
                shocked[hit] = shocked[hit] - sev * exposure[hit]
                eq = np.cumprod(np.clip(1.0 + shocked, 1e-9, None))
                sd = shocked.std(ddof=1)
                sharpes[k] = shocked.mean() / sd * np.sqrt(_WEEKS_PER_YEAR) if sd > 0 else 0.0
                totrets[k] = eq[-1] - 1.0
            grid[f"p{p:.2f}_sev{sev:.2f}"] = {
                "annual_prob": p, "severity": sev,
                "median_sharpe": round(float(np.median(sharpes)), 3),
                "p05_sharpe": round(float(np.percentile(sharpes, 5)), 3),
                "median_total_return": round(float(np.median(totrets)), 4),
                "mean_total_return": round(float(np.mean(totrets)), 4),
                "p05_total_return": round(float(np.percentile(totrets, 5)), 4),
                "p01_total_return": round(float(np.percentile(totrets, 1)), 4),
                "prob_total_return_negative": round(float((totrets < 0).mean()), 4),
                "prob_at_least_one_collapse": round(float((n_hits > 0).mean()), 4),
            }

    worst_total = worst_week = None
    for sev in _TAIL_SEVERITY:
        best = None
        for tt in range(T):
            shocked = net.copy()
            shocked[tt] = shocked[tt] - sev * exposure[tt]
            tr = float(np.cumprod(np.clip(1.0 + shocked, 1e-9, None))[-1] - 1.0)
            if best is None or tr < best[0]:
                best = (tr, tt)
        if sev == 1.0:
            worst_total = round(best[0], 4)
            worst_week = idx[best[1]].date().isoformat()
    return {"base_no_tail": {"sharpe": base_metrics.get("sharpe"), "cagr": base_metrics.get("cagr"),
                             "total_return": base_metrics.get("total_return")},
            "grid": grid,
            "deterministic_worst_case": {"severity": 1.0, "total_return_if_full_loss_at_worst_week": worst_total,
                                         "worst_week": worst_week},
            "exposure_model": "haircut applies to deployed carry capital; sev=1.0 = total loss of it",
            "paths": paths, "seed": seed}


# ==========================================================================
# Per-coin breakdown
# ==========================================================================
def per_coin_breakdown(cost_key: str = "BASE") -> Dict[str, Any]:
    r = run_carry(cost_key=cost_key)
    spot_ret, perp_ret, fwd_funding, sig = r["spot_ret"], r["perp_ret"], r["fwd_funding"], r["signal"]
    T, N = spot_ret.shape
    # reconstruct per-coin weight path
    held = np.zeros(N, dtype=bool)
    contrib = np.zeros(N)
    weeks_held = np.zeros(N)
    for t in range(T):
        elig = _eligibility(sig[t], held)
        held = elig
        w = _target_weights(elig)
        ok = np.isfinite(spot_ret[t]) & np.isfinite(perp_ret[t])
        w = np.where(ok, w, 0.0)
        step = w * (np.nan_to_num(spot_ret[t]) - np.nan_to_num(perp_ret[t])
                    + np.where(np.isfinite(fwd_funding[t]), fwd_funding[t], 0.0))
        contrib += np.nan_to_num(step)
        weeks_held += (w > 0)
    out = {b: {"total_contribution": round(float(contrib[j]), 4), "weeks_held": int(weeks_held[j])}
           for j, b in enumerate(CRYPTO_BASES)}
    ranked = sorted(out.items(), key=lambda kv: kv[1]["total_contribution"], reverse=True)
    return {"per_coin": out, "top5": [k for k, _ in ranked[:5]], "bottom5": [k for k, _ in ranked[-5:]]}


# ==========================================================================
# Verdicts (frozen decision rules)
# ==========================================================================
_VALID_EDGE = ("FUNDING_CARRY_EDGE_CONFIRMED", "FUNDING_CARRY_EDGE_PROMISING",
               "FUNDING_CARRY_EDGE_NOT_ESTABLISHED", "FUNDING_CARRY_EDGE_NEGATIVE")
_VALID_TAIL = ("FUNDING_CARRY_SURVIVES_TAIL_YES", "FUNDING_CARRY_SURVIVES_TAIL_MARGINAL",
               "FUNDING_CARRY_SURVIVES_TAIL_NO")


def classify_edge(base_metrics: Dict[str, Any], adverse_metrics: Dict[str, Any],
                  placebo: Dict[str, Any], persistence: Dict[str, Any],
                  neutrality: Dict[str, Any]) -> Tuple[str, str]:
    if base_metrics.get("state") != "OK":
        return "FUNDING_CARRY_EDGE_NOT_ESTABLISHED", "Insufficient sample."
    sharpe = base_metrics.get("sharpe") or 0.0
    adv = adverse_metrics.get("sharpe") if adverse_metrics.get("state") == "OK" else None
    pctl = placebo.get("real_percentile")
    pooled_corr = persistence.get("pooled_corr")
    pos_years = base_metrics.get("positive_years", 0)
    n_years = base_metrics.get("n_years", 0)
    year_frac = pos_years / n_years if n_years else 0.0
    btc_beta = abs((neutrality.get("btc", {}) or {}).get("beta", 1.0))

    if sharpe < 0.0:
        return "FUNDING_CARRY_EDGE_NEGATIVE", f"Net Sharpe {sharpe} negative after BASE costs."
    if (sharpe >= 1.0 and pctl is not None and pctl >= 0.95 and pooled_corr is not None
            and pooled_corr >= 0.2 and year_frac >= 0.80 and adv is not None and adv >= 0.5
            and btc_beta < 0.15):
        return "FUNDING_CARRY_EDGE_CONFIRMED", (
            f"Net Sharpe {sharpe} (BASE), {adv} (ADVERSE); beats the random-eligibility placebo "
            f"(pctl {pctl}); trailing funding predicts forward funding (pooled corr {pooled_corr}); "
            f"positive in {pos_years}/{n_years} years; BTC beta {btc_beta:.3f} (delta-neutral).")
    if sharpe >= 0.5 and pctl is not None and pctl >= 0.90:
        return "FUNDING_CARRY_EDGE_PROMISING", (
            f"Net Sharpe {sharpe} (BASE) and above the 90th pct of the placebo ({pctl}), but does not "
            f"clear the full bar (Sharpe>=1.0, placebo>=0.95, persistence>=0.2 [{pooled_corr}], "
            f">=80% positive years [{year_frac:.2f}], ADVERSE Sharpe>=0.5 [{adv}], BTC beta<0.15 [{btc_beta:.3f}]).")
    return "FUNDING_CARRY_EDGE_NOT_ESTABLISHED", (
        f"Net Sharpe {sharpe} (BASE), placebo percentile {pctl}, pooled persistence {pooled_corr} -- "
        "does not clear the pre-registered bar.")


def classify_tail(stress: Dict[str, Any]) -> Tuple[str, str]:
    """Tail robustness is judged on the LOSS tail, not the median -- a rare
    catastrophe leaves the median path untouched by construction. Reference
    cell: 5%/yr collapse probability with a 50% haircut (a consensus
    crypto-counterparty estimate). Harsh cell: 10%/yr with total loss."""
    grid = stress.get("grid", {})
    cell = grid.get("p0.05_sev0.50")
    harsh = grid.get("p0.10_sev1.00")
    if not cell:
        return "FUNDING_CARRY_SURVIVES_TAIL_NO", "Stress grid missing the reference cell."
    p05 = cell.get("p05_total_return")
    mean_tr = cell.get("mean_total_return")
    prob_neg = cell.get("prob_total_return_negative")
    harsh_prob_neg = (harsh or {}).get("prob_total_return_negative")
    harsh_p05 = (harsh or {}).get("p05_total_return")

    survives_ref = (p05 is not None and p05 > 0.0 and prob_neg is not None and prob_neg <= 0.10)
    survives_harsh = (harsh_prob_neg is not None and harsh_prob_neg <= 0.25
                      and harsh_p05 is not None and harsh_p05 > -0.75)

    if survives_ref and survives_harsh:
        return "FUNDING_CARRY_SURVIVES_TAIL_YES", (
            f"At the reference cell (5%/yr collapse, 50% haircut) the 5th-percentile total return is "
            f"still positive ({p05}) and only {prob_neg:.0%} of paths end underwater; even the harsh "
            f"10%/yr total-loss cell keeps {harsh_prob_neg:.0%} ruin and a {harsh_p05} 5th percentile.")
    if survives_ref:
        return "FUNDING_CARRY_SURVIVES_TAIL_MARGINAL", (
            f"The reference cell holds up (5th-pct total return {p05}, ruin {prob_neg:.0%}), but the "
            f"harsh 10%/yr total-loss cell does not (ruin {harsh_prob_neg}, 5th pct {harsh_p05}). The "
            f"carry is fine under a modest counterparty tail and dangerous under an aggressive one.")
    if mean_tr is not None and mean_tr > 0.0 and prob_neg is not None and prob_neg <= 0.25:
        return "FUNDING_CARRY_SURVIVES_TAIL_MARGINAL", (
            f"At 5%/yr x 50% haircut the mean total return stays positive ({mean_tr}) but the 5th "
            f"percentile is {p05} and {prob_neg:.0%} of paths end underwater.")
    return "FUNDING_CARRY_SURVIVES_TAIL_NO", (
        f"At a plausible 5%/yr exchange-collapse probability with a 50% haircut the 5th-percentile "
        f"total return is {p05} and {prob_neg:.0%} of paths end underwater; the carry is not robust "
        f"to the counterparty tail.")


def classify_overall(edge: str, tail: str) -> str:
    if edge == "FUNDING_CARRY_EDGE_CONFIRMED" and tail == "FUNDING_CARRY_SURVIVES_TAIL_YES":
        return "PROFITABLE_SWING_EDGE_FOUND"
    if edge in ("FUNDING_CARRY_EDGE_CONFIRMED", "FUNDING_CARRY_EDGE_PROMISING") and \
       tail in ("FUNDING_CARRY_SURVIVES_TAIL_YES", "FUNDING_CARRY_SURVIVES_TAIL_MARGINAL"):
        return "PROFITABLE_SWING_EDGE_PROMISING"
    return "PROFITABLE_SWING_EDGE_NOT_ESTABLISHED"


# ==========================================================================
# Result container
# ==========================================================================
@dataclass
class Phase96Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    design_note: Dict[str, Any]
    universe: List[str]
    perp_ingestion: List[Dict[str, Any]]
    perp_data_ready: Dict[str, Any]
    headline_base: Dict[str, Any]
    headline_adverse: Dict[str, Any]
    halves: Dict[str, Any]
    controls: Dict[str, Any]
    per_coin_breakdown: Dict[str, Any]
    tail_stress: Dict[str, Any]
    edge_verdict: str
    edge_reason: str
    tail_verdict: str
    tail_reason: str
    overall_verdict: str
    determinism: Dict[str, Any]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True
    live_automation_enabled: bool = False
    live_broker_transmission: str = "BLOCKED"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _strip_private(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_private(v) for k, v in obj.items() if not k.startswith("_")
                and not isinstance(v, (np.ndarray, pd.Index))}
    if isinstance(obj, list):
        return [_strip_private(v) for v in obj]
    return obj


def run(do_ingest: bool = True) -> Phase96Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()

    ingestion: List[Dict[str, Any]] = []
    if do_ingest:
        ready = perp_data_ready()
        if ready["n_missing"] > 0:
            ingestion = [o.to_dict() for o in ingest_perp_ohlcv()]
            _PANEL_CACHE.clear()
    ready = perp_data_ready()

    base = run_carry(cost_key="BASE")
    adverse = run_carry(cost_key="ADVERSE")
    idx = base["index"]
    headline_base = _metrics(base["net"], idx, extra=base)
    headline_adverse = _metrics(adverse["net"], idx, extra=adverse)
    halves = _half_split(base["net"], idx)

    placebo = random_eligibility_placebo()
    persistence = funding_persistence()
    attribution = basis_attribution()
    neutrality = delta_neutrality_check()
    ladder = cost_ladder()
    thr_nbhd = threshold_neighbourhood()
    controls = {
        "random_eligibility_placebo": placebo,
        "funding_persistence": persistence,
        "basis_attribution": attribution,
        "delta_neutrality_check": neutrality,
        "cost_ladder": ladder,
        "threshold_neighbourhood": thr_nbhd,
    }
    pcb = per_coin_breakdown()
    tail = exchange_collapse_stress()

    edge_v, edge_r = classify_edge(headline_base, headline_adverse, placebo, persistence, neutrality)
    tail_v, tail_r = classify_tail(tail)
    overall = classify_overall(edge_v, tail_v)

    d1 = _metrics(run_carry(cost_key="BASE")["net"], idx)
    d2 = _metrics(run_carry(cost_key="BASE")["net"], idx)
    determinism_match = (json.dumps(d1, sort_keys=True, default=str)
                         == json.dumps(d2, sort_keys=True, default=str))

    payload = _strip_private({"headline_base": headline_base, "headline_adverse": headline_adverse,
                              "controls": controls, "tail": tail, "edge": edge_v, "tail_v": tail_v,
                              "overall": overall})
    chash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase96Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        design_note=DESIGN_NOTE, universe=list(CRYPTO_BASES),
        perp_ingestion=ingestion, perp_data_ready=ready,
        headline_base=headline_base, headline_adverse=headline_adverse, halves=halves,
        controls=_strip_private(controls), per_coin_breakdown=pcb, tail_stress=tail,
        edge_verdict=edge_v, edge_reason=edge_r, tail_verdict=tail_v, tail_reason=tail_r,
        overall_verdict=overall, determinism={"match": determinism_match},
        runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase96Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase96_funding_carry", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("Phase 96 - crypto perpetual funding-rate carry ...", flush=True)
    res = run()
    h = persist(res)   # persist first -- verbose printing must never lose the artifact
    print(f"\n=== PHASE 96 ({res.runtime_seconds}s) ===")
    print(f"perp data ready: {res.perp_data_ready}")
    m = res.headline_base
    if m.get("state") == "OK":
        print(f"\n[HEADLINE BASE]  {m['start']} -> {m['end']}  ({m['n_weeks']} wk)")
        print(f"  Sharpe {m['sharpe']:+.2f}  CAGR {m['cagr']:+.2%}  vol {m['ann_vol']:.2%}  "
              f"maxDD {m['max_drawdown']:+.2%}  ({m['max_dd_weeks']} wk)")
        print(f"  ann funding {m['ann_funding']:+.2%}  ann basis {m['ann_basis']:+.2%}  "
              f"ann cost {m['ann_cost']:+.2%}  avg positions {m['avg_n_positions']}  "
              f"deployed {m['avg_capital_deployed']:.0%}")
        print(f"  positive years {m['positive_years']}/{m['n_years']}  weekly skew {m['weekly_skew']}  "
              f"kurtosis {m['weekly_kurtosis']}")
    am = res.headline_adverse
    if am.get("state") == "OK":
        print(f"[ADVERSE costs] Sharpe {am['sharpe']:+.2f}  CAGR {am['cagr']:+.2%}")
    h1 = res.halves.get("first_half", {}); h2 = res.halves.get("second_half", {})
    print(f"halves Sharpe: {h1.get('sharpe')} -> {h2.get('sharpe')}")
    c = res.controls
    print(f"\nrandom-eligibility placebo: real pctl {c['random_eligibility_placebo'].get('real_percentile')}")
    print(f"funding persistence pooled corr: {c['funding_persistence'].get('pooled_corr')} "
          f"({c['funding_persistence'].get('n_coin_positive')}/{len(res.universe)} coins positive)")
    print(f"basis attribution: {json.dumps(c['basis_attribution'], default=str)}")
    print(f"delta-neutrality: btc beta {c['delta_neutrality_check'].get('btc', {}).get('beta')}")
    print(f"cost ladder: { {k: v['sharpe'] for k, v in c['cost_ladder'].items()} }")
    print(f"\n=== TAIL (exchange-collapse Monte-Carlo) ===")
    print(f"base no-tail: {res.tail_stress['base_no_tail']}")
    for key in ("p0.02_sev0.50", "p0.05_sev0.50", "p0.10_sev1.00"):
        print(f"  {key}: {res.tail_stress['grid'].get(key)}")
    print(f"  deterministic worst week: {res.tail_stress['deterministic_worst_case']}")
    print(f"\nEDGE:  {res.edge_verdict}\n  {res.edge_reason}")
    print(f"TAIL:  {res.tail_verdict}\n  {res.tail_reason}")
    print(f"\nOVERALL: {res.overall_verdict}")
    print(f"determinism match: {res.determinism['match']}")
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "DESIGN_NOTE", "CRYPTO_BASES", "SPOT_ASSET", "PERP_ASSET",
    "ingest_perp_ohlcv", "perp_data_ready", "build_panels", "run_carry", "random_eligibility_placebo",
    "funding_persistence", "basis_attribution", "delta_neutrality_check", "cost_ladder",
    "threshold_neighbourhood", "exchange_collapse_stress", "per_coin_breakdown",
    "classify_edge", "classify_tail", "classify_overall", "run", "persist", "get_result", "main",
]
