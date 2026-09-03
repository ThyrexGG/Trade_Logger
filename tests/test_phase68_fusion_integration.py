# -*- coding: utf-8 -*-
"""
Phase 68 — historical market evidence flowing into the Phase-67 fusion layer.

The canonical evidence model / semantics are unchanged (no competing model). What
changes: TECHNICAL / SMC / SEASONALITY / REGIME now carry real candle-derived
evidence when a candle window resolves, and a deterministic prior — when used —
is explicitly labelled and never counts as observed market evidence.
"""
import math
from datetime import datetime, timezone

import pytest

import historical_market_data as hmd
import api.evidence_fusion as fusion
from api.evidence_model import EvidenceState


def _prov(slope=0.12):
    def prov(asset, tf, as_of_epoch, lookback):
        tf_sec = hmd.tf_seconds(tf)
        n = lookback + 80
        rows = []
        for i in range(n):
            t = as_of_epoch - (n - i) * tf_sec
            px = 100.0 + i * slope + 2.0 * math.sin(i / 8.0)
            rows.append({"time": int(t), "open": px - 0.05, "high": px + 0.4,
                         "low": px - 0.4, "close": px, "volume": 1000 + (i % 40)})
        return rows
    return prov


@pytest.fixture(autouse=True)
def _clean():
    hmd._reset_live_feed_state()
    hmd.set_test_provider(None)
    fusion.invalidate()
    yield
    hmd.set_test_provider(None)
    hmd._reset_live_feed_state()
    fusion.invalidate()


T = datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)


def test_historical_technical_enters_fusion_as_real_evidence():
    hmd.set_test_provider(_prov(0.15))
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=T)
    tech = snap.category("TECHNICAL")
    assert tech.state == EvidenceState.AVAILABLE.value
    assert tech.provenance in ("historical_ohlcv", "live_ohlcv")
    assert tech.direction == "BULLISH"
    assert tech.evidence_count >= 3
    for it in tech.evidence:
        if it.state == EvidenceState.AVAILABLE.value:
            assert datetime.fromisoformat(it.latest_input_timestamp) <= T


def test_historical_smc_and_regime_enter_fusion():
    hmd.set_test_provider(_prov(0.1))
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=T)
    assert snap.category("SMC").state == EvidenceState.AVAILABLE.value
    assert snap.category("SMC").provenance in ("historical_ohlcv", "live_ohlcv")
    reg = snap.category("REGIME")
    assert reg.state == EvidenceState.AVAILABLE.value
    assert any(it.metric.startswith("Cross-asset regime: ") for it in reg.evidence)


def test_historical_without_provider_stays_insufficient():
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=T)
    for cat in ("TECHNICAL", "SMC", "SEASONALITY", "REGIME"):
        c = snap.category(cat)
        assert c.state in (EvidenceState.INSUFFICIENT_EVIDENCE.value,
                           EvidenceState.PROVIDER_UNAVAILABLE.value)
        assert c.reason
        # no deterministic prior in historical mode
        assert all(e.provenance != "deterministic_prior" for e in c.evidence)


def test_deterministic_prior_is_labelled_and_excluded_from_direction(monkeypatch):
    """Live mode, no real candles: the Phase-55 prior may be attached for context
    but must be provenance=deterministic_prior, state NOT_APPLICABLE, and must not
    drive the category direction/score."""
    import market_data
    monkeypatch.setattr(market_data, "get_candles_with_source",
                        lambda *a, **k: ([], "synthetic_fallback"))
    hmd._reset_live_feed_state()
    fusion.invalidate()
    snap = fusion.get_asset_intelligence("XAUUSD")
    tech = snap.category("TECHNICAL")
    assert tech.state == EvidenceState.INSUFFICIENT_EVIDENCE.value
    assert tech.direction == "UNKNOWN"
    assert tech.score is None
    for e in tech.evidence:
        assert e.provenance == "deterministic_prior"
        assert e.source == "model_prior"
        assert e.state == EvidenceState.NOT_APPLICABLE.value
        assert "not derived from market data" in (e.note or "").lower()


def test_prior_never_labelled_historical_ohlcv(monkeypatch):
    import market_data
    monkeypatch.setattr(market_data, "get_candles_with_source",
                        lambda *a, **k: ([], "synthetic_fallback"))
    hmd._reset_live_feed_state()
    fusion.invalidate()
    d = fusion.get_asset_intelligence("XAUUSD").to_dict()
    for c in d["categories"]:
        for e in c["evidence"]:
            if e.get("provenance") == "deterministic_prior":
                assert e.get("source") != "historical_ohlcv"
                assert e.get("source_id", "").startswith("phase55:")


def test_snapshot_t1_ne_t2_for_technical():
    hmd.set_test_provider(_prov(0.15))
    s1 = fusion.get_asset_intelligence("XAUUSD", as_of=T)
    s2 = fusion.get_asset_intelligence(
        "XAUUSD", as_of=datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc))
    t1, t2 = s1.category("TECHNICAL"), s2.category("TECHNICAL")
    # different windows -> different latest_input_timestamp on the evidence
    lit1 = {e.latest_input_timestamp for e in t1.evidence if e.latest_input_timestamp}
    lit2 = {e.latest_input_timestamp for e in t2.evidence if e.latest_input_timestamp}
    assert lit1 and lit2 and lit1 != lit2


def test_evidence_model_not_duplicated():
    """Phase 68 reuses the Phase-67 model — no parallel evidence class."""
    from api.evidence_model import EvidenceItem
    import market_evidence_engine as mee
    r = None
    hmd.set_test_provider(_prov())
    r = mee.technical_evidence("XAUUSD", as_of=T, timeframe="1h")
    assert all(isinstance(it, EvidenceItem) for it in r.items)
