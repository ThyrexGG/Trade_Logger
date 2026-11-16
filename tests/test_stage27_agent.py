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


# --- run log (2026-11-11: the hidden scheduled task printed into the void, so "my sync stopped" could not be
# diagnosed afterwards). Everything an automatic run prints is mirrored into mt5_sync.log. ---------------------
def _fresh_log(agent, monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "app_dir", lambda: tmp_path)
    monkeypatch.setattr(agent, "_run_log", None)
    monkeypatch.setattr("sys.stdout", None)    # pythonw.exe: no stdout at all
    monkeypatch.setattr("sys.stderr", None)


def test_run_log_captures_prints_even_with_no_stdout(agent, monkeypatch, tmp_path):
    _fresh_log(agent, monkeypatch, tmp_path)
    agent.start_run_log("once")
    print("MetaTrader 5 isn't open - skipping this sync")      # goes through the tee into the file
    agent._log_line("--- run ended (ok)")
    text = (tmp_path / "mt5_sync.log").read_text(encoding="utf-8")
    assert "run started" in text and "once" in text
    assert "MetaTrader 5 isn't open - skipping this sync" in text
    assert "run ended (ok)" in text


def test_run_log_rotates_past_the_cap(agent, monkeypatch, tmp_path):
    (tmp_path / "mt5_sync.log").write_text("x" * (agent._LOG_MAX_BYTES + 10), encoding="utf-8")
    _fresh_log(agent, monkeypatch, tmp_path)
    agent.start_run_log("once")
    assert (tmp_path / "mt5_sync.log.1").exists()
    assert (tmp_path / "mt5_sync.log").stat().st_size < 1000


def test_run_log_failure_never_breaks_a_sync(agent, monkeypatch, tmp_path):
    _fresh_log(agent, monkeypatch, tmp_path / "does" / "not" / "exist")    # unwritable folder
    agent.start_run_log("once")                                            # must not raise
    print("still prints fine")
    agent._log_line("ignored")


def test_the_task_is_allowed_to_run_on_battery(agent):
    # schtasks /Create defaults to "don't start on batteries": on a laptop the sync silently stopped whenever
    # the charger was out. install_task() must clear it after creating the task.
    src = _AGENT.read_text(encoding="utf-8")
    assert "DisallowStartIfOnBatteries=$false" in src
    assert src.index("_allow_task_on_battery()") < src.index("write_uninstall_shortcut()", src.index("def install_task"))


def test_a_lock_left_by_a_dead_run_does_not_block_sync_now(agent, tmp_path, monkeypatch):
    """2026-11-16: a run died mid-sync without clearing .sync.lock, and every "Sync now" for
    the next 10 minutes said "another sync is already running" and did nothing."""
    import os
    monkeypatch.setattr(agent, "app_dir", lambda: tmp_path)
    lock = tmp_path / ".sync.lock"
    lock.write_text("999999999", encoding="utf-8")  # fresh lock, no such process
    got = agent._acquire_run_lock()
    assert got == lock and lock.read_text(encoding="utf-8") == str(os.getpid())
    agent._release_run_lock(got)


def test_a_lock_held_by_a_live_run_still_blocks(agent, tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(agent, "app_dir", lambda: tmp_path)
    (tmp_path / ".sync.lock").write_text(str(os.getppid()), encoding="utf-8")
    assert agent._pid_alive(os.getpid())
    assert agent._acquire_run_lock() is None
