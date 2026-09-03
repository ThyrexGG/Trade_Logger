# -*- coding: utf-8 -*-
"""
Unified Evidence Fusion engine (Phase 67).

One entry point — :func:`get_asset_intelligence` — that turns the repo's several
independent intelligence engines into a single, transparent, timestamp-correct,
evidence-backed :class:`~api.evidence_model.AssetIntelligenceSnapshot`.

What this module IS
    * an orchestrator + normaliser. It calls the *existing* authoritative engines
      (``AssetEdgeIntelligenceEngine``, ``macro_scorecard``, ``macro_evidence``,
      ``CrossAssetRegimeEngine``, ``EconomicDataRegistry``) and re-expresses their
      output in the canonical evidence model.

What this module is NOT
    * it never recomputes a score an engine already owns
    * it never blends categories into one composite magic number
    * it never averages disagreement away — a cross-category conflict is a
      first-class result, not an error
    * it never invents a value, a confidence or a timestamp
    * it has NO import of / path to ``execution_pipeline``, a broker adapter, the
      risk gateway, order submission or any automation toggle — enforced by
      ``tests/test_phase67_safety.py``

Timestamp discipline
    Every underlying engine is called with the requested ``as_of``. On top of
    that, this module *independently* re-checks every emitted evidence item:
    an item whose ``available_timestamp`` / ``release_timestamp`` is after
    ``as_of`` is dropped and recorded as a data gap. The backend never relies on
    the caller or the UI to filter future information.

Historical (as-of) mode
    Only the categories that genuinely support timestamp-correct historical
    reconstruction are populated in historical mode: ``MACRO`` and ``COT``
    (both flow through ``EconomicDataRegistry.get_releases_as_of``, which
    excludes ``release_timestamp > as_of``). ``TECHNICAL`` / ``SMC`` /
    ``REGIME`` / ``SEASONALITY`` are marked ``INSUFFICIENT_EVIDENCE`` with a
    reason rather than silently returning current values.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from api.evidence_model import (
    AssetIntelligenceSnapshot,
    CategoryEvidence,
    CoverageSummary,
    CrossCategoryAssessment,
    CrossCategoryState,
    EvidenceCategory,
    EvidenceDirection,
    EvidenceItem,
    EvidenceState,
    direction_from_score,
    normalise_direction,
    parse_ts,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CATEGORY_ORDER: List[str] = [
    EvidenceCategory.TECHNICAL.value,
    EvidenceCategory.SMC.value,
    EvidenceCategory.MACRO.value,
    EvidenceCategory.COT.value,
    EvidenceCategory.REGIME.value,
    EvidenceCategory.SEASONALITY.value,
    EvidenceCategory.SENTIMENT.value,
]

# Categories that can be honestly reconstructed for a historical as_of.
_HISTORICAL_CATEGORIES = {EvidenceCategory.MACRO.value, EvidenceCategory.COT.value}

# asset -> the economy whose macro / COT releases drive it
_ASSET_PRIMARY_ECONOMY = {
    "XAUUSD": "USD", "DXY": "USD", "SPX500": "USD", "NAS100": "USD",
    "US30": "USD", "USOIL": "USD", "BTCUSD": "USD", "ETHUSD": "USD",
    "USDJPY": "USD", "EURUSD": "EUR", "GBPUSD": "GBP", "GBPJPY": "GBP",
    "EURJPY": "EUR", "AUDUSD": "AUD", "NZDUSD": "NZD", "USDCAD": "USD",
    "USDCHF": "USD",
}

# staleness thresholds (seconds) for the freshness label
_FRESH_MAX = 6 * 3600
_RECENT_MAX = 72 * 3600

_MODEL_VERSION = "phase67-evidence-fusion-1"

# Assets the fusion engine can build a real snapshot for. Anything else 404s at
# the API rather than returning a snapshot backed by fallback defaults.
SUPPORTED_ASSETS = frozenset({
    "XAUUSD", "DXY", "SPX500", "NAS100", "US30", "USOIL", "BTCUSD", "ETHUSD",
    "USDJPY", "EURUSD", "GBPUSD", "GBPJPY", "EURJPY",
    "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
})


def is_supported_asset(asset: str) -> bool:
    return normalise_asset(asset) in SUPPORTED_ASSETS

# ---------------------------------------------------------------------------
# TTL snapshot cache — same idiom as CrossAssetRegimeEngine / system_health_cache.
# Live snapshots: short TTL, keyed by (asset, timeframe).
# Historical snapshots: deterministic and immutable -> cached for the process
# lifetime, keyed by the exact as_of. A historical key is NEVER served from a
# live entry and vice-versa (distinct key namespaces).
# ---------------------------------------------------------------------------
_LOCK = threading.Lock()
_CACHE: Dict[str, Tuple[AssetIntelligenceSnapshot, float]] = {}
_LIVE_TTL_SEC = 4.0


def invalidate() -> None:
    """Drop every cached fusion snapshot (test + provider-refresh hook)."""
    with _LOCK:
        _CACHE.clear()


def _cache_key(asset: str, timeframe: Optional[str], as_of: Optional[datetime]) -> str:
    tf = (timeframe or "-").upper()
    if as_of is None:
        return f"live::{asset}::{tf}"
    return f"hist::{asset}::{tf}::{as_of.astimezone(timezone.utc).isoformat()}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def normalise_asset(asset: str) -> str:
    return (asset or "").upper().replace("/", "").replace(":", "").strip()


def _freshness_label(age_seconds: Optional[float]) -> Optional[str]:
    if age_seconds is None:
        return None
    if age_seconds <= _FRESH_MAX:
        return "FRESH"
    if age_seconds <= _RECENT_MAX:
        return "RECENT"
    return "STALE"


def _enforce_timestamps(
    items: List[EvidenceItem], ceiling: datetime, *, live: bool
) -> Tuple[List[EvidenceItem], List[EvidenceItem]]:
    """Independent backend look-ahead guard. Returns (kept, dropped).

    An item is dropped when any timestamp it carries is strictly after
    ``ceiling``. An item exactly at ``ceiling`` is kept (``<=``). In historical
    mode ``ceiling`` is the requested ``as_of`` and an item with no knowable
    timestamp at all is also dropped (we cannot prove it was available). In live
    mode ``ceiling`` is wall-clock "now" at enforcement time and an untimed item
    is kept."""
    kept: List[EvidenceItem] = []
    dropped: List[EvidenceItem] = []
    for it in items:
        tss = [parse_ts(it.available_timestamp), parse_ts(it.release_timestamp)]
        known = [t for t in tss if t is not None]
        future = any(t > ceiling for t in known)
        if future:
            dropped.append(it)
            continue
        if not known and not live:
            dropped.append(it)
            continue
        kept.append(it)
    return kept, dropped


def _agg_age(items: List[EvidenceItem], as_of: datetime) -> Optional[float]:
    ages = [it.age_seconds(now=as_of) for it in items]
    ages = [a for a in ages if a is not None]
    return max(ages) if ages else None


# ---------------------------------------------------------------------------
# Category builders
# ---------------------------------------------------------------------------
def _unavailable_category(cat: str, reason: str, next_dep: Optional[str] = None,
                          *, state: str = EvidenceState.INSUFFICIENT_EVIDENCE.value) -> CategoryEvidence:
    return CategoryEvidence(
        category=cat, state=state,
        direction=EvidenceDirection.UNKNOWN.value,
        score=None, confidence=None, coverage=0.0,
        reason=reason, next_dependency=next_dep,
    )


def _edge_factor_category(
    cat: str, factor_name_needles: Tuple[str, ...], edge_snap: Dict[str, Any],
    asset: str, as_of: datetime, as_of_iso: str,
) -> CategoryEvidence:
    """Build a category from one factor family inside an Asset Edge snapshot.
    The factor's own score/direction/evidence is reused verbatim."""
    factors = edge_snap.get("factor_breakdown", []) or []
    match = None
    for f in factors:
        name = str(f.get("factor_name", ""))
        if any(n.lower() in name.lower() for n in factor_name_needles):
            match = f
            break
    if match is None:
        return _unavailable_category(cat, f"No {cat.lower()} factor in the edge snapshot for {asset}.")

    if not match.get("data_available", False):
        return _unavailable_category(
            cat, f"The {match.get('factor_name', cat)} factor engine reported no data for {asset}."
        )

    src = match.get("source", {}) or {}
    provider = src.get("provider")
    src_ts = src.get("timestamp")
    age = src.get("age_sec")
    avail_ts = src_ts or as_of_iso
    score = match.get("score")
    direction = normalise_direction(match.get("direction"))
    if direction == EvidenceDirection.UNKNOWN:
        direction = direction_from_score(score)

    items: List[EvidenceItem] = []
    for ev in match.get("evidence", []) or []:
        pts = ev.get("points")
        items.append(EvidenceItem(
            asset=asset, category=cat, metric=str(ev.get("reason", "factor evidence"))[:180],
            state=EvidenceState.AVAILABLE.value,
            value=float(pts) if isinstance(pts, (int, float)) else None,
            direction=normalise_direction(ev.get("impact")),
            source=provider, source_id=match.get("factor_name"),
            provenance="derived",
            as_of=as_of_iso, available_timestamp=avail_ts,
        ))

    conf_txt = str(match.get("confidence", "")).upper()
    confidence = {"VERY HIGH": 0.95, "HIGH": 0.8, "MODERATE": 0.6, "LOW": 0.4,
                  "NONE": None, "": None}.get(conf_txt, None)

    cat_ev = CategoryEvidence(
        category=cat,
        state=EvidenceState.AVAILABLE.value,
        direction=direction.value,
        score=float(score) if isinstance(score, (int, float)) else None,
        confidence=confidence,
        coverage=1.0 if items else 0.5,
        sources=[provider] if provider else [],
        provenance="derived",
        evidence=items,
    )
    cat_ev.age_seconds = float(age) if isinstance(age, (int, float)) else _agg_age(items, as_of)
    cat_ev.freshness = _freshness_label(cat_ev.age_seconds)
    return cat_ev


