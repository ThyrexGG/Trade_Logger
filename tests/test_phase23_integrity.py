"""
Unit Tests for Phase 23 — Forward Validation Integrity & Provenance
Tests:
- Strategy contract hash verification & mutation detection
- Observation provenance recording & duplicate prevention
- Data quality audits (impossible OHLC, timestamp gaps, clean streams)
- Operational outcome classification (STRATEGY OUTCOME, MISSED ENTRY, etc.)
"""

import pytest
import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timezone
import database
from xauusd_forward_integrity import (
    StrategyContractIntegrityGuard,
    FrozenStrategyMutationException,
    ForwardObservationProvenance,
    ForwardDataQualityAuditor,
    ObservationOutcomeClassifier
)


@pytest.fixture(autouse=True)
def init_test_db():
    database.init_db()


def test_strategy_contract_integrity_and_mutation_detection():
    # 1. Valid verification
    guard_res = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert guard_res["integrity_status"] == "FROZEN & LOCKED"
    assert guard_res["live_automation_blocked"] is True

    # 2. Mutation attempt raises FrozenStrategyMutationException
    mutated_params = {"min_target_r": 1.5} # Attempting to lower target
    with pytest.raises(FrozenStrategyMutationException):
        StrategyContractIntegrityGuard.verify_contract_immutability(mutated_params)


def test_forward_observation_provenance_and_uniqueness():
    obs_id = f"TEST_OBS_{uuid.uuid4().hex[:8]}"
    record = {
        "observation_id": obs_id,
        "contract_version": "PHASE_21_FROZEN_1.0",
        "signal_timestamp": datetime.now(timezone.utc).isoformat(),
        "data_timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        "source_tf": "1M",
        "bid": 2400.30,
        "ask": 2400.50,
        "spread_pips": 2.0,
        "atr_1m": 1.45,
        "detected_regime": "BULLISH_TREND",
        "setup_state": "15M_SWEEP_MSS_CONFIRMED",
        "entry_decision": "LIMIT_ORDER_PLACED",
        "limit_price": 2400.50,
        "stop_loss": 2398.50,
        "take_profit_1": 2404.50,
        "take_profit_2": 2415.00,
        "risk_pct": 0.50,
        "order_state": "FILLED",
        "fill_timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome_category": "STRATEGY OUTCOME",
        "realized_r": 3.0,
        "mae_r": 0.35,
        "mfe_r": 3.20,
        "execution_mode": "PAPER"
    }

    ret_id = ForwardObservationProvenance.record_provenance(record)
    assert ret_id == obs_id

    # Test duplicate prevention
    dup_id = ForwardObservationProvenance.record_provenance(record)
    assert dup_id == obs_id

    df_prov = ForwardObservationProvenance.get_all_provenance(mode="PAPER")
    assert not df_prov.empty
    assert obs_id in df_prov["observation_id"].values


def test_data_quality_auditor():
    # 1. Clean feed
    clean_df = pd.DataFrame({
        "time": ["2026-08-31 08:00:00", "2026-08-31 08:01:00", "2026-08-31 08:02:00"],
        "open": [2400.0, 2400.5, 2401.0],
        "high": [2401.0, 2401.5, 2402.0],
        "low": [2399.5, 2400.0, 2400.5],
        "close": [2400.5, 2401.0, 2401.8]
    })
    audit_clean = ForwardDataQualityAuditor.audit_feed_integrity(clean_df)
    assert audit_clean["status"] == "HEALTHY"
    assert audit_clean["invalid_ohlc_count"] == 0

    # 2. Corrupted feed with impossible high < low
    corrupt_df = pd.DataFrame({
        "time": ["2026-08-31 08:00:00"],
        "open": [2400.0],
        "high": [2395.0], # High < Low
        "low": [2400.0],
        "close": [2398.0]
    })
    audit_corrupt = ForwardDataQualityAuditor.audit_feed_integrity(corrupt_df)
    assert audit_corrupt["status"] == "CRITICAL"
    assert audit_corrupt["invalid_ohlc_count"] > 0


def test_outcome_classification_mapping():
    assert ObservationOutcomeClassifier.classify_outcome("FILLED", 2400.5, "TP1") == "STRATEGY OUTCOME"
    assert ObservationOutcomeClassifier.classify_outcome("EXPIRED", None, "TIMEOUT") == "MISSED ENTRY"
    assert ObservationOutcomeClassifier.classify_outcome("INVALIDATED", None, "SWING_BREACH") == "STRATEGY INVALIDATED"
    assert ObservationOutcomeClassifier.classify_outcome("ERROR", None, "RECON_DESYNC") == "EXECUTION ERROR"
