# -*- coding: utf-8 -*-
"""
FastAPI Price Alerts Router (Stage 13)

Migrates the legacy Streamlit "PRICE ALERTS" workflow (`app.py` -> the
`database.*_price_alert` helpers + the `price_alerts` table) to an HTTP surface
for the React SPA.

**Monitoring only.** Nothing here submits, modifies, cancels or transmits an
order, enables automation, or touches `execution_pipeline` / a broker adapter /
the risk gateway. Price-alert *evaluation* (crossing detection + notification
dispatch) stays exactly where it already lives — the standalone `auto_sync.py`
daemon calling `database.get_active_price_alerts()` + `alerts.notify_price_alert`
+ `database.mark_price_alert_triggered`. This router is a thin CRUD adapter over
the same authoritative table; it does not evaluate or notify.

Server-maintained fields (`id`, `status`, `created_at`, `triggered_at`) are
never client-controlled.
"""
import math
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Path

import database
from symbol_mapping import CANONICAL_SYMBOLS, normalize_symbol
from api.schemas import (
    AlertItem,
    AlertsResponse,
    AlertCreateRequest,
    AlertCreateResponse,
    AlertDeleteResponse,
)

router = APIRouter(prefix="/api/alerts", tags=["Price Alerts"])

_SUPPORTED_SYMBOLS = sorted(CANONICAL_SYMBOLS.keys())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _s(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    text = str(value)
    return text if text and text.lower() != "nan" else None


def _placeholder(conn: Any) -> str:
    is_sq = isinstance(conn, sqlite3.Connection) or type(conn).__module__.startswith("sqlite3")
    return "?" if is_sq else "%s"


def _alert_item(r: Dict[str, Any]) -> AlertItem:
    cond = str(r.get("condition") or "").upper()
    return AlertItem(
        id=int(r["id"]),
        symbol=str(r.get("symbol") or "").upper(),
        target_price=float(r.get("target_price") or 0.0),
        condition="BELOW" if cond == "BELOW" else "ABOVE",
        status=str(r.get("status") or "ACTIVE").upper(),
        account_id=str(r.get("account_id") or "ALL"),
        notes=_s(r.get("notes")),
        created_at=_s(r.get("created_at")),
        triggered_at=_s(r.get("triggered_at")),
    )


def _fetch_alert_row(alert_id: int) -> Optional[Dict[str, Any]]:
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM price_alerts WHERE id = {_placeholder(conn)}",
            (int(alert_id),),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


@router.get("", response_model=AlertsResponse)
def list_alerts() -> AlertsResponse:
    """Authoritative list of price alerts (`price_alerts`, newest first, 50)."""
    df = database.get_all_price_alerts(limit=50, ttl_sec=8.0)
    items: List[AlertItem] = []
    if isinstance(df, pd.DataFrame) and not df.empty:
        for _, r in df.iterrows():
            items.append(_alert_item(r.to_dict()))

    active = sum(1 for a in items if a.status == "ACTIVE")
    triggered = sum(1 for a in items if a.status == "TRIGGERED")
    return AlertsResponse(
        alerts=items,
        total=len(items),
        active=active,
        triggered=triggered,
        supported_symbols=_SUPPORTED_SYMBOLS,
        source="price_alerts",
        timestamp=_now(),
    )


@router.post("", response_model=AlertCreateResponse, status_code=201)
def create_alert(payload: AlertCreateRequest) -> AlertCreateResponse:
    """
    Create one price alert. `symbol` is validated / normalized against the
    project's canonical symbol registry (`symbol_mapping.normalize_symbol`) —
    an unrecognized symbol is rejected 422. `condition` is `ABOVE` (fires when
    price >= target) or `BELOW` (price <= target). Persistence is delegated to
    the canonical `database.create_price_alert`; `status` (`ACTIVE`),
    `created_at` and `id` are set server-side.
    """
    canon = normalize_symbol(payload.symbol)
    if not canon:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported symbol '{payload.symbol}'. Supported: {', '.join(_SUPPORTED_SYMBOLS)}",
        )

    notes = (payload.notes or "").strip()
    new_id = database.create_price_alert(
        symbol=canon,
        target_price=float(payload.target_price),
        condition=payload.condition,
        notes=notes,
    )

    row = _fetch_alert_row(int(new_id)) if new_id is not None else None
    if row is None:  # pragma: no cover - defensive; the row was just written
        raise HTTPException(status_code=500, detail="Alert was created but could not be read back")

    return AlertCreateResponse(alert=_alert_item(row), timestamp=_now())


@router.delete("/{alert_id}", response_model=AlertDeleteResponse)
def remove_alert(alert_id: int = Path(..., ge=1)) -> AlertDeleteResponse:
    """Delete one existing alert. Unknown id -> 404. Uses `database.delete_price_alert`."""
    if _fetch_alert_row(alert_id) is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    database.delete_price_alert(alert_id)
    return AlertDeleteResponse(deleted=True, alert_id=int(alert_id), timestamp=_now())
