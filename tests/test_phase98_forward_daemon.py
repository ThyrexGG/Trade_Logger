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
import re
import sys
from datetime import datetime, timedelta, timezone

import phase98_forward_daemon as d


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
        return _P()

    monkeypatch.setattr(d.subprocess, "run", fake_run)
    assert d.run_harness() == 0
    assert captured["cmd"][:2] == [sys.executable, "-m"]
    assert captured["cmd"][2] == "phase98_carry_forward_evidence"
    assert "--refresh" in captured["cmd"]


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
