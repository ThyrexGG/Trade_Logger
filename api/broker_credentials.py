# -*- coding: utf-8 -*-
"""
Per-user broker credentials, encrypted at rest (platform plan W8.5).

Each user can connect their own Capital.com account. The API key / login /
password are encrypted with Fernet (AES-128-CBC + HMAC) using a single
server-held key in ``TL_CREDENTIAL_ENC_KEY`` and stored as one ciphertext blob
in ``broker_connections.secret_ciphertext``. Plaintext secrets never leave the
server: the list/read API returns only non-secret metadata; the decrypted
secret is handed out solely to the sync path.

``account_id`` and ``is_demo`` are stored in the clear — a broker account id is
an identifier, not a credential, and the demo flag is just routing.

Still no order path. These credentials are used only for Capital.com's
read-only history / balance / positions endpoints (see ``capital_sync``).

The table follows the repo's runtime-DDL pattern (like ``sessions`` /
``users``): ``CREATE TABLE IF NOT EXISTS`` on first use, not an Alembic
revision.
"""
from __future__ import annotations

import json
import os
import secrets as _secrets
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import database
import tenant

_KEY_ENV = "TL_CREDENTIAL_ENC_KEY"
_SECRET_FIELDS = ("api_key", "email", "password")

_table_ready = False
_table_lock = threading.Lock()


class CredentialError(Exception):
    """Encryption key missing / invalid, or a connection not found for the tenant."""


# --- key / crypto ------------------------------------------------------

def enc_enabled() -> bool:
    return bool((os.getenv(_KEY_ENV) or "").strip())


