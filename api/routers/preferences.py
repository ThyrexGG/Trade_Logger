# -*- coding: utf-8 -*-
"""
FastAPI Preferences Router — Stage 3 User Preferences Endpoint
Directly consumes UserPreferencesManager with SQLite persistence.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from api.schemas import UserPreferencesModel, UserPreferencesUpdateRequest, UserPreferencesResponse
from user_preferences import UserPreferencesManager, DEFAULT_PREFERENCES

router = APIRouter(prefix="/api", tags=["Preferences"])

ALLOWED_LAYOUTS = {"DEFAULT", "RESEARCH", "COMPACT", "ANALYSIS"}
ALLOWED_ASSETS = {"XAUUSD", "USDJPY", "EURUSD", "GBPUSD", "GBPJPY", "SPX500", "NAS100", "DXY", "BTCUSD", "USOIL"}
ALLOWED_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h", "1d"}
ALLOWED_FILTERS = {"ALL", "COMMODITY", "FOREX", "INDEX", "CRYPTO"}


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences() -> UserPreferencesResponse:
    """
    Retrieves the current persistent user terminal preferences.
    """
    prefs = UserPreferencesManager.get_all_preferences()
    validated_model = UserPreferencesModel(**prefs)
    return UserPreferencesResponse(
        preferences=validated_model,
        updated_at=datetime.now(timezone.utc).isoformat()
    )


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_preferences(req: UserPreferencesUpdateRequest) -> UserPreferencesResponse:
    """
    Updates one or more user preferences and persists to SQLite.
    Validates layout, asset, timeframe, and filter constraints.
    """
    update_dict = req.model_dump(exclude_unset=True)

    if "active_workspace_layout" in update_dict:
        layout = update_dict["active_workspace_layout"].upper().strip()
        if layout not in ALLOWED_LAYOUTS:
            raise HTTPException(status_code=400, detail=f"Invalid layout '{layout}'. Allowed: {list(ALLOWED_LAYOUTS)}")
        update_dict["active_workspace_layout"] = layout

    if "selected_asset" in update_dict:
        asset = update_dict["selected_asset"].upper().strip()
        if asset not in ALLOWED_ASSETS:
            raise HTTPException(status_code=400, detail=f"Invalid asset '{asset}'.")
        update_dict["selected_asset"] = asset

    if "selected_timeframe" in update_dict:
        tf = update_dict["selected_timeframe"].lower().strip()
        if tf not in ALLOWED_TIMEFRAMES:
            raise HTTPException(status_code=400, detail=f"Invalid timeframe '{tf}'.")
        update_dict["selected_timeframe"] = tf

    if "watchlist_filter" in update_dict:
        filt = update_dict["watchlist_filter"].upper().strip()
        if filt not in ALLOWED_FILTERS:
            raise HTTPException(status_code=400, detail=f"Invalid filter '{filt}'.")
        update_dict["watchlist_filter"] = filt

    # Apply updates to SQLite store
    for key, val in update_dict.items():
        UserPreferencesManager.set_preference(key, val, persist_to_db=True)

    updated_prefs = UserPreferencesManager.get_all_preferences()
    return UserPreferencesResponse(
        preferences=UserPreferencesModel(**updated_prefs),
        updated_at=datetime.now(timezone.utc).isoformat()
    )
