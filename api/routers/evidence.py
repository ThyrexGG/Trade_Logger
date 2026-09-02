# -*- coding: utf-8 -*-
"""
FastAPI Forward Evidence & Governance Router — Stage 3 Read-Only Evidence State Endpoint
Consumes ForwardEvidenceCockpit, Phase49MonitoringFacade, and Phase50Facade directly.
Preserves locked historical baseline and Strategy Contract SHA-256 without modification.
"""
from datetime import datetime, timezone
from fastapi import APIRouter
from api.schemas import ForwardEvidenceStateResponse, HistoricalBaselineModel
from forward_evidence_cockpit import ForwardEvidenceCockpit
from xauusd_forward_statistical_monitoring import (
    HISTORICAL_BASELINE,
    FROZEN_CONTRACT_HASH
)

router = APIRouter(prefix="/api/forward-evidence", tags=["Forward Evidence & Governance"])


@router.get("/state", response_model=ForwardEvidenceStateResponse)
async def get_forward_evidence_state() -> ForwardEvidenceStateResponse:
    """
    Returns the authoritative forward statistical monitoring state, Wilson score intervals,
    milestone progression, and locked historical holdout comparison.
    """
    cockpit_state = ForwardEvidenceCockpit.load_cockpit_state()
    p49 = cockpit_state.get("p49", {})
    metrics = p49.get("metrics", {})
    milestones = p49.get("milestones", {})
    decision = p49.get("decision", {})
    uncertainty = p49.get("uncertainty", {})
    wilson_ci = uncertainty.get("wilson_win_rate_ci", (0.0, 1.0))

    baseline = HistoricalBaselineModel(
        sample_size=int(HISTORICAL_BASELINE.get("trades_n", 82)),
        expected_r=float(HISTORICAL_BASELINE.get("expectancy_r", 0.637)),
        win_rate_pct=float(HISTORICAL_BASELINE.get("win_rate_pct", 58.6)),
        profit_factor=float(HISTORICAL_BASELINE.get("profit_factor", 2.52)),
        status="LOCKED & UNPOOLED"
    )

    return ForwardEvidenceStateResponse(
        symbol="XAUUSD",
        mode="PAPER",
        sample_n=int(metrics.get("trades_n", 0)),
        win_rate_pct=float(metrics.get("win_rate_pct", 0.0)),
        profit_factor=float(metrics.get("profit_factor", 0.0)),
        expected_r=float(metrics.get("expectancy_r", 0.0)),
        next_milestone=int(milestones.get("next_milestone", 1)),
        decision_state=str(decision.get("decision_state", "WAITING FOR SAMPLE")),
        wilson_ci_lower_pct=round(float(wilson_ci[0]) * 100.0, 2),
        wilson_ci_upper_pct=round(float(wilson_ci[1]) * 100.0, 2),
        historical_baseline=baseline,
        strategy_contract_hash=FROZEN_CONTRACT_HASH,
        live_broker_transmission="BLOCKED",
        timestamp=cockpit_state.get("evaluated_at", datetime.now(timezone.utc).isoformat())
    )
