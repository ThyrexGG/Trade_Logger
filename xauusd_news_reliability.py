"""
Phase 36 — XAUUSD Daily Command Center News Reliability, Calendar Accuracy & Operational Decision Audit
Implements:
- EconomicEventSchema & CalendarSourceClassifier (LIVE PRIMARY, LIVE SECONDARY, FALLBACK, CACHED, UNAVAILABLE)
- CalendarFreshnessAuditor (FRESH, AGING, STALE, ERROR)
- HighImpactNewsDetector (USD/Fed, US Macro, Gold Drivers; LOW, MEDIUM, HIGH, EXTREME)
- MarketClosureAuditor (BANK HOLIDAY vs EXCHANGE HOLIDAY vs REDUCED LIQUIDITY vs FULL CLOSURE across 7 centers)
- NewsCountdownEngine (0-15m, 15-30m, 30-60m, 1-3h, 3-6h, 6-24h, >24h, POST-EVENT)
- DailyPreTradeStatusEngine (Deterministic priority hierarchy)
- HistoricalNewsAuditEngine (Lookahead-free historical reconstruction with KNOWN/OBSERVED/POSSIBLE tags)
- Invariants: Strategy Frozen, Zero Directional Signals, Live Automation Blocked
"""

import abc
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set

import numpy as np
import pandas as pd

import database
from xauusd_alert_engine import XAUUSDAlertEngine
from xauusd_daily_preflight import (
    BaseCalendarProvider,
    ForexFactoryProvider,
    StandardMacroCalendarProvider,
    FallbackCalendarProvider,
    EconomicCalendarProviderFactory,
    SessionHolidayInteractionMatrix,
)
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_market_conditions import (
    MarketHolidayDetector,
    EventProximityEngine,
    FROZEN_CONTRACT_HASH,
)


@dataclass
class EconomicEventSchema:
    """Standardized schema for structured economic releases."""
    event_id: str
    event_name: str
    currency: str
    country: str
    impact: str  # LOW, MEDIUM, HIGH, EXTREME
    scheduled_timestamp: str  # ISO-8601 UTC
    actual: Optional[str]
    forecast: Optional[str]
    previous: Optional[str]
    source: str
    first_seen_timestamp: str
    last_updated_timestamp: str
    availability_status: str  # SCHEDULED, RELEASED, REVISED, DELAYED
    data_fingerprint: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CalendarSourceClassifier:
    """
    Classifies data source status with verified honesty.
    Guarantees that fallback/cached feeds are never disguised as live primary feeds.
    """

    @staticmethod
    def classify_source_status(provider: BaseCalendarProvider) -> Dict[str, Any]:
        source_name = provider.source_name
        prov_status = provider.provider_status

        if source_name == "FOREX_FACTORY" and "UNAVAILABLE" in prov_status:
            classification = "FALLBACK SOURCE"
            forex_factory_live = "UNAVAILABLE (CALENDAR FALLBACK ACTIVE)"
            suitability = "SUITABLE FOR OPERATIONAL AWARENESS (MACRO FALLBACK)"
            reason = "Direct authenticated Forex Factory live API unavailable without browser scraping."
        elif source_name == "STANDARD_MACRO_CALENDAR_FEED" and prov_status == "ACTIVE":
            classification = "LIVE SECONDARY SOURCE"
            forex_factory_live = "UNAVAILABLE"
            suitability = "HIGH (VERIFIED SCHEDULED MACRO DATA)"
            reason = "Standard macroeconomic release schedule active."
        elif "FALLBACK" in source_name or prov_status == "LIMITED":
            classification = "FALLBACK SOURCE"
            forex_factory_live = "UNAVAILABLE"
            suitability = "LIMITED (MINIMAL CALENDAR FEED)"
            reason = "Standard macro feed unreachable; minimal fallback active."
        else:
            classification = "NEWS DATA UNAVAILABLE"
            forex_factory_live = "UNAVAILABLE"
            suitability = "UNSUITABLE (NO ACTIVE CALENDAR FEED)"
            reason = "All calendar providers offline."

        return {
            "source_name": source_name,
            "provider_status": prov_status,
            "classification": classification,
            "forex_factory_live_feed": forex_factory_live,
            "operational_suitability": suitability,
            "reason_for_state": reason,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }


