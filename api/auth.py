# -*- coding: utf-8 -*-
"""
Single-user authentication for the TradeLogger API (platform plan W3).

The API is read-only — auth exists so that once the port is reachable from the
internet, private financial history is not world-readable. There is still no
order path and no execution authority anywhere.

Model (D5 — single user now, multi-user later as W8):
- One passphrase. Its scrypt hash lives in the environment
  (`TL_AUTH_PASSWORD_HASH`), or a plaintext `TL_AUTH_PASSWORD` is hashed at boot
  (convenient for a private box; the hash form is preferred).
- Login mints an opaque session token (`secrets.token_urlsafe`). Only its
  SHA-256 is stored, in a `sessions` table. The token rides in an httpOnly
  cookie (`tl_session`) or an `Authorization: Bearer` header.
- Long-lived (default 30 days) and revocable — logout deletes the row, and
  `revoke_all_sessions()` is the "log out everywhere" button.
- Per-IP login rate limit with lockout.

Break-glass: set `TL_AUTH_DISABLED=1` (auth off entirely) or set a known
`TL_AUTH_PASSWORD` and restart. With NO password configured at all, auth is
disabled and every route is open — this keeps local dev and the test suite
working unchanged.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import database

_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_TOKEN_BYTES = 32
_COOKIE_NAME = "tl_session"

_sessions_ready = False
_sessions_lock = threading.Lock()

# --- per-IP login rate limiter (in-process) ---------------------------
_attempts: Dict[str, list] = {}
_attempts_lock = threading.Lock()


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _int_env(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


def cookie_name() -> str:
    return _COOKIE_NAME


def cookie_samesite() -> str:
    """SameSite policy for the session cookie.

    Default ``lax`` is right when the app and API share a site. Set
    ``TL_AUTH_COOKIE_SAMESITE=none`` when they are on unrelated domains (e.g.
    a ``*.pages.dev`` frontend calling a ``*.onrender.com`` API) — a Lax cookie
    is not sent on those cross-site requests. ``none`` implies a Secure cookie.
    """
    v = _env("TL_AUTH_COOKIE_SAMESITE", "lax").lower()
    return v if v in ("lax", "strict", "none") else "lax"


def cookie_secure() -> bool:
    # A SameSite=None cookie is only stored by browsers when it is also Secure.
    if cookie_samesite() == "none":
        return True
    return _env("TL_AUTH_COOKIE_SECURE", "1") not in ("0", "false", "no")


def session_ttl_days() -> int:
    return _int_env("TL_AUTH_SESSION_DAYS", 30)


# --- password ---------------------------------------------------------

def hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
    """`scrypt$<salt_hex>$<hash_hex>` — stdlib, no dependency."""
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
    )
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_hash(password: str, stored: str) -> bool:
    """True if ``password`` matches a ``scrypt$salt$hash`` string. Public so the
    multi-user identity layer can check per-account password hashes with the
    same KDF the single-user gate uses."""
    return _verify_against_hash(password, stored)


def _verify_against_hash(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, hash_hex = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=len(hash_hex) // 2,
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def _configured_hash() -> Optional[str]:
    h = _env("TL_AUTH_PASSWORD_HASH")
    if h:
        return h
    pw = _env("TL_AUTH_PASSWORD")
    if pw:
        # hashed per-process; deterministic salt from the password so a restart
        # keeps existing sessions valid without persisting the hash.
        salt = hashlib.sha256(b"tl-auth-static::" + pw.encode("utf-8")).digest()[:16]
        return hash_password(pw, salt=salt)
    return None


def auth_enabled() -> bool:
    if _env("TL_AUTH_DISABLED") in ("1", "true", "yes"):
        return False
    return _configured_hash() is not None


def verify_password(password: str) -> bool:
    stored = _configured_hash()
    if not stored or not password:
        return False
    return _verify_against_hash(password, stored)


# --- session store ---------------------------------------------------

def _ph(conn) -> str:
    return "%s" if database.is_postgres() else "?"


def _ensure_sessions_table() -> None:
    global _sessions_ready
    if _sessions_ready:
        return
    with _sessions_lock:
        if _sessions_ready:
            return
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    label TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT 'local'
                )
                """
            )
            # existing single-user deployments: add the column in place
            try:
                cur.execute(
                    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'local'"
                    if database.is_postgres()
                    else "ALTER TABLE sessions ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local'"
                )
            except Exception:
                conn.rollback()
            conn.commit()
            _sessions_ready = True
        finally:
            conn.close()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_session(label: str = "", user_id: str = "local") -> Tuple[str, str]:
    """Returns (raw_token, expires_at_iso). Only the hash is stored.

    ``user_id`` ties the session to an account in multi-user mode; it stays
    ``"local"`` for the single-user passphrase gate.
    """
    _ensure_sessions_table()
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    now = _now()
    expires = now + timedelta(days=session_ttl_days())
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"INSERT INTO sessions (token_hash, label, created_at, expires_at, last_seen_at, user_id) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (_hash_token(token), (label or "")[:120], now.isoformat(),
             expires.isoformat(), now.isoformat(), user_id or "local"),
        )
        conn.commit()
    finally:
        conn.close()
    return token, expires.isoformat()