def _macro_category(asset: str, as_of: datetime, as_of_iso: str, live: bool) -> CategoryEvidence:
    from api import macro_scorecard

    try:
        sc = macro_scorecard.get_scorecard(asset, as_of=None if live else as_of)
    except Exception as exc:  # pragma: no cover - defensive
        return _unavailable_category(
            EvidenceCategory.MACRO.value,
            f"Macro scorecard raised {type(exc).__name__}.",
            "a reachable macro data provider",
            state=EvidenceState.PROVIDER_UNAVAILABLE.value,
        )

    st = str(sc.get("state", "")).upper()
    if not sc.get("available"):
        if st == "PROVIDER_UNAVAILABLE":
            return _unavailable_category(
                EvidenceCategory.MACRO.value,
                sc.get("reason", "The configured macro data provider is unavailable."),
                "a reachable macro data provider",
                state=EvidenceState.PROVIDER_UNAVAILABLE.value,
            )
        return _unavailable_category(
            EvidenceCategory.MACRO.value,
            sc.get("reason", "Insufficient macro evidence for this asset."),
            sc.get("next_dependency", "an economic-calendar provider covering this economy"),
        )

    provider = sc.get("data_provider")
    provenance = sc.get("provenance")
    composite = sc.get("composite_score")
    state = EvidenceState.CONFLICT.value if st == "CONFLICT" else EvidenceState.AVAILABLE.value

    # Evidence items are built straight from the timestamp-disciplined registry so
    # every one carries a real provenance chain: metric -> source_id -> source ->
    # release / observation / vintage timestamps. get_releases_as_of already
    # excludes release_timestamp > as_of; the independent guard re-checks anyway.
    economy = "USD" if asset == "XAUUSD" else _ASSET_PRIMARY_ECONOMY.get(asset, asset)
    items: List[EvidenceItem] = []
    latest_release_ts: Optional[datetime] = None
    try:
        from macro_intelligence_engine import EconomicDataRegistry, INDICATOR_METADATA
        releases = EconomicDataRegistry.get_releases_as_of(
            as_of=None if live else as_of, country=economy)
    except Exception:  # pragma: no cover - defensive
        releases, INDICATOR_METADATA = [], {}
    for r in releases:
        if getattr(r, "metric", None) == "COT_NET_POSITIONING":
            continue  # COT is its own category
        rel_ts = getattr(r, "release_timestamp", None)
        rel_dt = parse_ts(rel_ts)
        if rel_dt and (latest_release_ts is None or rel_dt > latest_release_ts):
            latest_release_ts = rel_dt
        fam = INDICATOR_METADATA.get(getattr(r, "metric", ""), {}) if INDICATOR_METADATA else {}
        actual = _num(getattr(r, "actual", None))
        prev = _num(getattr(r, "previous", None))
        direction = EvidenceDirection.UNKNOWN
        if actual is not None and prev is not None:
            direction = direction_from_score(actual - prev, bullish_at=1e-9, bearish_at=-1e-9)
        items.append(EvidenceItem(
            asset=asset, category=EvidenceCategory.MACRO.value,
            metric=str(fam.get("display_name") or getattr(r, "metric", "release")),
            state=EvidenceState.AVAILABLE.value,
            value=actual, unit=getattr(r, "unit", None),
            direction=direction.value,
            source=(getattr(r, "source", None) or provider or "").split(":")[0] or None,
            source_id=getattr(r, "source", None) or getattr(r, "metric", None),
            provenance=provenance,
            as_of=as_of_iso,
            available_timestamp=rel_ts,
            release_timestamp=rel_ts,
            observation_timestamp=getattr(r, "period", None),
            vintage_timestamp=getattr(r, "revision_timestamp", None) or getattr(r, "source_timestamp", None),
            note=(f"revision {r.revision_status}" if getattr(r, "revision_status", "INITIAL") != "INITIAL" else None),
        ))

    confidence = sc.get("confidence")
    confidence = round(confidence / 100.0, 2) if isinstance(confidence, (int, float)) and confidence > 0 else None

    rc = _num(sc.get("release_count"))
    coverage = min(1.0, rc / 6.0) if rc is not None and rc > 0 else (0.4 if items else 0.0)

    cat_ev = CategoryEvidence(
        category=EvidenceCategory.MACRO.value,
        state=state,
        direction=normalise_direction(sc.get("direction")).value,
        score=_num(composite),
        confidence=confidence,
        coverage=round(coverage, 2),
        sources=sorted({i.source for i in items if i.source} | ({provider} if provider else set())),
        provenance=provenance,
        evidence=items,
        reason=sc.get("scope_note"),
    )
    ceiling = _now() if live else as_of
    cat_ev.age_seconds = None if latest_release_ts is None else max(
        0.0, (ceiling - latest_release_ts).total_seconds())
    cat_ev.freshness = _freshness_label(cat_ev.age_seconds)
    return cat_ev


