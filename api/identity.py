# -*- coding: utf-8 -*-
"""
Multi-user identity (platform plan W8.1).

Supabase Auth is the identity provider. The frontend signs a user in with
``@supabase/supabase-js`` and sends the access token as an
``Authorization: Bearer`` header. This module verifies that token against the
project's JWT secret (HS256, **stdlib only** — no new dependency, same spirit as
``api/auth.py`` hand-rolling scrypt) and provisions a local ``users`` row the
first time an allow-listed email is seen.

Two auth modes, selected by ``TL_AUTH_MODE``:

* ``passphrase`` (default) — the single-user W3 flow in ``api/auth.py`` is
  unchanged. ``current_user_id()`` returns the fixed local id so the
  per-user data layer (W8.4) has something to scope to.
* ``supabase`` — every ``/api/*`` route (bar the exempt set) needs a valid
  Supabase JWT whose email is on ``TL_SIGNUP_ALLOWLIST`` (or is
  ``TL_OWNER_EMAIL``). Anyone else gets 403 even with a valid Supabase
  session — sign-up is invite-only for a handful of friends.

Still no order path. Identity only decides *whose* journal rows a request may
read and write. The frozen research/execution layer and macro data stay global
and read-only for everyone.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import database
from api import auth as _auth

# The user id every row is stamped with when the server runs in single-user
# ``passphrase`` mode (local dev, the test suite, the current live deploy).
# W8.4 backfills existing rows to this id, so switching a box to ``supabase``
# mode later means re-owning those rows to a real account, not losing them.
LOCAL_USER_ID = "local"

_users_ready = False
_users_lock = threading.Lock()

# The JWT is re-verified (cheap, stdlib HMAC) on every request, but the
# provisioning round-trip to the DB — the "upsert + touch last_seen" — is
# throttled per user so a polling client does not write a row every second.
# A disabled account therefore takes up to _PROVISION_TTL_SEC to lock out.
_PROVISION_TTL_SEC = 60
_provision_cache: Dict[str, tuple] = {}   # user_id -> (user_dict, monotonic_ts)
_provision_cache_lock = threading.Lock()

# A valid Supabase token whose email is not invited is refused every request.
# Cache that "no" briefly so a client retrying in a loop doesn't re-hit the
# allowlist + DB each time (cheap DoS guard for the invite-only surface).
_DENY_TTL_SEC = 30
_deny_cache: Dict[str, tuple] = {}        # user_id -> (reason, monotonic_ts)


class InvalidToken(Exception):
    """The bearer token is missing, malformed, expired or wrongly signed."""


class NotAllowed(Exception):
    """A valid user whose email is not invited, or whose account is disabled."""


class EmailTaken(Exception):
    """Sign-up for an email that already has an account."""


class BadCredentials(Exception):
    """Wrong email / password at native sign-in."""


class InvalidResetToken(Exception):
    """A password-reset token that is missing, unknown, expired, or used up."""


# --- env ------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def auth_mode() -> str:
    """``passphrase`` (default, single-user W3), ``multiuser`` (native
    email+password, W10), or ``supabase`` (external JWT, W8 — kept but no
    longer the recommended path)."""
    v = _env("TL_AUTH_MODE", "passphrase").lower()
    return v if v in ("supabase", "multiuser") else "passphrase"


def native_enabled() -> bool:
    return auth_mode() == "multiuser"


def _jwt_secret() -> str:
    return _env("SUPABASE_JWT_SECRET")


def supabase_url() -> str:
    """The project URL, e.g. ``https://abc.supabase.co`` (no trailing slash).

    Used to discover the JWKS endpoint for the asymmetric (ES256/RS256)
    signing keys and to pin the token issuer. Optional — if unset, the
    issuer claim on a verified token is used for key discovery instead.
    """
    return _env("SUPABASE_URL").rstrip("/")


def supabase_enabled() -> bool:
    # Either signing scheme is enough to run: the legacy shared secret
    # (HS256) or the project URL for the asymmetric keys (ES256/RS256).
    return auth_mode() == "supabase" and bool(_jwt_secret() or supabase_url())


def owner_email() -> str:
    return _env("TL_OWNER_EMAIL").lower()


def signup_allowlist() -> set[str]:
    """Lower-cased invited emails. ``TL_OWNER_EMAIL`` is always included."""
    raw = _env("TL_SIGNUP_ALLOWLIST")
    emails = {e.strip().lower() for e in raw.split(",") if e.strip()}
    owner = owner_email()
    if owner:
        emails.add(owner)
    return emails


def signup_open() -> bool:
    """The "grand opening" switch — ``TL_SIGNUP_OPEN=1`` lets anyone create an
    account, bypassing ``TL_SIGNUP_ALLOWLIST`` entirely. Off by default: an
    unset/blank/"0" value keeps sign-up invite-only, same as before this
    existed. When this is on, ``create_account``'s per-IP cap below is the
    only thing standing between "free trial" and "one person, unlimited
    accounts" — the allowlist itself no longer does that job."""
    return _env("TL_SIGNUP_OPEN", "0").lower() in ("1", "true", "yes")


