# -*- coding: utf-8 -*-
"""
Tests for W13 — prop-firm challenge tracker (`/api/challenge/*`).

Config lives in the existing `app_settings` key-value table, scoped by
tenant + account exactly like `analytics_initial_balance` (see
tests/test_analytics_saved_balance.py, same pattern reused here). Trade
population is real seeded `closed_trades` rows under a distinctive test
account_id, cleaned up in `finally`; the live account balance is monkeypatched
since `account_metadata` isn't otherwise exercised by these tests.
"""
import json
import types
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import database
from api import challenge as engine
from api.main import app

client = TestClient(app)

_ACCOUNT = "TEST_CHALLENGE_ACCOUNT_1"
_OTHER = "TEST_CHALLENGE_ACCOUNT_2"


def _backdate(account, days):
    """Test helper: push created_at/phase_start_date into the past so seeded
    trades from a few days ago fall inside the challenge/phase window — a
    real challenge is configured once, on day 1, before any of its trades."""
    cfg = engine.get_config(account)
    when = (date.today() - timedelta(days=days)).isoformat()
    cfg["created_at"] = when
    cfg["phase_start_date"] = when
    database.set_setting(engine._key(account), json.dumps(cfg))


def _seed_trade(account, days_ago, pnl):
    when = (date.today() - timedelta(days=days_ago)).isoformat()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(
            f"INSERT INTO closed_trades (trade_id, account_id, symbol, direction, volume, "
            f"entry_price, exit_price, entry_time, exit_time, net_profit) VALUES "
            f"({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (f"TEST_CHALLENGE_TRADE_{account}_{days_ago}_{pnl}", account, "EURUSD", "BUY", 0.1,
             1.1000, 1.1010, f"{when}T00:00:00Z", f"{when}T01:00:00Z", pnl))
        conn.commit()
    finally:
        conn.close()
    database.invalidate_db_cache("closed_trades")


def _cleanup(*accounts):
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        for acc in accounts:
            cur.execute(f"DELETE FROM closed_trades WHERE account_id = {ph}", (acc,))
            cur.execute(f"DELETE FROM app_settings WHERE key LIKE {ph}", (f"challenge_config::%::{acc}",))
        conn.commit()
    finally:
        conn.close()
    database.invalidate_db_cache("closed_trades")


@pytest.fixture(autouse=True)
def _isolate():
    _cleanup(_ACCOUNT, _OTHER)
    yield
    _cleanup(_ACCOUNT, _OTHER)


# --- not configured -------------------------------------------------------

def test_status_not_configured_is_all_null():
    r = client.get(f"/api/challenge/status?account={_ACCOUNT}")
    assert r.status_code == 200
    d = r.json()
    assert d["configured"] is False
    assert d["account_id"] == _ACCOUNT
    assert d["phase"] is None
    assert d["current_balance"] is None
    assert d["profit_day_dates"] == []


# --- config CRUD -----------------------------------------------------------

def test_save_config_defaults_to_phase_1_at_account_size():
    r = client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000})
    assert r.status_code == 200
    d = r.json()
    assert d["configured"] is True
    assert d["phase"] == "1"
    assert d["phase_start_balance"] == 5000.0
    assert d["config"]["firm"] == "5ers"
    assert d["config"]["phase1_target_pct"] == 10.0
    assert d["config"]["max_drawdown_pct"] == 10.0


def test_updating_config_preserves_phase_progress():
    client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000})
    client.post("/api/challenge/advance", json={"account_id": _ACCOUNT, "to": "2"})
    r = client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000, "daily_loss_pct": 4.0})
    d = r.json()
    assert d["phase"] == "2"  # not reset back to "1" by the rule edit
    assert d["config"]["daily_loss_pct"] == 4.0


def test_config_rejects_bad_input():
    assert client.post("/api/challenge/config", json={"account_id": "", "account_size": 5000}).status_code == 422
    assert client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 0}).status_code == 422
    assert client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000, "drawdown_mode": "banana"}).status_code == 422
    assert client.post("/api/challenge/config", json={"account_size": 5000}).status_code == 422  # missing account_id


def test_delete_config_returns_to_unconfigured():
    client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000})
    r = client.delete(f"/api/challenge/config?account={_ACCOUNT}")
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert client.get(f"/api/challenge/status?account={_ACCOUNT}").json()["configured"] is False


def test_advance_and_reset_require_existing_config():
    assert client.post("/api/challenge/advance", json={"account_id": _ACCOUNT, "to": "2"}).status_code == 404
    assert client.post("/api/challenge/reset", json={"account_id": _ACCOUNT}).status_code == 404


def test_config_does_not_leak_across_accounts():
    client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000})
    assert client.get(f"/api/challenge/status?account={_OTHER}").json()["configured"] is False


# --- phase progress / profit days (real seeded trades) --------------------

