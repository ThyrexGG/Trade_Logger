# -*- coding: utf-8 -*-
"""
Historical intraday OHLCV provider abstraction (Phase 73).

Phases 69-72 wired yfinance directly into ``market_data_ingest`` and registered a
single ``store`` provider with ``historical_market_data``. Phase 73 formalises
that into a **provider protocol with capability metadata**, so:

  * strategy / backtester code never couples to a vendor,
  * a provider declares what it can and cannot deliver *before* ingestion,
  * an additional key-gated vendor can be dropped in via env vars only
    (``HISTORICAL_OHLCV_PROVIDER`` / ``HISTORICAL_OHLCV_API_KEY``), never a
    secret in source / frontend / artifact / AI context,
  * when depth is inadequate the result is an explicit
    ``INSUFFICIENT_HISTORICAL_DEPTH`` — never fabricated candles.

Data flow (unchanged where it works):
    provider.fetch() -> normalise -> validate (historical_data_store) ->
    historical_candles -> get_candle_window(as_of) -> backtester / strategy
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

import research_universe

# canonical timeframe -> seconds
_TF_SEC = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}

INTRADAY_TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")


class ProviderCapabilityState:
    OK = "OK"
    INSUFFICIENT_HISTORICAL_DEPTH = "INSUFFICIENT_HISTORICAL_DEPTH"
    TIMEFRAME_NOT_SUPPORTED = "TIMEFRAME_NOT_SUPPORTED"
    INSTRUMENT_NOT_SUPPORTED = "INSTRUMENT_NOT_SUPPORTED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass
class ProviderCapability:
    """What a provider can deliver for one instrument x timeframe, decided
    *before* ingestion — from the provider's own documented limits, not a guess."""
    provider: str
    instrument: str
    timeframe: str
    state: str
    approx_depth_days: Optional[float]
    required_depth_days: float
    reason: str = ""
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class FetchResult:
    """The outcome of one provider fetch — candles plus the metadata §4 requires."""
    provider: str
    instrument: str
    timeframe: str
    candles: List[Dict[str, Any]]                # {time,open,high,low,close,volume} epoch-sec UTC
    requested_start: Optional[str]
    requested_end: Optional[str]
    actual_start: Optional[str]
    actual_end: Optional[str]
    retrieved_at: str
    timezone: str                                # always "UTC" once normalised
    source_id: str                               # e.g. "yfinance:GC=F:15m"
    completeness: Optional[float]                 # actual_bars / expected_bars, 0..1
    capability: ProviderCapability
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.candles)

    def to_meta(self) -> Dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "candles"}
        d["capability"] = self.capability.to_dict()
        d["bars"] = len(self.candles)
        return d


class HistoricalIntradayProvider(Protocol):
    name: str

    def capability(self, instrument: str, timeframe: str) -> ProviderCapability: ...

    def fetch(self, instrument: str, timeframe: str,
              start: Optional[datetime] = None) -> FetchResult: ...


# --------------------------------------------------------------------------
# Required history depth per timeframe (from research_universe sufficiency rules,
# translated to days). A provider that cannot reach this is INSUFFICIENT.
# --------------------------------------------------------------------------
def required_depth_days(timeframe: str) -> float:
    rule = research_universe.sufficiency_rule(timeframe)
    if rule is None:
        return 365.0
    sec = _TF_SEC.get(timeframe, 900)
    # min_bars over a ~5/7 trading-week factor
    return round(rule.min_bars * sec / 86400.0 / (5 / 7), 1)


# --------------------------------------------------------------------------
# yfinance provider — the currently configured free source
# --------------------------------------------------------------------------
# Documented yfinance intraday history limits (probed 2026-09, GC=F):
_YF_DEPTH_DAYS = {"1m": 8.0, "2m": 38.0, "5m": 70.0, "15m": 70.0, "30m": 70.0,
                  "1h": 730.0, "4h": 730.0, "1d": 3650.0}
