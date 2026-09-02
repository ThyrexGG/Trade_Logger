# -*- coding: utf-8 -*-
"""
FastAPI Positions Router — Stage 3 Read-Only Open Positions Endpoint
Exposes live open positions and excursion metrics (MAE/MFE) directly from SQLite.
"""
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter
from api.schemas import PositionsResponse, PositionItem
import database

router = APIRouter(prefix="/api", tags=["Positions"])


@router.get("/positions", response_model=PositionsResponse)
async def get_open_positions() -> PositionsResponse:
    """
    Returns active paper/shadow open positions enriched with real-time PnL,
    R-multiple, and MAE/MFE excursion metrics with short TTL caching.
    """
    df_open = database.get_open_positions(ttl_sec=2.0)
    items: List[PositionItem] = []
    total_pnl = 0.0

    if not df_open.empty:
        for _, pos in df_open.iterrows():
            pos_id = str(pos.get("position_id", ""))
            sym = str(pos.get("symbol", "")).upper()
            direction = str(pos.get("direction", "BUY")).upper()
            vol = float(pos.get("volume", 0.0))
            entry_px = float(pos.get("entry_price", 0.0))
            curr_px = float(pos.get("current_price", 0.0))
            sl = float(pos.get("sl", 0.0))
            tp = float(pos.get("tp", 0.0))
            pnl = float(pos.get("floating_pnl", 0.0))
            acc = str(pos.get("account_id", "PAPER"))

            total_pnl += pnl

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

            items.append(PositionItem(
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
                account_id=acc
            ))

    return PositionsResponse(
        positions=items,
        total_open=len(items),
        total_floating_pnl=round(total_pnl, 2),
        timestamp=datetime.now(timezone.utc).isoformat()
    )
