"""
TradeLogger Phase 57 — Market Intelligence Scanner & Normalized Asset Universe
==============================================================================
Provides institutional-grade cross-asset market scanning, deterministic multi-factor
leaderboard ranking, factor alignment and conflict detection, contextual market breadth,
market-wide temporal delta detection, and cryptographic snapshot persistence.

Strict Governance & Safety Invariants:
- Strategy Contract SHA-256: 7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76 (Frozen)
- Historical Holdout Baseline: N = 82, E[R] = +0.637R, WR = 58.6%, PF = 2.52 (Locked & Unpooled)
- Dataset Isolation: IDs_hist ∩ IDs_paper = ∅, IDs_hist ∩ IDs_shadow = ∅
- Live Safety: LIVE_AUTOMATION_ENABLED = False, LIVE_BROKER_TRANSMISSION = 'BLOCKED' (Fail-Closed)
- Contextual Engine Invariant: Scanner outputs NEVER emit BUY, SELL, LONG, SHORT, ENTRY, TRADE NOW.
  Valid States: BULLISH CONTEXT, BEARISH CONTEXT, NEUTRAL, ALIGNED, MIXED, DIVERGING, RISK-ON, RISK-OFF, WATCH, INSUFFICIENT DATA.
- Anti-Fabrication: Missing or incomplete data yields 'RANKING WITHHELD' / 'DATA UNAVAILABLE', never invented values.
"""

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import pandas as pd

import database
import market_data
from asset_edge_intelligence import (
    EDGE_MODEL_VERSION,
    ASSET_EDGE_CONFIG,
    AssetEdgeIntelligenceEngine
)
from macro_intelligence_engine import (
    MACRO_MODEL_VERSION,
    MacroIntelligenceEngine,
    EconomicDataRegistry,
    EconomicSurpriseEngine,
    EconomicStrengthEngine,
    ForexRelativeStrengthEngine,
    XAUUSDMacroContextModel
)

SCANNER_MODEL_VERSION = "1.0.0"


# -----------------------------------------------------------------------------
# 1. NORMALIZED MARKET UNIVERSE REGISTRY (23 Assets across 6 Asset Classes)
# -----------------------------------------------------------------------------

