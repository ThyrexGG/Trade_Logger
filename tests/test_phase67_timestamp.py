# -*- coding: utf-8 -*-
"""
Phase 67 — timestamp discipline for the evidence fusion layer.

The backend — not the UI — must guarantee that a fused snapshot never contains
information dated after its ``as_of``. These tests drive the registry directly
so the assertions are deterministic and fully offline.

Explicit cases from the phase spec:
  1. future technical / derived evidence excluded (independent guard)
  2. future macro release excluded
  3. future COT release excluded
  4. evidence exactly at as_of is allowed
  5. historical reconstruction: snapshot(T1) != snapshot(T2) when evidence changed
  6. a future release cannot appear in an earlier snapshot
"""
from datetime import datetime, timezone

import pytest

import api.evidence_fusion as fusion
from api.evidence_model import EvidenceItem, EvidenceState


@pytest.fixture
def registry(monkeypatch):
    from macro_intelligence_engine import EconomicDataRegistry, MacroReleaseRecord

    # Keep every macro provider fully offline and out of the shared registry —
    # these tests seed their own deterministic releases.
    monkeypatch.setenv("MACRO_DATA_PROVIDER", "seed_demo")
    monkeypatch.setenv("MACRO_COT_PROVIDER", "none")
    monkeypatch.setenv("MACRO_FORECAST_PROVIDER", "none")
    try:
        from api.providers import cftc_provider as _cp
        monkeypatch.setattr(_cp, "_http_get",
                            lambda p, t: (_ for _ in ()).throw(OSError("offline in tests")))
    except Exception:
        pass

    saved = list(EconomicDataRegistry._RELEASES)
    saved_init = EconomicDataRegistry._INITIALIZED
    saved_mgd = EconomicDataRegistry._PROVIDER_MANAGED

    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = True
    EconomicDataRegistry._PROVIDER_MANAGED = True  # suppress canonical re-seed

    def add(metric, country, period, release_ts, actual, previous=None, source="FRED:TEST",
            revision_status="INITIAL", revision_ts=None):
        EconomicDataRegistry.register_release(MacroReleaseRecord(
            metric=metric, country=country, period=period,
            release_timestamp=release_ts, forecast=None, actual=actual, previous=previous,
            unit="%", source=source, source_timestamp=release_ts,
            revision_status=revision_status, revision_timestamp=revision_ts,
        ))

    fusion.invalidate()
    yield EconomicDataRegistry, add
    fusion.invalidate()
    EconomicDataRegistry._RELEASES = saved
    EconomicDataRegistry._INITIALIZED = saved_init
    EconomicDataRegistry._PROVIDER_MANAGED = saved_mgd


def _macro_cat(snap):
    return snap.category("MACRO")


def _cot_cat(snap):
    return snap.category("COT")


# --- 1. independent guard drops a future derived item --------------------
def test_independent_guard_excludes_future_item():
    as_of = datetime(2026, 9, 10, tzinfo=timezone.utc)
    items = [
        EvidenceItem(asset="X", category="TECHNICAL", metric="past",
                     available_timestamp="2026-09-09T00:00:00Z"),
        EvidenceItem(asset="X", category="TECHNICAL", metric="exact",
                     available_timestamp="2026-09-10T00:00:00Z"),
        EvidenceItem(asset="X", category="TECHNICAL", metric="future",
                     available_timestamp="2026-09-10T00:00:01Z"),
        EvidenceItem(asset="X", category="TECHNICAL", metric="future-release",
                     release_timestamp="2026-12-01T00:00:00Z"),
    ]
    kept, dropped = fusion._enforce_timestamps(items, as_of, live=False)
    assert [i.metric for i in kept] == ["past", "exact"]
    assert {i.metric for i in dropped} == {"future", "future-release"}


def test_untimed_item_kept_live_dropped_historical():
    untimed = [EvidenceItem(asset="X", category="TECHNICAL", metric="no-ts")]
    kept_live, _ = fusion._enforce_timestamps(untimed, datetime.now(timezone.utc), live=True)
    kept_hist, dropped_hist = fusion._enforce_timestamps(
        list(untimed), datetime(2025, 1, 1, tzinfo=timezone.utc), live=False)
    assert len(kept_live) == 1
    assert kept_hist == [] and len(dropped_hist) == 1


