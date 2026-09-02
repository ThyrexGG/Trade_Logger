# -*- coding: utf-8 -*-
"""
FastAPI Operations Router — Read-Only Journal / Audit / System (Stage 11)

Thin adapter over authoritative SQLite state:
  - Journal  -> `database.get_closed_trades()` (the `closed_trades` table)
  - Audit    -> the `execution_orders` table (operational execution trail)
               + `ResearchDecisionAuditEngine` ledger record count
  - System   -> `/api/health` values + `system_health.evaluate_system_health`

Every value is produced by the authoritative system and merely serialized.
GET-only: nothing here mutates operational state, submits orders or touches a
broker. `sqlite3` placeholders are handled for both SQLite and Postgres.
"""
import math
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, Query

import database
from api.schemas import (
    JournalResponse,
    JournalTradeItem,
    AuditResponse,
    AuditOrderItem,
    OperationsSystemResponse,
    SystemSafetyGate,
    ReconciliationHealth,
)

router = APIRouter(prefix="/api/operations", tags=["Operations"])


def _f(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _s(value: Any):
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    text = str(value)
    return text if text and text.lower() != "nan" else None


def _num_or_none(value: Any):
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


# --- Journal --------------------------------------------------------------

@router.get("/journal", response_model=JournalResponse)
def get_journal() -> JournalResponse:
    """
    Read-only trade journal — the authoritative `closed_trades` table
    (execution facts + subjective setup_tag / notes / rating). No write path
    is exposed by the current backend, so this surface is read-only.
    """
    df = database.get_closed_trades(ttl_sec=5.0)
    entries: List[JournalTradeItem] = []
    wins = losses = 0
    total_net = 0.0
    accounts: set[str] = set()

    if isinstance(df, pd.DataFrame) and not df.empty:
        for _, r in df.iterrows():
            net = _f(r.get("net_profit"))
            total_net += net
            if net > 0:
                wins += 1
            elif net < 0:
                losses += 1
            acc = _s(r.get("account_id")) or "UNKNOWN"
            accounts.add(acc)
            rating_raw = r.get("rating")
            try:
                rating = int(rating_raw) if rating_raw is not None and str(rating_raw) != "nan" else None
            except (TypeError, ValueError):
                rating = None
            entries.append(JournalTradeItem(
                trade_id=_s(r.get("trade_id")) or "",
                account_id=acc,
                symbol=(_s(r.get("symbol")) or "").upper(),
                direction=(_s(r.get("direction")) or "").upper(),
                volume=_f(r.get("volume")),
                entry_price=_f(r.get("entry_price")),
                exit_price=_f(r.get("exit_price")),
                commission=_f(r.get("commission")),
                swap=_f(r.get("swap")),
                gross_profit=_f(r.get("gross_profit")),
                net_profit=net,
                entry_time=_s(r.get("entry_time")) or "",
                exit_time=_s(r.get("exit_time")) or "",
                duration_minutes=_f(r.get("duration_minutes")),
                setup_tag=_s(r.get("setup_tag")),
                notes=_s(r.get("notes")),
                rating=rating,
                chart_snapshot_url=_s(r.get("chart_snapshot_url")),
            ))

    return JournalResponse(
        entries=entries,
        total_trades=len(entries),
        wins=wins,
        losses=losses,
        total_net_profit=round(total_net, 2),
        accounts=sorted(accounts),
        source="closed_trades",
        writable=False,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# --- Audit ---------------------------------------------------------------

_AUDIT_COLUMNS = [
    "execution_id", "signal_id", "symbol", "side", "requested_quantity",
    "requested_entry", "stop_loss", "take_profit", "broker", "mode", "state",
    "reconciliation_status", "created_at", "submitted_at", "resolved_at",
    "filled_at", "execution_latency_ms", "reject_reason", "last_error",
]


@router.get("/audit", response_model=AuditResponse)
def get_audit(limit: int = Query(default=200, ge=1, le=1000)) -> AuditResponse:
    """
    Read-only operational execution audit trail — the `execution_orders` table.
    Every row is an immutable historical record of an execution attempt with its
    authoritative mode / state / reject reason. `signal_payload` is not exposed.
    """
    conn = database.get_connection()
    is_sq = isinstance(conn, sqlite3.Connection) or type(conn).__module__.startswith("sqlite3")
    ph = "?" if is_sq else "%s"
    cur = conn.cursor()

    events: List[AuditOrderItem] = []
    total_records = 0
    state_counts: Dict[str, int] = {}
    mode_counts: Dict[str, int] = {}
    latest_at = None

    try:
        cur.execute("SELECT COUNT(*) FROM execution_orders")
        total_records = int(cur.fetchone()[0])

        cur.execute("SELECT state, COUNT(*) FROM execution_orders GROUP BY state")
        state_counts = {str(k or "UNKNOWN"): int(v) for k, v in cur.fetchall()}
        cur.execute("SELECT mode, COUNT(*) FROM execution_orders GROUP BY mode")
        mode_counts = {str(k or "UNKNOWN"): int(v) for k, v in cur.fetchall()}

        cur.execute(
            f"SELECT {', '.join(_AUDIT_COLUMNS)} FROM execution_orders "
            f"ORDER BY created_at DESC LIMIT {ph}",
            (limit,),
        )
        cols = [c[0] for c in cur.description]
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            events.append(AuditOrderItem(
                execution_id=_s(d.get("execution_id")) or "",
                signal_id=_s(d.get("signal_id")),
                symbol=_s(d.get("symbol")),
                side=_s(d.get("side")),
                requested_quantity=_num_or_none(d.get("requested_quantity")),
                requested_entry=_num_or_none(d.get("requested_entry")),
                stop_loss=_num_or_none(d.get("stop_loss")),
                take_profit=_num_or_none(d.get("take_profit")),
                broker=_s(d.get("broker")),
                mode=_s(d.get("mode")),
                state=_s(d.get("state")),
                reconciliation_status=_s(d.get("reconciliation_status")),
                created_at=_s(d.get("created_at")),
                submitted_at=_s(d.get("submitted_at")),
                resolved_at=_s(d.get("resolved_at")),
                filled_at=_s(d.get("filled_at")),
                execution_latency_ms=_num_or_none(d.get("execution_latency_ms")),
                reject_reason=_s(d.get("reject_reason")),
                last_error=_s(d.get("last_error")),
            ))
        if events:
            latest_at = events[0].created_at
    finally:
        conn.close()

    decision_ledger = _decision_ledger_count()

    return AuditResponse(
        events=events,
        total_returned=len(events),
        total_records=total_records,
        state_counts=state_counts,
        mode_counts=mode_counts,
        decision_ledger_records=decision_ledger,
        latest_event_at=latest_at,
        source="execution_orders",
        read_only=True,
        live_broker_transmission="BLOCKED",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _decision_ledger_count() -> int:
    try:
        from xauusd_research_decision_audit import ResearchDecisionAuditEngine
        return len(ResearchDecisionAuditEngine.get_audit_history(limit=1000))
    except Exception:
        return 0


# --- System ------------------------------------------------------------

@router.get("/system", response_model=OperationsSystemResponse)
def get_system() -> OperationsSystemResponse:
    """
    Operational system health: the authoritative `/api/health` safety values
    plus the deterministic `system_health.evaluate_system_health` PAPER-mode
    diagnostic gate (kill switch, DB connectivity, reconciliation worker,
    unresolved orders). No live automation is enabled and none can be from here.
    """
    gate_raw: Dict[str, Any] = {}
    try:
        import system_health
        gate_raw = system_health.evaluate_system_health(broker="MT5", mode="PAPER") or {}
    except Exception as exc:  # pragma: no cover - defensive
        gate_raw = {
            "overall_status": "UNKNOWN",
            "automation_allowed": False,
            "reasons": [f"system health evaluation failed: {type(exc).__name__}"],
            "checks": {},
        }

    checks = gate_raw.get("checks", {}) or {}
    recon = checks.get("reconciliation") or {}

    gate = SystemSafetyGate(
        overall_status=str(gate_raw.get("overall_status", "UNKNOWN")),
        automation_allowed=bool(gate_raw.get("automation_allowed", False)),
        reasons=[str(r) for r in (gate_raw.get("reasons") or [])],
        kill_switch_engaged=checks.get("kill_switch_engaged"),
        emergency_halt_engaged=checks.get("emergency_halt_engaged"),
        database_connected=checks.get("database_connected"),
        unresolved_unknown_orders_count=checks.get("unresolved_unknown_orders_count"),
        reconciliation=ReconciliationHealth(
            status=_s(recon.get("status")),
            healthy=recon.get("healthy"),
            reason=_s(recon.get("reason")),
            last_heartbeat=_s(recon.get("last_heartbeat")),
            last_success=_s(recon.get("last_success")),
            consecutive_failures=recon.get("consecutive_failures"),
            iterations_count=recon.get("iterations_count"),
        ) if recon else None,
    )

    try:
        df_open = database.get_open_positions(ttl_sec=2.0)
        open_count = 0 if df_open is None or df_open.empty else int(len(df_open))
    except Exception:
        open_count = 0

    return OperationsSystemResponse(
        api_status="HEALTHY",
        app_name="TradeLogger Fast Terminal API",
        version="2.0.0",
        live_automation_enabled=False,
        live_broker_transmission="BLOCKED",
        safety_gate=gate,
        open_positions=open_count,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
