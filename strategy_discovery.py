# -*- coding: utf-8 -*-
"""
Strategy discovery engine (Phase 70).

Evaluates ``INSTRUMENT x STRATEGY x PARAMETERS x SESSION x REGIME`` on the
**persistent Phase-69 candle store** and turns each run into a reproducible,
evidence-backed research record. Nothing about backtest mechanics is
reimplemented here — every number comes from:

  * ``backtester.run_backtest``           — the canonical next-bar mechanical sim
  * ``research_engine.BootstrapEstimator``  — deterministic 95% CI on E[R]
  * ``research_engine.ScorecardClassifier`` — objective STRONG/PROMISING/…/FAILED
  * ``research_engine.ThreeLayerDataSplitter`` semantics (train / OOS)

Discovery runs against store data only (no per-request network). Data-capable
timeframes are 1h / 4h / 1d (`research_universe.timeframe_is_data_capable`);
anything else returns ``INSUFFICIENT_EVIDENCE`` with a named dependency — never a
"0 trades" verdict.

Read-only: no import of / path to any execution / broker / risk module.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import backtester
import historical_data_store as store
import research_engine
import research_universe
import strategies

# --------------------------------------------------------------------------
# Canonical discovery timeframe stack. Base is what the strategy executes on;
# struct/bias are the HTF context frames the backtester aligns without
# look-ahead. These mirror backtester's own timeframe -> (struct, bias) map.
# --------------------------------------------------------------------------
TF_STACK: Dict[str, Tuple[str, str]] = {
    "1m": ("15m", "1h"),   # Phase 73 — native execution TF of the frozen Gold contract
    "5m": ("15m", "1h"),
    "15m": ("1h", "4h"),
    "1h": ("4h", "1d"),
    "4h": ("1d", "1d"),
    "1d": ("1d", "1d"),
}

# Deterministic execution assumptions (research-grade friction). Per-instrument
# spread in *price* terms is pip_size * SPREAD_PIPS.
SPREAD_PIPS = 1.5
SLIPPAGE_PIPS = 0.5
COMMISSION_PCT = 0.005
RANDOM_SEED = 42
TRAIN_SPLIT = 0.70
_MIN_TRADES_FOR_EDGE = 30

SESSIONS = ("ASIA", "LONDON", "NEW_YORK", "LONDON_NY_OVERLAP")
REGIMES = ("TRENDING", "RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY")


# ==========================================================================
# Strategy definitions (§12) — machine-readable, wrapping the strategies/ registry
# ==========================================================================
@dataclass(frozen=True)
class StrategyDefinition:
    id: str
    registry_name: str          # key in strategies.STRATEGY_REGISTRY
    version: str
    family: str
    instrument_scope: str       # "universe" | "fx" | "metal" | csv of symbols
    entry_conditions: str
    exit_conditions: str
    stop_model: str
    target_model: str
    parameter_schema: Dict[str, Dict[str, Any]]   # name -> {default, grid, kind}
    filters: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    def defaults(self) -> Dict[str, float]:
        return {k: v["default"] for k, v in self.parameter_schema.items()}


def _sl_tp_schema() -> Dict[str, Dict[str, Any]]:
    return {
        "sl_atr": {"default": 1.5, "grid": [1.0, 1.5, 2.0], "kind": "float"},
        "tp_atr": {"default": 2.5, "grid": [2.0, 3.0, 4.0], "kind": "float"},
    }


STRATEGY_DEFINITIONS: Dict[str, StrategyDefinition] = {
    "ict_2022_sweep_mss_fvg": StrategyDefinition(
        id="ict_2022_sweep_mss_fvg",
        registry_name="ICT 2022 Model",
        version=strategies.get_strategy("ICT 2022 Model").version,
        family="LIQUIDITY_SWEEP + MSS + FVG",
        instrument_scope="universe",
        entry_conditions="SSL/BSL liquidity sweep -> aligned MSS (body close beyond fractal) -> "
                         "retrace into displacement FVG; HTF bias must not oppose",
        exit_conditions="fixed target or stop; market entry, 1-bar expiry",
        stop_model="beyond swept level - 0.2*ATR (fallback sl_atr*ATR)",
        target_model="entry +/- tp_atr*ATR",
        parameter_schema=_sl_tp_schema(),
        filters="HTF bias alignment; recent-window setup sequence",
    ),
    "liquidity_sweep_reversal": StrategyDefinition(
        id="liquidity_sweep_reversal",
        registry_name="Liquidity Sweep Reversal",
        version=strategies.get_strategy("Liquidity Sweep Reversal").version,
        family="LIQUIDITY_SWEEP reversal",
        instrument_scope="universe",
        entry_conditions="sweep of a major swing high (BSL) / low (SSL) that rejects and closes back inside",
        exit_conditions="fixed target or stop",
        stop_model="beyond the sweep wick",
        target_model="entry +/- tp_atr*ATR",
        parameter_schema=_sl_tp_schema(),
        filters="major swing level only",
    ),
    "smc_continuation_bos_fvg": StrategyDefinition(
        id="smc_continuation_bos_fvg",
        registry_name="USDJPY SMC Continuation",
        version=strategies.get_strategy("USDJPY SMC Continuation").version,
        family="HTF bias + BOS + FVG continuation",
        instrument_scope="universe",
        entry_conditions="in-trend BOS then retrace into the continuation FVG in the HTF-bias direction",
        exit_conditions="fixed target or stop",
        stop_model="beyond the origin of the BOS leg",
        target_model="entry +/- tp_atr*ATR",
        parameter_schema=_sl_tp_schema(),
        filters="HTF bias must agree",
    ),
    "trend_continuation_ema": StrategyDefinition(
        id="trend_continuation_ema",
        registry_name="Trend Continuation",
        version=strategies.get_strategy("Trend Continuation").version,
        family="EMA trend pullback",
        instrument_scope="universe",
        entry_conditions="pullback to EMA in an established up/down trend",
        exit_conditions="fixed target or stop",
        stop_model="sl_atr*ATR",
        target_model="tp_atr*ATR",
        parameter_schema=_sl_tp_schema(),
    ),
    "mean_reversion_rsi": StrategyDefinition(
        id="mean_reversion_rsi",
        registry_name="Mean Reversion",
        version=strategies.get_strategy("Mean Reversion").version,
        family="RSI mean reversion",
        instrument_scope="universe",
        entry_conditions="RSI < 30 long / RSI > 70 short",
        exit_conditions="fixed target or stop",
        stop_model="sl_atr*ATR",
        target_model="tp_atr*ATR",
        parameter_schema=_sl_tp_schema(),
    ),
}


def list_strategy_definitions() -> List[Dict[str, Any]]:
    return [d.to_dict() for d in STRATEGY_DEFINITIONS.values()]


def get_strategy_definition(sid: str) -> Optional[StrategyDefinition]:
    return STRATEGY_DEFINITIONS.get(sid)


# ==========================================================================
# Store -> backtester DataFrame adapter
# ==========================================================================
def _candles_df(candles: List[Dict[str, Any]]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("dt").sort_index()
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    return df[["Open", "High", "Low", "Close", "Volume"]]


@dataclass
class PreparedData:
    asset: str
    timeframe: str
    df: pd.DataFrame
    df_struct: pd.DataFrame
    df_bias: pd.DataFrame
    dataset_id: str
    dataset_hash: str
    coverage: Dict[str, Any]
    struct_tf: str
    bias_tf: str
    tier: str = "SUFFICIENT"          # SUFFICIENT | PARTIAL — set by prepare_data


# In-process cache: a full pair-ranking run calls prepare_data once per
# (asset, timeframe) per strategy — the candle fetch + DataFrame build is by far
# the most expensive step and is identical across strategies. Cache it.
_PREP_CACHE: Dict[str, Tuple[Optional["PreparedData"], Dict[str, Any]]] = {}


def clear_prepare_cache() -> None:
    _PREP_CACHE.clear()


_PARTIAL_MIN_BASE_BARS = 800   # hard floor for an explicitly-labelled PARTIAL read


def prepare_data(asset: str, timeframe: str, as_of: Optional[datetime] = None,
                 allow_partial: bool = False
                 ) -> Tuple[Optional[PreparedData], Dict[str, Any]]:
    """Pull base + HTF windows from the store. Returns (PreparedData|None, sufficiency).

    ``allow_partial`` (Phase 73): also return data that is real but below the
    sufficiency bar, tagged ``tier="PARTIAL"``. The ranking pipeline never sets
    this — only an explicitly-labelled exploratory read (native Gold
    revalidation) does. Still requires a hard floor of real bars."""
    asset = research_universe.normalise(asset)
    timeframe = (timeframe or "").strip().lower()
    _ck = f"{asset}::{timeframe}::{int(as_of.timestamp()) if as_of else 'live'}::{allow_partial}"
    if _ck in _PREP_CACHE:
        return _PREP_CACHE[_ck]

    def _cache(val):
        _PREP_CACHE[_ck] = val
        return val

    if timeframe not in TF_STACK:
        return _cache((None, {"state": "NOT_APPLICABLE",
                              "reason": f"timeframe '{timeframe}' not in the discovery stack"}))

    suf = store.data_sufficiency(asset, timeframe)
    capable = research_universe.timeframe_is_data_capable(timeframe)
    tier = "SUFFICIENT"

    if not (capable and suf["state"] == "AVAILABLE"):
        if not allow_partial:
            reason = suf.get("reason") or (
                f"{timeframe} has no multi-year depth on the wired data source"
                if not capable else str(suf.get("reasons")))
            return _cache((None, {"state": "INSUFFICIENT_EVIDENCE", "reason": reason,
                                  "next_dependency": "an intraday OHLCV provider",
                                  "coverage": suf.get("coverage")}))
        tier = "PARTIAL"

    struct_tf, bias_tf = TF_STACK[timeframe]
    as_of_epoch = int(as_of.timestamp()) if as_of else None
    base = store.get_candles(asset, timeframe, as_of=as_of_epoch)
    struct = store.get_candles(asset, struct_tf, as_of=as_of_epoch)
    bias = store.get_candles(asset, bias_tf, as_of=as_of_epoch)

    floor = (_PARTIAL_MIN_BASE_BARS if tier == "PARTIAL"
             else research_universe.sufficiency_rule(timeframe).min_bars)
    if len(base) < floor:
        s = store.data_sufficiency(asset, timeframe)
        s["reason"] = f"only {len(base)} {timeframe} bars in store (floor {floor})"
        return _cache((None, s))

    df, dfs, dfb = _candles_df(base), _candles_df(struct), _candles_df(bias)
    raw = json.dumps({"asset": asset, "tf": timeframe, "n": len(base),
                      "first": base[0]["time"], "last": base[-1]["time"],
                      "struct_n": len(struct), "bias_n": len(bias),
                      "tier": tier, "as_of": as_of_epoch}, sort_keys=True)
    dhash = hashlib.sha256(raw.encode()).hexdigest()
    cov = store.get_coverage(asset, timeframe).to_dict()
    return _cache((PreparedData(
        asset=asset, timeframe=timeframe, df=df, df_struct=dfs, df_bias=dfb,
        dataset_id=f"{asset}:{timeframe}:{base[0]['time']}-{base[-1]['time']}"
                   + (f":asof{as_of_epoch}" if as_of_epoch else ""),
        dataset_hash=dhash, coverage=cov, struct_tf=struct_tf, bias_tf=bias_tf,
        tier=tier,
    ), {**suf, "tier": tier}))


# ==========================================================================
# Metrics helpers
# ==========================================================================
def _r_multiples(trades: List[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    for t in trades:
        entry, sl = t.get("entry_price"), t.get("stop_loss")
        pnl = t.get("pnl")
        if entry is None or sl is None or pnl is None:
            continue
        risk = abs(float(entry) - float(sl)) * float(t.get("position_size") or 0.0)
        if risk <= 0:
            continue
        out.append(float(pnl) / risk)
    return out


def _metric_block(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {"total_trades": 0, "state": "INSUFFICIENT_EVIDENCE"}
    r = _r_multiples(trades)
    wins = [x for x in r if x > 0]
    losses = [x for x in r if x <= 0]
    gross_w = sum(wins)
    gross_l = abs(sum(losses)) or 1e-9
    equity = []
    cum = 0.0
    for x in r:
        cum += x
        equity.append(cum)
    peak = 0.0
    max_dd = 0.0
    for e in equity:
        peak = max(peak, e)
        max_dd = max(max_dd, peak - e)
    # longest losing streak
    cur_streak = worst = 0
    for x in r:
        if x <= 0:
            cur_streak += 1
            worst = max(worst, cur_streak)
        else:
            cur_streak = 0
    n = len(r)
    return {
        "total_trades": n,
        "win_rate_pct": round(100.0 * len(wins) / n, 1) if n else 0.0,
        "expectancy_r": round(sum(r) / n, 3) if n else 0.0,
        "median_r": round(sorted(r)[n // 2], 3) if n else 0.0,
        "profit_factor": round(gross_w / gross_l, 2),
        "gross_return_r": round(sum(r), 2),
        "max_drawdown_r": round(max_dd, 2),
        "avg_trade_r": round(sum(r) / n, 3) if n else 0.0,
        "largest_win_r": round(max(r), 3) if r else 0.0,
        "largest_loss_r": round(min(r), 3) if r else 0.0,
        "max_consecutive_losses": worst,
        "state": "AVAILABLE" if n >= _MIN_TRADES_FOR_EDGE else "INSUFFICIENT_EVIDENCE",
    }


def _session_of(ts: pd.Timestamp) -> str:
    h = ts.tz_convert("UTC").hour if ts.tzinfo else ts.hour
    if 12 <= h < 16:
        return "LONDON_NY_OVERLAP"
    if 7 <= h < 12:
        return "LONDON"
    if 16 <= h < 21:
        return "NEW_YORK"
    return "ASIA"


def _breakdown_by(trades: List[Dict[str, Any]], key_fn) -> Dict[str, Any]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for t in trades:
        try:
            k = key_fn(t)
        except Exception:
            k = "UNKNOWN"
        buckets.setdefault(k, []).append(t)
    return {k: _metric_block(v) for k, v in buckets.items()}


# ==========================================================================
# Discovery run
# ==========================================================================
@dataclass
class DiscoveryResult:
    asset: str
    strategy_id: str
    strategy_version: str
    timeframe: str
    state: str
    reason: str
    params: Dict[str, float]
    dataset_id: Optional[str]
    dataset_hash: Optional[str]
    is_metrics: Dict[str, Any]
    oos_metrics: Dict[str, Any]
    all_metrics: Dict[str, Any]
    bootstrap_ci: Dict[str, Any]
    scorecard: Dict[str, Any]
    session_breakdown: Dict[str, Any]
    regime_breakdown: Dict[str, Any]
    temporal_breakdown: Dict[str, Any]
    execution_assumptions: Dict[str, Any]
    coverage: Optional[Dict[str, Any]]
    generated_at: str
    next_dependency: Optional[str] = None
    data_tier: str = "SUFFICIENT"     # SUFFICIENT | PARTIAL | n/a

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _insufficient(asset, sid, timeframe, suf) -> DiscoveryResult:
    sdef = STRATEGY_DEFINITIONS.get(sid)
    return DiscoveryResult(
        asset=research_universe.normalise(asset), strategy_id=sid,
        strategy_version=sdef.version if sdef else "?", timeframe=timeframe,
        state="INSUFFICIENT_EVIDENCE", reason=suf.get("reason") or str(suf.get("reasons")),
        params={}, dataset_id=None, dataset_hash=None,
        is_metrics={"total_trades": 0}, oos_metrics={"total_trades": 0},
        all_metrics={"total_trades": 0}, bootstrap_ci={}, scorecard={},
        session_breakdown={}, regime_breakdown={}, temporal_breakdown={},
        execution_assumptions={}, coverage=suf.get("coverage"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        next_dependency=suf.get("next_dependency"),
    )


def discover(asset: str, strategy_id: str, timeframe: str = "1h",
             params: Optional[Dict[str, float]] = None,
             as_of: Optional[datetime] = None,
             allow_partial: bool = False,
             ) -> DiscoveryResult:
    """Run one INSTRUMENT x STRATEGY x PARAMS discovery on store data.

    ``allow_partial`` (Phase 73) also runs on real-but-below-bar intraday data,
    with ``DiscoveryResult.reason`` / ``state`` carrying the PARTIAL tier. Only an
    explicitly-labelled exploratory read sets this — never the ranking pipeline."""
    sdef = STRATEGY_DEFINITIONS.get(strategy_id)
    if sdef is None:
        raise KeyError(f"unknown strategy_id '{strategy_id}'")
    asset = research_universe.normalise(asset)
    timeframe = (timeframe or "1h").strip().lower()
    p = {**sdef.defaults(), **(params or {})}

    prepared, suf = prepare_data(asset, timeframe, as_of=as_of, allow_partial=allow_partial)
    if prepared is None:
        return _insufficient(asset, strategy_id, timeframe, suf)

    inst = research_universe.get_instrument(asset)
    fixed_spread = inst.pip_size * SPREAD_PIPS
    slippage = inst.pip_size * SLIPPAGE_PIPS

    res = backtester.run_backtest(
        symbol=asset, timeframe=timeframe, strategy=sdef.registry_name,
        risk_pct=1.0, sl_atr=p.get("sl_atr", 1.5), tp_atr=p.get("tp_atr", 2.5),
        slippage=slippage, commission_pct=COMMISSION_PCT, fixed_spread=fixed_spread,
        train_split=TRAIN_SPLIT,
        preloaded_data={"df": prepared.df, "df_struct": prepared.df_struct,
                        "df_bias": prepared.df_bias},
    )
    if "error" in res:
        return DiscoveryResult(
            asset=asset, strategy_id=strategy_id, strategy_version=sdef.version,
            timeframe=timeframe, state="INSUFFICIENT_EVIDENCE",
            reason=f"backtest produced no result: {res['error']}", params=p,
            dataset_id=prepared.dataset_id, dataset_hash=prepared.dataset_hash,
            is_metrics={"total_trades": 0}, oos_metrics={"total_trades": 0},
            all_metrics={"total_trades": 0}, bootstrap_ci={}, scorecard={},
            session_breakdown={}, regime_breakdown={}, temporal_breakdown={},
            execution_assumptions=_assumptions(fixed_spread, slippage),
            coverage=prepared.coverage,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    trades = res.get("trades", [])
    is_trades = [t for t in trades if not t.get("is_oos")]
    oos_trades = [t for t in trades if t.get("is_oos")]
    all_block = _metric_block(trades)
    is_block = _metric_block(is_trades)
    oos_block = _metric_block(oos_trades)

    oos_r = _r_multiples(oos_trades)
    ci = research_engine.BootstrapEstimator.calculate_r_expectancy_ci(
        oos_r if oos_r else _r_multiples(trades), random_seed=RANDOM_SEED)

    scorecard = research_engine.ScorecardClassifier.evaluate_strategy(
        is_metrics=is_block, oos_metrics=oos_block, holdout_metrics=oos_block,
        bootstrap_ci=ci, wfo_status="Unknown", parameter_stability="UNKNOWN")

    sess = _breakdown_by(trades, lambda t: t.get("session")
                         or _session_of(pd.Timestamp(t["entry_time"])))
    temporal = _breakdown_by(trades, lambda t: str(pd.Timestamp(t["entry_time"]).year))
    regime_bd = _regime_breakdown(trades, prepared)

    enough = all_block.get("total_trades", 0) >= _MIN_TRADES_FOR_EDGE
    if prepared.tier == "PARTIAL":
        state = "PARTIAL"
        reason = (f"PARTIAL data ({prepared.coverage.get('count')} {timeframe} bars, "
                  f"{all_block.get('total_trades', 0)} trades) — real but below the sufficiency "
                  f"bar; exploratory only, NOT validation-grade")
    elif enough:
        state, reason = "AVAILABLE", "robust sample"
    else:
        state = "INSUFFICIENT_EVIDENCE"
        reason = f"only {all_block.get('total_trades', 0)} trades (< {_MIN_TRADES_FOR_EDGE})"

    return DiscoveryResult(
        asset=asset, strategy_id=strategy_id, strategy_version=sdef.version,
        timeframe=timeframe, state=state, reason=reason, params=p,
        dataset_id=prepared.dataset_id, dataset_hash=prepared.dataset_hash,
        is_metrics=is_block, oos_metrics=oos_block, all_metrics=all_block,
        bootstrap_ci=ci, scorecard=scorecard,
        session_breakdown=sess, regime_breakdown=regime_bd, temporal_breakdown=temporal,
        execution_assumptions=_assumptions(fixed_spread, slippage),
        coverage=prepared.coverage,
        generated_at=datetime.now(timezone.utc).isoformat(),
        next_dependency=None if state == "AVAILABLE"
        else "more history / a lower timeframe with real intraday depth",
        data_tier=prepared.tier,
    )


def _assumptions(fixed_spread: float, slippage: float) -> Dict[str, Any]:
    return {
        "execution": "next-bar; limit fills require touch; market fills at open+/-slippage",
        "fixed_spread_price": round(fixed_spread, 6),
        "slippage_price": round(slippage, 6),
        "commission_pct": COMMISSION_PCT,
        "spread_pips": SPREAD_PIPS, "slippage_pips": SLIPPAGE_PIPS,
        "train_split": TRAIN_SPLIT, "random_seed": RANDOM_SEED,
        "source": "historical_candles store (Phase 69)",
    }


def _regime_breakdown(trades, prepared: PreparedData) -> Dict[str, Any]:
    """Classify each trade's entry bar by a compact ATR/EMA regime derived from the
    prepared base frame (same signals/thresholds family as CrossAssetRegimeEngine,
    which is a live-only engine and not used in historical discovery)."""
    if not trades:
        return {}
    df = prepared.df.copy()
    ema20 = df["Close"].ewm(span=20, adjust=False).mean()
    ema50 = df["Close"].ewm(span=50, adjust=False).mean()
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    atr_pct = (atr / df["Close"]) * 100.0
    atr_med = atr_pct.rolling(200, min_periods=30).median()

    def classify(ts) -> str:
        try:
            i = df.index.get_indexer([pd.Timestamp(ts)], method="nearest")[0]
        except Exception:
            return "UNKNOWN"
        trending = abs(ema20.iloc[i] - ema50.iloc[i]) / max(df["Close"].iloc[i], 1e-9) > 0.001
        hot = bool(atr_pct.iloc[i] > (atr_med.iloc[i] or atr_pct.iloc[i]))
        if trending:
            return "TRENDING"
        return "HIGH_VOLATILITY" if hot else "RANGING"

    return _breakdown_by(trades, lambda t: classify(t["entry_time"]))


# ==========================================================================
# ResearchRankingScore (§22) — decomposable, NOT a market/trade signal
# ==========================================================================
RANKING_WEIGHTS = {
    "oos_expectancy": 0.30,
    "oos_ci_lower": 0.20,
    "profit_factor": 0.15,
    "sample_size": 0.15,
    "drawdown": 0.10,
    "wfo_stability": 0.10,
}


def research_ranking_score(result: DiscoveryResult, wfo_stability: Optional[float] = None
                           ) -> Dict[str, Any]:
    """A sorting aid for research candidates. Every component stays visible; the
    underlying metrics are never hidden behind the number. This is NOT a
    ``MarketScore`` / ``TradeScore`` and must never drive an order."""
    oos = result.oos_metrics
    ci = result.bootstrap_ci
    n = oos.get("total_trades", 0)
    if result.state != "AVAILABLE" or n < _MIN_TRADES_FOR_EDGE:
        return {"score": None, "state": "INSUFFICIENT_EVIDENCE",
                "components": {}, "weights": RANKING_WEIGHTS,
                "note": "not scored — insufficient OOS sample"}

    def clamp01(x): return max(0.0, min(1.0, x))
    comp = {
        "oos_expectancy": clamp01((oos.get("expectancy_r", 0.0) + 0.2) / 0.8),
        "oos_ci_lower": clamp01((ci.get("ci_lower", -1.0) + 0.2) / 0.6),
        "profit_factor": clamp01((oos.get("profit_factor", 0.0) - 1.0) / 1.5),
        "sample_size": clamp01((n - _MIN_TRADES_FOR_EDGE) / 270.0),
        "drawdown": clamp01(1.0 - oos.get("max_drawdown_r", 0.0) / 15.0),
        "wfo_stability": clamp01(wfo_stability) if wfo_stability is not None else 0.0,
    }
    score = round(100.0 * sum(RANKING_WEIGHTS[k] * comp[k] for k in RANKING_WEIGHTS), 1)
    return {
        "score": score,
        "state": "AVAILABLE",
        "components": {k: round(v, 3) for k, v in comp.items()},
        "weights": RANKING_WEIGHTS,
        "raw_metrics": {
            "oos_expectancy_r": oos.get("expectancy_r"),
            "oos_ci": ci.get("ci_range_str"),
            "oos_profit_factor": oos.get("profit_factor"),
            "oos_trades": n,
            "oos_max_drawdown_r": oos.get("max_drawdown_r"),
            "wfo_stability": wfo_stability,
        },
        "note": "ResearchRankingScore — a candidate-sorting aid, NOT a trading signal",
    }


__all__ = [
    "StrategyDefinition", "STRATEGY_DEFINITIONS", "list_strategy_definitions",
    "get_strategy_definition", "TF_STACK", "PreparedData", "prepare_data",
    "DiscoveryResult", "discover", "research_ranking_score", "RANKING_WEIGHTS",
]
