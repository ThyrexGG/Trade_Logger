# -*- coding: utf-8 -*-
"""
FastAPI Forward Evidence & Governance Router — Read-Only Evidence State Endpoints
Consumes Phase49MonitoringFacade directly and serializes the authoritative
forward statistical monitoring state without duplicating any calculation.

Preserves the locked historical baseline and Strategy Contract SHA-256.
GET requests never mutate state: the read path uses the Stage 3.5D cached
snapshot and the milestone snapshot listing is a plain SELECT.
"""
from datetime import datetime, timezone
from fastapi import APIRouter
from api.schemas import (
    ForwardEvidenceStateResponse,
    HistoricalBaselineModel,
    ForwardMetricsModel,
    UncertaintyModel,
    HoldoutComparisonModel,
    AlphaDecayModel,
    MilestoneProgressModel,
    MilestoneRoadmapEntry,
    DecisionStateModel,
    DatasetProvenanceModel,
    SafetyBarrierModel,
)
from xauusd_forward_statistical_monitoring import (
    Phase49MonitoringFacade,
    HISTORICAL_BASELINE,
    FROZEN_CONTRACT_HASH,
)

router = APIRouter(prefix="/api/forward-evidence", tags=["Forward Evidence & Governance"])


def _ci(value, fallback):
    """Normalizes a (lower, upper) confidence-interval tuple/list to List[float]."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [float(value[0]), float(value[1])]
    return list(fallback)


@router.get("/state", response_model=ForwardEvidenceStateResponse)
async def get_forward_evidence_state() -> ForwardEvidenceStateResponse:
    """
    Returns the authoritative forward statistical monitoring state: forward
    metrics, Wilson / bootstrap uncertainty, alpha-decay surveillance, milestone
    progression, decision state, dataset provenance and the locked historical
    holdout comparison. Every field is computed by the Phase 49 engine.
    """
    # Stage 3.5D: authoritative Phase 49 state through the bounded, thread-safe
    # read-snapshot cache. This dict is produced verbatim by
    # evaluate_full_forward_state(); the router only serializes it.
    p49 = Phase49MonitoringFacade.get_cached_forward_state_snapshot(mode="PAPER", symbol="XAUUSD")

    metrics = p49.get("metrics", {}) or {}
    uncertainty = p49.get("uncertainty", {}) or {}
    comparison = p49.get("comparison", {}) or {}
    alpha = p49.get("alpha_decay", {}) or {}
    milestones = p49.get("milestones", {}) or {}
    decision = p49.get("decision", {}) or {}
    dataset = p49.get("dataset", {}) or {}
    barrier = p49.get("live_automation_barrier", {}) or {}

    # Legacy top-level Wilson CI fields — preserved exactly as the original
    # Stage 3 adapter emitted them (percent scale, unchanged semantics). The
    # authoritative Wilson-score interval is also exposed, on its native
    # percent scale, inside `uncertainty.ci_95_wr` / `ci_90_wr` / `ci_99_wr`.
    wilson_ci = uncertainty.get("wilson_win_rate_ci", (0.0, 1.0))

    baseline = HistoricalBaselineModel(
        sample_size=int(HISTORICAL_BASELINE.get("trades_n", 82)),
        expected_r=float(HISTORICAL_BASELINE.get("expectancy_r", 0.637)),
        win_rate_pct=float(HISTORICAL_BASELINE.get("win_rate_pct", 58.6)),
        profit_factor=float(HISTORICAL_BASELINE.get("profit_factor", 2.52)),
        status="LOCKED & UNPOOLED",
    )

    metrics_model = ForwardMetricsModel(
        trades_n=int(metrics.get("trades_n", 0)),
        win_rate_pct=float(metrics.get("win_rate_pct", 0.0)),
        expectancy_r=float(metrics.get("expectancy_r", 0.0)),
        average_r=float(metrics.get("average_r", 0.0)),
        median_r=float(metrics.get("median_r", 0.0)),
        profit_factor=float(metrics.get("profit_factor", 0.0)),
        cumulative_r=float(metrics.get("cumulative_r", 0.0)),
        max_drawdown_r=float(metrics.get("max_drawdown_r", 0.0)),
        std_dev_r=float(metrics.get("std_dev_r", 0.0)),
        win_count=int(metrics.get("win_count", 0)),
        loss_count=int(metrics.get("loss_count", 0)),
        breakeven_count=int(metrics.get("breakeven_count", 0)),
        win_streak=int(metrics.get("win_streak", 0)),
        loss_streak=int(metrics.get("loss_streak", 0)),
        outcomes={k: float(v) for k, v in (metrics.get("outcomes", {}) or {}).items()},
        maturity_tier=str(metrics.get("maturity_tier", "NO_FORWARD_DATA")),
        maturity_label=str(metrics.get("maturity_label", "NO FORWARD SAMPLE (N = 0)")),
        interpretation=str(metrics.get("interpretation", "")),
    )

    uncertainty_model = UncertaintyModel(
        sample_n=int(uncertainty.get("sample_n", 0)),
        statistical_status=str(uncertainty.get("statistical_status", "NO_FORWARD_DATA")),
        status_badge=str(uncertainty.get("status_badge", "INSUFFICIENT SAMPLE (N = 0)")),
        win_rate_statement=str(uncertainty.get("win_rate_statement", "")),
        expectancy_statement=str(uncertainty.get("expectancy_statement", "")),
        ci_90_wr=_ci(uncertainty.get("ci_90_wr"), None) if uncertainty.get("ci_90_wr") is not None else None,
        ci_95_wr=_ci(uncertainty.get("ci_95_wr"), None) if uncertainty.get("ci_95_wr") is not None else None,
        ci_99_wr=_ci(uncertainty.get("ci_99_wr"), None) if uncertainty.get("ci_99_wr") is not None else None,
        ci_90_exp=_ci(uncertainty.get("ci_90_exp"), None) if uncertainty.get("ci_90_exp") is not None else None,
        ci_95_exp=_ci(uncertainty.get("ci_95_exp"), None) if uncertainty.get("ci_95_exp") is not None else None,
        ci_99_exp=_ci(uncertainty.get("ci_99_exp"), None) if uncertainty.get("ci_99_exp") is not None else None,
        prohibited_claim=str(uncertainty.get("prohibited_claim", "")),
        valid_statement=str(uncertainty.get("valid_statement", "")),
    )

    holdout_model = HoldoutComparisonModel(
        historical=comparison.get("historical", dict(HISTORICAL_BASELINE)),
        forward=comparison.get("forward", {}),
        deltas=comparison.get("deltas", {}),
        comparison_verdict=str(comparison.get("comparison_verdict", "NO FORWARD EVIDENCE (N = 0)")),
        explanation=str(comparison.get("explanation", "")),
        pooling_prevention_check=str(comparison.get("pooling_prevention_check", "PASS (DATASETS UNPOOLED)")),
    )

    alpha_model = AlphaDecayModel(
        forward_n=int(alpha.get("forward_n", 0)),
        decay_state=str(alpha.get("decay_state", "")),
        loss_clustering_detected=bool(alpha.get("loss_clustering_detected", False)),
        expectancy_deterioration=bool(alpha.get("expectancy_deterioration", False)),
        max_drawdown_expansion=alpha.get("max_drawdown_expansion"),
        action_required=str(alpha.get("action_required", "")),
        summary=str(alpha.get("summary", "")),
    )

    milestone_model = MilestoneProgressModel(
        current_n=int(milestones.get("current_n", 0)),
        next_milestone=int(milestones.get("next_milestone", 1)),
        trades_remaining=int(milestones.get("trades_remaining", 0)),
        completion_pct_toward_next=float(milestones.get("completion_pct_toward_next", 0.0)),
        milestone_roadmap=[
            MilestoneRoadmapEntry(
                target_n=int(m.get("target_n", 0)),
                status_label=str(m.get("status_label", "PENDING")),
                trades_remaining=int(m.get("trades_remaining", 0)),
                is_reached=bool(m.get("is_reached", False)),
            )
            for m in milestones.get("milestone_roadmap", []) or []
        ],
    )

    decision_model = DecisionStateModel(
        decision_state=str(decision.get("decision_state", "INSUFFICIENT EVIDENCE (N = 0)")),
        rationale=str(decision.get("rationale", "")),
        research_action=str(decision.get("research_action", "")),
    )

    dataset_model = DatasetProvenanceModel(
        symbol=str(dataset.get("symbol", "XAUUSD")),
        mode=str(dataset.get("mode", "PAPER")),
        total_records=int(dataset.get("total_records", 0)),
        clean_n=int(dataset.get("clean_n", 0)),
        quarantined_count=int(dataset.get("quarantined_count", 0)),
        dataset_fingerprint=str(dataset.get("dataset_fingerprint", "")),
        contract_hash=str(dataset.get("contract_hash", FROZEN_CONTRACT_HASH)),
        is_isolated=bool(dataset.get("is_isolated", True)),
        status=str(dataset.get("status", "WAITING_FOR_GENUINE_OBSERVATIONS")),
    )

    safety_model = SafetyBarrierModel(
        live_automation_enabled=bool(barrier.get("live_automation_enabled", False)),
        broker_transmission=str(barrier.get("broker_transmission", "BLOCKED (FAIL-CLOSED)")),
        status=str(barrier.get("status", "PASS (SAFETY LOCKED)")),
    )

    return ForwardEvidenceStateResponse(
        symbol=str(p49.get("symbol", "XAUUSD")),
        mode=str(p49.get("mode", "PAPER")),
        sample_n=metrics_model.trades_n,
        win_rate_pct=metrics_model.win_rate_pct,
        profit_factor=metrics_model.profit_factor,
        expected_r=metrics_model.expectancy_r,
        next_milestone=milestone_model.next_milestone,
        decision_state=decision_model.decision_state,
        wilson_ci_lower_pct=round(float(wilson_ci[0]) * 100.0, 2),
        wilson_ci_upper_pct=round(float(wilson_ci[1]) * 100.0, 2),
        historical_baseline=baseline,
        strategy_contract_hash=str(p49.get("contract_hash", FROZEN_CONTRACT_HASH)),
        contract_valid=bool(p49.get("contract_valid", True)),
        live_broker_transmission="BLOCKED",
        metrics=metrics_model,
        uncertainty=uncertainty_model,
        holdout=holdout_model,
        alpha_decay=alpha_model,
        milestones=milestone_model,
        decision=decision_model,
        dataset=dataset_model,
        safety=safety_model,
        timestamp=str(p49.get("evaluated_at", datetime.now(timezone.utc).isoformat())),
    )