def max_users() -> int:
    """Capacity ceiling for open registration -- ``TL_MAX_USERS`` active
    accounts in total. 0 / unset / junk means no ceiling. Only open sign-up is
    capped: the owner and anyone on the invite list can always get in, so a
    full server never locks out the people it was opened for first."""
    try:
        return max(0, int(_env("TL_MAX_USERS", "0")))
    except ValueError:
        return 0


# --- per-IP signup cap (in-process, open-registration only) -------------
#
# auth.rate_limited_for() (shared with login) is the wrong tool for this: it
# only counts *failed* attempts and a success wipes it clean (right for
# "stop someone guessing a password", wrong for "stop someone minting
# accounts" -- a success is exactly the thing to cap there). This is a
# separate, deliberately simple counter of successful signups per IP. Same
# limitation as auth.py's limiter: in-process, so it resets on deploy and
# doesn't share state across multiple instances -- fine for a single Render
# web service, not a substitute for real abuse tooling if this ever needs
# to scale past that.
_signup_ips: Dict[str, list] = {}
_signup_ips_lock = threading.Lock()


def _signup_max_per_ip() -> int:
    try:
        return int(_env("TL_SIGNUP_MAX_PER_IP", "2"))
    except ValueError:
        return 2


def _signup_window_seconds() -> int:
    try:
        return int(_env("TL_SIGNUP_WINDOW_HOURS", "24")) * 3600
    except ValueError:
        return 24 * 3600


def signup_rate_limited_for(ip: str) -> Optional[int]:
    """Seconds the caller must wait, or None if this IP may create another
    account right now."""
    if not ip:
        return None
    win = _signup_window_seconds()
    now = time.time()
    with _signup_ips_lock:
        hits = [t for t in _signup_ips.get(ip, []) if now - t < win]
        _signup_ips[ip] = hits
        if len(hits) >= _signup_max_per_ip():
            return int(win - (now - hits[0])) + 1
    return None


def record_signup(ip: str) -> None:
    if not ip:
        return
    with _signup_ips_lock:
        _signup_ips.setdefault(ip, []).append(time.time())


# --- JWT verification --------------------------------------------------
#
# Supabase issues access tokens under one of two signing schemes:
#   * HS256 — the legacy project "JWT secret" (a shared symmetric key). Verified
#     with stdlib HMAC, no network call.
#   * ES256 / RS256 — the newer asymmetric signing keys. The public half is
#     published at ``<project>/auth/v1/.well-known/jwks.json``; we fetch and
#     cache it and verify with ``cryptography`` (already a dependency).
# Both are accepted so a project on either scheme just works.

_JWKS_TTL_SEC = 600
_jwks_cache: Dict[str, tuple] = {}       # jwks_url -> ({kid: jwk}, monotonic_ts)
_jwks_lock = threading.Lock()
_ASYM_ALGS = {"ES256", "RS256"}


