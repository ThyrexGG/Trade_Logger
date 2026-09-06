# -*- coding: utf-8 -*-
"""
Economic-calendar provider (Stage 18G).

FRED gives *released historical* observations with revisions. It has no forward
schedule, no consensus forecast, and no impact rating. A calendar provider fills
that gap — scheduled events with a real time, currency, impact, forecast,
previous, and the actual once it prints.

Two sources, chosen by `MACRO_CALENDAR_PROVIDER`:

  * ``forexfactory`` (default) — the public ForexFactory weekly JSON feed
    (`nfs.faireconomy.media`). Keyless. Rate-limited hard (HTTP 429), so the
    result is cached for an hour and the last good week is persisted to the
    artifact store so a fresh process still has a calendar.
  * ``fmp`` — Financial Modeling Prep `/api/v3/economic_calendar`. Needs
    `FMP_API_KEY`. Reliable, carries an explicit impact + estimate.
  * ``none`` — disable; the calendar view falls back to FRED observations only.

Used only for `get_events()` (the calendar view). The scoring engines still run
on FRED's revision-aware observation registry. `provider` / `provenance` on
every row makes the source explicit.

Read-only. No import of / path to execution_pipeline, broker_adapter,
risk_gateway. Never raises.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

_SUPPORTED_CCY = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY"}

_IMPACT = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW", "HOLIDAY": "HOLIDAY",
           "3": "HIGH", "2": "MEDIUM", "1": "LOW"}

# ForexFactory currency tag for a non-country-specific note (BRICS summit, G20…)
_GLOBAL_TAGS = {"ALL", "", "WORLD", "GLOBAL"}

_INDICATOR_HINTS = [
    ("NON-FARM", "NFP"), ("NONFARM", "NFP"), ("PAYROLL", "NFP"),
    ("EMPLOYMENT CHANGE", "NFP"),
    ("CORE CPI", "CORE_CPI"), ("CPI", "CPI"), ("INFLATION RATE", "CPI"),
    ("CORE PCE", "CORE_PCE"), ("PCE", "PCE"),
    ("GDP", "GDP"), ("UNEMPLOYMENT RATE", "UNEMPLOYMENT"),
    ("JOBLESS CLAIMS", "JOBLESS_CLAIMS"), ("INITIAL CLAIMS", "JOBLESS_CLAIMS"),
    ("RETAIL SALES", "RETAIL_SALES"),
    ("INTEREST RATE", "INTEREST_RATE"), ("RATE DECISION", "INTEREST_RATE"),
    ("RATE STATEMENT", "INTEREST_RATE"), ("FOMC", "INTEREST_RATE"),
    ("FEDERAL FUNDS", "INTEREST_RATE"), ("REFINANCING RATE", "INTEREST_RATE"),
    ("POLICY RATE", "INTEREST_RATE"), ("BANK RATE", "INTEREST_RATE"),
    ("CASH RATE", "INTEREST_RATE"), ("OFFICIAL CASH RATE", "INTEREST_RATE"),
    ("MONETARY POLICY", "INTEREST_RATE"),
    ("PMI", "PMI"), ("ISM", "PMI"),
    ("CONSUMER CONFIDENCE", "CONSUMER_CONF"), ("CONSUMER SENTIMENT", "CONSUMER_CONF"),
]

_CATEGORY = {
    "NFP": "LABOR", "UNEMPLOYMENT": "LABOR", "JOBLESS_CLAIMS": "LABOR",
    "CPI": "INFLATION", "CORE_CPI": "INFLATION", "PCE": "INFLATION", "CORE_PCE": "INFLATION",
    "GDP": "GROWTH", "RETAIL_SALES": "GROWTH", "CONSUMER_CONF": "GROWTH", "PMI": "GROWTH",
    "INTEREST_RATE": "MONETARY_POLICY",
}


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def calendar_provider_key() -> str:
    # ForexFactory by default. FMP's economic-calendar endpoint moved behind a
    # paid plan (Aug 2025), so an FMP key alone does NOT switch to it — set
    # MACRO_CALENDAR_PROVIDER=fmp explicitly if you have a paid FMP plan.
    return (os.getenv("MACRO_CALENDAR_PROVIDER") or "forexfactory").strip().lower()


def calendar_enabled() -> bool:
    """Whether the calendar layer should do real work. Off when disabled by
    config, and off under pytest (no live network in the suite) unless a test
    explicitly opts in with MACRO_CALENDAR_ENABLED=1."""
    if calendar_provider_key() == "none":
        return False
    if os.getenv("PYTEST_CURRENT_TEST") and (os.getenv("MACRO_CALENDAR_ENABLED") or "") != "1":
        return False
    return True


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.upper() in ("N/A", "NA", "-", "--", "TENTATIVE", "NONE"):
        return None
    neg = s.startswith("-")
    s = s.lstrip("+-").replace(",", "").replace("%", "").strip()
    mult = 1.0
    if s and s[-1] in "KkMmBbTt":
        mult = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}[s[-1].lower()]
        s = s[:-1]
    try:
        return (-1 if neg else 1) * float(s) * mult
    except ValueError:
        return None


def _indicator_of(title: str) -> Optional[str]:
    t = (title or "").upper()
    for needle, ind in _INDICATOR_HINTS:
        if needle in t:
            return ind
    return None


def _iso(raw: Any) -> Optional[str]:
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00").replace(" ", "T", 1))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def _kind_of(title: str, impact: str) -> str:
    """A row's flavour, for display: holiday | speech | release."""
    if impact.upper() == "HOLIDAY":
        return "holiday"
    t = title.upper()
    if "SPEAK" in t or "SPEECH" in t or "TESTIMONY" in t or "PRESS CONFERENCE" in t:
        return "speech"
    if "HOLIDAY" in t:
        return "holiday"
    return "release"