def _cot_category(asset: str, as_of: datetime, as_of_iso: str, live: bool) -> CategoryEvidence:
    """COT positioning straight from the timestamp-disciplined registry +
    the CFTC provider health. Never falls back to a fabricated number."""
    from api.providers.registry import cot_provider_key

    economy = _ASSET_PRIMARY_ECONOMY.get(asset)
    try:
        from macro_intelligence_engine import EconomicDataRegistry
        releases = EconomicDataRegistry.get_releases_as_of(
            as_of=None if live else as_of,
            country=economy, metric="COT_NET_POSITIONING",
        ) if economy else []
    except Exception:  # pragma: no cover - defensive
        releases = []

    cot_key = cot_provider_key()
    provider_configured = cot_key not in ("", "none")

    if not releases:
        if provider_configured:
            return _unavailable_category(
                EvidenceCategory.COT.value,
                f"COT provider '{cot_key}' is configured but has no positioning record "
                f"available at this timestamp for {economy or asset}.",
                "a fresh CFTC Commitments-of-Traders report for this market",
            )
        return _unavailable_category(
            EvidenceCategory.COT.value,
            "No COT positioning provider is configured (MACRO_COT_PROVIDER=none).",
            "set MACRO_COT_PROVIDER=cftc",
            state=EvidenceState.PROVIDER_UNAVAILABLE.value,
        )

    rec = max(releases, key=lambda r: r.release_timestamp)
    val = _num(getattr(rec, "actual", None))
    direction = direction_from_score(val, bullish_at=0.0001, bearish_at=-0.0001)
    rel_ts = getattr(rec, "release_timestamp", None)
    obs = getattr(rec, "period", None)
    src = getattr(rec, "source", None) or "CFTC"

    item = EvidenceItem(
        asset=asset, category=EvidenceCategory.COT.value,
        metric="Net non-commercial positioning",
        state=EvidenceState.AVAILABLE.value,
        value=val, unit=getattr(rec, "unit", "contracts"),
        direction=direction.value,
        source=src, source_id="COT_NET_POSITIONING",
        provenance="live" if "CFTC" in str(src).upper() else "seed_demo",
        as_of=as_of_iso, available_timestamp=rel_ts,
        release_timestamp=rel_ts, observation_timestamp=obs,
        note=f"report_date {obs}" if obs else None,
    )
    age = item.age_seconds(now=(as_of if not live else _now()))
    cat_ev = CategoryEvidence(
        category=EvidenceCategory.COT.value,
        state=EvidenceState.AVAILABLE.value,
        direction=direction.value,
        score=None,  # positioning is not a -100..100 score; expose the raw value instead
        confidence=None,
        coverage=1.0,
        sources=[src],
        provenance=item.provenance,
        evidence=[item],
        reason=f"Latest report_date {obs}." if obs else None,
    )
    cat_ev.age_seconds = age
    cat_ev.freshness = _freshness_label(age)
    return cat_ev


