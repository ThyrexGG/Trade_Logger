# -*- coding: utf-8 -*-
"""
EdgeFinder-style Macro Scorecard shaper (Phase 64).

This module is a **thin adapter** over the existing Phase-56 macro engines
(`macro_intelligence_engine`) — it computes nothing new. It re-shapes the
authoritative factor-group / surprise / composite output into the
information architecture the user needs:

  composite macro bias + gauge
      -> 6 named categories (Technical / COT / Sentiment / Growth / Jobs / Inflation)
          -> per-indicator Actual / Forecast / Previous / Surprise / date / direction
          -> supporting / conflicting evidence + provenance
  score history (from MacroIntelligenceSnapshotStore — honest empty state)
  per-country economic heatmap

Rules honoured:
  * Read-only. No import of / path to execution_pipeline, broker_adapter,
    risk_gateway. GET-only surfaces.
  * Never fabricate. A category with no authoritative source returns
    ``state: "INSUFFICIENT_EVIDENCE"`` + ``next_dependency`` — never a made-up
    number. Technical and retail-Sentiment currently have no macro provider.
  * Lookahead-safe: every engine call flows through
    ``EconomicDataRegistry.get_releases_as_of`` which excludes
    ``release_timestamp > as_of``.
  * Provenance on every response (provider / is_live / provenance / as_of /
    model version). Seeded data is labelled ``seed_demo``.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from api.macro_provider import SUPPORTED_CURRENCIES

# Instruments the scorecard can evaluate. USD/EUR/GBP/JPY + the FX pairs whose
# both legs have releases + gold. CAD/AUD/NZD/CHF are accepted but resolve to
# INSUFFICIENT_EVIDENCE (no seeded releases) rather than UNSUPPORTED.
_FX_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "EURJPY"]
SUPPORTED_INSTRUMENTS: List[str] = [
    *SUPPORTED_CURRENCIES, *_FX_PAIRS, "XAUUSD",
]

# EdgeFinder countries (heatmap sidebar). US/EU/UK/JP have seeded releases;
# the rest resolve to INSUFFICIENT_EVIDENCE until a provider supplies them.
HEATMAP_COUNTRIES: List[str] = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF", "CNY"]

MODEL_VERSION = "phase64-scorecard-1"
_DISCLAIMER = "CONTEXTUAL MACRO INTELLIGENCE — deterministic, read-only, never an execution signal."

# engine factor-group key -> scorecard category
_CATEGORY_FROM_GROUP = {
    "GROWTH": "growth",
    "INFLATION": "inflation",
    "LABOR": "jobs",
    "MONETARY_POLICY": "rates",
    "SENTIMENT_POSITIONING": "cot",
}
_INDICATOR_FAMILY = {
    "growth": {"GROWTH"},
    "inflation": {"INFLATION"},
    "jobs": {"LABOR"},
    # Policy rate + sovereign yields — the single biggest driver of an FX pair's
    # macro lean (the rate differential / carry). Kept in its own category so the
    # composite score reconciles with something visible instead of hiding inside
    # "inflation".
    "rates": {"MONETARY_POLICY"},
    "cot": {"SENTIMENT_POSITIONING"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provenance() -> Dict[str, Any]:
    """Provenance + (for a real provider) a TTL-guarded registry hydrate."""
    try:
        from api.macro_provider import ensure_macro_data
        meta = ensure_macro_data()
        meta["model_version"] = MODEL_VERSION
        meta["as_of"] = _now()
        return meta
    except Exception:
        return {
            "data_provider": "seed_demo", "provider_is_live": False,
            "provenance": "seed_demo", "provider_state": "SEED_DEMO",
            "model_version": MODEL_VERSION, "as_of": _now(),
        }


def _bias_label(score: float) -> str:
    if score >= 50:
        return "VERY BULLISH"
    if score >= 15:
        return "BULLISH"
    if score <= -50:
        return "VERY BEARISH"
    if score <= -15:
        return "BEARISH"
    return "NEUTRAL"


def _direction(score: float) -> str:
    if score >= 15:
        return "BULLISH"
    if score <= -15:
        return "BEARISH"
    return "NEUTRAL"


def _gauge(score: float) -> int:
    """Map the engine's -100..100 score to an EdgeFinder-style integer gauge."""
    return int(max(-10, min(10, round(score / 10.0))))


