# -*- coding: utf-8 -*-
"""
Open signup (the "grand opening" switch) + the per-IP signup cap that
replaces the invite allowlist as the abuse guard once it's on.

TL_SIGNUP_OPEN=1 bypasses TL_SIGNUP_ALLOWLIST entirely -- anyone can create
an account. That means the allowlist no longer stops one person minting
unlimited accounts, so a separate, deliberately simple per-IP counter
(identity.signup_rate_limited_for / record_signup) takes over that job.
Unlike auth.rate_limited_for() (shared with login, only counts failures,
wiped clean by a success), this one counts successful signups and never
resets on success -- a success is exactly the thing being capped.
"""
import pytest
from fastapi.testclient import TestClient

import database
from api import auth as api_auth
from api import identity
from api.main import app

OWNER = "owner@example.com"
INVITED = "invited@example.com"
STRANGER = "stranger@example.com"
PW = "correct-horse-battery"


@pytest.fixture()
def mu(monkeypatch):
    monkeypatch.setenv("TL_AUTH_MODE", "multiuser")
    monkeypatch.setenv("TL_OWNER_EMAIL", OWNER)
    monkeypatch.setenv("TL_SIGNUP_ALLOWLIST", f"{OWNER}, {INVITED}")
    monkeypatch.delenv("TL_SIGNUP_OPEN", raising=False)
    monkeypatch.delenv("TL_SIGNUP_MAX_PER_IP", raising=False)
    monkeypatch.delenv("TL_SIGNUP_WINDOW_HOURS", raising=False)
    monkeypatch.setenv("TL_AUTH_COOKIE_SECURE", "0")  # TestClient talks http
    monkeypatch.delenv("TL_AUTH_DISABLED", raising=False)
    identity.ensure_users_table()
    api_auth._ensure_sessions_table()
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email LIKE '%@example.com'")
    cur.execute("DELETE FROM sessions WHERE label LIKE '%example%' OR user_id != 'local'")
    conn.commit()
    conn.close()
    identity._provision_cache.clear()
    identity._deny_cache.clear()
    with identity._signup_ips_lock:
        identity._signup_ips.clear()
    yield
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email LIKE '%@example.com'")
    conn.commit()
    conn.close()
    with identity._signup_ips_lock:
        identity._signup_ips.clear()


def _signup(c, email, password=PW):
    return c.post("/api/auth/signup", json={"email": email, "password": password})


# --- identity layer ---------------------------------------------------

def test_signup_open_defaults_off(mu):
    assert identity.signup_open() is False


def test_signup_open_reads_env(mu, monkeypatch):
    monkeypatch.setenv("TL_SIGNUP_OPEN", "1")
    assert identity.signup_open() is True
    monkeypatch.setenv("TL_SIGNUP_OPEN", "0")
    assert identity.signup_open() is False


def test_stranger_still_rejected_when_closed(mu):
    with pytest.raises(identity.NotAllowed):
        identity.create_account(STRANGER, PW, ip="1.2.3.4")


def test_stranger_allowed_when_open(mu, monkeypatch):
    monkeypatch.setenv("TL_SIGNUP_OPEN", "1")
    u = identity.create_account(STRANGER, PW, ip="1.2.3.4")
    assert u["role"] == "member" and u["status"] == "active"


def test_per_ip_cap_kicks_in_after_max(mu, monkeypatch):
    monkeypatch.setenv("TL_SIGNUP_OPEN", "1")
    monkeypatch.setenv("TL_SIGNUP_MAX_PER_IP", "2")
    ip = "9.9.9.9"
    identity.create_account("a@example.com", PW, ip=ip)
    identity.create_account("b@example.com", PW, ip=ip)
    with pytest.raises(identity.NotAllowed, match="Too many accounts"):
        identity.create_account("c@example.com", PW, ip=ip)


def test_per_ip_cap_does_not_leak_across_ips(mu, monkeypatch):
    monkeypatch.setenv("TL_SIGNUP_OPEN", "1")
    monkeypatch.setenv("TL_SIGNUP_MAX_PER_IP", "1")
    identity.create_account("a@example.com", PW, ip="1.1.1.1")
    # a different IP is unaffected by the first one's cap
    u = identity.create_account("b@example.com", PW, ip="2.2.2.2")
    assert u["status"] == "active"


def test_cap_does_not_apply_when_signup_is_closed(mu, monkeypatch):
    # The allowlist is the gate when closed -- the per-IP cap is specifically
    # an open-mode abuse guard, not a general signup throttle.
    monkeypatch.setenv("TL_SIGNUP_MAX_PER_IP", "1")
    ip = "3.3.3.3"
    u1 = identity.create_account(OWNER, PW, ip=ip)
    u2 = identity.create_account(INVITED, PW, ip=ip)
    assert u1["status"] == "active" and u2["status"] == "active"


# --- router layer -------------------------------------------------------

def test_signup_route_rejects_stranger_when_closed(mu):
    c = TestClient(app)
    r = _signup(c, STRANGER)
    assert r.status_code == 403


def test_signup_route_allows_stranger_when_open(mu, monkeypatch):
    monkeypatch.setenv("TL_SIGNUP_OPEN", "1")
    c = TestClient(app)
    r = _signup(c, STRANGER)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["user"]["email"] == STRANGER


def test_status_and_me_report_signup_open(mu, monkeypatch):
    c = TestClient(app)
    assert c.get("/api/auth/status").json()["signup_open"] is False
    assert c.get("/api/auth/me").json()["signup_open"] is False

    monkeypatch.setenv("TL_SIGNUP_OPEN", "1")
    assert c.get("/api/auth/status").json()["signup_open"] is True
    assert c.get("/api/auth/me").json()["signup_open"] is True
