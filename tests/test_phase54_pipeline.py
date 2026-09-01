"""
Phase 54 — Tests for 8-Stage Forward Observation Pipeline
"""

import pytest
from forward_evidence_cockpit import ForwardEvidenceCockpit


def test_pipeline_operational_data():
    state = ForwardEvidenceCockpit.load_cockpit_state()
    p50 = state["p50"]
    assert "heartbeats" in p50
    hb = p50["heartbeats"]
    assert "all_healthy" in hb
    assert hb["subsystems_count"] == 8
    assert "stages" in p50
    assert len(p50["stages"]) >= 8
