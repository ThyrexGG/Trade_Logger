# -*- coding: utf-8 -*-
"""
FastAPI router for the killzone liquidity-sweep + MSS scanner (W15).

Thin adapter over `killzone_scanner.scan()` — no logic here, no execution
path, no broker/order import. GET-only, read-only, pattern-flagging output
that is explicitly never presented as a signal (see the response's own
`disclaimer` field and `killzone_scanner.py`'s module docstring).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Query

import killzone_scanner
from api.schemas import KillzoneScanResponse

router = APIRouter(prefix="/api/scanner", tags=["Scanner"])


@router.get("/killzone", response_model=KillzoneScanResponse)
def killzone_scan(
    symbol: str = Query(default="USDJPY", min_length=2, max_length=12),
    ltf: str = Query(default="15m", description="Lower timeframe for sweep/MSS detection: 1m, 5m, 15m, 1h"),
    htf: str = Query(default="1h", description="Higher timeframe for structural bias: 1h (see killzone_scanner.scan for why not 1d/4h)"),
) -> KillzoneScanResponse:
    """Candidate liquidity-sweep + market-structure-shift events on `symbol`,
    tagged with whether each fell in a named ICT killzone and whether its
    direction agrees with the higher-timeframe structural bias. Never a
    recommendation — every field is a plain, disclosed computation a human
    still has to judge."""
    try:
        result = killzone_scanner.scan(symbol=symbol.strip(), ltf=ltf, htf=htf)
    except Exception as exc:
        return KillzoneScanResponse(
            ok=False, symbol=symbol.strip().upper(),
            error=f"Scanner failed: {type(exc).__name__}: {exc}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    return KillzoneScanResponse(**result)
