# -*- coding: utf-8 -*-
"""
FastAPI router for the prop-firm challenge tracker (W13).

Config writes go through a settings blob (`api/challenge.py`); every other
route just computes a live status snapshot from already-authoritative
sources. No execution path, no order or broker-credential access.
"""
from fastapi import APIRouter, HTTPException, Query

from api import challenge as engine
from api.schemas import (
    ChallengeAdvanceRequest,
    ChallengeConfigRequest,
    ChallengeResetRequest,
    ChallengeStatusResponse,
)

router = APIRouter(prefix="/api/challenge", tags=["Challenge"])


@router.get("/status", response_model=ChallengeStatusResponse)
def challenge_status(account: str = Query(..., min_length=1, max_length=128)) -> ChallengeStatusResponse:
    """Live phase progress / drawdown / daily-loss / profit-day snapshot for
    one account. `configured=false` (all other fields null) if this account
    has no saved challenge config yet — not an error."""
    return ChallengeStatusResponse(**engine.compute_status(account.strip()))


@router.post("/config", response_model=ChallengeStatusResponse)
def save_challenge_config(body: ChallengeConfigRequest) -> ChallengeStatusResponse:
    """Create or update the rule set for one account. Updating an existing
    config edits its rules in place — phase progress is untouched; use
    `/reset` to actually restart the attempt."""
    account = body.account_id.strip()
    engine.save_config(account, body.model_dump(exclude={"account_id"}))
    return ChallengeStatusResponse(**engine.compute_status(account))


@router.post("/advance", response_model=ChallengeStatusResponse)
def advance_challenge_phase(body: ChallengeAdvanceRequest) -> ChallengeStatusResponse:
    """Manually mark the current phase passed and move to the next one —
    snapshots the live balance as the new phase's starting point."""
    account = body.account_id.strip()
    if engine.advance_phase(account, body.to) is None:
        raise HTTPException(status_code=404, detail=f"No challenge configured for account '{account}'")
    return ChallengeStatusResponse(**engine.compute_status(account))


@router.post("/reset", response_model=ChallengeStatusResponse)
def reset_challenge(body: ChallengeResetRequest) -> ChallengeStatusResponse:
    """Restart the attempt from Phase 1 at the configured account size —
    for a failed evaluation bought again, not for a routine edit."""
    account = body.account_id.strip()
    if engine.reset_challenge(account) is None:
        raise HTTPException(status_code=404, detail=f"No challenge configured for account '{account}'")
    return ChallengeStatusResponse(**engine.compute_status(account))


@router.delete("/config")
def delete_challenge_config(account: str = Query(..., min_length=1, max_length=128)) -> dict:
    from datetime import datetime, timezone

    engine.delete_config(account.strip())
    return {"account_id": account.strip(), "deleted": True, "timestamp": datetime.now(timezone.utc).isoformat()}
