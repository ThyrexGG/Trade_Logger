# -*- coding: utf-8 -*-
"""
Phase 66 — consensus-forecast live smoke test.

No free authoritative consensus-forecast source is configured (see
``api/providers/forecast_provider.py``). Unless one is wired up and its
credentials provided, this test does not run.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("MACRO_FORECAST_SMOKE_KEY"),
    reason="LIVE SMOKE TEST NOT RUN — CREDENTIALS NOT CONFIGURED",
)


def test_forecast_live_smoke():  # pragma: no cover - only with a real provider
    from api.providers.forecast_provider import get_forecast_provider

    p = get_forecast_provider()
    assert p.configured
    fcs = p.get_forecasts()
    assert isinstance(fcs, list)
    for fc in fcs[:5]:
        assert fc.indicator and fc.country and fc.period
        # a real provider must not fabricate — forecast may legitimately be None
        assert fc.forecast is None or isinstance(fc.forecast, (int, float))