def _b64url_decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def _b64url_uint(segment: str) -> int:
    return int.from_bytes(_b64url_decode(segment), "big")


def _jwks_url(issuer: str) -> str:
    base = supabase_url() or (issuer or "").rstrip("/")
    if not base:
        raise InvalidToken("no issuer / SUPABASE_URL for signing-key discovery")
    if base.endswith("/auth/v1"):
        return f"{base}/.well-known/jwks.json"
    return f"{base}/auth/v1/.well-known/jwks.json"


def _fetch_jwks(url: str, *, force: bool = False) -> Dict[str, dict]:
    now = time.monotonic()
    if not force:
        with _jwks_lock:
            hit = _jwks_cache.get(url)
            if hit and now - hit[1] < _JWKS_TTL_SEC:
                return hit[0]
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - https project URL
            doc = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - network/parse
        with _jwks_lock:
            hit = _jwks_cache.get(url)
        if hit:
            return hit[0]      # serve stale rather than lock everyone out
        raise InvalidToken(f"could not fetch signing keys: {exc}") from exc
    keys = {k["kid"]: k for k in doc.get("keys", []) if k.get("kid")}
    with _jwks_lock:
        _jwks_cache[url] = (keys, now)
    return keys


def _public_key_from_jwk(jwk: Dict[str, Any]):
    from cryptography.hazmat.primitives.asymmetric import ec, rsa

    kty = jwk.get("kty")
    if kty == "EC":
        if jwk.get("crv") != "P-256":
            raise InvalidToken(f"unsupported EC curve {jwk.get('crv')!r}")
        return ec.EllipticCurvePublicNumbers(
            _b64url_uint(jwk["x"]), _b64url_uint(jwk["y"]), ec.SECP256R1()
        ).public_key()
    if kty == "RSA":
        return rsa.RSAPublicNumbers(
            _b64url_uint(jwk["e"]), _b64url_uint(jwk["n"])
        ).public_key()
    raise InvalidToken(f"unsupported key type {kty!r}")


def _verify_asymmetric(
    signing_input: bytes, signature: bytes, alg: str, kid: str, issuer: str
) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding
    from cryptography.hazmat.primitives.asymmetric import utils as asym_utils

    if not kid:
        raise InvalidToken("token header has no kid")
    pinned = supabase_url()
    if pinned and issuer and not issuer.rstrip("/").startswith(pinned):
        raise InvalidToken("token issuer does not match SUPABASE_URL")

    url = _jwks_url(issuer)
    jwk = _fetch_jwks(url).get(kid) or _fetch_jwks(url, force=True).get(kid)
    if jwk is None:
        raise InvalidToken(f"no signing key for kid {kid!r}")

    pub = _public_key_from_jwk(jwk)
    try:
        if alg == "ES256":
            if len(signature) != 64:
                raise InvalidToken("malformed ES256 signature")
            der = asym_utils.encode_dss_signature(
                int.from_bytes(signature[:32], "big"),
                int.from_bytes(signature[32:], "big"),
            )
            pub.verify(der, signing_input, ec.ECDSA(hashes.SHA256()))
        elif alg == "RS256":
            pub.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        else:  # pragma: no cover - guarded by caller
            raise InvalidToken(f"unsupported alg {alg!r}")
    except InvalidSignature as exc:
        raise InvalidToken("bad signature") from exc
    except (ValueError, TypeError) as exc:
        raise InvalidToken(f"signature check failed: {exc}") from exc