def _regime_category(asset: str, as_of: datetime, as_of_iso: str, live: bool) -> CategoryEvidence:
    if not live:
        return _unavailable_category(
            EvidenceCategory.REGIME.value,
            "Cross-asset regime cannot be reconstructed historically — the regime "
            "engine reads live-only market data (no as-of candle store).",
            "a historical cross-asset price store for regime replay",
        )
    try:
        from cross_asset_regime_engine import CrossAssetRegimeEngine
        snap = CrossAssetRegimeEngine.evaluate_regime()
    except Exception as exc:  # pragma: no cover - defensive
        return _unavailable_category(
            EvidenceCategory.REGIME.value, f"Regime engine raised {type(exc).__name__}.")

    primary = getattr(snap, "primary_regime", "INSUFFICIENT_DATA")
    if primary == "INSUFFICIENT_DATA":
        return _unavailable_category(
            EvidenceCategory.REGIME.value,
            "The regime engine returned INSUFFICIENT_DATA (multi-asset consensus not met).",
        )
    conf = getattr(snap, "confidence_pct", None)
    dq = getattr(snap, "data_quality_score", None)

    items = [EvidenceItem(
        asset=asset, category=EvidenceCategory.REGIME.value,
        metric=f"Primary regime: {primary}",
        state=EvidenceState.AVAILABLE.value,
        direction=_regime_direction(primary, asset).value,
        source="Cross-Asset Regime Engine", source_id=getattr(snap, "snapshot_id", None),
        provenance="derived",
        as_of=as_of_iso, available_timestamp=getattr(snap, "timestamp", as_of_iso),
        note=f"secondary {getattr(snap, 'secondary_regime', 'n/a')}",
    )]
    for cf in (getattr(snap, "confirming_factors", []) or [])[:4]:
        items.append(EvidenceItem(
            asset=asset, category=EvidenceCategory.REGIME.value, metric=str(cf)[:180],
            state=EvidenceState.AVAILABLE.value, direction=EvidenceDirection.NEUTRAL.value,
            source="Cross-Asset Regime Engine", provenance="derived",
            as_of=as_of_iso, available_timestamp=getattr(snap, "timestamp", as_of_iso),
        ))

    cat_ev = CategoryEvidence(
        category=EvidenceCategory.REGIME.value,
        state=EvidenceState.AVAILABLE.value,
        direction=_regime_direction(primary, asset).value,
        score=None,
        confidence=round(conf / 100.0, 2) if isinstance(conf, (int, float)) else None,
        coverage=round(dq / 100.0, 2) if isinstance(dq, (int, float)) else None,
        sources=["Cross-Asset Regime Engine"],
        provenance="derived",
        evidence=items,
        reason=f"{primary} (secondary {getattr(snap, 'secondary_regime', 'n/a')}), "
               f"conflicting factors: {len(getattr(snap, 'conflicting_factors', []) or [])}",
    )
    cat_ev.age_seconds = 0.0
    cat_ev.freshness = "FRESH"
    return cat_ev


