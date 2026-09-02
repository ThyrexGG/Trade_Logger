# -*- coding: utf-8 -*-
"""
FastAPI Analytics Router (Stage 14)

Migrates the legacy Streamlit "ANALYTICS & OVERVIEW" workflow (`app.py:1882-2470`)
to an HTTP surface for the React SPA.

**Strictly read-only.** GET-only. Nothing here submits / modifies / cancels /
transmits an order, enables automation, or touches `execution_pipeline` /
a broker adapter / the risk gateway. The Streamlit page's "Sync MT5" /
"Sync Capital" buttons are data-ingestion actions, not analytics, and are NOT
migrated here.

Every performance number is produced by the authoritative
`analytics.calculate_performance_metrics` — no formula is reimplemented. The
router only filters the `closed_trades` population (account / symbol / date,
exactly as the Streamlit page does) and shapes derived series for display.

Note: `research_analytics.py` powers a *different* Streamlit tab (the XAUUSD
adversarial audit under Research & Strategy Lab) and is out of scope for this
stage.
"""
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

import analytics
import database
from api.schemas import (
    AnalyticsAvailable,
    AnalyticsFiltersEcho,
    AnalyticsPerformanceResponse,
    DailyPnl,
    DirectionStats,
    EquityAnchor,
    PeriodReturns,
    PerformanceMetrics,
    SymbolBreakdownRow,
    SymbolPnl,
    TagBreakdownRow,
)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

_MAX_EQUITY_POINTS = 400


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_trades() -> pd.DataFrame:
    """The authoritative closed-trade population, dates parsed exactly as `app.py`."""
    df = database.get_closed_trades(ttl_sec=5.0)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    for col in ("entry_time", "exit_time"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="mixed", utc=True).dt.tz_localize(None)
    return df


