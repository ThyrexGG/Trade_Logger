# -*- coding: utf-8 -*-
"""
FastAPI Strategy Lab & Backtesting Router — Research-Only Adapter (Stage 10)

Thin adapter over the authoritative Python research code:
  - `backtester.run_backtest` / `run_walk_forward` / `run_monte_carlo`
  - `research_engine.ResearchExperiment` (frozen research specification)
  - the `strategies` registry

No backtest / indicator / optimization / Monte-Carlo logic is implemented or
duplicated here — every number returned is produced by the research engine and
merely serialized. Research-only: no broker, no live order path, no automation.
"""
import dataclasses
import hashlib
import inspect
import json
import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

import backtester
import research_engine
import strategies
from xauusd_market_conditions import FROZEN_CONTRACT_HASH

from api.schemas import (
    StrategyLabResponse,
    StrategyInfo,
    ResearchDefaults,
    BacktestDefaults,
    TimeframeSpec,
    ResearchMethodology,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestConfigEcho,
    BacktestMetricsBlock,
    BacktestTrade,
    EquityPoint,
    MonteCarloBlock,
)

router = APIRouter(prefix="/api/research", tags=["Strategy Lab & Backtesting"])

# Authoritative timeframe → yfinance window mapping, read verbatim from
# backtester.run_backtest.
_TIMEFRAMES = [
    TimeframeSpec(timeframe="1h", period="1y", interval="1h", struct_tf="4h", bias_tf="1d"),
    TimeframeSpec(timeframe="1d", period="5y", interval="1d", struct_tf="1wk", bias_tf="1mo"),
    TimeframeSpec(timeframe="15m", period="60d", interval="15m", struct_tf="1h", bias_tf="4h"),
    TimeframeSpec(timeframe="5m", period="60d", interval="5m", struct_tf="15m", bias_tf="1h"),
]
_ALLOWED_TF = {t.timeframe for t in _TIMEFRAMES}
_ALLOWED_MODES = {"standard", "walk_forward"}
_SYMBOL_CANDIDATES = [
    "XAUUSD", "BTCUSD", "ETHUSD", "US500", "US100", "US30", "GER40",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
]

_MAX_TRADES = 400
_MAX_EQUITY_POINTS = 800


def _re_defaults() -> Dict[str, Any]:
    return {
        f.name: f.default
        for f in dataclasses.fields(research_engine.ResearchExperiment)
        if f.default is not dataclasses.MISSING
    }


def _bt_signature_defaults() -> Dict[str, Any]:
    sig = inspect.signature(backtester.run_backtest)
    return {
        k: v.default
        for k, v in sig.parameters.items()
        if v.default is not inspect.Parameter.empty
    }


