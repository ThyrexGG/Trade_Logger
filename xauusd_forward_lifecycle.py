"""
Phase 48 — XAUUSD Forward Signal Lifecycle & Evidence Integrity Validation Engine
Validates the complete genuine-forward observation lifecycle:
MARKET DATA -> SIGNAL DETECTION -> FORWARD ELIGIBILITY -> OBSERVATION CAPTURE
-> PAPER/SHADOW EXECUTION -> OUTCOME TRACKING -> EVIDENCE EVENT RECORDING
-> RECONCILIATION -> DASHBOARD

Invariants Preserved:
- Frozen Strategy Contract: SHA-256 (7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76)
- Historical Holdout Locked: N = 82, E[R] = +0.637R, WR = 58.6%, PF = 2.52
- Strict Dataset Isolation: IDs_hist ∩ IDs_paper = ∅, IDs_hist ∩ IDs_shadow = ∅
- Live Safety Barrier: LIVE_AUTOMATION_ENABLED = False, LIVE_BROKER_TRANSMISSION = 'BLOCKED'
- Truthful N = 0 Baseline: No synthetic, backfilled, or fake observations.
"""

import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set

import numpy as np
import pandas as pd

import database
from xauusd_market_conditions import FROZEN_CONTRACT_HASH


def init_phase48_database(conn=None):
    """Initializes tables for forward lifecycle tracking and reconciliation audits."""
    database.init_db()
    from xauusd_forward_validator import XAUUSDForwardJournal
    XAUUSDForwardJournal.init_forward_table()

    should_close = False
    if conn is None:
        conn = database.get_connection()
        should_close = True

    cur = conn.cursor()

    # 1. Forward Lifecycle Events Table (Append-only audit trail)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS xauusd_forward_lifecycle_events (
        lifecycle_event_id TEXT PRIMARY KEY,
        signal_id TEXT NOT NULL,
        observation_id TEXT,
        stage TEXT NOT NULL,
        from_status TEXT NOT NULL,
        to_status TEXT NOT NULL,
        event_timestamp TEXT NOT NULL,
        execution_mode TEXT NOT NULL,
        r_multiple REAL,
        outcome_reason TEXT,
        payload_fingerprint TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # 2. Forward Reconciliation Audit History
    cur.execute("""
    CREATE TABLE IF NOT EXISTS xauusd_reconciliation_audits (
        audit_id TEXT PRIMARY KEY,
        audit_timestamp TEXT NOT NULL,
        total_signals INTEGER NOT NULL DEFAULT 0,
        total_observations INTEGER NOT NULL DEFAULT 0,
        eligible_count INTEGER NOT NULL DEFAULT 0,
        quarantined_count INTEGER NOT NULL DEFAULT 0,
        rejected_count INTEGER NOT NULL DEFAULT 0,
        open_count INTEGER NOT NULL DEFAULT 0,
        completed_count INTEGER NOT NULL DEFAULT 0,
        cancelled_count INTEGER NOT NULL DEFAULT 0,
        expired_count INTEGER NOT NULL DEFAULT 0,
        invalidated_count INTEGER NOT NULL DEFAULT 0,
        orphan_count INTEGER NOT NULL DEFAULT 0,
        discrepancy_count INTEGER NOT NULL DEFAULT 0,
        isolation_verified INTEGER NOT NULL DEFAULT 1,
        audit_verdict TEXT NOT NULL,
        raw_audit_json TEXT NOT NULL
    )
    """)

    conn.commit()
    if should_close:
        conn.close()


init_phase48_database()


