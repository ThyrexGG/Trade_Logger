"""
Phase 54 — Tests for UI Renderers & Cockpit Subviews
"""

import pytest
from forward_evidence_cockpit import ForwardEvidenceCockpit


def test_all_cockpit_tabs_render():
    state = ForwardEvidenceCockpit.load_cockpit_state()
    # Must execute with zero unhandled exceptions
    ForwardEvidenceCockpit.render_overview_tab(state)
    ForwardEvidenceCockpit.render_statistics_tab(state)
    ForwardEvidenceCockpit.render_milestones_tab(state)
    ForwardEvidenceCockpit.render_stability_tab(state)
    ForwardEvidenceCockpit.render_pipeline_tab(state)
    ForwardEvidenceCockpit.render_forensics_tab(state)
    ForwardEvidenceCockpit.render_governance_tab(state)