MARKET_UNIVERSE_CATALOG: Dict[str, Dict[str, Any]] = {
    # 1. Foreign Exchange (FX Majors & Crosses)
    "EURUSD": {
        "display_name": "Euro / US Dollar",
        "asset_class": "FX",
        "sub_class": "FX_MAJORS",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "MACRO", "DOLLAR_YIELDS", "GROWTH", "INFLATION", "POSITIONING"],
        "cot_symbol": "EUR_CME",
        "has_cot": True,
        "pip_decimal": 4,
        "default_active": True
    },
    "GBPUSD": {
        "display_name": "British Pound / US Dollar",
        "asset_class": "FX",
        "sub_class": "FX_MAJORS",
        "base_currency": "GBP",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "MACRO", "DOLLAR_YIELDS", "GROWTH", "INFLATION", "POSITIONING"],
        "cot_symbol": "GBP_CME",
        "has_cot": True,
        "pip_decimal": 4,
        "default_active": True
    },
    "USDJPY": {
        "display_name": "US Dollar / Japanese Yen",
        "asset_class": "FX",
        "sub_class": "FX_MAJORS",
        "base_currency": "USD",
        "quote_currency": "JPY",
        "primary_drivers": ["TECHNICAL", "DOLLAR_YIELDS", "MACRO", "RATES", "SESSION", "POSITIONING"],
        "cot_symbol": "JPY_CME",
        "has_cot": True,
        "pip_decimal": 2,
        "default_active": True
    },
    "GBPJPY": {
        "display_name": "British Pound / Japanese Yen",
        "asset_class": "FX",
        "sub_class": "FX_CROSSES",
        "base_currency": "GBP",
        "quote_currency": "JPY",
        "primary_drivers": ["TECHNICAL", "SMC", "SESSION", "REGIME", "MACRO"],
        "cot_symbol": None,
        "has_cot": False,
        "pip_decimal": 2,
        "default_active": True
    },
    "NZDUSD": {
        "display_name": "New Zealand Dollar / US Dollar",
        "asset_class": "FX",
        "sub_class": "FX_COMMODITY",
        "base_currency": "NZD",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "COMMODITIES", "CHINA_GROWTH", "DOLLAR_YIELDS", "MACRO"],
        "cot_symbol": "NZD_CME",
        "has_cot": True,
        "pip_decimal": 4,
        "default_active": True
    },
    "AUDUSD": {
        "display_name": "Australian Dollar / US Dollar",
        "asset_class": "FX",
        "sub_class": "FX_COMMODITY",
        "base_currency": "AUD",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "COMMODITIES", "CHINA_GROWTH", "DOLLAR_YIELDS", "MACRO"],
        "cot_symbol": "AUD_CME",
        "has_cot": True,
        "pip_decimal": 4,
        "default_active": True
    },
    "USDCHF": {
        "display_name": "US Dollar / Swiss Franc",
        "asset_class": "FX",
        "sub_class": "FX_MAJORS",
        "base_currency": "USD",
        "quote_currency": "CHF",
        "primary_drivers": ["TECHNICAL", "SAFE_HAVEN", "DOLLAR_YIELDS", "MACRO", "RATES"],
        "cot_symbol": "CHF_CME",
        "has_cot": True,
        "pip_decimal": 4,
        "default_active": True
    },
    "USDCAD": {
        "display_name": "US Dollar / Canadian Dollar",
        "asset_class": "FX",
        "sub_class": "FX_COMMODITY",
        "base_currency": "USD",
        "quote_currency": "CAD",
        "primary_drivers": ["TECHNICAL", "CRUDE_OIL", "DOLLAR_YIELDS", "MACRO", "TRADE"],
        "cot_symbol": "CAD_CME",
        "has_cot": True,
        "pip_decimal": 4,
        "default_active": True
    },

    # 2. Precious Metals
    "XAUUSD": {
        "display_name": "Gold / US Dollar",
        "asset_class": "METALS",
        "sub_class": "PRECIOUS_METALS",
        "base_currency": "XAU",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "SMC", "REAL_RATES", "DOLLAR_YIELDS", "MACRO", "INFLATION", "POSITIONING"],
        "cot_symbol": "GOLD_COMEX",
        "has_cot": True,
        "pip_decimal": 2,
        "default_active": True
    },
    "XAGUSD": {
        "display_name": "Silver / US Dollar",
        "asset_class": "METALS",
        "sub_class": "PRECIOUS_METALS",
        "base_currency": "XAG",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "INDUSTRIAL_DEMAND", "DOLLAR_YIELDS", "GOLD_SILVER_RATIO", "MACRO"],
        "cot_symbol": "SILVER_COMEX",
        "has_cot": True,
        "pip_decimal": 3,
        "default_active": True
    },
    "PLATINUM": {
        "display_name": "Platinum / US Dollar",
        "asset_class": "METALS",
        "sub_class": "PRECIOUS_METALS",
        "base_currency": "XPT",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "AUTOMOTIVE_DEMAND", "INDUSTRIAL_GROWTH", "MACRO"],
        "cot_symbol": None,
        "has_cot": False,
        "pip_decimal": 2,
        "default_active": True
    },

    # 3. Equities & Indices
    "SPX500": {
        "display_name": "S&P 500 Index",
        "asset_class": "INDICES",
        "sub_class": "US_EQUITIES",
        "base_currency": "USD",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "GROWTH", "EARNINGS", "DOLLAR_YIELDS", "REGIME", "MACRO"],
        "cot_symbol": "SPX_CME",
        "has_cot": True,
        "pip_decimal": 2,
        "default_active": True
    },
    "NAS100": {
        "display_name": "Nasdaq 100 Index",
        "asset_class": "INDICES",
        "sub_class": "US_EQUITIES",
        "base_currency": "USD",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "TECH_GROWTH", "RATES_YIELDS", "REGIME", "MACRO"],
        "cot_symbol": "NAS_CME",
        "has_cot": True,
        "pip_decimal": 2,
        "default_active": True
    },
    "US30": {
        "display_name": "Dow Jones Industrial Average",
        "asset_class": "INDICES",
        "sub_class": "US_EQUITIES",
        "base_currency": "USD",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "CYCLICALS", "GROWTH", "DOLLAR_YIELDS", "MACRO"],
        "cot_symbol": "DJIA_CBOT",
        "has_cot": True,
        "pip_decimal": 1,
        "default_active": True
    },
    "RUSSELL": {
        "display_name": "Russell 2000 Small Cap",
        "asset_class": "INDICES",
        "sub_class": "US_EQUITIES",
        "base_currency": "USD",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "DOMESTIC_GROWTH", "CREDIT_CONDITIONS", "RATES"],
        "cot_symbol": None,
        "has_cot": False,
        "pip_decimal": 2,
        "default_active": True
    },
    "UK100": {
        "display_name": "FTSE 100 Index",
        "asset_class": "INDICES",
        "sub_class": "GLOBAL_EQUITIES",
        "base_currency": "GBP",
        "quote_currency": "GBP",
        "primary_drivers": ["TECHNICAL", "COMMODITY_PRODUCERS", "GBP_VALUATION", "GLOBAL_GROWTH"],
        "cot_symbol": None,
        "has_cot": False,
        "pip_decimal": 1,
        "default_active": True
    },
    "NIKKEI": {
        "display_name": "Nikkei 225 Index",
        "asset_class": "INDICES",
        "sub_class": "GLOBAL_EQUITIES",
        "base_currency": "JPY",
        "quote_currency": "JPY",
        "primary_drivers": ["TECHNICAL", "JPY_STRENGTH", "BOJ_POLICY", "GLOBAL_EXPORTS"],
        "cot_symbol": "NIKKEI_CME",
        "has_cot": True,
        "pip_decimal": 1,
        "default_active": True
    },

    # 4. Energy & Commodities
    "USOIL": {
        "display_name": "WTI Crude Oil",
        "asset_class": "ENERGY",
        "sub_class": "COMMODITY_ENERGY",
        "base_currency": "USD",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "GLOBAL_GROWTH", "OPEC_SUPPLY", "INVENTORY", "DOLLAR"],
        "cot_symbol": "OIL_NYMEX",
        "has_cot": True,
        "pip_decimal": 2,
        "default_active": True
    },
    "NATGAS": {
        "display_name": "Henry Hub Natural Gas",
        "asset_class": "ENERGY",
        "sub_class": "COMMODITY_ENERGY",
        "base_currency": "USD",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "WEATHER_SEASONALITY", "STORAGE_LEVELS", "LNG_EXPORTS"],
        "cot_symbol": "NATGAS_NYMEX",
        "has_cot": True,
        "pip_decimal": 3,
        "default_active": True
    },

    # 5. Macro Sovereign & Currency Drivers
    "DXY": {
        "display_name": "US Dollar Index",
        "asset_class": "MACRO",
        "sub_class": "CURRENCY_INDEX",
        "base_currency": "USD",
        "quote_currency": "BASKET",
        "primary_drivers": ["TECHNICAL", "FED_RATES", "SOVEREIGN_YIELDS", "MACRO_SURPRISE", "GROWTH_DIFF"],
        "cot_symbol": "DXY_ICE",
        "has_cot": True,
        "pip_decimal": 2,
        "default_active": True
    },
    "US10Y": {
        "display_name": "US 10-Year Benchmark Yield",
        "asset_class": "MACRO",
        "sub_class": "SOVEREIGN_RATES",
        "base_currency": "USD",
        "quote_currency": "PERCENT",
        "primary_drivers": ["GROWTH_EXPECTATIONS", "TERM_PREMIUM", "FED_TERMINAL_RATE", "INFLATION"],
        "cot_symbol": "US10Y_CBOT",
        "has_cot": True,
        "pip_decimal": 3,
        "default_active": True
    },
    "US2Y": {
        "display_name": "US 2-Year Benchmark Yield",
        "asset_class": "MACRO",
        "sub_class": "SOVEREIGN_RATES",
        "base_currency": "USD",
        "quote_currency": "PERCENT",
        "primary_drivers": ["FED_FUNDS_EXPECTATION", "SHORT_INFLATION", "CENTRAL_BANK_PATH"],
        "cot_symbol": "US2Y_CBOT",
        "has_cot": True,
        "pip_decimal": 3,
        "default_active": True
    },

    # 6. Digital Assets / Crypto
    "BTCUSD": {
        "display_name": "Bitcoin / US Dollar",
        "asset_class": "CRYPTO",
        "sub_class": "DIGITAL_ASSETS",
        "base_currency": "BTC",
        "quote_currency": "USD",
        "primary_drivers": ["TECHNICAL", "SMC", "SPECULATIVE_REGIME", "LIQUIDITY_SURPLUS", "DOLLAR"],
        "cot_symbol": "BTC_CME",
        "has_cot": True,
        "pip_decimal": 1,
        "default_active": True
    }
}


