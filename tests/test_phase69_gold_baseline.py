# -*- coding: utf-8 -*-
"""Phase 69 — recovered Gold discovery baseline (§2/§3/§31)."""
import gold_strategy_baseline as gsb
from xauusd_market_conditions import FROZEN_CONTRACT_HASH


def test_previous_discovery_is_recovered_not_invented():
    b = gsb.get_gold_baseline()
    pd_ = b.previous_discovery
    assert pd_.instrument == "XAUUSD"
    assert pd_.execution_timeframe == "1m"
    assert "1D" in pd_.timeframe_stack and "1M FVG" in pd_.timeframe_stack
    assert pd_.holdout_sample_n == 82
    # the honest data-provenance statement
    assert "NOT present in the repository" in pd_.data_source


def test_holdout_metrics_match_locked_baseline_exactly():
    b = gsb.get_gold_baseline()
    m = {x.name: x.value for x in b.previous_discovery.metrics}
    assert m["holdout_expectancy_r"] == 0.637
    assert m["holdout_win_rate_pct"] == 58.6
    assert m["holdout_profit_factor"] == 2.52
    assert m["holdout_ci95_low_r"] == 0.477
    assert m["holdout_ci95_high_r"] == 0.817


def test_unverifiable_metrics_are_flagged():
    b = gsb.get_gold_baseline()
    for x in b.previous_discovery.metrics:
        # every recovered metric is from a research doc, not reproducible here
        assert x.reconstructable is False
        assert x.source_doc
    assert len(b.previous_discovery.unverifiable) >= 4


def test_frozen_contract_hash_unchanged_and_canonical():
    b = gsb.get_gold_baseline()
    assert b.frozen_contract_hash == FROZEN_CONTRACT_HASH
    assert b.frozen_contract_hash == gsb.CANONICAL_CONTRACT_HASH
    assert b.frozen_contract_hash == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert b.contract_hash_matches_canonical is True


def test_edge_status_is_insufficient_evidence_in_phase69():
    b = gsb.get_gold_baseline()
    assert b.edge_status == gsb.EdgeStatus.INSUFFICIENT_EVIDENCE.value
    assert b.revalidated_metrics is None
    assert b.latest_oos_metrics is None
    assert b.last_validated_at is None
    assert b.next_dependency


def test_edge_status_rules_are_objective_and_complete():
    rules = gsb.edge_status_rules()
    assert set(rules) == {s.value for s in gsb.EdgeStatus}
    for text in rules.values():
        assert len(text) > 40  # each state has a concrete rule, not a label


def test_baseline_persists_to_research_artifacts():
    h = gsb.persist_baseline()
    assert len(h) == 64
    import historical_data_store as store
    loaded = store.load_artifact(gsb.ARTIFACT_KEY)
    assert loaded is not None
    assert loaded["payload"]["previous_discovery"]["holdout_sample_n"] == 82


def test_gold_is_not_forced_to_win():
    # baseline must not assert a live ranking / "#1" claim
    b = gsb.get_gold_baseline()
    blob = str(b.to_dict()).lower()
    assert "guaranteed" not in blob
    assert "#1" not in blob
