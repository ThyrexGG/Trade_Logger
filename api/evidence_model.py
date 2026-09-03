# -*- coding: utf-8 -*-
"""
Canonical evidence model for the Unified Evidence Fusion layer (Phase 67).

This module defines *only* the data representation — no orchestration, no I/O,
no scoring, no network, no import of / path to any execution module. The fusion
engine (``api.evidence_fusion``) populates these structures from the existing
authoritative engines; the API router serialises them.

Design rules honoured here (see ``docs/PHASE_67_EVIDENCE_FUSION.md``):

  * Missing evidence must stay distinguishable from neutral evidence — hence an
    explicit :class:`EvidenceState` on every item and category. ``PROVIDER_UNAVAILABLE``
    is never collapsed into ``INSUFFICIENT_EVIDENCE``.
  * Nothing is invented. A field the source cannot supply is ``None`` — never a
    fabricated number. ``confidence=None`` is a valid, honest value.
  * Timestamps are first-class. Every item carries the instants that matter for
    look-ahead safety (``available_timestamp``, plus release / observation /
    vintage where the source is an economic release).
  * There is no blind composite. A category exposes its own score/direction; the
    snapshot exposes an evidence matrix and a cross-category assessment, not a
    single magic number.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class EvidenceState(str, Enum):
    """The lifecycle state of one evidence item or one category summary.

    These states are deliberately distinct. Downstream code and the UI must be
    able to tell "we asked and there is no source" (``PROVIDER_UNAVAILABLE``)
    apart from "there is a source but not enough data yet"
    (``INSUFFICIENT_EVIDENCE``) apart from "the data is real but old"
    (``STALE``) apart from "two sources disagree" (``CONFLICT``).
    """

    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    STALE = "STALE"
    CONFLICT = "CONFLICT"
    NOT_APPLICABLE = "NOT_APPLICABLE"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class EvidenceDirection(str, Enum):
    """Directional lean of an evidence item / category, normalised across sources."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class CrossCategoryState(str, Enum):
    """Whether the populated categories agree, disagree, or can't be judged."""

    AGREEMENT = "AGREEMENT"
    MIXED = "MIXED"
    CONFLICT = "CONFLICT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


# Canonical category identifiers. Only categories with a real source in the repo
# are ever populated; the rest are reported as INSUFFICIENT_EVIDENCE so coverage
# stays honest (see EvidenceFusionEngine.CATEGORY_ORDER).
class EvidenceCategory(str, Enum):
    TECHNICAL = "TECHNICAL"
    SMC = "SMC"
    MACRO = "MACRO"
    COT = "COT"
    REGIME = "REGIME"
    SEASONALITY = "SEASONALITY"
    SENTIMENT = "SENTIMENT"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


_DIRECTION_ALIASES = {
    "BULLISH": EvidenceDirection.BULLISH,
    "LEAN BULLISH": EvidenceDirection.BULLISH,
    "VERY BULLISH": EvidenceDirection.BULLISH,
    "EXTREME BULLISH": EvidenceDirection.BULLISH,
    "LONG": EvidenceDirection.BULLISH,
    "POSITIVE": EvidenceDirection.BULLISH,
    "UP": EvidenceDirection.BULLISH,
    "BEARISH": EvidenceDirection.BEARISH,
    "LEAN BEARISH": EvidenceDirection.BEARISH,
    "VERY BEARISH": EvidenceDirection.BEARISH,
    "EXTREME BEARISH": EvidenceDirection.BEARISH,
    "SHORT": EvidenceDirection.BEARISH,
    "NEGATIVE": EvidenceDirection.BEARISH,
    "DOWN": EvidenceDirection.BEARISH,
    "NEUTRAL": EvidenceDirection.NEUTRAL,
    "INLINE": EvidenceDirection.NEUTRAL,
    "FLAT": EvidenceDirection.NEUTRAL,
    "MIXED": EvidenceDirection.NEUTRAL,
}


def normalise_direction(raw: Any) -> EvidenceDirection:
    """Map a source's free-text direction onto the canonical enum. Unknown /
    missing text becomes ``UNKNOWN`` — never silently ``NEUTRAL``."""
    if raw is None:
        return EvidenceDirection.UNKNOWN
    if isinstance(raw, EvidenceDirection):
        return raw
    key = str(raw).strip().upper()
    if not key:
        return EvidenceDirection.UNKNOWN
    return _DIRECTION_ALIASES.get(key, EvidenceDirection.UNKNOWN)