_YF_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}
_YF_RESAMPLE = {"4h": ("1h", 4)}


class YFinanceProvider:
    name = "yfinance"

    def capability(self, instrument: str, timeframe: str) -> ProviderCapability:
        inst = research_universe.get_instrument(instrument)
        need = required_depth_days(timeframe)
        if inst is None:
            return ProviderCapability(self.name, instrument, timeframe,
                                      ProviderCapabilityState.INSTRUMENT_NOT_SUPPORTED,
                                      None, need, "not in the research universe")
        if timeframe not in INTRADAY_TIMEFRAMES:
            return ProviderCapability(self.name, instrument, timeframe,
                                      ProviderCapabilityState.TIMEFRAME_NOT_SUPPORTED,
                                      None, need, f"timeframe '{timeframe}' not supported")
        depth = _YF_DEPTH_DAYS.get(timeframe if timeframe != "4h" else "1h")
        lims: List[str] = []
        if inst.category in ("FX_MAJOR", "FX_CROSS"):
            lims.append("FX served as Yahoo '<PAIR>=X' synthetic spot - no real volume, "
                        "weaker intraday quality")
        if timeframe == "4h":
            lims.append("4h is resampled from 1h (not a native yfinance interval)")
        if depth is not None and depth < need:
            return ProviderCapability(
                self.name, instrument, timeframe,
                ProviderCapabilityState.INSUFFICIENT_HISTORICAL_DEPTH,
                depth, need,
                f"yfinance gives ~{depth:.0f}d of {timeframe}; ~{need:.0f}d needed for a "
                f"statistically valid sample", lims)
        return ProviderCapability(self.name, instrument, timeframe,
                                  ProviderCapabilityState.OK, depth, need, "", lims)

    def fetch(self, instrument: str, timeframe: str,
              start: Optional[datetime] = None) -> FetchResult:
        import market_data_ingest as ing  # reuse the existing, tested fetch/normalise path

        cap = self.capability(instrument, timeframe)
        inst = research_universe.get_instrument(instrument)
        now = datetime.now(timezone.utc)
        base = FetchResult(
            provider=self.name, instrument=research_universe.normalise(instrument),
            timeframe=timeframe, candles=[],
            requested_start=start.isoformat() if start else None,
            requested_end=now.isoformat(), actual_start=None, actual_end=None,
            retrieved_at=now.isoformat(), timezone="UTC",
            source_id=f"yfinance:{inst.yf_symbol if inst else '?'}:{timeframe}",
            completeness=None, capability=cap,
        )
        if cap.state in (ProviderCapabilityState.INSTRUMENT_NOT_SUPPORTED,
                         ProviderCapabilityState.TIMEFRAME_NOT_SUPPORTED):
            base.error = cap.reason
            return base
        if ing.yf is None:
            base.error = "yfinance unavailable in this environment"
            base.capability.state = ProviderCapabilityState.PROVIDER_UNAVAILABLE
            return base

        resample_factor = None
        if timeframe in _YF_RESAMPLE:
            src_tf, resample_factor = _YF_RESAMPLE[timeframe]
            interval, period = src_tf, ing._YF_PLAN[src_tf][1]
        else:
            interval, period = _YF_INTERVAL[timeframe], ing._YF_PLAN[timeframe][1]

        try:
            df = ing._yf_download(inst.yf_symbol, interval, period, start=start)
        except Exception as e:  # pragma: no cover - network
            base.error = f"fetch failed: {e!r}"
            base.capability.state = ProviderCapabilityState.PROVIDER_UNAVAILABLE
            return base

        candles = ing._frame_to_candles(df)
        if resample_factor:
            candles = ing._resample(candles, resample_factor, _TF_SEC[interval])
        if not candles:
            base.error = "no candles returned from source"
            return base

        candles.sort(key=lambda c: c["time"])
        base.candles = candles
        base.actual_start = datetime.fromtimestamp(candles[0]["time"], tz=timezone.utc).isoformat()
        base.actual_end = datetime.fromtimestamp(candles[-1]["time"], tz=timezone.utc).isoformat()
        span_sec = candles[-1]["time"] - candles[0]["time"]
        tf_sec = _TF_SEC.get(timeframe, 900)
        expected = int(span_sec / tf_sec * (5 / 7)) + 1 if tf_sec else len(candles)
        base.completeness = round(min(1.0, len(candles) / max(expected, 1)), 3)
        return base


