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
import tenant

ACCOUNT_TABLES: tuple = ("closed_trades", "open_positions", "account_metadata",
                        "raw_deals", "price_alerts")

# Single-column primary key per ACCOUNT_TABLES entry -- what `restore_account`
# conflicts on so a restore never duplicates a row that's already there.
_PRIMARY_KEY: Dict[str, str] = {
    "closed_trades": "trade_id",
    "open_positions": "position_id",
    "account_metadata": "account_id",
    "raw_deals": "deal_id",
    "price_alerts": "id",
}

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
    uid = tenant.current_user_id()
    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        out: Dict[str, Dict[str, int]] = {}
        for table in ACCOUNT_TABLES:
            cursor.execute(
                f"SELECT account_id, COUNT(*) FROM {table} WHERE user_id = {ph} GROUP BY account_id",
                (uid,),
            )
            for account_id, count in cursor.fetchall():
                out.setdefault(str(account_id), {})[table] = int(count)
        return out
    finally:
        conn.close()


def export_account(account_id: str, output_dir: Optional[str] = None) -> str:
    """Read-only. Dumps every row across ACCOUNT_TABLES for ``account_id``
    into one timestamped JSON snapshot file and returns its path. Never
    deletes or modifies anything."""
    uid = tenant.current_user_id()
    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)
        tables: Dict[str, List[Dict[str, Any]]] = {}
        for table in ACCOUNT_TABLES:
            cursor.execute(
                f"SELECT * FROM {table} WHERE account_id = {placeholder} AND user_id = {placeholder}",
                (account_id, uid),
            )
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

    uid = tenant.current_user_id()
    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)
        deleted: Dict[str, int] = {}
        for table in ACCOUNT_TABLES:
            cursor.execute(
                f"DELETE FROM {table} WHERE account_id = {placeholder} AND user_id = {placeholder}",
                (account_id, uid),
            )
            deleted[table] = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_exports(account_id: Optional[str] = None, output_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists export snapshots on disk (newest first), optionally filtered to
    one account_id. Each entry is what `restore_account` needs plus enough
    to show a human which snapshot is which -- it does not open every file,
    just reads each manifest's small header fields."""
    out_dir = output_dir or _EXPORT_DIR_DEFAULT
    if not os.path.isdir(out_dir):
        return []
    uid = tenant.current_user_id()
    entries: List[Dict[str, Any]] = []
    for name in os.listdir(out_dir):
        if not (name.startswith("account_export_") and name.endswith(".json")):
            continue
        path = os.path.join(out_dir, name)
        try:
            manifest = _load_export_manifest(path)
        except Exception:
            continue
        exp_account_id = str(manifest.get("account_id", ""))
        if account_id is not None and exp_account_id != str(account_id):
            continue
        # Only surface snapshots this tenant could actually restore -- a
        # snapshot belongs to this tenant if every row in it does.
        tables = manifest.get("tables", {})
        owned = all(
            str(row.get("user_id")) == str(uid)
            for rows in tables.values()
            for row in rows
            if "user_id" in row
        )
        if not owned:
            continue
        entries.append({
            "export_path": path,
            "account_id": exp_account_id,
            "exported_at": manifest.get("exported_at"),
            "row_counts": manifest.get("row_counts", {}),
        })
    entries.sort(key=lambda e: e.get("exported_at") or "", reverse=True)
    return entries


def restore_account(exported_file_path: str) -> Dict[str, int]:
    """Re-inserts every row from an export snapshot -- the undo for
    `remove_account`. Refuses (raises ValueError) unless every row in the
    snapshot belongs to the calling tenant, so one user's export can never
    be replayed into another user's data. A row whose primary key already
    exists is left alone (skip, never overwrite) -- restoring is additive
    and safe to run more than once. Returns rows actually inserted per
    table."""
    if not os.path.isfile(exported_file_path):
        raise ValueError(f"Export file not found: {exported_file_path}.")
    manifest = _load_export_manifest(exported_file_path)
    tables = manifest.get("tables", {})

    uid = tenant.current_user_id()
    for table, rows in tables.items():
        for row in rows:
            row_uid = row.get("user_id")
            if row_uid is not None and str(row_uid) != str(uid):
                raise ValueError(
                    f"Export contains rows for a different user (table={table}) -- refusing to restore."
                )

    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)
        is_pg = database.is_postgres()
        restored: Dict[str, int] = {}
        for table in ACCOUNT_TABLES:
            rows = tables.get(table) or []
            if not rows:
                restored[table] = 0
                continue
            cols = list(rows[0].keys())
            col_list = ", ".join(cols)
            value_placeholders = ", ".join([placeholder] * len(cols))
            pk = _PRIMARY_KEY[table]
            if is_pg:
                sql = (f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) "
                       f"ON CONFLICT ({pk}) DO NOTHING")
            else:
                sql = f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({value_placeholders})"
            inserted = 0
            for row in rows:
                cursor.execute(sql, [row.get(c) for c in cols])
                if cursor.rowcount and cursor.rowcount > 0:
                    inserted += 1
            restored[table] = inserted
        conn.commit()
        return restored
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


__all__ = [
    "ACCOUNT_TABLES", "list_accounts", "export_account", "remove_account",
    "list_exports", "restore_account",
]
