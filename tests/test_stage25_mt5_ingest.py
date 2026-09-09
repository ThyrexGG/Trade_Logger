# -*- coding: utf-8 -*-
"""
W9 — MT5 push-agent ingest.

A friend on a MetaTrader broker runs ``agent/mt5_push_agent.py`` locally; it
POSTs their raw MT5 snapshot to ``/api/ingest/mt5``. The request's tenant is
already bound, so the reconstruction + writes all land on that user's rows.

Data ingestion only: these tests assert there is no order path and that one
user's push can never touch another user's data.
"""
import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import database
import mt5_ingest
import tenant
from api import identity
from api.main import app

FAKE_JWT_SECRET = "fake-fixture-jwt-secret"
ALICE = "alice@example.com"
BOB = "bob@example.com"


def _seg(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def _jwt(sub: str, email: str) -> str:
    h = _seg({"alg": "HS256", "typ": "JWT"})
    p = _seg({"sub": sub, "email": email, "aud": "authenticated",
              "iat": int(time.time()) - 5, "exp": int(time.time()) + 3600})
    sig = hmac.new(FAKE_JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"


def _deal(ticket, position, dtype, price, ts, volume=1.0, profit=0.0):
    return {
        "deal_id": str(ticket), "symbol": "XAUUSD.pro", "type": dtype,
        "volume": volume, "price": price, "commission": -0.5, "swap": 0.0,
        "profit": profit, "timestamp": int(ts), "position_id": str(position),
    }


def _round_trip_deals(position="900", entry_ts=1_700_000_000):
    """One fully closed long: buy then sell, same volume."""
    return [
        _deal(1, position, "BUY", 2000.0, entry_ts, profit=0.0),
        _deal(2, position, "SELL", 2010.0, entry_ts + 3600, profit=10.0),
    ]


@pytest.fixture()
def clean(monkeypatch):
    database.init_db()
    conn = database.get_connection()
    cur = conn.cursor()
    ph = database.get_sql_placeholder(conn)
    for t in ("closed_trades", "raw_deals", "open_positions", "account_metadata"):
        cur.execute(
            f"DELETE FROM {t} WHERE user_id IN ({ph}, {ph}, {ph}, {ph})",
            ("alice", "bob", "u-alice", "u-bob"),
        )
    conn.commit()
    conn.close()
    database.invalidate_db_cache()
    yield
    database.invalidate_db_cache()


# --- reconstruction logic ------------------------------------------------

def test_matched_position_becomes_one_closed_trade(clean):
    with tenant.use("alice"):
        summary = mt5_ingest.ingest_mt5_payload("MT5_777", deals=_round_trip_deals())
        assert summary["raw_deals"] == 2
        assert summary["closed_trades"] == 1
        df = database.get_closed_trades()
        assert list(df["symbol"]) == ["XAUUSD"]          # suffix normalised
        assert list(df["account_id"]) == ["MT5_777"]
        assert round(float(df.iloc[0]["net_profit"]), 2) == 9.0   # 10 profit - 1.0 commission


def test_open_only_position_is_not_closed(clean):
    with tenant.use("alice"):
        summary = mt5_ingest.ingest_mt5_payload(
            "MT5_777", deals=[_deal(1, "901", "BUY", 2000.0, 1_700_000_000)]
        )
        assert summary["raw_deals"] == 1
        assert summary["closed_trades"] == 0
        assert database.get_closed_trades().empty


def test_non_trade_deal_types_are_dropped(clean):
    with tenant.use("alice"):
        deals = _round_trip_deals() + [
            {"deal_id": "99", "symbol": "", "type": "2", "volume": 0.0, "price": 0.0,
             "commission": 0.0, "swap": 0.0, "profit": 500.0, "timestamp": 1_700_000_000,
             "position_id": "deposit"},
        ]
        summary = mt5_ingest.ingest_mt5_payload("MT5_777", deals=deals)
        assert summary["raw_deals"] == 2          # the deposit row is ignored


def test_balance_and_positions_snapshot(clean):
    with tenant.use("alice"):
        mt5_ingest.ingest_mt5_payload(
            "MT5_777",
            balance={"balance": 1000.0, "equity": 1015.0, "currency": "USD"},
            positions=[{"position_id": "p1", "symbol": "EURUSD", "direction": "BUY",
                        "volume": 0.5, "entry_price": 1.1, "current_price": 1.11,
                        "floating_pnl": 5.0, "open_time": "2026-01-01T00:00:00"}],
        )
        assert "MT5_777" in database.get_account_balances(ttl_sec=0)
        assert len(database.get_open_positions()) == 1
        # a later snapshot with no positions clears them
        mt5_ingest.ingest_mt5_payload("MT5_777", positions=[])
        assert len(database.get_open_positions()) == 0


def test_oversized_push_is_rejected(clean):
    with tenant.use("alice"):
        with pytest.raises(ValueError):
            mt5_ingest.ingest_mt5_payload(
                "MT5_777",
                deals=[_deal(i, "p", "BUY", 1.0, 1) for i in range(mt5_ingest.MAX_DEALS_PER_PUSH + 1)],
            )


# --- tenant isolation --------------------------------------------------

def test_one_users_push_cannot_touch_another(clean):
    with tenant.use("alice"):
        mt5_ingest.ingest_mt5_payload("MT5_777", deals=_round_trip_deals(position="900"))
    with tenant.use("bob"):
        # same account id + position id, different tenant
        mt5_ingest.ingest_mt5_payload("MT5_777", deals=_round_trip_deals(position="900"))
        assert len(database.get_closed_trades()) == 1
    with tenant.use("alice"):
        df = database.get_closed_trades()
        assert len(df) == 1
        assert round(float(df.iloc[0]["net_profit"]), 2) == 9.0   # unchanged


# --- through the HTTP gate -------------------------------------------

@pytest.fixture()
def supa(monkeypatch, clean):
    monkeypatch.setenv("TL_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", FAKE_JWT_SECRET)
    monkeypatch.setenv("TL_SIGNUP_ALLOWLIST", f"{ALICE},{BOB}")
    monkeypatch.delenv("TL_OWNER_EMAIL", raising=False)
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


def test_ingest_endpoint_is_tenant_scoped_and_has_no_order_path(supa):
    c = TestClient(app)
    ah = {"Authorization": f"Bearer {_jwt('u-alice', ALICE)}"}
    bh = {"Authorization": f"Bearer {_jwt('u-bob', BOB)}"}

    body = {"account_id": "MT5_777", "agent_version": "1.0.0", "deals": _round_trip_deals()}
    r = c.post("/api/ingest/mt5", json=body, headers=ah)
    assert r.status_code == 200
    out = r.json()
    assert out["closed_trades"] == 1
    assert out["safety_barrier"] == {
        "live_automation_enabled": False, "live_broker_transmission": "BLOCKED",
    }

    # cursor now reflects alice's newest deal; bob still sees nothing
    a_cur = c.get("/api/ingest/mt5/cursor", params={"account": "MT5_777"}, headers=ah).json()
    b_cur = c.get("/api/ingest/mt5/cursor", params={"account": "MT5_777"}, headers=bh).json()
    assert a_cur["last_deal_timestamp"] == 1_700_003_600
    assert b_cur["last_deal_timestamp"] == 0

    with tenant.use("u-bob"):
        assert database.get_closed_trades().empty


def test_ingest_requires_auth_in_supabase_mode(supa):
    c = TestClient(app)
    assert c.post("/api/ingest/mt5", json={"account_id": "MT5_1", "deals": []}).status_code == 401
    assert c.get("/api/ingest/mt5/cursor", params={"account": "MT5_1"}).status_code == 401


def test_ingest_module_pulls_in_no_execution_code():
    import sys
    import importlib

    for mod in ("execution_pipeline", "risk_gateway", "order_execution", "broker_adapter"):
        sys.modules.pop(mod, None)
    importlib.reload(mt5_ingest)
    assert "order_execution" not in sys.modules
    assert "broker_adapter" not in sys.modules
