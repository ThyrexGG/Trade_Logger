"""
Phase 57: Test Suite for System Safety & Contextual Output Governance
Verifies:
- Scanner outputs are strictly CONTEXTUAL, NEVER trade signals (no BUY, SELL, LONG, SHORT, ENTRY, TRADE NOW)
- Allowed context states: BULLISH CONTEXT, BEARISH CONTEXT, NEUTRAL, ALIGNED, MIXED, DIVERGING, RISK-ON, RISK-OFF, WATCH, INSUFFICIENT DATA
- Live automation lock remains fail-closed (LIVE_AUTOMATION_ENABLED = False)
"""

import pytest
from market_intelligence_scanner import MarketScannerEngine, MarketUniverseRegistry
from xauusd_forward_end_to_end_proof import Phase50SafetyBarrier
import execution_pipeline


FORBIDDEN_SIGNALS = ["BUY", "SELL", "LONG", "SHORT", "ENTRY", "TRADE NOW", "EXECUTE"]
ALLOWED_CONTEXTS = [
    "BULLISH CONTEXT", "BEARISH CONTEXT", "NEUTRAL",
    "ALIGNED", "MIXED", "DIVERGING", "RISK-ON", "RISK-OFF", "WATCH", "INSUFFICIENT DATA"
]


def test_no_directional_trade_signals_in_scan_records():
    records = MarketScannerEngine.scan_all_assets()
    for r in records:
        assert r.context_state in ALLOWED_CONTEXTS or any(ac in r.context_state for ac in ALLOWED_CONTEXTS)
        for sig in FORBIDDEN_SIGNALS:
            assert r.context_state != sig, f"Found forbidden signal '{sig}' in context_state for {r.symbol}"
            assert r.conflict_state != sig, f"Found forbidden signal '{sig}' in conflict_state for {r.symbol}"


def test_live_automation_lock_unbroken():
    # Verify invariant
    assert Phase50SafetyBarrier.LIVE_AUTOMATION_ENABLED is False
    assert getattr(execution_pipeline, "LIVE_BROKER_TRANSMISSION", "BLOCKED") == "BLOCKED"