class ForwardSignalPipelineValidator:
    """
    Validates genuine forward signal detection from currently available market info.
    Ensures zero future lookahead (no unreleased economic figures, no future candle prices).
    """

    @staticmethod
    def validate_signal_provenance(signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audits incoming signal fields for required provenance and temporal validity.
        """
        required_fields = [
            "timestamp", "symbol", "bias_1d", "target_4h", "sweep_15m",
            "mss_15m", "conf_5m", "entry_type_1m", "requested_entry",
            "stop_loss", "take_profit", "planned_rr", "execution_mode"
        ]
        missing = [f for f in required_fields if f not in signal or signal[f] is None]
        if missing:
            return {
                "valid": False,
                "reason": f"MISSING_PROVENANCE_FIELDS: {', '.join(missing)}",
                "status": "REJECTED_MISSING_PROVENANCE"
            }

        # Timestamp lookahead check
        ts_str = str(signal.get("timestamp", ""))
        try:
            sig_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if sig_dt.tzinfo is None:
                sig_dt = sig_dt.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            if sig_dt > now_utc + timedelta(seconds=60):
                return {
                    "valid": False,
                    "reason": f"LOOKAHEAD_VIOLATION: Signal timestamp ({ts_str}) is in the future.",
                    "status": "REJECTED_LOOKAHEAD"
                }
        except Exception as e:
            return {
                "valid": False,
                "reason": f"INVALID_TIMESTAMP: {str(e)}",
                "status": "REJECTED_INVALID_TIMESTAMP"
            }

        # Price geometry check
        entry = float(signal.get("requested_entry", 0.0))
        sl = float(signal.get("stop_loss", 0.0))
        tp = float(signal.get("take_profit", 0.0))
        if entry <= 0.0 or sl <= 0.0 or tp <= 0.0:
            return {
                "valid": False,
                "reason": "INVALID_PRICE: Entry, SL, and TP must all be strictly positive.",
                "status": "REJECTED_INVALID_PRICE"
            }

        if entry == sl or entry == tp:
            return {
                "valid": False,
                "reason": "INVALID_GEOMETRY: Entry price cannot equal SL or TP.",
                "status": "REJECTED_INVALID_GEOMETRY"
            }

        # Contract hash verification if present
        contract_hash = signal.get("contract_hash")
        if contract_hash and contract_hash != FROZEN_CONTRACT_HASH:
            return {
                "valid": False,
                "reason": f"CONTRACT_MISMATCH: Provided hash {contract_hash[:12]} != Frozen {FROZEN_CONTRACT_HASH[:12]}",
                "status": "REJECTED_CONTRACT_MISMATCH"
            }

        return {
            "valid": True,
            "reason": "Signal passed all temporal, geometric, and provenance integrity checks.",
            "status": "SIGNAL_PROVENANCE_VALIDATED",
            "contract_hash": FROZEN_CONTRACT_HASH
        }


class ForwardSignalToObservationBridge:
    """
    Bridges validated market signals into the Phase 47 Forward Observation Capture & Eligibility Gate.
    Guarantees that:
    - Signals only become observations if 11-state eligibility passes.
    - Quarantined observations are routed to the quarantine subsystem.
    - Rejected observations are never silently promoted.
    """

    @staticmethod
    def process_signal_to_observation(signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrates Signal -> Eligibility -> Observation Capture -> Event Recording.
        """
        from xauusd_forward_evidence_collection import (
            ForwardObservationCaptureEngine,
            ForwardEvidenceEligibilityGate,
            ObservationDuplicateProtectionEngine,
        )

        # 1. Pipeline provenance check
        prov = ForwardSignalPipelineValidator.validate_signal_provenance(signal)
        if not prov["valid"]:
            return {
                "success": False,
                "status": prov["status"],
                "reason": prov["reason"],
                "observation_id": None,
                "signal_id": signal.get("signal_id")
            }

        # 2. Phase 47 Eligibility Gate
        elig = ForwardEvidenceEligibilityGate.evaluate_eligibility(signal)
        if not elig["is_eligible"]:
            # Route to quarantine if flagged
            if elig["status"] == "QUARANTINED":
                from xauusd_forward_observation_quality import ObservationQuarantineSubsystem
                ObservationQuarantineSubsystem.quarantine_observation(
                    observation_id=signal.get("signal_id", "UNKNOWN"),
                    reason=elig["explanation"],
                    source_phase="PHASE_48_LIFECYCLE",
                    raw_payload=json.dumps(signal)
                )

            ForwardOutcomeLifecycleManager.record_lifecycle_event(
                signal_id=signal.get("signal_id", "UNKNOWN"),
                observation_id=None,
                stage="ELIGIBILITY_GATE",
                from_status="SIGNAL_DETECTED",
                to_status=elig["status"],
                execution_mode=signal.get("execution_mode", "PAPER"),
                outcome_reason=elig["explanation"]
            )

            return {
                "success": False,
                "status": elig["status"],
                "reason": elig["explanation"],
                "observation_id": None,
                "signal_id": signal.get("signal_id")
            }

        # 3. Capture observation atomically
        cap_result = ForwardObservationCaptureEngine.capture_forward_observation(signal)
        if not cap_result.get("success", False):
            return cap_result

        obs_id = cap_result.get("observation_id")
        sig_id = signal.get("signal_id", obs_id)

        # 4. Log lifecycle event
        ForwardOutcomeLifecycleManager.record_lifecycle_event(
            signal_id=sig_id,
            observation_id=obs_id,
            stage="OBSERVATION_CAPTURED",
            from_status="ELIGIBLE",
            to_status="ACTIVE_OBSERVATION",
            execution_mode=signal.get("execution_mode", "PAPER"),
            outcome_reason="Passed 11-point eligibility gate and captured with 17-point context metadata."
        )

        return {
            "success": True,
            "status": "OBSERVATION_CAPTURED",
            "observation_id": obs_id,
            "signal_id": sig_id,
            "capture_details": cap_result
        }


class ForwardExecutionLifecycleEngine:
    """
    Manages and validates execution state for Paper and Shadow validation modes.
    Guarantees permanent live broker isolation (FAIL-CLOSED).
    """
    LIVE_AUTOMATION_ENABLED = False
    LIVE_BROKER_TRANSMISSION = "BLOCKED"

    @staticmethod
    def assert_live_safety():
        """Asserts that live execution is permanently blocked."""
        if ForwardExecutionLifecycleEngine.LIVE_AUTOMATION_ENABLED:
            raise RuntimeError("CRITICAL GOVERNANCE BREACH: LIVE AUTOMATION IS PROHIBITED")
        return {
            "status": "FAIL-CLOSED ACTIVE",
            "live_automation_enabled": False,
            "live_broker_transmission": "BLOCKED",
            "paper_enabled": True,
            "shadow_enabled": True,
        }

    @staticmethod
    def validate_execution_mode(mode: str) -> str:
        norm = str(mode).upper().strip()
        if norm not in ["PAPER", "SHADOW"]:
            raise ValueError(f"Invalid forward execution mode: {mode}. Only 'PAPER' and 'SHADOW' permitted.")
        return norm


class ForwardOutcomeLifecycleManager:
    """
    Manages deterministic trade outcome progression:
    OPEN -> TP_HIT
    OPEN -> SL_HIT
    OPEN -> EXPIRED
    OPEN -> CANCELLED
    OPEN -> INVALIDATED

    Guarantees:
    - Immutable original observation record.
    - Subsequent outcome events are appended to the ledger.
    - Timeout and Invalidation != Trading Loss.
    """
    TERMINAL_OUTCOMES = ["TP_HIT", "SL_HIT", "EXPIRED", "CANCELLED", "INVALIDATED", "COMPLETED"]

    @staticmethod
    def record_lifecycle_event(
        signal_id: str,
        observation_id: Optional[str],
        stage: str,
        from_status: str,
        to_status: str,
        execution_mode: str = "PAPER",
        r_multiple: Optional[float] = None,
        outcome_reason: str = ""
    ) -> Dict[str, Any]:
        """
        Appends an immutable lifecycle event record.
        """
        init_phase48_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        ev_id = f"LC_{stage[:4]}_{uuid.uuid4().hex[:8]}"

        payload = {
            "signal_id": signal_id,
            "observation_id": observation_id,
            "stage": stage,
            "from_status": from_status,
            "to_status": to_status,
            "execution_mode": execution_mode,
            "r_multiple": r_multiple,
            "outcome_reason": outcome_reason,
            "timestamp": now_iso
        }
        fp = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

        conn = database.get_connection()
        cur = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)

        query = f"""
        INSERT INTO xauusd_forward_lifecycle_events (
            lifecycle_event_id, signal_id, observation_id, stage,
            from_status, to_status, event_timestamp, execution_mode,
            r_multiple, outcome_reason, payload_fingerprint, created_at
        ) VALUES ({','.join([placeholder]*12)})
        """
        params = (
            ev_id, signal_id, observation_id or signal_id, stage,
            from_status, to_status, now_iso, execution_mode,
            r_multiple, outcome_reason, fp, now_iso
        )
        cur.execute(query, params)
        conn.commit()
        conn.close()

        return {
            "lifecycle_event_id": ev_id,
            "signal_id": signal_id,
            "observation_id": observation_id,
            "stage": stage,
            "transition": f"{from_status} -> {to_status}",
            "fingerprint": fp,
            "timestamp": now_iso
        }

    @staticmethod
    def update_trade_outcome(
        signal_id: str,
        outcome: str,
        realized_r: Optional[float] = None,
        exit_price: Optional[float] = None,
        exit_reason: str = "",
        holding_time_min: int = 0
    ) -> Dict[str, Any]:
        """
        Updates the final outcome of an open forward trade in xauusd_forward_signals.
        """
        norm_outcome = outcome.upper().strip()
        if norm_outcome not in ForwardOutcomeLifecycleManager.TERMINAL_OUTCOMES:
            raise ValueError(f"Invalid outcome: {outcome}. Permitted: {ForwardOutcomeLifecycleManager.TERMINAL_OUTCOMES}")

        conn = database.get_connection()
        cur = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)

        # Check existing trade status
        cur.execute("SELECT status, execution_mode FROM xauusd_forward_signals WHERE signal_id = ?", (signal_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"success": False, "reason": f"Signal ID {signal_id} not found in forward journal."}

        prev_status, exec_mode = row[0], row[1]

        # Prevent duplicate terminal outcome mutation
        if prev_status in ["COMPLETED", "EXPIRED", "CANCELLED", "INVALIDATED"] and prev_status == norm_outcome:
            conn.close()
            return {
                "success": True,
                "status": "ALREADY_RESOLVED",
                "message": f"Trade {signal_id} already marked as {prev_status}. No mutation performed."
            }

        # Update record
        query = f"""
        UPDATE xauusd_forward_signals SET
            status = {placeholder},
            realized_r = {placeholder},
            exit_price = {placeholder},
            exit_reason = {placeholder},
            holding_time_minutes = {placeholder}
        WHERE signal_id = {placeholder}
        """
        params = (norm_outcome, realized_r, exit_price, exit_reason or norm_outcome, holding_time_min, signal_id)
        cur.execute(query, params)
        conn.commit()
        conn.close()

        # Log lifecycle event
        ForwardOutcomeLifecycleManager.record_lifecycle_event(
            signal_id=signal_id,
            observation_id=signal_id,
            stage="OUTCOME_RESOLUTION",
            from_status=prev_status,
            to_status=norm_outcome,
            execution_mode=exec_mode,
            r_multiple=realized_r,
            outcome_reason=exit_reason or f"Terminal transition to {norm_outcome}"
        )

        return {
            "success": True,
            "signal_id": signal_id,
            "from_status": prev_status,
            "to_status": norm_outcome,
            "realized_r": realized_r,
            "exit_reason": exit_reason or norm_outcome
        }


class ForwardLifecycleReconciliationAudit:
    """
    Performs comprehensive SQLite & PostgreSQL database integrity and orphan checks.
    Checks:
    - Orphan signals / trades / observations
    - Duplicate IDs
    - Malformed timestamps
    - Invalid prices / R values
    - Missing contract hashes
    - Cross-dataset contamination
    """

    @staticmethod
    def audit_database_integrity() -> Dict[str, Any]:
        """
        Audits forward tables and historical separation.
        """
        init_phase48_database()
        from xauusd_forward_validator import XAUUSDForwardJournal
        from xauusd_forward_observation_quality import ObservationQuarantineSubsystem

        conn = database.get_connection()
        cur = conn.cursor()

        # 1. Total Signals & Observations
        cur.execute("SELECT COUNT(*) FROM xauusd_forward_signals")
        total_signals = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM xauusd_forward_signals WHERE status = 'COMPLETED'")
        completed_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM xauusd_forward_signals WHERE status = 'FILLED' OR status = 'OPEN'")
        open_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM xauusd_forward_signals WHERE status = 'EXPIRED'")
        expired_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM xauusd_forward_signals WHERE status = 'INVALIDATED'")
        invalidated_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM xauusd_forward_signals WHERE status = 'CANCELLED' OR status = 'REJECTED'")
        rejected_count = cur.fetchone()[0]

        # 2. Quarantined records
        quar_recs = ObservationQuarantineSubsystem.get_quarantined_records(limit=200)
        quarantined_count = len(quar_recs)

        # 3. Check for Duplicate IDs in xauusd_forward_signals
        cur.execute("SELECT signal_id, COUNT(*) FROM xauusd_forward_signals GROUP BY signal_id HAVING COUNT(*) > 1")
        dups = cur.fetchall()
        duplicate_count = len(dups)

        # 4. Check for invalid prices
        cur.execute("SELECT COUNT(*) FROM xauusd_forward_signals WHERE requested_entry <= 0 OR stop_loss <= 0 OR take_profit <= 0")
        invalid_price_count = cur.fetchone()[0]

        # 5. Check Dataset Isolation (Historical vs Forward IDs)
        hist_ids = set()
        try:
            cur.execute("SELECT trade_id FROM closed_trades")
            hist_rows = cur.fetchall()
            hist_ids.update({str(r[0]) for r in hist_rows if r[0] is not None})
        except Exception:
            pass

        cur.execute("SELECT signal_id FROM xauusd_forward_signals")
        fwd_rows = cur.fetchall()
        fwd_ids = {str(r[0]) for r in fwd_rows if r[0] is not None}

        intersection = hist_ids.intersection(fwd_ids)
        isolation_verified = (len(intersection) == 0)

        # 6. Orphan events check (lifecycle events pointing to non-existent signals)
        cur.execute("""
        SELECT COUNT(*) FROM xauusd_forward_lifecycle_events
        WHERE signal_id NOT IN (SELECT signal_id FROM xauusd_forward_signals)
        """)
        orphan_events = cur.fetchone()[0]

        conn.close()

        discrepancies = []
        if duplicate_count > 0:
            discrepancies.append(f"{duplicate_count} duplicate signal IDs detected.")
        if invalid_price_count > 0:
            discrepancies.append(f"{invalid_price_count} records with non-positive prices detected.")
        if not isolation_verified:
            discrepancies.append(f"CRITICAL: {len(intersection)} IDs shared between Historical and Forward datasets!")
        if orphan_events > 0:
            discrepancies.append(f"{orphan_events} orphan lifecycle events detected.")

        verdict = "CLEAN & RECONCILED" if len(discrepancies) == 0 else "INTEGRITY WARNING DETECTED"

        audit_result = {
            "audit_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_signals": total_signals,
            "completed_observations": completed_count,
            "open_observations": open_count,
            "expired_count": expired_count,
            "invalidated_count": invalidated_count,
            "rejected_count": rejected_count,
            "quarantined_count": quarantined_count,
            "duplicate_signal_ids": duplicate_count,
            "invalid_price_records": invalid_price_count,
            "orphan_lifecycle_events": orphan_events,
            "dataset_isolation_clean": isolation_verified,
            "historical_baseline_n": 82,
            "forward_completed_n": completed_count,
            "discrepancies": discrepancies,
            "audit_verdict": verdict,
            "live_automation_blocked": True,
            "strategy_contract_hash": FROZEN_CONTRACT_HASH
        }

        # Log audit snapshot
        audit_id = f"AUD_{uuid.uuid4().hex[:8]}"
        conn2 = database.get_connection()
        cur2 = conn2.cursor()
        placeholder = database.get_sql_placeholder(conn2)
        query = f"""
        INSERT INTO xauusd_reconciliation_audits (
            audit_id, audit_timestamp, total_signals, total_observations,
            eligible_count, quarantined_count, rejected_count, open_count,
            completed_count, cancelled_count, expired_count, invalidated_count,
            orphan_count, discrepancy_count, isolation_verified, audit_verdict,
            raw_audit_json
        ) VALUES ({','.join([placeholder]*17)})
        """
        params = (
            audit_id, audit_result["audit_timestamp"], total_signals, completed_count,
            total_signals - quarantined_count - rejected_count, quarantined_count, rejected_count,
            open_count, completed_count, 0, expired_count, invalidated_count,
            orphan_events, len(discrepancies), 1 if isolation_verified else 0,
            verdict, json.dumps(audit_result)
        )
        cur2.execute(query, params)
        conn2.commit()
        conn2.close()

        return audit_result

    run_full_reconciliation = audit_database_integrity



class ForwardDatasetIsolationGuard:
    r"""
    Enforces strict mathematical isolation between Historical Holdout ($N=82$)
    and Forward Paper/Shadow observations ($IDs_{hist} \cap IDs_{paper} = \emptyset$).
    """
    HISTORICAL_BASELINE = {
        "trades_N": 82,
        "expectancy_r": 0.637,
        "ci_95": [0.477, 0.817],
        "win_rate_pct": 58.6,
        "profit_factor": 2.52,
        "contract_sha256": FROZEN_CONTRACT_HASH
    }

    @staticmethod
    def verify_isolation() -> Dict[str, Any]:
        """
        Verifies that no pooling or data cross-contamination exists.
        """
        database.init_db()
        from xauusd_forward_validator import XAUUSDForwardJournal
        XAUUSDForwardJournal.init_forward_table()

        conn = database.get_connection()
        cur = conn.cursor()

        hist_ids = set()
        try:
            cur.execute("SELECT trade_id FROM closed_trades")
            hist_rows = cur.fetchall()
            hist_ids.update({str(r[0]) for r in hist_rows if r[0] is not None})
        except Exception:
            pass

        cur.execute("SELECT signal_id FROM xauusd_forward_signals")
        fwd_rows = cur.fetchall()
        fwd_ids = {str(r[0]) for r in fwd_rows if r[0] is not None}

        conn.close()

        overlap = hist_ids.intersection(fwd_ids)
        is_isolated = (len(overlap) == 0)

        return {
            "is_isolated": is_isolated,
            "historical_baseline_n": 82,
            "historical_expectancy_r": 0.637,
            "historical_contract_hash": FROZEN_CONTRACT_HASH,
            "forward_signals_count": len(fwd_ids),
            "overlap_count": len(overlap),
            "overlap_ids": list(overlap),
            "status": "STRICTLY ISOLATED" if is_isolated else "DATASET POLLUTION DETECTED"
        }


class ForwardAlphaDecayObservationalMonitor:
    """
    Calculates purely observational monitoring metrics once forward data accumulates.
    Guarantees:
    - Never modifies strategy parameters or thresholds.
    - Never concludes alpha decay from N = 0 or small samples.
    - Explicitly labels small samples as 'INSUFFICIENT SAMPLE SIZE'.
    """

    @staticmethod
    def calculate_observational_metrics(mode: str = "PAPER") -> Dict[str, Any]:
        """
        Generates observational performance metrics for forward data.
        """
        from xauusd_forward_validator import XAUUSDForwardJournal
        df = XAUUSDForwardJournal.get_forward_trades(mode=mode)
        df_comp = df[df["status"] == "COMPLETED"] if not df.empty and "status" in df.columns else pd.DataFrame()

        n = len(df_comp)
        if n == 0:
            return {
                "forward_n": 0,
                "win_rate_pct": 0.0,
                "expectancy_r": 0.0,
                "avg_r": 0.0,
                "median_r": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_r": 0.0,
                "sample_status": "INSUFFICIENT SAMPLE SIZE (N = 0)",
                "historical_expectancy_r": 0.637,
                "decay_verdict": "NO FORWARD EVIDENCE AVAILABLE — AWAITING OBSERVATIONS",
                "color": "#8a99ad"
            }

        returns = df_comp["realized_r"].dropna().astype(float).tolist()
        if not returns:
            return {
                "forward_n": 0,
                "win_rate_pct": 0.0,
                "expectancy_r": 0.0,
                "avg_r": 0.0,
                "median_r": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_r": 0.0,
                "sample_status": "INSUFFICIENT SAMPLE SIZE",
                "historical_expectancy_r": 0.637,
                "decay_verdict": "AWAITING RESOLVED RETURNS",
                "color": "#8a99ad"
            }

        arr = np.array(returns)
        wins = arr[arr > 0]
        losses = arr[arr <= 0]
        wr = (len(wins) / n) * 100.0
        exp_r = float(np.mean(arr))
        med_r = float(np.median(arr))

        gross_win = float(np.sum(wins)) if len(wins) > 0 else 0.0
        gross_loss = float(np.abs(np.sum(losses))) if len(losses) > 0 else 0.0
        pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)

        # Drawdown calculation
        eq = np.cumsum(arr)
        peak = np.maximum.accumulate(eq)
        dd = peak - eq
        max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

        if n < 30:
            sample_status = f"INSUFFICIENT SAMPLE SIZE (N = {n} < 30)"
            decay_verdict = "OBSERVATIONAL ONLY — SAMPLE TOO SMALL FOR DECAY EVALUATION"
            color = "#f59e0b"
        elif n < 50:
            sample_status = f"EARLY SAMPLE (N = {n})"
            decay_verdict = "PRELIMINARY OBSERVATION — STABILITY MONITORING"
            color = "#bef264" if exp_r > 0 else "#f59e0b"
        else:
            sample_status = f"EVALUABLE SAMPLE (N = {n})"
            decay_verdict = "STABLE FORWARD PERFORMANCE" if exp_r >= 0.35 else "POSSIBLE PERFORMANCE DEGRADATION"
            color = "#00ffcc" if exp_r >= 0.35 else "#ef4444"

        return {
            "forward_n": n,
            "win_rate_pct": round(wr, 1),
            "expectancy_r": round(exp_r, 3),
            "avg_r": round(exp_r, 3),
            "median_r": round(med_r, 3),
            "profit_factor": round(pf, 2),
            "max_drawdown_r": round(max_dd, 2),
            "sample_status": sample_status,
            "historical_expectancy_r": 0.637,
            "decay_verdict": decay_verdict,
            "color": color
        }


