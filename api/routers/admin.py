# -*- coding: utf-8 -*-
"""
FastAPI Admin Router (platform plan W8.7).

A minimal owner-only surface for the multi-user build: see who has an account
and disable / re-enable one. Only a user whose ``users.role`` is ``owner`` may
call these; everyone else gets 403. Meaningful only in supabase auth mode.

Read-only with respect to trading — nothing here touches a journal row, a
broker connection's secret, or an order path.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from api import identity

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def _require_owner(request: Request) -> Dict[str, Any]:
    user = getattr(getattr(request, "state", None), "user", None)
    if not user or user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner only.")
    return user


@router.get("/users")
def list_users(request: Request) -> Dict[str, Any]:
    _require_owner(request)
    users = [
        {
            "id": u["id"], "email": u["email"], "display_name": u.get("display_name"),
            "role": u["role"], "status": u["status"],
            "created_at": u["created_at"], "last_seen_at": u["last_seen_at"],
        }
        for u in identity.list_users()
    ]
    return {"users": users, "count": len(users)}


@router.post("/users/{user_id}/disable")
def disable_user(user_id: str, request: Request) -> Dict[str, Any]:
    me = _require_owner(request)
    if user_id == me["id"]:
        raise HTTPException(status_code=400, detail="You can't disable your own account.")
    target = identity.get_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="No such user.")
    identity.set_user_status(user_id, "disabled")
    return {"id": user_id, "status": "disabled"}


@router.post("/users/{user_id}/enable")
def enable_user(user_id: str, request: Request) -> Dict[str, Any]:
    _require_owner(request)
    if not identity.get_user(user_id):
        raise HTTPException(status_code=404, detail="No such user.")
    identity.set_user_status(user_id, "active")
    return {"id": user_id, "status": "active"}
