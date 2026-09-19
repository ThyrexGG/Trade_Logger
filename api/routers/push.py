"""Push notification endpoints: phone-device registration, a test push, and the
trade-event feed the desktop app polls.

Everything here is scoped to the signed-in user by the auth gate's tenant binding.
Nothing here can place or change a trade — it only reports events the broker
sync already recorded (see ``trade_notify``).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

import database
import tenant
import trade_notify

router = APIRouter(prefix="/api/push", tags=["Push"])

_TOKEN_PREFIXES = ("ExponentPushToken[", "ExpoPushToken[")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=10, max_length=300)
    platform: Optional[str] = Field(default=None, max_length=20)
    device_name: Optional[str] = Field(default=None, max_length=120)

    @field_validator("token")
    @classmethod
    def _looks_like_expo_token(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(_TOKEN_PREFIXES) or not v.endswith("]"):
            raise ValueError("token must be an Expo push token (ExponentPushToken[...])")
        return v


class UnregisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=10, max_length=300)


@router.post("/register")
def register_device(body: RegisterRequest) -> Dict[str, Any]:
    """Save this phone's push token for the signed-in user (idempotent)."""
    database.upsert_push_device(body.token, platform=body.platform, device_name=body.device_name)
    return {"ok": True, "devices": len(database.list_push_devices()), "timestamp": _now()}


@router.post("/unregister")
def unregister_device(body: UnregisterRequest) -> Dict[str, Any]:
    """Stop pushing to this phone (used on logout / when the user turns alerts off)."""
    removed = database.delete_push_device(body.token)
    return {"ok": True, "removed": removed, "devices": len(database.list_push_devices()), "timestamp": _now()}


@router.post("/test")
def send_test_push() -> Dict[str, Any]:
    """Send a test notification to the caller's registered phones and report Expo's answer,
    so a setup problem (missing credentials, wrong token) is visible instead of silent."""
    devices = database.list_push_devices()
    result = trade_notify.send_test(devices, user_id=tenant.current_user_id())
    return {**result, "devices": len(devices), "push_enabled": trade_notify.push_enabled(), "timestamp": _now()}


@router.get("/events")
def trade_events(
    after_id: Optional[int] = Query(default=None, ge=0, description="return events newer than this id"),
    limit: int = Query(default=50, ge=1, le=200),
) -> Dict[str, Any]:
    """Recent trade open/close events for the desktop app to turn into native notifications.

    With no ``after_id`` only ``latest_id`` is returned (a baseline, so a fresh
    desktop install does not replay history); pass it back as ``after_id`` on the next poll."""
    latest = database.latest_trade_event_id()
    events: List[Dict[str, Any]] = []
    if after_id is not None:
        events = database.list_trade_events(after_id=after_id, limit=limit)
    return {"events": events, "latest_id": latest, "user_id": tenant.current_user_id(), "timestamp": _now()}
