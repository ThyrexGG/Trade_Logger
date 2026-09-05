# -*- coding: utf-8 -*-
"""
Account management -- list, export, and remove an account's historical
footprint from the trade journal / research database.

Scope: this module only ever touches the 5 tables that actually carry an
``account_id`` column (``closed_trades``, ``open_positions``,
``account_metadata``, ``raw_deals``, ``price_alerts`` -- verified by
inspecting every ``CREATE TABLE`` in database.py; every other table,
including ``execution_orders`` and ``execution_audit_log``, has no
account_id column and is untouched). It never reads or writes MT5/
Capital.com credentials (``.env``), never imports an execution/broker/risk
module, and never places, modifies, or cancels an order -- it is a pure
data-management utility over already-recorded history.

Safety discipline for ``remove_account``: it refuses to delete anything
unless it is given the path to an export snapshot that was just produced
for that exact account_id (``export_account``'s own return value) --
"export first, then clear" is enforced in code, not left to the caller's
memory. The export step itself is fully read-only and safe to run at any
time.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import database

ACCOUNT_TABLES: tuple = ("closed_trades", "open_positions", "account_metadata",
                        "raw_deals", "price_alerts")

_EXPORT_DIR_DEFAULT = os.path.join(os.path.dirname(__file__), "exports")


def _rows_as_dicts(cursor, rows) -> List[Dict[str, Any]]:
    cols = [d[0] for d in cursor.description]
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        out.append(d)
    return out


def list_accounts() -> Dict[str, Dict[str, int]]:
    """Row counts per account_id, per table -- lets a caller see exactly
    what exists before choosing one to export/remove."""
    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        out: Dict[str, Dict[str, int]] = {}
        for table in ACCOUNT_TABLES:
            cursor.execute(f"SELECT account_id, COUNT(*) FROM {table} GROUP BY account_id")
            for account_id, count in cursor.fetchall():
                out.setdefault(str(account_id), {})[table] = int(count)
        return out
    finally:
        conn.close()


def export_account(account_id: str, output_dir: Optional[str] = None) -> str:
    """Read-only. Dumps every row across ACCOUNT_TABLES for ``account_id``
    into one timestamped JSON snapshot file and returns its path. Never
    deletes or modifies anything."""
    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)
        tables: Dict[str, List[Dict[str, Any]]] = {}
        for table in ACCOUNT_TABLES:
            cursor.execute(f"SELECT * FROM {table} WHERE account_id = {placeholder}", (account_id,))
            tables[table] = _rows_as_dicts(cursor, cursor.fetchall())
    finally:
        conn.close()

    out_dir = output_dir or _EXPORT_DIR_DEFAULT
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_id = "".join(c if c.isalnum() else "_" for c in str(account_id))
    path = os.path.join(out_dir, f"account_export_{safe_id}_{ts}.json")
    payload = {
        "account_id": account_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "row_counts": {t: len(rows) for t, rows in tables.items()},
        "tables": tables,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    return path


def _load_export_manifest(exported_file_path: str) -> Dict[str, Any]:
    with open(exported_file_path, encoding="utf-8") as fh:
        return json.load(fh)


def remove_account(account_id: str, exported_file_path: str) -> Dict[str, int]:
    """Deletes every row for ``account_id`` across ACCOUNT_TABLES. Refuses
    to run unless ``exported_file_path`` is a real, readable export
    snapshot whose own account_id matches -- "export first, then clear" is
    enforced here, not left to the caller. Returns the number of rows
    deleted per table."""
    if not os.path.isfile(exported_file_path):
        raise ValueError(f"Export file not found: {exported_file_path}. "
                        "Run export_account(account_id) first and pass its return value here.")
    manifest = _load_export_manifest(exported_file_path)
    if str(manifest.get("account_id")) != str(account_id):
        raise ValueError(f"Export file is for account_id={manifest.get('account_id')!r}, "
                        f"not {account_id!r} -- refusing to delete.")

    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)
        deleted: Dict[str, int] = {}
        for table in ACCOUNT_TABLES:
            cursor.execute(f"DELETE FROM {table} WHERE account_id = {placeholder}", (account_id,))
            deleted[table] = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


__all__ = ["ACCOUNT_TABLES", "list_accounts", "export_account", "remove_account"]