# --- 2 + 6. future macro release excluded from an earlier snapshot -------
def test_future_macro_release_excluded(registry):
    _, add = registry
    add("CPI", "USD", "2026-07", "2026-08-12T12:30:00Z", 3.2, previous=3.1)
    add("CPI", "USD", "2026-08", "2026-09-11T12:30:00Z", 3.4, previous=3.2)  # future vs T1

    t1 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=t1)
    macro = _macro_cat(snap)
    periods = {e.observation_timestamp for e in macro.evidence}
    assert "2026-07" in periods
    assert "2026-08" not in periods  # the 2026-09-11 release is invisible at T1
    # and it is recorded honestly as excluded, not silently missing
    assert snap.as_of == t1.isoformat()


# --- 3. future COT release excluded ------------------------------------
def test_future_cot_release_excluded(registry):
    _, add = registry
    add("COT_NET_POSITIONING", "USD", "2026-08-25", "2026-08-28T20:30:00Z", 190000.0,
        source="CFTC")
    add("COT_NET_POSITIONING", "USD", "2026-09-15", "2026-09-18T20:30:00Z", 205000.0,
        source="CFTC")  # future vs T1

    t1 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=t1)
    cot = _cot_cat(snap)
    assert cot.state == EvidenceState.AVAILABLE.value
    assert len(cot.evidence) == 1
    assert cot.evidence[0].observation_timestamp == "2026-08-25"
    assert cot.evidence[0].value == 190000.0


# --- 4. evidence exactly at as_of is allowed ---------------------------
def test_release_exactly_at_as_of_included(registry):
    _, add = registry
    add("CPI", "USD", "2026-08", "2026-09-11T12:30:00Z", 3.4, previous=3.2)
    at = datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=at)
    periods = {e.observation_timestamp for e in _macro_cat(snap).evidence}
    assert "2026-08" in periods


# --- 5. historical reconstruction differs when evidence changed --------
def test_snapshot_t1_differs_from_t2(registry):
    _, add = registry
    add("CPI", "USD", "2026-07", "2026-08-12T12:30:00Z", 3.2, previous=3.1)
    add("GDP", "USD", "2026-Q2", "2026-08-28T12:30:00Z", 2.1, previous=1.9)
    add("CPI", "USD", "2026-08", "2026-09-11T12:30:00Z", 3.6, previous=3.2)

    t1 = datetime(2026, 8, 20, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 20, tzinfo=timezone.utc)
    s1 = fusion.get_asset_intelligence("XAUUSD", as_of=t1)
    s2 = fusion.get_asset_intelligence("XAUUSD", as_of=t2)

    n1 = _macro_cat(s1).evidence_count
    n2 = _macro_cat(s2).evidence_count
    assert n1 == 1 and n2 == 3
    assert s1.to_dict()["categories"] != s2.to_dict()["categories"]


# --- revised observation honours vintage ------------------------------
def test_revised_observation_carries_vintage(registry):
    _, add = registry
    add("GDP", "USD", "2026-Q2", "2026-07-30T12:30:00Z", 2.4, previous=2.0,
        revision_status="REVISED", revision_ts="2026-08-28T12:30:00Z")
    at = datetime(2026, 9, 5, tzinfo=timezone.utc)
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=at)
    gdp = [e for e in _macro_cat(snap).evidence if e.observation_timestamp == "2026-Q2"]
    assert gdp and gdp[0].vintage_timestamp == "2026-08-28T12:30:00Z"


def test_historical_mode_excludes_live_only_categories(registry):
    _, add = registry
    add("CPI", "USD", "2026-07", "2026-08-12T12:30:00Z", 3.2, previous=3.1)
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert snap.mode == "HISTORICAL"
    for cat in ("TECHNICAL", "SMC", "SEASONALITY", "REGIME"):
        c = snap.category(cat)
        assert c.state in (EvidenceState.INSUFFICIENT_EVIDENCE.value,
                           EvidenceState.PROVIDER_UNAVAILABLE.value)
        assert c.evidence_count == 0
        assert c.reason  # says *why* it isn't reconstructable
