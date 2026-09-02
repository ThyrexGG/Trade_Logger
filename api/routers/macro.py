# -*- coding: utf-8 -*-
"""
FastAPI Macro / Market Intelligence Router (Stage 18F).

Read-only. Thin envelope over `api.macro_service` (which orchestrates the
deterministic engines in `macro_intelligence_engine.py` + the Stage 18A
provider). GET-only; no import of / path to execution_pipeline, broker_adapter
or risk_gateway. Every response carries `data_provider` / `provider_is_live` /
`provenance` — seeded/demo data is never presented as real.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api import macro_service
from api.macro_provider import IMPACT_LEVELS, SUPPORTED_CURRENCIES
from api.macro_service import SUPPORTED_ASSETS
from api.schemas import (
    MacroAssetResponse,
    MacroAssetsResponse,
    MacroCurrenciesResponse,
    MacroCurrencyResponse,
    MacroEventsResponse,
    MacroOverviewResponse,
    MacroPairsResponse,
    MacroSurprisesResponse,
)

router = APIRouter(prefix="/api/macro", tags=["Macro Intelligence"])

_WINDOWS = {"all", "upcoming", "recent"}


def _valid_date(raw: str, field: str) -> None:
    try:
        datetime.strptime(raw.strip(), "%Y-%m-%d")
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail=f"{field} must be an ISO date (YYYY-MM-DD)")


@router.get("/events", response_model=MacroEventsResponse)
def macro_events(
    window: str = Query(default="all"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    country: str | None = Query(default=None, max_length=48),
    currency: str | None = Query(default=None, max_length=3),
    impact: str | None = Query(default=None),
    indicator: str | None = Query(default=None, max_length=48),
    limit: int = Query(default=200, ge=1, le=500),
) -> MacroEventsResponse:
    if window not in _WINDOWS:
        raise HTTPException(status_code=422, detail=f"window must be one of {sorted(_WINDOWS)}")
    if start:
        _valid_date(start, "start")
    if end:
        _valid_date(end, "end")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    if currency and currency.upper() not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=422, detail=f"currency must be one of {SUPPORTED_CURRENCIES}")
    if impact and impact.upper() not in IMPACT_LEVELS:
        raise HTTPException(status_code=422, detail=f"impact must be one of {IMPACT_LEVELS}")
    return MacroEventsResponse(**macro_service.get_events(
        window=window, start=start, end=end, country=country, currency=currency,
        impact=impact, indicator=indicator, limit=limit,
    ))


@router.get("/events/upcoming", response_model=MacroEventsResponse)
def macro_events_upcoming(limit: int = Query(default=100, ge=1, le=500)) -> MacroEventsResponse:
    return MacroEventsResponse(**macro_service.get_events(window="upcoming", limit=limit))


@router.get("/events/recent", response_model=MacroEventsResponse)
def macro_events_recent(limit: int = Query(default=100, ge=1, le=500)) -> MacroEventsResponse:
    return MacroEventsResponse(**macro_service.get_events(window="recent", limit=limit))


@router.get("/surprises", response_model=MacroSurprisesResponse)
def macro_surprises(
    currency: str | None = Query(default=None, max_length=3),
    limit: int = Query(default=60, ge=1, le=200),
) -> MacroSurprisesResponse:
    if currency and currency.upper() not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=422, detail=f"currency must be one of {SUPPORTED_CURRENCIES}")
    return MacroSurprisesResponse(**macro_service.get_surprises(currency=currency, limit=limit))


@router.get("/currencies", response_model=MacroCurrenciesResponse)
def macro_currencies() -> MacroCurrenciesResponse:
    return MacroCurrenciesResponse(**macro_service.get_currencies())


@router.get("/currencies/{currency}", response_model=MacroCurrencyResponse)
def macro_currency(currency: str) -> MacroCurrencyResponse:
    if currency.upper() not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=404, detail=f"Unsupported currency. Supported: {SUPPORTED_CURRENCIES}")
    return MacroCurrencyResponse(**macro_service.get_currency(currency))


@router.get("/pairs", response_model=MacroPairsResponse)
def macro_pairs() -> MacroPairsResponse:
    return MacroPairsResponse(**macro_service.get_pairs())


@router.get("/assets", response_model=MacroAssetsResponse)
def macro_assets() -> MacroAssetsResponse:
    return MacroAssetsResponse(**macro_service.get_assets())


@router.get("/assets/{asset}", response_model=MacroAssetResponse)
def macro_asset(asset: str) -> MacroAssetResponse:
    if asset.upper() not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"Unsupported asset. Supported: {SUPPORTED_ASSETS}")
    return MacroAssetResponse(**macro_service.get_asset(asset))


@router.get("/overview", response_model=MacroOverviewResponse)
def macro_overview() -> MacroOverviewResponse:
    return MacroOverviewResponse(**macro_service.get_overview())
