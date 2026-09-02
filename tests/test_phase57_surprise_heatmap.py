"""
Phase 57: Test Suite for Economic Surprise Heatmap Engine
Verifies:
- Economic surprise matrix generation across 9 economies
- Z-score surprise calculation & bounds
- Historical surprise momentum tracking
- Raw event ledger format
"""

import pytest
from economic_heatmap import SurpriseHeatmapEngine, SUPPORTED_ECONOMIES


def test_surprise_matrix_completeness():
    matrix = SurpriseHeatmapEngine.generate_surprise_matrix()
    assert len(matrix) == 9
    assert set(matrix.keys()) == set(SUPPORTED_ECONOMIES)

    for econ, data in matrix.items():
        assert "economy" in data
        assert "composite_surprise_z" in data
        assert "surprise_state" in data
        assert "recent_events" in data
        assert isinstance(data["recent_events"], list)
        assert -5.0 <= data["composite_surprise_z"] <= 5.0


def test_surprise_momentum_trend():
    momentum = SurpriseHeatmapEngine.get_surprise_momentum()
    assert len(momentum) == 9
    for m in momentum:
        assert "economy" in m
        assert "current_z" in m
        assert "prior_z" in m
        assert "momentum_delta" in m
        assert "trend" in m
        assert m["trend"] in ("IMPROVING", "DETERIORATING", "STABLE")


def test_recent_releases_ledger():
    releases = SurpriseHeatmapEngine.get_recent_releases_ledger(limit=10)
    assert isinstance(releases, list)
    assert len(releases) <= 10
    if releases:
        rel = releases[0]
        assert "event_name" in rel
        assert "economy" in rel
        assert "actual" in rel
        assert "consensus" in rel
        assert "surprise_z" in rel
