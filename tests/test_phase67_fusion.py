# -*- coding: utf-8 -*-
"""
Phase 67 — evidence fusion engine behaviour.

Covers: multiple categories, partial vs full coverage, cross-category
agreement / conflict, missing categories, PROVIDER_UNAVAILABLE kept distinct
from INSUFFICIENT_EVIDENCE, no blind composite, deterministic caching.
"""
from datetime import datetime, timezone

import pytest

import api.evidence_fusion as fusion
from api.evidence_model import (
    CategoryEvidence,
    CrossCategoryState,
    EvidenceDirection,
    EvidenceState,
)


@pytest.fixture(autouse=True)
def _clean():
    fusion.invalidate()
    yield
    fusion.invalidate()


def _cat(direction, state=EvidenceState.AVAILABLE.value, score=None):
    return CategoryEvidence(category="X", state=state, direction=direction, score=score)


# --- cross-category assessment ---------------------------------------
def test_cross_category_agreement():
    cats = [_cat(EvidenceDirection.BULLISH.value) for _ in range(3)]
    a = fusion._cross_category(cats)
    assert a.state == CrossCategoryState.AGREEMENT.value
    assert a.agreement_ratio == 1.0
    assert a.conflicting_categories == []


def test_cross_category_conflict_is_not_averaged_away():
    cats = [
        _cat(EvidenceDirection.BULLISH.value),
        _cat(EvidenceDirection.BULLISH.value),
        _cat(EvidenceDirection.BEARISH.value),
        _cat(EvidenceDirection.BEARISH.value),
    ]
    a = fusion._cross_category(cats)
    assert a.state == CrossCategoryState.CONFLICT.value
    assert 0.4 < a.agreement_ratio < 0.6
    assert set(a.supporting_categories) and set(a.opposing_categories)
    # the note must name the disagreement, not resolve it
    assert "disagree" in a.note.lower() or "not averaged" in a.note.lower()


def test_cross_category_insufficient_with_one_direction():
    cats = [_cat(EvidenceDirection.BULLISH.value),
            _cat(EvidenceDirection.NEUTRAL.value),
            _cat(EvidenceDirection.UNKNOWN.value, state=EvidenceState.INSUFFICIENT_EVIDENCE.value)]
    a = fusion._cross_category(cats)
    assert a.state == CrossCategoryState.INSUFFICIENT_EVIDENCE.value


# --- coverage --------------------------------------------------------
def test_coverage_keeps_provider_unavailable_distinct():
    cats = [
        _cat(EvidenceDirection.BULLISH.value),
        _cat(EvidenceDirection.UNKNOWN.value, state=EvidenceState.INSUFFICIENT_EVIDENCE.value),
        _cat(EvidenceDirection.UNKNOWN.value, state=EvidenceState.PROVIDER_UNAVAILABLE.value),
    ]
    cov = fusion._coverage(cats)
    assert cov.available_categories == 1
    assert cov.insufficient_categories == 1
    assert cov.provider_unavailable_categories == 1
    assert cov.total_categories == 3
    assert cov.coverage_ratio == round(1 / 3, 3)


# --- full snapshot (live) -------------------------------------------
def test_live_snapshot_has_all_canonical_categories():
    snap = fusion.get_asset_intelligence("XAUUSD")
    got = [c.category for c in snap.categories]
    assert got == fusion.CATEGORY_ORDER
    # at least macro + one edge factor populated in a normal live run
    assert any(c.is_populated for c in snap.categories)


def test_snapshot_dict_has_no_blind_composite():
    d = fusion.get_asset_intelligence("XAUUSD").to_dict()
    assert "overall_score" not in d and "composite_score" not in d
    assert "cross_category_state" in d
    # each category carries its OWN score, never a blended one
    for c in d["categories"]:
        assert set(c).issuperset({"category", "state", "direction", "score", "evidence_count"})


def test_provider_unavailable_not_downgraded_to_insufficient():
    # sentiment has no provider in the repo -> must be PROVIDER_UNAVAILABLE
    snap = fusion.get_asset_intelligence("XAUUSD")
    sent = snap.category("SENTIMENT")
    assert sent.state == EvidenceState.PROVIDER_UNAVAILABLE.value
    assert sent.state != EvidenceState.INSUFFICIENT_EVIDENCE.value


def test_unsupported_asset_helper():
    assert fusion.is_supported_asset("XAUUSD")
    assert fusion.is_supported_asset("xauusd")
    assert not fusion.is_supported_asset("NOTREAL")


# --- caching --------------------------------------------------------
def test_live_cache_returns_same_object_within_ttl():
    a = fusion.get_asset_intelligence("XAUUSD")
    b = fusion.get_asset_intelligence("XAUUSD")
    assert a is b
    fusion.invalidate()
    c = fusion.get_asset_intelligence("XAUUSD")
    assert c is not a


def test_historical_key_never_served_from_live_entry():
    live = fusion.get_asset_intelligence("XAUUSD")
    hist = fusion.get_asset_intelligence("XAUUSD", as_of=datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert live is not hist
    assert live.mode == "LIVE" and hist.mode == "HISTORICAL"
    # a historical snapshot is deterministic -> cached and identical on re-request
    hist2 = fusion.get_asset_intelligence("XAUUSD", as_of=datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert hist is hist2