def direction_from_score(
    score: Optional[float], *, bullish_at: float = 10.0, bearish_at: float = -10.0
) -> EvidenceDirection:
    """Derive a direction from a signed score in [-100, 100]. ``None`` -> UNKNOWN."""
    if score is None:
        return EvidenceDirection.UNKNOWN
    if score >= bullish_at:
        return EvidenceDirection.BULLISH
    if score <= bearish_at:
        return EvidenceDirection.BEARISH
    return EvidenceDirection.NEUTRAL


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_ts(raw: Any) -> Optional[datetime]:
    """Best-effort parse of an ISO timestamp (accepts a trailing ``Z``).
    Returns a tz-aware UTC ``datetime`` or ``None``. Never raises."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        s = str(raw).strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Evidence item
# ---------------------------------------------------------------------------
@dataclass
class EvidenceItem:
    """One atomic, source-attributed observation about an asset.

    Not every source populates every field. ``None`` means "this source cannot
    tell us" — it is never a stand-in for zero / neutral.
    """

    asset: str
    category: str                       # EvidenceCategory value
    metric: str                         # e.g. "CPI", "4H structure", "net positioning"
    state: str = EvidenceState.AVAILABLE.value

    value: Optional[float] = None
    unit: Optional[str] = None
    direction: str = EvidenceDirection.UNKNOWN.value
    strength: Optional[float] = None    # 0..1 magnitude of the signal, if derivable
    confidence: Optional[float] = None  # 0..1 — None when not objectively derivable

    # provenance
    source: Optional[str] = None        # human label, e.g. "FRED", "CFTC", "Edge Engine"
    source_id: Optional[str] = None     # machine id, e.g. "CPIAUCSL", "COT_NET_POSITIONING"
    provenance: Optional[str] = None    # "live" | "seed_demo" | "derived" | "unavailable"

    # timestamps (all ISO-8601 UTC strings)
    as_of: Optional[str] = None                 # snapshot instant this item was cut for
    available_timestamp: Optional[str] = None   # when this fact became knowable
    release_timestamp: Optional[str] = None     # economic release: first public print
    observation_timestamp: Optional[str] = None # economic release: the period observed
    vintage_timestamp: Optional[str] = None     # economic release: data vintage

    note: Optional[str] = None

    # ------------------------------------------------------------------
    def age_seconds(self, *, now: Optional[datetime] = None) -> Optional[float]:
        ref = now or datetime.now(timezone.utc)
        base = parse_ts(self.available_timestamp) or parse_ts(self.release_timestamp)
        if base is None:
            return None
        return max(0.0, (ref - base).total_seconds())

    def is_visible_at(self, as_of: datetime) -> bool:
        """True iff this item was knowable at ``as_of``. An item exactly at the
        boundary IS visible (``<=``). An item with no knowable timestamp is
        treated as visible only in live mode — the fusion engine decides that;
        here we answer purely on the timestamps we hold."""
        for ts in (self.available_timestamp, self.release_timestamp):
            dt = parse_ts(ts)
            if dt is not None and dt > as_of:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["age_seconds"] = self.age_seconds()
        return d


# ---------------------------------------------------------------------------
# Category summary
# ---------------------------------------------------------------------------
@dataclass
class CategoryEvidence:
    """A category-level roll-up of its evidence items. The score/direction are
    the category's own (from its authoritative engine) — they are NOT blended
    with other categories here."""

    category: str
    state: str = EvidenceState.INSUFFICIENT_EVIDENCE.value
    direction: str = EvidenceDirection.UNKNOWN.value
    score: Optional[float] = None          # category-native score, -100..100
    confidence: Optional[float] = None     # 0..1 or None
    coverage: Optional[float] = None       # 0..1 — how much of the category's inputs resolved
    freshness: Optional[str] = None        # "FRESH" | "RECENT" | "STALE" | None
    age_seconds: Optional[float] = None
    sources: List[str] = field(default_factory=list)
    provenance: Optional[str] = None
    evidence: List[EvidenceItem] = field(default_factory=list)
    reason: Optional[str] = None           # why INSUFFICIENT_EVIDENCE / PROVIDER_UNAVAILABLE
    next_dependency: Optional[str] = None  # what would make this category available

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def is_populated(self) -> bool:
        return self.state == EvidenceState.AVAILABLE.value

    @property
    def is_missing(self) -> bool:
        return self.state in (
            EvidenceState.INSUFFICIENT_EVIDENCE.value,
            EvidenceState.PROVIDER_UNAVAILABLE.value,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "state": self.state,
            "direction": self.direction,
            "score": self.score,
            "confidence": self.confidence,
            "coverage": self.coverage,
            "freshness": self.freshness,
            "age_seconds": self.age_seconds,
            "evidence_count": self.evidence_count,
            "sources": list(self.sources),
            "provenance": self.provenance,
            "reason": self.reason,
            "next_dependency": self.next_dependency,
            "evidence": [e.to_dict() for e in self.evidence],
        }


# ---------------------------------------------------------------------------
# Cross-category assessment
# ---------------------------------------------------------------------------
@dataclass
class CrossCategoryAssessment:
    """Explicit agreement / disagreement across the populated categories.
    Disagreement is represented, never averaged away."""

    state: str = CrossCategoryState.INSUFFICIENT_EVIDENCE.value
    supporting_categories: List[str] = field(default_factory=list)   # bullish lean
    opposing_categories: List[str] = field(default_factory=list)     # bearish lean
    neutral_categories: List[str] = field(default_factory=list)
    conflicting_categories: List[str] = field(default_factory=list)  # the minority side
    dominant_direction: str = EvidenceDirection.UNKNOWN.value
    agreement_ratio: Optional[float] = None   # 0..1 across directional categories
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CoverageSummary:
    """Category availability, computed only from real category states."""

    per_category: Dict[str, str] = field(default_factory=dict)   # category -> EvidenceState
    available_categories: int = 0
    provider_unavailable_categories: int = 0
    insufficient_categories: int = 0
    total_categories: int = 0
    coverage_ratio: Optional[float] = None    # available / total, 0..1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Asset intelligence snapshot
# ---------------------------------------------------------------------------
@dataclass
class AssetIntelligenceSnapshot:
    """The single canonical, timestamp-correct evidence representation of one
    asset. Consumed by the API, the Asset Deep Dive, the AI context builder and
    research surfaces."""

    asset: str
    as_of: str                              # ISO UTC — the instant everything is cut for
    generated_at: str                       # ISO UTC — wall-clock of this computation
    mode: str = "LIVE"                       # "LIVE" | "HISTORICAL"
    timeframe: Optional[str] = None

    categories: List[CategoryEvidence] = field(default_factory=list)
    cross_category: CrossCategoryAssessment = field(default_factory=CrossCategoryAssessment)
    coverage: CoverageSummary = field(default_factory=CoverageSummary)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    data_gaps: List[Dict[str, Any]] = field(default_factory=list)
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    provider_health: Dict[str, Any] = field(default_factory=dict)

    model_version: str = "phase67-evidence-fusion-1"
    disclaimer: str = (
        "UNIFIED EVIDENCE CONTEXT — deterministic, read-only, timestamp-correct. "
        "Category scores are contextual intelligence, never an execution signal. "
        "Missing evidence is not neutral evidence; a provider outage is not "
        "insufficient evidence."
    )
    safety_barrier: Dict[str, Any] = field(
        default_factory=lambda: {
            "live_automation_enabled": False,
            "live_broker_transmission": "BLOCKED",
        }
    )

    # ------------------------------------------------------------------
    def category(self, name: str) -> Optional[CategoryEvidence]:
        for c in self.categories:
            if c.category == str(name):
                return c
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "as_of": self.as_of,
            "generated_at": self.generated_at,
            "mode": self.mode,
            "timeframe": self.timeframe,
            "categories": [c.to_dict() for c in self.categories],
            "cross_category_state": self.cross_category.state,
            "cross_category": self.cross_category.to_dict(),
            "coverage": self.coverage.to_dict(),
            "conflicts": list(self.conflicts),
            "data_gaps": list(self.data_gaps),
            "provenance": list(self.provenance),
            "provider_health": dict(self.provider_health),
            "model_version": self.model_version,
            "disclaimer": self.disclaimer,
            "safety_barrier": dict(self.safety_barrier),
        }


__all__ = [
    "EvidenceState",
    "EvidenceDirection",
    "CrossCategoryState",
    "EvidenceCategory",
    "EvidenceItem",
    "CategoryEvidence",
    "CrossCategoryAssessment",
    "CoverageSummary",
    "AssetIntelligenceSnapshot",
    "normalise_direction",
    "direction_from_score",
    "parse_ts",
]