def _confidence_state(n_indicators: int, groups_present: int) -> str:
    if groups_present >= 3 and n_indicators >= 5:
        return "OK"
    if groups_present >= 1:
        return "PARTIAL"
    return "INSUFFICIENT_EVIDENCE"


# --------------------------------------------------------------------------
# indicator rows
# --------------------------------------------------------------------------

def _indicator_rows(country: str, families: set, as_of: Optional[datetime]) -> List[Dict[str, Any]]:
    from macro_intelligence_engine import (
        EconomicDataRegistry,
        EconomicSurpriseEngine,
        INDICATOR_METADATA,
    )

    releases = EconomicDataRegistry.get_releases_as_of(as_of=as_of, country=country)
    rows: List[Dict[str, Any]] = []
    for r in releases:
        meta = INDICATOR_METADATA.get(r.metric, {})
        fam = meta.get("family", "GROWTH")
        if fam not in families:
            continue
        s = EconomicSurpriseEngine.evaluate_release_surprise(r)
        rows.append({
            "indicator": s["indicator"],
            "name": s.get("display_name", s["indicator"]),
            "family": fam,
            "actual": s.get("actual"),
            "forecast": s.get("forecast"),
            "previous": s.get("previous"),
            "unit": s.get("unit"),
            "surprise": s.get("raw_surprise"),
            "z_score": s.get("z_score"),
            "surprise_state": s.get("surprise_state"),
            "direction": s.get("direction"),
            "implication": s.get("market_implication"),
            "release_time": s.get("release_time"),
            "freshness": s.get("freshness"),
        })
    rows.sort(key=lambda x: str(x.get("release_time") or ""), reverse=True)
    return rows


# --------------------------------------------------------------------------
# per-economy category scores
# --------------------------------------------------------------------------

def _economy_categories(country: str, as_of: Optional[datetime]) -> Dict[str, Dict[str, Any]]:
    """Per-category scores for one economy.

    A category is only emitted with an *evidence-backed* score when the registry
    actually has ≥1 contributing release for it. The Phase-56 factor engine
    substitutes a model prior when a group has no releases (e.g. COT defaults to
    ~238.5k contracts); that prior must never be presented as a real reading, so
    such a category is returned as ``INSUFFICIENT_EVIDENCE`` instead.
    """
    from macro_intelligence_engine import MacroFactorGroupingEngine

    groups = MacroFactorGroupingEngine.evaluate_factor_groups(country=country, as_of=as_of)
    out: Dict[str, Dict[str, Any]] = {}
    for gkey, cat in _CATEGORY_FROM_GROUP.items():
        g = groups.get(gkey)
        if not g:
            continue
        rows = _indicator_rows(country, _INDICATOR_FAMILY[cat], as_of)
        score = float(g.get("score", 0.0))
        if not rows:
            out[cat] = {
                "score": None, "gauge": None, "direction": "INSUFFICIENT_EVIDENCE",
                "state": "INSUFFICIENT_EVIDENCE",
                "reason": f"No {cat} releases for {country} from the current provider.",
                "model_prior": round(score, 1),
                "indicators": [], "supporting": [], "conflicting": [],
            }
            if cat == "cot":
                out[cat]["next_dependency"] = "MACRO_COT_PROVIDER=cftc — free CFTC feed, no API key"
            continue
        out[cat] = {
            "score": round(score, 1),
            "gauge": _gauge(score),
            "direction": _direction(score),
            "engine_direction": g.get("direction"),
            "confidence": g.get("confidence"),
            "freshness": g.get("freshness"),
            "supporting": list(g.get("supporting_metrics", []))[:4],
            "conflicting": list(g.get("conflicting_metrics", []))[:3],
            "indicators": rows,
            "state": "OK",
        }
    return out


