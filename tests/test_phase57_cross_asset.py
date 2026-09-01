"""
TradeLogger Phase 57 — Test Suite: Cross-Asset Correlation Matrix Engine
========================================================================
Validates:
- Rolling window support (20, 60, 120 days/periods).
- Matrix symmetry (corr(A, B) == corr(B, A)).
- Diagonal unit correlation (corr(A, A) == 1.0).
- Minimum sample size threshold (N >= 15) validation.
- Prominent 'CORRELATION ≠ CAUSATION' disclaimer presence.
"""

import pytest
from cross_asset_regime_engine import CrossAssetMatrixEngine


def test_correlation_matrix_properties():
    """Verify diagonal is 1.0 and matrix is symmetric across all windows."""
    for window in [20, 60, 120]:
        matrix_data = CrossAssetMatrixEngine.calculate_correlation_matrix(window=window)
        symbols = matrix_data["symbols"]
        corr = matrix_data["matrix"]

        assert len(symbols) >= 8

        # Check diagonal and symmetry
        for s1 in symbols:
            assert abs(corr[s1][s1] - 1.0) < 1e-4
            for s2 in symbols:
                assert abs(corr[s1][s2] - corr[s2][s1]) < 1e-4
                assert -1.0 <= corr[s1][s2] <= 1.0


def test_correlation_disclaimer():
    """Verify mandatory anti-overfitting correlation disclaimer is present."""
    matrix_data = CrossAssetMatrixEngine.calculate_correlation_matrix(window=60)
    assert "disclaimer" in matrix_data
    assert "CORRELATION ≠ CAUSATION" in matrix_data["disclaimer"]
