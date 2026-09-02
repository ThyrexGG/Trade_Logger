# -*- coding: utf-8 -*-
"""
FastAPI Market Intelligence Router — Stage 3 Read-Only Intelligence Endpoints
Directly consumes UnifiedMarketIntelligenceAggregator, MarketScannerEngine,
AssetContextProfileEngine, and EconomicHeatmapEngine without formula duplication.
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException

from api.schemas import (
    IntelligenceSummaryResponse,
    OpportunityMapResponse,
    OpportunityMapItem,
    AssetProfileResponse,
    EconomicHeatmapResponse,
    EconomyHeatmapRow
)
from market_intelligence_command_center import (
    UnifiedMarketIntelligenceAggregator,
    AssetContextProfileEngine
)
from market_intelligence_scanner import MarketScannerEngine, MarketRankingEngine
from economic_heatmap import EconomicHeatmapEngine

router = APIRouter(prefix="/api/intelligence", tags=["Market Intelligence"])


@router.get("/summary", response_model=IntelligenceSummaryResponse)
async def get_intelligence_summary() -> IntelligenceSummaryResponse:
    """
    Returns 3-second executive market summary (primary regime, breadth, macro environment, data health).
    """
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    regime = snap.regime_snapshot
    breadth = snap.market_breadth
    macro = snap.macro_environment
    health = snap.data_health

    return IntelligenceSummaryResponse(
        primary_regime=regime.primary_regime,
        secondary_regime=getattr(regime, "secondary_regime", "NEUTRAL"),
        regime_confidence_pct=float(regime.confidence_pct),
        breadth_bullish_pct=float(breadth.get("pct_bullish", 0.0)),
        breadth_bearish_pct=float(breadth.get("pct_bearish", 0.0)),
        breadth_neutral_pct=float(breadth.get("pct_neutral", 0.0)),
        strongest_asset=str(breadth.get("strongest_asset", "XAUUSD")),
        weakest_asset=str(breadth.get("weakest_asset", "EURUSD")),
        usd_strength_score=float(macro.get("usd_strength_score", 0.0)),
        usd_strength_state=str(macro.get("usd_strength_state", "NEUTRAL")),
        overall_data_quality=int(health.get("overall_quality_score", 85)),
        quality_rating=str(health.get("quality_rating", "HIGH INTEGRITY")),
        live_broker_transmission="BLOCKED",
        timestamp=snap.as_of.isoformat()
    )


@router.get("/opportunity-map", response_model=OpportunityMapResponse)
async def get_opportunity_map() -> OpportunityMapResponse:
    """
    Returns normalized 23-instrument comparative ranking leaderboard.
    """
    scanned_records = MarketScannerEngine.scan_universe(asset_class="ALL")
    ranked_records = MarketRankingEngine.rank_records(scanned_records)

    items = []
    for r in ranked_records:
        # Note: ranked_records returns dictionaries from MarketRankingEngine
        if isinstance(r, dict):
            items.append(OpportunityMapItem(
                symbol=str(r.get("symbol", "")),
                asset_class=str(r.get("asset_class", "")),
                edge_score=float(r.get("edge_score", 0.0)),
                macro_score=float(r.get("macro_score", 0.0)),
                agreement_pct=float(r.get("factor_agreement_pct", 50.0)),
                data_quality_score=int(r.get("data_quality_score", 85)),
                context_state=str(r.get("context_state", "NEUTRAL")),
                dominant_driver=str(r.get("dominant_driver", "NONE")),
                conflict_state=str(r.get("conflict_state", "ALIGNED")),
                ranking_eligible=bool(r.get("ranking_eligible", True))
            ))
        else:
            items.append(OpportunityMapItem(
                symbol=r.symbol,
                asset_class=r.asset_class,
                edge_score=float(r.edge_score),
                macro_score=float(r.macro_score),
                agreement_pct=float(r.factor_agreement_pct),
                data_quality_score=int(r.data_quality_score),
                context_state=r.context_state,
                dominant_driver=r.dominant_driver,
                conflict_state=r.conflict_state,
                ranking_eligible=bool(r.ranking_eligible)
            ))

    return OpportunityMapResponse(
        total_assets=len(items),
        ranked_assets=items,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/asset-profile/{symbol}", response_model=AssetProfileResponse)
async def get_asset_profile(symbol: str) -> AssetProfileResponse:
    """
    Returns comprehensive 6-pillar contextual deep dive profile for any requested symbol.
    """
    sym_clean = symbol.upper().replace("/", "").replace(":", "").strip()
    profile = AssetContextProfileEngine.build_asset_profile(sym_clean)

    if not profile:
        raise HTTPException(status_code=404, detail=f"Asset profile not found for '{sym_clean}'")

    edge_snap = profile.get("edge_snapshot", {})
    macro_prof = profile.get("macro_profile", {})
    dq = profile.get("data_quality", {})
    conflicts_data = profile.get("conflict_analysis", {})

    overall_edge = float(edge_snap.get("overall_score", 0.0))
    macro_score = float(macro_prof.get("overall_score", macro_prof.get("score", 0.0)))
    
    factors = edge_snap.get("factor_breakdown", [])
    tech_score = next((float(f["score"]) for f in factors if "Technical" in f.get("factor_name", "")), 0.0)
    pos_score = next((float(f["score"]) for f in factors if "Positioning" in f.get("factor_name", "")), 0.0)

    why_points = [f"{pt.get('factor')}: {pt.get('reason')}" for pt in profile.get("why_points", []) if isinstance(pt, dict)]
    conflict_list = conflicts_data.get("diverging_factors", []) if isinstance(conflicts_data, dict) else []

    return AssetProfileResponse(
        symbol=sym_clean,
        overall_edge_score=overall_edge,
        macro_context_score=macro_score,
        technical_score=tech_score,
        positioning_score=pos_score,
        data_quality_score=int(dq.get("score", 85)),
        factor_agreement_pct=float(edge_snap.get("factor_agreement_pct", 50.0)),
        context_state=str(edge_snap.get("context_state", "NEUTRAL")),
        dominant_drivers=why_points[:4] if why_points else ["Multi-factor scoring active."],
        conflicts=conflict_list,
        recent_surprises=profile.get("recent_surprises", []),
        cot_sentiment=profile.get("positioning_factor", {}) or {},
        timestamp=profile.get("as_of", datetime.now(timezone.utc).isoformat())
    )


@router.get("/heatmap", response_model=EconomicHeatmapResponse)
async def get_economic_heatmap() -> EconomicHeatmapResponse:
    """
    Returns 9-economy x 5-category fundamental surprise and macro matrix.
    """
    raw_matrix = EconomicHeatmapEngine.generate_heatmap_matrix()

    rows = []
    for r in raw_matrix:
        rows.append(EconomyHeatmapRow(
            economy_code=r.get("economy_code", ""),
            country_name=r.get("country_name", ""),
            flag=r.get("flag", ""),
            growth=r.get("growth", {}),
            inflation=r.get("inflation", {}),
            labor=r.get("labor", {}),
            rates=r.get("rates", {}),
            surprise=r.get("surprise", {})
        ))

    return EconomicHeatmapResponse(
        matrix=rows,
        total_economies=len(rows),
        timestamp=datetime.now(timezone.utc).isoformat()
    )
