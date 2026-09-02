# -*- coding: utf-8 -*-
"""
FastAPI Daily Command Center Router (Stage 15A)

"What matters today?" — a single read-only aggregate that re-shapes slices of
already-authoritative TradeLogger sources into one payload so the React page
needs one request instead of a fan-out:

  * daily / all-time performance  -> analytics.calculate_performance_metrics
  * open positions                -> database.get_open_positions
  * price alerts                  -> database.get_all_price_alerts
  * market regime / breadth       -> UnifiedMarketIntelligenceAggregator
  * research decision state       -> Phase49MonitoringFacade (cached snapshot)
  * research notes                -> DailyResearchJournal.get_notes  (read-only)
  * watchlist highlights          -> UnifiedWatchlistEngine

No new calculation is performed here and nothing is mutated. GET-only. There is
no import of / path to execution_pipeline, a broker adapter, or the risk gateway.
Each section is built defensively: a failing source degrades that one section
(listed in `sections_degraded`) instead of failing the whole overview.

The heavy XAUUSD news / economic-calendar engine
(`xauusd_daily_command_center.DailyTradingCommandEngine`) is intentionally NOT
migrated here — that macro layer stays in Streamlit pending the separately
specified macro-intelligence stage.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter

import analytics
import database
from api.schemas import (
    CCAccountSummary,
    CCAlerts,
    CCDailyPerformance,
    CCMarketContext,
    CCNote,
    CCPositions,
    CCResearchState,
    CCSafety,
    CCSessionClock,
    CCSymbolExposure,
    CCTriggeredAlert,
    CCWatchHighlight,
    CommandCenterOverviewResponse,
)

router = APIRouter(prefix="/api/command-center", tags=["Daily Command Center"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- session clock (pure UTC-hour computation, no network) --------------
_SESSIONS = [
    (0, 8, "ASIA", "LONDON", 8),
    (8, 13, "LONDON", "LONDON / NEW YORK OVERLAP", 13),
    (13, 17, "LONDON / NEW YORK OVERLAP", "NEW YORK", 17),
    (17, 21, "NEW YORK", "ASIA", 24),
    (21, 24, "INTER-SESSION ROLLOVER", "ASIA", 24),
]


def _session_clock(now: datetime) -> CCSessionClock:
    h = now.hour
    for lo, hi, cur, nxt, next_h in _SESSIONS:
        if lo <= h < hi:
            mins = (next_h - h) * 60 - now.minute
            return CCSessionClock(
                utc_time=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
                current_session=cur,
                next_session=nxt,
                next_session_in_min=max(0, mins),
            )
    return CCSessionClock(utc_time=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
                          current_session="UNKNOWN", next_session="UNKNOWN")


# --- section builders --------------------------------------------------
def _load_trades() -> pd.DataFrame:
    df = database.get_closed_trades(ttl_sec=5.0)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    for col in ("entry_time", "exit_time"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="mixed", utc=True).dt.tz_localize(None)
    return df


def _daily_and_account(now: datetime):
    df = _load_trades()
    if df.empty:
        empty = analytics.calculate_performance_metrics(pd.DataFrame(), 10000.0)
        daily = CCDailyPerformance(date=now.date().isoformat(), net_pnl=0.0, trades=0,
                                   wins=0, losses=0, win_rate=0.0, gross_profit=0.0, gross_loss=0.0)
        account = CCAccountSummary(all_time_net_pnl=0.0, all_time_trades=0, all_time_win_rate=0.0,
                                   profit_factor=empty["profit_factor"], max_drawdown_pct=0.0,
                                   official_balance=None, derived_balance=empty["final_balance"])
        return daily, account

    today = pd.Timestamp(now.date())
    day_df = df[(df["exit_time"] >= today) & (df["exit_time"] < today + pd.Timedelta(days=1))]
    day_m = analytics.calculate_performance_metrics(day_df, 10000.0)
    daily = CCDailyPerformance(
        date=now.date().isoformat(),
        net_pnl=day_m["total_net_pnl"], trades=day_m["total_trades"],
        wins=day_m["winning_trades"], losses=day_m["losing_trades"],
        win_rate=day_m["win_rate"], gross_profit=day_m["total_gross_profit"],
        gross_loss=day_m["total_gross_loss"],
    )

    all_m = analytics.calculate_performance_metrics(df.sort_values("exit_time"), 10000.0)
    official = None
    try:
        balances = database.get_account_balances() or {}
        if balances:
            official = round(float(sum(b["balance"] for b in balances.values())), 2)
    except Exception:
        official = None
    account = CCAccountSummary(
        all_time_net_pnl=all_m["total_net_pnl"], all_time_trades=all_m["total_trades"],
        all_time_win_rate=all_m["win_rate"], profit_factor=all_m["profit_factor"],
        max_drawdown_pct=all_m["max_drawdown_pct"], official_balance=official,
        derived_balance=all_m["final_balance"],
    )
    return daily, account


def _positions_section() -> CCPositions:
    df = database.get_open_positions(ttl_sec=2.0)
    if df is None or df.empty:
        return CCPositions(total_open=0, total_floating_pnl=0.0, long_count=0, short_count=0, by_symbol=[])
    by_sym: Dict[str, Dict[str, Any]] = {}
    total = 0.0
    longs = shorts = 0
    for _, p in df.iterrows():
        sym = str(p.get("symbol", "")).upper()
        pnl = float(p.get("floating_pnl", 0.0) or 0.0)
        total += pnl
        d = str(p.get("direction", "")).upper()
        if "BUY" in d or "LONG" in d:
            longs += 1
        elif "SELL" in d or "SHORT" in d:
            shorts += 1
        slot = by_sym.setdefault(sym, {"count": 0, "pnl": 0.0})
        slot["count"] += 1
        slot["pnl"] += pnl
    return CCPositions(
        total_open=int(len(df)), total_floating_pnl=round(total, 2),
        long_count=longs, short_count=shorts,
        by_symbol=[CCSymbolExposure(symbol=s, count=v["count"], floating_pnl=round(v["pnl"], 2))
                   for s, v in sorted(by_sym.items())],
    )


def _alerts_section() -> CCAlerts:
    df = database.get_all_price_alerts(limit=50, ttl_sec=8.0)
    if df is None or df.empty:
        return CCAlerts(active=0, triggered=0, triggered_recent=[])
    active = triggered = 0
    recent: List[CCTriggeredAlert] = []
    for _, a in df.iterrows():
        status = str(a.get("status", "")).upper()
        if status == "ACTIVE":
            active += 1
        elif status == "TRIGGERED":
            triggered += 1
            if len(recent) < 5:
                recent.append(CCTriggeredAlert(
                    id=int(a["id"]), symbol=str(a.get("symbol", "")).upper(),
                    condition=str(a.get("condition", "")).upper(),
                    target_price=float(a.get("target_price", 0.0) or 0.0),
                    triggered_at=str(a.get("triggered_at")) if a.get("triggered_at") is not None else None,
                ))
    return CCAlerts(active=active, triggered=triggered, triggered_recent=recent)


def _market_context() -> CCMarketContext:
    from market_intelligence_command_center import UnifiedMarketIntelligenceAggregator
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    regime = snap.regime_snapshot
    breadth = snap.market_breadth
    macro = snap.macro_environment
    health = snap.data_health
    return CCMarketContext(
        primary_regime=str(regime.primary_regime),
        regime_confidence_pct=float(regime.confidence_pct),
        breadth_bullish_pct=float(breadth.get("pct_bullish", 0.0)),
        breadth_bearish_pct=float(breadth.get("pct_bearish", 0.0)),
        strongest_asset=str(breadth.get("strongest_asset", "")),
        weakest_asset=str(breadth.get("weakest_asset", "")),
        usd_strength_state=str(macro.get("usd_strength_state", "NEUTRAL")),
        data_quality=int(health.get("overall_quality_score", 0)),
    )


def _research_state() -> CCResearchState:
    from xauusd_forward_statistical_monitoring import Phase49MonitoringFacade
    p49 = Phase49MonitoringFacade.get_cached_forward_state_snapshot(mode="PAPER", symbol="XAUUSD")
    decision = p49.get("decision", {}) or {}
    metrics = p49.get("metrics", {}) or {}
    state = str(decision.get("decision_state") or decision.get("state") or "INSUFFICIENT EVIDENCE")
    n = int(metrics.get("trades_n") or metrics.get("sample_n") or 0)
    headline = str(decision.get("rationale") or decision.get("research_action")
                   or f"Forward evidence: {state}")
    return CCResearchState(decision_state=state, sample_n=n, headline=headline)


def _research_notes() -> List[CCNote]:
    from xauusd_daily_command_center import DailyResearchJournal
    notes = DailyResearchJournal.get_notes(limit=5) or []
    return [CCNote(
        note_id=str(nt.get("note_id", "")), created_at=str(nt.get("created_at", "")),
        category=str(nt.get("category", "")), note_text=str(nt.get("note_text", "")),
        session_context=str(nt.get("session_context")) if nt.get("session_context") else None,
    ) for nt in notes]


def _watchlist_highlights() -> List[CCWatchHighlight]:
    from trading_workspace_cockpit import TradingWorkspaceCockpit
    rows = TradingWorkspaceCockpit.get_watchlist_data(asset_filter="ALL", search_query="") or []
    out: List[CCWatchHighlight] = []
    for r in rows:
        score = r.get("edge_score")
        out.append(CCWatchHighlight(
            symbol=str(r.get("symbol", "")).upper(),
            last_price=float(r["price"]) if r.get("price") is not None else None,
            bias=str(r.get("bias_4h")) if r.get("bias_4h") else None,
            score=float(score) if score is not None else None,
        ))
    out.sort(key=lambda w: abs(w.score) if w.score is not None else 0.0, reverse=True)
    return out[:6]


def _safety() -> CCSafety:
    try:
        import system_health
        gate = system_health.evaluate_system_health(broker="MT5", mode="PAPER") or {}
        checks = gate.get("checks", {}) or {}
        return CCSafety(
            automation_enabled=False, live_broker_transmission="BLOCKED",
            kill_switch_engaged=checks.get("kill_switch_engaged"),
            overall_status=str(gate.get("overall_status", "UNKNOWN")),
        )
    except Exception:
        return CCSafety()


@router.get("/overview", response_model=CommandCenterOverviewResponse)
def get_overview() -> CommandCenterOverviewResponse:
    """
    Aggregated read-only "what matters today" overview. One request; each section
    is an authoritative source re-shaped, never recomputed. A section that cannot
    be built is returned null/empty and named in `sections_degraded`.
    """
    now = _now()
    degraded: List[str] = []
    results: Dict[str, Any] = {}

    # The sections are independent and I/O-bound (cached engine reads / live
    # market snapshots). Run them concurrently so the overview is bounded by the
    # slowest source, not their sum. A failing source degrades only its section.
    jobs = {
        "daily_and_account": lambda: _daily_and_account(now),
        "positions": _positions_section,
        "alerts": _alerts_section,
        "market_context": _market_context,
        "research_state": _research_state,
        "research_notes": _research_notes,
        "watchlist_highlights": _watchlist_highlights,
        "safety": _safety,
    }
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {name: pool.submit(fn) for name, fn in jobs.items()}
        for name, fut in futures.items():
            try:
                results[name] = fut.result()
            except Exception:
                results[name] = None
                degraded.extend(["daily_performance", "account_summary"] if name == "daily_and_account" else [name])

    daily = account = None
    if results.get("daily_and_account") is not None:
        daily, account = results["daily_and_account"]
    positions = results.get("positions")
    alerts = results.get("alerts")
    market = results.get("market_context")
    research = results.get("research_state")
    notes: List[CCNote] = results.get("research_notes") or []
    highlights: List[CCWatchHighlight] = results.get("watchlist_highlights") or []
    safety = results.get("safety") or CCSafety()

    return CommandCenterOverviewResponse(
        as_of=now.isoformat(),
        session=_session_clock(now),
        safety=safety,
        daily_performance=daily,
        account_summary=account,
        positions=positions,
        alerts=alerts,
        market_context=market,
        research_state=research,
        research_notes=notes,
        watchlist_highlights=highlights,
        sections_degraded=degraded,
        source="command_center_aggregate",
        timestamp=now.isoformat(),
    )
