# -*- coding: utf-8 -*-
"""
Referral-bonus claims (W-something: monetization).

A user self-reports "I signed up with your 5ers link" here; the owner
reviews it by eye (there's no API tying a small affiliate's dashboard back
to a specific TradeLogger account) via the admin endpoints in this same
router. See api/referrals.py for what "reward" actually means right now —
a recorded promise, not something enforced automatically.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from api import referrals as ref

router = APIRouter(prefix="/api/referrals", tags=["Referrals"])


def _require_owner(request: Request) -> Dict[str, Any]:
    user = getattr(getattr(request, "state", None), "user", None)
    if not user or user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner only.")
    return user


@router.post("/claim")
def claim(partner_id: str = Query(...), note: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Self-report a referral signup. Idempotent — claiming the same partner
    twice returns the existing claim rather than creating a duplicate."""
    return {"claim": ref.claim_referral(partner_id, note)}


@router.get("/mine")
def mine() -> Dict[str, Any]:
    """The current user's own claims, so the UI can show pending/verified/rejected."""
    return {"claims": ref.list_my_claims()}


@router.get("/admin/all")
def admin_list(request: Request, status: Optional[str] = Query(None)) -> Dict[str, Any]:
    _require_owner(request)
    return {"claims": ref.list_all_claims(status)}


@router.post("/admin/{claim_id}/verify")
def admin_verify(claim_id: str, request: Request) -> Dict[str, Any]:
    me = _require_owner(request)
    try:
        return {"claim": ref.set_claim_status(claim_id, "verified", me["id"])}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/admin/{claim_id}/reject")
def admin_reject(claim_id: str, request: Request) -> Dict[str, Any]:
    me = _require_owner(request)
    try:
        return {"claim": ref.set_claim_status(claim_id, "rejected", me["id"])}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
