# -*- coding: utf-8 -*-
"""
Phase 62 - Test Fail-Closed Safety Barriers & Order Execution Blocking
"""
import pytest
import streamlit as st
import database
import execution_pipeline
import risk_gateway
import ui_components


def test_live_broker_transmission_permanently_blocked():
    """Verify that execution pipeline rejects live transmission."""
    req = execution_pipeline.CanonicalExecutionRequest(
        signal_id="TEST_PHASE62_SAFETY",
        symbol="XAUUSD",
        side="BUY",
        quantity=0.01,
        requested_entry=2400.0,
        broker="CAPITAL",
        mode="LIVE",  # Attempting live transmission
        source="TEST_SAFETY",
        strategy="Safety Verification"
    )
    res = execution_pipeline.submit_order(req)
    assert res["status"].upper() in ["REJECTED", "BLOCKED", "ERROR"]


def test_risk_gateway_rejects_negative_lot():
    """Verify pre-trade risk gateway blocks invalid stop loss geometry."""
    res = risk_gateway.calculate_pre_trade_risk_preview(
        symbol="XAUUSD",
        side="BUY",
        entry_price=2400.0,
        stop_loss=2450.0,  # Invalid SL above entry for BUY
        take_profit_1=2500.0,
        requested_risk_pct=1.0,
        account_balance=10000.0
    )
    assert res["is_valid"] is False


def test_safety_banner_unmistakable_markup(monkeypatch):
    """Verify safety banner contains unmistakable permanent block."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)

    monkeypatch.setattr(st, "markdown", fake_markdown)
    ui_components.render_safety_banner()

    assert len(called) >= 1
    combined = "".join(called)
    assert "SAFETY GATE ENFORCED" in combined
    assert "LIVE BROKER TRANSMISSION IS PERMANENTLY BLOCKED" in combined
