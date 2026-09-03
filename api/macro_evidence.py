# -*- coding: utf-8 -*-
"""
Multi-provider macro evidence orchestrator (Phase 66).

One entry point — ``ensure_evidence()`` — that every macro read funnels through
(``api.macro_provider.ensure_macro_data`` is now a thin shim over it). It:

  1. hydrates the base **observation** provider (seed_demo / none / FRED)
  2. hydrates the **COT** provider (CFTC) — additive
  3. pulls **consensus forecasts** and merges them onto matching releases by the
     canonical release identity ``(country, metric, period)`` — never by name
  4. runs deterministic **conflict detection** with a documented source
     precedence, and surfaces ``CONFLICT`` rather than silently picking a value
  5. builds a per-economy × per-category **coverage matrix**
  6. returns one provenance/status dict — same keys the old shim returned, plus
     ``providers`` / ``capabilities`` / ``coverage`` / ``conflicts`` (the macro
     response envelope allows extra keys, so downstream shapers pass them
     through untouched)

The scoring engines are never called from here and never learn a vendor name.
No import of / path to execution_pipeline, broker_adapter, risk_gateway.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from api.providers.registry import (
    CAPABILITY_CATEGORIES,
    Capability,
    MacroProviderRegistry,
    cot_provider_key,
)

# category <- indicator family
_FAMILY_CATEGORY = {
    "GROWTH": "growth",
    "LABOR": "jobs",
    "INFLATION": "inflation",
    "MONETARY_POLICY": "inflation",
    "SENTIMENT_POSITIONING": "cot",
}
_OBSERVATION_CATEGORIES = ("growth", "jobs", "inflation")
_ALL_CATEGORIES = ("growth", "jobs", "inflation", "cot", "sentiment")
_COVERAGE_COUNTRIES = ("USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF")

# --- source precedence (documented, justified) -----------------------------
# Higher rank wins a conflict. Rationale:
#   4  a national statistical agency / central bank, direct
#   3  FRED / ALFRED — the Federal Reserve's mirror of official series
#   2  OECD-harmonised cross-country series
#   1  any other secondary aggregator
#   0  unknown
_PRECEDENCE_RULES = [
    (4, ("BLS", "BEA", "CENSUS", "EUROSTAT", "ONS", "STATISTICS BUREAU", "CABINET OFFICE",
         "FEDERAL RESERVE", "ECB", "BANK OF ENGLAND", "BANK OF JAPAN", "CFTC",
         "COMMODITY FUTURES TRADING COMMISSION", "DEPARTMENT OF LABOR")),
    (3, ("FRED", "ALFRED")),
    (2, ("OECD",)),
]
_CONFLICT_TOLERANCE = 0.05  # absolute; values within this are "agree"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_rank(source: Optional[str]) -> int:
    s = (source or "").upper()
    for rank, needles in _PRECEDENCE_RULES:
        if any(n in s for n in needles):
            return rank
    return 1 if s else 0


# --- conflict detection --------------------------------------------------

def detect_conflicts(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """``claims`` = list of ``{"identity": (country, metric, period), "field":
    "actual"|"previous"|"forecast", "source": str, "value": float}``.

    Returns one entry per (identity, field) where two sources give materially
    different values, naming the precedence-selected winner. Identical values
    (within tolerance) never produce a conflict.
    """
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for c in claims:
        if c.get("value") is None:
            continue
        groups.setdefault((tuple(c["identity"]), c["field"]), []).append(c)

    out: List[Dict[str, Any]] = []
    for (identity, field), items in groups.items():
        vals = [i["value"] for i in items]
        if max(vals) - min(vals) <= _CONFLICT_TOLERANCE:
            continue
        winner = max(items, key=lambda i: (source_rank(i["source"]), str(i["source"])))
        out.append({
            "identity": list(identity),
            "country": identity[0],
            "metric": identity[1],
            "period": identity[2],
            "field": field,
            "state": "CONFLICT",
            "selected_source": winner["source"],
            "selected_value": winner["value"],
            "claims": [{"source": i["source"], "value": i["value"], "rank": source_rank(i["source"])}
                       for i in sorted(items, key=lambda i: -source_rank(i["source"]))],
        })
    return out


# --- forecast merge ----------------------------------------------------

def merge_forecasts(forecasts: List[Any], *, as_of: Optional[datetime] = None) -> Dict[str, Any]:
    """Attach consensus forecasts to matching releases in EconomicDataRegistry.

    Match ONLY on ``(country, metric, period)``. A forecast with no matching
    release is dropped (we never invent a release to hang a forecast on). A
    forecast whose vintage is not yet known at ``as_of`` is skipped.
    """
    from api.providers.forecast_provider import forecast_lookahead_ok
    from macro_intelligence_engine import EconomicDataRegistry

    EconomicDataRegistry.seed_canonical_registry()  # no-op if provider-managed / already seeded
    by_identity: Dict[tuple, Any] = {}
    for r in EconomicDataRegistry._RELEASES:
        by_identity[(r.country, r.metric, r.period)] = r

    merged = 0
    unmatched = 0
    claims: List[Dict[str, Any]] = []
    for fc in forecasts:
        if getattr(fc, "forecast", None) is None:
            continue
        if not forecast_lookahead_ok(fc, as_of):
            continue
        rec = by_identity.get(fc.identity())
        if rec is None:
            unmatched += 1
            continue
        if rec.forecast is not None:
            claims.append({"identity": fc.identity(), "field": "forecast",
                           "source": rec.source, "value": float(rec.forecast)})
            claims.append({"identity": fc.identity(), "field": "forecast",
                           "source": fc.source, "value": float(fc.forecast)})
        rec.forecast = float(fc.forecast)
        if rec.previous is None and getattr(fc, "previous", None) is not None:
            rec.previous = float(fc.previous)
        elif getattr(fc, "previous", None) is not None and rec.previous is not None:
            claims.append({"identity": fc.identity(), "field": "previous",
                           "source": rec.source, "value": float(rec.previous)})
            claims.append({"identity": fc.identity(), "field": "previous",
                           "source": fc.source, "value": float(fc.previous)})
        merged += 1

    return {"merged": merged, "unmatched": unmatched, "conflicts": detect_conflicts(claims)}


# --- coverage matrix -------------------------------------------------

def _base_state(meta: Dict[str, Any]) -> str:
    st = meta.get("provider_state") or ""
    if st in ("PROVIDER_UNAVAILABLE", "PENDING"):
        return "PROVIDER_UNAVAILABLE"
    if st == "NONE":
        return "NONE"
    if meta.get("provider_is_live"):
        return "LIVE" if meta.get("provenance") == "live" else "PROVIDER_UNAVAILABLE"
    if st == "SEED_DEMO":
        return "SEED_DEMO"
    return "SEED_DEMO"


def build_coverage(meta: Dict[str, Any], cot_status: Optional[Dict[str, Any]],
                   conflict_countries: set) -> Dict[str, Dict[str, str]]:
    from macro_intelligence_engine import EconomicDataRegistry, INDICATOR_METADATA

    base = _base_state(meta)
    cot_live = set((cot_status or {}).get("coverage") or [])
    cot_state = (cot_status or {}).get("provider_state")

    matrix: Dict[str, Dict[str, str]] = {}
    for ccy in _COVERAGE_COUNTRIES:
        try:
            releases = EconomicDataRegistry.get_releases_as_of(country=ccy)
        except Exception:
            releases = []
        fams = set()
        for r in releases:
            fam = INDICATOR_METADATA.get(r.metric, {}).get("family")
            if fam:
                fams.add(fam)
        cats: Dict[str, str] = {}
        for cat in _OBSERVATION_CATEGORIES:
            has = any(_FAMILY_CATEGORY.get(f) == cat for f in fams)
            if base == "PROVIDER_UNAVAILABLE":
                cats[cat] = "PROVIDER_UNAVAILABLE"
            elif base == "NONE":
                cats[cat] = "NONE"
            elif has and ccy in conflict_countries:
                cats[cat] = "CONFLICT"
            elif has:
                cats[cat] = "LIVE" if base == "LIVE" else "SEED_DEMO"
            else:
                cats[cat] = "INSUFFICIENT_EVIDENCE"
        # cot
        has_cot = any(r.metric == "COT_NET_POSITIONING" for r in releases)
        if ccy in cot_live:
            cats["cot"] = "LIVE"
        elif cot_state == "PROVIDER_UNAVAILABLE":
            cats["cot"] = "PROVIDER_UNAVAILABLE"
        elif has_cot and base == "SEED_DEMO":
            cats["cot"] = "SEED_DEMO"
        else:
            cats["cot"] = "INSUFFICIENT_EVIDENCE"
        # sentiment — no provider
        cats["sentiment"] = "INSUFFICIENT_EVIDENCE"
        matrix[ccy] = cats
    return matrix


# --- base observation provider ------------------------------------

def _base_meta() -> Dict[str, Any]:
    key = (os.getenv("MACRO_DATA_PROVIDER") or "seed_demo").strip().lower()
    if key == "fred":
        try:
            from api.providers.fred_provider import FredMacroProvider
            st = FredMacroProvider().hydrate_registry()
            return {
                "data_provider": "fred",
                "provider_is_live": True,
                "provenance": "live" if st.get("records_registered", 0) > 0 else "unavailable",
                "provider_state": st.get("provider_state", "PENDING"),
                "provider_status": st,
            }
        except Exception as exc:  # pragma: no cover - defensive
            return {
                "data_provider": "fred", "provider_is_live": True,
                "provenance": "unavailable", "provider_state": "PROVIDER_UNAVAILABLE",
                "provider_status": {"last_error": type(exc).__name__},
            }
    if key == "none":
        return {"data_provider": "none", "provider_is_live": False,
                "provenance": "unavailable", "provider_state": "NONE"}
    return {"data_provider": "seed_demo", "provider_is_live": False,
            "provenance": "seed_demo", "provider_state": "SEED_DEMO"}


def ensure_evidence(*, as_of: Optional[datetime] = None) -> Dict[str, Any]:
    """The one macro-evidence entry point. Never raises."""
    meta = _base_meta()

    # 2. COT (additive)
    cot_status: Optional[Dict[str, Any]] = None
    if cot_provider_key() == "cftc":
        try:
            from api.providers.cftc_provider import CftcCotProvider
            cot_status = CftcCotProvider().hydrate_registry()
        except Exception as exc:  # pragma: no cover - defensive
            cot_status = {"provider_state": "PROVIDER_UNAVAILABLE", "last_error": type(exc).__name__}

    # 3. forecasts (merge)
    forecast_status: Optional[Dict[str, Any]] = None
    merge_result: Dict[str, Any] = {"merged": 0, "unmatched": 0, "conflicts": []}
    try:
        from api.providers.forecast_provider import get_forecast_provider
        fp = get_forecast_provider()
        forecast_status = fp.status()
        if getattr(fp, "configured", False) and meta.get("provenance") != "unavailable":
            fp.hydrate()
            merge_result = merge_forecasts(fp.get_forecasts(as_of=as_of), as_of=as_of)
    except Exception as exc:  # pragma: no cover - defensive
        forecast_status = {"provider_state": "PROVIDER_UNAVAILABLE", "last_error": type(exc).__name__}

    # 4. sentiment
    sentiment_status: Optional[Dict[str, Any]] = None
    try:
        from api.providers.sentiment_provider import get_sentiment_provider
        sentiment_status = get_sentiment_provider().status()
    except Exception:  # pragma: no cover - defensive
        sentiment_status = None

    conflicts = list(merge_result.get("conflicts") or [])
    conflict_countries = {c["country"] for c in conflicts}

    coverage = build_coverage(meta, cot_status, conflict_countries)

    out = dict(meta)
    if conflicts and out.get("provider_state") in ("LIVE", "SEED_DEMO"):
        out["provider_state"] = "CONFLICT"
    out.update({
        "as_of": _now(),
        "providers": [i.to_dict() for i in MacroProviderRegistry.discover()],
        "capabilities": _capability_summary(),
        "coverage": coverage,
        "conflicts": conflicts,
        "cot_status": cot_status,
        "forecast_status": forecast_status,
        "sentiment_status": sentiment_status,
        "forecast_merge": {"merged": merge_result.get("merged", 0),
                           "unmatched": merge_result.get("unmatched", 0)},
    })
    return out


def providers_report() -> Dict[str, Any]:
    """Read-only provider diagnostics for `GET /api/macro/providers`. Runs a
    TTL-guarded evidence refresh first so health reflects reality. Never exposes
    a secret — provider `status()` methods only report state / coverage / errors.
    """
    ev = ensure_evidence()
    infos = MacroProviderRegistry.discover()
    return {
        "available": any(i.configured for i in infos),
        "as_of": _now(),
        "base_provider": ev.get("data_provider"),
        "provider_state": ev.get("provider_state"),
        "providers": [i.to_dict() for i in infos],
        "capabilities": ev.get("capabilities", {}),
        "coverage": ev.get("coverage", {}),
        "conflicts": ev.get("conflicts", []),
        "precedence": [
            {"rank": rank, "matches": list(needles)} for rank, needles in _PRECEDENCE_RULES
        ] + [{"rank": 1, "matches": ["any other named source"]},
             {"rank": 0, "matches": ["unknown"]}],
        "disclaimer": "Read-only provider diagnostics. Macro is context, never an execution signal.",
        "timestamp": _now(),
    }


def _capability_summary() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for cap in Capability:
        keys = MacroProviderRegistry.providers_for(cap)
        configured = []
        for k in keys:
            prov = MacroProviderRegistry.get(k)
            if prov is not None and getattr(prov, "configured", False):
                configured.append(k)
        out[str(cap)] = {
            "declared_by": keys,
            "configured_by": configured,
            "available": bool(configured),
            "categories": CAPABILITY_CATEGORIES.get(cap, []),
        }
    return out
