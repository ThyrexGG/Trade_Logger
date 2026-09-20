# -*- coding: utf-8 -*-
"""
Weekly performance summary (see api/weekly_summary.py): this week so far and last week, plus the on/off
switch for the Sunday notification. Read-only over closed trades.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from api import weekly_summary

router = APIRouter(prefix="/api/weekly-summary", tags=["Weekly summary"])

_NOTE = ("Weeks run Monday to Sunday (UTC). The summary is sent on Sunday from 12:00 UTC and counts closed "
         "trades only. A week with no closed trades sends nothing.")


class SummarySettingIn(BaseModel):
    model_config = {"extra": "forbid"}
    enabled: bool


def _week(start, now: datetime) -> Dict[str, Any]:
    end = start + timedelta(days=6)
    return {
        "start": start.isoformat(), "end": end.isoformat(), "key": weekly_summary.week_key(start),
        "is_current": weekly_summary.week_start(now.date()) == start,
        "summary": weekly_summary.summarize(start),
    }


@router.get("")
def get_summary() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    cur = weekly_summary.week_start(now.date())
    return {
        "enabled": weekly_summary.is_enabled(),
        "weeks": [_week(cur, now), _week(cur - timedelta(days=7), now)],
        "note": _NOTE,
        "timestamp": now.isoformat(),
    }


@router.put("")
def set_summary(body: SummarySettingIn) -> Dict[str, Any]:
    weekly_summary.set_enabled(body.enabled)
    if body.enabled:
        try:  # the watcher that sends it must be running
            from api import sync_service
            sync_service.watch_alerts()
        except Exception:  # noqa: BLE001 - saving the preference must not fail because the watcher could not start
            pass
    return {"enabled": weekly_summary.is_enabled()}
