# -*- coding: utf-8 -*-
"""
Phase 65 — FRED live smoke test.

SKIPPED unless `FRED_API_KEY` is present in the environment. When it runs it
makes a small number of real calls (a handful of series), verifies normalization
and lookahead, and records coverage/latency. It never prints the key and never
hammers the API (the provider's 6h in-process cache means one hydrate).
"""
import os
import time

import pytest

pytestmark = pytest.mark.skipif(
    not (os.getenv("FRED_API_KEY") or "").strip(),
    reason="LIVE PROVIDER SMOKE TEST NOT RUN — NO CREDENTIALS CONFIGURED (set FRED_API_KEY)",
)


def test_fred_live_smoke(monkeypatch, capsys):
    monkeypatch.setenv("MACRO_DATA_PROVIDER", "fred")
    from api.providers import fred_provider as fp
    from macro_intelligence_engine import EconomicDataRegistry

    fp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False

    t0 = time.perf_counter()
    st = fp.FredMacroProvider().hydrate_registry(force=True)
    elapsed = time.perf_counter() - t0

    assert st["provider_state"] in ("LIVE", "LIVE_STALE"), st
    assert st["records_registered"] > 0

    recs = EconomicDataRegistry._RELEASES
    countries = sorted({r.country for r in recs})
    metrics = sorted({r.metric for r in recs})

    # every live record must be authoritative and forecast-free
    for r in recs:
        assert r.source.startswith("FRED:")
        assert r.forecast is None
        assert r.actual is not None
        assert r.release_timestamp.endswith("Z")

    # lookahead sanity against the real data
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    visible = EconomicDataRegistry.get_releases_as_of(as_of=now)
    assert all(r.release_timestamp <= now.isoformat().replace("+00:00", "Z") for r in visible)

    with capsys.disabled():
        print(f"\n  FRED live smoke: {elapsed:.1f}s  |  {st['records_registered']} records")
        print(f"  countries: {countries}")
        print(f"  metrics:   {metrics}")
        print(f"  coverage:  {st['coverage']}")
        if st["series_errors"]:
            print(f"  series not available: {st['series_errors']}")