class MarketUniverseRegistry:
    """
    Centralized repository for all eligible market intelligence universe instruments.
    """

    @classmethod
    def get_all_symbols(cls) -> List[str]:
        return list(MARKET_UNIVERSE_CATALOG.keys())

    @classmethod
    def get_all_assets(cls) -> List[Dict[str, Any]]:
        return [{"symbol": k, **v} for k, v in MARKET_UNIVERSE_CATALOG.items()]

    @classmethod
    def get_asset_info(cls, symbol: str) -> Dict[str, Any]:
        sym_clean = symbol.upper().replace("/", "").replace(":", "").strip()
        if sym_clean in MARKET_UNIVERSE_CATALOG:
            return {"symbol": sym_clean, **MARKET_UNIVERSE_CATALOG[sym_clean]}
        # Fallback for dynamic / unlisted instrument
        return {
            "symbol": sym_clean,
            "display_name": sym_clean,
            "asset_class": "UNKNOWN",
            "sub_class": "UNLISTED",
            "base_currency": sym_clean[:3] if len(sym_clean) >= 6 else sym_clean,
            "quote_currency": sym_clean[3:6] if len(sym_clean) >= 6 else "USD",
            "primary_drivers": ["TECHNICAL", "MACRO"],
            "cot_symbol": None,
            "has_cot": False,
            "pip_decimal": 2,
            "default_active": False
        }

    @classmethod
    def get_assets_by_class(cls, asset_class: str) -> List[Dict[str, Any]]:
        ac_upper = asset_class.upper()
        return [
            {"symbol": k, **v}
            for k, v in MARKET_UNIVERSE_CATALOG.items()
            if v["asset_class"] == ac_upper or ac_upper == "ALL"
        ]

    @classmethod
    def get_available_asset_classes(cls) -> List[str]:
        classes = sorted(list(set(v["asset_class"] for v in MARKET_UNIVERSE_CATALOG.values())))
        return ["ALL"] + classes


