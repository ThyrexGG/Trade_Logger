# -*- coding: utf-8 -*-
"""
Phase 66 — CFTC COT live smoke test.

The CFTC public reporting API needs no key, so this CAN run for real — but it
hits the network, so it is gated behind ``RUN_LIVE_SMOKE=1`` to keep the normal
suite fully offline. It never prints a secret (there is none) and pulls only a
small, bounded slice.

    RUN_LIVE_SMOKE=1 pytest tests/test_phase66_cftc_smoke.py -s
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_SMOKE") != "1",
    reason="LIVE PROVIDER SMOKE TEST NOT RUN — set RUN_LIVE_SMOKE=1 to hit the real CFTC API",
)


def test_cftc_live_smoke(monkeypatch):
    monkeypatch.setenv("MACRO_COT_PROVIDER", "cftc")
    monkeypatch.setenv("CFTC_CACHE_TTL_SEC", "0")
    monkeypatch.setenv("CFTC_HISTORY_WEEKS", "3")
    from api.providers import cftc_provider as cp
    from macro_intelligence_engine import EconomicDataRegistry

    cp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False

    st = cp.CftcCotProvider().hydrate_registry(force=True)
    print("\nCFTC live:", {k: st[k] for k in ("provider_state", "records_registered",
                                              "coverage", "latency_ms")})
    assert st["provider_state"] in ("LIVE", "LIVE_STALE"), st
    assert st["records_registered"] > 0
    assert "USD" in st["coverage"]

    obs = cp.CftcCotProvider().get_observations()
    o = obs[0]
    assert o["source"].startswith("CFTC:")
    assert o["release_timestamp"].endswith("Z")
    assert o["non_commercial_net"] == o["non_commercial_long"] - o["non_commercial_short"]
    assert o["report_date"] < o["release_timestamp"][:10]
    print("sample:", {k: o[k] for k in ("country", "report_date", "release_timestamp",
                                        "non_commercial_net", "open_interest")})

    cp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
