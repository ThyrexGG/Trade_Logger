# -*- coding: utf-8 -*-
"""
Referral-bonus claims — self-report + owner review.

Mirrors test_stage24_admin.py's fake-JWT / supabase-mode fixture for
exercising the owner-only endpoints without a full signup flow; the
owner-check itself (`_require_owner`) is the identical mechanism admin.py
uses, just reused in this router.
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
from api import referrals as ref
from api.main import app

FAKE_JWT_SECRET = "fake-fixture-jwt-secret-referrals"
OWNER = "ref-owner@example.com"
FRIEND = "ref-friend@example.com"


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
    monkeypatch.setattr(identity, "_DENY_TTL_SEC", 0)
    identity._provision_cache.clear()
    identity._deny_cache.clear()
    identity.ensure_users_table()
    ref.ensure_claims_table()
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email LIKE '%@example.com'")
    cur.execute("DELETE FROM referral_claims WHERE partner_id = 'test-partner'")
    conn.commit()
    conn.close()
    yield
    identity._provision_cache.clear()
    identity._deny_cache.clear()


def test_claim_then_claim_again_is_idempotent(supa):
    c = TestClient(app)
    fh = {"Authorization": f"Bearer {_jwt('u-friend', FRIEND)}"}

    r1 = c.post("/api/referrals/claim", params={"partner_id": "test-partner", "note": "used the link"}, headers=fh)
    assert r1.status_code == 200
    claim1 = r1.json()["claim"]
    assert claim1["status"] == "pending"
    assert claim1["partner_id"] == "test-partner"

    r2 = c.post("/api/referrals/claim", params={"partner_id": "test-partner", "note": "different note"}, headers=fh)
    assert r2.status_code == 200
    claim2 = r2.json()["claim"]
    assert claim2["id"] == claim1["id"]  # same claim, not a duplicate
    assert claim2["note"] == "used the link"  # first note wins, not overwritten


def test_mine_lists_only_the_caller_own_claims(supa):
    c = TestClient(app)
    fh = {"Authorization": f"Bearer {_jwt('u-friend', FRIEND)}"}
    oh = {"Authorization": f"Bearer {_jwt('u-owner', OWNER)}"}

    c.post("/api/referrals/claim", params={"partner_id": "test-partner"}, headers=fh)

    mine_friend = c.get("/api/referrals/mine", headers=fh).json()["claims"]
    assert len(mine_friend) == 1

    mine_owner = c.get("/api/referrals/mine", headers=oh).json()["claims"]
    assert mine_owner == []  # the owner never claimed anything


def test_admin_endpoints_are_owner_only(supa):
    c = TestClient(app)
    fh = {"Authorization": f"Bearer {_jwt('u-friend', FRIEND)}"}
    oh = {"Authorization": f"Bearer {_jwt('u-owner', OWNER)}"}

    r = c.post("/api/referrals/claim", params={"partner_id": "test-partner"}, headers=fh)
    claim_id = r.json()["claim"]["id"]

    assert c.get("/api/referrals/admin/all", headers=fh).status_code == 403
    assert c.post(f"/api/referrals/admin/{claim_id}/verify", headers=fh).status_code == 403

    all_claims = c.get("/api/referrals/admin/all", headers=oh).json()["claims"]
    assert any(cl["id"] == claim_id for cl in all_claims)
    # the admin listing joins the claimant's email in, for the owner to
    # cross-check against the affiliate dashboard by eye
    assert any(cl["email"] == FRIEND for cl in all_claims)


def test_owner_can_verify_and_reject(supa):
    c = TestClient(app)
    fh = {"Authorization": f"Bearer {_jwt('u-friend', FRIEND)}"}
    oh = {"Authorization": f"Bearer {_jwt('u-owner', OWNER)}"}

    claim_id = c.post("/api/referrals/claim", params={"partner_id": "test-partner"}, headers=fh).json()["claim"]["id"]

    r = c.post(f"/api/referrals/admin/{claim_id}/verify", headers=oh)
    assert r.status_code == 200
    verified = r.json()["claim"]
    assert verified["status"] == "verified"
    assert verified["reviewed_by"] is not None
    assert verified["reviewed_at"] is not None

    r2 = c.post(f"/api/referrals/admin/{claim_id}/reject", headers=oh)
    assert r2.json()["claim"]["status"] == "rejected"


def test_verify_unknown_claim_is_404(supa):
    c = TestClient(app)
    oh = {"Authorization": f"Bearer {_jwt('u-owner', OWNER)}"}
    r = c.post("/api/referrals/admin/does-not-exist/verify", headers=oh)
    assert r.status_code == 404
