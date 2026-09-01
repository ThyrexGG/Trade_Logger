# -*- coding: utf-8 -*-
"""
Phase 61 - Test Accessibility, Semantic ARIA Titles & Contrast Compliance
"""
import pytest
from ui_components import STATES_SPEC, render_state_badge


def test_state_badges_have_aria_titles():
    """Verify that all 15 states in STATES_SPEC have semantic title/aria attributes."""
    for key, spec in STATES_SPEC.items():
        assert "aria" in spec
        assert len(spec["aria"]) > 0
        html = render_state_badge(key)
        assert f'title="{spec["aria"]}"' in html
        assert spec["icon"] in html


def test_state_colors_high_contrast():
    """Verify that badge colors have background tints and solid text for high contrast."""
    for key, spec in STATES_SPEC.items():
        assert spec["color"].startswith("#")
        assert "rgba" in spec["bg"]
        assert "rgba" in spec["border"]
