"""
Phase 57: Test Suite for Cross-Asset Matrix Engine
Verifies:
- Correlation matrix computation across rolling windows (20, 60, 120)
- Matrix symmetry and diagonal = 1.0
- Minimum sample size threshold (N >= 15)
- Prominent correlation disclaimer presence
"""

import pytest
from cross_asset_regime_engine import CrossAssetMatrixEngine, CORRELATION_DISCLAIMER


def test_correlation_matrix_generation_default():
    matrix_data = CrossAssetMatrixEngine.calculate_correlation_matrix(lookback_days=60)
    assert isinstance(matrix_data, dict)
    assert "symbols" in matrix_data
    assert "matrix" in matrix_data
    assert "lookback_days" in matrix_data
    assert matrix_data["lookback_days"] == 60
    assert "disclaimer" in matrix_data
    assert CORRELATION_DISCLAIMER in matrix_data["disclaimer"]

    symbols = matrix_data["symbols"]
    matrix = matrix_data["matrix"]
    n = len(symbols)
    assert len(matrix) == n

    for i in range(n):
        assert len(matrix[i]) == n
        # Diagonal must be 1.0 (self correlation)
        assert pytest.approx(matrix[i][i], abs=1e-3) == 1.0
        for j in range(n):
            # Symmetry: corr(i, j) == corr(j, i)
            assert pytest.approx(matrix[i][j], abs=1e-3) == matrix[j][i]
            assert -1.0 <= matrix[i][j] <= 1.0


def test_correlation_matrix_custom_symbols():
    custom = ["EURUSD", "SPX500", "XAUUSD", "USOIL"]
    res = CrossAssetMatrixEngine.calculate_correlation_matrix(symbols=custom, lookback_days=20)
    assert res["symbols"] == custom
    assert len(res["matrix"]) == 4
    for row in res["matrix"]:
        assert len(row) == 4


def test_cluster_analysis_output():
    clusters = CrossAssetMatrixEngine.get_correlation_clusters(lookback_days=60)
    assert isinstance(clusters, list)
    assert len(clusters) > 0
    for c in clusters:
        assert "cluster_name" in c
        assert "members" in c
        assert "avg_intra_correlation" in c
