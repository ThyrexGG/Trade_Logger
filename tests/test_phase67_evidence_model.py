# -*- coding: utf-8 -*-
"""
Phase 67 — canonical evidence model.

The model must keep missing evidence distinguishable from neutral evidence,
never fabricate a confidence, and answer look-ahead questions purely on the
timestamps an item actually holds.
"""
from datetime import datetime, timedelta, timezone

import pytest

from api.evidence_model import (
    AssetIntelligenceSnapshot,
    CategoryEvidence,
    CoverageSummary,
    CrossCategoryAssessment,
    EvidenceDirection,
    EvidenceItem,
    EvidenceState,
    direction_from_score,
    normalise_direction,
    parse_ts,
)


def test_states_are_distinct():
    vals = {s.value for s in EvidenceState}
    assert {"AVAILABLE", "INSUFFICIENT_EVIDENCE", "PROVIDER_UNAVAILABLE",
            "STALE", "CONFLICT", "NOT_APPLICABLE"} <= vals
    assert EvidenceState.PROVIDER_UNAVAILABLE.value != EvidenceState.INSUFFICIENT_EVIDENCE.value


def test_missing_is_not_neutral():
    missing = CategoryEvidence(category="COT", state=EvidenceState.PROVIDER_UNAVAILABLE.value)
    neutral = CategoryEvidence(
        category="MACRO", state=EvidenceState.AVAILABLE.value,
        direction=EvidenceDirection.NEUTRAL.value, score=0.0,
    )
    assert missing.is_missing and not missing.is_populated
    assert neutral.is_populated and not neutral.is_missing
    assert missing.direction == EvidenceDirection.UNKNOWN.value
    assert missing.score is None and neutral.score == 0.0


def test_confidence_is_none_not_fabricated():
    item = EvidenceItem(asset="XAUUSD", category="TECHNICAL", metric="4H structure")
    assert item.confidence is None
    cat = CategoryEvidence(category="TECHNICAL", state=EvidenceState.AVAILABLE.value)
    assert cat.confidence is None


def test_direction_normalisation_never_silently_neutral():
    assert normalise_direction("BULLISH") == EvidenceDirection.BULLISH
    assert normalise_direction("very bearish") == EvidenceDirection.BEARISH
    assert normalise_direction("") == EvidenceDirection.UNKNOWN
    assert normalise_direction(None) == EvidenceDirection.UNKNOWN
    assert normalise_direction("wobbly") == EvidenceDirection.UNKNOWN  # not NEUTRAL


def test_direction_from_score_none_is_unknown():
    assert direction_from_score(None) == EvidenceDirection.UNKNOWN
    assert direction_from_score(0.0) == EvidenceDirection.NEUTRAL
    assert direction_from_score(50) == EvidenceDirection.BULLISH
    assert direction_from_score(-50) == EvidenceDirection.BEARISH


def test_parse_ts_accepts_z_and_naive():
    a = parse_ts("2026-09-01T12:00:00Z")
    b = parse_ts("2026-09-01T12:00:00+00:00")
    assert a == b and a.tzinfo is not None
    assert parse_ts("garbage") is None
    assert parse_ts(None) is None


def test_item_visibility_boundary_inclusive():
    as_of = datetime(2026, 9, 10, tzinfo=timezone.utc)
    exact = EvidenceItem(asset="X", category="MACRO", metric="CPI",
                         available_timestamp="2026-09-10T00:00:00Z")
    future = EvidenceItem(asset="X", category="MACRO", metric="CPI",
                          release_timestamp="2026-09-10T00:00:01Z")
    past = EvidenceItem(asset="X", category="MACRO", metric="CPI",
                        release_timestamp="2026-09-01T00:00:00Z")
    assert exact.is_visible_at(as_of) is True     # <= boundary allowed
    assert future.is_visible_at(as_of) is False
    assert past.is_visible_at(as_of) is True


def test_age_seconds_from_release_timestamp():
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    it = EvidenceItem(asset="X", category="MACRO", metric="CPI",
                      release_timestamp=(now - timedelta(hours=2)).isoformat())
    age = it.age_seconds(now=now)
    assert 7100 < age < 7300
    assert EvidenceItem(asset="X", category="T", metric="m").age_seconds(now=now) is None


def test_snapshot_to_dict_shape_has_no_blind_composite():
    snap = AssetIntelligenceSnapshot(
        asset="XAUUSD", as_of="2026-09-10T00:00:00Z", generated_at="2026-09-10T00:00:01Z",
        categories=[CategoryEvidence(category="MACRO", state=EvidenceState.AVAILABLE.value)],
        cross_category=CrossCategoryAssessment(),
        coverage=CoverageSummary(),
    )
    d = snap.to_dict()
    # explicitly NO single fused score / composite
    assert "overall_score" not in d
    assert "composite_score" not in d
    assert "cross_category_state" in d and "coverage" in d and "categories" in d
    assert d["safety_barrier"]["live_broker_transmission"] == "BLOCKED"
