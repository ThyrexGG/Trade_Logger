# -*- coding: utf-8 -*-
"""
Phase 61 - Test Responsive Token Scales & Media Queries in Global Stylesheet
"""
import pytest
import ui_components


def test_responsive_media_queries_present(monkeypatch):
    """Verify that injected CSS stylesheet contains responsive media query breakpoints."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)

    monkeypatch.setattr(ui_components.st, "markdown", fake_markdown)
    ui_components.inject_global_design_system()

    assert len(called) >= 1
    css_str = "".join(called)
    assert "@media (max-width: 1440px)" in css_str
    assert "@media (max-width: 1280px)" in css_str
    assert "tl-telemetry-ribbon" in css_str