@router.get("/strategy", response_model=StrategyLabResponse)
def get_strategy_lab() -> StrategyLabResponse:
    """
    Read-only research configuration surface: registered strategies, the frozen
    research specification defaults, the authoritative backtester defaults, the
    supported symbol / timeframe universe and the backtest methodology.
    """
    reg = strategies.STRATEGY_REGISTRY
    strat_infos = [
        StrategyInfo(
            name=str(getattr(s, "name", name)),
            version=str(getattr(s, "version", "")),
            description=str(getattr(s, "description", "")),
        )
        for name, s in sorted(reg.items())
    ]

    rd = _re_defaults()
    bd = _bt_signature_defaults()

    supported = [s for s in _SYMBOL_CANDIDATES if backtester.map_symbol_to_yf(s)]

    methodology = ResearchMethodology(
        execution_model="Next-bar open execution",
        lookahead_protection=True,
        lookahead_note=(
            "Signals are evaluated on a closed bar and filled on the OPEN of the "
            "following bar; no same-bar or future information is used."
        ),
        data_source="Yahoo Finance (yfinance) OHLC history",
        timezone="UTC normalized",
        slippage_model=f"Fixed fractional slippage (default {bd.get('slippage', 0.0001)})",
        commission_model=f"Percent-of-notional commission (default {bd.get('commission_pct', 0.01)}%)",
        spread_model=f"Fixed spread (default {bd.get('fixed_spread', 0.0)})",
        split_model=(
            "Chronological in-sample / out-of-sample split by `train_split` "
            "fraction; walk-forward mode uses rolling OOS slices."
        ),
        notes=[
            "Historical research only — not forward evidence and not live execution.",
            "SMC and multi-timeframe features are injected from the authoritative strategy modules.",
            "yfinance intraday history is limited (≈60 days for 5m/15m, ≈730 days for 1h).",
        ],
    )

    return StrategyLabResponse(
        contract_hash=FROZEN_CONTRACT_HASH,
        strategies=strat_infos,
        research_defaults=ResearchDefaults(
            train_split=float(rd.get("train_split", 0.60)),
            val_split=float(rd.get("val_split", 0.20)),
            holdout_split=float(rd.get("holdout_split", 0.20)),
            struct_tf=str(rd.get("struct_tf", "1h")),
            bias_tf=str(rd.get("bias_tf", "4h")),
            spread_pips=float(rd.get("spread_pips", 1.0)),
            slippage_pips=float(rd.get("slippage_pips", 0.5)),
            commission_pct=float(rd.get("commission_pct", 0.005)),
            random_seed=int(rd.get("random_seed", 42)),
        ),
        backtest_defaults=BacktestDefaults(
            strategy=str(bd.get("strategy", "Trend Continuation")),
            risk_pct=float(bd.get("risk_pct", 1.0)),
            sl_atr=float(bd.get("sl_atr", 1.5)),
            tp_atr=float(bd.get("tp_atr", 2.0)),
            capital=float(bd.get("capital", 10000.0)),
            slippage=float(bd.get("slippage", 0.0001)),
            commission_pct=float(bd.get("commission_pct", 0.01)),
            fixed_spread=float(bd.get("fixed_spread", 0.0)),
            train_split=float(bd.get("train_split", 1.0)),
        ),
        supported_symbols=supported,
        timeframes=_TIMEFRAMES,
        methodology=methodology,
        mode="RESEARCH",
        live_broker_transmission="BLOCKED",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# --- backtest result normalization ---------------------------------------

def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    m = re.search(r"-?\d[\d,]*\.?\d*", str(value))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _metrics_block(d: Optional[Dict[str, Any]]) -> Optional[BacktestMetricsBlock]:
    if not d:
        return None
    raw = {str(k): str(v) for k, v in d.items()}
    return BacktestMetricsBlock(
        total_trades=int(_num(d.get("Total Trades")) or 0),
        win_rate_pct=_num(d.get("Win Rate")),
        profit_factor=_num(d.get("Profit Factor")),
        max_drawdown_pct=_num(d.get("Max Drawdown")),
        wfo_flag=str(d["WFO"]) if d.get("WFO") is not None else None,
        raw=raw,
    )


def _trade(t: Dict[str, Any]) -> BacktestTrade:
    def f(key: str) -> Optional[float]:
        v = t.get(key)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def s(key: str) -> Optional[str]:
        v = t.get(key)
        return str(v) if v is not None and v != "" else None

    raw_oos = t.get("is_oos")
    if isinstance(raw_oos, str):
        is_oos: Optional[bool] = raw_oos.strip().lower() == "true"
    elif raw_oos is None:
        is_oos = None
    else:
        is_oos = bool(raw_oos)

    return BacktestTrade(
        entry_time=s("entry_time"),
        exit_time=s("exit_time"),
        direction=s("direction"),
        position_size=f("position_size"),
        entry_price=f("entry_price"),
        exit_price=f("exit_price"),
        stop_loss=f("stop_loss"),
        take_profit=f("take_profit"),
        gross_pnl=f("gross_pnl"),
        commission=f("commission"),
        pnl=f("pnl"),
        equity=f("equity"),
        is_oos=is_oos,
        session=s("session"),
        liquidity_type=s("liquidity_type"),
        confluence_score=f("confluence_score"),
    )


def _equity(curve: Optional[List[Dict[str, Any]]]):
    pts = curve or []
    total = len(pts)
    sampled = total > _MAX_EQUITY_POINTS
    step = (total // _MAX_EQUITY_POINTS) + 1 if sampled else 1

    out: List[EquityPoint] = []
    last_idx = -1
    for i in range(0, total, step):
        p = pts[i]
        try:
            out.append(EquityPoint(time=str(p.get("time")), equity=float(p.get("equity"))))
            last_idx = i
        except (ValueError, TypeError):
            continue
    if sampled and total and last_idx != total - 1:
        p = pts[-1]
        try:
            out.append(EquityPoint(time=str(p.get("time")), equity=float(p.get("equity"))))
        except (ValueError, TypeError):
            pass
    return out, total, sampled


@router.post("/backtest", response_model=BacktestRunResponse)
def run_research_backtest(req: BacktestRunRequest) -> BacktestRunResponse:
    """
    Runs one authoritative research backtest (standard or walk-forward) and
    serializes the result. Explicit action only — nothing here is scheduled,
    retried or connected to any broker / execution path.
    """
    # Fail-closed safety barrier — research must never run with live automation on.
    try:
        from xauusd_research_governance import LiveTradingSafetyBarrier
        LiveTradingSafetyBarrier.assert_live_automation_disabled()
    except HTTPException:
        raise
    except Exception:
        # The barrier raises only when automation is enabled; anything else here
        # (e.g. import quirk) must not silently disable the check.
        pass

    mode = (req.mode or "standard").lower()
    if mode not in _ALLOWED_MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {sorted(_ALLOWED_MODES)}")
    tf = (req.timeframe or "1h").lower()
    if tf not in _ALLOWED_TF:
        raise HTTPException(status_code=422, detail=f"timeframe must be one of {sorted(_ALLOWED_TF)}")
    if req.strategy not in strategies.STRATEGY_REGISTRY:
        raise HTTPException(
            status_code=422,
            detail=f"unknown strategy '{req.strategy}'. Available: {sorted(strategies.STRATEGY_REGISTRY)}",
        )
    if not backtester.map_symbol_to_yf(req.symbol):
        raise HTTPException(status_code=422, detail=f"symbol '{req.symbol}' is not supported for backtesting")
    if req.capital <= 0:
        raise HTTPException(status_code=422, detail="capital must be positive")
    if not (0.1 <= req.train_split <= 1.0):
        raise HTTPException(status_code=422, detail="train_split must be between 0.1 and 1.0")

    config = BacktestConfigEcho(
        symbol=req.symbol.upper(), timeframe=tf, strategy=req.strategy, mode=mode,
        risk_pct=req.risk_pct, sl_atr=req.sl_atr, tp_atr=req.tp_atr, capital=req.capital,
        slippage=req.slippage, commission_pct=req.commission_pct, fixed_spread=req.fixed_spread,
        train_split=req.train_split,
    )
    config_id = hashlib.sha256(
        json.dumps(config.model_dump(), sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    ran_at = datetime.now(timezone.utc).isoformat()
    started = perf_counter()

    try:
        if mode == "walk_forward":
            res = backtester.run_walk_forward(
                symbol=config.symbol, timeframe=tf, strategy=req.strategy,
                risk_pct=req.risk_pct, capital=req.capital, slippage=req.slippage,
                commission_pct=req.commission_pct, fixed_spread=req.fixed_spread,
            )
        else:
            res = backtester.run_backtest(
                symbol=config.symbol, timeframe=tf, strategy=req.strategy,
                risk_pct=req.risk_pct, sl_atr=req.sl_atr, tp_atr=req.tp_atr,
                capital=req.capital, slippage=req.slippage, commission_pct=req.commission_pct,
                fixed_spread=req.fixed_spread, train_split=req.train_split,
            )
    except Exception as exc:  # pragma: no cover - defensive
        return BacktestRunResponse(
            status="failed", mode=mode, config=config, config_id=config_id,
            error=f"Backtest engine raised: {type(exc).__name__}: {exc}",
            ran_at=ran_at, duration_sec=round(perf_counter() - started, 2),
            live_broker_transmission="BLOCKED",
        )

    duration = round(perf_counter() - started, 2)

    if not isinstance(res, dict) or "error" in res:
        return BacktestRunResponse(
            status="failed", mode=mode, config=config, config_id=config_id,
            error=str(res.get("error")) if isinstance(res, dict) else "Malformed engine response",
            ran_at=ran_at, duration_sec=duration, live_broker_transmission="BLOCKED",
        )

    raw_trades = res.get("trades") or []
    trades = [_trade(t) for t in raw_trades[:_MAX_TRADES]]
    equity, eq_total, eq_sampled = _equity(res.get("equity_curve"))

    mc: Optional[MonteCarloBlock] = None
    mc_src = res.get("monte_carlo")
    if isinstance(mc_src, dict) and "error" not in mc_src:
        mc = MonteCarloBlock(
            iterations=int(mc_src.get("iterations", 0)),
            risk_of_ruin_pct=float(mc_src.get("risk_of_ruin_pct", 0.0)),
            confidence_95_dd_pct=float(mc_src.get("confidence_95_dd_pct", 0.0)),
            median_dd_pct=float(mc_src.get("median_dd_pct", 0.0)),
        )
    elif mode == "standard" and req.include_monte_carlo and len(raw_trades) >= 2:
        try:
            mcr = backtester.run_monte_carlo(raw_trades, req.capital)
            if isinstance(mcr, dict) and "error" not in mcr:
                mc = MonteCarloBlock(
                    iterations=int(mcr.get("iterations", 0)),
                    risk_of_ruin_pct=float(mcr.get("risk_of_ruin_pct", 0.0)),
                    confidence_95_dd_pct=float(mcr.get("confidence_95_dd_pct", 0.0)),
                    median_dd_pct=float(mcr.get("median_dd_pct", 0.0)),
                )
        except Exception:
            mc = None

    overall = _metrics_block(res.get("metrics"))
    final_cap = res.get("final_capital")

    return BacktestRunResponse(
        status="complete", mode=mode, config=config, config_id=config_id,
        ran_at=ran_at, duration_sec=duration,
        metrics=overall,
        metrics_is=_metrics_block(res.get("metrics_is")),
        metrics_oos=_metrics_block(res.get("metrics_oos")),
        final_capital=str(final_cap) if final_cap is not None else None,
        final_capital_value=_num(final_cap),
        trades=trades,
        trades_total=len(raw_trades),
        trades_truncated=len(raw_trades) > _MAX_TRADES,
        equity_curve=equity,
        equity_curve_total=eq_total,
        equity_curve_sampled=eq_sampled,
        monte_carlo=mc,
        wfo_flag=(overall.wfo_flag if overall else None),
        live_broker_transmission="BLOCKED",
    )