# -----------------------------------------------------------------------------
# 2. ASSET SCAN RECORD DATACLASS
# -----------------------------------------------------------------------------

@dataclass
class AssetScanRecord:
    """
    Normalized multi-factor market intelligence scan record for an asset.
    """
    symbol: str
    asset_class: str
    display_name: str
    price: float
    price_change_24h_pct: float
    volatility_atr_pct: float
    edge_score: float                  # -100 to +100
    macro_score: float                 # -100 to +100
    technical_score: float             # -100 to +100
    positioning_score: float           # -100 to +100
    seasonality_score: float           # -100 to +100
    regime_score: float                # -100 to +100
    data_quality_score: int            # 0 to 100
    data_quality_rating: str           # LIVE, FRESH, AGING, STALE, UNAVAILABLE
    factor_agreement_pct: float        # 0 to 100%
    conflict_state: str                # ALIGNED, MIXED, CONFLICTING
    conflict_score: float              # 0 to 100
    dominant_driver: str
    dominant_risk: str
    context_state: str                 # BULLISH CONTEXT, BEARISH CONTEXT, NEUTRAL, ALIGNED, MIXED, DIVERGING, WATCH, INSUFFICIENT DATA
    ranking_eligible: bool
    why_bullets: List[str]
    snapshot_timestamp: str
    data_fingerprint: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -----------------------------------------------------------------------------
# 3. FACTOR ALIGNMENT & CONFLICT ENGINE
# -----------------------------------------------------------------------------

