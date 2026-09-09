# -*- coding: utf-8 -*-
"""
W8.1 — multi-user identity (Supabase Auth).

Covers the stdlib HS256 verifier, invite-only provisioning, and the dual-mode
``/api/*`` gate. Still no order path — identity only decides *whose* journal
rows a request may touch.
"""
import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import database
from api import identity
from api.main import app

FAKE_JWT_SECRET = "fake-fixture-jwt-secret"
OWNER = "owner@example.com"
FRIEND = "friend@example.com"
STRANGER = "stranger@example.com"


def _seg(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def _mint(claims: dict, *, secret: str = FAKE_JWT_SECRET, alg: str = "HS256") -> str:
    header = _seg({"alg": alg, "typ": "JWT"})
    payload = _seg(claims)
    sig = hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"


def _claims(sub: str, email: str, **over) -> dict:
    base = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": int(time.time()) - 10,
        "exp": int(time.time()) + 3600,
    }
    base.update(over)
    return base


@pytest.fixture()
def supa_env(monkeypatch):
    monkeypatch.setenv("TL_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", FAKE_JWT_SECRET)
    monkeypatch.setenv("TL_OWNER_EMAIL", OWNER)
    monkeypatch.setenv("TL_SIGNUP_ALLOWLIST", f"{FRIEND}, {OWNER}")
    monkeypatch.delenv("TL_AUTH_DISABLED", raising=False)
    identity._provision_cache.clear(); identity._deny_cache.clear()
    _wipe_users()
    yield
    identity._provision_cache.clear(); identity._deny_cache.clear()
    _wipe_users()


def _wipe_users():
    identity.ensure_users_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE email LIKE '%@example.com'")
        conn.commit()
    finally:
        conn.close()


# --- token verification -------------------------------------------------

def test_decode_valid_token(supa_env):
    claims = identity.decode_token(_mint(_claims("u-1", FRIEND)))
    assert claims["sub"] == "u-1"
    assert claims["email"] == FRIEND


def test_decode_rejects_bad_signature(supa_env):
    tok = _mint(_claims("u-1", FRIEND), secret="not-the-secret")
    with pytest.raises(identity.InvalidToken):
        identity.decode_token(tok)


def test_decode_rejects_expired(supa_env):
    tok = _mint(_claims("u-1", FRIEND, exp=int(time.time()) - 120))
    with pytest.raises(identity.InvalidToken):
        identity.decode_token(tok)


def test_decode_rejects_wrong_alg(supa_env):
    tok = _mint(_claims("u-1", FRIEND), alg="none")
    with pytest.raises(identity.InvalidToken):
        identity.decode_token(tok)


def test_decode_rejects_wrong_audience(supa_env):
    tok = _mint(_claims("u-1", FRIEND, aud="anon"))
    with pytest.raises(identity.InvalidToken):
        identity.decode_token(tok)


def test_decode_rejects_garbage(supa_env):
    with pytest.raises(identity.InvalidToken):
        identity.decode_token("not-a-jwt")


# --- provisioning -----------------------------------------------------

def test_provision_creates_member(supa_env):
    user = identity.provision_user(_claims("u-friend", FRIEND))
    assert user["role"] == "member"
    assert user["status"] == "active"
    assert identity.get_user("u-friend")["email"] == FRIEND


def test_provision_owner_gets_owner_role(supa_env):
    user = identity.provision_user(_claims("u-owner", OWNER))
    assert user["role"] == "owner"


def test_provision_rejects_uninvited(supa_env):
    with pytest.raises(identity.NotAllowed):
        identity.provision_user(_claims("u-x", STRANGER))
    assert identity.get_user("u-x") is None


def test_provision_rejects_disabled_account(supa_env):
    identity.provision_user(_claims("u-friend", FRIEND))
    identity.set_user_status("u-friend", "disabled")
    with pytest.raises(identity.NotAllowed):
        identity.provision_user(_claims("u-friend", FRIEND))


def test_provision_fails_closed_without_allowlist(monkeypatch, supa_env):
    monkeypatch.delenv("TL_SIGNUP_ALLOWLIST", raising=False)
    monkeypatch.delenv("TL_OWNER_EMAIL", raising=False)
    with pytest.raises(identity.NotAllowed):
        identity.provision_user(_claims("u-any", FRIEND))


def test_provision_is_idempotent_and_refreshes(supa_env):
    identity.provision_user(_claims("u-friend", FRIEND))
    again = identity.provision_user(_claims("u-friend", FRIEND, user_metadata={"full_name": "Fry"}))
    assert again["display_name"] == "Fry"
    assert len([u for u in identity.list_users() if u["id"] == "u-friend"]) == 1


# --- the /api/* gate --------------------------------------------------

def test_gate_blocks_without_token(supa_env):
    c = TestClient(app)
    assert c.get("/api/watchlist").status_code == 401


def test_gate_allows_invited_token_and_sets_user(supa_env):
    c = TestClient(app)
    tok = _mint(_claims("u-friend", FRIEND))
    r = c.get("/api/watchlist", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["authenticated"] is True
    assert me["user"]["email"] == FRIEND
    assert me["user"]["role"] == "member"


def test_gate_rejects_uninvited_token_with_reason(supa_env):
    c = TestClient(app)
    tok = _mint(_claims("u-str", STRANGER))
    assert c.get("/api/watchlist", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["authenticated"] is False
    assert "not invited" in (me["error"] or "").lower() or "not granted" in (me["error"] or "").lower()


def test_health_and_status_exempt_in_supabase_mode(supa_env):
    c = TestClient(app)
    assert c.get("/api/health").status_code == 200
    s = c.get("/api/auth/status").json()
    assert s["mode"] == "supabase"
    assert s["auth_required"] is True
    assert s["authenticated"] is False


def test_gate_503_when_supabase_mode_misconfigured(monkeypatch, supa_env):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    c = TestClient(app)
    assert c.get("/api/health").status_code == 200          # exempt still works
    assert c.get("/api/watchlist").status_code == 503        # fail closed


def test_login_endpoint_refused_in_supabase_mode(supa_env):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"password": "whatever"})
    assert r.status_code == 400
    assert "supabase" in r.json()["error"].lower()


def test_passphrase_mode_untouched(monkeypatch):
    monkeypatch.delenv("TL_AUTH_MODE", raising=False)
    monkeypatch.delenv("TL_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("TL_AUTH_PASSWORD_HASH", raising=False)
    c = TestClient(app)
    assert c.get("/api/watchlist").status_code == 200
    assert c.get("/api/auth/status").json()["mode"] == "passphrase"


def test_current_user_id_defaults_to_local(monkeypatch):
    monkeypatch.delenv("TL_AUTH_MODE", raising=False)

    class _Req:
        class state:  # noqa: N801
            pass

    assert identity.current_user_id(_Req()) == identity.LOCAL_USER_ID