def generate_key() -> str:
    """A fresh urlsafe-base64 Fernet key — for ``TL_CREDENTIAL_ENC_KEY``."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode("ascii")


def _fernet():
    raw = (os.getenv(_KEY_ENV) or "").strip()
    if not raw:
        raise CredentialError(
            f"{_KEY_ENV} is not configured — broker connections are disabled. "
            f"Generate one with: python -c \"from api.broker_credentials import generate_key; print(generate_key())\""
        )
    try:
        from cryptography.fernet import Fernet
        return Fernet(raw.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise CredentialError(f"{_KEY_ENV} is not a valid Fernet key: {exc}") from exc


def _encrypt(secret: Dict[str, str]) -> str:
    payload = json.dumps({k: str(secret.get(k, "")) for k in _SECRET_FIELDS}).encode("utf-8")
    return _fernet().encrypt(payload).decode("ascii")


def _decrypt(ciphertext: str) -> Dict[str, str]:
    try:
        data = json.loads(_fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8"))
    except CredentialError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CredentialError(f"could not decrypt stored credential: {exc}") from exc
    return {k: str(data.get(k, "")) for k in _SECRET_FIELDS}


# --- table -----------------------------------------------------------

def _ph(conn) -> str:
    return "%s" if database.is_postgres() else "?"


def ensure_table() -> None:
    global _table_ready
    if _table_ready:
        return
    with _table_lock:
        if _table_ready:
            return
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS broker_connections (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    broker TEXT NOT NULL DEFAULT 'capital',
                    label TEXT,
                    secret_ciphertext TEXT NOT NULL,
                    account_id TEXT,
                    is_demo INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_sync_at TEXT,
                    last_sync_ok INTEGER,
                    last_error TEXT
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_broker_connections_user "
                "ON broker_connections (user_id)"
            )
            conn.commit()
            _table_ready = True
        finally:
            conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_META_COLS = (
    "id, user_id, broker, label, account_id, is_demo, is_active, "
    "created_at, updated_at, last_sync_at, last_sync_ok, last_error"
)


def _row_to_meta(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "user_id": row[1],
        "broker": row[2],
        "label": row[3],
        "account_id": row[4],
        "is_demo": bool(row[5]),
        "is_active": bool(row[6]),
        "created_at": row[7],
        "updated_at": row[8],
        "last_sync_at": row[9],
        "last_sync_ok": None if row[10] is None else bool(row[10]),
        "last_error": row[11],
    }


# --- CRUD (tenant-scoped) -------------------------------------------

def list_connections(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Metadata only — never the secret."""
    uid = tenant.resolve(user_id)
    ensure_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {_META_COLS} FROM broker_connections WHERE user_id = {_ph(conn)} "
            f"ORDER BY created_at",
            (uid,),
        )
        return [_row_to_meta(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _get_row(conn, conn_id: str, uid: str):
    cur = conn.cursor()
    ph = _ph(conn)
    cur.execute(
        f"SELECT {_META_COLS}, secret_ciphertext FROM broker_connections "
        f"WHERE id = {ph} AND user_id = {ph}",
        (conn_id, uid),
    )
    return cur.fetchone()


def get_meta(conn_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    uid = tenant.resolve(user_id)
    ensure_table()
    conn = database.get_connection()
    try:
        row = _get_row(conn, conn_id, uid)
        return _row_to_meta(row) if row else None
    finally:
        conn.close()


def get_secret(conn_id: str, user_id: Optional[str] = None) -> Dict[str, str]:
    """Decrypted ``{api_key, email, password}`` + ``account_id`` / ``is_demo``.
    Used only by the sync path."""
    uid = tenant.resolve(user_id)
    ensure_table()
    conn = database.get_connection()
    try:
        row = _get_row(conn, conn_id, uid)
    finally:
        conn.close()
    if not row:
        raise CredentialError("connection not found")
    meta = _row_to_meta(row)
    secret = _decrypt(row[-1])
    secret["account_id"] = meta["account_id"] or ""
    secret["is_demo"] = meta["is_demo"]
    return secret


def create_connection(
    *, secret: Dict[str, str], account_id: str, is_demo: bool = False,
    label: str = "", broker: str = "capital", user_id: Optional[str] = None,
) -> Dict[str, Any]:
    missing = [f for f in _SECRET_FIELDS if not str(secret.get(f, "")).strip()]
    if missing:
        raise CredentialError(f"missing credential fields: {', '.join(missing)}")
    uid = tenant.resolve(user_id)
    ensure_table()
    cid = _secrets.token_urlsafe(12)
    ct = _encrypt(secret)
    now = _now()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"INSERT INTO broker_connections "
            f"(id, user_id, broker, label, secret_ciphertext, account_id, is_demo, "
            f" is_active, created_at, updated_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 1, {ph}, {ph})",
            (cid, uid, broker, (label or None), ct, (account_id or None),
             1 if is_demo else 0, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return get_meta(cid, uid)


def update_connection(
    conn_id: str, *, secret: Optional[Dict[str, str]] = None,
    account_id: Optional[str] = None, is_demo: Optional[bool] = None,
    label: Optional[str] = None, is_active: Optional[bool] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    uid = tenant.resolve(user_id)
    ensure_table()
    sets: List[str] = []
    params: List[Any] = []
    conn = database.get_connection()
    ph = _ph(conn)
    try:
        if not _get_row(conn, conn_id, uid):
            raise CredentialError("connection not found")
        if secret is not None:
            # merge onto the existing secret so a partial edit keeps the rest
            current = _decrypt(_get_row(conn, conn_id, uid)[-1])
            merged = {f: (str(secret[f]) if secret.get(f) else current.get(f, "")) for f in _SECRET_FIELDS}
            sets.append(f"secret_ciphertext = {ph}")
            params.append(_encrypt(merged))
        if account_id is not None:
            sets.append(f"account_id = {ph}")
            params.append(account_id or None)
        if is_demo is not None:
            sets.append(f"is_demo = {ph}")
            params.append(1 if is_demo else 0)
        if label is not None:
            sets.append(f"label = {ph}")
            params.append(label or None)
        if is_active is not None:
            sets.append(f"is_active = {ph}")
            params.append(1 if is_active else 0)
        if not sets:
            return get_meta(conn_id, uid)
        sets.append(f"updated_at = {ph}")
        params.append(_now())
        params.extend([conn_id, uid])
        cur = conn.cursor()
        cur.execute(
            f"UPDATE broker_connections SET {', '.join(sets)} WHERE id = {ph} AND user_id = {ph}",
            tuple(params),
        )
        conn.commit()
    finally:
        conn.close()
    return get_meta(conn_id, uid)


def delete_connection(conn_id: str, user_id: Optional[str] = None) -> bool:
    uid = tenant.resolve(user_id)
    ensure_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"DELETE FROM broker_connections WHERE id = {ph} AND user_id = {ph}",
            (conn_id, uid),
        )
        n = cur.rowcount or 0
        conn.commit()
        return n > 0
    finally:
        conn.close()


def record_sync_result(conn_id: str, ok: bool, error: Optional[str] = None,
                       user_id: Optional[str] = None) -> None:
    uid = tenant.resolve(user_id)
    ensure_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"UPDATE broker_connections SET last_sync_at = {ph}, last_sync_ok = {ph}, "
            f"last_error = {ph} WHERE id = {ph} AND user_id = {ph}",
            (_now(), 1 if ok else 0, (error or None)[:500] if error else None, conn_id, uid),
        )
        conn.commit()
    finally:
        conn.close()


def active_connections_all_users(broker: str = "capital") -> List[Dict[str, Any]]:
    """Every active connection across all users — for the per-user sync loop
    (W8.6). Includes the decrypted secret; callers run one tenant at a time."""
    ensure_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"SELECT {_META_COLS}, secret_ciphertext FROM broker_connections "
            f"WHERE is_active = 1 AND broker = {ph} ORDER BY user_id, created_at",
            (broker,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        meta = _row_to_meta(row)
        secret = _decrypt(row[-1])
        secret["account_id"] = meta["account_id"] or ""
        secret["is_demo"] = meta["is_demo"]
        out.append({"id": meta["id"], "user_id": meta["user_id"], "secret": secret})
    return out


if __name__ == "__main__":  # pragma: no cover
    print(generate_key())