# --------------------------------------------------------------------------
# Env-key vendor provider — architecture only, no vendor bundled (§5)
# --------------------------------------------------------------------------
class EnvKeyVendorProvider:
    """Placeholder for a keyed commercial vendor. Reads
    ``HISTORICAL_OHLCV_PROVIDER`` / ``HISTORICAL_OHLCV_API_KEY`` from the
    environment only. Ships **disabled** — no vendor client is bundled. When a
    key is present but no adapter is wired it returns ``PROVIDER_UNAVAILABLE``
    with a clear message rather than doing anything.
    """
    name = "env_vendor"

    def _configured(self) -> Optional[str]:
        p = (os.getenv("HISTORICAL_OHLCV_PROVIDER") or "").strip().lower()
        return p if p and p not in ("", "none", "auto", "yfinance", "store") else None

    def capability(self, instrument: str, timeframe: str) -> ProviderCapability:
        need = required_depth_days(timeframe)
        name = self._configured()
        if not name:
            return ProviderCapability("env_vendor", instrument, timeframe,
                                      ProviderCapabilityState.NOT_CONFIGURED, None, need,
                                      "no HISTORICAL_OHLCV_PROVIDER configured")
        return ProviderCapability(
            name, instrument, timeframe, ProviderCapabilityState.PROVIDER_UNAVAILABLE,
            None, need,
            f"HISTORICAL_OHLCV_PROVIDER={name} is set but no vendor adapter is bundled — "
            f"add one that registers via historical_data_provider.register()")

    def fetch(self, instrument: str, timeframe: str,
              start: Optional[datetime] = None) -> FetchResult:
        _ = start
        cap = self.capability(instrument, timeframe)
        now = datetime.now(timezone.utc)
        return FetchResult(
            provider=cap.provider, instrument=research_universe.normalise(instrument),
            timeframe=timeframe, candles=[], requested_start=None, requested_end=None,
            actual_start=None, actual_end=None, retrieved_at=now.isoformat(),
            timezone="UTC", source_id=f"{cap.provider}:unconfigured", completeness=None,
            capability=cap, error=cap.reason,
        )


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
_PROVIDERS: Dict[str, "HistoricalIntradayProvider"] = {
    "yfinance": YFinanceProvider(),
    "env_vendor": EnvKeyVendorProvider(),
}


def register(name: str, provider: "HistoricalIntradayProvider") -> None:
    _PROVIDERS[name.strip().lower()] = provider


def get_provider(name: Optional[str] = None) -> "HistoricalIntradayProvider":
    if name:
        p = _PROVIDERS.get(name.strip().lower())
        if p:
            return p
    configured = (os.getenv("HISTORICAL_OHLCV_PROVIDER") or "").strip().lower()
    if configured in _PROVIDERS and configured not in ("auto", "store", "none", ""):
        return _PROVIDERS[configured]
    return _PROVIDERS["yfinance"]


def list_capabilities(timeframes=INTRADAY_TIMEFRAMES) -> List[Dict[str, Any]]:
    prov = get_provider()
    out = []
    for inst in research_universe.universe():
        for tf in timeframes:
            out.append(prov.capability(inst.symbol, tf).to_dict())
    return out


__all__ = [
    "INTRADAY_TIMEFRAMES", "ProviderCapabilityState", "ProviderCapability",
    "FetchResult", "HistoricalIntradayProvider", "YFinanceProvider",
    "EnvKeyVendorProvider", "register", "get_provider", "list_capabilities",
    "required_depth_days",
]