def _insufficient_category(reason: str, next_dep: str) -> Dict[str, Any]:
    return {
        "score": None, "gauge": None, "direction": "INSUFFICIENT_EVIDENCE",
        "state": "INSUFFICIENT_EVIDENCE", "reason": reason, "next_dependency": next_dep,
        "indicators": [], "supporting": [], "conflicting": [],
    }


def _technical_stub() -> Dict[str, Any]:
    return _insufficient_category(
        "No chartable symbol for this instrument on the macro layer.",
        "a per-instrument daily / intraday candle feed",
    )


# Which real, tradeable chart to read for a scorecard instrument. Bare non-USD
# currencies are intentionally omitted — a USD-cross proxy would invert the sign.
_TECH_SYMBOL = {
    "XAUUSD": "XAUUSD",
    "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY",
    "GBPJPY": "GBPJPY", "EURJPY": "EURJPY",
}


# short TTL memo — candle-derived reads only move bar-to-bar, and several
# callers (UI instrument switching, snapshotting) hit the same symbol in bursts.
_MARKET_TTL_SEC = 240.0
_market_cache: Dict[str, tuple] = {}


def _memoized(key: str):
    hit = _market_cache.get(key)
    if hit and (datetime.now(timezone.utc).timestamp() - hit[0]) < _MARKET_TTL_SEC:
        return hit[1]
    return None


def _memo_put(key: str, val: Any) -> Any:
    _market_cache[key] = (datetime.now(timezone.utc).timestamp(), val)
    return val


def _technical_category(instrument: str, as_of: Optional[datetime]) -> Dict[str, Any]:
    """Chart-trend (EMA/RSI/MACD/MTF) + seasonality, from real candles.

    Reuses ``market_evidence_engine`` — the same timestamp-safe, candle-derived
    evidence the Evidence Fusion layer uses. Best-effort: any failure or missing
    candle window degrades to INSUFFICIENT_EVIDENCE, never a fabricated read.
    """
    sym = _TECH_SYMBOL.get(instrument)
    if not sym:
        return _technical_stub()
    if as_of is None:
        cached = _memoized(f"tech:{sym}")
        if cached is not None:
            return cached
    out = _technical_category_compute(sym, as_of)
    return _memo_put(f"tech:{sym}", out) if as_of is None else out


def _technical_category_compute(sym: str, as_of: Optional[datetime]) -> Dict[str, Any]:
    try:
        import market_evidence_engine as mee

        tech = mee.technical_evidence(sym, as_of)
        seas = mee.seasonality_evidence(sym, as_of)
    except Exception:
        return _technical_stub()

    live_parts = [
        (r, w) for r, w in ((tech, 0.7), (seas, 0.3))
        if r is not None and r.state == "AVAILABLE" and r.score is not None
    ]
    if not live_parts:
        reason = (getattr(tech, "reason", None)
                  or "No candle window resolved for a chart-trend read.")
        return _insufficient_category(reason, f"a reachable candle feed for {sym}")

    wsum = sum(r.score * w for r, w in live_parts)
    wtot = sum(w for _, w in live_parts)
    score = round(wsum / wtot, 1)

    rows: List[Dict[str, Any]] = []
    for r in (tech, seas):
        if r is None:
            continue
        for it in (r.items or []):
            if getattr(it, "state", None) != "AVAILABLE":
                continue
            rows.append({
                "indicator": it.metric, "name": it.metric, "family": "TECHNICAL",
                "actual": it.value, "forecast": None, "previous": None,
                "unit": it.unit, "surprise": None, "z_score": None,
                "surprise_state": None, "direction": it.direction,
                "implication": it.note,
                "release_time": it.latest_input_timestamp or it.as_of,
                "freshness": None,
            })

    has_seasonality = seas is not None and seas.state == "AVAILABLE"
    return {
        "score": score, "gauge": _gauge(score), "direction": _direction(score),
        "state": "OK", "engine_direction": _direction(score),
        "confidence": getattr(tech, "confidence", None),
        "basis": f"{sym} chart — EMA/RSI/MACD + MTF bias"
                 + (" + calendar seasonality" if has_seasonality else " (no seasonal sample yet)"),
        "indicators": rows, "supporting": [], "conflicting": [],
    }


