"""
Phase 44 — Sequential Blocks & Regime Stability Test Suite
Validates chronological tertiles/quartiles evaluation and market subgroup stability.
"""

import pandas as pd
import pytest
from xauusd_alpha_decay_monitor import (
    SequentialBlockStabilityEngine,
    RegimeSpecificAlphaDecayEngine,
)


def test_sequential_blocks_insufficient_sample():
    """Validates block evaluation with small sample."""
    res = SequentialBlockStabilityEngine.evaluate_sequential_blocks(pd.DataFrame())

    assert res["has_enough_data"] is False
    assert "INSUFFICIENT" in res["status"]


def test_sequential_blocks_with_sample():
    """Validates block evaluation with N = 12 observations."""
    data = [{"r_multiple": 1.0 if i < 6 else -0.5, "signal_id": f"OBS_{i}"} for i in range(12)]
    df = pd.DataFrame(data)

    res = SequentialBlockStabilityEngine.evaluate_sequential_blocks(df)
    assert res["has_enough_data"] is True
    assert len(res["tertiles"]) == 3
    assert len(res["quartiles"]) == 4


def test_regime_specific_decay_evaluation():
    """Validates operational subgroup structure and sample protection."""
    res = RegimeSpecificAlphaDecayEngine.evaluate_regime_decay(pd.DataFrame())

    assert "subgroups" in res
    assert len(res["subgroups"]) == 8
    assert "disclaimer" in res
    for sg in res["subgroups"]:
        assert "statistical_tier" in sg
        assert sg["sample_n"] == 0
