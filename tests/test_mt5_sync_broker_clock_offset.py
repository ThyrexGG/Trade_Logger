# -*- coding: utf-8 -*-
"""
mt5_sync.py -- the second, separate MT5 read path (the local "Sync now" /
in-process auto-sync loop), distinct from the standalone push-agent
(agent/mt5_push_agent.py, covered by tests/test_stage27_agent.py). Both talk
to MT5 directly and both were exposed to the same bug: MT5's position/deal
``.time`` is the BROKER SERVER's wall clock, epoch-encoded as if it were true
UTC. 5c22ba9 fixed this for the push-agent only; mt5_sync.py kept storing the
raw, uncorrected value, so a trade could still be bucketed under the wrong
calendar day when synced through this path (local fallback, in-process auto
sync, the "Sync now" button).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import mt5_gate
import mt5_sync


def test_sync_mt5_corrects_the_broker_clock_offset(monkeypatch):
    mt5_gate._server_utc_offset_sec = 0
    mt5_gate._server_utc_offset_checked_at = 0.0

    true_now = int(time.time())
    offset = 10800  # broker is UTC+3, matching the real FundedNext account this was found on
    event_true_utc = true_now - 600  # closed 10 minutes ago, in real UTC

    class _Tick:
        time = true_now + offset

    class _Acc:
        login = 14271408
        balance = 100.0
        equity = 100.0
        currency = "USD"
        company = "FundedNext Ltd"

    class _Pos:
        ticket = 1
        symbol = "NDX100"
        type = 1
        volume = 0.09
        price_open = 30353.79
        price_current = 30264.49
        sl = 0.0
        tp = 0.0
        profit = 80.37
        swap = 0.0
        time = event_true_utc + offset  # broker-clock-labeled, as MT5 actually returns it

    class _Deal:
        ticket = 2
        symbol = "NDX100"
        type = 1
        volume = 0.09
        price = 30264.49
        commission = 0.0
        swap = 0.0
        profit = 80.37
        time = event_true_utc + offset
        position_id = 1

    fake_mt5 = type("_M", (), {
        "shutdown": staticmethod(lambda: None),
        "initialize": staticmethod(lambda *a, **k: True),
        "account_info": staticmethod(lambda: _Acc()),
        "positions_get": staticmethod(lambda: [_Pos()]),
        "history_deals_get": staticmethod(lambda *_a, **_k: [_Deal()]),
        "symbol_select": staticmethod(lambda *_a, **_k: True),
        "symbol_info_tick": staticmethod(lambda *_a, **_k: _Tick()),
        "last_error": staticmethod(lambda: (0, "ok")),
    })
    monkeypatch.setattr(mt5_sync, "mt5", fake_mt5)
    monkeypatch.setattr(mt5_sync, "MT5_AVAILABLE", True)
    monkeypatch.setattr(mt5_gate, "is_mt5_enabled", lambda: True)
    monkeypatch.setattr(mt5_sync.database, "init_db", lambda *a, **k: None)
    monkeypatch.setattr(mt5_sync.database, "get_last_deal_timestamp", lambda *a, **k: 0)

    captured = {}

    def _fake_ingest(account_id, balance, positions, deals, logfn=print):
        captured["positions"] = positions
        captured["deals"] = deals
        return {"raw_deals": len(deals), "closed_trades": 0, "open_positions": len(positions)}

    monkeypatch.setattr(mt5_sync, "ingest_mt5_payload", _fake_ingest)

    assert mt5_sync.sync_mt5() is True

    assert captured["positions"][0]["open_time"] == datetime.fromtimestamp(
        event_true_utc, tz=timezone.utc
    ).isoformat()
    assert captured["deals"][0]["timestamp"] == event_true_utc