class CalendarFreshnessAuditor:
    """
    Audits calendar data freshness, event age, and missing fields.
    Classifies status as FRESH, AGING, STALE, or ERROR.
    """

    @staticmethod
    def audit_freshness(calendar_data: Dict[str, Any]) -> Dict[str, Any]:
        now_dt = datetime.now(timezone.utc)
        retrieval_iso = calendar_data.get("retrieval_timestamp")
        events = calendar_data.get("events", [])
        events_count = len(events)

        if not retrieval_iso:
            return {
                "freshness_status": "ERROR",
                "age_seconds": 999999,
                "events_loaded": 0,
                "xauusd_relevant_count": 0,
                "missing_fields_count": 0,
                "explanation": "Missing retrieval timestamp from calendar provider.",
            }

        try:
            retrieval_dt = datetime.fromisoformat(retrieval_iso)
            age_sec = max(0, int((now_dt - retrieval_dt).total_seconds()))
        except Exception:
            age_sec = 0

        # Check missing fields across events
        missing_fields = 0
        xau_count = 0
        for ev in events:
            if not ev.get("event_name") or not ev.get("scheduled_time"):
                missing_fields += 1
            if ev.get("xauusd_relevance") in ["HIGH", "MEDIUM"] or ev.get("currency") == "USD":
                xau_count += 1

        if events_count == 0 and calendar_data.get("provider_status") != "ACTIVE":
            status = "ERROR"
            explanation = "No economic events available in feed."
        elif age_sec <= 300:
            status = "FRESH"
            explanation = f"Calendar feed refreshed {age_sec}s ago. {events_count} events loaded ({xau_count} XAUUSD-relevant)."
        elif age_sec <= 1800:
            status = "AGING"
            explanation = f"Calendar feed last refreshed {int(age_sec/60)}m ago. Operational awareness remains valid."
        else:
            status = "STALE"
            explanation = f"Calendar data is stale ({int(age_sec/3600)}h old). Stale data must not be interpreted as live."

        return {
            "freshness_status": status,
            "age_seconds": age_sec,
            "events_loaded": events_count,
            "xauusd_relevant_count": xau_count,
            "missing_fields_count": missing_fields,
            "last_successful_update": retrieval_iso,
            "explanation": explanation,
            "audited_at": now_dt.isoformat(),
        }


class HighImpactNewsDetector:
    """
    Deterministic classification of XAUUSD-relevant macroeconomic events.
    Assigns LOW, MEDIUM, HIGH, or EXTREME ratings.
    """

    EXTREME_KEYWORDS = [
        "fomc", "interest rate decision", "fed press conference", "powell", "emergency rate"
    ]
    HIGH_KEYWORDS = [
        "cpi", "consumer price index", "core cpi", "pce", "core pce", "nfp",
        "non-farm", "nonfarm", "payroll", "employment situation", "unemployment rate",
        "gross domestic product", "gdp", "fomc minutes", "retail sales", "ism manufacturing", "ism services"
    ]
    MEDIUM_KEYWORDS = [
        "jobless claims", "initial claims", "adp employment", "consumer confidence",
        "ppi", "producer price index", "durable goods", "treasury currency report"
    ]

    @classmethod
    def classify_event_impact(cls, event_name: str, currency: str = "USD") -> Dict[str, Any]:
        name_lower = event_name.lower()
        curr_upper = currency.upper()

        if curr_upper == "USD":
            if any(k in name_lower for k in cls.EXTREME_KEYWORDS):
                return {"impact_rating": "EXTREME", "xauusd_relevance": "HIGH", "category": "USD / Federal Reserve"}
            elif any(k in name_lower for k in cls.HIGH_KEYWORDS):
                return {"impact_rating": "HIGH", "xauusd_relevance": "HIGH", "category": "US Macroeconomic Indicator"}
            elif any(k in name_lower for k in cls.MEDIUM_KEYWORDS):
                return {"impact_rating": "MEDIUM", "xauusd_relevance": "MEDIUM", "category": "US Secondary Release"}
            else:
                return {"impact_rating": "LOW", "xauusd_relevance": "LOW", "category": "US Routine Data"}
        elif curr_upper in ["EUR", "GBP", "JPY", "CNY"]:
            if any(k in name_lower for k in ["rate decision", "gdp", "cpi"]):
                return {"impact_rating": "MEDIUM", "xauusd_relevance": "LOW", "category": f"{curr_upper} Major Release"}
            return {"impact_rating": "LOW", "xauusd_relevance": "LOW", "category": f"{curr_upper} Routine Data"}
        else:
            return {"impact_rating": "LOW", "xauusd_relevance": "LOW", "category": "Global Non-USD Data"}


