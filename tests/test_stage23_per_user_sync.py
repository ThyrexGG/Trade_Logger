# -*- coding: utf-8 -*-
"""
W8.6 — per-user broker sync.

A sync cycle is bound to one tenant: a user with saved broker connections
syncs each of them under that tenant; the single-user "local" owner falls back
to the CAPITAL_* env. The heartbeat and the auto-sync toggle are per-user.

Data ingestion only — no order path.
"""
import pytest

import database
import tenant
from api import broker_credentials as bc
from api import sync_service

FAKE_CREDS = {"api_key": "fake-api-key", "email": "u@example.test", "password": "fake-password"}


@pytest.fixture()
def enc(monkeypatch):
    monkeypatch.setenv("TL_CREDENTIAL_ENC_KEY", bc.generate_key())
    database.init_db()
    bc.ensure_table()
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM broker_connections WHERE user_id IN ('alice', 'bob', 'local')")
    cur.execute("DELETE FROM user_settings WHERE user_id IN ('alice', 'bob', 'local')")
    conn.commit()
    conn.close()
    database.invalidate_db_cache()
    sync_service._known_by_user.clear()
    yield
    database.invalidate_db_cache()


# --- per-user settings -------------------------------------------------

def test_user_setting_isolated(enc):
    database.set_user_setting("sync_auto_enabled", "true", user_id="alice")
    assert database.get_user_setting("sync_auto_enabled", "false", user_id="alice") == "true"
    assert database.get_user_setting("sync_auto_enabled", "false", user_id="bob") == "false"
    assert "alice" in database.user_ids_with_setting("sync_auto_enabled", "true")
    assert "bob" not in database.user_ids_with_setting("sync_auto_enabled", "true")


def test_auto_toggle_is_per_user(enc):
    sync_service.set_auto(True, user_id="alice")
    assert sync_service.is_auto_enabled("alice") is True
    assert sync_service.is_auto_enabled("bob") is False


def test_heartbeat_is_per_user(enc, monkeypatch):
    seen = []

    def fake_cycle(known, logfn=None, creds=None):
        seen.append((tenant.current_user_id(), creds))
        return {"errors": [], "mt5_ok": False, "capital_ok": True, "new_closed_trades": 0}

    monkeypatch.setattr(sync_service.auto_sync, "run_sync_cycle", fake_cycle)

    with tenant.use("alice"):
        bc.create_connection(secret=FAKE_CREDS, account_id="A1")

    sync_service.run_for_user("alice", source="test")
    assert sync_service._heartbeat_age_sec("alice") is not None
    assert sync_service._heartbeat_age_sec("bob") is None
    # the cycle ran bound to alice, with alice's creds
    assert seen and seen[0][0] == "alice"
    assert seen[0][1]["api_key"] == "fake-api-key"


def test_run_for_user_without_connection_skips_non_local(enc, monkeypatch):
    monkeypatch.setattr(sync_service.auto_sync, "run_sync_cycle",
                        lambda *a, **k: pytest.fail("must not sync a user with no connection"))
    out = sync_service.run_for_user("bob", source="test")
    assert out.get("skipped") is True and out["reason"] == "no_connection"


def test_local_owner_falls_back_to_env(enc, monkeypatch):
    calls = {"creds": "unset"}

    def fake_cycle(known, logfn=None, creds=None):
        calls["creds"] = creds
        return {"errors": [], "mt5_ok": False, "capital_ok": True, "new_closed_trades": 0}

    monkeypatch.setattr(sync_service.auto_sync, "run_sync_cycle", fake_cycle)
    out = sync_service.run_for_user(tenant.LOCAL_USER_ID, source="test")
    assert out["connections"] == 0
    assert calls["creds"] is None          # env path


def test_run_if_stale_is_per_user(enc, monkeypatch):
    monkeypatch.setattr(sync_service.auto_sync, "run_sync_cycle",
                        lambda *a, **k: {"errors": [], "mt5_ok": False, "capital_ok": True, "new_closed_trades": 0})
    with tenant.use("alice"):
        bc.create_connection(secret=FAKE_CREDS, account_id="A1")

    first = sync_service.run_if_stale(900, user_id="alice")
    assert "ran" in first
    # immediately again -> fresh, skipped
    second = sync_service.run_if_stale(900, user_id="alice")
    assert second.get("skipped") is True and second["reason"] == "fresh"
    # bob is independent — still stale
    monkeypatch.setattr(sync_service.auto_sync, "run_sync_cycle",
                        lambda *a, **k: pytest.fail("bob has no connection"))
    third = sync_service.run_if_stale(900, user_id="bob")
    assert third.get("skipped") is True and third["reason"] == "no_connection"
