# -*- coding: utf-8 -*-
"""
W10 — native email + password multi-user auth.

Identity is first-party now: sign-up / sign-in against the ``users`` table
(scrypt hashes), an opaque session token in an httpOnly cookie, invite-only
via ``TL_SIGNUP_ALLOWLIST``. No external provider, no JWT.

Still read-only downstream — identity only decides whose rows a request
touches. These tests prove the gate, the invite check, the owner role, the
disable path, and per-account isolation.
"""
import pytest
from fastapi.testclient import TestClient

import database
import tenant
from api import auth as api_auth
from api import identity
from api.main import app

OWNER = "owner@example.com"
FRIEND = "friend@example.com"
STRANGER = "stranger@example.com"
PW = "correct-horse-battery"


@pytest.fixture()
def mu(monkeypatch):
    monkeypatch.setenv("TL_AUTH_MODE", "multiuser")
    monkeypatch.setenv("TL_OWNER_EMAIL", OWNER)
    monkeypatch.setenv("TL_SIGNUP_ALLOWLIST", f"{OWNER}, {FRIEND}")
    monkeypatch.setenv("TL_AUTH_COOKIE_SECURE", "0")  # TestClient talks http
    monkeypatch.delenv("TL_AUTH_DISABLED", raising=False)
    identity.ensure_users_table()
    api_auth._ensure_sessions_table()
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email LIKE '%@example.com'")
    cur.execute("DELETE FROM sessions WHERE label LIKE '%example%' OR user_id != 'local'")
    for t in ("closed_trades", "journal_entries"):
        cur.execute(f"DELETE FROM {t} WHERE user_id LIKE 'u_%' OR user_id LIKE '%-%'")
    conn.commit()
    conn.close()
    identity._provision_cache.clear()
    identity._deny_cache.clear()
    yield
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email LIKE '%@example.com'")
    conn.commit()
    conn.close()


def _signup(c, email, password=PW):
    return c.post("/api/auth/signup", json={"email": email, "password": password})


# --- identity layer -------------------------------------------------

def test_create_account_sets_owner_role(mu):
    u = identity.create_account(OWNER, PW)
    assert u["role"] == "owner" and u["status"] == "active"
    assert identity.create_account(FRIEND, PW)["role"] == "member"


def test_create_account_rejects_uninvited(mu):
    with pytest.raises(identity.NotAllowed):
        identity.create_account(STRANGER, PW)


def test_create_account_rejects_duplicate(mu):
    identity.create_account(FRIEND, PW)
    with pytest.raises(identity.EmailTaken):
        identity.create_account(FRIEND, "another-password")


def test_create_account_rejects_weak_password(mu):
    with pytest.raises(ValueError):
        identity.create_account(FRIEND, "short")


def test_verify_credentials(mu):
    identity.create_account(FRIEND, PW)
    assert identity.verify_credentials(FRIEND, PW)["email"] == FRIEND
    assert identity.verify_credentials("FRIEND@EXAMPLE.COM", PW)["email"] == FRIEND
    with pytest.raises(identity.BadCredentials):
        identity.verify_credentials(FRIEND, "wrong")
    with pytest.raises(identity.BadCredentials):
        identity.verify_credentials("nobody@example.com", PW)


def test_disabled_account_is_refused(mu):
    u = identity.create_account(FRIEND, PW)
    identity.set_user_status(u["id"], "disabled")
    with pytest.raises(identity.NotAllowed):
        identity.verify_credentials(FRIEND, PW)


# --- HTTP gate -----------------------------------------------------

def test_signup_logs_in_and_unlocks(mu):
    c = TestClient(app)
    assert c.get("/api/watchlist").status_code == 401
    r = _signup(c, OWNER)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["token"] and body["user"]["role"] == "owner"
    # the session cookie now rides along
    assert c.get("/api/watchlist").status_code == 200
    assert c.get("/api/auth/me").json()["user"]["email"] == OWNER


def test_uninvited_signup_is_403(mu):
    c = TestClient(app)
    r = _signup(c, STRANGER)
    assert r.status_code == 403
    assert "invite" in r.json()["error"].lower()
    assert c.get("/api/watchlist").status_code == 401


def test_login_flow_and_bad_password(mu):
    identity.create_account(FRIEND, PW)
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": FRIEND, "password": "nope"}).status_code == 401
    r = c.post("/api/auth/login", json={"email": FRIEND, "password": PW})
    assert r.status_code == 200 and r.json()["token"]
    assert c.get("/api/watchlist").status_code == 200
    c.post("/api/auth/logout")
    assert c.get("/api/watchlist").status_code == 401


def test_bearer_token_is_accepted(mu):
    c = TestClient(app)
    tok = _signup(c, FRIEND).json()["token"]
    fresh = TestClient(app)  # no cookies
    h = {"Authorization": f"Bearer {tok}"}
    assert fresh.get("/api/auth/me", headers=h).json()["user"]["email"] == FRIEND
    assert fresh.get("/api/watchlist", headers=h).status_code == 200


def test_disable_locks_out_within_the_session(mu):
    c = TestClient(app)
    owner_tok = _signup(c, OWNER).json()["token"]
    fc = TestClient(app)
    friend = _signup(fc, FRIEND).json()["user"]
    assert fc.get("/api/watchlist").status_code == 200

    r = c.post(f"/api/admin/users/{friend['id']}/disable")
    assert r.status_code == 200
    assert fc.get("/api/watchlist").status_code == 401           # session no longer resolves
    c.post(f"/api/admin/users/{friend['id']}/enable")
    assert fc.get("/api/watchlist").status_code == 200


def test_two_accounts_are_isolated(mu):
    ac = TestClient(app)
    alice = _signup(ac, OWNER).json()["user"]
    bc = TestClient(app)
    _signup(bc, FRIEND)

    with tenant.use(alice["id"]):
        database.save_closed_trades([dict(
            trade_id="a-1", account_id="ACC", symbol="XAUUSD", direction="LONG",
            volume=1.0, entry_price=2000.0, exit_price=2010.0, commission=0.0, swap=0.0,
            gross_profit=10.0, net_profit=10.0, entry_time="2026-01-01T00:00:00",
            exit_time="2026-01-02T00:00:00", duration_minutes=60.0, setup_tag=None)])
    database.invalidate_db_cache()

    a_perf = ac.get("/api/analytics/performance").json()
    b_perf = bc.get("/api/analytics/performance").json()
    assert a_perf["matched_trades"] >= 1
    assert b_perf["matched_trades"] == 0

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM closed_trades WHERE trade_id = 'a-1'")
    conn.commit()
    conn.close()


def test_status_reports_multiuser(mu):
    c = TestClient(app)
    s = c.get("/api/auth/status").json()
    assert s["mode"] == "multiuser" and s["auth_required"] is True and s["authenticated"] is False
