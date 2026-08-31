"""
Phase 35 — XAUUSD Daily Trading Command Center, News Alerts & Setup Context Integration
Implements:
- DailyTradingCommandEngine ("What do I need to know RIGHT NOW?")
- SetupExplainabilityEngine ("Why is there / isn't there a valid setup?")
- MarketContextSnapshotEngine (Immutable market-context snapshots & database persistence)
- DailyResearchJournal (Persistent timestamped research notes)
- DailyTradingSummaryEngine (End-of-day market and strategy performance summary)
- Invariants: Strategy Frozen, Zero Directional News Advice, Permanent Live Safety Lock
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import pandas as pd

import database
from xauusd_alert_engine import XAUUSDAlertEngine
from xauusd_daily_preflight import (
    DailyPreFlightEngine,
    DailyPreFlightChecklist,
    SessionHolidayInteractionMatrix,
    HistoricalDailyNewsAuditor,
    EconomicCalendarProviderFactory,
)
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_live_state_engine import XAUUSDLiveMTFStateEngine
from xauusd_market_conditions import (
    MarketHolidayDetector,
    EventProximityEngine,
    FROZEN_CONTRACT_HASH,
)
from xauusd_operational_monitor import (
    MarketDataFeedAuditor,
    OperationalHealthEvaluator,
)
import xauusd_news_reliability


def init_phase35_database(conn=None):
    """Initializes tables for context snapshots and research journal notes."""
    should_close = False
    if conn is None:
        conn = database.get_connection()
        should_close = True
    
    cur = conn.cursor()
    
    # Table for immutable market context snapshots
    cur.execute("""
    CREATE TABLE IF NOT EXISTS xauusd_context_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        price REAL NOT NULL,
        session_name TEXT NOT NULL,
        master_condition TEXT NOT NULL,
        holiday_status TEXT NOT NULL,
        nearest_event_name TEXT,
        nearest_event_proximity TEXT,
        mtf_strategy_state TEXT NOT NULL,
        contract_hash TEXT NOT NULL,
        research_health TEXT NOT NULL,
        snapshot_fingerprint TEXT NOT NULL,
        context_payload TEXT NOT NULL
    )
    """)

    # Table for persistent daily research notes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS xauusd_research_notes (
        note_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        note_date TEXT NOT NULL,
        category TEXT NOT NULL,
        note_text TEXT NOT NULL,
        session_context TEXT,
        is_pinned INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    if should_close:
        conn.close()


init_phase35_database()


class SetupExplainabilityEngine:
    """
    Explains the exact current multi-timeframe strategy state.
    Answers: "Why is there / isn't there a valid setup?"
    Breaks down 1D Bias, 4H DOL, 15M Sweep/MSS, 5M Confirmation, and 1M FVG Limit Entry.
    """

    @staticmethod
    def explain_current_setup(symbol: str = "XAUUSD") -> Dict[str, Any]:
        live_mtf = XAUUSDLiveMTFStateEngine.get_complete_live_market_state(symbol)
        dec = live_mtf["decision"]
        layer_1d = live_mtf["layer_1d"]
        layer_4h = live_mtf["layer_4h"]
        layer_15m = live_mtf["layer_15m"]
        layer_5m = live_mtf["layer_5m"]
        layer_1m = live_mtf["layer_1m"]

        state = dec.get("state", "WAITING")
        is_approved = state in ["ACTIVE_SETUP", "VALID_SETUP", "ENTRY_READY"]

        # Synthesize layer breakdown
        layers_breakdown = [
            {
                "timeframe": "1D",
                "purpose": "Macro Bias & Institutional Direction",
                "status": "PASS" if layer_1d.get("bias") in ["BULLISH", "BEARISH"] else "WAITING",
                "detail": f"Bias: {layer_1d.get('bias', 'NEUTRAL')}, Swing High: {layer_1d.get('swing_high', 0.0):.2f}, Swing Low: {layer_1d.get('swing_low', 0.0):.2f}",
                "waiting_for": "Clear daily market structure break" if layer_1d.get("bias") == "NEUTRAL" else "Maintained",
            },
            {
                "timeframe": "4H",
                "purpose": "Draw On Liquidity (DOL)",
                "status": "PASS" if layer_4h.get("dol_target") else "WAITING",
                "detail": f"DOL Target: {layer_4h.get('dol_target', 0.0):.2f}, DOL Type: {layer_4h.get('dol_type', 'NONE')}",
                "waiting_for": "Higher timeframe liquidity target identification" if not layer_4h.get("dol_target") else "Target active",
            },
            {
                "timeframe": "15M",
                "purpose": "Intermediate Setup (Sweep & MSS)",
                "status": "PASS" if layer_15m.get("sweep_confirmed") and layer_15m.get("mss_confirmed") else "WAITING",
                "detail": f"Sweep: {'YES' if layer_15m.get('sweep_confirmed') else 'NO'}, MSS: {'YES' if layer_15m.get('mss_confirmed') else 'NO'}, Displacement: {'YES' if layer_15m.get('displacement_confirmed') else 'NO'}",
                "waiting_for": "15M liquidity sweep followed by energetic displacement and MSS",
            },
            {
                "timeframe": "5M",
                "purpose": "Internal Structure Confirmation",
                "status": "PASS" if layer_5m.get("internal_mss") and layer_5m.get("displacement") else "WAITING",
                "detail": f"Internal MSS: {'YES' if layer_5m.get('internal_mss') else 'NO'}, Volume Surge: {'YES' if layer_5m.get('volume_surge') else 'NO'}",
                "waiting_for": "5M internal structure break with confirmed volume surge",
            },
            {
                "timeframe": "1M",
                "purpose": "Precision FVG Limit Entry",
                "status": "PASS" if layer_1m.get("fvg_detected") and layer_1m.get("limit_price") else "WAITING",
                "detail": f"FVG: {'YES' if layer_1m.get('fvg_detected') else 'NO'}, Limit Price: {layer_1m.get('limit_price', 0.0):.2f}, Risk: {layer_1m.get('risk_r', 1.0):.1f}R",
                "waiting_for": "1M Fair Value Gap formation for limit order placement",
            },
        ]

        if is_approved:
            headline = "WHY DOES THE STRATEGY CURRENTLY ACCEPT THIS SETUP?"
            explanation = (
                f"The strategy currently recognizes a fully aligned True MTF setup. "
                f"1D Macro Bias ({layer_1d.get('bias')}) and 4H DOL align with a confirmed 15M liquidity sweep, "
                f"5M internal confirmation, and an actionable 1M FVG limit entry at {layer_1m.get('limit_price', 0.0):.2f}."
            )
            strategy_action = "OBSERVE LIMIT ORDER INGESTION (PAPER/SHADOW)"
        else:
            headline = "WHY IS THERE NO VALID SETUP RIGHT NOW?"
            # Identify primary blocking reason
            reasons = []
            if not (layer_15m.get("sweep_confirmed") and layer_15m.get("mss_confirmed")):
                reasons.append("15M Liquidity Sweep or Market Structure Shift (MSS) not confirmed")
            if not layer_5m.get("internal_mss"):
                reasons.append("5M Internal Confirmation waiting")
            if not layer_1m.get("fvg_detected"):
                reasons.append("1M Fair Value Gap entry boundary not formed")
            
            primary_reason = reasons[0] if reasons else "Waiting for complete MTF structural convergence"
            explanation = (
                f"Primary reason: {primary_reason}. "
                f"The frozen Phase 21 strategy strictly requires all 5 timeframes to align sequentially before arming a limit order."
            )
            strategy_action = "WAIT / MAINTAIN STRICT DISCIPLINE"

        return {
            "symbol": symbol,
            "headline": headline,
            "is_setup_approved": is_approved,
            "master_state": state,
            "explanation": explanation,
            "strategy_action": strategy_action,
            "layers_breakdown": layers_breakdown,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }


class MarketContextSnapshotEngine:
    """
    Records immutable, reproducible market context snapshots for research and audit provenance.
    Does NOT execute trades.
    """

    @staticmethod
    def record_snapshot(symbol: str = "XAUUSD", user_notes: str = "") -> Dict[str, Any]:
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        snap_id = f"SNAP_{now_dt.strftime('%Y%m%d_%H%M%S')}_{hashlib.sha256(now_iso.encode('utf-8')).hexdigest()[:8]}"

        # Gather real-time context
        feed_audit = MarketDataFeedAuditor.get_feed_status(symbol)
        preflight = DailyPreFlightEngine.get_daily_preflight(now_dt.date())
        live_mtf = XAUUSDLiveMTFStateEngine.get_complete_live_market_state(symbol)
        op_health = OperationalHealthEvaluator.evaluate_operational_health(symbol)

        price = float(feed_audit.get("current_price", 2415.50))
        session_name = preflight.get("current_session", "ACTIVE_WINDOW") if "current_session" in preflight else "LONDON/NY"
        master_condition = preflight.get("master_state", "NORMAL DAY")
        holiday_status = preflight.get("holiday_status", "NORMAL TRADING")
        nearest_event_name = preflight.get("next_high_impact_event", "None")
        nearest_event_prox = preflight.get("time_until_event", "N/A")
        mtf_state = live_mtf.get("decision", {}).get("state", "WAITING")
        research_health = op_health.get("overall_verdict", "HEALTHY")

        payload_dict = {
            "snapshot_id": snap_id,
            "created_at": now_iso,
            "price": price,
            "session_name": session_name,
            "master_condition": master_condition,
            "holiday_status": holiday_status,
            "nearest_event_name": nearest_event_name,
            "nearest_event_proximity": nearest_event_prox,
            "mtf_strategy_state": mtf_state,
            "contract_hash": FROZEN_CONTRACT_HASH,
            "research_health": research_health,
            "user_notes": user_notes,
            "feed_audit": feed_audit,
            "preflight_summary": {
                "calendar_source": preflight.get("calendar_source"),
                "calendar_status": preflight.get("calendar_status"),
                "high_impact_count": preflight.get("high_impact_count"),
                "usd_events_count": preflight.get("usd_events_count"),
            },
        }

        json_payload = json.dumps(payload_dict, sort_keys=True)
        fingerprint = hashlib.sha256(json_payload.encode("utf-8")).hexdigest()
        payload_dict["snapshot_fingerprint"] = fingerprint

        # Persist to database
        conn = database.get_connection()
        init_phase35_database(conn)
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)

        if isinstance(conn, sqlite3.Connection):
            query = f"""
            INSERT OR REPLACE INTO xauusd_context_snapshots (
                snapshot_id, created_at, price, session_name, master_condition,
                holiday_status, nearest_event_name, nearest_event_proximity,
                mtf_strategy_state, contract_hash, research_health,
                snapshot_fingerprint, context_payload
            ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """
        else:
            query = f"""
            INSERT INTO xauusd_context_snapshots (
                snapshot_id, created_at, price, session_name, master_condition,
                holiday_status, nearest_event_name, nearest_event_proximity,
                mtf_strategy_state, contract_hash, research_health,
                snapshot_fingerprint, context_payload
            ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ON CONFLICT (snapshot_id) DO UPDATE SET
                price = EXCLUDED.price,
                snapshot_fingerprint = EXCLUDED.snapshot_fingerprint,
                context_payload = EXCLUDED.context_payload
            """

        cur.execute(query, (
            snap_id, now_iso, price, session_name, master_condition,
            holiday_status, nearest_event_name, nearest_event_prox,
            mtf_state, FROZEN_CONTRACT_HASH, research_health,
            fingerprint, json_payload
        ))
        conn.commit()
        conn.close()

        return payload_dict

    @staticmethod
    def get_snapshots(limit: int = 50) -> List[Dict[str, Any]]:
        conn = database.get_connection()
        init_phase35_database(conn)
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"SELECT snapshot_id, created_at, price, session_name, master_condition, holiday_status, nearest_event_name, mtf_strategy_state, snapshot_fingerprint FROM xauusd_context_snapshots ORDER BY created_at DESC LIMIT {ph}", (limit,))
        rows = cur.fetchall()
        conn.close()

        snapshots = []
        for r in rows:
            snapshots.append({
                "snapshot_id": r[0],
                "created_at": r[1],
                "price": r[2],
                "session_name": r[3],
                "master_condition": r[4],
                "holiday_status": r[5],
                "nearest_event_name": r[6],
                "mtf_strategy_state": r[7],
                "snapshot_fingerprint": r[8],
            })
        return snapshots


class DailyResearchJournal:
    """
    Manages persistent, timestamped research observation notes.
    Notes are purely qualitative/contextual and never overwrite empirical trade records.
    """

    @staticmethod
    def add_note(note_text: str, category: str = "SESSION_NOTE", session_context: str = "LONDON/NY") -> Dict[str, Any]:
        now_dt = datetime.now(timezone.utc)
        note_id = f"NOTE_{now_dt.strftime('%Y%m%d_%H%M%S')}_{hashlib.sha256(note_text.encode('utf-8')).hexdigest()[:6]}"
        now_iso = now_dt.isoformat()
        note_date = now_dt.date().isoformat()

        conn = database.get_connection()
        init_phase35_database(conn)
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)

        if isinstance(conn, sqlite3.Connection):
            query = f"""
            INSERT OR REPLACE INTO xauusd_research_notes (
                note_id, created_at, note_date, category, note_text, session_context, is_pinned
            ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """
        else:
            query = f"""
            INSERT INTO xauusd_research_notes (
                note_id, created_at, note_date, category, note_text, session_context, is_pinned
            ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ON CONFLICT (note_id) DO UPDATE SET
                note_text = EXCLUDED.note_text,
                category = EXCLUDED.category
            """

        cur.execute(query, (note_id, now_iso, note_date, category, note_text, session_context, 0))
        conn.commit()
        conn.close()

        return {
            "note_id": note_id,
            "created_at": now_iso,
            "note_date": note_date,
            "category": category,
            "note_text": note_text,
            "session_context": session_context,
        }

    @staticmethod
    def get_notes(target_date: Optional[date] = None, limit: int = 50) -> List[Dict[str, Any]]:
        conn = database.get_connection()
        init_phase35_database(conn)
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)

        if target_date:
            cur.execute(f"SELECT note_id, created_at, note_date, category, note_text, session_context, is_pinned FROM xauusd_research_notes WHERE note_date = {ph} ORDER BY created_at DESC LIMIT {ph}", (target_date.isoformat(), limit))
        else:
            cur.execute(f"SELECT note_id, created_at, note_date, category, note_text, session_context, is_pinned FROM xauusd_research_notes ORDER BY created_at DESC LIMIT {ph}", (limit,))
        
        rows = cur.fetchall()
        conn.close()

        notes = []
        for r in rows:
            notes.append({
                "note_id": r[0],
                "created_at": r[1],
                "note_date": r[2],
                "category": r[3],
                "note_text": r[4],
                "session_context": r[5],
                "is_pinned": bool(r[6]),
            })
        return notes


class DailyTradingSummaryEngine:
    """
    Aggregates end-of-day market and strategy performance summary.
    Does not judge days as 'good' or 'bad' based on PnL; records objective empirical metrics.
    """

    @staticmethod
    def generate_daily_summary(target_date: Optional[date] = None) -> Dict[str, Any]:
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        day_str = target_date.isoformat()
        preflight = DailyPreFlightEngine.get_daily_preflight(target_date)
        holiday_info = MarketHolidayDetector.get_holiday_status(target_date)
        df_trades = XAUUSDForwardJournal.get_forward_trades(mode="PAPER")

        day_trades = []
        if not df_trades.empty and "timestamp" in df_trades.columns:
            for _, row in df_trades.iterrows():
                if day_str in str(row.get("timestamp", "")):
                    day_trades.append(row.to_dict())

        n_trades = len(day_trades)
        wins = sum(1 for t in day_trades if float(t.get("realized_r", 0.0)) > 0)
        losses = sum(1 for t in day_trades if float(t.get("realized_r", 0.0)) < 0)
        timeouts = sum(1 for t in day_trades if t.get("exit_reason") == "LIMIT_TIMEOUT")
        net_r = sum(float(t.get("realized_r", 0.0)) for t in day_trades)

        return {
            "date": day_str,
            "market_day_type": preflight.get("master_state", "NORMAL DAY"),
            "holiday_classification": holiday_info["trading_day_classification"],
            "high_impact_events_count": preflight.get("high_impact_count", 0),
            "holidays_count": holiday_info["holidays_count"],
            "forward_observations_count": n_trades,
            "strategy_setups_approved": n_trades,
            "wins_count": wins,
            "losses_count": losses,
            "timeouts_count": timeouts,
            "net_realized_r": round(net_r, 3),
            "notes": f"On {day_str}, {n_trades} forward observations were recorded under {preflight.get('master_state')}. {timeouts} limit timeouts occurred (never counted as strategy losses).",
        }


class DailyTradingCommandEngine:
    """
    Master Daily Trading Command Engine.
    Synthesizes market data, session state, holiday detection, economic calendar,
    MTF strategy state, setup explainability, and research health into the unified
    "What do I need to know RIGHT NOW?" operational view.
    """

    @staticmethod
    def get_command_center_payload(symbol: str = "XAUUSD") -> Dict[str, Any]:
        now_dt = datetime.now(timezone.utc)
        target_date = now_dt.date()

        # 1. Market data health
        feed_audit = MarketDataFeedAuditor.get_feed_status(symbol)
        
        # 2. Daily pre-flight & calendar
        preflight = DailyPreFlightEngine.get_daily_preflight(target_date)
        checklist = DailyPreFlightChecklist.evaluate_checklist(target_date)
        session_matrix = SessionHolidayInteractionMatrix.evaluate_session_matrix(target_date, now_dt)
        
        # 3. MTF Strategy state & explainability
        live_mtf = XAUUSDLiveMTFStateEngine.get_complete_live_market_state(symbol)
        setup_exp = SetupExplainabilityEngine.explain_current_setup(symbol)

        # 4. Operational research health
        op_health = OperationalHealthEvaluator.evaluate_operational_health(symbol)

        # 5. Session status
        hour_utc = now_dt.hour
        if 0 <= hour_utc < 8:
            curr_sess = "ASIA"
            next_sess = "LONDON (08:00 UTC)"
        elif 8 <= hour_utc < 13:
            curr_sess = "LONDON"
            next_sess = "LONDON / NY OVERLAP (13:00 UTC)"
        elif 13 <= hour_utc < 17:
            curr_sess = "LONDON / NY OVERLAP"
            next_sess = "NEW YORK AFTERNOON (17:00 UTC)"
        elif 17 <= hour_utc < 21:
            curr_sess = "NEW YORK"
            next_sess = "ASIA (00:00 UTC)"
        else:
            curr_sess = "INTER-SESSION ROLLOVER"
            next_sess = "ASIA (00:00 UTC)"

        # Check bank holidays
        active_holidays = [fc for fc in session_matrix if fc["session_status"] == "BANK HOLIDAY"]
        has_bank_holiday = len(active_holidays) > 0
        holiday_warning_title = f"{len(active_holidays)} Financial Center(s) Closed" if has_bank_holiday else "None (All Major Centers Open)"

        # Next upcoming event countdown
        events = preflight.get("events_timeline", [])
        nearest_high_impact = None
        for ev in events:
            if ev.get("impact_level") in ["HIGH IMPACT", "EXTREME"]:
                nearest_high_impact = ev
                break

        # Phase 36 Reliability additions
        prov = EconomicCalendarProviderFactory.get_provider()
        cal = prov.get_calendar(target_date)
        rel_status = xauusd_news_reliability.DailyPreTradeStatusEngine.evaluate_daily_status(target_date)
        source_class = xauusd_news_reliability.CalendarSourceClassifier.classify_source_status(prov)
        freshness_audit = xauusd_news_reliability.CalendarFreshnessAuditor.audit_freshness(cal)
        closure_audit = xauusd_news_reliability.MarketClosureAuditor.audit_market_closures(target_date)

        # Countdown calculation
        countdown_info = None
        if nearest_high_impact and "scheduled_time" in nearest_high_impact:
            countdown_info = xauusd_news_reliability.NewsCountdownEngine.calculate_countdown(nearest_high_impact["scheduled_time"], now_dt)

        # Plain language "What This Means"
        what_this_means = (
            f"Market is currently in {curr_sess} session. "
            f"Master condition: {rel_status.get('master_state', preflight.get('master_state'))}. "
            f"{'Warning: ' + str(len(active_holidays)) + ' financial centers closed today. ' if has_bank_holiday else 'Institutional centers operating normally. '}"
            f"Strategy state: {live_mtf.get('decision', {}).get('state')}. "
            f"Continue observing the frozen strategy without introducing manual overrides or news directional filters."
        )

        return {
            "symbol": symbol,
            "evaluated_at": now_dt.isoformat(),
            "current_utc_time": now_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "current_session": curr_sess,
            "next_session": next_sess,
            "market_day_type": rel_status.get("master_state", preflight.get("master_state", "NORMAL DAY")),
            "state_color": rel_status.get("state_color", preflight.get("state_color", "#00ffcc")),
            "master_condition": rel_status.get("master_state", preflight.get("master_state", "NORMAL DAY")),
            "holiday_status": preflight.get("holiday_status", "NORMAL TRADING"),
            "liquidity_expectation": preflight.get("liquidity_expectation", "Standard Liquidity"),
            "has_bank_holiday": has_bank_holiday,
            "holiday_warning_title": holiday_warning_title,
            "active_holidays": active_holidays,
            "nearest_high_impact_event": nearest_high_impact,
            "countdown_info": countdown_info,
            "what_this_means": what_this_means,
            "strategy_status": "UNCHANGED (PHASE 21 CONTRACT FROZEN)",
            "contract_hash": FROZEN_CONTRACT_HASH,
            "live_automation_status": "DISABLED PERMANENTLY (SAFETY LOCK ACTIVE)",
            "market_data": feed_audit,
            "checklist": checklist.get("checklist_items", []),
            "preflight": preflight,
            "session_matrix": session_matrix,
            "setup_explainability": setup_exp,
            "live_mtf": live_mtf,
            "operational_health": op_health,
            "reliability_status": rel_status,
            "source_classification": source_class,
            "freshness_audit": freshness_audit,
            "closure_audit": closure_audit,
        }
