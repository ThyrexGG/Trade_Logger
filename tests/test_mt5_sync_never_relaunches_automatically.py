# -*- coding: utf-8 -*-
"""
A recurring automatic sync (the in-process loop's "auto"/"open" sources, the
standalone daemon) must NEVER be the reason MetaTrader pops open -- that was
the original 2026-09 bug (fixed for market_data.py/account_state.py's passive
reads this session), and turning on continuous auto-sync in the local
fallback reintroduced it through a THIRD path: mt5_sync.sync_mt5() itself,
called every 60s, was still willing to launch a closed terminal (minimized,
but still a launch -- and closing it again just meant it came back within a
minute). Only a genuine one-off "Sync now" click may still launch it.
"""
import auto_sync
import mt5_gate
import mt5_sync


def test_sync_mt5_skips_instead_of_launching_when_required_already_running(monkeypatch):
    monkeypatch.setattr(mt5_gate, "is_mt5_enabled", lambda: True)
    monkeypatch.setattr(mt5_gate, "mt5_terminal_running", lambda: False)
    called = {"guarded_initialize": False}
    monkeypatch.setattr(mt5_gate, "guarded_initialize", lambda *a, **k: called.__setitem__("guarded_initialize", True) or True)

    assert mt5_sync.sync_mt5(require_already_running=True) is False
    assert called["guarded_initialize"] is False  # never even tried to connect, let alone launch


def test_sync_mt5_may_still_launch_for_a_manual_sync(monkeypatch):
    monkeypatch.setattr(mt5_gate, "is_mt5_enabled", lambda: True)
    monkeypatch.setattr(mt5_gate, "mt5_terminal_running", lambda: False)
    called = {"guarded_initialize": False}

    def _fake_guarded_initialize(mt5_module, **kwargs):
        called["guarded_initialize"] = True
        return False  # simulate "couldn't connect" so the function returns early, not a full fake sync

    monkeypatch.setattr(mt5_gate, "guarded_initialize", _fake_guarded_initialize)
    monkeypatch.setattr(mt5_sync, "mt5", type("_M", (), {"shutdown": staticmethod(lambda: None), "last_error": staticmethod(lambda: (0, "ok"))}))

    assert mt5_sync.sync_mt5(require_already_running=False) is False
    assert called["guarded_initialize"] is True  # a manual sync IS allowed to attempt a connect/launch


def test_run_sync_cycle_passes_require_flag_through_to_sync_mt5(monkeypatch):
    seen = {}

    def _fake_sync_mt5(require_already_running=False):
        seen["require_already_running"] = require_already_running
        return True

    monkeypatch.setattr(auto_sync.mt5_sync, "sync_mt5", _fake_sync_mt5)
    monkeypatch.setattr(auto_sync, "mt5_gate", type("_G", (), {"is_mt5_enabled": staticmethod(lambda: True)}), raising=False)
    import mt5_gate as real_mt5_gate
    monkeypatch.setattr(real_mt5_gate, "is_mt5_enabled", lambda: True)
    monkeypatch.setattr(auto_sync.capital_sync, "sync_capital", lambda creds=None: False)
    monkeypatch.setattr(auto_sync.database, "get_closed_trades", lambda **k: __import__("pandas").DataFrame())

    auto_sync.run_sync_cycle(set(), logfn=lambda _m: None, require_mt5_already_running=True)
    assert seen["require_already_running"] is True

    auto_sync.run_sync_cycle(set(), logfn=lambda _m: None, require_mt5_already_running=False)
    assert seen["require_already_running"] is False
