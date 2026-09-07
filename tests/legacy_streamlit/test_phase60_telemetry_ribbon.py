# -*- coding: utf-8 -*-
"""
Phase 60 - Test Global Telemetry Ribbon & Status Invariants
"""
import pytest
import streamlit as st
import ui_components


def test_telemetry_ribbon_structure_and_metrics():
    """Verify that global telemetry ribbon contains all essential operational items."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)
        
    orig_md = st.markdown
    st.markdown = fake_markdown
    try:
        ui_components.render_global_telemetry_ribbon(
            symbol="XAUUSD",
            price=2415.50,
            timeframe="15m",
            session_name="LONDON / NY OVERLAP",
            data_health="HEALTHY",
            exec_mode="PAPER",
            system_health="NORMAL",
            live_blocked=True,
            spread_pips=0.25
        )
        assert len(called) == 1
        html = called[0]
        assert "tl-telemetry-ribbon" in html
        assert "XAUUSD" in html
        assert "$2,415.50" in html
        assert "15m" in html
        assert "LONDON / NY OVERLAP" in html
        assert "DATA HEALTHY" in html
        assert "PAPER EXECUTION" in html
        assert "SYS HEALTHY" in html
        assert "LIVE - BLOCKED" in html or "LIVE" in html
        assert "SPREAD:" in html
        assert "0.2" in html or "0.3" in html
    finally:
        st.markdown = orig_md


def test_telemetry_ribbon_stale_and_shadow_states():
    """Verify telemetry ribbon adapts correctly to degraded data health and shadow mode."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)
        
    orig_md = st.markdown
    st.markdown = fake_markdown
    try:
        ui_components.render_global_telemetry_ribbon(
            symbol="EURUSD",
            price=1.0850,
            timeframe="1h",
            session_name="ASIAN / TOKYO",
            data_health="STALE",
            exec_mode="SHADOW",
            system_health="DEGRADED",
            live_blocked=True
        )
        assert len(called) == 1
        html = called[0]
        assert "EURUSD" in html
        assert "1.0850" in html
        assert "STALE DATA" in html
        assert "SHADOW EXECUTION" in html
        assert "SYS DEGRADED" in html
    finally:
        st.markdown = orig_md


def test_safety_banner_fail_closed_invariant():
    """Verify that render_safety_banner contains permanent fail-closed notice."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)
        
    orig_md = st.markdown
    st.markdown = fake_markdown
    try:
        ui_components.render_safety_banner()
        assert len(called) == 1
        html = called[0]
        assert "SAFETY GATE ENFORCED" in html
        assert "LIVE BROKER TRANSMISSION IS PERMANENTLY BLOCKED" in html
        assert "AUTOMATION = OFF" in html
    finally:
        st.markdown = orig_md
