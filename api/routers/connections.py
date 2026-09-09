# -*- coding: utf-8 -*-
"""
FastAPI Broker Connections Router (platform plan W8.5).

Each user manages their own Capital.com connection here. Credentials are
encrypted at rest (``api/broker_credentials``); this router never returns a
secret — only metadata and the last sync outcome.

Data ingestion only. "Test" logs in and reads the account; "Sync now" runs one
Capital.com history/balance/position pull for that connection. No order path,
no automation — execution stays permanently BLOCKED.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import tenant
from api import broker_credentials as bc

router = APIRouter(prefix="/api/connections", tags=["Broker Connections"])

_SAFETY = {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}


class SecretIn(BaseModel):
    model_config = {"extra": "forbid"}
    api_key: str = Field(default="", max_length=512)
    email: str = Field(default="", max_length=256)
    password: str = Field(default="", max_length=512)


class ConnectionCreate(BaseModel):
    model_config = {"extra": "forbid"}
    label: str = Field(default="", max_length=120)
    account_id: str = Field(default="", max_length=128)
    is_demo: bool = False
    secret: SecretIn


class ConnectionUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    label: Optional[str] = Field(default=None, max_length=120)
    account_id: Optional[str] = Field(default=None, max_length=128)
    is_demo: Optional[bool] = None
    is_active: Optional[bool] = None
    secret: Optional[SecretIn] = None


def _uid(request: Request) -> str:
    return tenant.current_user_id()


def _envelope(extra: Dict[str, Any]) -> Dict[str, Any]:
    return {**extra, "encryption_configured": bc.enc_enabled(), "safety_barrier": _SAFETY}


@router.get("")
def list_connections(request: Request) -> Dict[str, Any]:
    if not bc.enc_enabled():
        return _envelope({"connections": [], "detail": "Broker connections are not enabled on this server."})
    return _envelope({"connections": bc.list_connections(_uid(request))})


@router.post("", status_code=201)
def create_connection(body: ConnectionCreate, request: Request) -> Dict[str, Any]:
    try:
        meta = bc.create_connection(
            secret=body.secret.model_dump(),
            account_id=body.account_id,
            is_demo=body.is_demo,
            label=body.label,
            user_id=_uid(request),
        )
    except bc.CredentialError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _envelope({"connection": meta})


@router.patch("/{conn_id}")
def update_connection(conn_id: str, body: ConnectionUpdate, request: Request) -> Dict[str, Any]:
    try:
        meta = bc.update_connection(
            conn_id,
            secret=body.secret.model_dump() if body.secret else None,
            account_id=body.account_id,
            is_demo=body.is_demo,
            label=body.label,
            is_active=body.is_active,
            user_id=_uid(request),
        )
    except bc.CredentialError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _envelope({"connection": meta})


@router.delete("/{conn_id}")
def delete_connection(conn_id: str, request: Request) -> Dict[str, Any]:
    ok = bc.delete_connection(conn_id, _uid(request))
    if not ok:
        raise HTTPException(status_code=404, detail="connection not found")
    return _envelope({"deleted": conn_id})


@router.post("/{conn_id}/test")
def test_connection(conn_id: str, request: Request) -> Dict[str, Any]:
    """Log in to Capital.com with the stored credentials and read the account —
    no data is written."""
    uid = _uid(request)
    try:
        secret = bc.get_secret(conn_id, uid)
    except bc.CredentialError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    ok, msg = _probe(secret)
    bc.record_sync_result(conn_id, ok, None if ok else msg, uid)
    return _envelope({"ok": ok, "detail": msg})


@router.post("/{conn_id}/sync")
def sync_connection(conn_id: str, request: Request) -> Dict[str, Any]:
    """Run one Capital.com history/balance/positions pull for this connection."""
    uid = _uid(request)
    try:
        secret = bc.get_secret(conn_id, uid)
    except bc.CredentialError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    import capital_sync
    try:
        with tenant.use(uid):
            ok = bool(capital_sync.sync_capital(creds=secret))
        err = None if ok else "sync returned no data / auth failed"
    except Exception as exc:  # noqa: BLE001
        ok, err = False, str(exc)[:300]
    bc.record_sync_result(conn_id, ok, err, uid)
    return _envelope({"ok": ok, "detail": err or "synced"})


def _probe(secret: Dict[str, str]) -> tuple[bool, str]:
    """Minimal auth check against Capital.com — POST /session, read a token."""
    import requests
    base = ("https://demo-api-capital.backend-capital.com/api/v1"
            if secret.get("is_demo") else
            "https://api-capital.backend-capital.com/api/v1")
    try:
        r = requests.post(
            f"{base}/session",
            headers={"X-CAP-API-KEY": (secret.get("api_key") or "").strip(),
                     "Content-Type": "application/json"},
            json={"identifier": (secret.get("email") or "").strip(),
                  "password": (secret.get("password") or "").strip()},
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"network error: {exc}"
    if r.status_code == 200 and r.headers.get("CST"):
        return True, "authenticated"
    return False, f"auth failed ({r.status_code})"
