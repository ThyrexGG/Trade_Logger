# -*- coding: utf-8 -*-
"""
W8.5 — per-user broker credentials, encrypted at rest.

Secrets are Fernet-encrypted with TL_CREDENTIAL_ENC_KEY; the metadata API never
returns them; connections are tenant-scoped. No order path — these credentials
feed only Capital.com's read-only endpoints.
"""
import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import database
import tenant
from api import broker_credentials as bc
from api import identity
from api.main import app

SECRET = {"api_key": "AK-123", "email": "me@example.com", "password": "p@ss-w0rd"}


@pytest.fixture()
def enc(monkeypatch):
    monkeypatch.setenv("TL_CREDENTIAL_ENC_KEY", bc.generate_key())
    bc.ensure_table()
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM broker_connections WHERE user_id IN ('alice', 'bob', 'local')")
    conn.commit()
    conn.close()
    yield


def test_enc_enabled_reflects_env(monkeypatch):
    monkeypatch.delenv("TL_CREDENTIAL_ENC_KEY", raising=False)
    assert bc.enc_enabled() is False
    monkeypatch.setenv("TL_CREDENTIAL_ENC_KEY", bc.generate_key())
    assert bc.enc_enabled() is True


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("TL_CREDENTIAL_ENC_KEY", raising=False)
    with pytest.raises(bc.CredentialError):
        bc.create_connection(secret=SECRET, account_id="A1")


def test_roundtrip_and_ciphertext_opaque(enc):
    with tenant.use("alice"):
        meta = bc.create_connection(secret=SECRET, account_id="A1", is_demo=True, label="demo")
        got = bc.get_secret(meta["id"])
    assert got["api_key"] == SECRET["api_key"]
    assert got["password"] == SECRET["password"]
    assert got["account_id"] == "A1"
    assert got["is_demo"] is True

    # the stored blob must not contain any plaintext secret
    conn = database.get_connection()
    cur = conn.cursor()
    ph = database.get_sql_placeholder(conn)
    cur.execute(f"SELECT secret_ciphertext FROM broker_connections WHERE id = {ph}", (meta["id"],))
    ct = cur.fetchone()[0]
    conn.close()
    for v in SECRET.values():
        assert v not in ct


def test_metadata_api_never_returns_secret(enc):
    with tenant.use("alice"):
        bc.create_connection(secret=SECRET, account_id="A1")
        rows = bc.list_connections()
        meta = bc.get_meta(rows[0]["id"])
    blob = json.dumps(rows) + json.dumps(meta)
    for v in SECRET.values():
        assert v not in blob
    assert "secret_ciphertext" not in blob


def test_connections_are_tenant_scoped(enc):
    with tenant.use("alice"):
        a = bc.create_connection(secret=SECRET, account_id="A1")
    with tenant.use("bob"):
        assert bc.list_connections() == []
        assert bc.get_meta(a["id"]) is None
        with pytest.raises(bc.CredentialError):
            bc.get_secret(a["id"])
        with pytest.raises(bc.CredentialError):
            bc.update_connection(a["id"], label="stolen")
        assert bc.delete_connection(a["id"]) is False
    with tenant.use("alice"):
        assert len(bc.list_connections()) == 1


def test_partial_secret_update_merges(enc):
    with tenant.use("alice"):
        m = bc.create_connection(secret=SECRET, account_id="A1")
        bc.update_connection(m["id"], secret={"password": "new-pass"})
        got = bc.get_secret(m["id"])
    assert got["password"] == "new-pass"
    assert got["api_key"] == SECRET["api_key"]     # untouched
    assert got["email"] == SECRET["email"]


def test_active_connections_all_users(enc):
    with tenant.use("alice"):
        bc.create_connection(secret=SECRET, account_id="A1")
    with tenant.use("bob"):
        b = bc.create_connection(secret={"api_key": "BK", "email": "b@x.com", "password": "bpw"},
                                 account_id="B1")
        bc.update_connection(b["id"], is_active=False)
    active = bc.active_connections_all_users()
    users = {c["user_id"] for c in active}
    assert "alice" in users
    assert "bob" not in users                       # bob's is inactive
    alice = next(c for c in active if c["user_id"] == "alice")
    assert alice["secret"]["api_key"] == "AK-123"


def test_record_sync_result(enc):
    with tenant.use("alice"):
        m = bc.create_connection(secret=SECRET, account_id="A1")
        bc.record_sync_result(m["id"], False, "boom")
        meta = bc.get_meta(m["id"])
    assert meta["last_sync_ok"] is False
    assert meta["last_error"] == "boom"


# --- through the HTTP gate ------------------------------------------------

def _jwt(sub, email, secret):
    seg = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    h, p = seg({"alg": "HS256", "typ": "JWT"}), seg(
        {"sub": sub, "email": email, "aud": "authenticated",
         "iat": int(time.time()) - 5, "exp": int(time.time()) + 3600})
    sig = hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"


@pytest.fixture()
def supa(monkeypatch, enc):
    jwt_secret = "conn-test-secret"
    monkeypatch.setenv("TL_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setenv("TL_SIGNUP_ALLOWLIST", "alice@example.com,bob@example.com")
    monkeypatch.delenv("TL_OWNER_EMAIL", raising=False)
    identity._provision_cache.clear()
    identity.ensure_users_table()
    conn = database.get_connection()
    conn.cursor().execute("DELETE FROM users WHERE email LIKE '%@example.com'")
    conn.commit()
    conn.close()
    yield jwt_secret
    identity._provision_cache.clear()


def test_http_connections_isolated(supa):
    c = TestClient(app)
    ah = {"Authorization": f"Bearer {_jwt('u-alice', 'alice@example.com', supa)}"}
    bh = {"Authorization": f"Bearer {_jwt('u-bob', 'bob@example.com', supa)}"}

    r = c.post("/api/connections", headers=ah, json={
        "label": "mine", "account_id": "A1", "is_demo": True,
        "secret": {"api_key": "AK", "email": "a@x.com", "password": "pw"}})
    assert r.status_code == 201, r.text
    cid = r.json()["connection"]["id"]
    assert "secret" not in json.dumps(r.json())
    assert "AK" not in json.dumps(r.json())

    assert len(c.get("/api/connections", headers=ah).json()["connections"]) == 1
    assert c.get("/api/connections", headers=bh).json()["connections"] == []

    assert c.patch(f"/api/connections/{cid}", headers=bh, json={"label": "x"}).status_code == 404
    assert c.delete(f"/api/connections/{cid}", headers=bh).status_code == 404
    assert c.delete(f"/api/connections/{cid}", headers=ah).status_code == 200
