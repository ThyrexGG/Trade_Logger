# -*- coding: utf-8 -*-
"""
FastAPI Accounts Router — list, export, and remove an account's historical
footprint from the trade journal / research database.

Read-only listing and export; removal is destructive but gated in code
(account_management.remove_account) to require a matching export snapshot
first — "export first, then clear" is enforced server-side, not left to
the caller. This router never touches MT5/Capital.com credentials, never
imports an execution/broker/risk module, and never places, modifies, or
cancels an order.
"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

import account_management as am

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


@router.get("")
def list_accounts() -> Dict[str, Any]:
    """Row counts per account_id, per table, across every table that
    carries an account_id column. Use this to see what exists before
    exporting or removing one."""
    return {"accounts": am.list_accounts()}


@router.post("/{account_id}/export")
def export_account(account_id: str) -> Dict[str, Any]:
    """Read-only: writes a full JSON snapshot of this account's rows
    (closed trades, open positions, account metadata, raw deals, price
    alerts) to disk and returns its path. Never deletes anything. Pass the
    returned `export_path` to the DELETE endpoint to actually remove the
    account afterward."""
    path = am.export_account(account_id)
    return {"account_id": account_id, "export_path": path}


@router.delete("/{account_id}")
def remove_account(account_id: str,
                   exported_file_path: str = Query(..., description=(
                       "Path returned by POST /api/accounts/{account_id}/export "
                       "for this exact account_id -- required so removal can "
                       "never run without an export already on disk."))
                   ) -> Dict[str, Any]:
    """Deletes every row for this account_id across the account-scoped
    tables. Refuses (HTTP 400) unless `exported_file_path` is a real
    export snapshot for this exact account_id."""
    try:
        deleted = am.remove_account(account_id, exported_file_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"account_id": account_id, "deleted_rows": deleted}
