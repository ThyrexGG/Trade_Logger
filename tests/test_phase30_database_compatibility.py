"""
Phase 30 — Database Dialect Compatibility & Query Abstraction Tests
Validates that database helpers and query generators function interchangeably
across SQLite and PostgreSQL dialects without syntax collisions or unescaped placeholders.
"""

import sqlite3
import pandas as pd
import pytest
import database
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_forward_integrity import ForwardObservationProvenance
from xauusd_decision_history import XAUUSDDecisionHistory
from xauusd_alert_engine import XAUUSDAlertEngine
from xauusd_forward_evidence_ledger import ForwardEvidenceLedger
from xauusd_research_decision_audit import ResearchDecisionAuditEngine
from xauusd_research_governance import ResearchHypothesisFirewall


def test_centralized_placeholder_helper():
    """Validates get_sql_placeholder produces correct placeholder based on connection type."""
    # SQLite connection
    conn_sqlite = sqlite3.connect(":memory:")
    assert database.get_sql_placeholder(conn_sqlite) == "?"
    conn_sqlite.close()

    # None falls back to environment
    if database.is_postgres():
        assert database.get_sql_placeholder(None) == "%s"
    else:
        assert database.get_sql_placeholder(None) == "?"


def test_forward_journal_dialect_adaptation():
    """Validates forward journal signal logging and querying executes cleanly."""
    XAUUSDForwardJournal.init_forward_table()
    sig_id = XAUUSDForwardJournal.log_forward_signal({
        "symbol": "XAUUSD",
        "bias_1d": "BULLISH",
        "target_4h": "PDH",
        "sweep_15m": "Asian Low Swept",
        "mss_15m": "Bullish MSS",
        "conf_5m": "Confirmed",
        "entry_type_1m": "1M FVG Limit",
        "requested_entry": 2400.0,
        "stop_loss": 2398.5,
        "take_profit": 2404.5,
        "planned_rr": 3.0,
        "execution_mode": "PAPER",
        "status": "FILLED",
        "realized_r": 3.0
    })
    assert sig_id.startswith("FWD_")

    df_paper = XAUUSDForwardJournal.get_forward_trades(mode="PAPER")
    assert isinstance(df_paper, pd.DataFrame)
    assert not df_paper.empty
    assert "execution_mode" in df_paper.columns


def test_provenance_and_integrity_dialect_adaptation():
    """Validates observation provenance recording and querying executes cleanly."""
    ForwardObservationProvenance.init_provenance_table()
    obs_id = ForwardObservationProvenance.record_provenance({
        "symbol": "XAUUSD",
        "bid": 2400.30,
        "ask": 2400.50,
        "spread_pips": 2.0,
        "atr_1m": 1.45,
        "detected_regime": "BULLISH_TREND",
        "setup_state": "15M_SWEEP_MSS_CONFIRMED",
        "entry_decision": "LIMIT_ORDER_PLACED",
        "limit_price": 2400.50,
        "stop_loss": 2398.50,
        "take_profit_1": 2404.50,
        "take_profit_2": 2415.00,
        "risk_pct": 0.50,
        "order_state": "FILLED",
        "execution_mode": "PAPER"
    })
    assert obs_id.startswith("OBS_XAU_")

    df_prov = ForwardObservationProvenance.get_all_provenance(mode="PAPER")
    assert isinstance(df_prov, pd.DataFrame)
    assert not df_prov.empty


def test_alert_engine_dialect_adaptation():
    """Validates alert logging, filtering, and acknowledgement."""
    XAUUSDAlertEngine.init_events_table()
    evt_id = XAUUSDAlertEngine.log_event({
        "event_type": "CUSUM_DRIFT",
        "severity": "WARNING",
        "metric": "CUSUM_SCORE",
        "observed_value": 4.2,
        "baseline_value": 0.0,
        "threshold": 4.0,
        "explanation": "CUSUM score exceeded warning threshold.",
        "recommended_action": "Monitor next 5 forward executions closely."
    })
    assert evt_id.startswith("EVT_")

    events = XAUUSDAlertEngine.get_events(severity_filter="WARNING", limit=10)
    assert len(events) >= 1

    ack = XAUUSDAlertEngine.acknowledge_alert(evt_id)
    assert ack is True


def test_evidence_ledger_dialect_adaptation():
    """Validates immutable evidence ledger creation and querying."""
    ForwardEvidenceLedger.init_table()
    snap_id = ForwardEvidenceLedger.create_snapshot({
        "trades_n": 10,
        "expectancy_r": 0.55,
        "median_r": 0.50,
        "win_rate_pct": 60.0,
        "profit_factor": 2.1,
        "max_drawdown_r": 2.5,
        "recovery_factor": 2.2,
        "ci_90_lower": 0.1,
        "ci_90_upper": 1.0,
        "ci_95_lower": 0.05,
        "ci_95_upper": 1.05,
        "ci_99_lower": -0.05,
        "ci_99_upper": 1.15,
        "hist_expectancy_diff": -0.087,
        "hist_expectancy_ratio": 0.863,
        "governance_stage": "Stage 0",
        "evidence_score": 75.0,
        "research_decision_state": "CONTINUE MONITORING",
        "next_milestone": "N = 30"
    })
    assert snap_id.startswith("SNAP_")

    snaps = ForwardEvidenceLedger.get_snapshots(limit=5)
    assert len(snaps) >= 1
    assert isinstance(snaps[0], dict)

    single = ForwardEvidenceLedger.get_snapshot_by_id(snap_id)
    assert single is not None
    assert single["snapshot_id"] == snap_id


def test_decision_history_and_audit_dialect_adaptation():
    """Validates decision history and research governance audit trail."""
    XAUUSDDecisionHistory.init_history_table()
    dec_id = XAUUSDDecisionHistory.record_decision_snapshot({
        "stage": "Stage 0 (Data Accumulation)",
        "forward_n": 15,
        "expectancy_r": 0.45,
        "ci_lower": 0.10,
        "ci_upper": 0.80,
        "drawdown_r": 1.8,
        "execution_health": "OPTIMAL",
        "drift_status": "CONSISTENT",
        "integrity_status": "PASS",
        "overall_decision": "COLLECTING FORWARD DATA",
        "next_action": "Continue forward observations."
    })
    assert dec_id.startswith("DEC_")

    timeline = XAUUSDDecisionHistory.get_decision_timeline(limit=10)
    assert len(timeline) >= 1

    ResearchDecisionAuditEngine.init_table()
    audit_id = ResearchDecisionAuditEngine.record_audit_decision({
        "current_stage": "Stage 0 — Monitoring",
        "trades_n": 15,
        "evidence_score": 78.5,
        "expectancy_r": 0.45,
        "ci_95_str": "[+0.100R, +0.800R]",
        "drawdown_r": 1.8,
        "drift_state": "CONSISTENT",
        "execution_state": "OPTIMAL",
        "integrity_state": "PASS",
        "decision_state": "CONTINUE MONITORING",
        "reasons": ["Baseline alignment active"],
        "unresolved_uncertainties": ["Sample N < 30"],
        "recommended_next_action": "Accumulate forward sample."
    })
    assert audit_id.startswith("AUDIT_")

    history = ResearchDecisionAuditEngine.get_audit_history(limit=5)
    assert len(history) >= 1