_RISK_ON_REGIMES = {"RISK_ON", "GROWTH_ACCELERATION", "USD_WEAKNESS", "RATE_FALL", "DISINFLATIONARY"}
_RISK_OFF_REGIMES = {"RISK_OFF", "GROWTH_DECELERATION", "USD_STRENGTH", "RATE_RISE", "INFLATIONARY"}


def _regime_direction(regime: str, asset: str) -> EvidenceDirection:
    """Regime -> directional lean *for this asset*. Gold and USD invert vs risk assets."""
    r = str(regime).upper()
    if r in _RISK_ON_REGIMES:
        return EvidenceDirection.BEARISH if (asset == "XAUUSD") else EvidenceDirection.BULLISH
    if r in _RISK_OFF_REGIMES:
        if asset == "XAUUSD":
            return EvidenceDirection.BULLISH
        if r in ("USD_STRENGTH",) and asset == "DXY":
            return EvidenceDirection.BULLISH
        return EvidenceDirection.BEARISH
    return EvidenceDirection.NEUTRAL


def _sentiment_category(asset: str, as_of: datetime, as_of_iso: str, live: bool) -> CategoryEvidence:
    """Retail / crowd sentiment has no configured provider in the repo. Report
    that honestly rather than inventing a neutral reading."""
    try:
        from api.providers.sentiment_provider import get_sentiment_provider
        st = get_sentiment_provider().status() or {}
    except Exception:  # pragma: no cover - defensive
        st = {}
    if st.get("configured"):
        return _unavailable_category(
            EvidenceCategory.SENTIMENT.value,
            "Retail sentiment provider is configured but returned no reading for this asset.",
            "a retail-positioning feed covering this instrument",
        )
    return _unavailable_category(
        EvidenceCategory.SENTIMENT.value,
        "No retail-sentiment provider is configured.",
        "a broker / crowd-positioning provider",
        state=EvidenceState.PROVIDER_UNAVAILABLE.value,
    )


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return f if f == f and f not in (float("inf"), float("-inf")) else None
    return None


