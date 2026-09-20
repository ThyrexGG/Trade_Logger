# -*- coding: utf-8 -*-
"""
Loss-limit alerts (see api/loss_limits.py): view how each account stands against its daily-loss and
drawdown limits, and set or clear those limits. Notification only — nothing here closes, blocks or
places a trade.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from api import loss_limits

router = APIRouter(prefix="/api/loss-limits", tags=["Loss limits"])

_NOTE = ("Uses closed trades only — an open position's floating loss is not counted. "
         "'Today' is the server's calendar day (UTC).")


class LimitsIn(BaseModel):
    model_config = {"extra": "forbid"}
    daily_loss: Optional[float] = Field(default=None, ge=0, le=1e9, description="money; empty/0 = no daily limit")
    drawdown_pct: Optional[float] = Field(default=None, ge=0, lt=100, description="% below peak; empty/0 = no drawdown limit")


def _public(status: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in status.items() if not k.startswith("_")}


def _envelope(accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"accounts": accounts, "warn_at_pct": int(loss_limits.WARN_RATIO * 100), "note": _NOTE,
            "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("")
def list_limits() -> Dict[str, Any]:
    limits = loss_limits.get_limits()
    return _envelope([_public(loss_limits.compute_status(a, limits.get(a, {}))) for a in loss_limits.account_ids()])


@router.put("/{account}")
def save_limits(body: LimitsIn, account: str = Path(..., min_length=1, max_length=128)) -> Dict[str, Any]:
    account = account.strip()
    try:
        loss_limits.set_limits(account, body.daily_loss, body.drawdown_pct)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:  # make sure the background watcher is running, and tell the user at once if a limit is already crossed
        from api import sync_service
        sync_service.watch_alerts()
        loss_limits.check(lambda _m: None)
    except Exception:  # noqa: BLE001 - saving must not fail because the watcher could not start
        pass
    return _public(loss_limits.compute_status(account))


@router.delete("/{account}")
def clear_limits(account: str = Path(..., min_length=1, max_length=128)) -> Dict[str, Any]:
    loss_limits.set_limits(account.strip(), None, None)
    return {"account_id": account.strip(), "cleared": True}
