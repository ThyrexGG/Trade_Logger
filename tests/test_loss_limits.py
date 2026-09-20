# -*- coding: utf-8 -*-
"""Daily-loss and drawdown limit alerts: when they fire, that they fire once, and that they stay per user."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import database
import tenant
from api import loss_limits
from api.main import app

client = TestClient(app)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "limits.db")
    monkeypatch.setenv("TL_PUSH_ENABLED", "0")
    monkeypatch.setattr(database, "get_db_url", lambda: None)
    monkeypatch.setattr(database, "get_connection", lambda: sqlite3.connect(path, timeout=30))
    monkeypatch.setattr(database, "_PUSH_TABLES_READY", False)
    monkeypatch.setattr(database, "_DB_INITIALIZED", False)
    database.init_db(force=True)
    database.invalidate_db_cache()
    yield path


def _trade(pnl, days_ago=0, account="ACC1", hours_ago=0.0):
    """One manual closed trade whose exit lands `days_ago` days (and a few minutes) before now, in UTC."""
    exit_t = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)
    if days_ago == 0 and exit_t.date() != datetime.now(timezone.utc).date():
        exit_t = datetime.now(timezone.utc)  # never let "today" slip into yesterday near midnight UTC
    database.add_manual_trade({
        "account_id": account, "symbol": "EURUSD", "direction": "BUY", "volume": 1.0, "entry_price": 1.0,
        "exit_price": 1.0, "commission": 0.0, "swap": 0.0, "gross_profit": pnl,
        "entry_time": (exit_t - timedelta(minutes=5)).isoformat(), "exit_time": exit_t.isoformat(),
    })


def _events():
    return [e for e in database.list_trade_events(after_id=0, limit=100) if e["kind"] == "risk"]


def test_daily_loss_warns_at_80_percent_then_reached_and_never_repeats(db):
    with tenant.use("alice"):
        loss_limits.set_limits("ACC1", 100, None)
        _trade(-70)
        assert loss_limits.check() == 0                      # 70% - quiet
        _trade(-15)                                          # 85%
        assert loss_limits.check() == 1
        assert loss_limits.check() == 0                      # same level, same day: not again
        _trade(-20)                                          # 105%
        assert loss_limits.check() == 1
        assert loss_limits.check() == 0
        titles = [e["title"] for e in _events()]
        assert titles == ["Daily loss limit close to — ACC1", "Daily loss limit reached — ACC1"] or \
               sorted(titles) == sorted(["Daily loss limit close to — ACC1", "Daily loss limit reached — ACC1"])
        assert "$105.00" in " ".join(e["body"] for e in _events())


def test_jumping_straight_past_the_limit_sends_only_the_reached_alert(db):
    with tenant.use("alice"):
        loss_limits.set_limits("ACC1", 100, None)
        _trade(-150)
        assert loss_limits.check() == 1
        assert [e["title"] for e in _events()] == ["Daily loss limit reached — ACC1"]


def test_yesterdays_loss_and_other_accounts_do_not_count(db):
    with tenant.use("alice"):
        loss_limits.set_limits("ACC1", 100, None)
        _trade(-500, days_ago=2)
        _trade(-500, account="OTHER")
        _trade(+300)                                          # a winning day is never an alert
        assert loss_limits.check() == 0
        st = loss_limits.compute_status("ACC1")
        assert st["today_loss"] == 0 and st["daily_ratio"] == 0


def test_drawdown_measured_from_the_peak_and_rearms_on_a_new_high(db):
    with tenant.use("alice"):
        database.set_setting(f"analytics_initial_balance::alice::ACC1", "1000")
        loss_limits.set_limits("ACC1", None, 10)
        _trade(+100, days_ago=5)                              # peak 1100
        _trade(-95, days_ago=4)                               # 1005 -> 8.6% of a 10% limit = warn
        assert loss_limits.check() == 1
        assert loss_limits.check() == 0
        _trade(-20, days_ago=3)                               # 985 -> 10.45% = reached
        assert loss_limits.check() == 1
        st = loss_limits.compute_status("ACC1")
        assert st["peak_balance"] == 1100 and st["current_balance"] == 985 and st["drawdown_pct"] == 10.45
        _trade(+400, days_ago=2)                              # new high 1385: drawdown resets to 0
        _trade(-160, days_ago=1)                              # 1225 -> 11.6% below the new peak: a new alert
        assert loss_limits.check() == 1


def test_drawdown_without_a_starting_balance_is_reported_not_guessed(db):
    with tenant.use("alice"):
        loss_limits.set_limits("ACC1", None, 10)
        _trade(-500, days_ago=1)
        assert loss_limits.check() == 0
        st = loss_limits.compute_status("ACC1")
        assert st["drawdown_needs_balance"] is True and st["drawdown_pct"] is None


def test_each_user_only_gets_their_own_alerts(db):
    with tenant.use("alice"):
        loss_limits.set_limits("ACC1", 100, None)
        _trade(-150)
    with tenant.use("bob"):
        _trade(-999)                                          # bob has no limits at all
        assert loss_limits.check() == 0
        assert _events() == []
        assert loss_limits.get_limits() == {}
    with tenant.use("alice"):
        assert loss_limits.check() == 1
        assert len(_events()) == 1


def test_limits_api_round_trip_and_validation(db):
    with tenant.use("alice"):
        _trade(-10)
        assert client.put("/api/loss-limits/ACC1", json={"daily_loss": 50, "drawdown_pct": 8}).status_code == 200
        rows = client.get("/api/loss-limits").json()["accounts"]
        acc = next(r for r in rows if r["account_id"] == "ACC1")
        assert acc["daily_loss_limit"] == 50 and acc["drawdown_limit_pct"] == 8
        assert acc["today_loss"] == 10 and acc["daily_ratio"] == 0.2
        assert "_peak_at" not in acc
        assert client.put("/api/loss-limits/ACC1", json={"drawdown_pct": 100}).status_code == 422
        assert client.put("/api/loss-limits/ACC1", json={"daily_loss": -5}).status_code == 422
        assert client.put("/api/loss-limits/ACC1", json={"nope": 1}).status_code == 422
        assert client.delete("/api/loss-limits/ACC1").json()["cleared"] is True
        assert loss_limits.get_limits() == {}


def test_saving_a_limit_that_is_already_crossed_notifies_immediately(db):
    with tenant.use("alice"):
        _trade(-120)
        assert client.put("/api/loss-limits/ACC1", json={"daily_loss": 100}).status_code == 200
        assert len(_events()) == 1


def test_logging_a_losing_manual_trade_triggers_the_check(db):
    with tenant.use("alice"):
        loss_limits.set_limits("ACC1", 100, None)
        exit_t = datetime.now(timezone.utc)
        body = {
            "account_id": "ACC1", "symbol": "EURUSD", "direction": "BUY", "volume": 1, "entry_price": 1, "exit_price": 1,
            "commission": 0, "swap": 0, "gross_profit": -130,
            "entry_time": (exit_t - timedelta(minutes=5)).isoformat(), "exit_time": exit_t.isoformat(),
        }
        assert client.post("/api/operations/journal/trades", json=body).status_code == 200
        assert len(_events()) == 1


def test_users_with_limits_are_found_by_the_background_watcher(db):
    from api import sync_service
    with tenant.use("carol"):
        loss_limits.set_limits("ACC1", 100, None)
    assert "carol" in sync_service._alert_user_ids()
    with tenant.use("carol"):
        _trade(-150)
    sync_service._check_alerts_for({"carol"})
    with tenant.use("carol"):
        assert len(_events()) == 1