def _parse_date(raw: str, field: str) -> pd.Timestamp:
    try:
        return pd.Timestamp(datetime.strptime(raw.strip(), "%Y-%m-%d"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"{field} must be an ISO date (YYYY-MM-DD)")


def _metrics_model(raw: Dict[str, Any]) -> PerformanceMetrics:
    return PerformanceMetrics(
        **{k: raw[k] for k in raw if k not in ("long_stats", "short_stats", "best_symbols", "worst_symbols")},
        long_stats=DirectionStats(**raw["long_stats"]),
        short_stats=DirectionStats(**raw["short_stats"]),
        best_symbols=[SymbolPnl(symbol=str(s["symbol"]), net_profit=float(s["net_profit"])) for s in raw["best_symbols"]],
        worst_symbols=[SymbolPnl(symbol=str(s["symbol"]), net_profit=float(s["net_profit"])) for s in raw["worst_symbols"]],
    )


def _empty_metrics(initial_balance: float) -> PerformanceMetrics:
    return _metrics_model(analytics.calculate_performance_metrics(pd.DataFrame(), initial_balance))


def _period_returns(filtered: pd.DataFrame, initial_balance: float) -> PeriodReturns:
    """Replicates the Streamlit period-return math (windows are relative to now)."""
    if filtered.empty:
        return PeriodReturns(avg_daily_pct=0.0, weekly_pct=0.0, monthly_pct=0.0,
                             annualized_pct=0.0, weekly_pnl=0.0, monthly_pnl=0.0)
    daily = filtered.groupby(filtered["exit_time"].dt.date)["net_profit"].sum()
    daily_rets = daily / initial_balance * 100.0
    avg_daily = float(daily_rets.mean()) if not daily_rets.empty else 0.0

    now = pd.Timestamp.now()
    weekly_pnl = float(filtered.loc[filtered["exit_time"] >= now - pd.Timedelta(days=7), "net_profit"].sum())
    monthly_pnl = float(filtered.loc[filtered["exit_time"] >= now - pd.Timedelta(days=30), "net_profit"].sum())
    weekly_ret = weekly_pnl / initial_balance * 100.0
    monthly_ret = monthly_pnl / initial_balance * 100.0
    if avg_daily > 0:
        annualized = ((1 + avg_daily / 100.0) ** 252 - 1) * 100.0
    else:
        annualized = avg_daily if avg_daily < 0 else 0.0

    return PeriodReturns(
        avg_daily_pct=round(avg_daily, 2),
        weekly_pct=round(weekly_ret, 2),
        monthly_pct=round(monthly_ret, 2),
        annualized_pct=round(annualized, 2),
        weekly_pnl=round(weekly_pnl, 2),
        monthly_pnl=round(monthly_pnl, 2),
    )


def _equity_curve(filtered: pd.DataFrame, initial_balance: float):
    ordered = filtered.sort_values(by="exit_time").reset_index(drop=True)
    balances = initial_balance + ordered["net_profit"].cumsum()
    anchors: List[EquityAnchor] = []
    for i, row in ordered.iterrows():
        anchors.append(EquityAnchor(
            time=pd.Timestamp(row["exit_time"]).isoformat(),
            equity=round(float(balances.iloc[i]), 2),
            net_profit=round(float(row["net_profit"]), 2),
            symbol=str(row["symbol"]).upper(),
        ))
    sampled = False
    if len(anchors) > _MAX_EQUITY_POINTS:
        step = math.ceil(len(anchors) / _MAX_EQUITY_POINTS)
        decimated = anchors[::step]
        if decimated[-1] is not anchors[-1]:
            decimated.append(anchors[-1])
        anchors = decimated
        sampled = True
    return anchors, sampled


@router.get("/performance", response_model=AnalyticsPerformanceResponse)
def get_performance(
    account: Optional[str] = Query(default=None, description="account_id, or omit for ALL"),
    symbols: Optional[str] = Query(default=None, description="comma-separated symbols; omit for all"),
    start: Optional[str] = Query(default=None, description="ISO date, filters exit_time >= start"),
    end: Optional[str] = Query(default=None, description="ISO date, filters exit_time <= end (inclusive day)"),
    initial_balance: float = Query(default=10000.0, gt=0, description="starting balance for the equity curve"),
) -> AnalyticsPerformanceResponse:
    """
    Account / symbol / date-filtered trading performance for the closed-trade
    journal. All headline metrics come from
    `analytics.calculate_performance_metrics`; derived series (equity curve,
    daily P&L, symbol / tag breakdown, period returns) mirror the Streamlit page.
    """
    if not math.isfinite(initial_balance):
        raise HTTPException(status_code=422, detail="initial_balance must be finite")

    df = _load_trades()
    all_accounts = sorted(df["account_id"].astype(str).unique()) if not df.empty else []

    # --- account filter ---
    acc = (account or "").strip()
    if acc and acc.upper() != "ALL" and acc not in all_accounts:
        raise HTTPException(status_code=422, detail=f"Unknown account '{acc}'")
    acc_label = acc if (acc and acc.upper() != "ALL") else "ALL"

    acc_df = df if acc_label == "ALL" else df[df["account_id"].astype(str) == acc_label]

    avail_symbols = sorted(acc_df["symbol"].astype(str).str.upper().unique()) if not acc_df.empty else []
    date_min = acc_df["exit_time"].min().date().isoformat() if not acc_df.empty else None
    date_max = acc_df["exit_time"].max().date().isoformat() if not acc_df.empty else None
    available = AnalyticsAvailable(
        accounts=all_accounts, symbols=avail_symbols, date_min=date_min, date_max=date_max,
    )

    # --- symbol filter ---
    requested_symbols: List[str] = []
    if symbols is not None and symbols.strip():
        requested_symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        unknown = [s for s in requested_symbols if s not in avail_symbols]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Symbol(s) not in the selected population: {', '.join(unknown)}",
            )

    # --- date filter ---
    start_ts = _parse_date(start, "start") if start else None
    end_ts = _parse_date(end, "end") if end else None
    if start_ts is not None and end_ts is not None and start_ts > end_ts:
        raise HTTPException(status_code=422, detail="start must be on or before end")

    filtered = acc_df
    if requested_symbols:
        filtered = filtered[filtered["symbol"].astype(str).str.upper().isin(requested_symbols)]
    if start_ts is not None:
        filtered = filtered[filtered["exit_time"] >= start_ts]
    if end_ts is not None:
        filtered = filtered[filtered["exit_time"] < end_ts + pd.Timedelta(days=1)]

    filters_echo = AnalyticsFiltersEcho(
        account=acc_label,
        symbols=requested_symbols or avail_symbols,
        start=start_ts.date().isoformat() if start_ts is not None else None,
        end=end_ts.date().isoformat() if end_ts is not None else None,
        initial_balance=float(initial_balance),
    )

    # --- empty population ---
    if filtered is None or filtered.empty:
        return AnalyticsPerformanceResponse(
            metrics=_empty_metrics(initial_balance),
            equity_curve=[], equity_curve_sampled=False, daily_pnl=[],
            symbol_breakdown=[], tag_breakdown=[],
            period_returns=_period_returns(pd.DataFrame(), initial_balance),
            official_balance=_official_balance(acc_label),
            filters_applied=filters_echo, available=available, matched_trades=0,
            source="closed_trades", timestamp=_now(),
        )

    filtered = filtered.sort_values(by="exit_time").reset_index(drop=True)

    metrics = _metrics_model(analytics.calculate_performance_metrics(filtered, initial_balance))
    equity_curve, sampled = _equity_curve(filtered, initial_balance)

    daily = (
        filtered.groupby(filtered["exit_time"].dt.date)
        .agg(net_profit=("net_profit", "sum"), trades=("net_profit", "size"))
        .reset_index()
        .sort_values(by="exit_time")
    )
    daily_pnl = [
        DailyPnl(date=pd.Timestamp(r["exit_time"]).date().isoformat(),
                 net_profit=round(float(r["net_profit"]), 2), trades=int(r["trades"]))
        for _, r in daily.iterrows()
    ]

    sym_group = filtered.groupby(filtered["symbol"].astype(str).str.upper())
    symbol_breakdown = []
    for sym, g in sym_group:
        wins = int((g["net_profit"] > 0).sum())
        n = int(len(g))
        symbol_breakdown.append(SymbolBreakdownRow(
            symbol=str(sym), net_profit=round(float(g["net_profit"].sum()), 2),
            trades=n, wins=wins, win_rate=round(wins / n * 100.0, 2) if n else 0.0,
        ))
    symbol_breakdown.sort(key=lambda r: r.net_profit, reverse=True)

    tag_series = filtered["setup_tag"].fillna("Untagged").replace("", "Untagged") if "setup_tag" in filtered.columns else pd.Series(["Untagged"] * len(filtered))
    tag_group = filtered.assign(_tag=tag_series).groupby("_tag")
    tag_breakdown = [
        TagBreakdownRow(setup_tag=str(tag), net_profit=round(float(g["net_profit"].sum()), 2), trades=int(len(g)))
        for tag, g in tag_group
    ]
    tag_breakdown.sort(key=lambda r: r.net_profit, reverse=True)

    return AnalyticsPerformanceResponse(
        metrics=metrics,
        equity_curve=equity_curve,
        equity_curve_sampled=sampled,
        daily_pnl=daily_pnl,
        symbol_breakdown=symbol_breakdown,
        tag_breakdown=tag_breakdown,
        period_returns=_period_returns(filtered, initial_balance),
        official_balance=_official_balance(acc_label),
        filters_applied=filters_echo,
        available=available,
        matched_trades=int(len(filtered)),
        source="closed_trades",
        timestamp=_now(),
    )


def _official_balance(acc_label: str) -> Optional[float]:
    try:
        balances = database.get_account_balances() or {}
    except Exception:
        return None
    if acc_label != "ALL":
        entry = balances.get(acc_label)
        return round(float(entry["balance"]), 2) if entry else None
    if balances:
        return round(float(sum(b["balance"] for b in balances.values())), 2)
    return None
