# -*- coding: utf-8 -*-
"""
Phase 68 — property / invariant tests (§38).

The invariants that matter more than coverage:
  * no evidence timestamp > as_of
  * no historical snapshot contains a live-only (network) fetch
  * provider-unavailable != neutral ; missing != zero
  * no execution module reachable from any intelligence module
  * frozen strategy hash unchanged ; dataset isolation intact
"""
import hashlib
import math
import os
import re
import types
from datetime import datetime, timezone

import pytest

import historical_market_data as hmd
import api.evidence_fusion as fusion
from api.evidence_model import EvidenceState, EvidenceDirection

_FROZEN = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
_FORBIDDEN = {"execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
              "order_execution", "execution_config", "paper_simulator"}
_INTEL_MODULES = ["api.evidence_model", "api.evidence_fusion", "market_evidence_engine",
                  "historical_market_data", "api.ai_context"]


def _prov(asset, tf, as_of_epoch, lookback):
    tf_sec = hmd.tf_seconds(tf)
    n = lookback + 80
    return [{"time": int(as_of_epoch - (n - i) * tf_sec),
             "open": 100 + i * 0.1, "high": 100 + i * 0.1 + 0.5,
             "low": 100 + i * 0.1 - 0.5, "close": 100 + i * 0.1 + math.sin(i / 6),
             "volume": 800 + i} for i in range(n)]


@pytest.fixture(autouse=True)
def _clean():
    hmd._reset_live_feed_state()
    hmd.set_test_provider(None)
    fusion.invalidate()
    yield
    hmd.set_test_provider(None)
    hmd._reset_live_feed_state()
    fusion.invalidate()


_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_QUARTER_RE = re.compile(r"^(\d{4})-Q([1-4])$")


def _as_datetime(ts: str) -> datetime:
    """`observation_timestamp` is documented (api/evidence_model.py) as "the
    period observed" for macro evidence, not a strict timestamp -- it can be
    a bare "YYYY-MM" or "YYYY-Qn" period label instead of an ISO datetime
    (see api/evidence_fusion.py's `observation_timestamp=getattr(r, "period",
    None)`, and test_phase67_timestamp.py asserting exactly that). To still
    check the "no evidence after as_of" invariant against a period label,
    resolve it to the *end* of the period it names -- the conservative
    reading, since anything before full elapse of that period would be the
    real leak this invariant exists to catch.
    """
    m = _QUARTER_RE.match(ts)
    if m:
        year, q = int(m.group(1)), int(m.group(2))
        end_month = q * 3
        next_month_first = datetime(year + (1 if end_month == 12 else 0), (end_month % 12) + 1, 1, tzinfo=timezone.utc)
        return next_month_first
    if _MONTH_RE.match(ts):
        year, month = int(ts[:4]), int(ts[5:7])
        next_month_first = datetime(year + (1 if month == 12 else 0), (month % 12) + 1, 1, tzinfo=timezone.utc)
        return next_month_first
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # a bare "YYYY-MM-DD" release date has no tz


@pytest.mark.parametrize("asset", ["XAUUSD", "USDJPY", "EURUSD", "BTCUSD"])
@pytest.mark.parametrize("as_of", [
    datetime(2026, 1, 10, 8, 0, tzinfo=timezone.utc),
    datetime(2026, 4, 22, 14, 30, tzinfo=timezone.utc),
    datetime(2026, 7, 3, 21, 15, tzinfo=timezone.utc),
])
def test_invariant_no_evidence_after_as_of(asset, as_of):
    hmd.set_test_provider(_prov)
    fusion.invalidate()
    snap = fusion.get_asset_intelligence(asset, as_of=as_of)
    assert snap.as_of == as_of.isoformat()
    for c in snap.categories:
        for e in c.evidence:
            for ts in (e.available_timestamp, e.release_timestamp,
                       e.latest_input_timestamp, e.observation_timestamp):
                if not ts:
                    continue
                dt = _as_datetime(str(ts))
                assert dt <= as_of, f"{c.category}/{e.metric} ts {ts} > as_of {as_of}"


def test_invariant_historical_mode_uses_no_live_fetch(monkeypatch):
    """A historical snapshot must never touch the live candle feed."""
    import market_data
    calls = {"n": 0}
    real = market_data.get_candles_with_source

    def _spy(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(market_data, "get_candles_with_source", _spy)
    hmd.set_test_provider(_prov)
    fusion.invalidate()
    fusion.get_asset_intelligence("XAUUSD", as_of=datetime(2026, 2, 1, tzinfo=timezone.utc))
    assert calls["n"] == 0  # test provider path only — no network


def test_invariant_provider_unavailable_is_not_neutral():
    # no test provider, historical as_of -> candle windows return None
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=datetime(2025, 1, 1, tzinfo=timezone.utc))
    for cat in ("TECHNICAL", "SMC", "REGIME", "SEASONALITY"):
        c = snap.category(cat)
        assert c.state in (EvidenceState.INSUFFICIENT_EVIDENCE.value,
                           EvidenceState.PROVIDER_UNAVAILABLE.value)
        assert c.direction == EvidenceDirection.UNKNOWN.value
        assert c.score is None


def test_invariant_missing_regime_input_is_not_zero():
    ok = {"XAUUSD", "DXY", "SPX500"}
    hmd.set_test_provider(lambda a, tf, e, lb: _prov(a, tf, e, lb) if a in ok else None)
    fusion.invalidate()
    snap = fusion.get_asset_intelligence("XAUUSD", as_of=datetime(2026, 5, 1, tzinfo=timezone.utc))
    reg = snap.category("REGIME")
    for e in reg.evidence:
        if "MISSING_INPUT" in (e.note or ""):
            assert e.value is None


def test_invariant_no_execution_module_in_intelligence():
    for name in _INTEL_MODULES:
        mod = __import__(name, fromlist=["_"])
        bound = {v.__name__ for v in vars(mod).values() if isinstance(v, types.ModuleType)}
        assert not (bound & _FORBIDDEN), f"{name} -> {bound & _FORBIDDEN}"


def test_invariant_frozen_contract_hash():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "docs", "phase-audits", "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    with open(path, "rb") as fh:
        assert hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest() == _FROZEN


def test_invariant_no_new_composite_master_score():
    hmd.set_test_provider(_prov)
    fusion.invalidate()
    d = fusion.get_asset_intelligence("XAUUSD",
                                     as_of=datetime(2026, 6, 1, tzinfo=timezone.utc)).to_dict()
    for k in ("overall_score", "composite_score", "master_score", "tradelogger_score"):
        assert k not in d
    # each category keeps its OWN score; there is no blended top-level number
    assert isinstance(d["categories"], list)


def test_invariant_live_and_historical_never_collide_in_cache():
    hmd.set_test_provider(_prov)
    live = fusion.get_asset_intelligence("XAUUSD")
    hist = fusion.get_asset_intelligence("XAUUSD", as_of=datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert live.mode == "LIVE" and hist.mode == "HISTORICAL"
    assert live is not hist