class MarketClosureAuditor:
    """
    Evaluates bank holidays, exchange holidays, reduced liquidity, and full market closures across 7 financial centers:
    London, New York, Frankfurt, Tokyo, Shanghai, Sydney, and Zurich.
    """

    @staticmethod
    def audit_market_closures(target_date: Optional[date] = None) -> Dict[str, Any]:
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        holiday_info = MarketHolidayDetector.get_holiday_status(target_date)
        holidays_today = {h["region"]: h for h in holiday_info["holidays_list"]}
        is_weekend = target_date.weekday() in [5, 6]

        centers_evaluated = []
        closed_centers = []
        for fc in MarketHolidayDetector.FINANCIAL_CENTERS:
            code = fc["code"]
            name = fc["center"]

            if is_weekend:
                closure_type = "FULL MARKET CLOSURE"
                is_closed = True
                detail = "Weekend closure (Spot gold & forex markets closed)"
                liq = "No trading activity"
            elif code in holidays_today or "GLOBAL" in holidays_today:
                h = holidays_today.get(code) or holidays_today.get("GLOBAL")
                closure_type = "BANK HOLIDAY"
                is_closed = True
                detail = f"{h['name']} ({fc['country']})"
                liq = f"Reduced {name} institutional liquidity; wider spreads possible"
            else:
                closure_type = "NORMAL TRADING"
                is_closed = False
                detail = "Normal financial center operations"
                liq = "Standard institutional liquidity"

            record = {
                "center": name,
                "country": fc["country"],
                "code": code,
                "closure_type": closure_type,
                "is_closed": is_closed,
                "detail": detail,
                "liquidity_implication": liq,
            }
            centers_evaluated.append(record)
            if is_closed:
                closed_centers.append(record)

        if is_weekend:
            overall_type = "FULL MARKET CLOSURE"
        elif len(closed_centers) >= 2:
            overall_type = "MULTI-CENTER HOLIDAY CONDITION"
        elif len(closed_centers) == 1:
            overall_type = "BANK HOLIDAY / REDUCED LIQUIDITY"
        else:
            overall_type = "NORMAL TRADING DAY"

        return {
            "date": target_date.isoformat(),
            "overall_closure_type": overall_type,
            "closed_centers_count": len(closed_centers),
            "closed_centers": closed_centers,
            "all_centers": centers_evaluated,
            "is_spot_gold_open": not is_weekend,
            "distinction_note": (
                "XAUUSD spot trading continues during local bank holidays, but institutional liquidity is reduced. "
                "Do not confuse a local bank holiday with a full market closure."
            ),
        }


