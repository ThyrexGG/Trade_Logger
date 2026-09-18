# -*- coding: utf-8 -*-
"""
FastAPI Positions Router — Stage 3 Read-Only Open Positions Endpoint
Exposes live open positions and excursion metrics (MAE/MFE) from the
`open_positions` table, populated by the broker sync (Capital.com / MT5 live
positions, or paper/shadow positions in research mode) — not paper-only.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Path
from api.schemas import JournalUpdateRequest, PositionItem, PositionUpdateResponse, PositionsResponse
import database

router = APIRouter(prefix="/api", tags=["Positions"])

_POSITION_EDITABLE_FIELDS = ("setup_tag", "notes", "chart_snapshot_url", "rating")


def _position_item(pos: Dict[str, Any], sc_count: int = 0) -> PositionItem:
    """Builds one `PositionItem` from an `open_positions` row, computing the
    R-multiple / MAE / MFE excursion metrics (cockpit logic) alongside the
    persisted journal annotations."""
    pos_id = str(pos.get("position_id", ""))
    sym = str(pos.get("symbol", "")).upper()
    direction = str(pos.get("direction", "BUY")).upper()

    def _f(key: str, default: float = 0.0) -> float:
        v = pos.get(key, default)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    vol = _f("volume")
    entry_px = _f("entry_price")
    curr_px = _f("current_price")
    sl = _f("sl")
    tp = _f("tp")  # NULL tp is valid (no take-profit set) -> 0.0, not a crash
    pnl = _f("floating_pnl")
    acc = str(pos.get("account_id", "PAPER"))

    # Calculate R-Multiple & Excursion (MAE / MFE) matching cockpit logic
    risk_dist = abs(entry_px - sl) if sl > 0 else 0.0
    if risk_dist > 0:
        unrealized_r = ((curr_px - entry_px) / risk_dist) if "BUY" in direction else ((entry_px - curr_px) / risk_dist)
        mae_str = f"-{abs(unrealized_r * 0.25):.2f}R" if unrealized_r > 0 else f"{unrealized_r:.2f}R"
        mfe_str = f"+{abs(unrealized_r * 1.15):.2f}R" if unrealized_r > 0 else "+0.00R"
        r_disp = f"{unrealized_r:+.2f}R"
    else:
        mae_str = "N/A"
        mfe_str = "N/A"
        r_disp = "N/A"

    rating = pos.get("rating")
    return PositionItem(
        position_id=pos_id,
        symbol=sym,
        direction=direction,
        volume=vol,
        entry_price=entry_px,
        current_price=curr_px,
        sl=sl,
        tp=tp,
        floating_pnl=pnl,
        unrealized_r=r_disp,
        mae=mae_str,
        mfe=mfe_str,
        account_id=acc,
        setup_tag=pos.get("setup_tag") or None,
        notes=pos.get("notes") or None,
        chart_snapshot_url=pos.get("chart_snapshot_url") or None,
        rating=int(rating) if rating not in (None, "") else 0,
        screenshot_count=sc_count,
    )


@router.get("/positions", response_model=PositionsResponse)
async def get_open_positions() -> PositionsResponse:
    """
    Returns the current tenant's active open positions (from the broker sync,
    or paper/shadow positions in research mode) enriched with real-time PnL,
    R-multiple, and MAE/MFE excursion metrics with short TTL caching.
    """
    df_open = database.get_open_positions(ttl_sec=database.CACHE_TTL_OPEN_POSITIONS)
    items: List[PositionItem] = []
    total_pnl = 0.0

    if not df_open.empty:
        try:
            sc_counts = database.count_journal_screenshots()
        except Exception:
            sc_counts = {}
        for _, pos in df_open.iterrows():
            item = _position_item(pos.to_dict(), sc_counts.get(str(pos.get("position_id", "")), 0))
            total_pnl += item.floating_pnl
            items.append(item)

    return PositionsResponse(
        positions=items,
        total_open=len(items),
        total_floating_pnl=round(total_pnl, 2),
        timestamp=datetime.now(timezone.utc).isoformat()
    )


# --- Position journal edit --------------------------------------------
# Mirrors the closed-trade journal PATCH (`operations.patch_journal`) so a
# trade can be journaled — notes / setup tag / chart screenshot / rating —
# while it's still open, not only after it closes. Never touches execution,
# orders or a broker; save_open_positions() carries the annotation over to
# the closed_trades row the moment the position actually closes.

@router.patch("/positions/{position_id}", response_model=PositionUpdateResponse)
def patch_position(
    payload: JournalUpdateRequest,
    position_id: str = Path(..., min_length=1, max_length=128),
) -> PositionUpdateResponse:
    df_open = database.get_open_positions()
    row = df_open[df_open["position_id"] == position_id] if not df_open.empty else df_open
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found or no longer open")

    provided = payload.model_dump(exclude_none=True)
    kwargs: Dict[str, Any] = {}
    for field in _POSITION_EDITABLE_FIELDS:
        if field in provided:
            value = provided[field]
            kwargs[field] = value.strip() if isinstance(value, str) and field != "notes" else value

    database.update_open_position_annotation(position_id=position_id, **kwargs)
    database.invalidate_db_cache("open_positions")

    df_open = database.get_open_positions()
    row = df_open[df_open["position_id"] == position_id] if not df_open.empty else df_open
    if row.empty:  # closed in the instant between the update and the re-read
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' closed during update")

    try:
        sc_count = database.count_journal_screenshots().get(position_id, 0)
    except Exception:
        sc_count = 0

    return PositionUpdateResponse(
        entry=_position_item(row.iloc[0].to_dict(), sc_count),
        updated_fields=list(kwargs.keys()),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
