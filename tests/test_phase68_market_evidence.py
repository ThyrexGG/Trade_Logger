# -*- coding: utf-8 -*-
"""
Phase 68 — real, timestamp-safe market evidence engine.

Technical / SMC / seasonality / regime evidence computed from a deterministic
in-process candle provider. Covers warm-up handling, reproducibility, provenance,
look-ahead safety and honest gaps.
"""
import math
from datetime import datetime, timezone

import pytest

import historical_market_data as hmd
import market_evidence_engine as mee
from api.evidence_model import EvidenceState


def _trend(slope):
    def prov(asset, tf, as_of_epoch, lookback):
        tf_sec = hmd.tf_seconds(tf)
        n = lookback + 80
        out = []
        for i in range(n):
            t = as_of_epoch - (n - i) * tf_sec
            px = 100.0 + i * slope + 2.0 * math.sin(i / 8.0)
            out.append({"time": int(t), "open": px - 0.05, "high": px + 0.4,
                        "low": px - 0.4, "close": px, "volume": 1000 + (i % 50)})
        return out
    return prov


@pytest.fixture(autouse=True)
def _clean():
    hmd._reset_live_feed_state()
    hmd.set_test_provider(None)
    yield
    hmd.set_test_provider(None)
    hmd._reset_live_feed_state()


T = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


# --- technical -------------------------------------------------------
def test_technical_uptrend_is_bullish_and_real():
    hmd.set_test_provider(_trend(0.15))
    r = mee.technical_evidence("XAUUSD", as_of=T, timeframe="1h")
    assert r.state == EvidenceState.AVAILABLE.value
    assert r.direction == "BULLISH"
    assert r.provenance == "historical_ohlcv"
    metrics = {it.metric.split(" on ")[0] for it in r.items}
    assert any("EMA alignment" in m for m in metrics)
    assert any("RSI(14)" in m for m in metrics)
    assert any("MACD" in m for m in metrics)
    for it in r.items:
        if it.state == EvidenceState.AVAILABLE.value:
            assert it.latest_input_timestamp is not None
            assert datetime.fromisoformat(it.latest_input_timestamp) <= T
            assert it.timeframe and it.calculation_window


def test_technical_downtrend_is_bearish():
    hmd.set_test_provider(_trend(-0.15))
    r = mee.technical_evidence("XAUUSD", as_of=T, timeframe="1h")
    assert r.state == EvidenceState.AVAILABLE.value
    assert r.direction == "BEARISH"


def test_technical_insufficient_warmup():
    hmd.set_test_provider(lambda a, tf, e, lb: _trend(0.1)(a, tf, e, 5)[:10])
    r = mee.technical_evidence("XAUUSD", as_of=T, timeframe="1h")
    assert r.state == EvidenceState.INSUFFICIENT_EVIDENCE.value
    assert "warm-up" in (r.reason or "").lower() or "candles" in (r.reason or "").lower()


def test_technical_reproducible():
    hmd.set_test_provider(_trend(0.12))
    a = mee.technical_evidence("XAUUSD", as_of=T, timeframe="1h")
    b = mee.technical_evidence("XAUUSD", as_of=T, timeframe="1h")
    assert a.score == b.score and a.direction == b.direction
    assert [it.value for it in a.items] == [it.value for it in b.items]


def test_technical_no_provider_is_honest_gap():
    r = mee.technical_evidence("XAUUSD", as_of=T, timeframe="1h")
    assert r.state == EvidenceState.INSUFFICIENT_EVIDENCE.value
    assert r.next_dependency


# --- SMC ------------------------------------------------------------
def test_smc_is_candle_derived_with_confirmation_timestamps():
    hmd.set_test_provider(_trend(0.1))
    r = mee.smc_evidence("XAUUSD", as_of=T, timeframe="15m")
    assert r.state == EvidenceState.AVAILABLE.value
    assert r.provenance == "historical_ohlcv"
    for it in r.items:
        assert it.latest_input_timestamp is not None
        assert datetime.fromisoformat(it.latest_input_timestamp) <= T
        if it.observation_timestamp:  # formation time
            assert datetime.fromisoformat(it.observation_timestamp) <= T


def test_smc_future_structure_excluded():
    """A provider that emits candles well past as_of must not leak a structure
    formed after as_of (truncation happens in get_candle_window)."""
    tf_sec = hmd.tf_seconds("15m")

    def prov(asset, tf, as_of_epoch, lookback):
        base = as_of_epoch - 200 * tf_sec
        rows = []
        for k in range(400):  # half are after as_of
            px = 100 + k * 0.05
            rows.append({"time": int(base + k * tf_sec), "open": px, "high": px + 1,
                         "low": px - 1, "close": px + 0.1, "volume": 500})
        return rows

    hmd.set_test_provider(prov)
    r = mee.smc_evidence("XAUUSD", as_of=T, timeframe="15m")
    for it in r.items:
        if it.observation_timestamp:
            assert datetime.fromisoformat(it.observation_timestamp) <= T
        assert datetime.fromisoformat(it.latest_input_timestamp) <= T


# --- seasonality --------------------------------------------------
def test_seasonality_insufficient_sample_is_honest():
    # 30 daily candles — far below the multi-year threshold
    hmd.set_test_provider(lambda a, tf, e, lb: _trend(0.05)(a, "1d", e, 30)[:30])
    r = mee.seasonality_evidence("XAUUSD", as_of=T)
    assert r.state == EvidenceState.INSUFFICIENT_EVIDENCE.value
    assert "fabricated" in (r.reason or "").lower() or "need >=" in (r.reason or "")


def test_seasonality_real_sample_reports_size():
    hmd.set_test_provider(lambda a, tf, e, lb: _trend(0.02)(a, "1d", e, 1200))
    r = mee.seasonality_evidence("XAUUSD", as_of=T)
    assert r.state == EvidenceState.AVAILABLE.value
    assert any("sample_size=" in (it.note or "") for it in r.items)


# --- regime -----------------------------------------------------
def test_regime_missing_input_not_zero():
    """Only some benchmarks resolve -> INSUFFICIENT, and the missing ones are
    explicitly MISSING_INPUT, never silently neutral."""
    ok = {"DXY", "SPX500", "XAUUSD"}

    def prov(asset, tf, e, lb):
        if asset not in ok:
            return None
        return _trend(0.1)(asset, tf, e, lb)

    hmd.set_test_provider(prov)
    r = mee.regime_evidence("XAUUSD", as_of=T)
    assert r.state == EvidenceState.INSUFFICIENT_EVIDENCE.value
    missing = [it for it in r.items if "MISSING_INPUT" in (it.note or "")]
    assert missing
    assert "not treated as 0" in " ".join(it.note for it in missing)
    assert all(it.value is None for it in missing)  # never a fabricated number


def test_regime_full_coverage_classifies():
    hmd.set_test_provider(_trend(0.2))  # everything up -> risk-on-ish
    r = mee.regime_evidence("XAUUSD", as_of=T)
    assert r.state == EvidenceState.AVAILABLE.value
    assert r.coverage == 1.0
    assert any(it.metric.startswith("Cross-asset regime: ") for it in r.items)
    for it in r.items:
        if it.latest_input_timestamp:
            assert datetime.fromisoformat(it.latest_input_timestamp) <= T
