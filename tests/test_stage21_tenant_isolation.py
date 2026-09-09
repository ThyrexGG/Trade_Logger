# -*- coding: utf-8 -*-
"""
W8.4 — per-tenant data isolation.

Every journal-side table carries ``user_id`` and every ``database.*`` read/write
scopes to the current tenant (``tenant.py`` context var, set per request by the
API middleware in supabase mode). These tests prove one tenant can never see or
mutate another's rows — directly through ``database`` and through the HTTP gate.

Still read-only: no order path anywhere.
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
from api import identity
from api.main import app

SECRET = "test-supabase-jwt-secret-w84"
ALICE = "alice@example.com"
BOB = "bob@example.com"


# --- helpers ---------------------------------------------------------------

def _seg(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def _jwt(sub: str, email: str) -> str:
    h = _seg({"alg": "HS256", "typ": "JWT"})
    p = _seg({"sub": sub, "email": email, "aud": "authenticated",
              "iat": int(time.time()) - 5, "exp": int(time.time()) + 3600})
    sig = hmac.new(SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"


def _trade(tid: str, symbol: str = "XAUUSD", pnl: float = 10.0) -> dict:
    return dict(trade_id=tid, account_id="ACC", symbol=symbol, direction="LONG",
               volume=1.0, entry_price=2000.0, exit_price=2010.0, commission=0.0,
               swap=0.0, gross_profit=pnl, net_profit=pnl, entry_time="2026-01-01T00:00:00",
               exit_time="2026-01-02T00:00:00", duration_minutes=60.0, setup_tag=None)


@pytest.fixture()
def clean_tenants():
    database.init_db()
    conn = database.get_connection()
    cur = conn.cursor()
    ph = database.get_sql_placeholder(conn)
    for t in ("closed_trades", "raw_deals", "open_positions", "account_metadata",
              "price_alerts", "journal_entries", "journal_screenshots"):
        cur.execute(f"DELETE FROM {t} WHERE user_id IN ({ph}, {ph})", ("alice", "bob"))
    conn.commit()
    conn.close()
    database.invalidate_db_cache()
    yield
    database.invalidate_db_cache()


# --- direct database layer -----------------------------------------------

def test_closed_trades_isolated_by_tenant(clean_tenants):
    with tenant.use("alice"):
        database.save_closed_trades([_trade("a1"), _trade("a2")])
    with tenant.use("bob"):
        database.save_closed_trades([_trade("b1")])
        assert sorted(database.get_closed_trades()["trade_id"]) == ["b1"]
    with tenant.use("alice"):
        assert sorted(database.get_closed_trades()["trade_id"]) == ["a1", "a2"]


def test_one_tenant_cannot_mutate_anothers_trade(clean_tenants):
    with tenant.use("alice"):
        database.save_closed_trades([_trade("a1")])
    with tenant.use("bob"):
        database.update_setup_tag("a1", "hijacked")           # different tenant
        database.update_trade_journal("a1", notes="hijacked")
    with tenant.use("alice"):
        row = database.get_closed_trades().iloc[0]
        assert row["setup_tag"] in (None, "")                 # untouched
        assert (row.get("notes") or "") == ""


def test_journal_entries_isolated(clean_tenants):
    with tenant.use("alice"):
        database.create_journal_entry("ja", "idea", "XAUUSD", "A", "body", ["x"])
    with tenant.use("bob"):
        assert database.list_journal_entries() == []
        assert database.get_journal_entry("ja") is None
        assert database.journal_entry_exists("ja") is False
        assert database.update_journal_entry("ja", title="stolen") is False
        assert database.delete_journal_entry("ja") is False
    with tenant.use("alice"):
        assert database.get_journal_entry("ja")["title"] == "A"


def test_price_alerts_isolated(clean_tenants):
    with tenant.use("alice"):
        aid = database.create_price_alert("XAUUSD", 2500, "ABOVE")
    with tenant.use("bob"):
        assert len(database.get_all_price_alerts()) == 0
        assert database.get_active_price_alerts() == []
        database.delete_price_alert(aid)                       # no-op cross-tenant
        database.mark_price_alert_triggered(aid)
    with tenant.use("alice"):
        alerts = database.get_active_price_alerts()
        assert len(alerts) == 1 and alerts[0]["id"] == aid     # still active, still there


def test_balances_and_positions_isolated(clean_tenants):
    with tenant.use("alice"):
        database.save_account_balance("ACC-A", 1000, 1010)
        database.save_open_positions("ACC-A", [dict(
            position_id="pa", account_id="ACC-A", symbol="XAUUSD", direction="LONG",
            volume=1.0, entry_price=2000, current_price=2005, sl=0, tp=0,
            floating_pnl=5, swap=0, open_time="2026-01-01", updated_at="2026-01-01")])
    with tenant.use("bob"):
        assert database.get_account_balances(ttl_sec=0) == {}
        assert len(database.get_open_positions()) == 0
    with tenant.use("alice"):
        assert "ACC-A" in database.get_account_balances(ttl_sec=0)
        assert len(database.get_open_positions()) == 1


def test_passphrase_mode_is_the_local_tenant(clean_tenants):
    # no context bound -> everything is tenant "local", exactly like pre-W8
    database.save_closed_trades([_trade("loc1")])
    assert "loc1" in list(database.get_closed_trades()["trade_id"])
    with tenant.use(None):
        assert "loc1" in list(database.get_closed_trades()["trade_id"])
    assert tenant.current_user_id() == tenant.LOCAL_USER_ID


# --- through the HTTP gate (supabase mode) ------------------------------

@pytest.fixture()
def supa(monkeypatch, clean_tenants):
    monkeypatch.setenv("TL_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setenv("TL_SIGNUP_ALLOWLIST", f"{ALICE},{BOB}")
    monkeypatch.delenv("TL_OWNER_EMAIL", raising=False)
    identity._provision_cache.clear()
    identity.ensure_users_table()
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email LIKE '%@example.com'")
    conn.commit()
    conn.close()
    yield
    identity._provision_cache.clear()


def test_http_requests_are_tenant_scoped(supa):
    c = TestClient(app)
    ah = {"Authorization": f"Bearer {_jwt('u-alice', ALICE)}"}
    bh = {"Authorization": f"Bearer {_jwt('u-bob', BOB)}"}

    # seed alice's data straight into her tenant
    with tenant.use("u-alice"):
        database.save_closed_trades([_trade("ax", symbol="EURUSD")])
        database.create_journal_entry("aj", "idea", "EURUSD", "mine", "b", [])
    database.invalidate_db_cache()

    a_ops = c.get("/api/operations/journal", headers=ah).json()
    b_ops = c.get("/api/operations/journal", headers=bh).json()
    a_ids = {e["trade_id"] for e in a_ops.get("entries", [])}
    b_ids = {e["trade_id"] for e in b_ops.get("entries", [])}
    assert "ax" in a_ids
    assert "ax" not in b_ids

    # bob's analytics must not count alice's trade
    b_perf = c.get("/api/analytics/performance", headers=bh).json()
    assert b_perf["matched_trades"] == 0
