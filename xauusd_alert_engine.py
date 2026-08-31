"""
Phase 26 — XAUUSD Forward Validation Event-Based Alert Engine
Manages persistent monitor events in SQLite, severity classification (INFORMATION, WARNING, CRITICAL),
explainable alert payloads (5 questions), and non-destructive alert acknowledgement.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import database


class XAUUSDAlertEngine:
    """
    Manages persistent logging, query, and acknowledgement of forward validation monitoring events.
    """

    @staticmethod
    def init_events_table():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS xauusd_monitor_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                metric TEXT NOT NULL,
                observed_value REAL,
                baseline_value REAL,
                threshold REAL,
                explanation TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                source_observation_id TEXT,
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def log_event(event_data: Dict[str, Any]) -> str:
        """
        Logs a new monitoring event to the database.
        """
        XAUUSDAlertEngine.init_events_table()
        conn = database.get_connection()
        cur = conn.cursor()

        event_id = event_data.get("event_id", f"EVT_{uuid.uuid4().hex[:10].upper()}")
        now_str = datetime.now(timezone.utc).isoformat()
        ts = event_data.get("timestamp", now_str)
        severity = event_data.get("severity", "INFORMATION").upper()
        
        vals = (
            event_id,
            ts,
            event_data.get("event_type", "GENERAL_OBSERVATION"),
            severity,
            event_data.get("metric", "N/A"),
            float(event_data.get("observed_value")) if event_data.get("observed_value") is not None else None,
            float(event_data.get("baseline_value")) if event_data.get("baseline_value") is not None else None,
            float(event_data.get("threshold")) if event_data.get("threshold") is not None else None,
            event_data.get("explanation", "Forward observation event recorded."),
            event_data.get("recommended_action", "Continue standard forward observation stream."),
            event_data.get("source_observation_id"),
            1 if event_data.get("acknowledged") else 0,
            now_str
        )

        is_sq = isinstance(conn, sqlite3.Connection) or type(conn).__module__.startswith("sqlite3")
        if is_sq:
            cur.execute("""
                INSERT OR REPLACE INTO xauusd_monitor_events (
                    event_id, timestamp, event_type, severity, metric, observed_value,
                    baseline_value, threshold, explanation, recommended_action,
                    source_observation_id, acknowledged, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, vals)
        else:
            cur.execute("""
                INSERT INTO xauusd_monitor_events (
                    event_id, timestamp, event_type, severity, metric, observed_value,
                    baseline_value, threshold, explanation, recommended_action,
                    source_observation_id, acknowledged, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    timestamp = EXCLUDED.timestamp,
                    event_type = EXCLUDED.event_type,
                    severity = EXCLUDED.severity,
                    metric = EXCLUDED.metric,
                    observed_value = EXCLUDED.observed_value,
                    baseline_value = EXCLUDED.baseline_value,
                    threshold = EXCLUDED.threshold,
                    explanation = EXCLUDED.explanation,
                    recommended_action = EXCLUDED.recommended_action,
                    source_observation_id = EXCLUDED.source_observation_id,
                    acknowledged = EXCLUDED.acknowledged,
                    created_at = EXCLUDED.created_at
            """, vals)

        conn.commit()
        conn.close()
        return event_id

    @staticmethod
    def get_events(
        severity_filter: str = "ALL",
        acknowledged_filter: str = "ALL",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieves events with optional severity and acknowledgement filtering.
        """
        XAUUSDAlertEngine.init_events_table()
        conn = database.get_connection()
        cur = conn.cursor()

        is_sq = isinstance(conn, sqlite3.Connection) or type(conn).__module__.startswith("sqlite3")
        placeholder = "?" if is_sq else "%s"

        query = "SELECT * FROM xauusd_monitor_events WHERE 1=1"
        params: List[Any] = []

        if severity_filter.upper() != "ALL":
            query += f" AND severity = {placeholder}"
            params.append(severity_filter.upper())

        if acknowledged_filter.upper() == "ACKNOWLEDGED":
            query += " AND acknowledged = 1"
        elif acknowledged_filter.upper() == "UNACKNOWLEDGED":
            query += " AND acknowledged = 0"

        query += f" ORDER BY timestamp DESC LIMIT {placeholder}"
        params.append(limit)

        cur.execute(query, tuple(params))
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        conn.close()

        events = []
        for r in rows:
            events.append(dict(zip(cols, r)))
        return events

    @staticmethod
    def acknowledge_alert(event_id: str) -> bool:
        """
        Marks an alert as acknowledged without mutating event details or deleting historical logs.
        """
        XAUUSDAlertEngine.init_events_table()
        conn = database.get_connection()
        cur = conn.cursor()
        is_sq = isinstance(conn, sqlite3.Connection) or type(conn).__module__.startswith("sqlite3")
        placeholder = "?" if is_sq else "%s"
        cur.execute(f"UPDATE xauusd_monitor_events SET acknowledged = 1 WHERE event_id = {placeholder}", (event_id,))
        modified = cur.rowcount > 0
        conn.commit()
        conn.close()
        return modified

    @staticmethod
    def explain_alert(event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds the canonical 5-part explainable alert breakdown.
        1. WHAT HAPPENED?
        2. HOW BAD IS IT?
        3. WHY DOES IT MATTER?
        4. WHAT CAUSED THE ALERT?
        5. WHAT SHOULD I DO?
        """
        severity = event.get("severity", "INFORMATION").upper()
        metric = event.get("metric", "Unknown Metric")
        obs_val = event.get("observed_value")
        base_val = event.get("baseline_value")
        thresh_val = event.get("threshold")

        # Severity interpretation
        severity_map = {
            "INFORMATION": "NORMAL — Standard forward research progress.",
            "WARNING": "WATCH / WARNING — Potential drift or friction detected; monitor closely.",
            "CRITICAL": "CRITICAL — Governance or integrity threshold breached; human investigation required."
        }
        how_bad = severity_map.get(severity, "NORMAL")

        # Why it matters
        if "EXPECTANCY" in metric.upper():
            why_matter = "Expectancy reflects the average return per dollar of initial risk. Changes here influence strategy viability."
        elif "DRAWDOWN" in metric.upper():
            why_matter = "Drawdown measures equity contraction from peak. Tracking vs historical stress (7.15R) ensures capital safety."
        elif "TIMEOUT" in metric.upper() or "FILL" in metric.upper():
            why_matter = "Execution quality reveals microstructure friction (spread, slippage, speed) distinct from strategy edge."
        elif "PARITY" in metric.upper():
            why_matter = "Paper and Shadow execution must match 100% to guarantee deterministic trade modeling."
        else:
            why_matter = "Ensures forward observations adhere to the frozen strategy contract and research governance rules."

        # What caused
        obs_str = f"{obs_val:.2f}" if obs_val is not None else "N/A"
        base_str = f"{base_val:.2f}" if base_val is not None else "N/A"
        thresh_str = f"{thresh_val:.2f}" if thresh_val is not None else "N/A"
        what_caused = f"Observed Metric: {metric} = {obs_str} (Baseline: {base_str}, Threshold: {thresh_str})"

        return {
            "event_id": event.get("event_id"),
            "what_happened": event.get("explanation", "Event recorded."),
            "how_bad_is_it": how_bad,
            "why_does_it_matter": why_matter,
            "what_caused_the_alert": what_caused,
            "what_should_i_do": event.get("recommended_action", "Maintain forward observation streaming."),
            "severity": severity,
            "acknowledged": bool(event.get("acknowledged"))
        }
