# -*- coding: utf-8 -*-
"""
W9 — MT5 sync agent (``agent/mt5_push_agent.py``).

The agent is a standalone client that ships as a Windows .exe; most of it
needs MetaTrader + Windows to exercise. These tests cover the pure pieces:
config merging, the "is it set up yet" check, and the hidden-VBS launcher
string (a quoting bug there would silently break every friend's schedule).
"""
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

_AGENT = Path(__file__).resolve().parents[1] / "agent" / "mt5_push_agent.py"


@pytest.fixture(scope="module")
def agent():
    spec = importlib.util.spec_from_file_location("mt5_push_agent", _AGENT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_defaults_load_without_a_config_file(agent, tmp_path):
    cfg = agent.load_config(tmp_path / "nope.json")
    assert cfg["server_url"].startswith("https://")
    assert cfg["poll_minutes"] == 15
    # nothing personal yet -> not complete
    assert agent.config_status(cfg) == (False, "")


def test_config_file_overrides_and_completes(agent, tmp_path):
    p = tmp_path / "mt5_agent_config.json"
    p.write_text(json.dumps({
        "_comment": "ignored",
        "email": "friend@example.com",
        "password": "hunter2",
        "poll_minutes": 30,
        "server_url": "https://example.test/",
    }), encoding="utf-8")
    cfg = agent.load_config(p)
    assert cfg["server_url"] == "https://example.test"     # trailing slash trimmed
    assert cfg["poll_minutes"] == 30
    assert "_comment" not in cfg
    assert agent.config_status(cfg) == (True, "multiuser")


def test_passphrase_mode_is_complete_without_supabase(agent, tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"passphrase": "shared-secret"}), encoding="utf-8")
    cfg = agent.load_config(p)
    assert agent.config_status(cfg) == (True, "passphrase")


def test_bad_json_config_exits(agent, tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{ not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        agent.load_config(p)


def test_poll_minutes_floor(agent, tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"poll_minutes": 1}), encoding="utf-8")
    assert agent.load_config(p)["poll_minutes"] == 5


def test_vbs_launcher_quotes_are_doubled(agent):
    line = agent._vbs_line(r'"C:\Program Files\tradelogger-mt5-sync.exe" --once')
    # VBS escapes a double-quote by doubling it; the whole command is one
    # string argument to .Run
    assert line.startswith('CreateObject("WScript.Shell").Run "')
    assert line.rstrip().endswith('", 0, False')
    assert '""C:\\Program Files\\tradelogger-mt5-sync.exe"" --once' in line
    # exactly one .Run call, one line
    assert line.count("\n") == 1


def test_runner_command_targets_once(agent):
    cmd = agent._runner_command()
    assert cmd.endswith("--once")
    assert cmd.count('"') >= 2      # the executable path is quoted


def test_sync_once_skips_without_launching_when_mt5_closed(agent, monkeypatch):
    """The automatic paths (--once / --daemon) pass require_already_running=True
    so a closed MT5 terminal means "no more trades to catch", not "launch it
    for me" — mt5_connect() (which would call mt5.initialize() and start a
    fresh terminal) must never be reached in that case."""
    monkeypatch.setattr(agent, "_mt5_pids", lambda: set())

    def _boom(*_a, **_k):
        raise AssertionError("mt5_connect() should not be called when MT5 isn't running")

    monkeypatch.setattr(agent, "mt5_connect", _boom)
    agent.sync_once({}, auth=None, require_already_running=True)  # must return quietly, not raise


def test_sync_once_still_connects_when_not_required(agent, monkeypatch):
    """A manual/explicit sync (require_already_running=False, the default —
    what the wizard's own first sync uses) keeps the old behaviour of letting
    mt5_connect() launch MT5 if it isn't open."""
    monkeypatch.setattr(agent, "_mt5_pids", lambda: set())
    called = []
    monkeypatch.setattr(agent, "mt5_connect", lambda cfg: called.append(cfg))

    class _Boom(Exception):
        pass

    monkeypatch.setattr(agent, "mt5", type("_M", (), {
        "account_info": staticmethod(lambda: (_ for _ in ()).throw(_Boom())),
        "shutdown": staticmethod(lambda: None),
    }))
    with pytest.raises(_Boom):
        agent.sync_once({}, auth=None, require_already_running=False)
    assert called == [{}]  # mt5_connect *was* reached this time


def test_read_snapshot_corrects_the_broker_clock_offset(agent, monkeypatch):
    """MT5's position/deal .time is the BROKER SERVER's wall clock, epoch-encoded as if it
    were true UTC -- not a real UTC instant. A broker sitting 2h ahead of UTC would
    otherwise store an entry/exit time 2h late, which is enough to flip a trade near
    midnight onto the wrong calendar day once the frontend converts it to the viewer's own
    timezone. read_snapshot() must detect that offset (via a live tick vs this machine's
    real wall clock) and subtract it back out of every stored timestamp."""
    monkeypatch.setattr(agent, "_server_offset_sec", 0)
    monkeypatch.setattr(agent, "_server_offset_checked_at", 0.0)

    true_now = int(time.time())
    offset = 7200  # broker is UTC+2
    event_true_utc = true_now - 3600  # something that closed "an hour ago", in real UTC

    class _Tick:
        time = true_now + offset

    class _Acc:
        login = 14271408
        balance = 100.0
        equity = 100.0
        currency = "USD"

    class _Pos:
        ticket = 1
        symbol = "EURUSD"
        type = 0
        volume = 1.0
        price_open = 1.1
        price_current = 1.11
        sl = 0.0
        tp = 0.0
        profit = 5.0
        swap = 0.0
        time = event_true_utc + offset  # broker-clock-labeled, as MT5 actually returns it

    class _Deal:
        ticket = 2
        symbol = "EURUSD"
        type = 0
        volume = 1.0
        price = 1.1
        commission = 0.0
        swap = 0.0
        profit = 5.0
        time = event_true_utc + offset
        position_id = 1

    fake_mt5 = type("_M", (), {
        "account_info": staticmethod(lambda: _Acc()),
        "positions_get": staticmethod(lambda: [_Pos()]),
        "history_deals_get": staticmethod(lambda *_a, **_k: [_Deal()]),
        "symbol_select": staticmethod(lambda *_a, **_k: True),
        "symbol_info_tick": staticmethod(lambda *_a, **_k: _Tick()),
    })
    monkeypatch.setattr(agent, "mt5", fake_mt5)

    snap = agent.read_snapshot(0)

    assert agent.server_utc_offset_sec() == offset
    assert snap["positions"][0]["open_time"] == datetime.fromtimestamp(
        event_true_utc, tz=timezone.utc
    ).isoformat()
    assert snap["deals"][0]["timestamp"] == event_true_utc