def session_user(token: str) -> Optional[str]:
    """The account id a live session token belongs to, or ``None`` if the token
    is unknown or expired. Expired rows are pruned on the way out."""
    if not token:
        return None
    _ensure_sessions_table()
    th = _hash_token(token)
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"SELECT expires_at, user_id FROM sessions WHERE token_hash = {ph}", (th,))
        row = cur.fetchone()
        if not row:
            return None
        try:
            expires = datetime.fromisoformat(str(row[0]))
        except ValueError:
            return None
        if expires <= _now():
            cur.execute(f"DELETE FROM sessions WHERE token_hash = {ph}", (th,))
            conn.commit()
            return None
        try:
            cur.execute(
                f"UPDATE sessions SET last_seen_at = {ph} WHERE token_hash = {ph}",
                (_now().isoformat(), th),
            )
            conn.commit()
        except Exception:
            pass
        return str(row[1] or "local")
    finally:
        conn.close()


def validate_token(token: str) -> bool:
    if not token:
        return False
    _ensure_sessions_table()
    th = _hash_token(token)
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"SELECT expires_at FROM sessions WHERE token_hash = {ph}", (th,))
        row = cur.fetchone()
        if not row:
            return False
        try:
            expires = datetime.fromisoformat(str(row[0]))
        except ValueError:
            return False
        if expires <= _now():
            cur.execute(f"DELETE FROM sessions WHERE token_hash = {ph}", (th,))
            conn.commit()
            return False
        # best-effort last-seen touch
        try:
            cur.execute(
                f"UPDATE sessions SET last_seen_at = {ph} WHERE token_hash = {ph}",
                (_now().isoformat(), th),
            )
            conn.commit()
        except Exception:
            pass
        return True
    finally:
        conn.close()


def revoke_token(token: str) -> None:
    if not token:
        return
    _ensure_sessions_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"DELETE FROM sessions WHERE token_hash = {ph}", (_hash_token(token),))
        conn.commit()
    finally:
        conn.close()


def revoke_all_sessions() -> int:
    _ensure_sessions_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions")
        n = cur.rowcount or 0
        conn.commit()
        return n
    finally:
        conn.close()


def purge_expired() -> int:
    _ensure_sessions_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"DELETE FROM sessions WHERE expires_at <= {ph}", (_now().isoformat(),))
        n = cur.rowcount or 0
        conn.commit()
        return n
    finally:
        conn.close()


# --- rate limiting --------------------------------------------------

def _max_attempts() -> int:
    return _int_env("TL_AUTH_MAX_ATTEMPTS", 5)


def _lockout_seconds() -> int:
    return _int_env("TL_AUTH_LOCKOUT_MINUTES", 15) * 60


def rate_limited_for(ip: str) -> Optional[int]:
    """Seconds the caller must wait, or None if they may attempt a login."""
    win = _lockout_seconds()
    now = time.time()
    with _attempts_lock:
        hits = [t for t in _attempts.get(ip, []) if now - t < win]
        _attempts[ip] = hits
        if len(hits) >= _max_attempts():
            return int(win - (now - hits[0])) + 1
    return None


def record_login_failure(ip: str) -> None:
    with _attempts_lock:
        _attempts.setdefault(ip, []).append(time.time())


def record_login_success(ip: str) -> None:
    with _attempts_lock:
        _attempts.pop(ip, None)


# --- CLI: generate a hash for the env var --------------------------

if __name__ == "__main__":  # pragma: no cover
    import getpass

    pw1 = getpass.getpass("New API passphrase: ")
    pw2 = getpass.getpass("Confirm: ")
    if pw1 != pw2:
        raise SystemExit("passphrases do not match")
    if len(pw1) < 10:
        raise SystemExit("use at least 10 characters")
    print("\nAdd this to the server environment (.env):\n")
    print(f'TL_AUTH_PASSWORD_HASH={hash_password(pw1)}')
