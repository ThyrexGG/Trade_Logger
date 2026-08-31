"""
Phase 28 — XAUUSD Forward Evidence Ledger
Maintains an immutable, append-only repository of forward evidence snapshots.
Allows creating snapshots, viewing historical snapshots, and comparing two snapshots.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import database


class ForwardEvidenceLedger:
    """
    Append-only repository for immutable research evidence snapshots.
    """
    TABLE_NAME = "xauusd_evidence_ledger"

    @staticmethod
    def init_table():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {ForwardEvidenceLedger.TABLE_NAME} (
                snapshot_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                trades_n INTEGER NOT NULL,
                expectancy_r REAL NOT NULL,
                median_r REAL NOT NULL,
                win_rate_pct REAL NOT NULL,
                profit_factor REAL NOT NULL,
                max_drawdown_r REAL NOT NULL,
                recovery_factor REAL NOT NULL,
                ci_90_lower REAL NOT NULL,
                ci_90_upper REAL NOT NULL,
                ci_95_lower REAL NOT NULL,
                ci_95_upper REAL NOT NULL,
                ci_99_lower REAL NOT NULL,
                ci_99_upper REAL NOT NULL,
                hist_expectancy_diff REAL NOT NULL,
                hist_expectancy_ratio REAL NOT NULL,
                baseline_consistency TEXT NOT NULL,
                avg_mae_r REAL NOT NULL,
                avg_mfe_r REAL NOT NULL,
                limit_fill_rate_pct REAL NOT NULL,
                timeout_rate_pct REAL NOT NULL,
                avg_slippage_pips REAL NOT NULL,
                avg_spread_pips REAL NOT NULL,
                paper_shadow_parity TEXT NOT NULL,
                data_integrity_status TEXT NOT NULL,
                contract_hash TEXT NOT NULL,
                governance_stage TEXT NOT NULL,
                evidence_score REAL NOT NULL,
                research_decision_state TEXT NOT NULL,
                next_milestone TEXT NOT NULL,
                raw_payload TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def create_snapshot(data: Dict[str, Any]) -> str:
        """
        Records a new immutable evidence snapshot to the ledger.
        """
        ForwardEvidenceLedger.init_table()
        snapshot_id = f"SNAP_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        ts = datetime.now(timezone.utc).isoformat()

        conn = database.get_connection()
        vals = (
            snapshot_id,
            ts,
            int(data.get("trades_n", 0)),
            float(data.get("expectancy_r", 0.0)),
            float(data.get("median_r", 0.0)),
            float(data.get("win_rate_pct", 0.0)),
            float(data.get("profit_factor", 0.0)),
            float(data.get("max_drawdown_r", 0.0)),
            float(data.get("recovery_factor", 0.0)),
            float(data.get("ci_90_lower", 0.0)),
            float(data.get("ci_90_upper", 0.0)),
            float(data.get("ci_95_lower", 0.0)),
            float(data.get("ci_95_upper", 0.0)),
            float(data.get("ci_99_lower", 0.0)),
            float(data.get("ci_99_upper", 0.0)),
            float(data.get("hist_expectancy_diff", 0.0)),
            float(data.get("hist_expectancy_ratio", 0.0)),
            str(data.get("baseline_consistency", "NOT ENOUGH DATA")),
            float(data.get("avg_mae_r", 0.0)),
            float(data.get("avg_mfe_r", 0.0)),
            float(data.get("limit_fill_rate_pct", 100.0)),
            float(data.get("timeout_rate_pct", 0.0)),
            float(data.get("avg_slippage_pips", 1.0)),
            float(data.get("avg_spread_pips", 2.0)),
            str(data.get("paper_shadow_parity", "100% PARITY")),
            str(data.get("data_integrity_status", "PASS")),
            str(data.get("contract_hash", "LOCKED")),
            str(data.get("governance_stage", "Stage 0")),
            float(data.get("evidence_score", 0.0)),
            str(data.get("research_decision_state", "COLLECTING")),
            str(data.get("next_milestone", "N = 30")),
            json.dumps(data)
        )

        is_sq = isinstance(conn, sqlite3.Connection) or type(conn).__module__.startswith("sqlite3")
        cur = conn.cursor()
        if is_sq:
            cur.execute(f"""
                INSERT OR REPLACE INTO {ForwardEvidenceLedger.TABLE_NAME} (
                    snapshot_id, timestamp, trades_n, expectancy_r, median_r, win_rate_pct,
                    profit_factor, max_drawdown_r, recovery_factor, ci_90_lower, ci_90_upper,
                    ci_95_lower, ci_95_upper, ci_99_lower, ci_99_upper, hist_expectancy_diff,
                    hist_expectancy_ratio, baseline_consistency, avg_mae_r, avg_mfe_r,
                    limit_fill_rate_pct, timeout_rate_pct, avg_slippage_pips, avg_spread_pips,
                    paper_shadow_parity, data_integrity_status, contract_hash, governance_stage,
                    evidence_score, research_decision_state, next_milestone, raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, vals)
        else:
            cur.execute(f"""
                INSERT INTO {ForwardEvidenceLedger.TABLE_NAME} (
                    snapshot_id, timestamp, trades_n, expectancy_r, median_r, win_rate_pct,
                    profit_factor, max_drawdown_r, recovery_factor, ci_90_lower, ci_90_upper,
                    ci_95_lower, ci_95_upper, ci_99_lower, ci_99_upper, hist_expectancy_diff,
                    hist_expectancy_ratio, baseline_consistency, avg_mae_r, avg_mfe_r,
                    limit_fill_rate_pct, timeout_rate_pct, avg_slippage_pips, avg_spread_pips,
                    paper_shadow_parity, data_integrity_status, contract_hash, governance_stage,
                    evidence_score, research_decision_state, next_milestone, raw_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_id) DO NOTHING
            """, vals)

        conn.commit()
        conn.close()
        return snapshot_id

    @staticmethod
    def get_snapshots(limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves historical snapshots ordered chronologically descending.
        """
        ForwardEvidenceLedger.init_table()
        conn = database.get_connection()
        cur = conn.cursor()
        is_sq = isinstance(conn, sqlite3.Connection) or type(conn).__module__.startswith("sqlite3")
        placeholder = "?" if is_sq else "%s"
        cur.execute(f"SELECT * FROM {ForwardEvidenceLedger.TABLE_NAME} ORDER BY timestamp DESC LIMIT {placeholder}", (limit,))
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        conn.close()
        return [dict(zip(cols, r)) for r in rows]

    @staticmethod
    def get_snapshot_by_id(snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single snapshot by its unique ID.
        """
        ForwardEvidenceLedger.init_table()
        conn = database.get_connection()
        cur = conn.cursor()
        is_sq = isinstance(conn, sqlite3.Connection) or type(conn).__module__.startswith("sqlite3")
        placeholder = "?" if is_sq else "%s"
        cur.execute(f"SELECT * FROM {ForwardEvidenceLedger.TABLE_NAME} WHERE snapshot_id = {placeholder}", (snapshot_id,))
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        conn.close()
        return dict(zip(cols, row)) if row else None

    @staticmethod
    def compare_snapshots(id_earlier: str, id_later: str) -> Dict[str, Any]:
        """
        Computes delta comparisons between two snapshots.
        """
        snap1 = ForwardEvidenceLedger.get_snapshot_by_id(id_earlier)
        snap2 = ForwardEvidenceLedger.get_snapshot_by_id(id_later)

        if not snap1 or not snap2:
            return {
                "status": "COMPARISON ERROR",
                "error": "One or both snapshot IDs do not exist in the ledger."
            }

        # Ensure correct chronological ordering
        if snap1["timestamp"] > snap2["timestamp"]:
            snap1, snap2 = snap2, snap1

        return {
            "earlier_snapshot_id": snap1["snapshot_id"],
            "earlier_timestamp": snap1["timestamp"],
            "later_snapshot_id": snap2["snapshot_id"],
            "later_timestamp": snap2["timestamp"],
            "deltas": {
                "new_trades": snap2["trades_n"] - snap1["trades_n"],
                "expectancy_change": round(snap2["expectancy_r"] - snap1["expectancy_r"], 3),
                "win_rate_change_pct": round(snap2["win_rate_pct"] - snap1["win_rate_pct"], 1),
                "profit_factor_change": round(snap2["profit_factor"] - snap1["profit_factor"], 2),
                "drawdown_change_r": round(snap2["max_drawdown_r"] - snap1["max_drawdown_r"], 2),
                "evidence_score_change": round(snap2["evidence_score"] - snap1["evidence_score"], 1),
                "ci_95_width_change": round(
                    (snap2["ci_95_upper"] - snap2["ci_95_lower"]) - (snap1["ci_95_upper"] - snap1["ci_95_lower"]), 3
                )
            },
            "earlier_decision_state": snap1["research_decision_state"],
            "later_decision_state": snap2["research_decision_state"],
            "earlier_stage": snap1["governance_stage"],
            "later_stage": snap2["governance_stage"]
        }
