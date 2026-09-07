# -*- coding: utf-8 -*-
"""
Phase 63 / Stage 3 Migration Test Suite — FastAPI Read-Only Expansion & Semantic Parity Verification
=====================================================================================================
Verifies:
1. /api/preferences: GET/PUT parity with SQLite persistence & input validation.
2. /api/intelligence/*: Semantic parity for summary, opportunity-map, asset-profile, and heatmap.
3. /api/risk/preview: Calculation-only parity with authoritative risk gateway (zero execution mutation).
4. /api/positions: Read-only open positions parity with MAE/MFE excursion metrics.
5. /api/forward-evidence/state: Read-only forward evidence state & locked historical baseline parity.
6. Safety Barriers: Confirms fail-closed invariant and absence of order mutation endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

from user_preferences import UserPreferencesManager
from market_intelligence_command_center import (
    UnifiedMarketIntelligenceAggregator,
    AssetContextProfileEngine
)
from market_intelligence_scanner import MarketScannerEngine, MarketRankingEngine
from economic_heatmap import EconomicHeatmapEngine
from risk_gateway import calculate_pre_trade_risk_preview
from forward_evidence_cockpit import ForwardEvidenceCockpit
from xauusd_forward_statistical_monitoring import (
    HISTORICAL_BASELINE,
    FROZEN_CONTRACT_HASH
)
import database

client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. Preferences Endpoint Tests
# -----------------------------------------------------------------------------
def test_api_preferences_get_parity():
    """Verify /api/preferences matches authoritative UserPreferencesManager."""
    response = client.get("/api/preferences")
    assert response.status_code == 200
    data = response.json()

    engine_prefs = UserPreferencesManager.get_all_preferences()
    api_prefs = data["preferences"]

    assert api_prefs["selected_asset"] == engine_prefs["selected_asset"]
    assert api_prefs["selected_timeframe"] == engine_prefs["selected_timeframe"]
    assert api_prefs["active_workspace_layout"] == engine_prefs["active_workspace_layout"]
    assert api_prefs["watchlist_filter"] == engine_prefs["watchlist_filter"]
    assert api_prefs["compact_mode"] == engine_prefs["compact_mode"]
    assert api_prefs["shortcuts_enabled"] == engine_prefs["shortcuts_enabled"]


def test_api_preferences_put_valid_update():
    """Verify /api/preferences PUT updates fields and persists to SQLite."""
    update_payload = {
        "active_workspace_layout": "COMPACT",
        "watchlist_filter": "FOREX",
        "compact_mode": True
    }
    response = client.put("/api/preferences", json=update_payload)
    assert response.status_code == 200
    data = response.json()

    api_prefs = data["preferences"]
    assert api_prefs["active_workspace_layout"] == "COMPACT"
    assert api_prefs["watchlist_filter"] == "FOREX"
    assert api_prefs["compact_mode"] is True

    # Verify underlying SQLite store
    assert UserPreferencesManager.get_preference("active_workspace_layout") == "COMPACT"
    assert UserPreferencesManager.get_preference("watchlist_filter") == "FOREX"
    assert UserPreferencesManager.get_preference("compact_mode") is True

    # Restore default layout
    client.put("/api/preferences", json={"active_workspace_layout": "DEFAULT", "watchlist_filter": "ALL", "compact_mode": False})


def test_api_preferences_put_invalid_rejection():
    """Verify /api/preferences rejects invalid layout and timeframe values."""
    res_bad_layout = client.put("/api/preferences", json={"active_workspace_layout": "INVALID_LAYOUT_XYZ"})
    assert res_bad_layout.status_code == 400

    res_bad_tf = client.put("/api/preferences", json={"selected_timeframe": "999years"})
    assert res_bad_tf.status_code == 400


# -----------------------------------------------------------------------------
# 2. Market Intelligence Endpoints & Semantic Parity Tests
# -----------------------------------------------------------------------------
def test_api_intelligence_summary_parity():
    """Verify /api/intelligence/summary matches UnifiedMarketIntelligenceAggregator."""
    response = client.get("/api/intelligence/summary")
    assert response.status_code == 200
    data = response.json()

    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    regime = snap.regime_snapshot
    breadth = snap.market_breadth

    assert data["primary_regime"] == regime.primary_regime
    assert data["regime_confidence_pct"] == pytest.approx(float(regime.confidence_pct))
    assert data["breadth_bullish_pct"] == pytest.approx(float(breadth.get("pct_bullish", 0.0)))
    assert data["breadth_bearish_pct"] == pytest.approx(float(breadth.get("pct_bearish", 0.0)))
    assert data["live_broker_transmission"] == "BLOCKED"


def test_api_intelligence_opportunity_map_parity():
    """Verify /api/intelligence/opportunity-map matches MarketScannerEngine."""
    response = client.get("/api/intelligence/opportunity-map")
    assert response.status_code == 200
    data = response.json()

    scanned_records = MarketScannerEngine.scan_universe("ALL")
    assert data["total_assets"] == len(scanned_records)
    assert len(data["ranked_assets"]) == len(scanned_records)

    symbols = {a["symbol"] for a in data["ranked_assets"]}
    assert "XAUUSD" in symbols
    assert "EURUSD" in symbols
    assert "SPX500" in symbols


def test_api_intelligence_asset_profile_xauusd_parity():
    """Verify /api/intelligence/asset-profile/XAUUSD matches AssetContextProfileEngine."""
    response = client.get("/api/intelligence/asset-profile/XAUUSD")
    assert response.status_code == 200
    data = response.json()

    engine_profile = AssetContextProfileEngine.build_asset_profile("XAUUSD")
    edge_snap = engine_profile.get("edge_snapshot", {})

    assert data["symbol"] == "XAUUSD"
    assert data["overall_edge_score"] == pytest.approx(float(edge_snap.get("overall_score", 0.0)))
    assert "dominant_drivers" in data
    assert "cot_sentiment" in data


def test_api_intelligence_heatmap_parity():
    """Verify /api/intelligence/heatmap matches EconomicHeatmapEngine."""
    response = client.get("/api/intelligence/heatmap")
    assert response.status_code == 200
    data = response.json()

    engine_matrix = EconomicHeatmapEngine.generate_heatmap_matrix()
    assert data["total_economies"] == len(engine_matrix)
    assert len(data["matrix"]) == len(engine_matrix)

    economy_codes = [row["economy_code"] for row in data["matrix"]]
    assert "USD" in economy_codes
    assert "EUR" in economy_codes
    assert "JPY" in economy_codes


# -----------------------------------------------------------------------------
# 3. Risk Gateway Preview Endpoint Tests (Calculation-Only)
# -----------------------------------------------------------------------------
def test_api_risk_preview_valid_calculation_parity():
    """Verify /api/risk/preview matches calculate_pre_trade_risk_preview without side effects."""
    payload = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "entry_price": 2400.0,
        "stop_loss": 2390.0,
        "take_profit_1": 2420.0,
        "requested_risk_pct": 1.0,
        "account_balance": 10000.0
    }
    response = client.post("/api/risk/preview", json=payload)
    assert response.status_code == 200
    data = response.json()

    engine_prev = calculate_pre_trade_risk_preview(
        symbol="XAUUSD",
        side="BUY",
        entry_price=2400.0,
        stop_loss=2390.0,
        take_profit_1=2420.0,
        requested_risk_pct=1.0,
        account_balance=10000.0
    )

    assert data["symbol"] == "XAUUSD"
    assert data["side"] == "BUY"
    assert data["calculated_lot_size"] == pytest.approx(engine_prev["calculated_lot_size"])
    assert data["actual_risk_usd"] == pytest.approx(engine_prev["actual_risk_usd"])
    assert data["actual_risk_pct"] == pytest.approx(engine_prev["actual_risk_pct"])
    assert data["reward_tp1_usd"] == pytest.approx(engine_prev["reward_tp1_usd"])
    assert data["reward_tp1_pct"] == pytest.approx(engine_prev["reward_tp1_pct"])
    assert data["risk_reward_ratio"] == engine_prev["risk_reward_ratio"]
    assert data["is_valid"] is True
    assert data["live_broker_transmission"] == "BLOCKED"


def test_api_risk_preview_invalid_input_handling():
    """Verify /api/risk/preview correctly flags invalid geometry."""
    payload = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "entry_price": 2400.0,
        "stop_loss": 2450.0,  # Invalid SL above entry for BUY
        "requested_risk_pct": 1.0,
        "account_balance": 10000.0
    }
    response = client.post("/api/risk/preview", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert len(data["errors"]) > 0


# -----------------------------------------------------------------------------
# 4. Positions Endpoint Tests (Read-Only)
# -----------------------------------------------------------------------------
def test_api_positions_get_parity():
    """Verify /api/positions matches database.get_open_positions."""
    response = client.get("/api/positions")
    assert response.status_code == 200
    data = response.json()

    df_open = database.get_open_positions()
    assert data["total_open"] == len(df_open)
    assert isinstance(data["positions"], list)


def test_api_positions_read_only_strictly_enforced():
    """Verify that /api/positions prohibits write mutations."""
    post_res = client.post("/api/positions", json={"symbol": "FAKE"})
    assert post_res.status_code == 405  # Method Not Allowed

    del_res = client.delete("/api/positions")
    assert del_res.status_code == 405  # Method Not Allowed


# -----------------------------------------------------------------------------
# 5. Forward Evidence Endpoint Tests (Read-Only)
# -----------------------------------------------------------------------------
def test_api_forward_evidence_state_parity():
    """Verify /api/forward-evidence/state matches ForwardEvidenceCockpit and frozen baseline."""
    response = client.get("/api/forward-evidence/state")
    assert response.status_code == 200
    data = response.json()

    assert data["symbol"] == "XAUUSD"
    assert data["mode"] == "PAPER"
    assert data["strategy_contract_hash"] == FROZEN_CONTRACT_HASH

    # Historical Baseline Verification (Immutable)
    baseline = data["historical_baseline"]
    assert baseline["sample_size"] == HISTORICAL_BASELINE["trades_n"]  # 82
    assert baseline["expected_r"] == pytest.approx(HISTORICAL_BASELINE["expectancy_r"])  # +0.637
    assert baseline["win_rate_pct"] == pytest.approx(HISTORICAL_BASELINE["win_rate_pct"])  # 58.6%
    assert baseline["profit_factor"] == pytest.approx(HISTORICAL_BASELINE["profit_factor"])  # 2.52
    assert baseline["status"] == "LOCKED & UNPOOLED"

    assert data["live_broker_transmission"] == "BLOCKED"


# -----------------------------------------------------------------------------
# 6. Safety & Non-Execution Invariant Verification
# -----------------------------------------------------------------------------
def test_api_no_order_submission_endpoints_exist():
    """Verify that no order execution or broker transmission endpoints exist."""
    res_order = client.post("/api/orders", json={"symbol": "XAUUSD"})
    assert res_order.status_code == 404  # Not Found

    res_exec = client.post("/api/execution/submit", json={"symbol": "XAUUSD"})
    assert res_exec.status_code == 404  # Not Found

    res_broker = client.get("/api/broker/connect")
    assert res_broker.status_code == 404  # Not Found
