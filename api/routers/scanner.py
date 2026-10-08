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
from api import killzone_alerts
from api.schemas import KillzoneBoardResponse, KillzoneScanResponse, KillzoneWatchConfig

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


@router.get("/killzone/board", response_model=KillzoneBoardResponse)
def killzone_board(
    symbols: str = Query(..., min_length=1, description="Comma-separated symbols, e.g. EURUSD,GBPUSD,NAS100"),
    ltf: str = Query(default="15m"),
    htf: str = Query(default="1h"),
) -> KillzoneBoardResponse:
    """`scan()` across several symbols at once (the watchlist "board" view) —
    same rules and same disclaimer as the single-symbol endpoint, just batched
    so the page doesn't need one request per symbol."""
    now_iso = datetime.now(timezone.utc).isoformat()
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    if not syms:
        return KillzoneBoardResponse(ok=False, results=[], timestamp=now_iso)
    try:
        raw = killzone_scanner.scan_many(syms, ltf=ltf, htf=htf)
    except Exception as exc:
        return KillzoneBoardResponse(ok=False, results=[], timestamp=now_iso)
    results = []
    for r in raw:
        try:
            results.append(KillzoneScanResponse(**r))
        except Exception as exc:
            results.append(KillzoneScanResponse(
                ok=False, symbol=str(r.get("symbol", "")).upper(),
                error=f"{type(exc).__name__}: {exc}", timestamp=now_iso,
            ))
    return KillzoneBoardResponse(ok=True, results=results, timestamp=now_iso)


@router.get("/killzone/watch-config", response_model=KillzoneWatchConfig)
def get_killzone_watch_config() -> KillzoneWatchConfig:
    """The current tenant's saved Killzone Scanner push-alert config (empty
    and disabled until they've saved one)."""
    return KillzoneWatchConfig(**killzone_alerts.get_config())


@router.post("/killzone/watch-config", response_model=KillzoneWatchConfig)
def set_killzone_watch_config(body: KillzoneWatchConfig) -> KillzoneWatchConfig:
    """Save which symbols to watch and the confluence bar a candidate must
    clear before it pushes a notification. See api/killzone_alerts.py —
    checked from the same background loop that already evaluates price
    alerts / the weekly summary, so this adds no new
    always-on cost."""
    saved = killzone_alerts.set_config(body.symbols, body.min_confluence, body.enabled)
    return KillzoneWatchConfig(**saved)
