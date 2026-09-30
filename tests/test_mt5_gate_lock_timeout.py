# -*- coding: utf-8 -*-
"""
Observed live (2026-09-30): a single MT5 call inside a held mt5_gate.LOCK
session hung indefinitely (the terminal's IPC got stuck), and because every
MT5-touching module used a bare `with LOCK:`, every other request needing
MT5 blocked forever waiting for it too -- their threadpool workers piled up
unreleased until the whole local-fallback server stopped answering ANY
request at all (including plain static pages that never touch MT5), and
stayed stuck until the process was killed and restarted.

mt5_gate.acquire(timeout) exists so a stuck session degrades to "MT5
unavailable this cycle" instead of a total server freeze. This test
reproduces the exact shape of the incident: one thread holds the lock far
longer than any caller should ever wait, and every caller must give up on
its own bounded timeout rather than hang.
"""
import threading
import time

import mt5_gate


def test_acquire_gives_up_instead_of_hanging_behind_a_stuck_holder():
    released = threading.Event()

    def _hog():
        with mt5_gate.acquire(5) as got:
            assert got is True
            released.wait(10)  # simulates an MT5 call that never returns in time

    t = threading.Thread(target=_hog, daemon=True)
    t.start()
    try:
        time.sleep(0.3)  # let the hog actually acquire first

        start = time.perf_counter()
        with mt5_gate.acquire(1.0) as got:
            elapsed = time.perf_counter() - start
            assert got is False  # gave up, did NOT wait for the holder
            assert elapsed < 2.0  # bounded by ITS OWN timeout, not the holder's
    finally:
        released.set()
        t.join(timeout=5)


def test_acquire_succeeds_once_the_holder_releases():
    def _quick_holder():
        with mt5_gate.acquire(5) as got:
            assert got is True
            time.sleep(0.2)

    t = threading.Thread(target=_quick_holder, daemon=True)
    t.start()
    time.sleep(0.05)

    with mt5_gate.acquire(2.0) as got:
        assert got is True  # the holder released well within this timeout
    t.join(timeout=5)


def test_guarded_initialize_returns_false_without_touching_mt5_if_lock_busy(monkeypatch):
    released = threading.Event()

    def _hog():
        with mt5_gate.acquire(5):
            released.wait(10)

    t = threading.Thread(target=_hog, daemon=True)
    t.start()
    try:
        time.sleep(0.3)
        called = {"initialize": False}
        fake_mt5 = type("_M", (), {"initialize": staticmethod(lambda **k: called.__setitem__("initialize", True) or True)})
        assert mt5_gate.guarded_initialize(fake_mt5, lock_timeout=1.0) is False
        assert called["initialize"] is False  # never even tried -- the lock itself is the thing that was busy
    finally:
        released.set()
        t.join(timeout=5)
