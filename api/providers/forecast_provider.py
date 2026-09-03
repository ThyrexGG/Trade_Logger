# -*- coding: utf-8 -*-
"""
Consensus-forecast provider contract (Phase 66).

Phase 65 established that FRED / ALFRED carries real *actuals* but **no consensus
forecast**. Without a forecast, ``surprise = actual - forecast`` is UNAVAILABLE
for every FRED-sourced indicator and the surprise dimension of the scorecard
goes dark.

This module defines the canonical forecast representation and the provider
contract for supplying one. It does **not** ship a live forecast source:

  * There is no free, authoritative, redistributable consensus-forecast feed.
    The well-known ones (Trading Economics, Investing.com, econoday) are paid
    and/or their terms forbid programmatic redistribution.
  * So the default is ``NullForecastProvider`` — it returns nothing, and the
    macro layer keeps ``forecast = None`` / surprise ``UNAVAILABLE``. That is a
    LICENSING / ACCESS limitation, documented as such — not a bug, and never
    papered over with a fabricated number.

To connect a real source later: implement the ``ForecastProvider`` shape in a
new module, register it in ``api/providers/registry.py``, and set
``MACRO_FORECAST_PROVIDER=<key>``. Nothing else changes — the evidence
orchestrator merges forecasts onto releases by canonical identity.

No import of / path to execution_pipeline, broker_adapter, risk_gateway.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from api.providers.registry import Capability, forecast_provider_key


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EconomicForecast:
    """Canonical consensus-forecast record for one economic release.

    Only fields the provider actually supplies are populated; everything else
    stays ``None``. ``(indicator, country, period)`` is the release identity used
    to merge this onto the matching ``MacroReleaseRecord`` — never a name match.
    """

    provider: str                       # registry key, e.g. "forecast"
    source: str                         # human source label
    indicator: str                     # CANONICAL metric (e.g. "CPI"), not a display name
    country: str                       # "USD" / "EUR" / ...
    period: str                        # observation period — "2026-08", "2026-Q2"
    forecast: Optional[float]
    previous: Optional[float] = None
    release_timestamp: Optional[str] = None      # expected/actual release time (UTC ISO)
    forecast_timestamp: Optional[str] = None     # VINTAGE — when THIS forecast became known (UTC ISO)
    retrieved_at: str = field(default_factory=_now_iso)
    unit: Optional[str] = None
    currency: Optional[str] = None
    n_estimates: Optional[int] = None
    consensus_low: Optional[float] = None
    consensus_high: Optional[float] = None
    event_id: Optional[str] = None               # provider's own id, secondary identifier

    def identity(self) -> tuple:
        return (self.country, self.indicator, self.period)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@runtime_checkable
class ForecastProvider(Protocol):
    KEY: str
    CAPABILITIES: frozenset
    name: str
    is_live: bool

    @property
    def configured(self) -> bool: ...

    def get_forecasts(self, *, as_of: Optional[datetime] = None) -> List[EconomicForecast]: ...

    def status(self) -> Dict[str, Any]: ...

    def hydrate(self) -> Dict[str, Any]: ...


class NullForecastProvider:
    """No consensus-forecast source configured. Returns nothing — deliberately.

    This is the honest default: surprise stays UNAVAILABLE rather than being
    fabricated from a model prior or a stale figure.
    """

    KEY = "none"
    CAPABILITIES = frozenset({Capability.CONSENSUS_FORECAST})
    name = "No forecast provider"
    is_live = False

    @property
    def configured(self) -> bool:
        return False

    def get_forecasts(self, *, as_of: Optional[datetime] = None) -> List[EconomicForecast]:
        return []

    def status(self) -> Dict[str, Any]:
        return {
            "provider": "none",
            "provider_state": "NOT_CONFIGURED",
            "configured": False,
            "reason": "No consensus-forecast source is configured. surprise = actual - "
                      "forecast is UNAVAILABLE; forecasts are never fabricated. This is a "
                      "licensing/access limitation — free authoritative consensus feeds do "
                      "not exist.",
            "forecasts": 0,
        }

    def hydrate(self) -> Dict[str, Any]:
        return self.status()


_FORECAST_PROVIDERS = {
    "none": NullForecastProvider,
}


def get_forecast_provider() -> "ForecastProvider":
    key = forecast_provider_key()
    factory = _FORECAST_PROVIDERS.get(key, NullForecastProvider)
    return factory()


def forecast_lookahead_ok(fc: EconomicForecast, as_of: Optional[datetime]) -> bool:
    """A forecast may enter a historical (as_of) context only if its VINTAGE was
    already known at ``as_of``. A forecast with no vintage is only ever valid in
    a live ("now", as_of is None) context — never back-dated.
    """
    if as_of is None:
        return True
    if not fc.forecast_timestamp:
        return False
    cutoff = as_of.isoformat().replace("+00:00", "Z")
    return str(fc.forecast_timestamp).replace("+00:00", "Z") <= cutoff


# keep os import meaningful for the "no hardcoded secret" guard style used elsewhere
_ = os