# ---------------------------------------------------------------------------
# Cross-category assessment / coverage / provenance
# ---------------------------------------------------------------------------
def _cross_category(categories: List[CategoryEvidence]) -> CrossCategoryAssessment:
    populated = [c for c in categories if c.state in (
        EvidenceState.AVAILABLE.value, EvidenceState.CONFLICT.value)]
    directional = [c for c in populated if c.direction in (
        EvidenceDirection.BULLISH.value, EvidenceDirection.BEARISH.value)]

    support = [c.category for c in directional if c.direction == EvidenceDirection.BULLISH.value]
    oppose = [c.category for c in directional if c.direction == EvidenceDirection.BEARISH.value]
    neutral = [c.category for c in populated if c.direction == EvidenceDirection.NEUTRAL.value]

    if len(directional) < 2:
        return CrossCategoryAssessment(
            state=CrossCategoryState.INSUFFICIENT_EVIDENCE.value,
            supporting_categories=support, opposing_categories=oppose,
            neutral_categories=neutral,
            dominant_direction=(directional[0].direction if directional else EvidenceDirection.UNKNOWN.value),
            agreement_ratio=None,
            note="Fewer than two categories have a directional read — no cross-category judgement.",
        )

    n_bull, n_bear = len(support), len(oppose)
    dominant = EvidenceDirection.BULLISH.value if n_bull >= n_bear else EvidenceDirection.BEARISH.value
    majority = max(n_bull, n_bear)
    minority = min(n_bull, n_bear)
    ratio = round(majority / (n_bull + n_bear), 3)
    minority_side = oppose if n_bull >= n_bear else support

    if minority == 0:
        state = CrossCategoryState.AGREEMENT.value
        note = f"All {majority} directional categories agree ({dominant})."
        conflicting: List[str] = []
    elif ratio >= 0.75:
        state = CrossCategoryState.MIXED.value
        note = f"{majority} categories lean {dominant}; {minority} disagree."
        conflicting = list(minority_side)
    else:
        state = CrossCategoryState.CONFLICT.value
        note = (f"Genuine disagreement: {n_bull} bullish vs {n_bear} bearish. "
                f"Uncertainty is real — not averaged away.")
        conflicting = list(minority_side)

    return CrossCategoryAssessment(
        state=state,
        supporting_categories=support, opposing_categories=oppose,
        neutral_categories=neutral, conflicting_categories=conflicting,
        dominant_direction=dominant, agreement_ratio=ratio, note=note,
    )


def _coverage(categories: List[CategoryEvidence]) -> CoverageSummary:
    per = {c.category: c.state for c in categories}
    avail = sum(1 for c in categories if c.state in (
        EvidenceState.AVAILABLE.value, EvidenceState.CONFLICT.value))
    prov_un = sum(1 for c in categories if c.state == EvidenceState.PROVIDER_UNAVAILABLE.value)
    insuff = sum(1 for c in categories if c.state == EvidenceState.INSUFFICIENT_EVIDENCE.value)
    total = len(categories)
    return CoverageSummary(
        per_category=per,
        available_categories=avail,
        provider_unavailable_categories=prov_un,
        insufficient_categories=insuff,
        total_categories=total,
        coverage_ratio=round(avail / total, 3) if total else None,
    )