def _price_behavior(instrument: str, as_of: Optional[datetime]) -> Optional[Dict[str, Any]]:
    """EdgeFinder-style volatility context: average daily move + realized vol,
    from the real daily candle window. ``None`` when there is no chart or too
    little history (never a fabricated figure)."""
    sym = _TECH_SYMBOL.get(instrument)
    if not sym:
        return None
    if as_of is None:
        cached = _memoized(f"pb:{sym}")
        if cached is not None:
            return cached
    out = _price_behavior_compute(sym, as_of)
    return _memo_put(f"pb:{sym}", out) if as_of is None else out


def _price_behavior_compute(sym: str, as_of: Optional[datetime]) -> Optional[Dict[str, Any]]:
    try:
        from historical_market_data import get_candle_window

        w = get_candle_window(sym, "1d", as_of, lookback=180)
        if w is None or w.n < 7:
            return None
        df = w.to_df()
        ret = df["close"].astype(float).pct_change().dropna() * 100.0
        if len(ret) < 6:
            return None
        recent = ret.tail(7).abs().mean()
        alln = int(len(ret))
        overall = ret.abs().mean()
        vol = float(ret.std())
        ratio = (recent / overall) if overall else 1.0
        label = "elevated" if ratio >= 1.3 else "subdued" if ratio <= 0.7 else "normal"
        return {
            "symbol": sym,
            "avg_daily_move_recent_pct": round(float(recent), 2),
            "avg_daily_move_window_pct": round(float(overall), 2),
            "window_sessions": alln,
            "realized_vol_pct": round(vol, 2),
            "regime": label,
            "source": w.source_id,
        }
    except Exception:
        return None


def _sentiment_stub() -> Dict[str, Any]:
    return _insufficient_category(
        "No retail-positioning provider. COT (institutional) positioning is shown in the COT category.",
        "a retail / crowd sentiment feed (broker positioning, AAII) behind MacroDataProvider",
    )


# --------------------------------------------------------------------------
# public: single-instrument scorecard
# --------------------------------------------------------------------------

def _provider_unavailable(meta: Dict[str, Any]) -> bool:
    """A real provider is configured but has no data (outage / never hydrated).
    We must NOT silently fall back to the seeded canonical dataset."""
    return meta.get("provider_is_live") and meta.get("provenance") == "unavailable"