def decode_token(token: str, *, leeway: int = 30) -> Dict[str, Any]:
    """Verify a Supabase access token (HS256 or ES256/RS256) and return its
    claims. Raises :class:`InvalidToken` on any problem."""
    if not token or token.count(".") != 2:
        raise InvalidToken("not a JWT")

    header_b64, payload_b64, sig_b64 = token.split(".")
    try:
        header = json.loads(_b64url_decode(header_b64))
        claims = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(sig_b64)
    except Exception as exc:  # noqa: BLE001
        raise InvalidToken(f"malformed JWT: {exc}") from exc

    alg = header.get("alg")
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    if alg == "HS256":
        secret = _jwt_secret()
        if not secret:
            raise InvalidToken("SUPABASE_JWT_SECRET is not configured")
        expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, signature):
            raise InvalidToken("bad signature")
    elif alg in _ASYM_ALGS:
        _verify_asymmetric(signing_input, signature, alg, header.get("kid", ""),
                           str(claims.get("iss") or ""))
    else:
        raise InvalidToken(f"unsupported alg {alg!r}")

    now = time.time()
    exp = claims.get("exp")
    if exp is not None and float(exp) < now - leeway:
        raise InvalidToken("expired")
    nbf = claims.get("nbf")
    if nbf is not None and float(nbf) > now + leeway:
        raise InvalidToken("not yet valid")

    aud = claims.get("aud")
    auds = aud if isinstance(aud, list) else [aud] if aud else []
    if auds and "authenticated" not in auds:
        raise InvalidToken(f"unexpected audience {aud!r}")

    if not claims.get("sub"):
        raise InvalidToken("no subject")
    return claims


# --- users table -------------------------------------------------------

def _ph(conn) -> str:
    return "%s" if database.is_postgres() else "?"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_users_table() -> None:
    global _users_ready
    if _users_ready:
        return
    with _users_lock:
        if _users_ready:
            return
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    role TEXT NOT NULL DEFAULT 'member',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    password_hash TEXT
                )
                """
            )
            # native email+password (W10): existing W8 tables gain the column
            try:
                cur.execute(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT"
                    if database.is_postgres()
                    else "ALTER TABLE users ADD COLUMN password_hash TEXT"
                )
            except Exception:
                conn.rollback()
            conn.commit()
            _users_ready = True
        finally:
            conn.close()


def _row_to_user(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "email": row[1],
        "display_name": row[2],
        "role": row[3],
        "status": row[4],
        "created_at": row[5],
        "last_seen_at": row[6],
    }


_USER_COLS = "id, email, display_name, role, status, created_at, last_seen_at"


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    if not user_id:
        return None
    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {_USER_COLS} FROM users WHERE id = {_ph(conn)}", (user_id,))
        row = cur.fetchone()
        return _row_to_user(row) if row else None
    finally:
        conn.close()


def list_users() -> List[Dict[str, Any]]:
    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {_USER_COLS} FROM users ORDER BY created_at")
        return [_row_to_user(r) for r in cur.fetchall()]
    finally:
        conn.close()


def set_user_status(user_id: str, status: str) -> None:
    if status not in ("active", "disabled"):
        raise ValueError("status must be 'active' or 'disabled'")
    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"UPDATE users SET status = {ph} WHERE id = {ph}", (status, user_id))
        conn.commit()
    finally:
        conn.close()
    _forget(user_id)


def provision_user(claims: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert the local ``users`` row for a verified Supabase identity.

    Raises :class:`NotAllowed` if the email is not invited or the account has
    been disabled.
    """
    uid = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().lower()
    if not uid or not email:
        raise NotAllowed("token has no email")

    allow = signup_allowlist()
    if not allow:
        # Fail closed: with no allowlist and no owner configured nobody is in.
        raise NotAllowed("sign-up is not open on this server")
    if email not in allow:
        raise NotAllowed(f"{email} is not invited")

    meta = claims.get("user_metadata") or {}
    display = str(meta.get("full_name") or meta.get("name") or "").strip() or None
    role = "owner" if email == owner_email() else "member"
    now = _now_iso()

    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"SELECT {_USER_COLS} FROM users WHERE id = {ph}", (uid,))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                f"INSERT INTO users (id, email, display_name, role, status, created_at, last_seen_at) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, 'active', {ph}, {ph})",
                (uid, email, display, role, now, now),
            )
            conn.commit()
            return {
                "id": uid, "email": email, "display_name": display,
                "role": role, "status": "active", "created_at": now, "last_seen_at": now,
            }
        user = _row_to_user(row)
        if user["status"] == "disabled":
            raise NotAllowed("account disabled")
        # Keep email / display name fresh; never downgrade an existing role.
        cur.execute(
            f"UPDATE users SET email = {ph}, display_name = COALESCE({ph}, display_name), "
            f"last_seen_at = {ph} WHERE id = {ph}",
            (email, display, now, uid),
        )
        conn.commit()
        user["email"] = email
        user["last_seen_at"] = now
        if display:
            user["display_name"] = display
        return user
    finally:
        conn.close()