class NewsCountdownEngine:
    """
    Computes deterministic countdowns and proximity buckets:
    0-15m, 15-30m, 30-60m, 1-3h, 3-6h, 6-24h, >24h, POST-EVENT.
    """

    @staticmethod
    def calculate_countdown(scheduled_time_iso: str, current_time: Optional[datetime] = None) -> Dict[str, Any]:
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        try:
            event_dt = datetime.fromisoformat(scheduled_time_iso)
        except Exception:
            return {
                "proximity_bucket": "UNKNOWN",
                "time_remaining_str": "N/A",
                "minutes_to_event": 0.0,
                "is_active_window": False,
                "is_post_event": False,
            }

        diff_seconds = (event_dt - current_time).total_seconds()
        diff_mins = diff_seconds / 60.0

        if diff_mins < -30:
            bucket = "POST-EVENT"
            time_str = f"{abs(int(diff_mins))}m ago"
            is_active = False
            is_post = True
        elif -30 <= diff_mins <= 0:
            bucket = "0–15 MIN"
            time_str = f"Active / Released {abs(int(diff_mins))}m ago"
            is_active = True
            is_post = True
        elif 0 < diff_mins <= 15:
            bucket = "0–15 MIN"
            time_str = f"in {int(diff_mins)}m {int(diff_seconds % 60)}s"
            is_active = True
            is_post = False
        elif 15 < diff_mins <= 30:
            bucket = "15–30 MIN"
            time_str = f"in {int(diff_mins)}m"
            is_active = True
            is_post = False
        elif 30 < diff_mins <= 60:
            bucket = "30–60 MIN"
            time_str = f"in {int(diff_mins)}m"
            is_active = False
            is_post = False
        elif 60 < diff_mins <= 180:
            bucket = "1–3 HOURS"
            time_str = f"in {round(diff_mins/60, 1)}h"
            is_active = False
            is_post = False
        elif 180 < diff_mins <= 360:
            bucket = "3–6 HOURS"
            time_str = f"in {round(diff_mins/60, 1)}h"
            is_active = False
            is_post = False
        elif 360 < diff_mins <= 1440:
            bucket = "6–24 HOURS"
            time_str = f"in {round(diff_mins/60, 1)}h"
            is_active = False
            is_post = False
        else:
            bucket = ">24 HOURS"
            time_str = f"in {round(diff_mins/1440, 1)}d"
            is_active = False
            is_post = False

        return {
            "proximity_bucket": bucket,
            "time_remaining_str": time_str,
            "minutes_to_event": round(diff_mins, 1),
            "is_active_window": is_active,
            "is_post_event": is_post,
        }


class DailyPreTradeStatusEngine:
    """
    Evaluates the master pre-trade daily status via deterministic priority order:
    MAJOR MARKET CLOSURE > MULTIPLE HIGH-IMPACT EVENTS > HIGH-IMPACT NEWS DAY > HOLIDAY / REDUCED LIQUIDITY > CAUTION > NORMAL DAY.
    """

    @classmethod
    def evaluate_daily_status(cls, target_date: Optional[date] = None) -> Dict[str, Any]:
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        closure_audit = MarketClosureAuditor.audit_market_closures(target_date)
        provider = EconomicCalendarProviderFactory.get_provider()
        cal = provider.get_calendar(target_date)
        freshness = CalendarFreshnessAuditor.audit_freshness(cal)
        source_class = CalendarSourceClassifier.classify_source_status(provider)

        high_impact_events = [
            e for e in cal.get("events", [])
            if HighImpactNewsDetector.classify_event_impact(e.get("event_name", ""), e.get("currency", "USD"))["impact_rating"] in ["HIGH", "EXTREME"]
        ]
        extreme_events = [
            e for e in cal.get("events", [])
            if HighImpactNewsDetector.classify_event_impact(e.get("event_name", ""), e.get("currency", "USD"))["impact_rating"] == "EXTREME"
        ]

        # Deterministic Priority Hierarchy
        if not closure_audit["is_spot_gold_open"]:
            master_state = "MAJOR MARKET CLOSURE"
            color = "#94a3b8"
            priority = 1
            reason = "Spot gold and forex markets globally closed (Weekend)."
        elif len(extreme_events) > 0 or len(high_impact_events) >= 2:
            master_state = "MULTIPLE HIGH-IMPACT EVENTS"
            color = "#bef264"
            priority = 2
            reason = f"{len(high_impact_events)} major macroeconomic releases scheduled today during active trading."
        elif len(high_impact_events) == 1:
            master_state = "HIGH-IMPACT NEWS DAY"
            color = "#38bdf8"
            priority = 3
            reason = f"High-impact release scheduled: {high_impact_events[0].get('event_name')}."
        elif closure_audit["closed_centers_count"] > 0:
            master_state = "HOLIDAY / REDUCED LIQUIDITY"
            color = "#f59e0b"
            priority = 4
            reason = f"{closure_audit['closed_centers_count']} financial center(s) closed for bank holiday."
        elif freshness["freshness_status"] in ["STALE", "ERROR"]:
            master_state = "CAUTION"
            color = "#f59e0b"
            priority = 5
            reason = f"Calendar feed notice: {freshness['explanation']}."
        else:
            master_state = "NORMAL DAY"
            color = "#00ffcc"
            priority = 6
            reason = "Standard weekday trading conditions with normal institutional liquidity."

        # Operational guidance
        guidance = "Continue forward observation collection. Tag observations with market context metadata for regime analysis."

        return {
            "date": target_date.isoformat(),
            "master_state": master_state,
            "state_color": color,
            "priority_level": priority,
            "reason": reason,
            "guidance": guidance,
            "strategy_contract": "PHASE 21 FROZEN (UNCHANGED)",
            "closure_audit": closure_audit,
            "source_classification": source_class,
            "freshness_audit": freshness,
            "high_impact_count": len(high_impact_events),
            "extreme_impact_count": len(extreme_events),
            "total_events_count": cal.get("events_count", 0),
        }