def get_scorecard(
    instrument: str,
    as_of: Optional[datetime] = None,
    with_market: bool = True,
) -> Dict[str, Any]:
    """Full scorecard for one instrument.

    ``with_market=False`` skips the live candle-derived pieces (the Technical
    category + the price-behaviour block) — used by list/ranking callers and the
    AI context builder, which only need the macro composite and would otherwise
    pay for dozens of network candle fetches.
    """
    inst = instrument.upper().strip()
    meta = _provenance()

    if inst not in SUPPORTED_INSTRUMENTS:
        return {
            **meta, "instrument": inst, "available": False, "state": "UNSUPPORTED",
            "reason": f"Supported: {', '.join(SUPPORTED_INSTRUMENTS)}",
            "disclaimer": _DISCLAIMER, "timestamp": _now(),
        }

    if _provider_unavailable(meta):
        return {
            **meta, "instrument": inst, "available": False, "state": "PROVIDER_UNAVAILABLE",
            "reason": "The configured macro data provider is unavailable. Seeded data is "
                      "not shown in its place.",
            "composite_score": None, "gauge": None, "bias": None,
            "categories": [], "disclaimer": _DISCLAIMER, "timestamp": _now(),
        }

    from macro_intelligence_engine import (
        EconomicDataRegistry,
        ForexRelativeStrengthEngine,
        MacroIntelligenceEngine,
    )

    # A currency with no releases at all (CAD/AUD/NZD/CHF under seed_demo) —
    # never fabricate a score.
    if inst in SUPPORTED_CURRENCIES and len(EconomicDataRegistry.get_releases_as_of(as_of=as_of, country=inst)) == 0:
        return {
            **meta, "instrument": inst, "available": False, "state": "INSUFFICIENT_EVIDENCE",
            "reason": f"No economic releases for {inst} from provider '{meta['data_provider']}'.",
            "next_dependency": "a real economic-calendar provider covering this economy",
            "composite_score": None, "gauge": None, "bias": "INSUFFICIENT_EVIDENCE",
            "categories": [], "disclaimer": _DISCLAIMER, "timestamp": _now(),
        }

    # --- composite -------------------------------------------------------
    ctx = MacroIntelligenceEngine.evaluate_macro_context(inst, as_of=as_of)
    composite = float(ctx.get("macro_score", 0.0))
    if not math.isfinite(composite):
        composite = 0.0

    # --- categories -----------------------------------------------------
    if inst in ForexRelativeStrengthEngine.PAIRS_MAP:
        base, quote = ForexRelativeStrengthEngine.PAIRS_MAP[inst]
        base_cats = _economy_categories(base, as_of)
        quote_cats = _economy_categories(quote, as_of)
        cats: Dict[str, Any] = {}
        for name in ("growth", "inflation", "jobs", "rates", "cot"):
            b = base_cats.get(name)
            q = quote_cats.get(name)
            b_ok = bool(b) and isinstance(b.get("score"), (int, float))
            q_ok = bool(q) and isinstance(q.get("score"), (int, float))
            # A relative (base − quote) category needs BOTH legs with real
            # evidence — otherwise a missing leg silently reads as neutral.
            if not (b_ok and q_ok):
                if b or q:
                    missing = base if not b_ok else quote
                    cats[name] = {
                        "score": None, "gauge": None, "direction": "INSUFFICIENT_EVIDENCE",
                        "state": "INSUFFICIENT_EVIDENCE",
                        "reason": f"No {name} evidence for {missing}; a relative score needs both economies.",
                        "indicators": [], "supporting": [], "conflicting": [],
                    }
                continue
            bs = b["score"]
            qs = q["score"]
            rel = round(bs - qs, 1)
            cats[name] = {
                "score": rel, "gauge": _gauge(rel), "direction": _direction(rel),
                "state": "OK", "basis": f"{base} − {quote}",
                "base": {"economy": base, "score": bs, "direction": _direction(bs)} if b_ok else None,
                "quote": {"economy": quote, "score": qs, "direction": _direction(qs)} if q_ok else None,
                "indicators": (b or {}).get("indicators", []),
                "supporting": (b or {}).get("supporting", []),
                "conflicting": (b or {}).get("conflicting", []),
            }
        scope_note = f"Relative: {base} economy vs {quote} economy."
        primary_country = base
    else:
        primary_country = "USD" if inst == "XAUUSD" else inst
        cats = _economy_categories(primary_country, as_of)
        scope_note = (
            "USD macro with safe-haven interpretation (weak growth / dovish policy support gold)."
            if inst == "XAUUSD" else f"{inst} economy macro strength."
        )

    cats["technical"] = (
        _technical_category(inst, as_of) if with_market
        else _insufficient_category(
            "Chart-trend read not loaded in this summary view.",
            "open the full scorecard for the live technical read",
        )
    )
    cats["sentiment"] = _sentiment_stub()

    ordered = ["rates", "growth", "jobs", "inflation", "cot", "sentiment", "technical"]
    categories = [{"category": name, **cats[name]} for name in ordered if name in cats]

    scored = [c for c in categories if isinstance(c.get("score"), (int, float))]
    n_ind = sum(len(c.get("indicators", [])) for c in categories)
    state = _confidence_state(n_ind, len(scored))

    strongest = max(scored, key=lambda c: c["score"]) if scored else None
    weakest = min(scored, key=lambda c: c["score"]) if scored else None

    return {
        **meta,
        "instrument": inst,
        "available": True,
        "state": state,
        "composite_score": round(composite, 1),
        "gauge": _gauge(composite),
        "bias": _bias_label(composite),
        "direction": _direction(composite),
        "confidence": int(ctx.get("data_quality", 0)),
        "economic_strength": round(float(ctx.get("economic_strength", 0.0)), 1),
        "surprise_score": ctx.get("surprise_score"),
        "surprise_momentum": ctx.get("surprise_momentum"),
        "scope_note": scope_note,
        "read_basis": (
            "Structural read: it weighs the level and trend of growth, jobs, inflation and "
            "the rate/policy differential. It is NOT a short-term data-surprise tracker — "
            "tools that score every release as a beat/miss vs consensus (e.g. EdgeFinder) "
            "answer a different, faster question and can point the other way."
        ),
        "primary_country": primary_country,
        "price_behavior": _price_behavior(inst, as_of) if with_market else None,
        "categories": categories,
        "strongest_category": strongest["category"] if strongest else None,
        "weakest_category": weakest["category"] if weakest else None,
        "sub_scores": {
            "growth": (cats.get("growth") or {}).get("score"),
            "inflation": (cats.get("inflation") or {}).get("score"),
            "jobs": (cats.get("jobs") or {}).get("score"),
            "rates": (cats.get("rates") or {}).get("score"),
            "cot": (cats.get("cot") or {}).get("score"),
        },
        "release_count": len(EconomicDataRegistry.get_releases_as_of(as_of=as_of, country=primary_country)),
        "disclaimer": _DISCLAIMER,
        "timestamp": _now(),
    }


