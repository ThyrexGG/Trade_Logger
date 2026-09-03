# -*- coding: utf-8 -*-
"""
CFTC Commitments of Traders (COT) provider — Phase 66.

Source: the U.S. Commodity Futures Trading Commission public reporting API
(Socrata), Legacy Futures-Only report:

    https://publicreporting.cftc.gov/resource/6dca-aqww.json

Authoritative, official U.S. government data, free, **no API key**. It carries:

  * real institutional positioning (non-commercial long / short / net,
    commercial long / short, open interest)
  * the real ``report_date`` (the Tuesday the positions were measured)

What it does NOT carry — reported honestly, never fabricated:

  * a "forecast" for positioning — there is none; ``forecast = None``.
  * an explicit publication timestamp. The COT is published the following
    **Friday at 15:30 ET**. We therefore derive a conservative
    ``release_timestamp = report_date + 3 days @ 20:30 UTC`` (covers 15:30 ET in
    both DST states). Occasional US-holiday weeks push publication to the
    following Monday — documented imprecision, always erring *later* so a report
    is never shown before it was public.

The provider normalizes each market into a canonical
``macro_intelligence_engine.MacroReleaseRecord`` with
``metric = "COT_NET_POSITIONING"`` so the existing SENTIMENT_POSITIONING factor
group consumes it with **no engine change**.

Config (env, never committed):
    MACRO_COT_PROVIDER=cftc
    CFTC_TIMEOUT_SEC        (default 12)
    CFTC_CACHE_TTL_SEC      (default 21600 = 6h — COT is weekly)
    CFTC_HYDRATE_BUDGET_SEC (default 20)
    CFTC_RETRY_BACKOFF_SEC  (default 300)
    CFTC_HISTORY_WEEKS      (default 12 — how many recent reports to keep per market)

No import of / path to execution_pipeline, broker_adapter, risk_gateway.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from api.providers.registry import Capability

_CFTC_BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# canonical country/asset  ->  (CFTC legacy contract market code, human market label)
# One COT series per economy. GOLD carries the USD/gold positioning view (the
# same convention the seed dataset uses); the FX contracts carry their own
# currency. USD-index is deliberately omitted to avoid colliding with GOLD on the
# (metric, country, period) identity.
_MARKETS: Dict[str, Dict[str, str]] = {
    "USD": {"code": "088691", "label": "GOLD - COMMODITY EXCHANGE INC.", "asset": "XAUUSD"},
    "EUR": {"code": "099741", "label": "EURO FX - CHICAGO MERCANTILE EXCHANGE", "asset": "EURUSD"},
    "GBP": {"code": "096742", "label": "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE", "asset": "GBPUSD"},
    "JPY": {"code": "097741", "label": "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE", "asset": "USDJPY"},
    "CAD": {"code": "090741", "label": "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "asset": "USDCAD"},
    "CHF": {"code": "092741", "label": "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE", "asset": "USDCHF"},
    "AUD": {"code": "232741", "label": "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "asset": "AUDUSD"},
    "NZD": {"code": "112741", "label": "NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE", "asset": "NZDUSD"},
}
_CODE_TO_COUNTRY = {m["code"]: ccy for ccy, m in _MARKETS.items()}
_COT_METRIC = "COT_NET_POSITIONING"


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


# --- module-level hydration state (shared across provider instances) -------
_LOCK = threading.RLock()
_STATE: Dict[str, Any] = {
    "hydrated_at": 0.0,
    "last_success_wall": None,     # ISO str of last successful hydrate
    "last_failure_wall": None,     # ISO str of last failed hydrate
    "last_error": None,
    "registered": 0,
    "coverage": [],               # [country,...] with a fresh COT record
    "latency_ms": None,
    "observations": [],           # cached list[COTObservation dicts] (last good)
    "retry_not_before": 0.0,
}


@dataclass
class COTObservation:
    """Canonical COT snapshot for one market / report date."""

    provider: str
    source: str
    report_date: str              # observation date (Tuesday), ISO YYYY-MM-DD
    release_timestamp: str        # derived public-availability time, UTC ISO
    market: str
    asset: str
    country: str
    non_commercial_long: Optional[int]
    non_commercial_short: Optional[int]
    non_commercial_net: Optional[int]
    commercial_long: Optional[int]
    commercial_short: Optional[int]
    open_interest: Optional[int]
    retrieved_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _http_get(params: Dict[str, str], timeout: float):
    """Single Socrata GET. Monkeypatched in tests."""
    import requests

    return requests.get(_CFTC_BASE, params=params, timeout=timeout)


def _int(v: Any) -> Optional[int]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s.lower() in ("n/a", "na", "-", "."):
        return None
    try:
        return int(round(float(s)))
    except (TypeError, ValueError):
        return None


def _report_date(raw: Any) -> Optional[str]:
    """CFTC ``report_date_as_yyyy_mm_dd`` -> 'YYYY-MM-DD' (drops any time part)."""
    if not raw:
        return None
    s = str(raw).strip()
    head = s.split("T", 1)[0]
    try:
        date.fromisoformat(head)
        return head
    except ValueError:
        return None


def _release_ts(report_date_iso: str) -> str:
    """Conservative public-availability time: the Friday after the Tuesday
    report, 20:30 UTC (>= 15:30 ET in either DST state)."""
    d = date.fromisoformat(report_date_iso)
    friday = d + timedelta(days=3)
    return f"{friday.isoformat()}T20:30:00Z"


class CftcCotProvider:
    KEY = "cftc"
    CAPABILITIES = frozenset({Capability.COT_POSITIONING, Capability.HISTORICAL})
    name = "CFTC Commitments of Traders"
    is_live = True

    def __init__(self) -> None:
        self._timeout = float(_cfg_int("CFTC_TIMEOUT_SEC", 12))
        self._ttl = float(_cfg_int("CFTC_CACHE_TTL_SEC", 21600))
        self._budget = float(_cfg_int("CFTC_HYDRATE_BUDGET_SEC", 20))
        self._backoff = float(_cfg_int("CFTC_RETRY_BACKOFF_SEC", 300))
        self._weeks = max(2, _cfg_int("CFTC_HISTORY_WEEKS", 12))

    # --- provider contract ------------------------------------------------
    @property
    def configured(self) -> bool:
        # Public API, no key required — "configured" == "selected".
        return (os.getenv("MACRO_COT_PROVIDER") or "none").strip().lower() == "cftc"

    def status(self) -> Dict[str, Any]:
        with _LOCK:
            fresh = _STATE["hydrated_at"] > 0 and (time.monotonic() - _STATE["hydrated_at"]) < self._ttl
            if not self.configured:
                state = "NOT_CONFIGURED"
            elif _STATE["hydrated_at"] > 0 and _STATE["registered"] > 0:
                state = "LIVE" if fresh else "LIVE_STALE"
            elif _STATE["last_error"]:
                state = "PROVIDER_UNAVAILABLE"
            else:
                state = "PENDING"
            return {
                "provider": self.name,
                "provider_state": state,
                "configured": self.configured,
                "records_registered": _STATE["registered"],
                "coverage": list(_STATE["coverage"]),
                "last_success": _STATE["last_success_wall"],
                "last_failure": _STATE["last_failure_wall"],
                "last_error": _STATE["last_error"],
                "latency_ms": _STATE["latency_ms"],
                "hydrated_age_sec": round(time.monotonic() - _STATE["hydrated_at"], 1) if _STATE["hydrated_at"] else None,
                "cache_ttl_sec": self._ttl,
                "backoff_until_sec": max(0.0, round(_STATE["retry_not_before"] - time.monotonic(), 1)) or None,
            }

    def hydrate(self) -> Dict[str, Any]:
        return self.hydrate_registry()

    def get_observations(self) -> List[Dict[str, Any]]:
        with _LOCK:
            return list(_STATE["observations"])

    def hydrate_registry(self, force: bool = False) -> Dict[str, Any]:
        """Fetch recent COT for the mapped markets and register net-non-commercial
        positioning into EconomicDataRegistry. Best-effort — a failure leaves the
        last-good COT in place and records the error."""
        with _LOCK:
            if not self.configured:
                return self.status()
            now_m = time.monotonic()
            age = now_m - _STATE["hydrated_at"]
            if not force and _STATE["hydrated_at"] > 0 and age < self._ttl:
                return self.status()
            if not force and now_m < _STATE["retry_not_before"]:
                return self.status()

            codes = [m["code"] for m in _MARKETS.values()]
            in_list = ",".join(f"'{c}'" for c in codes)
            params = {
                "$select": ",".join([
                    "cftc_contract_market_code", "market_and_exchange_names",
                    "report_date_as_yyyy_mm_dd",
                    "noncomm_positions_long_all", "noncomm_positions_short_all",
                    "comm_positions_long_all", "comm_positions_short_all",
                    "open_interest_all",
                ]),
                "$where": f"cftc_contract_market_code in({in_list})",
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": str(self._weeks * len(codes) + len(codes)),
            }

            t0 = time.perf_counter()
            try:
                r = _http_get(params, self._timeout)
            except Exception as exc:
                return self._fail(f"{type(exc).__name__}")
            _STATE["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            code = getattr(r, "status_code", 0)
            if code == 429:
                return self._fail("rate_limited_429")
            if code >= 400:
                return self._fail(f"http_{code}")
            try:
                rows = r.json()
            except ValueError:
                return self._fail("malformed_json")
            if not isinstance(rows, list) or not rows:
                return self._fail("empty_or_unexpected_payload")

            obs = self._normalize(rows)
            if not obs:
                return self._fail("no_usable_rows_after_normalization")

            self._apply_to_registry(obs)
            _STATE["observations"] = [o.to_dict() for o in obs]
            _STATE["registered"] = len(obs)
            _STATE["coverage"] = sorted({o.country for o in obs})
            _STATE["hydrated_at"] = time.monotonic()
            _STATE["retry_not_before"] = 0.0
            _STATE["last_error"] = None
            _STATE["last_success_wall"] = datetime.now(timezone.utc).isoformat()
            return self.status()

    # --- internals ------------------------------------------------------
    def _fail(self, reason: str) -> Dict[str, Any]:
        _STATE["last_error"] = reason
        _STATE["last_failure_wall"] = datetime.now(timezone.utc).isoformat()
        _STATE["retry_not_before"] = time.monotonic() + self._backoff
        return self.status()

    def _normalize(self, rows: List[Dict[str, Any]]) -> List[COTObservation]:
        now_iso = datetime.now(timezone.utc).isoformat()
        by_code: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            c = str(row.get("cftc_contract_market_code") or "").strip()
            if c in _CODE_TO_COUNTRY:
                by_code.setdefault(c, []).append(row)

        out: List[COTObservation] = []
        for c, group in by_code.items():
            ccy = _CODE_TO_COUNTRY[c]
            mkt = _MARKETS[ccy]
            # newest-first from the API; keep the most recent N distinct dates
            seen_dates: set = set()
            for row in group:
                rd = _report_date(row.get("report_date_as_yyyy_mm_dd"))
                if not rd or rd in seen_dates:
                    continue
                seen_dates.add(rd)
                nc_long = _int(row.get("noncomm_positions_long_all"))
                nc_short = _int(row.get("noncomm_positions_short_all"))
                net = (nc_long - nc_short) if (nc_long is not None and nc_short is not None) else None
                if net is None:
                    continue
                out.append(COTObservation(
                    provider="cftc",
                    source=f"CFTC:{c}",
                    report_date=rd,
                    release_timestamp=_release_ts(rd),
                    market=str(row.get("market_and_exchange_names") or mkt["label"]),
                    asset=mkt["asset"],
                    country=ccy,
                    non_commercial_long=nc_long,
                    non_commercial_short=nc_short,
                    non_commercial_net=net,
                    commercial_long=_int(row.get("comm_positions_long_all")),
                    commercial_short=_int(row.get("comm_positions_short_all")),
                    open_interest=_int(row.get("open_interest_all")),
                    retrieved_at=now_iso,
                ))
                if len(seen_dates) >= self._weeks:
                    break
        return out

    def _apply_to_registry(self, obs: List[COTObservation]) -> None:
        from macro_intelligence_engine import EconomicDataRegistry, MacroReleaseRecord

        EconomicDataRegistry.seed_canonical_registry()
        covered = {o.country for o in obs}
        # Replace any existing COT rows (seeded prior or previous hydrate) for the
        # countries we're refreshing — never leave a stale/model-prior COT beside
        # a live one.
        EconomicDataRegistry._RELEASES = [
            r for r in EconomicDataRegistry._RELEASES
            if not (r.metric == _COT_METRIC and r.country in covered)
        ]
        now_iso = datetime.now(timezone.utc).isoformat()
        for o in sorted(obs, key=lambda x: (x.country, x.report_date)):
            EconomicDataRegistry.register_release(MacroReleaseRecord(
                metric=_COT_METRIC,
                country=o.country,
                period=o.report_date,
                release_timestamp=o.release_timestamp,
                forecast=None,                       # no consensus for positioning
                actual=float(o.non_commercial_net),
                previous=None,
                unit="contracts",
                source=o.source,
                source_timestamp=now_iso,
                revision_status="INITIAL",
                freshness_state="FRESH",
            ))


def reset_state_for_tests() -> None:  # pragma: no cover - test-only
    with _LOCK:
        _STATE.update({
            "hydrated_at": 0.0, "last_success_wall": None, "last_failure_wall": None,
            "last_error": None, "registered": 0, "coverage": [], "latency_ms": None,
            "observations": [], "retry_not_before": 0.0,
        })
