# -*- coding: utf-8 -*-
"""
Macro / economic-calendar data provider abstraction (Stage 18A).

TradeLogger's own implementation — NOT a clone of any external product.

A `MacroDataProvider` yields normalized `EconomicEvent` dicts. The application
never talks to a raw provider directly; it goes through `get_provider()` and the
normalizer, so a real external feed can be connected later by adding one
provider class and setting `MACRO_DATA_PROVIDER` — no other code changes.

DATA INTEGRITY: missing fields stay `None`. Nothing is fabricated. Every event
and every downstream response carries `provenance` so demo / seeded data is
never presented as real market information.

Providers available now:
  - "seed_demo"  (default) — the existing `EconomicDataRegistry` seeded dataset
                 + `StandardMacroCalendarProvider` upcoming schedule. Realistic
                 *shape*, but NOT live market data: `provider_is_live = False`,
                 every event `provenance = "seed_demo"`.
  - "none"       — returns nothing; every macro response is `available = False`.
  - real feeds   — add a class + register it; `provider_is_live = True` and
                 events `provenance = "live"`.
"""
from __future__ import annotations

import math
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Protocol

_IMPACT_MAP = {
    "LOW": "LOW", "MINIMAL": "LOW", "NEGLIGIBLE": "LOW",
    "MEDIUM": "MEDIUM", "MODERATE": "MEDIUM", "CAUTION": "MEDIUM", "INDIRECT": "MEDIUM",
    "HIGH": "HIGH", "HIGH IMPACT": "HIGH", "HIGH_IMPACT": "HIGH",
    "EXTREME": "CRITICAL", "CRITICAL": "CRITICAL",
}
IMPACT_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

_CCY_BY_COUNTRY = {
    "UNITED STATES": "USD", "US": "USD", "USA": "USD",
    "EURO AREA": "EUR", "EUROZONE": "EUR", "EUROPEAN UNION": "EUR", "EU": "EUR", "GERMANY": "EUR",
    "UNITED KINGDOM": "GBP", "UK": "GBP", "GREAT BRITAIN": "GBP",
    "JAPAN": "JPY",
    "SWITZERLAND": "CHF",
    "CANADA": "CAD",
    "AUSTRALIA": "AUD",
    "NEW ZEALAND": "NZD",
}
SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]