def get_scorecard_list() -> Dict[str, Any]:
    """Ranked mini-scorecards for every supported instrument (Top Setups-lite).

    Cached (short TTL) — it evaluates the factor engine for all 11 instruments
    and the underlying FRED data only refreshes every few hours.
    """
    cached = _memoized("scorecard_list")
    if cached is not None:
        return cached
    return _memo_put("scorecard_list", _get_scorecard_list_compute())


def _get_scorecard_list_compute() -> Dict[str, Any]:
    rows = []
    for inst in SUPPORTED_INSTRUMENTS:
        sc = get_scorecard(inst, with_market=False)
        if not sc.get("available"):
            rows.append({"instrument": inst, "available": False, "state": sc.get("state")})
            continue
        rows.append({
            "instrument": inst, "available": True, "state": sc["state"],
            "composite_score": sc["composite_score"], "gauge": sc["gauge"], "bias": sc["bias"],
            "sub_scores": sc["sub_scores"],
        })
    ranked = sorted(
        (r for r in rows if r.get("available")),
        key=lambda r: r["composite_score"], reverse=True,
    )
    return {
        **_provenance(),
        "available": len(ranked) > 0,
        "instruments": rows,
        "ranked": ranked,
        "disclaimer": _DISCLAIMER,
        "timestamp": _now(),
    }


# --------------------------------------------------------------------------
# public: score history (from the snapshot store — never fabricated)
# --------------------------------------------------------------------------

