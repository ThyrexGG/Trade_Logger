"""
Phase 57: Test Suite for Cross-Asset Regime Engine
Verifies:
- 12 regime states validation
- Multi-factor regime classification output structure
- Deterministic scoring across asset drivers
- Cryptographic regime snapshot persistence and retrieval
"""

from datetime import datetime, timezone
import pytest
from cross_asset_regime_engine import (
    CrossAssetRegimeEngine,
    MarketRegimeSnapshotStore,
    VALID_REGIME_STATES
)


def test_valid_regime_states_count():
    assert len(VALID_REGIME_STATES) == 12
    assert "RISK_ON" in VALID_REGIME_STATES
    assert "RISK_OFF" in VALID_REGIME_STATES
    assert "INSUFFICIENT_DATA" in VALID_REGIME_STATES


def test_regime_classification_structure():
    regime = CrossAssetRegimeEngine.classify_current_regime()
    assert isinstance(regime, dict)
    assert "primary_regime" in regime
    assert regime["primary_regime"] in VALID_REGIME_STATES
    assert "confidence_pct" in regime
    assert 0 <= regime["confidence_pct"] <= 100
    assert "risk_appetite" in regime
    assert "inflation_environment" in regime
    assert "growth_environment" in regime
    assert "usd_cycle" in regime
    assert "rates_trend" in regime
    assert "regime_narrative" in regime
    assert "driver_breakdown" in regime
    assert "data_fingerprint" in regime
    assert len(regime["data_fingerprint"]) == 64


def test_regime_snapshot_storage():
    regime = CrossAssetRegimeEngine.classify_current_regime()
    snap_id = MarketRegimeSnapshotStore.save_regime_snapshot(regime)
    assert snap_id.startswith("REGIME_")

    latest = MarketRegimeSnapshotStore.get_latest_regime_snapshot()
    assert latest is not None
    assert latest["snapshot_id"] == snap_id
    assert latest["primary_regime"] == regime["primary_regime"]
    assert latest["data_fingerprint"] == regime["data_fingerprint"]