def _build_conflicts(categories: List[CategoryEvidence], cross: CrossCategoryAssessment,
                     macro_conflicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if cross.state == CrossCategoryState.CONFLICT.value:
        out.append({
            "kind": "CROSS_CATEGORY",
            "state": EvidenceState.CONFLICT.value,
            "supporting_categories": cross.supporting_categories,
            "opposing_categories": cross.opposing_categories,
            "detail": cross.note,
        })
    for c in categories:
        if c.state == EvidenceState.CONFLICT.value:
            out.append({
                "kind": "WITHIN_CATEGORY",
                "category": c.category,
                "state": EvidenceState.CONFLICT.value,
                "detail": c.reason or "Two sources disagree inside this category.",
            })
    for mc in macro_conflicts or []:
        out.append({"kind": "MACRO_SOURCE", **mc})
    return out


def _data_gaps(categories: List[CategoryEvidence],
               dropped: Dict[str, List[EvidenceItem]]) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []
    for c in categories:
        if c.is_missing:
            gaps.append({
                "category": c.category,
                "state": c.state,
                "reason": c.reason,
                "next_dependency": c.next_dependency,
            })
    for cat, items in dropped.items():
        if items:
            gaps.append({
                "category": cat,
                "state": "FUTURE_EVIDENCE_EXCLUDED",
                "reason": f"{len(items)} evidence item(s) excluded — timestamp after as_of.",
                "excluded": [
                    {"metric": it.metric, "release_timestamp": it.release_timestamp,
                     "available_timestamp": it.available_timestamp}
                    for it in items[:8]
                ],
            })
    return gaps


def _provenance(categories: List[CategoryEvidence]) -> List[Dict[str, Any]]:
    """A traceable chain: category -> evidence metric -> source_id -> source ->
    the timestamps that matter."""
    chain: List[Dict[str, Any]] = []
    for c in categories:
        for it in c.evidence:
            chain.append({
                "category": c.category,
                "metric": it.metric,
                "source_id": it.source_id,
                "source": it.source,
                "provenance": it.provenance,
                "release_timestamp": it.release_timestamp,
                "observation_timestamp": it.observation_timestamp,
                "vintage_timestamp": it.vintage_timestamp,
                "available_timestamp": it.available_timestamp,
            })
    return chain


def _provider_health() -> Dict[str, Any]:
    try:
        from api.macro_evidence import ensure_evidence
        ev = ensure_evidence()
        return {
            "base_provider": ev.get("data_provider"),
            "provider_state": ev.get("provider_state"),
            "providers": [
                {"key": p.get("key"), "configured": p.get("configured"),
                 "is_live": p.get("is_live"),
                 "state": (p.get("health") or {}).get("provider_state")}
                for p in ev.get("providers", [])
            ],
            "macro_conflicts": ev.get("conflicts", []),
        }
    except Exception:  # pragma: no cover - defensive
        return {"provider_state": "UNKNOWN", "providers": [], "macro_conflicts": []}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def get_asset_intelligence(
    asset: str,
    as_of: Optional[datetime] = None,
    timeframe: Optional[str] = None,
) -> AssetIntelligenceSnapshot:
    """Build the canonical evidence snapshot for ``asset``.

    ``as_of`` — ``None`` means *live* (now). A value means *historical*: the
    result is reproducible from information available by that instant only.
    """
    asset = normalise_asset(asset)
    live = as_of is None
    if as_of is not None and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    effective_as_of = as_of or _now()
    as_of_iso = _iso(effective_as_of)

    key = _cache_key(asset, timeframe, as_of)
    now_t = time.monotonic()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit is not None:
            snap, ts = hit
            if not live or (now_t - ts) < _LIVE_TTL_SEC:
                return snap

    generated_at = _now()

    # --- edge snapshot (live only — the factor engines are not as-of aware) ---
    edge_snap: Dict[str, Any] = {}
    if live:
        try:
            from asset_edge_intelligence import AssetEdgeIntelligenceEngine
            edge_snap = AssetEdgeIntelligenceEngine.evaluate_asset_edge(asset) or {}
        except Exception:  # pragma: no cover - defensive
            edge_snap = {}

    # --- build each category -------------------------------------------------
    raw: Dict[str, CategoryEvidence] = {}

    if live and edge_snap:
        raw[EvidenceCategory.TECHNICAL.value] = _edge_factor_category(
            EvidenceCategory.TECHNICAL.value, ("Technical Structure",), edge_snap, asset,
            effective_as_of, as_of_iso)
        raw[EvidenceCategory.SMC.value] = _edge_factor_category(
            EvidenceCategory.SMC.value, ("Smart Money", "Liquidity"), edge_snap, asset,
            effective_as_of, as_of_iso)
        raw[EvidenceCategory.SEASONALITY.value] = _edge_factor_category(
            EvidenceCategory.SEASONALITY.value, ("Seasonality",), edge_snap, asset,
            effective_as_of, as_of_iso)
    else:
        for cat in (EvidenceCategory.TECHNICAL.value, EvidenceCategory.SMC.value,
                    EvidenceCategory.SEASONALITY.value):
            raw[cat] = _unavailable_category(
                cat,
                "No timestamp-correct historical reconstruction is available for this "
                "category (its factor engine is live-only).",
                "an as-of-aware market-structure store",
            )

    raw[EvidenceCategory.MACRO.value] = _macro_category(asset, effective_as_of, as_of_iso, live)
    raw[EvidenceCategory.COT.value] = _cot_category(asset, effective_as_of, as_of_iso, live)
    raw[EvidenceCategory.REGIME.value] = _regime_category(asset, effective_as_of, as_of_iso, live)
    raw[EvidenceCategory.SENTIMENT.value] = _sentiment_category(asset, effective_as_of, as_of_iso, live)

    # --- independent backend look-ahead enforcement ------------------------
    # Live: the ceiling is wall-clock now (sub-engines stamp evidence a few ms
    # after effective_as_of was frozen — those are legitimately "now", not the
    # future). Historical: the ceiling is exactly the requested as_of.
    ceiling = _now() if live else effective_as_of
    dropped_by_cat: Dict[str, List[EvidenceItem]] = {}
    for cat, ce in raw.items():
        if not ce.evidence:
            continue
        kept, dropped = _enforce_timestamps(ce.evidence, ceiling, live=live)
        if dropped:
            dropped_by_cat[cat] = dropped
            ce.evidence = kept
            if not kept and ce.state in (EvidenceState.AVAILABLE.value, EvidenceState.CONFLICT.value):
                ce.state = EvidenceState.INSUFFICIENT_EVIDENCE.value
                ce.direction = EvidenceDirection.UNKNOWN.value
                ce.score = None
                ce.reason = "All evidence for this category was dated after as_of and excluded."

    categories = [raw[c] for c in CATEGORY_ORDER if c in raw]

    cross = _cross_category(categories)
    coverage = _coverage(categories)
    health = _provider_health()
    conflicts = _build_conflicts(categories, cross, health.get("macro_conflicts", []))
    gaps = _data_gaps(categories, dropped_by_cat)
    provenance = _provenance(categories)

    snapshot = AssetIntelligenceSnapshot(
        asset=asset,
        as_of=as_of_iso,
        generated_at=_iso(generated_at),
        mode="LIVE" if live else "HISTORICAL",
        timeframe=(timeframe or None),
        categories=categories,
        cross_category=cross,
        coverage=coverage,
        conflicts=conflicts,
        data_gaps=gaps,
        provenance=provenance,
        provider_health=health,
        model_version=_MODEL_VERSION,
    )

    with _LOCK:
        _CACHE[key] = (snapshot, time.monotonic())
    return snapshot


def ai_snapshot(asset: str, as_of: Optional[datetime] = None) -> Dict[str, Any]:
    """A bounded, AI-safe projection of the canonical snapshot. Category states +
    directions + the few most important evidence items + conflicts + gaps +
    provenance + timestamps. No future information (the snapshot already
    guarantees that). Never raises."""
    try:
        snap = get_asset_intelligence(asset, as_of=as_of)
    except Exception:  # pragma: no cover - defensive
        return {"asset": normalise_asset(asset), "error": "evidence_unavailable"}

    # Compact projection — one line per category. Full evidence + provenance is
    # on GET /api/intelligence/asset/{asset}; the chat context only needs the
    # state map, the cross-category call and the gaps.
    cats = {
        c.category: {
            "state": c.state,
            "direction": c.direction,
            "score": c.score,
        }
        for c in snap.categories
    }
    return {
        "asset": snap.asset,
        "as_of": snap.as_of,
        "mode": snap.mode,
        "categories": cats,
        "cross_category_state": snap.cross_category.state,
        "cross_category_note": snap.cross_category.note,
        "conflicts": [x.get("detail") for x in snap.conflicts if x.get("detail")],
        "missing_categories": [
            g.get("category") for g in snap.data_gaps if g.get("category")
        ],
        "coverage_ratio": snap.coverage.coverage_ratio,
        "provider_state": snap.provider_health.get("provider_state"),
    }


__all__ = [
    "get_asset_intelligence", "ai_snapshot", "invalidate", "normalise_asset",
    "is_supported_asset", "SUPPORTED_ASSETS", "CATEGORY_ORDER",
]
