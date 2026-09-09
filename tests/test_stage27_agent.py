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
    assert cfg["supabase_url"].startswith("https://")
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
    assert agent.config_status(cfg) == (True, "supabase")


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