# --- native email + password (W10) -----------------------------------

def _norm_email(email: str) -> str:
    return str(email or "").strip().lower()


def create_account(email: str, password: str, display_name: str = "", ip: str = "") -> Dict[str, Any]:
    """Register a new local account.

    Invite-only by default: the email must be on ``TL_SIGNUP_ALLOWLIST`` (or
    be ``TL_OWNER_EMAIL``). With ``TL_SIGNUP_OPEN=1`` the allowlist is
    bypassed for anyone — ``ip`` (the caller's address, for the per-IP cap
    below) matters only in that mode; pass it whenever the route has one.

    Raises :class:`NotAllowed` (not invited, open-mode rate limit, or the
    ``TL_MAX_USERS`` ceiling reached),
    :class:`EmailTaken`, or ``ValueError`` (weak input).
    """
    email = _norm_email(email)
    if "@" not in email or len(email) > 254:
        raise ValueError("enter a valid email address")
    if len(password or "") < 8:
        raise ValueError("password must be at least 8 characters")

    open_signup = signup_open()
    if not open_signup:
        allow = signup_allowlist()
        if not allow:
            raise NotAllowed("sign-up is not open on this server")
        if email not in allow:
            raise NotAllowed(f"{email} is not on the invite list")
    elif ip:
        # Open registration has no invite gate, so this per-IP cap is the
        # actual abuse guard now -- see signup_rate_limited_for()'s docstring.
        wait = signup_rate_limited_for(ip)
        if wait is not None:
            raise NotAllowed(f"Too many accounts created from this network recently — try again in {wait // 60 + 1} min.")

    ensure_users_table()
    now = _now_iso()
    role = "owner" if email == owner_email() else "member"
    uid = uuid.uuid4().hex
    pw_hash = _auth.hash_password(password)
    display = (display_name or "").strip()[:120] or None

    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"SELECT id FROM users WHERE lower(email) = {ph}", (email,))
        if cur.fetchone():
            raise EmailTaken(email)
        cap = max_users()
        if open_signup and cap and email not in signup_allowlist():
            cur.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
            if int(cur.fetchone()[0]) >= cap:
                raise NotAllowed("TradeLogger is full right now — new sign-ups are paused. Please check back soon.")
        cur.execute(
            f"INSERT INTO users (id, email, display_name, role, status, created_at, last_seen_at, password_hash) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, 'active', {ph}, {ph}, {ph})",
            (uid, email, display, role, now, now, pw_hash),
        )
        conn.commit()
    finally:
        conn.close()
    if open_signup and ip:
        record_signup(ip)
    return {
        "id": uid, "email": email, "display_name": display, "role": role,
        "status": "active", "created_at": now, "last_seen_at": now,
    }


def verify_credentials(email: str, password: str) -> Dict[str, Any]:
    """Return the account for a correct email + password.

    Raises :class:`BadCredentials` (unknown email or wrong password) or
    :class:`NotAllowed` (account disabled).
    """
    email = _norm_email(email)
    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"SELECT {_USER_COLS}, password_hash FROM users WHERE lower(email) = {ph}",
            (email,),
        )
        row = cur.fetchone()
        if not row or not row[-1]:
            raise BadCredentials("invalid email or password")
        user = _row_to_user(row[:-1])
        if not _auth.verify_hash(password, str(row[-1])):
            raise BadCredentials("invalid email or password")
        if user["status"] == "disabled":
            raise NotAllowed("this account has been disabled")
        now = _now_iso()
        cur.execute(f"UPDATE users SET last_seen_at = {ph} WHERE id = {ph}", (now, user["id"]))
        conn.commit()
        user["last_seen_at"] = now
        return user
    finally:
        conn.close()


