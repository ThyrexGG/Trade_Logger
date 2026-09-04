# -*- coding: utf-8 -*-
"""
FRED (Federal Reserve Economic Data) macro provider — Phase 65.

FRED / ALFRED is an authoritative, free source published by the Federal Reserve
Bank of St. Louis. It carries:

  * real observation values (`actual`)
  * the prior observation (`previous`)
  * vintage / revision history via ALFRED `realtime_start` — so the **release
    timestamp** (when a value first became public) is real, and revisions are
    preserved (`initial_actual`, `revision_status`, `revision_timestamp`)
  * cross-country coverage for CPI / unemployment / policy rate / GDP via
    OECD-sourced series

What FRED does **not** provide — reported honestly, never fabricated:

  * **forecast / consensus** — FRED has none. `forecast = None`; the surprise
    engine returns `UNAVAILABLE` for FRED-sourced indicators. Category scoring
    falls back to absolute-level + trend logic already in the engine.
  * **CFTC COT positioning** — not on FRED -> COT stays INSUFFICIENT_EVIDENCE.
  * **ISM PMI** — proprietary, not on FRED.
  * **retail sentiment / technical** — not macro-provider data.

Config (env, never committed):
  MACRO_DATA_PROVIDER=fred
  FRED_API_KEY=<32-char key from https://fred.stlouisfed.org/docs/api/api_key.html>
  FRED_CACHE_TTL_SEC   (default 21600 = 6h — economic data updates slowly)
  FRED_TIMEOUT_SEC     (default 15)
  FRED_HISTORY_START   (default 2018-01-01 — how far back to pull observations)

No import of / path to execution_pipeline, broker_adapter, risk_gateway.
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

_FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# canonical metric -> (fred_series_id, fred_units_transform, unit_label)
#   pc1 = percent change from a year ago (YoY)
#   chg = change from previous obs
#   lin = level (as published)
_SERIES: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "USD": {
        "CPI":            ("CPIAUCSL", "pc1", "%"),
        "CORE_CPI":       ("CPILFESL", "pc1", "%"),
        "PCE":            ("PCEPI", "pc1", "%"),
        "CORE_PCE":       ("PCEPILFE", "pc1", "%"),
        "GDP":            ("A191RL1Q225SBEA", "lin", "% ann."),
        "RETAIL_SALES":   ("RSAFS", "pc1", "%"),
        "CONSUMER_CONF":  ("UMCSENT", "lin", "index"),
        "UNEMPLOYMENT":   ("UNRATE", "lin", "%"),
        "NFP":            ("PAYEMS", "chg", "k"),
        "JOBLESS_CLAIMS": ("ICSA", "lin", ""),
        "INTEREST_RATE":  ("DFEDTARU", "lin", "%"),
        "YIELD_2Y":       ("DGS2", "lin", "%"),
        "YIELD_10Y":      ("DGS10", "lin", "%"),
    },
    "EUR": {
        "CPI":           ("CP0000EZ19M086NEST", "pc1", "%"),
        "GDP":           ("CLVMNACSCAB1GQEA19", "pc1", "%"),
        "UNEMPLOYMENT":  ("LRHUTTTTEZM156S", "lin", "%"),
        "INTEREST_RATE": ("ECBDFR", "lin", "%"),
    },
    "GBP": {
        "CPI":           ("GBRCPIALLMINMEI", "pc1", "%"),
        "GDP":           ("CLVMNACSCAB1GQUK", "pc1", "%"),
        "UNEMPLOYMENT":  ("LRHUTTTTGBM156S", "lin", "%"),
        # IRSTCB01GBM156N was discontinued by FRED — 3-month interbank rate instead
        "INTEREST_RATE": ("IR3TIB01GBM156N", "lin", "%"),
    },
    "JPY": {
        "CPI":           ("JPNCPIALLMINMEI", "pc1", "%"),
        "GDP":           ("JPNRGDPEXP", "pc1", "%"),
        "UNEMPLOYMENT":  ("LRUNTTTTJPM156S", "lin", "%"),
        "INTEREST_RATE": ("IRSTCB01JPM156N", "lin", "%"),
    },
    "CAD": {
        "CPI":           ("CANCPIALLMINMEI", "pc1", "%"),
        "UNEMPLOYMENT":  ("LRUNTTTTCAM156S", "lin", "%"),
        "INTEREST_RATE": ("IRSTCB01CAM156N", "lin", "%"),
    },
    "AUD": {
        "CPI":           ("AUSCPIALLQINMEI", "pc1", "%"),
        "UNEMPLOYMENT":  ("LRUNTTTTAUM156S", "lin", "%"),
        "INTEREST_RATE": ("IR3TIB01AUM156N", "lin", "%"),
    },
    "NZD": {
        "CPI":          ("NZLCPIALLQINMEI", "pc1", "%"),
        "UNEMPLOYMENT": ("LRHUTTTTNZQ156S", "lin", "%"),
    },
    "CHF": {
        "CPI":           ("CHECPIALLMINMEI", "pc1", "%"),
        # LRHUTTTTCHM156S (monthly) and IRSTCB01CHM156N were discontinued by FRED
        "UNEMPLOYMENT":  ("LRHUTTTTCHQ156S", "lin", "%"),   # quarterly harmonised rate
        "INTEREST_RATE": ("IR3TIB01CHM156N", "lin", "%"),   # 3-month interbank rate
    },
}

_METRIC_FAMILY = {
    "CPI": "INFLATION", "CORE_CPI": "INFLATION", "PCE": "INFLATION", "CORE_PCE": "INFLATION",
    "GDP": "GROWTH", "RETAIL_SALES": "GROWTH", "CONSUMER_CONF": "GROWTH",
    "UNEMPLOYMENT": "LABOR", "NFP": "LABOR", "JOBLESS_CLAIMS": "LABOR",
    "INTEREST_RATE": "MONETARY_POLICY", "YIELD_2Y": "MONETARY_POLICY", "YIELD_10Y": "MONETARY_POLICY",
}


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


# --- module-level hydration state (shared across provider instances) -------
_LOCK = threading.RLock()
_STATE: Dict[str, Any] = {
    "hydrated_at": 0.0,          # time.monotonic() of last successful hydrate
    "last_error": None,          # str | None
    "registered": 0,             # records registered on last hydrate
    "coverage": {},              # {ccy: [metric,...]} actually loaded
    "series_errors": {},         # {series_id: reason}
    "records": [],               # cached list[MacroReleaseRecord] (last good)
    "retry_not_before": 0.0,     # backoff after a failed hydrate (monotonic)
}

# Total wall-clock budget for one hydrate pass — a broken / unreachable provider
# must degrade fast, never block a request. After a failed hydrate the provider
# backs off for FRED_RETRY_BACKOFF_SEC so subsequent requests are instant.
_FETCH_WORKERS = 8


def _http_get(params: Dict[str, str], timeout: float):
    import requests

    return requests.get(_FRED_BASE, params=params, timeout=timeout)


def _parse_num(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s in (".", "n/a", "NA", "-"):
        return None
    try:
        f = float(s)
        return f if f == f and abs(f) != float("inf") else None
    except ValueError:
        return None


def _fetch_series(series_id: str, units: str, api_key: str, timeout: float,
                  history_start: str) -> Optional[List[Dict[str, Any]]]:
    """One FRED/ALFRED call. Returns the raw observation rows, or None on any
    failure.

    First try a bounded ALFRED real-time window (first-print date + recent
    revisions). FRED rejects that with HTTP 400 in several cases:
      * ``units`` is a transform (``pc1`` / ``chg`` / ...) and
        ``realtime_start != realtime_end``;
      * the window spans more vintage dates than FRED allows (~2000) — hits
        daily series like ``DGS2`` / ``DFEDTARU``;
      * the series has no ALFRED vintage history at all.
    On a 400 we retry once **without** any real-time window — latest vintage
    only (accurate current value + short history, no first-print/revision
    split). A genuinely missing series still 400s and is recorded as an error."""
    base = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "units": units,
        "observation_start": history_start,
        "sort_order": "asc",
    }
    # bounded vintage window: ~4y keeps daily series under the ~2000-vintage cap
    # while preserving first-print/revision for anything the engine reports (-6)
    rt_start = (date.today() - timedelta(days=4 * 366)).isoformat()
    attempts = []
    if units == "lin":
        attempts.append({**base, "realtime_start": rt_start, "realtime_end": "9999-12-31"})
    attempts.append(base)  # latest-vintage-only fallback / default

    last_status = None
    for params in attempts:
        try:
            r = _http_get(params, timeout)
        except Exception as exc:  # timeout / connection / DNS
            _STATE["series_errors"][series_id] = f"{type(exc).__name__}"
            return None
        last_status = r.status_code
        if r.status_code == 429:
            _STATE["series_errors"][series_id] = "rate_limited_429"
            return None
        if r.status_code == 404:
            _STATE["series_errors"][series_id] = "not_found_404"
            return None
        if r.status_code >= 400:
            continue  # try the next (narrower) attempt
        try:
            body = r.json()
        except ValueError:
            _STATE["series_errors"][series_id] = "malformed_json"
            return None
        obs = body.get("observations")
        if not isinstance(obs, list):
            _STATE["series_errors"][series_id] = "no_observations_field"
            return None
        _STATE["series_errors"].pop(series_id, None)
        return obs

    _STATE["series_errors"][series_id] = f"http_{last_status}"
    return None


def _records_from_series(country: str, metric: str, series_id: str, unit_label: str,
                         obs: List[Dict[str, Any]]):
    """Collapse ALFRED vintage rows into one canonical MacroReleaseRecord per
    observation period (first-print value + latest revision)."""
    from macro_intelligence_engine import MacroReleaseRecord

    now_iso = datetime.now(timezone.utc).isoformat()
    by_period: Dict[str, List[Dict[str, Any]]] = {}
    for row in obs:
        d = row.get("date")
        val = _parse_num(row.get("value"))
        if not d or val is None:
            continue
        by_period.setdefault(d, []).append({"rt": row.get("realtime_start") or d, "v": val})

    periods = sorted(by_period)
    records = []
    prev_current: Optional[float] = None
    for i, period in enumerate(periods):
        vintages = sorted(by_period[period], key=lambda x: x["rt"])
        first = vintages[0]
        latest = vintages[-1]
        revised = len(vintages) > 1 and latest["v"] != first["v"]
        # release_timestamp = the date the FIRST print became public (ALFRED)
        rel_ts = f"{first['rt']}T13:30:00Z"  # conservative: standard AM release, UTC
        rec = MacroReleaseRecord(
            metric=metric,
            country=country,
            period=_period_label(period),
            release_timestamp=rel_ts,
            forecast=None,                        # FRED has no consensus — never guessed
            actual=latest["v"],
            previous=prev_current,
            unit=unit_label,
            source=f"FRED:{series_id}",
            source_timestamp=now_iso,             # retrieved_at
            revision_status="REVISED" if revised else "INITIAL",
            initial_actual=first["v"],
            revised_actual=latest["v"] if revised else None,
            revision_delta=round(latest["v"] - first["v"], 4) if revised else None,
            revision_timestamp=f"{latest['rt']}T13:30:00Z" if revised else None,
        )
        records.append(rec)
        prev_current = latest["v"]
    # keep only the most recent handful per metric — the engine only needs
    # current + a short history, and this bounds registry size.
    return records[-6:]


def _period_label(iso_date: str) -> str:
    """FRED observation date 'YYYY-MM-DD' -> 'YYYY-MM' (monthly) kept as-is for
    quarterly/annual series where the day encodes the quarter start."""
    try:
        d = date.fromisoformat(iso_date)
        return f"{d.year}-{d.month:02d}"
    except ValueError:
        return iso_date


class FredMacroProvider:
    name = "fred"
    is_live = True

    # Phase 66 — explicit capability declaration for the provider registry.
    KEY = "fred"
    try:  # avoid a hard import cycle at module load
        from api.providers.registry import Capability as _Cap
        CAPABILITIES = frozenset({
            _Cap.OBSERVATIONS, _Cap.RELEASE_TIMESTAMPS, _Cap.REVISIONS, _Cap.HISTORICAL,
        })
        del _Cap
    except Exception:  # pragma: no cover - defensive
        CAPABILITIES = frozenset()

    def __init__(self) -> None:
        self._api_key = (os.getenv("FRED_API_KEY") or "").strip()
        self._timeout = float(_cfg_int("FRED_TIMEOUT_SEC", 10))
        self._ttl = float(_cfg_int("FRED_CACHE_TTL_SEC", 21600))
        self._budget = float(_cfg_int("FRED_HYDRATE_BUDGET_SEC", 25))
        self._backoff = float(_cfg_int("FRED_RETRY_BACKOFF_SEC", 300))
        self._history_start = (os.getenv("FRED_HISTORY_START") or "2018-01-01").strip()

    # --- provider contract -------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def status(self) -> Dict[str, Any]:
        with _LOCK:
            fresh = (
                _STATE["hydrated_at"] > 0
                and (time.monotonic() - _STATE["hydrated_at"]) < self._ttl
            )
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
                "coverage": dict(_STATE["coverage"]),
                "series_errors": dict(_STATE["series_errors"]),
                "last_error": _STATE["last_error"],
                "hydrated_age_sec": round(time.monotonic() - _STATE["hydrated_at"], 1) if _STATE["hydrated_at"] else None,
                "cache_ttl_sec": self._ttl,
            }

    def hydrate_registry(self, force: bool = False) -> Dict[str, Any]:
        """Fetch mapped FRED series and load them into EconomicDataRegistry.
        Cheap no-op while the last hydrate is within TTL. Best-effort — a failed
        hydrate leaves the last-good registry in place and records the error."""
        with _LOCK:
            now_m = time.monotonic()
            if not self.configured:
                _STATE["last_error"] = "FRED_API_KEY not configured"
                return self.status()
            age = now_m - _STATE["hydrated_at"]
            if not force and _STATE["hydrated_at"] > 0 and age < self._ttl:
                return self.status()
            # Backoff: a broken provider stays degraded briefly so requests stay
            # instant instead of each one re-attempting 30+ slow HTTP calls.
            if not force and now_m < _STATE["retry_not_before"]:
                return self.status()

            from macro_intelligence_engine import EconomicDataRegistry

            # Take ownership so the seeded canonical dataset can never load in
            # place of (or alongside) live data.
            EconomicDataRegistry._PROVIDER_MANAGED = True

            _STATE["series_errors"] = {}
            deadline = now_m + self._budget
            jobs = [
                (ccy, metric, series_id, units, unit_label)
                for ccy, metrics in _SERIES.items()
                for metric, (series_id, units, unit_label) in metrics.items()
            ]

            def _one(job):
                ccy, metric, series_id, units, unit_label = job
                if time.monotonic() > deadline:
                    _STATE["series_errors"][series_id] = "budget_exceeded"
                    return None
                obs = _fetch_series(series_id, units, self._api_key, self._timeout, self._history_start)
                if not obs:
                    return None
                try:
                    recs = _records_from_series(ccy, metric, series_id, unit_label, obs)
                except Exception as exc:  # pragma: no cover - defensive
                    _STATE["series_errors"][series_id] = f"normalize:{type(exc).__name__}"
                    return None
                return (ccy, metric, recs) if recs else None

            all_records = []
            coverage: Dict[str, List[str]] = {}
            with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
                futs = [pool.submit(_one, j) for j in jobs]
                for fut in as_completed(futs, timeout=None):
                    try:
                        res = fut.result(timeout=max(0.1, deadline - time.monotonic() + 5))
                    except Exception:
                        continue
                    if res:
                        ccy, metric, recs = res
                        all_records.extend(recs)
                        coverage.setdefault(ccy, []).append(metric)

            if not all_records:
                _STATE["last_error"] = "FRED returned no usable observations for any mapped series"
                _STATE["retry_not_before"] = time.monotonic() + self._backoff
                # Leave the registry empty (not seeded) — downstream will
                # correctly report INSUFFICIENT_EVIDENCE / PROVIDER_UNAVAILABLE.
                if _STATE["registered"] == 0:
                    EconomicDataRegistry.reset_registry()
                return self.status()

            # Atomically replace the registry with the live dataset.
            EconomicDataRegistry.reset_registry()
            for rec in all_records:
                EconomicDataRegistry.register_release(rec)

            _STATE["records"] = all_records
            _STATE["registered"] = len(all_records)
            _STATE["coverage"] = coverage
            _STATE["hydrated_at"] = time.monotonic()
            _STATE["retry_not_before"] = 0.0
            _STATE["last_error"] = None
            return self.status()

    def get_events(self, start: date, end: date) -> List[Dict[str, Any]]:
        """Normalized EconomicEvent dicts for the calendar view — from the
        registry this provider hydrated."""
        self.hydrate_registry()
        from api.macro_provider import normalize_event
        from macro_intelligence_engine import EconomicDataRegistry

        out: List[Dict[str, Any]] = []
        seen: set = set()
        try:
            for rec in EconomicDataRegistry.get_releases_as_of(as_of=datetime.now(timezone.utc)):
                d = rec.to_dict()
                d["family"] = _METRIC_FAMILY.get(rec.metric)
                ev = normalize_event(d, provider=self.name, is_live=True)
                if ev and ev.get("timestamp"):
                    day = ev["timestamp"][:10]
                    if start.isoformat() <= day <= end.isoformat() and ev["event_id"] not in seen:
                        seen.add(ev["event_id"])
                        out.append(ev)
        except Exception:
            pass
        out.sort(key=lambda e: e.get("timestamp") or "")
        return out


def reset_state_for_tests() -> None:
    with _LOCK:
        _STATE.update({
            "hydrated_at": 0.0, "last_error": None, "registered": 0,
            "coverage": {}, "series_errors": {}, "records": [], "retry_not_before": 0.0,
        })
    try:
        from macro_intelligence_engine import EconomicDataRegistry
        EconomicDataRegistry._PROVIDER_MANAGED = False
    except Exception:
        pass
