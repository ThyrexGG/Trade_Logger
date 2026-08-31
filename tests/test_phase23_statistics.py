"""
Unit Tests for Phase 23 — Forward Statistics, Effect Size & Temporal Analytics
Tests:
- Forward effect size comparison and ratio against historical baseline (+0.637R)
- Rolling trade window statistics and curve generation
- Cumulative equity curve generation and dataset isolation
- Target milestone progression analysis (2R to 7R)
- Holding duration temporal bucketing
"""

import pytest
import numpy as np
import pandas as pd
from xauusd_forward_statistics import (
    ForwardEffectSizeComparator,
    RollingForwardAnalyzer,
    CumulativeEquityCurves,
    TargetMilestoneAnalyzer,
    HoldingTimeAnalyzer
)


def test_forward_effect_size_comparison():
    eff = ForwardEffectSizeComparator.compare_effect_size(mode="PAPER")
    assert "historical_expectancy_r" in eff
    assert eff["historical_expectancy_r"] == 0.637
    assert "forward_expectancy_r" in eff
    assert "absolute_difference_r" in eff
    assert "expectancy_ratio_pct" in eff
    assert "interpretation" in eff


def test_rolling_forward_analyzer():
    res = RollingForwardAnalyzer.calculate_rolling_metrics(mode="PAPER", window_size=20)
    assert "window_size" in res
    assert res["window_size"] == 20
    assert "rolling_curve" in res
    assert "current_rolling_expectancy_r" in res


def test_cumulative_equity_curve_isolation():
    curves = CumulativeEquityCurves.get_equity_curves(mode="PAPER")
    assert "historical_curve" in curves
    assert "forward_curve" in curves
    assert len(curves["historical_curve"]) == 82
    assert curves["isolation_verified"] is True


def test_target_milestone_progression():
    milestones = TargetMilestoneAnalyzer.analyze_milestones(mode="PAPER")
    assert isinstance(milestones, list)
    assert len(milestones) == 6
    names = [m["milestone"] for m in milestones]
    assert "2R Target" in names
    assert "3R Target" in names
    assert "7R Target" in names


def test_holding_time_temporal_bucketing():
    buckets = HoldingTimeAnalyzer.analyze_holding_durations(mode="PAPER")
    assert isinstance(buckets, list)
    assert len(buckets) == 7
    labels = [b["bucket"] for b in buckets]
    assert "< 15 min" in labels
    assert "> 8 hours" in labels