def get_scorecard_history(instrument: str, limit: int = 60) -> Dict[str, Any]:
    inst = instrument.upper().strip()
    meta = _provenance()
    if inst not in SUPPORTED_INSTRUMENTS:
        return {**meta, "instrument": inst, "available": False, "state": "UNSUPPORTED",
                "points": [], "timestamp": _now()}

    try:
        from macro_intelligence_engine import MacroIntelligenceSnapshotStore
        snaps = MacroIntelligenceSnapshotStore.get_recent_snapshots(symbol=inst, limit=limit)
    except Exception:
        snaps = []

    points = [
        {
            "timestamp": s.get("timestamp"),
            "composite_score": s.get("macro_score"),
            "direction": s.get("macro_direction"),
            "growth": s.get("growth_score"),
            "inflation": s.get("inflation_score"),
            "jobs": s.get("labor_score"),
            "cot": s.get("positioning_score"),
            "data_quality": s.get("data_quality"),
            "fingerprint": s.get("payload_fingerprint"),
        }
        for s in reversed(snaps)  # chronological ascending for charting
    ]
    return {
        **meta,
        "instrument": inst,
        "available": len(points) > 0,
        "state": "OK" if points else "NO_HISTORY",
        "points": points,
        "note": (
            "Historical snapshots accumulate over time — one immutable snapshot is recorded "
            "per instrument at most hourly when its scorecard is viewed. No synthetic history "
            "is generated." if not points else None
        ),
        "count": len(points),
        "timestamp": _now(),
    }


_SNAPSHOT_MIN_INTERVAL_SEC = 3600.0


def record_scorecard_snapshot(instrument: str) -> Optional[str]:
    """Best-effort: persist one immutable snapshot of the current scorecard.

    De-duplicated — skips if this instrument already has a snapshot newer than
    ``_SNAPSHOT_MIN_INTERVAL_SEC``. This is how the history genuinely populates:
    from real evaluations, never fabricated points. Any failure is swallowed —
    recording history must never break a read.
    """
    inst = instrument.upper().strip()
    if inst not in SUPPORTED_INSTRUMENTS:
        return None
    try:
        from macro_intelligence_engine import MacroIntelligenceSnapshotStore

        recent = MacroIntelligenceSnapshotStore.get_recent_snapshots(symbol=inst, limit=1)
        if recent:
            last_ts = recent[0].get("timestamp")
            if last_ts:
                try:
                    last = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - last).total_seconds()
                    if age < _SNAPSHOT_MIN_INTERVAL_SEC:
                        return None
                except (ValueError, TypeError):
                    pass

        sc = get_scorecard(inst, with_market=False)
        if not sc.get("available"):
            return None
        snapshot = {
            "symbol": inst,
            "timestamp": sc["timestamp"],
            "macro_score": sc["composite_score"],
            "macro_direction": sc["direction"],
            "economic_strength": sc["economic_strength"],
            "surprise_score": sc.get("surprise_score") or 0.0,
            "data_quality": sc["confidence"],
            "factor_scores": {
                "growth": sc["sub_scores"].get("growth") or 0.0,
                "inflation": sc["sub_scores"].get("inflation") or 0.0,
                "labor": sc["sub_scores"].get("jobs") or 0.0,
                "monetary_policy": sc["sub_scores"].get("rates") or 0.0,
                "positioning": sc["sub_scores"].get("cot") or 0.0,
            },
            "model_version": MODEL_VERSION,
        }
        return MacroIntelligenceSnapshotStore.record_snapshot(snapshot)
    except Exception:
        return None


# --------------------------------------------------------------------------
# public: per-country economic heatmap
# --------------------------------------------------------------------------

def _impact_direction(row: Dict[str, Any], for_asset: str) -> str:
    """Deterministic per-indicator interpretation for a currency vs equities.

    Currency impact: strong economy / hawkish surprise = bullish the currency.
    Equity impact: growth strength = bullish; a hawkish inflation surprise is a
    headwind (bearish) even though it can support the currency.
    """
    fam = row.get("family", "GROWTH")
    surprise = row.get("surprise")
    if surprise is None:
        return "NEUTRAL"
    z = row.get("z_score") or 0.0
    if abs(z) < 0.4:
        return "NEUTRAL"
    beat = z > 0

    if for_asset == "currency":
        if fam == "INFLATION":
            return "BULLISH" if beat else "BEARISH"          # hawkish supports FX
        if fam == "LABOR":
            inv = "unemploy" in row.get("name", "").lower() or "claims" in row.get("name", "").lower()
            strong = (not beat) if inv else beat
            return "BULLISH" if strong else "BEARISH"
        return "BULLISH" if beat else "BEARISH"              # growth / policy
    # equities
    if fam == "INFLATION":
        return "BEARISH" if beat else "BULLISH"              # hot inflation pressures multiples
    if fam == "LABOR":
        inv = "unemploy" in row.get("name", "").lower() or "claims" in row.get("name", "").lower()
        strong = (not beat) if inv else beat
        return "BULLISH" if strong else "BEARISH"
    return "BULLISH" if beat else "BEARISH"


