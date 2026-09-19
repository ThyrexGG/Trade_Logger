# -*- coding: utf-8 -*-
"""Price alerts fire from real prices only, without MT5 or a broker connection."""
import sqlite3

import pytest

import auto_sync
import database
import market_data
import tenant
import trade_notify
from api import sync_service


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "alerts.db")
    monkeypatch.setattr(database, "get_db_url", lambda: None)
    monkeypatch.setattr(database, "get_connection", lambda: sqlite3.connect(path, timeout=30))
    monkeypatch.setattr(database, "_DB_INITIALIZED", False)
    monkeypatch.setattr(database, "_PUSH_TABLES_READY", False)
    database.init_db(force=True)
    monkeypatch.setattr(auto_sync.mt5_sync, "MT5_AVAILABLE", False)
    monkeypatch.setattr(auto_sync.alerts, "notify_price_alert", lambda *a, **k: sent_global.append(a))
    sent_global.clear()
    return path


sent_global: list = []


def _fire_prices(monkeypatch, prices):
    monkeypatch.setattr(market_data, "get_verified_price", lambda sym, *a, **k: prices.get(sym))


def test_alert_fires_from_a_real_price_and_records_the_event(db, monkeypatch):
    _fire_prices(monkeypatch, {"XAUUSD": 4010.0})
    with tenant.use("alice"):
        aid = database.create_price_alert("XAUUSD", 4000, "ABOVE")
        assert auto_sync.check_price_alerts(logfn=lambda _m: None) == 1
        assert database.get_active_price_alerts() == []
        kinds = [e["kind"] for e in database.list_trade_events()]
        assert kinds == ["alert"] and aid
        assert auto_sync.check_price_alerts(logfn=lambda _m: None) == 0  # only once


def test_no_real_price_means_no_alert(db, monkeypatch):
    _fire_prices(monkeypatch, {})  # feeds down / unknown symbol -> None
    with tenant.use("alice"):
        database.create_price_alert("XAUUSD", 100000, "BELOW")
        assert auto_sync.check_price_alerts(logfn=lambda _m: None) == 0
        assert len(database.get_active_price_alerts()) == 1


def test_wrong_side_of_the_target_does_not_fire(db, monkeypatch):
    _fire_prices(monkeypatch, {"EURUSD": 1.08})
    with tenant.use("alice"):
        database.create_price_alert("EURUSD", 1.09, "ABOVE")
        database.create_price_alert("EURUSD", 1.07, "BELOW")
        assert auto_sync.check_price_alerts(logfn=lambda _m: None) == 0


def test_other_users_alert_never_uses_the_owners_global_channels(db, monkeypatch):
    _fire_prices(monkeypatch, {"XAUUSD": 4010.0})
    monkeypatch.setattr(sync_service, "_env_fallback_ok", lambda uid: uid == "owner")
    with tenant.use("friend"):
        database.create_price_alert("XAUUSD", 4000, "ABOVE")
        assert auto_sync.check_price_alerts(logfn=lambda _m: None) == 1
    assert sent_global == []           # nothing posted to the owner's Telegram/Discord/toast
    with tenant.use("owner"):
        database.create_price_alert("XAUUSD", 4000, "ABOVE")
        assert auto_sync.check_price_alerts(logfn=lambda _m: None) == 1
    assert len(sent_global) == 1


def test_server_watcher_checks_users_with_no_broker_connection(db, monkeypatch):
    _fire_prices(monkeypatch, {"XAUUSD": 4010.0})
    with tenant.use("carol"):
        database.create_price_alert("XAUUSD", 4000, "ABOVE")
    assert sync_service._alert_user_ids() == ["carol"]
    sync_service._check_alerts_for({"carol"})
    with tenant.use("carol"):
        assert database.get_active_price_alerts() == []
    assert sync_service._alert_user_ids() == []


def test_verified_price_refuses_placeholder_data(monkeypatch):
    monkeypatch.setattr(market_data, "_fmp_quote", lambda sym: None)
    monkeypatch.setattr(market_data, "get_candles_with_source",
                        lambda *a, **k: ([{"close": 2514.8}], "synthetic_fallback"))
    assert market_data.get_verified_price("XAUUSD") is None
    monkeypatch.setattr(market_data, "get_candles_with_source",
                        lambda *a, **k: ([{"close": 3912.5}], "yahoo"))
    assert market_data.get_verified_price("XAUUSD") == 3912.5
    monkeypatch.setattr(market_data, "_fmp_quote", lambda sym: 3915.0)
    assert market_data.get_verified_price("XAUUSD") == 3915.0
