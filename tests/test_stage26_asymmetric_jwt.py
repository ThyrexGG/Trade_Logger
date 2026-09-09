# -*- coding: utf-8 -*-
"""
W8.1 follow-up — Supabase asymmetric signing keys (ES256 / RS256).

Newer Supabase projects sign access tokens with an ECC/RSA key instead of the
legacy shared HS256 secret. The public half is published as a JWKS document;
``identity.decode_token`` fetches it (cached) and verifies with
``cryptography``. These tests mock the JWKS fetch so nothing hits the network.

Still identity-only — no order path.
"""
import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from api import identity

ISS = "https://proj.supabase.co/auth/v1"
KID = "test-kid-1"


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _int_b64u(n: int, size: int) -> str:
    return _b64u(n.to_bytes(size, "big"))


# --- EC P-256 -----------------------------------------------------------

_EC_KEY = ec.generate_private_key(ec.SECP256R1())
_EC_PUB = _EC_KEY.public_key().public_numbers()
_EC_JWK = {
    "kty": "EC", "crv": "P-256", "kid": KID, "alg": "ES256", "use": "sig",
    "x": _int_b64u(_EC_PUB.x, 32), "y": _int_b64u(_EC_PUB.y, 32),
}


def _mint_es256(claims: dict, *, key=_EC_KEY, kid: str = KID) -> str:
    header = _b64u(json.dumps({"alg": "ES256", "typ": "JWT", "kid": kid}).encode())
    payload = _b64u(json.dumps(claims).encode())
    der = key.sign(f"{header}.{payload}".encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return f"{header}.{payload}.{_b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


# --- RSA --------------------------------------------------------------

_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_RSA_PUB = _RSA_KEY.public_key().public_numbers()
_RSA_JWK = {
    "kty": "RSA", "kid": "rsa-kid", "alg": "RS256", "use": "sig",
    "n": _b64u(_RSA_PUB.n.to_bytes((_RSA_PUB.n.bit_length() + 7) // 8, "big")),
    "e": _b64u(_RSA_PUB.e.to_bytes((_RSA_PUB.e.bit_length() + 7) // 8, "big")),
}


def _mint_rs256(claims: dict, *, kid: str = "rsa-kid") -> str:
    header = _b64u(json.dumps({"alg": "RS256", "typ": "JWT", "kid": kid}).encode())
    payload = _b64u(json.dumps(claims).encode())
    sig = _RSA_KEY.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64u(sig)}"


def _claims(**over) -> dict:
    base = {
        "sub": "u-abc", "email": "friend@example.com", "aud": "authenticated",
        "iss": ISS, "iat": int(time.time()) - 10, "exp": int(time.time()) + 3600,
    }
    base.update(over)
    return base


@pytest.fixture()
def asym_env(monkeypatch):
    monkeypatch.setenv("TL_AUTH_MODE", "supabase")
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    identity._jwks_cache.clear()

    def fake_fetch(url, *, force=False):
        return {KID: _EC_JWK, "rsa-kid": _RSA_JWK}

    monkeypatch.setattr(identity, "_fetch_jwks", fake_fetch)
    yield
    identity._jwks_cache.clear()


# --- verification ----------------------------------------------------

def test_accepts_valid_es256(asym_env):
    claims = identity.decode_token(_mint_es256(_claims()))
    assert claims["sub"] == "u-abc"
    assert claims["email"] == "friend@example.com"


def test_accepts_valid_rs256(asym_env):
    claims = identity.decode_token(_mint_rs256(_claims()))
    assert claims["sub"] == "u-abc"


def test_rejects_es256_tampered_payload(asym_env):
    tok = _mint_es256(_claims())
    head, _payload, sig = tok.split(".")
    forged = base64.urlsafe_b64encode(
        json.dumps(_claims(email="attacker@example.com")).encode()
    ).rstrip(b"=").decode()
    with pytest.raises(identity.InvalidToken):
        identity.decode_token(f"{head}.{forged}.{sig}")


def test_rejects_unknown_kid(asym_env):
    with pytest.raises(identity.InvalidToken):
        identity.decode_token(_mint_es256(_claims(), kid="not-a-real-kid"))


def test_rejects_es256_signed_by_wrong_key(asym_env):
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(identity.InvalidToken):
        identity.decode_token(_mint_es256(_claims(), key=other))


def test_rejects_issuer_not_matching_supabase_url(asym_env, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://different-project.supabase.co")
    with pytest.raises(identity.InvalidToken):
        identity.decode_token(_mint_es256(_claims()))


def test_rejects_expired_es256(asym_env):
    with pytest.raises(identity.InvalidToken):
        identity.decode_token(_mint_es256(_claims(exp=int(time.time()) - 120)))


def test_supabase_enabled_with_url_only(monkeypatch):
    monkeypatch.setenv("TL_AUTH_MODE", "supabase")
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    assert identity.supabase_enabled() is True


def test_jwks_discovery_falls_back_to_issuer(asym_env, monkeypatch):
    # no SUPABASE_URL -> the verified issuer claim is used for key discovery
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    seen = {}

    def fake_fetch(url, *, force=False):
        seen["url"] = url
        return {KID: _EC_JWK}

    monkeypatch.setattr(identity, "_fetch_jwks", fake_fetch)
    identity.decode_token(_mint_es256(_claims()))
    assert seen["url"] == f"{ISS}/.well-known/jwks.json"
