# -*- coding: utf-8 -*-
"""
Phase 98 forward-evidence daemon (scheduler wrapper).

Covers: the "is a weekly run due" logic (no snapshot -> due; recent
snapshot -> not due; old snapshot -> due; unreadable -> due), run_once
no-op vs invoke, --force, the --status path, and that the wrapper carries
no strategy/execution logic and shells out to the harness with --refresh.
The harness subprocess is stubbed.
"""
import inspect
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import pytest

import legacy.phase98_forward_daemon as d


@pytest.fixture(autouse=True)
def _isolated_log(tmp_path, monkeypatch):
    """Every path through this daemon logs (`_log()` unconditionally appends to `d._LOG`), and only
    `subprocess.run` is mocked below -- without this, every test run silently appended real lines (in
    one case, the literal fixture text "OVERALL: X\\nartifact: y") to the real phase98_daemon_log.txt at
    the repo root. That's what the garbled entries throughout that file's real history actually were."""
    monkeypatch.setattr(d, "_LOG", str(tmp_path / "test_daemon_log.txt"))


def _hist(days_ago):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {"snapshot_history": [{"snapshot_key": "s", "captured_at": ts, "verdict": "X"}]}


# --- A. due logic -------------------------------------------------------
def test_due_when_no_snapshot(monkeypatch):
    monkeypatch.setattr("phase98_carry_forward_evidence.get_result", lambda: None, raising=False)
    assert d._last_snapshot_age_days() is None
    assert d.is_due() is True


def test_not_due_when_snapshot_recent(monkeypatch):
    monkeypatch.setattr("phase98_carry_forward_evidence.get_result", lambda: _hist(2), raising=False)
    assert 1.5 < d._last_snapshot_age_days() < 2.5
    assert d.is_due() is False


def test_due_when_snapshot_old(monkeypatch):
    monkeypatch.setattr("phase98_carry_forward_evidence.get_result", lambda: _hist(9), raising=False)
    assert d.is_due() is True


def test_due_when_store_unreadable(monkeypatch):
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr("phase98_carry_forward_evidence.get_result", boom, raising=False)
    assert d.is_due() is True


# --- B. run_once -----------------------------------------------------
def test_run_once_noop_when_not_due(monkeypatch):
    monkeypatch.setattr("phase98_carry_forward_evidence.get_result", lambda: _hist(1), raising=False)
    called = {"n": 0}
    monkeypatch.setattr(d, "run_harness", lambda: called.__setitem__("n", called["n"] + 1) or 0)
    assert d.run_once() == 0
    assert called["n"] == 0


def test_run_once_invokes_when_due(monkeypatch):
    monkeypatch.setattr("phase98_carry_forward_evidence.get_result", lambda: _hist(10), raising=False)
    called = {"n": 0}
    monkeypatch.setattr(d, "run_harness", lambda: called.__setitem__("n", called["n"] + 1) or 0)
    assert d.run_once() == 0
    assert called["n"] == 1


def test_run_once_force_runs_even_when_not_due(monkeypatch):
    monkeypatch.setattr("phase98_carry_forward_evidence.get_result", lambda: _hist(0.1), raising=False)
    called = {"n": 0}
    monkeypatch.setattr(d, "run_harness", lambda: called.__setitem__("n", called["n"] + 1) or 0)
    d.run_once(force=True)
    assert called["n"] == 1


# --- C. harness invocation --------------------------------------
def test_run_harness_shells_out_with_refresh(monkeypatch):
    captured = {}

    class _P:
        returncode = 0
        stdout = "OVERALL: X\nartifact: y"
        stderr = ""

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["kw"] = kw
        return _P()

    monkeypatch.setattr(d.subprocess, "run", fake_run)
    assert d.run_harness() == 0
    assert captured["cmd"][:2] == [sys.executable, "-m"]
    assert captured["cmd"][2] == "phase98_carry_forward_evidence"
    assert "--refresh" in captured["cmd"]
    # This file lives in legacy/, but the harness module it shells out to lives at the repo root -- the
    # subprocess must run from there (and `python -m phase98_carry_forward_evidence` must be able to find
    # it), or every invocation fails with "module not found" while the daemon itself still exits 0.
    # A previous version passed legacy/ here and the daily scheduled task silently failed for 6 days.
    assert os.path.isfile(os.path.join(captured["kw"]["cwd"], "phase98_carry_forward_evidence.py"))


def test_log_file_is_at_the_repo_root_not_in_legacy():
    # _LOG itself is monkeypatched away by the autouse fixture above (so tests never touch the real log);
    # _REPO_ROOT is what it's built from, and that must still point one level up from legacy/.
    assert d._REPO_ROOT == os.path.dirname(os.path.dirname(os.path.abspath(d.__file__)))
    assert os.path.isfile(os.path.join(d._REPO_ROOT, "phase98_carry_forward_evidence.py"))


def test_status_mode(monkeypatch, capsys):
    monkeypatch.setattr("phase98_carry_forward_evidence.get_result", lambda: _hist(3), raising=False)
    assert d.main(["--status"]) == 0
    out = capsys.readouterr().out
    assert "due now:" in out


# --- D. safety -------------------------------------------------
def test_wrapper_has_no_strategy_or_execution_logic():
    src = inspect.getsource(d)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    for f in ("order_execution", "broker_adapter", "execution_pipeline", "phase96", "phase97",
              "historical_data_store", "account_management"):
        assert not any(re.search(rf"\b{f}\b", l) for l in import_lines), f"unexpected import: {f}"
    for token in ("run_carry", "place_order", "submit_order", "def classify", "np.", "pd."):
        assert token not in src, f"strategy-ish token in wrapper: {token}"