def _event(*, source: str, provider: str, ccy: str, title: str, when: str,
           impact: str, actual: Any, forecast: Any, previous: Any,
           url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    ccy_raw = (ccy or "").strip().upper()
    when_iso = _iso(when)
    if not title or not when_iso:
        return None
    is_global = ccy_raw in _GLOBAL_TAGS
    if not is_global and ccy_raw not in _SUPPORTED_CCY:
        return None
    currency = None if is_global else ccy_raw
    country = "ALL" if is_global else ccy_raw

    imp = _IMPACT.get(str(impact or "").strip().upper(), "LOW")
    kind = _kind_of(title, imp)
    indicator = None if kind != "release" else _indicator_of(title)
    act = _num(actual)
    return {
        "event_id": f"{provider}:{country}:{title}:{when_iso[:16]}",
        "timestamp": when_iso,
        "country": country,
        "currency": currency,
        "event": title.strip(),
        "indicator": indicator,
        "category": ("HOLIDAY" if kind == "holiday" else "SPEECH" if kind == "speech"
                     else _CATEGORY.get(indicator or "")),
        "kind": kind,
        "impact": imp,
        "actual": act,
        "forecast": _num(forecast),
        "previous": _num(previous),
        "revised_previous": None,
        "unit": None,
        "source": source,
        "provider": provider,
        "status": "RELEASED" if act is not None else ("NOTE" if kind != "release" else "SCHEDULED"),
        "release_timestamp": when_iso,
        "provenance": "live",
        "metadata": {k: v for k, v in (("url", url),) if v},
    }


# --------------------------------------------------------------------------
# base
# --------------------------------------------------------------------------
class _BaseCalendarProvider:
    is_live = True
    KEY = "calendar"
    name = "Economic calendar"
    _artifact_key = "macro_calendar"

    try:
        from api.providers.registry import Capability as _Cap
        # RELEASE_CALENDAR only — the forecast values ride on the calendar rows
        # themselves; this provider does not implement the consensus-merge
        # interface that CONSENSUS_FORECAST providers use.
        CAPABILITIES = frozenset({_Cap.RELEASE_CALENDAR})
        del _Cap
    except Exception:  # pragma: no cover - defensive
        CAPABILITIES = frozenset()

    _HISTORY_DAYS = 75    # rolling window kept in the persisted snapshot
    _HORIZON_DAYS = 30

    def __init__(self) -> None:
        self._ttl = float(_cfg_int("MACRO_CALENDAR_TTL_SEC", 3600))
        self._timeout = float(_cfg_int("MACRO_CALENDAR_TIMEOUT_SEC", 12))
        self._backoff = float(_cfg_int("MACRO_CALENDAR_BACKOFF_SEC", 900))
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = {
            "fetched_at": 0.0, "wall_fetched_at": None, "events": [],
            "last_error": None, "retry_not_before": 0.0, "fetch_errors": {},
            "loaded_from": None,
        }

    # subclass contract ---------------------------------------------------
    @property
    def configured(self) -> bool:
        raise NotImplementedError

    def _fetch_raw(self) -> tuple:
        """Return (events: list[dict], errors: dict). Never raises out."""
        raise NotImplementedError

    # shared machinery --------------------------------------------------
    def _load_snapshot(self) -> None:
        st = self._state
        if st["events"] or st["wall_fetched_at"]:
            return
        try:
            import historical_data_store as store
            art = store.load_artifact(self._artifact_key)
            payload = (art or {}).get("payload") or {}
            evs = payload.get("events")
            if isinstance(evs, list) and evs:
                st["events"] = evs
                st["wall_fetched_at"] = payload.get("fetched_at")
                st["loaded_from"] = "snapshot"
        except Exception:
            pass

    def _save_snapshot(self) -> None:
        try:
            import historical_data_store as store
            store.save_artifact(self._artifact_key, "macro_calendar",
                                {"events": self._state["events"],
                                 "fetched_at": self._state["wall_fetched_at"],
                                 "source": self.name})
        except Exception:
            pass

    def _refresh(self) -> None:
        with self._lock:
            self._load_snapshot()
            now_m = time.monotonic()
            st = self._state
            fresh = st["fetched_at"] > 0 and now_m - st["fetched_at"] < self._ttl
            if fresh or now_m < st["retry_not_before"]:
                return
            try:
                events, errors = self._fetch_raw()
            except Exception as exc:  # pragma: no cover - defensive
                events, errors = [], {"fetch": type(exc).__name__}

            if not events:
                st["last_error"] = "calendar source returned no events (rate-limited / unreachable)"
                st["fetch_errors"] = errors
                st["retry_not_before"] = now_m + self._backoff
                return

            # Accumulate: the ForexFactory feed is current-week only, but each
            # refresh fills in `actual` for events that have since released.
            # Merge the fresh rows over whatever is stored (fresh wins — it has
            # the newest actuals), then prune to a rolling window so history
            # builds up week over week.
            best: Dict[str, Dict[str, Any]] = {ev["event_id"]: ev for ev in st["events"]}
            for ev in events:
                best[ev["event_id"]] = ev
            cutoff = (datetime.now(timezone.utc) - timedelta(days=self._HISTORY_DAYS)).isoformat()
            horizon = (datetime.now(timezone.utc) + timedelta(days=self._HORIZON_DAYS)).isoformat()
            merged = sorted(
                (e for e in best.values() if cutoff <= e["timestamp"] <= horizon),
                key=lambda e: e["timestamp"],
            )

            st["events"] = merged
            st["fetched_at"] = now_m
            st["wall_fetched_at"] = datetime.now(timezone.utc).isoformat()
            st["loaded_from"] = "network"
            st["last_error"] = None
            st["fetch_errors"] = errors
            st["retry_not_before"] = 0.0
            self._save_snapshot()

    def get_events(self, start: date, end: date) -> List[Dict[str, Any]]:
        if not self.configured:
            return []
        try:
            self._refresh()
        except Exception:  # pragma: no cover - defensive
            with self._lock:
                self._load_snapshot()
        s, e = start.isoformat(), end.isoformat()
        with self._lock:
            return [ev for ev in self._state["events"] if s <= ev["timestamp"][:10] <= e]

    def status(self) -> Dict[str, Any]:
        with self._lock:
            st = self._state
            age = time.monotonic() - st["fetched_at"] if st["fetched_at"] else None
            n = len(st["events"])
            if not self.configured:
                state = "NOT_CONFIGURED"
            elif n > 0:
                state = "LIVE" if (age is not None and age < self._ttl) else "LIVE_STALE"
            elif st["last_error"]:
                state = "PROVIDER_UNAVAILABLE"
            else:
                state = "PENDING"
            return {
                "provider": self.name,
                "provider_state": state,
                "configured": self.configured,
                "events_cached": n,
                "scheduled_ahead": sum(1 for ev in st["events"] if ev["status"] == "SCHEDULED"),
                "loaded_from": st["loaded_from"],
                "last_refresh_utc": st["wall_fetched_at"],
                "fetch_errors": dict(st["fetch_errors"]),
                "last_error": st["last_error"],
                "hydrated_age_sec": round(age, 1) if age is not None else None,
                "cache_ttl_sec": self._ttl,
            }

    def hydrate(self) -> Dict[str, Any]:
        try:
            self._refresh()
        except Exception:  # pragma: no cover
            pass
        return self.status()

    def reset_for_tests(self) -> None:  # pragma: no cover - test-only
        with self._lock:
            self._state.update({
                "fetched_at": 0.0, "wall_fetched_at": None, "events": [],
                "last_error": None, "retry_not_before": 0.0, "fetch_errors": {},
                "loaded_from": None,
            })


# --------------------------------------------------------------------------
# ForexFactory (keyless, rate-limited)
# --------------------------------------------------------------------------
class ForexFactoryCalendarProvider(_BaseCalendarProvider):
    name = "ForexFactory"
    KEY = "forexfactory"
    _artifact_key = "macro_calendar_forexfactory"
    # only the current-week feed is still published (last/next-week were retired)
    _URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    @property
    def configured(self) -> bool:
        return calendar_provider_key() == "forexfactory"

    def _fetch_raw(self) -> tuple:
        import requests
        try:
            r = requests.get(self._URL, timeout=self._timeout,
                             headers={"User-Agent": "TradeLogger/macro-calendar"})
        except Exception as exc:  # pragma: no cover - network
            return [], {"thisweek": type(exc).__name__}
        if r.status_code != 200:
            return [], {"thisweek": f"http_{r.status_code}"}
        try:
            payload = r.json()
        except Exception:
            return [], {"thisweek": "not_json"}
        if not isinstance(payload, list):
            return [], {"thisweek": "not_a_list"}
        out = []
        for it in payload:
            if not isinstance(it, dict):
                continue
            ev = _event(source="ForexFactory", provider="forexfactory",
                        ccy=it.get("country"), title=it.get("title"),
                        when=it.get("date"), impact=it.get("impact"),
                        actual=it.get("actual"), forecast=it.get("forecast"),
                        previous=it.get("previous"), url=it.get("url"))
            if ev:
                out.append(ev)
        return out, {}


# --------------------------------------------------------------------------
# Financial Modeling Prep (API key, reliable)
# --------------------------------------------------------------------------
class FmpCalendarProvider(_BaseCalendarProvider):
    name = "Financial Modeling Prep"
    KEY = "fmp"
    _artifact_key = "macro_calendar_fmp"
    _URL = "https://financialmodelingprep.com/api/v3/economic_calendar"

    def __init__(self) -> None:
        super().__init__()
        self._api_key = (os.getenv("FMP_API_KEY") or "").strip()

    @property
    def configured(self) -> bool:
        return calendar_provider_key() == "fmp" and bool(self._api_key)

    def _fetch_raw(self) -> tuple:
        import requests
        today = datetime.now(timezone.utc).date()
        params = {
            "from": (today - timedelta(days=10)).isoformat(),
            "to": (today + timedelta(days=21)).isoformat(),
            "apikey": self._api_key,
        }
        try:
            r = requests.get(self._URL, params=params, timeout=self._timeout)
        except Exception as exc:  # pragma: no cover - network
            return [], {"fmp": type(exc).__name__}
        if r.status_code != 200:
            return [], {"fmp": f"http_{r.status_code}"}
        try:
            payload = r.json()
        except Exception:
            return [], {"fmp": "not_json"}
        if not isinstance(payload, list):
            return [], {"fmp": "not_a_list"}
        out = []
        for it in payload:
            if not isinstance(it, dict):
                continue
            ev = _event(source="Financial Modeling Prep", provider="fmp",
                        ccy=it.get("currency") or it.get("country"),
                        title=it.get("event"), when=it.get("date"),
                        impact=it.get("impact"),
                        actual=it.get("actual"),
                        forecast=it.get("estimate") if it.get("estimate") is not None else it.get("consensus"),
                        previous=it.get("previous"))
            if ev:
                out.append(ev)
        return out, {}


# --------------------------------------------------------------------------
_PROVIDERS = {
    "forexfactory": ForexFactoryCalendarProvider,
    "fmp": FmpCalendarProvider,
}
_INSTANCES: Dict[str, _BaseCalendarProvider] = {}
_INSTANCE_LOCK = threading.Lock()


def get_calendar_provider() -> _BaseCalendarProvider:
    key = calendar_provider_key()
    cls = _PROVIDERS.get(key, ForexFactoryCalendarProvider)
    with _INSTANCE_LOCK:
        inst = _INSTANCES.get(cls.__name__)
        if inst is None:
            inst = cls()
            _INSTANCES[cls.__name__] = inst
        return inst


def reset_state_for_tests() -> None:  # pragma: no cover - test-only
    with _INSTANCE_LOCK:
        for inst in _INSTANCES.values():
            inst.reset_for_tests()
        _INSTANCES.clear()
