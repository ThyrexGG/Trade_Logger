# -*- coding: utf-8 -*-
"""
Phase 60 - Test Design Tokens, 15-State Visual Language & UI Component Primitives
"""
import pytest
import ui_components


def test_tokens_structure_and_completeness():
    """Verify that centralized design tokens contain all necessary color, typography, spacing, and radii keys."""
    tokens = ui_components.TOKENS
    assert "colors" in tokens
    assert "typography" in tokens
    assert "spacing" in tokens
    assert "radii" in tokens

    colors = tokens["colors"]
    required_colors = [
        "bg_app", "bg_panel", "bg_elevated", "bg_hover", "border_subtle",
        "border_card", "border_accent", "accent_primary", "text_primary",
        "text_secondary", "text_muted", "state_success", "state_warning",
        "state_error", "state_info", "state_neutral", "mode_paper",
        "mode_shadow", "mode_live_blocked"
    ]
    for rc in required_colors:
        assert rc in colors, f"Missing color token: {rc}"

    typography = tokens["typography"]
    required_type = ["font_family", "font_mono", "size_hero", "size_h1", "size_h2", "size_h3", "size_body", "size_caption"]
    for rt in required_type:
        assert rt in typography, f"Missing typography token: {rt}"


def test_15_state_visual_language_spec():
    """Verify that all 15 operational states are defined with required attributes."""
    spec = ui_components.STATES_SPEC
    required_states = [
        "SUCCESS", "WARNING", "ERROR", "INFO", "NEUTRAL",
        "NO_DATA", "LOADING", "DISCONNECTED", "STALE_DATA",
        "REJECTED", "QUARANTINED", "BLOCKED", "PAPER",
        "SHADOW", "LIVE_BLOCKED"
    ]
    assert len(spec) >= 15
    for st_name in required_states:
        assert st_name in spec, f"Missing state spec for {st_name}"
        item = spec[st_name]
        assert "label" in item
        assert "icon" in item
        assert "color" in item
        assert "bg" in item
        assert "border" in item
        assert "aria" in item
        assert "severity" in item


def test_render_state_badge_html():
    """Verify that render_state_badge outputs valid, accessible HTML badge."""
    badge_html = ui_components.render_state_badge("SUCCESS", "VERIFIED PASS")
    assert "tl-badge" in badge_html
    assert "VERIFIED PASS" in badge_html
    assert "#10b981" in badge_html
    assert "title=" in badge_html

    # Default fallback to NEUTRAL for unknown state
    fallback_html = ui_components.render_state_badge("UNKNOWN_STATE_KEY")
    assert "tl-badge" in fallback_html
    assert "STANDBY" in fallback_html


def test_render_metric_card_structure():
    """Verify metric card HTML output formatting."""
    # We can inspect the function doesn't crash and generates HTML
    # We test via monkeypatching st.markdown
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)
        
    import streamlit as st
    orig_md = st.markdown
    st.markdown = fake_markdown
    try:
        ui_components.render_metric_card(
            title="EXPECTANCY",
            value="+0.637 R",
            delta="+0.12R",
            status_color="#00ffcc",
            subtitle="Holdout Benchmark",
            badge_state="SUCCESS"
        )
        assert len(called) == 1
        html = called[0]
        assert "EXPECTANCY" in html
        assert "+0.637 R" in html
        assert "Holdout Benchmark" in html
        assert "tl-metric-card" in html
    finally:
        st.markdown = orig_md


def test_render_empty_state_structure():
    """Verify empty state component structure."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)
        
    import streamlit as st
    orig_md = st.markdown
    st.markdown = fake_markdown
    try:
        ui_components.render_empty_state(
            title="NO ACTIVE FORWARD SIGNALS",
            message="The system is currently flat and scanning.",
            state_key="NEUTRAL",
            action_hint="Signals appear when 15M structure confirms."
        )
        assert len(called) == 1
        html = called[0]
        assert "NO ACTIVE FORWARD SIGNALS" in html
        assert "tl-empty-state" in html
        assert "Signals appear when 15M structure confirms." in html
    finally:
        st.markdown = orig_md
