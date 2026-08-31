"""
Phase 38 — UI Rendering Compatibility & Component Payload Test Suite
Validates that Phase 38 data payloads convert cleanly into DataFrames, cards, and UI expanders.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
import pandas as pd
from xauusd_news_history_audit import HistoricalContextReconstructor
from xauusd_missed_event_detector import MissedEventAuditor
from xauusd_market_condition_correlation import (
    SubgroupCorrelationEngine,
    MarketContextDataQualityScorer,
    DailyContextCloseAuditor,
)
from xauusd_news_snapshot_store import MultiProviderComparator


def test_ui_dataframes_compatibility():
    """Validates that Phase 38 tables convert cleanly to pd.DataFrame."""
    target_dt = date(2026, 9, 1)

    # 1. Historical Reconstructed Events Table
    recon = HistoricalContextReconstructor.reconstruct_date_context(target_dt)
    df_events = pd.DataFrame(recon["events"])
    assert isinstance(df_events, pd.DataFrame)
    assert "event_name" in df_events.columns
    assert "impact" in df_events.columns

    # 2. Holiday Centers Table
    df_hol = pd.DataFrame(recon["holiday_audit"]["all_centers"])
    assert isinstance(df_hol, pd.DataFrame)
    assert len(df_hol) == 7

    # 3. Subgroups Correlation Table
    corr = SubgroupCorrelationEngine.audit_subgroup_correlations(mode="PAPER")
    df_corr = pd.DataFrame(corr["subgroups"])
    assert isinstance(df_corr, pd.DataFrame)
    assert len(df_corr) == 10

    # 4. Multi-Provider Comparison Table
    comp = MultiProviderComparator.compare_providers_for_date(target_dt)
    df_prov = pd.DataFrame(comp["providers"])
    assert isinstance(df_prov, pd.DataFrame)
    assert len(df_prov) == 3

    # 5. Data Quality Score Breakdown Table
    q_score = MarketContextDataQualityScorer.calculate_quality_score(target_dt)
    df_q = pd.DataFrame(q_score["breakdown"])
    assert isinstance(df_q, pd.DataFrame)
    assert len(df_q) == 6