def resolve_session_user(token: str) -> Optional[Dict[str, Any]]:
    """The account a native session cookie/token belongs to, or ``None``.

    ``None`` covers an unknown/expired session and a since-disabled account.
    """
    uid = _auth.session_user(token)
    if not uid or uid == LOCAL_USER_ID:
        return None
    user = get_user(uid)
    if user is None or user.get("status") == "disabled":
        return None
    return user


# --- request-time resolution -----------------------------------------

def resolve_user(token: str) -> Optional[Dict[str, Any]]:
    """Verified + provisioned user for a bearer token, or ``None``.

    ``None`` covers both "no / bad token" and "valid token but not invited" —
    the caller turns that into 401. Use :func:`resolve_user_strict` when the
    distinction matters (the login/status endpoints want to say *why*).
    """
    try:
        return resolve_user_strict(token)
    except (InvalidToken, NotAllowed):
        return None


def resolve_user_strict(token: str) -> Dict[str, Any]:
    claims = decode_token(token)
    uid = str(claims.get("sub") or "")
    now = time.monotonic()
    with _provision_cache_lock:
        hit = _provision_cache.get(uid)
        if hit and now - hit[1] < _PROVISION_TTL_SEC:
            return hit[0]
        deny = _deny_cache.get(uid)
        if deny and now - deny[1] < _DENY_TTL_SEC:
            raise NotAllowed(deny[0])
    try:
        user = provision_user(claims)
    except NotAllowed as exc:
        with _provision_cache_lock:
            _deny_cache[uid] = (str(exc), now)
        raise
    with _provision_cache_lock:
        _provision_cache[uid] = (user, now)
        _deny_cache.pop(uid, None)
    return user


def _forget(user_id: str) -> None:
    with _provision_cache_lock:
        _provision_cache.pop(user_id, None)
        _deny_cache.pop(user_id, None)


# --- password reset (native email + password, W16) ---------------------
#
# Same pattern as the sessions table in api/auth.py: a random token is handed
# to the caller once, only its SHA-256 lives in the DB, and it is single-use
# + short-lived. Separate table (not sessions) because a reset token proves
# "this mailbox", not "this is a live login" — different lifetime, different
# consume-once semantics, and it must survive being requested while the
# account has no valid session at all.

_resets_ready = False
_resets_lock = threading.Lock()

_reset_ips: Dict[str, list] = {}
_reset_ips_lock = threading.Lock()


def _ensure_password_resets_table() -> None:
    global _resets_ready
    if _resets_ready:
        return
    with _resets_lock:
        if _resets_ready:
            return
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS password_resets (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                )
                """
            )
            conn.commit()
            _resets_ready = True
        finally:
            conn.close()


def _reset_ttl_minutes() -> int:
    try:
        return int(_env("TL_PASSWORD_RESET_MINUTES", "30"))
    except ValueError:
        return 30


def _reset_max_per_ip() -> int:
    try:
        return int(_env("TL_PASSWORD_RESET_MAX_PER_IP", "5"))
    except ValueError:
        return 5


def _reset_max_per_email() -> int:
    try:
        return int(_env("TL_PASSWORD_RESET_MAX_PER_EMAIL", "3"))
    except ValueError:
        return 3


def _reset_keys(ip: str, email: str) -> List[Tuple[str, int]]:
    """Per-IP caps one caller; per-email stops a caller rotating IPs from
    flooding one victim's inbox."""
    keys = []
    if ip:
        keys.append((f"ip:{ip}", _reset_max_per_ip()))
    em = _norm_email(email)
    if em:
        keys.append((f"email:{em}", _reset_max_per_email()))
    return keys


