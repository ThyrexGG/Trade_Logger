"""
Phase 48 — Tests for Genuine Forward Signal Detection & Provenance Validation
"""

import pytest
from datetime import datetime, timezone, timedelta
from xauusd_forward_lifecycle import ForwardSignalPipelineValidator, ForwardSignalToObservationBridge


def test_valid_signal_provenance_validation():
    valid_sig = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        "bias_1d": "BULLISH",
        "target_4h": "PDH",
        "sweep_15m": "Asian Low Swept",
        "mss_15m": "Bullish MSS",
        "conf_5m": "Confirmed",
        "entry_type_1m": "1M FVG Limit",
        "requested_entry": 2400.0,
        "stop_loss": 2395.0,
        "take_profit": 2415.0,
        "planned_rr": 3.0,
        "execution_mode": "PAPER",
        "session": "London Open",
        "day_of_week": "Tuesday"
    }
    res = ForwardSignalPipelineValidator.validate_signal_provenance(valid_sig)
    assert res["valid"] is True
    assert res["status"] == "SIGNAL_PROVENANCE_VALIDATED"


def test_missing_provenance_fields_rejected():
    invalid_sig = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        "bias_1d": "BULLISH",
        # missing target_4h, stop_loss, etc.
    }
    res = ForwardSignalPipelineValidator.validate_signal_provenance(invalid_sig)
    assert res["valid"] is False
    assert "MISSING_PROVENANCE_FIELDS" in res["reason"]


def test_future_timestamp_lookahead_rejected():
    future_sig = {
        "timestamp": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "symbol": "XAUUSD",
        "bias_1d": "BULLISH",
        "target_4h": "PDH",
        "sweep_15m": "Asian Low Swept",
        "mss_15m": "Bullish MSS",
        "conf_5m": "Confirmed",
        "entry_type_1m": "1M FVG Limit",
        "requested_entry": 2400.0,
        "stop_loss": 2395.0,
        "take_profit": 2415.0,
        "planned_rr": 3.0,
        "execution_mode": "PAPER"
    }
    res = ForwardSignalPipelineValidator.validate_signal_provenance(future_sig)
    assert res["valid"] is False
    assert "LOOKAHEAD_VIOLATION" in res["reason"]


def test_non_positive_price_rejected():
    bad_price_sig = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        "bias_1d": "BULLISH",
        "target_4h": "PDH",
        "sweep_15m": "Asian Low Swept",
        "mss_15m": "Bullish MSS",
        "conf_5m": "Confirmed",
        "entry_type_1m": "1M FVG Limit",
        "requested_entry": -2400.0,
        "stop_loss": 2395.0,
        "take_profit": 2415.0,
        "planned_rr": 3.0,
        "execution_mode": "PAPER"
    }
    res = ForwardSignalPipelineValidator.validate_signal_provenance(bad_price_sig)
    assert res["valid"] is False
    assert "INVALID_PRICE" in res["reason"]
