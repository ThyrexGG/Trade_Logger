# -*- coding: utf-8 -*-
"""
Phase 61 - Test UI Components, Badges, Metrics, Empty States & Safety Banner
"""
import pytest
import streamlit as st
import ui_components


def test_render_safety_banner_markup(monkeypatch):
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


def test_render_metric_card_markup(monkeypatch):
    """Verify metric card HTML structure."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)

    monkeypatch.setattr(st, "markdown", fake_markdown)
    ui_components.render_metric_card("EXPECTANCY", "+0.637 R", "Locked baseline", "+0.10 R", "#10b981")

    assert len(called) >= 1
    combined = "".join(called)
    assert "tl-metric-card" in combined
    assert "EXPECTANCY" in combined
    assert "+0.637 R" in combined