def reset_rate_limited_for(ip: str, email: str = "") -> Optional[int]:
    """Seconds before another reset *request* is allowed, or ``None``.
    Deliberately separate from the login limiter (that one counts failures;
    this counts requests regardless of outcome, since every outcome looks the
    same to the caller — see ``request_password_reset``)."""
    win = 3600
    now = time.time()
    wait = None
    with _reset_ips_lock:
        for key, cap in _reset_keys(ip, email):
            hits = [t for t in _reset_ips.get(key, []) if now - t < win]
            _reset_ips[key] = hits
            if len(hits) >= cap:
                w = int(win - (now - hits[0])) + 1
                wait = w if wait is None else max(wait, w)
    return wait


def record_reset_request(ip: str, email: str = "") -> None:
    now = time.time()
    with _reset_ips_lock:
        for key, _cap in _reset_keys(ip, email):
            _reset_ips.setdefault(key, []).append(now)


def request_password_reset(email: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """If ``email`` belongs to an active account, mint a one-time reset token
    and return ``(raw_token, user)``. Returns ``None`` for an unknown email or
    a disabled account — callers MUST respond identically in both cases (no
    account-enumeration via response shape)."""
    email = _norm_email(email)
    if not email:
        return None
    ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(f"SELECT {_USER_COLS} FROM users WHERE lower(email) = {ph}", (email,))
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    user = _row_to_user(row)
    if user["status"] == "disabled":
        return None

    _ensure_password_resets_table()
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=_reset_ttl_minutes())
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"INSERT INTO password_resets (token_hash, user_id, created_at, expires_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph})",
            (token_hash, user["id"], now.isoformat(), expires.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return token, user


def reset_password(token: str, new_password: str) -> Dict[str, Any]:
    """Consume a reset token and set a new password.

    Raises :class:`InvalidResetToken` (unknown / expired / already-used) or
    ``ValueError`` (weak password). Revokes every existing session for the
    account, same as a "change password" should everywhere.
    """
    if not token:
        raise InvalidResetToken("missing token")
    if len(new_password or "") < 8:
        raise ValueError("password must be at least 8 characters")

    _ensure_password_resets_table()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"SELECT user_id, expires_at, used_at FROM password_resets WHERE token_hash = {ph}",
            (token_hash,),
        )
        row = cur.fetchone()
        if not row:
            raise InvalidResetToken("This reset link is invalid. Request a new one.")
        user_id, expires_at, used_at = row
        if used_at:
            raise InvalidResetToken("This reset link has already been used. Request a new one.")
        try:
            expires = datetime.fromisoformat(str(expires_at))
        except ValueError:
            raise InvalidResetToken("This reset link is invalid. Request a new one.")
        if expires <= datetime.now(timezone.utc):
            raise InvalidResetToken("This reset link has expired. Request a new one.")
        cur.execute(f"SELECT status FROM users WHERE id = {ph}", (user_id,))
        status_row = cur.fetchone()
        if not status_row or status_row[0] == "disabled":
            raise InvalidResetToken("This reset link is invalid. Request a new one.")

        now = _now_iso()
        pw_hash = _auth.hash_password(new_password)
        cur.execute(f"UPDATE users SET password_hash = {ph} WHERE id = {ph}", (pw_hash, user_id))
        # Burn every outstanding link for this account, not just this one --
        # otherwise the other links in a "requested it three times" inbox
        # stay live for the rest of their 30 minutes.
        cur.execute(
            f"UPDATE password_resets SET used_at = {ph} WHERE user_id = {ph} AND used_at IS NULL",
            (now, user_id),
        )
        conn.commit()
    finally:
        conn.close()

    user_id = str(user_id)
    _forget(user_id)
    _auth.revoke_user_sessions(user_id)
    user = get_user(user_id)
    if user is None:
        raise InvalidResetToken("That account no longer exists.")
    return user


def current_user_id(request) -> str:
    """The id every per-user row for this request is scoped to.

    ``multiuser`` / ``supabase`` mode: the authenticated account's id (the
    middleware has already put it on ``request.state``). ``passphrase`` /
    auth-disabled mode: the fixed :data:`LOCAL_USER_ID`.
    """
    uid = getattr(getattr(request, "state", None), "user_id", None)
    return uid or LOCAL_USER_ID