def get_country_heatmap(country: str, as_of: Optional[datetime] = None) -> Dict[str, Any]:
    ccy = country.upper().strip()
    meta = _provenance()
    if ccy not in HEATMAP_COUNTRIES:
        return {**meta, "country": ccy, "available": False, "state": "UNSUPPORTED",
                "reason": f"Supported: {', '.join(HEATMAP_COUNTRIES)}", "timestamp": _now()}

    if _provider_unavailable(meta):
        return {**meta, "country": ccy, "available": False, "state": "PROVIDER_UNAVAILABLE",
                "reason": "The configured macro data provider is unavailable. Seeded data is "
                          "not shown in its place.",
                "indicators": [], "categories": [], "timestamp": _now()}

    from macro_intelligence_engine import EconomicDataRegistry
    try:
        from economic_heatmap import GLOBAL_ECONOMIES
        econ = GLOBAL_ECONOMIES.get(ccy, {}) if isinstance(GLOBAL_ECONOMIES, dict) else {}
    except Exception:
        econ = {}

    if len(EconomicDataRegistry.get_releases_as_of(as_of=as_of, country=ccy)) == 0:
        return {
            **meta, "country": ccy, "country_name": econ.get("country_name", ccy),
            "available": False, "state": "INSUFFICIENT_EVIDENCE",
            "reason": f"No economic releases for {ccy} from provider '{meta['data_provider']}'.",
            "next_dependency": "a real economic-calendar provider covering this economy",
            "indicators": [], "categories": [], "timestamp": _now(),
        }

    all_families = {"GROWTH", "INFLATION", "LABOR", "MONETARY_POLICY", "SENTIMENT_POSITIONING"}
    rows = _indicator_rows(ccy, all_families, as_of)
    indicators = []
    for r in rows:
        indicators.append({
            **r,
            "currency_impact": _impact_direction(r, "currency"),
            "equity_impact": _impact_direction(r, "equities"),
        })

    cats = _economy_categories(ccy, as_of)
    categories = [
        {"category": name, "score": c["score"], "gauge": c["gauge"], "direction": c["direction"],
         "engine_direction": c.get("engine_direction"), "confidence": c.get("confidence"),
         "state": c.get("state", "OK")}
        for name, c in cats.items()
    ]
    scored_cats = [c["score"] for c in categories if isinstance(c["score"], (int, float))]
    agg = round(sum(scored_cats) / len(scored_cats), 1) if scored_cats else 0.0

    return {
        **meta,
        "country": ccy,
        "country_name": econ.get("country_name", ccy),
        "central_bank": econ.get("central_bank"),
        "available": True,
        "state": "OK" if len(indicators) >= 4 else "PARTIAL",
        "aggregate_score": agg,
        "aggregate_direction": _direction(agg),
        "indicators": indicators,
        "categories": categories,
        "disclaimer": _DISCLAIMER,
        "timestamp": _now(),
    }


def get_heatmap_index() -> Dict[str, Any]:
    """Which countries have data vs INSUFFICIENT_EVIDENCE (for the sidebar)."""
    from macro_intelligence_engine import EconomicDataRegistry
    out = []
    for c in HEATMAP_COUNTRIES:
        n = len(EconomicDataRegistry.get_releases_as_of(country=c))
        out.append({"country": c, "release_count": n,
                    "state": "OK" if n >= 4 else "PARTIAL" if n > 0 else "INSUFFICIENT_EVIDENCE"})
    return {**_provenance(), "available": any(r["release_count"] > 0 for r in out),
            "countries": out, "disclaimer": _DISCLAIMER, "timestamp": _now()}