def test_phase_progress_and_profit_days(monkeypatch):
    monkeypatch.setattr(database, "get_account_balances", lambda ttl_sec=2.0: {})
    client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000})
    _backdate(_ACCOUNT, 3)

    _seed_trade(_ACCOUNT, 2, 30)   # profit day (>= 0.5% of 5000 = 25)
    _seed_trade(_ACCOUNT, 1, 40)   # profit day
    _seed_trade(_ACCOUNT, 0, 26)   # profit day, today

    d = client.get(f"/api/challenge/status?account={_ACCOUNT}").json()
    assert d["current_balance"] == 5096.0
    assert d["phase_target_pct"] == 10.0
    assert d["phase_gain_amount"] == 96.0
    assert d["phase_progress_pct"] == pytest.approx(1.92, abs=0.01)
    assert d["phase_progress_ratio"] == pytest.approx(0.192, abs=0.001)
    assert d["profit_days_count"] == 3
    assert d["min_profit_days"] == 3
    assert len(d["profit_day_dates"]) == 3
    assert d["daily_loss_today_amount"] == 26.0
    assert d["daily_loss_used_pct"] == 0.0  # a green day uses none of the daily-loss budget


def test_trailing_drawdown_measures_from_the_peak(monkeypatch):
    client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000, "drawdown_mode": "trailing"})
    _backdate(_ACCOUNT, 3)
    _seed_trade(_ACCOUNT, 2, 200)   # balance -> 5200 (new peak)
    _seed_trade(_ACCOUNT, 1, -150)  # balance -> 5050
    _seed_trade(_ACCOUNT, 0, -50)   # balance -> 5000, today

    monkeypatch.setattr(database, "get_account_balances", lambda ttl_sec=2.0: {_ACCOUNT: {"balance": 5000.0, "equity": 5000.0, "currency": "USD"}})
    d = client.get(f"/api/challenge/status?account={_ACCOUNT}").json()
    assert d["peak_balance"] == 5200.0
    assert d["current_balance"] == 5000.0
    # (5200 - 5000) / 5200 * 100
    assert d["drawdown_used_pct"] == pytest.approx(3.846, abs=0.01)
    assert d["drawdown_budget_used_ratio"] == pytest.approx(0.3846, abs=0.001)
    assert d["daily_loss_today_amount"] == -50.0
    assert d["daily_loss_used_pct"] == 1.0  # 50 / 5000 * 100
    assert d["daily_loss_budget_used_ratio"] == pytest.approx(0.2, abs=0.001)  # 1.0 / 5.0


def test_static_drawdown_measures_from_the_initial_size_not_the_peak(monkeypatch):
    client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000, "drawdown_mode": "static"})
    _backdate(_ACCOUNT, 3)
    _seed_trade(_ACCOUNT, 2, 200)
    _seed_trade(_ACCOUNT, 1, -150)
    _seed_trade(_ACCOUNT, 0, -50)

    monkeypatch.setattr(database, "get_account_balances", lambda ttl_sec=2.0: {_ACCOUNT: {"balance": 5000.0, "equity": 5000.0, "currency": "USD"}})
    d = client.get(f"/api/challenge/status?account={_ACCOUNT}").json()
    # back at the original deposit exactly -> static mode shows zero drawdown,
    # even though trailing mode (previous test) shows ~3.8% off the peak
    assert d["drawdown_used_pct"] == 0.0
    assert d["drawdown_floor_balance"] == 4500.0  # 5000 * (1 - 10%)


def test_advance_phase_snapshots_live_balance_as_new_phase_start(monkeypatch):
    client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000})
    monkeypatch.setattr(database, "get_account_balances", lambda ttl_sec=2.0: {_ACCOUNT: {"balance": 5500.0, "equity": 5500.0, "currency": "USD"}})

    r = client.post("/api/challenge/advance", json={"account_id": _ACCOUNT, "to": "2"})
    d = r.json()
    assert d["phase"] == "2"
    assert d["phase_start_balance"] == 5500.0
    assert d["phase_target_pct"] == 5.0  # phase 2 default
    assert d["phase_progress_pct"] == 0.0  # just started phase 2, no gain yet


def test_advance_to_funded_has_no_target():
    client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000})
    r = client.post("/api/challenge/advance", json={"account_id": _ACCOUNT, "to": "funded"})
    d = r.json()
    assert d["phase"] == "funded"
    assert d["phase_target_pct"] is None
    assert d["phase_progress_ratio"] is None


def test_reset_restarts_from_phase_1_at_account_size(monkeypatch):
    client.post("/api/challenge/config", json={"account_id": _ACCOUNT, "account_size": 5000})
    monkeypatch.setattr(database, "get_account_balances", lambda ttl_sec=2.0: {_ACCOUNT: {"balance": 5500.0, "equity": 5500.0, "currency": "USD"}})
    client.post("/api/challenge/advance", json={"account_id": _ACCOUNT, "to": "2"})

    r = client.post("/api/challenge/reset", json={"account_id": _ACCOUNT})
    d = r.json()
    assert d["phase"] == "1"
    assert d["phase_start_balance"] == 5000.0


# --- execution isolation ----------------------------------------------------

def test_challenge_binds_no_execution_symbol():
    import api.routers.challenge as router_mod

    forbidden_names = {
        "execution_pipeline", "broker_adapter", "risk_gateway", "submit_order",
        "get_broker_adapter", "CanonicalExecutionRequest", "execution_recorder",
    }
    for mod in (engine, router_mod):
        for name, value in vars(mod).items():
            assert name not in forbidden_names, f"{mod.__name__} binds {name}"
            if isinstance(value, types.ModuleType):
                top = value.__name__.split(".")[0]
                assert top not in forbidden_names, f"{mod.__name__} imports {value.__name__}"
