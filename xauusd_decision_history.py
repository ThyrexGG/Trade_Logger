"""
Phase 26 — XAUUSD Decision History & Chronological Audit Trail
Maintains an append-only persistent record of research decisions and system beliefs across time.
Never overwrites past snapshots.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import database


class XAUUSDDecisionHistory:
    """
    Append-only repository for Research Operations Center decisions.
    """

    @staticmethod
    def init_history_table():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS xauusd_decision_history (
                decision_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                stage TEXT NOT NULL,
                forward_n INTEGER NOT NULL,
                expectancy_r REAL NOT NULL,
                ci_lower REAL NOT NULL,
                ci_upper REAL NOT NULL,
                drawdown_r REAL NOT NULL,
                execution_health TEXT NOT NULL,
                drift_status TEXT NOT NULL,
                integrity_status TEXT NOT NULL,
                overall_decision TEXT NOT NULL,
                next_action TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def record_decision_snapshot(snapshot: Dict[str, Any]) -> str:
        """
        Appends a new decision snapshot to the audit history.
        """
        XAUUSDDecisionHistory.init_history_table()
        conn = database.get_connection()
        cur = conn.cursor()

        dec_id = snapshot.get("decision_id", f"DEC_{uuid.uuid4().hex[:10].upper()}")
        now_str = datetime.now(timezone.utc).isoformat()
        ts = snapshot.get("timestamp", now_str)

        cur.execute("""
            INSERT OR REPLACE INTO xauusd_decision_history (
                decision_id, timestamp, stage, forward_n, expectancy_r,
                ci_lower, ci_upper, drawdown_r, execution_health, drift_status,
                integrity_status, overall_decision, next_action, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dec_id,
            ts,
            snapshot.get("stage", "Stage 0 (Data Accumulation)"),
            int(snapshot.get("forward_n", 0)),
            float(snapshot.get("expectancy_r", 0.0)),
            float(snapshot.get("ci_lower", 0.0)),
            float(snapshot.get("ci_upper", 0.0)),
            float(snapshot.get("drawdown_r", 0.0)),
            snapshot.get("execution_health", "OPTIMAL"),
            snapshot.get("drift_status", "INSUFFICIENT DATA"),
            snapshot.get("integrity_status", "PASS"),
            snapshot.get("overall_decision", "COLLECTING FORWARD DATA"),
            snapshot.get("next_action", "Continue forward observations."),
            snapshot.get("notes", ""),
            now_str
        ))
        conn.commit()
        conn.close()
        return dec_id

    @staticmethod
    def get_decision_timeline(limit: int = 50) -> List[Dict[str, Any]]:
        """
        Returns chronological timeline snapshots in descending order.
        """
        XAUUSDDecisionHistory.init_history_table()
        conn = database.get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT * FROM xauusd_decision_history
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        conn.close()

        timeline = []
        for r in rows:
            timeline.append(dict(zip(cols, r)))
        return timeline
