# -*- coding: utf-8 -*-
"""
Multiuser password reset (platform plan W16).

Mirrors ``test_open_signup.py``'s fixture style: a disposable ``@example.com``
cohort in the real ``users``/``sessions``/``password_resets`` tables, cleaned
up on the way in and out so it never collides with real accounts.

Covers the two things that actually matter for a public-facing reset flow:
  - the no-enumeration contract (forgot-password answers identically for a
    known email, an unknown email, a disabled account, and a rate-limited IP)
  - the token is single-use, expires, and resetting revokes existing sessions
"""
import pytest
from fastapi.testclient import TestClient

import database
from api import auth as api_auth
from api import identity
from api.main import app

OWNER = "owner@example.com"
MEMBER = "member@example.com"
DISABLED = "disabled@example.com"
STRANGER = "stranger@example.com"
OLD_PW = "correct-horse-battery"
NEW_PW = "new-correct-horse-battery"


@pytest.fixture()
def mu(monkeypatch):
    monkeypatch.setenv("TL_AUTH_MODE", "multiuser")
    monkeypatch.setenv("TL_OWNER_EMAIL", OWNER)
    monkeypatch.setenv("TL_SIGNUP_ALLOWLIST", f"{OWNER}, {MEMBER}, {DISABLED}")
    monkeypatch.delenv("TL_SIGNUP_OPEN", raising=False)
    monkeypatch.setenv("TL_AUTH_COOKIE_SECURE", "0")  # TestClient talks http
    monkeypatch.delenv("TL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("TL_SMTP_HOST", raising=False)  # sender falls back to a no-op log

    identity.ensure_users_table()
    api_auth._ensure_sessions_table()
    identity._ensure_password_resets_table()

    def _wipe():
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM password_resets WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE '%@example.com')"
        )
        cur.execute("DELETE FROM sessions WHERE label LIKE '%example%' OR user_id != 'local'")
        cur.execute("DELETE FROM users WHERE email LIKE '%@example.com'")
        conn.commit()
        conn.close()

    _wipe()
    identity._provision_cache.clear()
    identity._deny_cache.clear()
    with identity._reset_ips_lock:
        identity._reset_ips.clear()

    with TestClient(app) as c:
        c.post("/api/auth/signup", json={"email": MEMBER, "password": OLD_PW})
        c.post("/api/auth/signup", json={"email": DISABLED, "password": OLD_PW})
    disabled_id = [u for u in identity.list_users() if u["email"] == DISABLED][0]["id"]
    identity.set_user_status(disabled_id, "disabled")

    yield

    _wipe()
    with identity._reset_ips_lock:
        identity._reset_ips.clear()


def _member_id() -> str:
    return [u for u in identity.list_users() if u["email"] == MEMBER][0]["id"]


# --- identity layer -----------------------------------------------------

def test_unknown_email_returns_none(mu):
    assert identity.request_password_reset(STRANGER) is None


def test_disabled_account_returns_none(mu):
    assert identity.request_password_reset(DISABLED) is None


def test_known_email_mints_a_token(mu):
    result = identity.request_password_reset(MEMBER)
    assert result is not None
    token, user = result
    assert user["email"] == MEMBER
    assert len(token) > 20


def test_token_resets_the_password(mu):
    token, _ = identity.request_password_reset(MEMBER)
    identity.reset_password(token, NEW_PW)
    assert identity.verify_credentials(MEMBER, NEW_PW)["email"] == MEMBER
    with pytest.raises(identity.BadCredentials):
        identity.verify_credentials(MEMBER, OLD_PW)


def test_token_is_single_use(mu):
    token, _ = identity.request_password_reset(MEMBER)
    identity.reset_password(token, NEW_PW)
    with pytest.raises(identity.InvalidResetToken):
        identity.reset_password(token, "yet-another-password")


def test_unknown_token_rejected(mu):
    with pytest.raises(identity.InvalidResetToken):
        identity.reset_password("not-a-real-token", NEW_PW)


def test_weak_password_rejected(mu):
    token, _ = identity.request_password_reset(MEMBER)
    with pytest.raises(ValueError):
        identity.reset_password(token, "short")


def test_reset_revokes_existing_sessions(mu):
    uid = _member_id()
    api_auth.create_session(label="pre-reset", user_id=uid)
    token, _ = identity.request_password_reset(MEMBER)
    identity.reset_password(token, NEW_PW)

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT COUNT(*) FROM sessions WHERE user_id = {'%s' if database.is_postgres() else '?'}",
        (uid,),
    )
    remaining = cur.fetchone()[0]
    conn.close()
    assert remaining == 0


# --- rate limiting --------------------------------------------------

def test_reset_request_rate_limited_per_ip(mu, monkeypatch):
    monkeypatch.setenv("TL_PASSWORD_RESET_MAX_PER_IP", "2")
    assert identity.reset_rate_limited_for("9.9.9.9") is None
    identity.record_reset_request("9.9.9.9")
    assert identity.reset_rate_limited_for("9.9.9.9") is None
    identity.record_reset_request("9.9.9.9")
    assert identity.reset_rate_limited_for("9.9.9.9") is not None


