# -*- coding: utf-8 -*-
"""
W8.7 — owner-only admin surface + the deny cache.

The owner can list users and disable / re-enable one. A disabled account is
locked out of every /api/* route within the deny-cache TTL. Nothing here
touches a trading row.
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


def _jwt(sub, email):
    seg = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    h, p = seg({"alg": "HS256", "typ": "JWT"}), seg(
        {"sub": sub, "email": email, "aud": "authenticated",
         "iat": int(time.time()) - 5, "exp": int(time.time()) + 3600})
    sig = hmac.new(FAKE_JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"


@pytest.fixture()
def supa(monkeypatch):
    monkeypatch.setenv("TL_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", FAKE_JWT_SECRET)
    monkeypatch.setenv("TL_OWNER_EMAIL", OWNER)
    monkeypatch.setenv("TL_SIGNUP_ALLOWLIST", f"{OWNER},{FRIEND}")
    monkeypatch.setattr(identity, "_DENY_TTL_SEC", 0)   # don't cache denials across asserts
    identity._provision_cache.clear()
    identity._deny_cache.clear()
    identity.ensure_users_table()
    conn = database.get_connection()
    conn.cursor().execute("DELETE FROM users WHERE email LIKE '%@example.com'")
    conn.commit()
    conn.close()
    yield
    identity._provision_cache.clear()
    identity._deny_cache.clear()


def test_admin_is_owner_only(supa):
    c = TestClient(app)
    oh = {"Authorization": f"Bearer {_jwt('u-owner', OWNER)}"}
    fh = {"Authorization": f"Bearer {_jwt('u-friend', FRIEND)}"}

    assert c.get("/api/watchlist", headers=fh).status_code == 200   # provision friend
    assert c.get("/api/admin/users", headers=fh).status_code == 403
    r = c.get("/api/admin/users", headers=oh)
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()["users"]}
    assert {OWNER, FRIEND} <= emails


def test_owner_cannot_disable_self(supa):
    c = TestClient(app)
    oh = {"Authorization": f"Bearer {_jwt('u-owner', OWNER)}"}
    c.get("/api/watchlist", headers=oh)
    assert c.post("/api/admin/users/u-owner/disable", headers=oh).status_code == 400


def test_disable_then_locked_out(supa):
    c = TestClient(app)
    oh = {"Authorization": f"Bearer {_jwt('u-owner', OWNER)}"}
    fh = {"Authorization": f"Bearer {_jwt('u-friend', FRIEND)}"}

    assert c.get("/api/watchlist", headers=fh).status_code == 200
    identity._provision_cache.clear()

    assert c.post("/api/admin/users/u-friend/disable", headers=oh).status_code == 200
    assert c.get("/api/watchlist", headers=fh).status_code == 401     # locked out

    assert c.post("/api/admin/users/u-friend/enable", headers=oh).status_code == 200
    identity._provision_cache.clear()
    assert c.get("/api/watchlist", headers=fh).status_code == 200     # back in
