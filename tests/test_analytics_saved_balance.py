# -*- coding: utf-8 -*-
"""
Saved starting balance (Analytics) — persists across a reload.

Before this, "Starting balance" was a plain React state initialised to
10000 on every mount: nothing was ever written back to the server, so a
value someone typed in was gone the moment they refreshed. POST
.../initial-balance stores it (scoped by tenant + account, via the
existing generic app_settings key-value table); GET .../performance's
`available.saved_initial_balance` is how the frontend restores it, taking
priority over the auto-detected suggestion since it's what the user
actually said, not a guess.
"""
from fastapi.testclient import TestClient

import database
from api.main import app

client = TestClient(app)

_ACCOUNT = "TEST_SAVEDBAL_ACCOUNT_1"


def _seed():
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(
            f"INSERT INTO closed_trades (trade_id, account_id, symbol, direction, volume, "
            f"entry_price, exit_price, entry_time, exit_time) VALUES "
            f"({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            ("TEST_SAVEDBAL_TRADE_1", _ACCOUNT, "EURUSD", "BUY", 0.1, 1.1000, 1.1010,
             "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"))
        conn.commit()
    finally:
        conn.close()
    database.invalidate_db_cache("closed_trades")


def _cleanup():
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"DELETE FROM closed_trades WHERE account_id = {ph}", (_ACCOUNT,))
        cur.execute("DELETE FROM app_settings WHERE key LIKE 'analytics_initial_balance::%'")
        conn.commit()
    finally:
        conn.close()
    database.invalidate_db_cache("closed_trades")


def test_saved_balance_round_trips_and_wins_over_suggestion():
    _cleanup()
    _seed()
    try:
        before = client.get(f"/api/analytics/performance?account={_ACCOUNT}").json()
        assert before["available"]["saved_initial_balance"] is None

        r = client.post("/api/analytics/initial-balance", params={"account": _ACCOUNT, "value": 4242.5})
        assert r.status_code == 200
        assert r.json() == {"account": _ACCOUNT, "initial_balance": 4242.5}

        after = client.get(f"/api/analytics/performance?account={_ACCOUNT}").json()
        assert after["available"]["saved_initial_balance"] == 4242.5
    finally:
        _cleanup()


def test_saved_balance_rejects_non_positive_values():
    r = client.post("/api/analytics/initial-balance", params={"account": _ACCOUNT, "value": 0})
    assert r.status_code == 422
    r2 = client.post("/api/analytics/initial-balance", params={"account": _ACCOUNT, "value": -50})
    assert r2.status_code == 422


def test_saving_for_one_account_does_not_leak_into_another():
    _cleanup()
    _seed()
    other = "TEST_SAVEDBAL_ACCOUNT_2"
    try:
        client.post("/api/analytics/initial-balance", params={"account": _ACCOUNT, "value": 999.0})
        # `other` is unknown to the population -> 422, but the point here is
        # just that the setting key itself is per-account, not global; check
        # directly rather than through the (irrelevant) account-existence gate.
        from api.routers.analytics import _get_saved_initial_balance
        assert _get_saved_initial_balance(_ACCOUNT) == 999.0
        assert _get_saved_initial_balance(other) is None
    finally:
        _cleanup()
