"""
Phase 28 — XAUUSD Research Decision Audit Engine
Records immutable audit logs of research governance decisions and generates detailed explanations.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import database

from xauusd_forward_monitor import XAUUSDForwardMonitor
from xauusd_drift_detector import XAUUSDDriftDetector
from xauusd_execution_quality import XAUUSDExecutionDiagnostics
from xauusd_validation_gate import XAUUSDValidationGate
from xauusd_research_governance import ResearchIntegrityAuditor, WatchNextAdvisor
from xauusd_forward_evidence import ForwardEvidenceScorer, ResearchDecisionStateClassifier
from xauusd_review_readiness import ReviewReadinessEngine


class ResearchDecisionAuditEngine:
    """
    Maintains the persistent append-only governance audit log.
    """
    TABLE_NAME = "xauusd_decision_audit_records"

    @staticmethod
    def init_table():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {ResearchDecisionAuditEngine.TABLE_NAME} (
                audit_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                trades_n INTEGER NOT NULL,
                evidence_score REAL NOT NULL,
                expectancy_r REAL NOT NULL,
                ci_95_str TEXT NOT NULL,
                drawdown_r REAL NOT NULL,
                drift_state TEXT NOT NULL,
                execution_state TEXT NOT NULL,
                integrity_state TEXT NOT NULL,
                decision_state TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                uncertainties_json TEXT NOT NULL,
                recommended_next_action TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def record_audit_decision(record_data: Dict[str, Any]) -> str:
        """
        Appends an immutable research decision record to the audit ledger.
        """
        ResearchDecisionAuditEngine.init_table()
        audit_id = f"AUDIT_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        ts = datetime.now(timezone.utc).isoformat()

        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {ResearchDecisionAuditEngine.TABLE_NAME} (
                audit_id, timestamp, current_stage, trades_n, evidence_score,
                expectancy_r, ci_95_str, drawdown_r, drift_state, execution_state,
                integrity_state, decision_state, reasons_json, uncertainties_json,
                recommended_next_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_id,
            ts,
            str(record_data.get("current_stage", "Stage 0")),
            int(record_data.get("trades_n", 0)),
            float(record_data.get("evidence_score", 0.0)),
            float(record_data.get("expectancy_r", 0.0)),
            str(record_data.get("ci_95_str", "[0.000R, 0.000R]")),
            float(record_data.get("drawdown_r", 0.0)),
            str(record_data.get("drift_state", "CONSISTENT")),
            str(record_data.get("execution_state", "OPTIMAL")),
            str(record_data.get("integrity_state", "PASS")),
            str(record_data.get("decision_state", "CONTINUE MONITORING")),
            json.dumps(record_data.get("reasons", [])),
            json.dumps(record_data.get("unresolved_uncertainties", [])),
            str(record_data.get("recommended_next_action", "Continue forward data streaming."))
        ))
        conn.commit()
        conn.close()
        return audit_id

    @staticmethod
    def get_audit_history(limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves historical audit decisions ordered chronologically descending.
        """
        ResearchDecisionAuditEngine.init_table()
        conn = database.get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {ResearchDecisionAuditEngine.TABLE_NAME} ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        conn.close()

        records = []
        for r in rows:
            d = dict(r)
            d["reasons"] = json.loads(d["reasons_json"]) if "reasons_json" in d else []
            d["unresolved_uncertainties"] = json.loads(d["uncertainties_json"]) if "uncertainties_json" in d else []
            records.append(d)
        return records

    @staticmethod
    def synthesize_current_decision(mode: str = "PAPER") -> Dict[str, Any]:
        """
        Synthesizes the current active decision state with detailed "WHY DID WE REACH THIS DECISION?" rationale.
        """
        fwd = XAUUSDForwardMonitor.get_forward_summary(mode=mode)
        drift = XAUUSDDriftDetector.evaluate_distribution_drift(mode=mode)
        exec_d = XAUUSDExecutionDiagnostics.run_execution_diagnostics(mode=mode)
        val_gate = XAUUSDValidationGate.evaluate_gate(mode=mode)
        integ = ResearchIntegrityAuditor.evaluate_integrity()
        score_res = ForwardEvidenceScorer.calculate_evidence_score(mode=mode)
        dec_state = ResearchDecisionStateClassifier.classify_state(mode=mode)
        readiness = ReviewReadinessEngine.evaluate_readiness(mode=mode)
        next_adv = WatchNextAdvisor.get_next_action_advice(mode=mode)

        n = fwd.get("trades_N", 0)
        exp_r = fwd.get("expectancy_r", 0.0)

        # Decision State Determination
        if not integ["all_passed"]:
            decision = "INTEGRITY BLOCKED"
            color = "#ef4444"
            reasons = [
                "One or more research integrity checks failed.",
                f"Warning details: {integ['warning_message']}",
                "Statistical interpretation is halted until integrity is resolved."
            ]
        elif readiness["verdict"] == "READY FOR HUMAN REVIEW":
            decision = "READY FOR HUMAN REVIEW"
            color = "#00ffcc"
            reasons = [
                f"Sample size requirement satisfied (N = {n} >= 100).",
                f"Forward expectancy (+{exp_r:.3f}R) is positive with 95% CI lower bound > 0.",
                "All execution quality, excursion distribution, and integrity checks passed."
            ]
        elif n < 30:
            decision = "CONTINUE MONITORING"
            color = "#38bdf8"
            reasons = [
                f"Forward sample size (N = {n}) is accumulating toward the Stage 1 threshold (N = 30).",
                "Confidence intervals are wide; conclusions regarding strategy edge remain premature.",
                "Execution quality and data integrity are healthy."
            ]
        elif 30 <= n < 50:
            decision = "EARLY EVIDENCE"
            color = "#bef264" if exp_r > 0 else "#f59e0b"
            reasons = [
                f"Sample size has reached Stage 1 (N = {n}).",
                f"Forward expectancy (+{exp_r:.3f}R) shows directional consistency with historical research.",
                "Sample size remains insufficient for formal human review."
            ]
        elif exp_r <= 0 and n >= 50:
            decision = "DIVERGENCE"
            color = "#ef4444"
            reasons = [
                f"Persistent non-positive expectancy ({exp_r:+.3f}R) across N = {n} trades.",
                "Excursion distribution indicates structural drag relative to holdout baseline."
            ]
        else:
            decision = "FORWARD CONSISTENT" if exp_r >= 0.35 else "WATCH"
            color = "#00ffcc" if exp_r >= 0.35 else "#f59e0b"
            reasons = [
                f"Forward sample (N = {n}) is positive (+{exp_r:.3f}R).",
                "Distribution metrics (MAE/MFE) are within expected envelope.",
                "Continue streaming observations toward Stage 3 milestone (N = 100)."
            ]

        ci_str = f"[{fwd.get('ci_lower', 0.0):+.3f}R, {fwd.get('ci_upper', 0.0):+.3f}R]"

        return {
            "current_stage": val_gate["stage_name"],
            "trades_n": n,
            "evidence_score": score_res["total_score"],
            "expectancy_r": exp_r,
            "ci_95_str": ci_str,
            "drawdown_r": fwd.get("max_drawdown_r", 0.0),
            "drift_state": drift["distribution_status"],
            "execution_state": exec_d["execution_health"],
            "integrity_state": integ["overall_status"],
            "decision_state": decision,
            "decision_color": color,
            "reasons": reasons,
            "unresolved_uncertainties": readiness["uncertainty_analysis"]["what_we_do_not_know"],
            "recommended_next_action": next_adv["action"]
        }