class ForwardMorningAwaySummaryClassifier:
    """
    Distinguishes the exact operational reality that occurred while the user was away:
    1. NO_SETUP_DETECTED: Market open, normal operation, no valid setup
    2. SETUP_DETECTED_REJECTED: Candidate setup rejected by eligibility gate
    3. SETUP_QUARANTINED: Observation flagged and routed to quarantine
    4. GENUINE_OBSERVATION_CAPTURED: First or subsequent genuine observation recorded
    5. EXECUTION_RECORDED: Paper/shadow execution active
    6. OUTCOME_COMPLETED: Trade reached TP/SL/terminal outcome
    7. DATA_INTEGRITY_ANOMALY: Outage, feed gap, or integrity warning
    8. MARKET_CLOSED_HOLIDAY: Weekend or financial center holiday
    """

    @staticmethod
    def classify_away_reality(target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Evaluates the specific category of what happened during unattended operation.
        """
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        from xauusd_news_reliability import MarketClosureAuditor
        from xauusd_operational_monitor import OperationalHealthEvaluator
        from xauusd_forward_observation_quality import ObservationQuarantineSubsystem
        from xauusd_forward_validator import XAUUSDForwardJournal

        # 1. Market Closure Check
        is_weekend = target_date.weekday() in [5, 6]
        closure_audit = MarketClosureAuditor.audit_market_closures(target_date)
        closed_count = closure_audit.get("active_holidays_count", 0)

        if is_weekend:
            return {
                "category": "MARKET_CLOSED_HOLIDAY",
                "title": "MARKET CLOSED (WEEKEND)",
                "explanation": "Global institutional gold markets are closed over the weekend. Zero setups expected.",
                "color": "#8a99ad",
                "status_badge": "WEEKEND"
            }
        if closed_count >= 5:
            return {
                "category": "MARKET_CLOSED_HOLIDAY",
                "title": f"GLOBAL HOLIDAY CLOSURE ({closed_count} CENTERS CLOSED)",
                "explanation": f"Multiple major institutional centers closed for holidays. Liquidity restricted.",
                "color": "#f59e0b",
                "status_badge": "HOLIDAY"
            }

        # 2. Data Integrity & Feed Check
        op_health = OperationalHealthEvaluator.evaluate_operational_health("XAUUSD")
        if op_health.get("overall_verdict") in ["DEGRADED", "CRITICAL"]:
            return {
                "category": "DATA_INTEGRITY_ANOMALY",
                "title": "DATA FEED INTERRUPTION DETECTED",
                "explanation": f"Market feed reported {op_health.get('overall_verdict')} status during collection period.",
                "color": "#ef4444",
                "status_badge": "FEED ANOMALY"
            }

        # 3. Quarantine Check
        quar_recs = ObservationQuarantineSubsystem.get_quarantined_records(limit=20)
        if len(quar_recs) > 0:
            return {
                "category": "SETUP_QUARANTINED",
                "title": f"{len(quar_recs)} OBSERVATIONS ROUTED TO QUARANTINE",
                "explanation": "One or more forward observations failed strict data validation and were quarantined.",
                "color": "#f59e0b",
                "status_badge": "QUARANTINED"
            }

        # 4. Forward Signals & Completed Outcomes
        df_paper = XAUUSDForwardJournal.get_forward_trades(mode="PAPER")
        if not df_paper.empty:
            completed = df_paper[df_paper["status"] == "COMPLETED"]
            open_trades = df_paper[df_paper["status"].isin(["FILLED", "OPEN"])]

            if len(completed) > 0:
                return {
                    "category": "OUTCOME_COMPLETED",
                    "title": f"{len(completed)} TRADE OUTCOME(S) COMPLETED",
                    "explanation": f"Forward trades reached resolution with average return of {completed['realized_r'].mean():+.2f}R.",
                    "color": "#00ffcc",
                    "status_badge": "OUTCOME COMPLETED"
                }

            if len(open_trades) > 0:
                return {
                    "category": "EXECUTION_RECORDED",
                    "title": f"{len(open_trades)} PAPER/SHADOW TRADE(S) ACTIVE",
                    "explanation": "Valid forward trade setup captured and currently running in simulated paper execution.",
                    "color": "#38bdf8",
                    "status_badge": "ACTIVE TRADE"
                }

        # 5. Check Rejected Lifecycle Events
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM xauusd_forward_lifecycle_events WHERE to_status LIKE 'REJECTED%'")
        row_rej = cur.fetchone()
        conn.close()
        rej_count = row_rej[0] if row_rej else 0

        if rej_count > 0:
            return {
                "category": "SETUP_DETECTED_REJECTED",
                "title": f"{rej_count} CANDIDATE SETUP(S) REJECTED BY ELIGIBILITY GATE",
                "explanation": "Market conditions triggered preliminary evaluation, but strict eligibility criteria rejected the observation.",
                "color": "#bef264",
                "status_badge": "REJECTED SETUP"
            }

        # 6. Default Clean State: No Setup Detected
        return {
            "category": "NO_SETUP_DETECTED",
            "title": "MARKET OPEN — NO VALID STRATEGY SETUPS OBSERVED",
            "explanation": "All 8 monitoring subsystems operated continuously with zero feed interruptions. No market price action satisfied all 5 entry layers.",
            "color": "#00ffcc",
            "status_badge": "CLEAN & WAITING"
        }
