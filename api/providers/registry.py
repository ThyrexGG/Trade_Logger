# -*- coding: utf-8 -*-
"""
Macro provider registry & capability model (Phase 66).

The intelligence engine must know *what data exists*, never *which vendor
supplied it*. This module is the seam that keeps that true:

  * every provider declares a ``KEY`` and an explicit set of ``Capability`` —
    an unsupported capability is simply absent, never faked
  * the registry discovers providers, reports which are configured / live, and
    aggregates their self-reported health
  * nothing here fetches data or scores anything; it is pure metadata +
    dispatch, with no import of / path to any execution module

Providers implementing the informal contract expose:

    KEY: str
    CAPABILITIES: frozenset[Capability]
    configured: bool          # property — is a usable source configured?
    is_live: bool             # class attr — does it claim to serve real data?
    name: str                 # human label
    status() -> dict          # health / coverage / errors (NEVER secrets)
    hydrate() -> dict         # best-effort refresh; never raises

The forecast / sentiment "null" providers implement the same shape and simply
report ``configured = False`` + empty results, so a category with no source
resolves to INSUFFICIENT_EVIDENCE rather than a fabricated number.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class Capability(str, Enum):
    """A concrete thing a provider can actually supply. Absent == not supplied."""

    OBSERVATIONS = "observations"                 # released actual values
    RELEASE_TIMESTAMPS = "release_timestamps"     # real first-print timestamps
    REVISIONS = "revisions"                       # vintage / revision history
    HISTORICAL = "historical"                     # multi-year back history
    CONSENSUS_FORECAST = "consensus_forecast"     # survey / consensus forecast
    RELEASE_CALENDAR = "release_calendar"         # scheduled upcoming releases
    COT_POSITIONING = "cot_positioning"           # CFTC Commitments of Traders
    RETAIL_SENTIMENT = "retail_sentiment"         # broker / crowd positioning
    PMI = "pmi"                                   # ISM / S&P PMI surveys

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


# Which canonical scorecard categories a capability can feed. Used to build the
# per-economy coverage matrix without the orchestrator hard-coding vendor names.
CAPABILITY_CATEGORIES: Dict[Capability, List[str]] = {
    Capability.OBSERVATIONS: ["growth", "jobs", "inflation"],
    Capability.CONSENSUS_FORECAST: ["growth", "jobs", "inflation"],
    Capability.COT_POSITIONING: ["cot"],
    Capability.RETAIL_SENTIMENT: ["sentiment"],
    Capability.PMI: ["growth"],
}


@dataclass(frozen=True)
class ProviderInfo:
    """Immutable snapshot of one registered provider for diagnostics / UI."""

    key: str
    name: str
    capabilities: frozenset
    configured: bool
    is_live: bool
    health: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "capabilities": sorted(str(c) for c in self.capabilities),
            "configured": self.configured,
            "is_live": self.is_live,
            "health": self.health,
        }


class MacroProviderRegistry:
    """Process-wide registry of macro providers. Class-level, like the rest of
    the macro layer — one set of providers per process."""

    _FACTORIES: Dict[str, Callable[[], Any]] = {}

    # ------------------------------------------------------------------
    @classmethod
    def register(cls, key: str, factory: Callable[[], Any]) -> None:
        cls._FACTORIES[str(key).strip().lower()] = factory

    @classmethod
    def keys(cls) -> List[str]:
        return sorted(cls._FACTORIES)

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        factory = cls._FACTORIES.get(str(key).strip().lower())
        if factory is None:
            return None
        try:
            return factory()
        except Exception:  # pragma: no cover - defensive
            return None

    @classmethod
    def capabilities_of(cls, key: str) -> frozenset:
        prov = cls.get(key)
        return _capabilities(prov)

    @classmethod
    def providers_for(cls, cap: Capability) -> List[str]:
        """Registered provider keys that declare ``cap`` (configured or not)."""
        out = []
        for k in cls.keys():
            if cap in cls.capabilities_of(k):
                out.append(k)
        return out

    @classmethod
    def discover(cls) -> List[ProviderInfo]:
        infos: List[ProviderInfo] = []
        for k in cls.keys():
            prov = cls.get(k)
            if prov is None:
                infos.append(ProviderInfo(k, k, frozenset(), False, False,
                                          {"error": "provider failed to construct"}))
                continue
            infos.append(ProviderInfo(
                key=k,
                name=getattr(prov, "name", k),
                capabilities=_capabilities(prov),
                configured=bool(getattr(prov, "configured", False)),
                is_live=bool(getattr(prov, "is_live", False)),
                health=_safe_status(prov),
            ))
        return infos

    @classmethod
    def health(cls) -> Dict[str, Any]:
        infos = cls.discover()
        return {
            "providers": [i.to_dict() for i in infos],
            "configured_count": sum(1 for i in infos if i.configured),
            "live_count": sum(1 for i in infos if i.is_live and i.configured),
        }

    # test helper -------------------------------------------------------
    @classmethod
    def _reset_for_tests(cls) -> None:  # pragma: no cover - test-only
        cls._FACTORIES = {}
        _register_builtin_providers()


# --- helpers -----------------------------------------------------------

def _capabilities(prov: Any) -> frozenset:
    caps = getattr(prov, "CAPABILITIES", None) if prov is not None else None
    if not caps:
        return frozenset()
    try:
        return frozenset(caps)
    except TypeError:  # pragma: no cover - defensive
        return frozenset()


def _safe_status(prov: Any) -> Dict[str, Any]:
    fn = getattr(prov, "status", None)
    if not callable(fn):
        return {}
    try:
        st = fn()
        return st if isinstance(st, dict) else {}
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": type(exc).__name__}


# --- built-in registration ------------------------------------------
# Imports are lazy inside the factories so importing this module never drags in
# the whole provider stack (and never touches the network).

def _fred_factory():
    from api.providers.fred_provider import FredMacroProvider
    return FredMacroProvider()


def _cftc_factory():
    from api.providers.cftc_provider import CftcCotProvider
    return CftcCotProvider()


def _forecast_factory():
    from api.providers.forecast_provider import get_forecast_provider
    return get_forecast_provider()


def _sentiment_factory():
    from api.providers.sentiment_provider import get_sentiment_provider
    return get_sentiment_provider()


def _register_builtin_providers() -> None:
    MacroProviderRegistry.register("fred", _fred_factory)
    MacroProviderRegistry.register("cftc", _cftc_factory)
    MacroProviderRegistry.register("forecast", _forecast_factory)
    MacroProviderRegistry.register("sentiment", _sentiment_factory)


_register_builtin_providers()


# --- config helpers (single source of truth for the env knobs) --------

def cot_provider_key() -> str:
    return (os.getenv("MACRO_COT_PROVIDER") or "none").strip().lower()


def forecast_provider_key() -> str:
    return (os.getenv("MACRO_FORECAST_PROVIDER") or "none").strip().lower()


def sentiment_provider_key() -> str:
    return (os.getenv("MACRO_SENTIMENT_PROVIDER") or "none").strip().lower()