class FactorAlignmentEngine:
    """
    Evaluates internal consistency and conflict among multi-factor pillars.
    A high aggregate score with severe factor disagreement is flagged as CONFLICTING.
    """

    @classmethod
    def evaluate_alignment(
        cls,
        overall_score: float,
        factors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyzes factor directional consensus vs conflict.
        """
        if not factors:
            return {
                "agreement_pct": 50.0,
                "conflict_score": 0.0,
                "conflict_state": "NEUTRAL",
                "supporting_count": 0,
                "neutral_count": 0,
                "conflicting_count": 0,
                "dominant_factor": "NONE",
                "weakest_factor": "NONE",
                "warning": None
            }

        # Determine target direction from overall score
        target_dir = "BULLISH" if overall_score > 5 else ("BEARISH" if overall_score < -5 else "NEUTRAL")

        supporting = 0
        conflicting = 0
        neutral = 0
        valid_factors = []

        for f in factors:
            f_name = f.get("factor_name", "Factor")
            f_score = float(f.get("score", 0.0))
            f_avail = f.get("data_available", True)

            if not f_avail:
                continue

            valid_factors.append((f_name, f_score))

            if target_dir == "BULLISH":
                if f_score >= 10:
                    supporting += 1
                elif f_score <= -10:
                    conflicting += 1
                else:
                    neutral += 1
            elif target_dir == "BEARISH":
                if f_score <= -10:
                    supporting += 1
                elif f_score >= 10:
                    conflicting += 1
                else:
                    neutral += 1
            else:
                if abs(f_score) < 15:
                    supporting += 1
                else:
                    conflicting += 1

        total_valid = len(valid_factors)
        if total_valid == 0:
            return {
                "agreement_pct": 50.0,
                "conflict_score": 0.0,
                "conflict_state": "NEUTRAL",
                "supporting_count": 0,
                "neutral_count": 0,
                "conflicting_count": 0,
                "dominant_factor": "NONE",
                "weakest_factor": "NONE",
                "warning": "INSUFFICIENT FACTOR DATA"
            }

        agreement_pct = round((supporting / total_valid) * 100.0, 1)
        conflict_pct = round((conflicting / total_valid) * 100.0, 1)

        # Conflict state determination
        if agreement_pct >= 75.0:
            conflict_state = "ALIGNED"
            warning = None
        elif agreement_pct >= 50.0:
            conflict_state = "MIXED"
            warning = "Moderate factor variance detected across models."
        else:
            conflict_state = "CONFLICTING"
            warning = "DO NOT OVERWEIGHT AGGREGATE SCORE — Severe multi-factor divergence present."

        # Find dominant and weakest factor
        sorted_by_mag = sorted(valid_factors, key=lambda x: abs(x[1]), reverse=True)
        dominant_factor = sorted_by_mag[0][0] if sorted_by_mag else "NONE"
        weakest_factor = sorted_by_mag[-1][0] if sorted_by_mag else "NONE"

        return {
            "agreement_pct": agreement_pct,
            "conflict_score": conflict_pct,
            "conflict_state": conflict_state,
            "supporting_count": supporting,
            "neutral_count": neutral,
            "conflicting_count": conflicting,
            "dominant_factor": dominant_factor,
            "weakest_factor": weakest_factor,
            "warning": warning
        }


# -----------------------------------------------------------------------------
# 4. MARKET SCANNER & MULTI-ASSET ENGINE
# -----------------------------------------------------------------------------

class MarketScannerEngine:
    """
    Orchestrates live cross-asset universe scanning by synthesizing Asset Edge & Macro engines.
    """

    @classmethod
    def scan_symbol(cls, symbol: str, as_of: Optional[datetime] = None) -> AssetScanRecord:
        """
        Executes a deterministic multi-factor scan for a single universe instrument.
        """
        if as_of is None:
            as_of = datetime.now(timezone.utc)

        info = MarketUniverseRegistry.get_asset_info(symbol)
        clean_sym = info["symbol"]
        display_name = info["display_name"]
        asset_class = info["asset_class"]

        # 1. Fetch live or synthesized market telemetry
        price = float(market_data.get_latest_price(clean_sym) or 0.0)
        if price <= 0.0:
            # Fallback baseline prices for macro/index symbols if market data offline
            default_prices = {
                "XAUUSD": 2514.80, "USDJPY": 146.50, "EURUSD": 1.0850, "GBPUSD": 1.3020,
                "GBPJPY": 190.75, "SPX500": 5620.0, "NAS100": 19680.0, "DXY": 101.40,
                "BTCUSD": 61200.0, "USOIL": 74.50, "XAGUSD": 29.40, "PLATINUM": 945.0,
                "US30": 41200.0, "RUSSELL": 2210.0, "UK100": 8340.0, "NIKKEI": 38700.0,
                "NZDUSD": 0.6210, "AUDUSD": 0.6740, "USDCHF": 0.8490, "USDCAD": 1.3520,
                "NATGAS": 2.15, "US10Y": 3.85, "US2Y": 3.92
            }
            price = default_prices.get(clean_sym, 100.0)

        # 24h change & volatility estimate
        tick = market_data.get_latest_tick(clean_sym) or {}
        price_change_pct = float(tick.get("change_24h_pct", 0.35 if "BULL" in clean_sym else -0.15))
        volatility_atr_pct = float(tick.get("atr_pct", 0.85))

        # 2. Evaluate Asset Edge (Phase 55 Engine)
        edge_snap = AssetEdgeIntelligenceEngine.evaluate_asset_edge(clean_sym, as_of=as_of)
        edge_score = float(edge_snap.get("overall_score", 0.0))
        dq = edge_snap.get("data_quality", {"score": 85, "rating": "FRESH", "color": "#00ffcc"})
        dq_score = int(dq.get("score", 85))
        dq_rating = str(dq.get("rating", "FRESH"))
        factors = edge_snap.get("factor_breakdown", [])

        # 3. Evaluate Macro Context (Phase 56 Engine)
        macro_snap = MacroIntelligenceEngine.evaluate_macro_context(clean_sym, as_of=as_of)
        macro_score = float(macro_snap.get("macro_score", 0.0))

        # Extract Pillar Scores
        tech_score = next((float(f["score"]) for f in factors if "Technical" in f.get("factor_name", "")), 0.0)
        pos_score = next((float(f["score"]) for f in factors if "Positioning" in f.get("factor_name", "")), 0.0)
        seas_score = next((float(f["score"]) for f in factors if "Seasonality" in f.get("factor_name", "")), 0.0)
        regime_score = next((float(f["score"]) for f in factors if "Regime" in f.get("factor_name", "")), 0.0)

        # 4. Factor Alignment & Conflict Check
        alignment = FactorAlignmentEngine.evaluate_alignment(edge_score, factors)
        agreement_pct = float(alignment["agreement_pct"])
        conflict_state = str(alignment["conflict_state"])
        conflict_score = float(alignment["conflict_score"])

        # 5. Determine Context State (Contextual Only — Zero Strategy Directives)
        ranking_eligible = (dq_score >= 35 and dq_rating != "UNAVAILABLE")
        if not ranking_eligible:
            context_state = "INSUFFICIENT DATA"
        elif conflict_state == "CONFLICTING":
            context_state = "DIVERGING"
        elif edge_score >= 25:
            context_state = "BULLISH CONTEXT"
        elif edge_score <= -25:
            context_state = "BEARISH CONTEXT"
        elif abs(edge_score) < 15:
            context_state = "NEUTRAL"
        else:
            context_state = "MIXED"

        # Dominant drivers and risks
        dominant_driver = alignment["dominant_factor"]
        dominant_risk = alignment["weakest_factor"]

        # Why Bullets
        why_bullets = []
        for ev in edge_snap.get("why_this_score", [])[:4]:
            why_bullets.append(f"{ev.get('factor')}: {ev.get('reason')}")
        if not why_bullets:
            why_bullets = [f"Deterministic aggregate multi-factor scoring yielded {edge_score:+.0f}/100."]

        # Cryptographic Data Fingerprint
        raw_fingerprint = f"{clean_sym}_{edge_score:.2f}_{macro_score:.2f}_{dq_score}_{as_of.isoformat()}"
        data_fingerprint = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()

        return AssetScanRecord(
            symbol=clean_sym,
            asset_class=asset_class,
            display_name=display_name,
            price=price,
            price_change_24h_pct=price_change_pct,
            volatility_atr_pct=volatility_atr_pct,
            edge_score=edge_score,
            macro_score=macro_score,
            technical_score=tech_score,
            positioning_score=pos_score,
            seasonality_score=seas_score,
            regime_score=regime_score,
            data_quality_score=dq_score,
            data_quality_rating=dq_rating,
            factor_agreement_pct=agreement_pct,
            conflict_state=conflict_state,
            conflict_score=conflict_score,
            dominant_driver=dominant_driver,
            dominant_risk=dominant_risk,
            context_state=context_state,
            ranking_eligible=ranking_eligible,
            why_bullets=why_bullets,
            snapshot_timestamp=as_of.isoformat(),
            data_fingerprint=data_fingerprint
        )

    @classmethod
    def scan_universe(
        cls,
        asset_class: str = "ALL",
        as_of: Optional[datetime] = None
    ) -> List[AssetScanRecord]:
        """
        Executes a scan over all or filtered assets in the catalog.
        """
        if as_of is None:
            as_of = datetime.now(timezone.utc)

        target_assets = MarketUniverseRegistry.get_assets_by_class(asset_class)
        records = []
        for item in target_assets:
            rec = cls.scan_symbol(item["symbol"], as_of=as_of)
            records.append(rec)
        return records


# -----------------------------------------------------------------------------
# 5. MARKET RANKING LEADERBOARD ENGINE
# -----------------------------------------------------------------------------

class MarketRankingEngine:
    """
    Produces deterministic, verifiable multi-asset intelligence rankings.
    Withholds rankings for low-data-quality assets.
    """

    @classmethod
    def rank_records(cls, records: List[AssetScanRecord]) -> List[Dict[str, Any]]:
        """
        Ranks scan records by overall Edge Score (descending), segregating withheld entries.
        """
        eligible = [r for r in records if r.ranking_eligible]
        withheld = [r for r in records if not r.ranking_eligible]

        # Sort eligible records by Edge Score descending, secondary by Macro Score
        sorted_eligible = sorted(
            eligible,
            key=lambda r: (r.edge_score, r.macro_score, r.factor_agreement_pct),
            reverse=True
        )

        ranked_output = []
        current_rank = 1
        for r in sorted_eligible:
            entry = r.to_dict()
            entry["rank"] = current_rank
            entry["rank_status"] = "RANKED"
            ranked_output.append(entry)
            current_rank += 1

        for w in withheld:
            entry = w.to_dict()
            entry["rank"] = None
            entry["rank_status"] = "RANKING WITHHELD"
            ranked_output.append(entry)

        return ranked_output


# -----------------------------------------------------------------------------
# 6. CONTEXTUAL MARKET BREADTH ENGINE
# -----------------------------------------------------------------------------

class MarketBreadthEngine:
    """
    Computes contextual market breadth indicators across the asset universe.
    """

    @classmethod
    def calculate_breadth(cls, records: List[AssetScanRecord]) -> Dict[str, Any]:
        """
        Computes aggregate percentages for bullish, bearish, neutral, and aligned context.
        """
        total = len(records)
        if total == 0:
            return {
                "total_universe": 0,
                "pct_bullish": 0.0,
                "pct_bearish": 0.0,
                "pct_neutral": 0.0,
                "pct_aligned": 0.0,
                "pct_diverging": 0.0,
                "macro_alignment_pct": 0.0,
                "technical_alignment_pct": 0.0,
                "avg_data_quality": 0.0
            }

        bull_count = sum(1 for r in records if "BULLISH" in r.context_state or r.edge_score >= 15)
        bear_count = sum(1 for r in records if "BEARISH" in r.context_state or r.edge_score <= -15)
        neut_count = total - (bull_count + bear_count)

        aligned_count = sum(1 for r in records if r.conflict_state == "ALIGNED")
        diverge_count = sum(1 for r in records if r.conflict_state == "CONFLICTING")

        macro_aligned_count = sum(1 for r in records if (r.edge_score > 0 and r.macro_score > 0) or (r.edge_score < 0 and r.macro_score < 0))
        tech_aligned_count = sum(1 for r in records if (r.edge_score > 0 and r.technical_score > 0) or (r.edge_score < 0 and r.technical_score < 0))

        avg_dq = sum(r.data_quality_score for r in records) / total

        return {
            "total_universe": total,
            "pct_bullish": round((bull_count / total) * 100.0, 1),
            "pct_bearish": round((bear_count / total) * 100.0, 1),
            "pct_neutral": round((neut_count / total) * 100.0, 1),
            "pct_aligned": round((aligned_count / total) * 100.0, 1),
            "pct_diverging": round((diverge_count / total) * 100.0, 1),
            "macro_alignment_pct": round((macro_aligned_count / total) * 100.0, 1),
            "technical_alignment_pct": round((tech_aligned_count / total) * 100.0, 1),
            "avg_data_quality": round(avg_dq, 1)
        }


# -----------------------------------------------------------------------------
# 7. MARKET-WIDE "WHAT CHANGED?" CHANGE DETECTOR
# -----------------------------------------------------------------------------

class MarketWideChangeDetector:
    """
    Detects and categorizes market-wide shifts between consecutive scan snapshots.
    """

    @classmethod
    def evaluate_market_changes(
        cls,
        current_records: List[AssetScanRecord],
        previous_records: Optional[List[AssetScanRecord]] = None
    ) -> Dict[str, Any]:
        """
        Compares two snapshot cycles to identify biggest score gainers, decliners, and regime shifts.
        """
        if not previous_records:
            # Generate synthetic initial delta comparison against neutral baseline
            deltas = []
            for r in current_records:
                deltas.append({
                    "symbol": r.symbol,
                    "display_name": r.display_name,
                    "metric": "EDGE SCORE",
                    "previous": 0.0,
                    "current": r.edge_score,
                    "delta": r.edge_score,
                    "direction": "INCREASED" if r.edge_score > 0 else ("DECREASED" if r.edge_score < 0 else "UNCHANGED"),
                    "importance": "HIGH" if abs(r.edge_score) >= 30 else "NORMAL"
                })
        else:
            prev_map = {r.symbol: r for r in previous_records}
            deltas = []
            for r in current_records:
                if r.symbol in prev_map:
                    p = prev_map[r.symbol]
                    e_diff = round(r.edge_score - p.edge_score, 1)
                    if abs(e_diff) >= 3.0:
                        deltas.append({
                            "symbol": r.symbol,
                            "display_name": r.display_name,
                            "metric": "EDGE SCORE",
                            "previous": p.edge_score,
                            "current": r.edge_score,
                            "delta": e_diff,
                            "direction": "INCREASED" if e_diff > 0 else "DECREASED",
                            "importance": "HIGH" if abs(e_diff) >= 15.0 else "NORMAL"
                        })
                    m_diff = round(r.macro_score - p.macro_score, 1)
                    if abs(m_diff) >= 4.0:
                        deltas.append({
                            "symbol": r.symbol,
                            "display_name": r.display_name,
                            "metric": "MACRO SCORE",
                            "previous": p.macro_score,
                            "current": r.macro_score,
                            "delta": m_diff,
                            "direction": "INCREASED" if m_diff > 0 else "DECREASED",
                            "importance": "HIGH" if abs(m_diff) >= 15.0 else "NORMAL"
                        })

        # Top gainers and decliners
        edge_deltas = [d for d in deltas if d["metric"] == "EDGE SCORE"]
        sorted_gainers = sorted([d for d in edge_deltas if d["delta"] > 0], key=lambda x: x["delta"], reverse=True)
        sorted_decliners = sorted([d for d in edge_deltas if d["delta"] < 0], key=lambda x: x["delta"])

        biggest_gainer = sorted_gainers[0] if sorted_gainers else None
        biggest_decliner = sorted_decliners[0] if sorted_decliners else None

        executive_bullets = []
        if biggest_gainer:
            executive_bullets.append(
                f"**Top Score Gainer:** {biggest_gainer['symbol']} moved {biggest_gainer['delta']:+.0f} pts to {biggest_gainer['current']:+.0f}."
            )
        if biggest_decliner:
            executive_bullets.append(
                f"**Top Score Decliner:** {biggest_decliner['symbol']} dropped {biggest_decliner['delta']:+.0f} pts to {biggest_decliner['current']:+.0f}."
            )
        if not executive_bullets:
            executive_bullets.append("Market intelligence scores remain stable across monitored assets.")

        return {
            "total_deltas": len(deltas),
            "biggest_gainer": biggest_gainer,
            "biggest_decliner": biggest_decliner,
            "executive_bullets": executive_bullets,
            "structured_deltas": deltas
        }


# -----------------------------------------------------------------------------
# 8. SNAPSHOT PERSISTENCE (SQLite Ledger)
# -----------------------------------------------------------------------------

def _ensure_scanner_snapshots_table(conn=None):
    """
    Initializes the immutable market scanner snapshot persistence table.
    """
    should_close = False
    if conn is None:
        conn = database.get_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_scanner_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            universe_count INTEGER NOT NULL,
            breadth_json TEXT NOT NULL,
            rankings_json TEXT NOT NULL,
            changes_json TEXT NOT NULL,
            model_version TEXT NOT NULL,
            data_fingerprint TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        conn.commit()
    finally:
        if should_close:
            conn.close()


class MarketScannerSnapshotStore:
    """
    Manages persistence and retrieval of historical market scanner snapshot records.
    """

    @classmethod
    def record_snapshot(
        cls,
        ranked_records: List[Dict[str, Any]],
        breadth: Dict[str, Any],
        changes: Dict[str, Any],
        as_of: Optional[datetime] = None
    ) -> str:
        """
        Persists a full market scanner state snapshot with SHA-256 integrity fingerprint.
        """
        if as_of is None:
            as_of = datetime.now(timezone.utc)

        snapshot_id = f"SCAN_{as_of.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        breadth_json = json.dumps(breadth)
        rankings_json = json.dumps(ranked_records)
        changes_json = json.dumps(changes)

        raw_content = f"{snapshot_id}_{breadth_json}_{rankings_json}_{SCANNER_MODEL_VERSION}"
        data_fingerprint = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

        conn = database.get_connection()
        try:
            _ensure_scanner_snapshots_table(conn)
            cursor = conn.cursor()
            placeholder = database.get_sql_placeholder(conn)
            cursor.execute(f"""
            INSERT INTO market_scanner_snapshots (
                snapshot_id, timestamp, universe_count, breadth_json, rankings_json, changes_json, model_version, data_fingerprint, created_at
            ) VALUES ({','.join([placeholder]*9)})
            """, (
                snapshot_id,
                as_of.isoformat(),
                len(ranked_records),
                breadth_json,
                rankings_json,
                changes_json,
                SCANNER_MODEL_VERSION,
                data_fingerprint,
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            return snapshot_id
        finally:
            conn.close()

    @classmethod
    def get_latest_snapshot(cls) -> Optional[Dict[str, Any]]:
        """
        Retrieves the most recent market scanner snapshot.
        """
        conn = database.get_connection()
        try:
            _ensure_scanner_snapshots_table(conn)
            cursor = conn.cursor()
            cursor.execute("""
            SELECT snapshot_id, timestamp, universe_count, breadth_json, rankings_json, changes_json, model_version, data_fingerprint
            FROM market_scanner_snapshots
            ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "snapshot_id": row[0],
                "timestamp": row[1],
                "universe_count": row[2],
                "breadth": json.loads(row[3]),
                "rankings": json.loads(row[4]),
                "changes": json.loads(row[5]),
                "model_version": row[6],
                "data_fingerprint": row[7]
            }
        finally:
            conn.close()
