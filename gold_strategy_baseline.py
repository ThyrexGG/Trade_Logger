# -*- coding: utf-8 -*-
"""
Gold (XAUUSD) strategy baseline — the recovered previous discovery (Phase 69, §2/§3/§31).

The project's earlier strategy-discovery work (Phases 14-21) converged on XAUUSD.
That result is **not lost** — it is the frozen Strategy Contract itself
(``xauusd_market_conditions.FROZEN_CONTRACT_HASH``), fully specified in
``PHASE_21_XAUUSD_STRATEGY_CONTRACT.md`` and adversarially audited in
``PHASE_20_XAUUSD_FINAL_AUDIT.md``. ~45 ``xauusd_forward_*`` modules are the
forward-validation apparatus built around it.

This module is the permanent, machine-readable reference for that baseline. It
distinguishes:

    PreviousDiscovery          — what Phases 14-21 found (historical record)
    CurrentlyValidatedStrategy — what the Phase 70+ pipeline can independently
                                 confirm today (filled in by later phases)

Reproducibility honesty: the original Phase 19/20 numbers were produced from a
**1-minute XAUUSD dataset that is not in the repository**. Phase 68 documented
this as limitation P1-6. Each recovered metric therefore carries a
``reconstructable`` flag; nothing here is invented, and gaps are labelled
UNVERIFIABLE rather than filled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from xauusd_forward_accumulation import HistoricalVsForwardComparator

ARTIFACT_KEY = "gold_strategy_baseline"

# The repo's canonical frozen hash. The Phase 67/68 master prompts contained a
# transposition typo ("...21bda769..."); the repo value ("...21dba769...") is
# authoritative and MUST NOT change.
CANONICAL_CONTRACT_HASH = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


class EdgeStatus(str, Enum):
    """Objective edge-health states (§31). Rules are defined in ``edge_status_rules``."""
    VALIDATED = "VALIDATED"                     # revalidated pipeline PASS + forward not contradicting
    HEALTHY = "HEALTHY"                         # VALIDATED + recent forward sample confirms
    DEGRADED = "DEGRADED"                       # meaningful forward sample materially below OOS
    INVALIDATED = "INVALIDATED"                 # revalidation FAILED or forward edge gone negative w/ N>=threshold
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"  # not yet revalidated / not enough data


def edge_status_rules() -> Dict[str, str]:
    return {
        EdgeStatus.VALIDATED.value: (
            "Independent revalidation (Phase 71) returns PASS on the same contract "
            "(OOS E[R] > 0 with lower-confidence-bound > 0; WFO majority of windows positive; "
            "Monte Carlo P(ruin) < 5%) AND no forward sample with N>=20 contradicts it."
        ),
        EdgeStatus.HEALTHY.value: (
            "VALIDATED AND a forward sample with N>=20 has E[R] within 1 bootstrap SE of the "
            "revalidated OOS E[R]."
        ),
        EdgeStatus.DEGRADED.value: (
            "A forward sample with N>=20 has E[R] below (revalidated OOS E[R] - 2 bootstrap SE) "
            "but still >= 0. Single trades never trigger this."
        ),
        EdgeStatus.INVALIDATED.value: (
            "Revalidation returns FAILED, OR a forward sample with N>=30 has E[R] < 0 with an "
            "upper confidence bound < 0."
        ),
        EdgeStatus.INSUFFICIENT_EVIDENCE.value: (
            "Default. Revalidation not yet run, or the data/ forward sample needed for any of the "
            "above is not present. This is the current state in Phase 69."
        ),
    }


@dataclass(frozen=True)
class Metric:
    name: str
    value: Optional[float]
    unit: str
    reconstructable: bool
    source_doc: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class PreviousDiscovery:
    strategy_name: str
    strategy_version: str
    instrument: str
    execution_timeframe: str
    timeframe_stack: str
    session_policy: str
    entry_rule: str
    stop_rule: str
    target_rule: str
    risk_model: str
    filters: str
    historical_period: str
    holdout_sample_n: int
    data_source: str
    discovery_phase_range: str
    frozen_contract_hash: str
    metrics: List[Metric]
    verdict: str
    unverifiable: List[str]

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d["metrics"] = [m.to_dict() for m in self.metrics]
        return d


def _previous_discovery() -> PreviousDiscovery:
    locked = HistoricalVsForwardComparator.LOCKED_HISTORICAL_BASELINE
    P20 = "PHASE_20_XAUUSD_FINAL_AUDIT.md"
    P21 = "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md"
    return PreviousDiscovery(
        strategy_name="XAUUSD True Multi-Timeframe ICT/SMC",
        strategy_version="Phase-21 frozen contract (Model D: 1M FVG Limit Entry)",
        instrument="XAUUSD",
        execution_timeframe="1m",
        timeframe_stack="1D bias -> 4H draw-on-liquidity -> 15M setup -> 5M confirmation -> 1M FVG limit entry",
        session_policy="London 07:00-11:00 UTC and London/NY overlap 12:00-16:00 UTC only",
        entry_rule=(
            "After 15M liquidity sweep + MSS (body close beyond fractal swing) + displacement "
            "FVG (body >= 65% range, >= 0.5*ATR15M), and 5M aligned FVG confirmation, place a "
            "limit at the boundary (candle-3 high/low) of the first aligned 1M FVG."
        ),
        stop_rule="1M setup swing +/- 0.5*ATR(1M); bounded 5.0-35.0 pips; reject if > 35 pips",
        target_rule="Fixed 3.0R (or 4H DOL if higher structural congruency, cap 7.0R); TP1 50% at 2.0R, BE+0.1R",
        risk_model="Per-trade risk <= 1.0% (default 0.5%); max 1 XAUUSD position; portfolio aggregate risk <= 5%",
        filters="1D bias must be decisive (non-neutral); spread <= 4.0 pips; DOL must offer >= 2.0R",
        historical_period="Phases 14-20 research window (see PHASE_19 / PHASE_20); exact span not in repo",
        holdout_sample_n=int(locked["n"]),
        data_source="1-minute XAUUSD dataset used in Phases 19-20 — NOT present in the repository (P1-6)",
        discovery_phase_range="Phases 14-21",
        frozen_contract_hash=FROZEN_CONTRACT_HASH,
        verdict="Phase 20 adversarial verdict: STRONG — ROBUST RESEARCH CANDIDATE; approved for paper/shadow only",
        unverifiable=[
            "All Phase 19/20 backtest numbers below — the 1M source dataset is not in the repo",
            "Walk-forward '100% stability' claim (PHASE_20 §11) — WFO artifacts not in repo",
            "10,000-run Monte Carlo distribution (PHASE_20 §9) — simulation artifacts not in repo",
            "6-execution-model and SL/TP sensitivity tables (PHASE_20 §3-5)",
            "Cross-asset transfer table (PHASE_20 §7)",
        ],
        metrics=[
            Metric("holdout_expectancy_r", float(locked["expectancy_r"]), "R", False, P20,
                   "N=82 final holdout; locked, never re-optimised"),
            Metric("holdout_win_rate_pct", float(locked["win_rate_pct"]), "%", False, P20),
            Metric("holdout_profit_factor", float(locked["profit_factor"]), "ratio", False, P20),
            Metric("holdout_ci95_low_r", float(locked["ci_95"][0]), "R", False, P20, "95% bootstrap CI low"),
            Metric("holdout_ci95_high_r", float(locked["ci_95"][1]), "R", False, P20, "95% bootstrap CI high"),
            Metric("holdout_max_drawdown_r", float(locked["max_drawdown_r"]), "R", False, P20),
            Metric("avg_sl_distance_pips", 14.5, "pips", False, P20, "Model D"),
            Metric("monte_carlo_median_return_r", 102.8, "R", False, P20, "10k runs — artifact not in repo"),
            Metric("monte_carlo_p20r_drawdown", 0.0, "%", False, P20, "artifact not in repo"),
            Metric("friction_stress_3x_expectancy_r", 0.317, "R", False, P20,
                   "6.0 pip spread / 3.0 pip slippage / 250ms"),
        ],
    )


@dataclass
class GoldStrategyBaseline:
    strategy_id: str
    strategy_version: str
    discovery_phase_range: str
    frozen_contract_hash: str
    contract_hash_matches_canonical: bool
    previous_discovery: PreviousDiscovery
    original_metrics: Dict[str, Optional[float]]
    revalidated_metrics: Optional[Dict[str, Any]]
    latest_oos_metrics: Optional[Dict[str, Any]]
    wfo_status: str
    monte_carlo_status: str
    parameter_robustness: str
    regime_compatibility: str
    edge_status: str
    edge_status_reason: str
    edge_status_rules: Dict[str, str]
    last_validated_at: Optional[str]
    generated_at: str
    next_dependency: str

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d["previous_discovery"] = self.previous_discovery.to_dict()
        return d


def get_gold_baseline() -> GoldStrategyBaseline:
    """Return the baseline artifact. In Phase 69 the revalidation fields are
    explicitly empty / INSUFFICIENT_EVIDENCE — they are filled by Phase 71."""
    prev = _previous_discovery()
    hash_ok = FROZEN_CONTRACT_HASH == CANONICAL_CONTRACT_HASH
    return GoldStrategyBaseline(
        strategy_id="xauusd_true_mtf_ict_smc",
        strategy_version=prev.strategy_version,
        discovery_phase_range=prev.discovery_phase_range,
        frozen_contract_hash=FROZEN_CONTRACT_HASH,
        contract_hash_matches_canonical=hash_ok,
        previous_discovery=prev,
        original_metrics={m.name: m.value for m in prev.metrics},
        revalidated_metrics=None,
        latest_oos_metrics=None,
        wfo_status="NOT_REVALIDATED — Phase 21 claimed 100% window stability; artifacts not in repo",
        monte_carlo_status="NOT_REVALIDATED — Phase 20 claimed P(20R DD)=0% over 10k runs; artifacts not in repo",
        parameter_robustness="NOT_REVALIDATED — Phase 20 claimed a broad stability plateau (+/-20% on 6 params)",
        regime_compatibility=(
            "Phase 20 subgroup analysis: strong in London / London-NY overlap; "
            "insufficient sample in Asia / NY-afternoon. Not independently revalidated."
        ),
        edge_status=EdgeStatus.INSUFFICIENT_EVIDENCE.value,
        edge_status_reason=(
            "Phase 69 established the persistent data foundation only. Independent revalidation "
            "of the frozen contract (Phase 71) has not run, and the native 1M timeframe cannot be "
            "revalidated on yfinance data (P1-6). The forward-validation apparatus "
            "(xauusd_forward_*) remains the live evidence source for this contract."
        ),
        edge_status_rules=edge_status_rules(),
        last_validated_at=None,
        generated_at=datetime.now(timezone.utc).isoformat(),
        next_dependency=(
            "Phase 71: run the frozen contract through the Phase 70 discovery/robustness pipeline "
            "on 1h/1d data; native 1M revalidation needs an intraday OHLCV provider."
        ),
    )


def persist_baseline() -> str:
    """Snapshot the current baseline into ``research_artifacts``. Idempotent by
    content hash. Returns the content hash."""
    import historical_data_store
    return historical_data_store.save_artifact(
        ARTIFACT_KEY, "gold_strategy_baseline", get_gold_baseline().to_dict()
    )


__all__ = [
    "ARTIFACT_KEY",
    "CANONICAL_CONTRACT_HASH",
    "EdgeStatus",
    "edge_status_rules",
    "PreviousDiscovery",
    "GoldStrategyBaseline",
    "get_gold_baseline",
    "persist_baseline",
]