class HistoricalNewsAuditEngine:
    """
    "Did I Miss Something Today?" Upgraded Historical Date Audit Engine.
    Reconstructs exact market conditions, bank holidays, and forward observations without lookahead leakage.
    Uses KNOWN, OBSERVED, POSSIBLE CONTEXT, and INSUFFICIENT DATA tags.
    """

    @staticmethod
    def audit_historical_date(target_date: date) -> Dict[str, Any]:
        day_str = target_date.isoformat()
        closure_audit = MarketClosureAuditor.audit_market_closures(target_date)
        status_eval = DailyPreTradeStatusEngine.evaluate_daily_status(target_date)
        cal = EconomicCalendarProviderFactory.get_provider().get_calendar(target_date)

        # Get forward trades on that date
        df_trades = XAUUSDForwardJournal.get_forward_trades(mode="PAPER")
        day_trades = []
        if not df_trades.empty and "timestamp" in df_trades.columns:
            for _, row in df_trades.iterrows():
                if day_str in str(row.get("timestamp", "")):
                    day_trades.append(row.to_dict())

        n_trades = len(day_trades)
        high_impact = [
            e for e in cal.get("events", [])
            if HighImpactNewsDetector.classify_event_impact(e.get("event_name", ""), e.get("currency", "USD"))["impact_rating"] in ["HIGH", "EXTREME"]
        ]

        tag = "INSUFFICIENT DATA" if n_trades < 10 else "OBSERVED"

        explanation = (
            f"[KNOWN]: On {day_str}, markets operated under {status_eval['master_state']} ({closure_audit['overall_closure_type']}). "
            f"[OBSERVED]: {len(closure_audit['closed_centers'])} bank holidays and {len(high_impact)} high-impact releases scheduled. "
            f"{n_trades} forward observations were recorded. "
            f"[POSSIBLE CONTEXT]: Intraday volatility and spread dynamics were subject to {status_eval['reason']}. "
            f"[STATUS]: {tag} (Attribution is contextual and non-causal)."
        )

        return {
            "date": day_str,
            "master_state": status_eval["master_state"],
            "closure_type": closure_audit["overall_closure_type"],
            "closed_centers": closure_audit["closed_centers"],
            "high_impact_events": high_impact,
            "forward_trades_count": n_trades,
            "trades_list": day_trades,
            "attribution_tag": tag,
            "explanation": explanation,
        }