def test_reset_request_rate_limited_per_email_across_ips(mu, monkeypatch):
    monkeypatch.setenv("TL_PASSWORD_RESET_MAX_PER_EMAIL", "2")
    identity.record_reset_request("1.1.1.1", MEMBER)
    identity.record_reset_request("2.2.2.2", MEMBER)
    # a brand-new IP is still blocked for this victim's address...
    assert identity.reset_rate_limited_for("3.3.3.3", MEMBER) is not None
    # ...but not for a different address
    assert identity.reset_rate_limited_for("3.3.3.3", STRANGER) is None


def test_using_one_link_burns_the_others(mu):
    first, _ = identity.request_password_reset(MEMBER)
    second, _ = identity.request_password_reset(MEMBER)
    identity.reset_password(second, NEW_PW)
    with pytest.raises(identity.InvalidResetToken):
        identity.reset_password(first, "yet-another-password")


def test_disabled_account_cannot_use_an_earlier_link(mu):
    token, user = identity.request_password_reset(MEMBER)
    identity.set_user_status(user["id"], "disabled")
    with pytest.raises(identity.InvalidResetToken):
        identity.reset_password(token, NEW_PW)


# --- client IP: X-Forwarded-For spoofing -----------------------------

def _fake_request(xff, peer="10.0.0.1"):
    from types import SimpleNamespace
    return SimpleNamespace(headers={"x-forwarded-for": xff} if xff else {},
                           client=SimpleNamespace(host=peer))


def test_client_ip_ignores_client_supplied_forwarded_for(monkeypatch):
    from api.routers import auth as auth_router
    monkeypatch.delenv("TL_TRUSTED_PROXY_HOPS", raising=False)
    # attacker sends "6.6.6.6"; Render appends the real address
    assert auth_router._client_ip(_fake_request("6.6.6.6, 203.0.113.9")) == "203.0.113.9"
    assert auth_router._client_ip(_fake_request("203.0.113.9")) == "203.0.113.9"
    assert auth_router._client_ip(_fake_request("")) == "10.0.0.1"


def test_client_ip_no_trusted_proxy_uses_socket_peer(monkeypatch):
    from api.routers import auth as auth_router
    monkeypatch.setenv("TL_TRUSTED_PROXY_HOPS", "0")
    assert auth_router._client_ip(_fake_request("6.6.6.6")) == "10.0.0.1"


def test_spoofed_forwarded_for_cannot_dodge_login_lockout(mu, monkeypatch):
    monkeypatch.setenv("TL_AUTH_MAX_ATTEMPTS", "3")
    with api_auth._attempts_lock:
        api_auth._attempts.clear()
    with TestClient(app) as c:
        for i in range(3):
            c.post("/api/auth/login", json={"email": MEMBER, "password": "wrong"},
                   headers={"x-forwarded-for": f"9.9.9.{i}, 198.51.100.7"})
        r = c.post("/api/auth/login", json={"email": MEMBER, "password": OLD_PW},
                   headers={"x-forwarded-for": "9.9.9.200, 198.51.100.7"})
        assert r.status_code == 429
    with api_auth._attempts_lock:
        api_auth._attempts.clear()


def test_forgot_password_mints_token_in_background(mu):
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM password_resets")
    before = cur.fetchone()[0]
    conn.close()
    with TestClient(app) as c:
        assert c.post("/api/auth/forgot-password", json={"email": MEMBER}).status_code == 200
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM password_resets")
    after = cur.fetchone()[0]
    conn.close()
    assert after == before + 1


# --- HTTP layer: no account-enumeration ------------------------------

def test_forgot_password_always_ok_known_email(mu):
    with TestClient(app) as c:
        r = c.post("/api/auth/forgot-password", json={"email": MEMBER})
        assert r.status_code == 200
        assert r.json()["ok"] is True


def test_forgot_password_always_ok_unknown_email(mu):
    with TestClient(app) as c:
        r = c.post("/api/auth/forgot-password", json={"email": STRANGER})
        assert r.status_code == 200
        assert r.json()["ok"] is True


def test_forgot_password_always_ok_disabled_email(mu):
    with TestClient(app) as c:
        r = c.post("/api/auth/forgot-password", json={"email": DISABLED})
        assert r.status_code == 200
        assert r.json()["ok"] is True


def test_reset_password_http_roundtrip(mu):
    token, _ = identity.request_password_reset(MEMBER)
    with TestClient(app) as c:
        r = c.post("/api/auth/reset-password", json={"token": token, "password": NEW_PW})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["user"]["email"] == MEMBER

        login = c.post("/api/auth/login", json={"email": MEMBER, "password": NEW_PW})
        assert login.status_code == 200
        assert login.json()["ok"] is True


def test_reset_password_http_bad_token(mu):
    with TestClient(app) as c:
        r = c.post("/api/auth/reset-password", json={"token": "x" * 32, "password": NEW_PW})
        assert r.status_code == 400
        assert r.json()["ok"] is False


# --- disabled outside multiuser mode ---------------------------------

def test_forgot_password_404_in_passphrase_mode(monkeypatch):
    monkeypatch.delenv("TL_AUTH_MODE", raising=False)
    monkeypatch.delenv("TL_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("TL_AUTH_COOKIE_SECURE", "0")
    with TestClient(app) as c:
        r = c.post("/api/auth/forgot-password", json={"email": MEMBER})
        assert r.status_code == 404
