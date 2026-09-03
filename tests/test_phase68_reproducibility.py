# -*- coding: utf-8 -*-
"""
Phase 68 — historical snapshot reproducibility (§22) + serialization round-trip
(§23) + research-readiness (§47).

A fixed (asset, as_of, timeframe) must yield the same evidence on repeat, and the
canonical snapshot must survive to_dict -> from_dict without losing timestamps,
states, provenance, sources, confidence, conflicts or evidence values.
"""
import json
import math
from datetime import datetime, timezone

import pytest

import historical_market_data as hmd
import api.evidence_fusion as fusion
from api.evidence_model import AssetIntelligenceSnapshot, EvidenceState


def _prov(asset, tf, as_of_epoch, lookback):
    tf_sec = hmd.tf_seconds(tf)
    n = lookback + 80
    rows = []
    for i in range(n):
        t = as_of_epoch - (n - i) * tf_sec
        px = 100.0 + i * 0.11 + 2.0 * math.sin(i / 8.0)
        rows.append({"time": int(t), "open": px - 0.05, "high": px + 0.4,
                     "low": px - 0.4, "close": px, "volume": 1000 + (i % 40)})
    return rows


@pytest.fixture(autouse=True)
def _clean():
    hmd._reset_live_feed_state()
    hmd.set_test_provider(_prov)
    fusion.invalidate()
    yield
    hmd.set_test_provider(None)
    hmd._reset_live_feed_state()
    fusion.invalidate()


T = datetime(2026, 3, 15, 10, 30, tzinfo=timezone.utc)


def _strip_dynamic(d):
    d = json.loads(json.dumps(d))
    d.pop("generated_at", None)
    for c in d.get("categories", []):
        for e in c.get("evidence", []):
            e.pop("age_seconds", None)
        c.pop("age_seconds", None)
        c.pop("freshness", None)
    d.get("provider_health", {}).pop("providers", None)
    return d


def test_repeated_historical_snapshot_is_identical():
    fusion.invalidate()
    a = fusion.get_asset_intelligence("USDJPY", as_of=T).to_dict()
    fusion.invalidate()
    b = fusion.get_asset_intelligence("USDJPY", as_of=T).to_dict()
    assert _strip_dynamic(a) == _strip_dynamic(b)


def test_snapshot_to_dict_from_dict_round_trip():
    snap = fusion.get_asset_intelligence("USDJPY", as_of=T)
    d1 = snap.to_dict()
    restored = AssetIntelligenceSnapshot.from_dict(d1)
    d2 = restored.to_dict()

    assert d1["asset"] == d2["asset"]
    assert d1["as_of"] == d2["as_of"]
    assert d1["mode"] == d2["mode"]
    assert d1["cross_category_state"] == d2["cross_category_state"]
    assert d1["coverage"] == d2["coverage"]
    assert d1["conflicts"] == d2["conflicts"]
    assert d1["safety_barrier"] == d2["safety_barrier"]
    # every category: state / direction / score / provenance / evidence values
    for c1, c2 in zip(d1["categories"], d2["categories"]):
        assert (c1["category"], c1["state"], c1["direction"], c1["score"],
                c1["provenance"], c1["evidence_count"]) == \
               (c2["category"], c2["state"], c2["direction"], c2["score"],
                c2["provenance"], c2["evidence_count"])
        for e1, e2 in zip(c1["evidence"], c2["evidence"]):
            assert e1["metric"] == e2["metric"]
            assert e1["value"] == e2["value"]
            assert e1["state"] == e2["state"]
            assert e1["provenance"] == e2["provenance"]
            assert e1["latest_input_timestamp"] == e2["latest_input_timestamp"]
            assert e1["release_timestamp"] == e2["release_timestamp"]


def test_snapshot_survives_json():
    snap = fusion.get_asset_intelligence("USDJPY", as_of=T)
    blob = json.dumps(snap.to_dict())
    restored = AssetIntelligenceSnapshot.from_dict(json.loads(blob))
    assert restored.asset == "USDJPY"
    assert restored.as_of == T.isoformat()


def test_research_readiness_usdjpy_at_fixed_instant():
    """The headline research question: what did TradeLogger know about USDJPY at
    2026-03-15 10:30 UTC — using only evidence available then?"""
    snap = fusion.get_asset_intelligence("USDJPY", as_of=T)
    assert snap.mode == "HISTORICAL"
    assert snap.as_of == T.isoformat()

    # categories that CAN be reconstructed here are populated with real evidence
    for cat in ("TECHNICAL", "SMC", "SEASONALITY", "REGIME"):
        c = snap.category(cat)
        assert c is not None
        if c.state == EvidenceState.AVAILABLE.value:
            assert c.provenance in ("historical_ohlcv", "live_ohlcv")
            for e in c.evidence:
                if e.latest_input_timestamp:
                    assert datetime.fromisoformat(e.latest_input_timestamp) <= T

    # nothing in the entire snapshot is dated after as_of
    for c in snap.categories:
        for e in c.evidence:
            for ts in (e.available_timestamp, e.release_timestamp, e.latest_input_timestamp):
                if ts:
                    assert datetime.fromisoformat(ts.replace("Z", "+00:00")) <= T