def _num(value: Any) -> Optional[float]:
    """Parse a possibly-formatted number ("+0.3%", "225K", "3.2") -> float, or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    s = str(value).strip()
    if not s or s.upper() in ("N/A", "NA", "-", "--", "NONE", "TBD"):
        return None
    mult = 1.0
    su = s.upper().replace(",", "").replace("%", "").replace("+", "").strip()
    if su.endswith("K"):
        mult, su = 1_000.0, su[:-1]
    elif su.endswith("M"):
        mult, su = 1_000_000.0, su[:-1]
    elif su.endswith("B"):
        mult, su = 1_000_000_000.0, su[:-1]
    try:
        n = float(su) * mult
        return n if math.isfinite(n) else None
    except ValueError:
        return None


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    s = str(value).strip()
    return s or None


def normalize_event(raw: Dict[str, Any], *, provider: str, is_live: bool) -> Optional[Dict[str, Any]]:
    """
    Normalize one raw provider record into the canonical `EconomicEvent` shape.
    Returns None if the record is too malformed to be trusted (no name / no time).
    Missing individual fields are preserved as None — never guessed.
    """
    if not isinstance(raw, dict):
        return None

    name = raw.get("event_name") or raw.get("name") or raw.get("indicator") or raw.get("metric")
    when = raw.get("scheduled_time") or raw.get("release_timestamp") or raw.get("timestamp") or raw.get("utc_time")
    if not name or not when:
        return None

    country_raw = str(raw.get("country") or "").strip()
    currency = str(raw.get("currency") or "").strip().upper()
    if not currency:
        currency = _CCY_BY_COUNTRY.get(country_raw.upper(), "")

    impact_raw = str(raw.get("impact_level") or raw.get("impact") or raw.get("importance") or "").strip().upper()
    impact = _IMPACT_MAP.get(impact_raw, "MEDIUM" if impact_raw else "LOW")

    actual = _num(raw.get("actual"))
    forecast = _num(raw.get("forecast") if raw.get("forecast") is not None else raw.get("consensus"))
    previous = _num(raw.get("previous"))
    revised_prev = _num(raw.get("revised_previous") if raw.get("revised_previous") is not None else raw.get("initial_actual"))

    status = str(raw.get("status") or ("RELEASED" if actual is not None else "SCHEDULED")).upper()

    return {
        "event_id": str(raw.get("event_id") or raw.get("id") or f"{provider}:{name}:{when}"),
        "timestamp": _iso(when),
        "country": country_raw or None,
        "currency": currency or None,
        "event": str(name),
        "indicator": str(raw.get("metric") or raw.get("indicator") or "").upper() or None,
        "category": str(raw.get("category") or raw.get("family") or "").upper() or None,
        "impact": impact,
        "actual": actual,
        "forecast": forecast,
        "previous": previous,
        "revised_previous": revised_prev,
        "unit": str(raw.get("unit") or "").strip() or None,
        "source": str(raw.get("source") or raw.get("source_name") or "").strip() or None,
        "provider": provider,
        "status": status,
        "release_timestamp": _iso(raw.get("release_timestamp") or raw.get("source_timestamp") or raw.get("retrieval_timestamp")),
        "provenance": "live" if is_live else "seed_demo",
        "metadata": {
            k: raw.get(k)
            for k in ("relevance_tier", "potential_effect", "proximity_bucket", "revision_status", "period")
            if raw.get(k) is not None
        },
    }


class MacroDataProvider(Protocol):
    name: str
    is_live: bool

    def get_events(self, start: date, end: date) -> List[Dict[str, Any]]:
        """Return normalized EconomicEvent dicts with timestamp in [start, end]."""
        ...


class NullProvider:
    name = "none"
    is_live = False

    def get_events(self, start: date, end: date) -> List[Dict[str, Any]]:
        return []


class SeedDemoProvider:
    """
    Wraps the existing seeded datasets. Realistic shape, NOT live data.
      - historical releases (with actuals) -> `macro_intelligence_engine.EconomicDataRegistry`
      - upcoming schedule (forecast/previous, actual=None) -> `StandardMacroCalendarProvider`
    """
    name = "seed_demo"
    is_live = False

    def get_events(self, start: date, end: date) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()

        # 1. released observations
        try:
            from macro_intelligence_engine import EconomicDataRegistry
            for rec in EconomicDataRegistry.get_releases_as_of(as_of=datetime.now(timezone.utc)):
                d = rec.to_dict()
                ev = normalize_event(d, provider=self.name, is_live=False)
                if ev and ev["timestamp"]:
                    day = ev["timestamp"][:10]
                    if start.isoformat() <= day <= end.isoformat() and ev["event_id"] not in seen:
                        seen.add(ev["event_id"])
                        out.append(ev)
        except Exception:
            pass

        # 2. scheduled upcoming events
        try:
            from xauusd_daily_preflight import EconomicCalendarProviderFactory
            prov = EconomicCalendarProviderFactory.get_provider()
            cur = start
            while cur <= end and (cur - start).days <= 21:
                try:
                    cal = prov.get_calendar(cur)
                    for e in (cal.get("events", []) if isinstance(cal, dict) else []):
                        ev = normalize_event(e, provider=self.name, is_live=False)
                        if ev and ev["event_id"] not in seen:
                            seen.add(ev["event_id"])
                            out.append(ev)
                except Exception:
                    pass
                cur += timedelta(days=1)
        except Exception:
            pass

        out.sort(key=lambda e: e["timestamp"] or "")
        return out


_PROVIDERS = {
    "seed_demo": SeedDemoProvider,
    "none": NullProvider,
}


def get_provider() -> MacroDataProvider:
    key = (os.getenv("MACRO_DATA_PROVIDER") or "seed_demo").strip().lower()
    return _PROVIDERS.get(key, SeedDemoProvider)()
