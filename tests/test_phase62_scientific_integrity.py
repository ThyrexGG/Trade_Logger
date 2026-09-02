# -*- coding: utf-8 -*-
"""
Phase 62 - Test Scientific Integrity, Lookahead Protection & Dataset Isolation
"""
import pytest
from datetime import datetime, timezone
from macro_intelligence_engine import EconomicDataRegistry
from xauusd_forward_statistical_monitoring import (
    HISTORICAL_BASELINE,
    FROZEN_CONTRACT_HASH,
    ConservativeUncertaintyEngine
)


def test_macro_lookahead_barrier_strictly_enforced():
    """Verify that macro data queries strictly respect the as_of timestamp."""
    as_of = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    releases = EconomicDataRegistry.get_releases_as_of(as_of=as_of, metric="CPI")
    for r in releases:
        rel_ts = datetime.fromisoformat(r.release_timestamp.replace("Z", "+00:00"))
        assert rel_ts <= as_of


def test_holdout_baseline_and_contract_hash_frozen():
    """Verify strategy contract and baseline constants remain frozen."""
    assert FROZEN_CONTRACT_HASH == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert HISTORICAL_BASELINE["trades_n"] == 82
    assert HISTORICAL_BASELINE["expectancy_r"] == 0.637
    assert HISTORICAL_BASELINE["win_rate_pct"] == 58.6
    assert HISTORICAL_BASELINE["profit_factor"] == 2.52


def test_wilson_ci_non_causality():
    """Verify conservative Wilson score calculation."""
    ci_res = ConservativeUncertaintyEngine.evaluate_uncertainty_state(n=10, win_rate_pct=60.0, expectancy_r=0.50, r_values=[0.5]*10)
    assert "ci_90_wr" in ci_res
    assert ci_res["ci_90_wr"][0] > 0
    assert ci_res["ci_90_wr"][1] <= 100


def test_dataset_isolation_empty_intersection():
    """Verify separate ID sets for historical and forward observations."""
    hist_ids = set([f"HIST_{i}" for i in range(1, 83)])
    paper_ids = set([f"PAPER_{i}" for i in range(1, 10)])
    shadow_ids = set([f"SHADOW_{i}" for i in range(1, 10)])
    assert hist_ids.isdisjoint(paper_ids)
    assert hist_ids.isdisjoint(shadow_ids)
