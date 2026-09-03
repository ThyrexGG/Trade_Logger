# -*- coding: utf-8 -*-
"""
Canonical as-of-aware OHLCV candle window interface (Phase 68).

The repo's existing SMC / structure / regime functions in ``market_data.py``
already take a candle DataFrame and only look *inside* it. What was missing was a
single place that produces a candle window **truncated to ``candle_close <= as_of``**
so those functions become timestamp-correct with no change to their logic.

``get_candle_window(asset, timeframe, as_of, lookback)`` is that place.

Rules
  * Every candle in the returned window has closed at or before ``as_of``. The
    still-forming candle (``open + timeframe > as_of``) is dropped.
  * Live path (``as_of`` is now / recent): wraps
    ``market_data.get_candles_with_source``. If only the **synthetic offline
    fallback** served, this returns ``None`` — the fallback is never treated as
    real market data.
  * Historical path (``as_of`` in the past): dispatches to the provider named by
    ``HISTORICAL_OHLCV_PROVIDER``. The default ``auto`` resolves to the Phase-69
    persistent store (``historical_data_store``); when that store is empty it
    yields ``None`` for every request (the documented gap, now closeable by
    ``python -m market_data_ingest``). Tests install a deterministic in-process
    provider via ``set_test_provider``.
  * Read-only. No import of / path to any execution module.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

# timeframe -> seconds
_TF_SECONDS: Dict[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400, "d": 86400, "1w": 604800,
}

# how close to "now" an as_of can be and still be served by the live feed
_LIVE_TOLERANCE = timedelta(minutes=90)

_MIN_CANDLES = 2


def tf_seconds(timeframe: str) -> int:
    return _TF_SECONDS.get((timeframe or "").strip().lower(), 900)


def _norm_asset(asset: str) -> str:
    return (asset or "").upper().replace("/", "").replace(":", "").strip()


def _epoch(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CandleWindow
# ---------------------------------------------------------------------------
@dataclass
class CandleWindow:
    """A set of OHLCV candles, every one closed at or before ``as_of``."""

    asset: str
    timeframe: str
    candles: List[Dict[str, Any]]          # {time:int epoch (open), open,high,low,close,volume}
    as_of: str                             # ISO-8601 UTC
    provenance: str                        # "live_ohlcv" | "historical_ohlcv"
    source_id: str                         # e.g. "live:yahoo", "provider:<key>"
    latest_input_timestamp: str            # ISO — close time of the newest candle
    calculation_window: str
    requested_lookback: int = 250

    @property
    def n(self) -> int:
        return len(self.candles)

    @property
    def source(self) -> str:
        return self.provenance

    def to_df(self):
        import pandas as pd

        df = pd.DataFrame(self.candles)
        for col in ("open", "high", "low", "close", "volume"):
            if col not in df.columns:
                df[col] = 0.0
        return df

    def to_meta(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "timeframe": self.timeframe,
            "as_of": self.as_of,
            "provenance": self.provenance,
            "source_id": self.source_id,
            "latest_input_timestamp": self.latest_input_timestamp,
            "calculation_window": self.calculation_window,
            "candles": self.n,
        }


# ---------------------------------------------------------------------------
# Historical provider registry (Phase-66-style)
# ---------------------------------------------------------------------------
# A provider is any callable:  (asset, timeframe, as_of_epoch, lookback) -> list[candle]|None
HistoricalProviderFn = Callable[[str, str, float, int], Optional[List[Dict[str, Any]]]]

_LOCK = threading.Lock()
_PROVIDERS: Dict[str, HistoricalProviderFn] = {}
_TEST_PROVIDER: Optional[HistoricalProviderFn] = None

# Once the live candle feed has answered with only the synthetic offline fallback,
# stop hammering the network for a while — every subsequent live-window request
# in this window returns None immediately instead of paying N x socket timeouts.
_LIVE_FEED_DOWN_UNTIL: float = 0.0
_LIVE_FEED_DOWN_TTL = 120.0


def _live_feed_is_down() -> bool:
    return time.monotonic() < _LIVE_FEED_DOWN_UNTIL


def _mark_live_feed_down() -> None:
    global _LIVE_FEED_DOWN_UNTIL
    _LIVE_FEED_DOWN_UNTIL = time.monotonic() + _LIVE_FEED_DOWN_TTL


def _reset_live_feed_state() -> None:  # test hook
    global _LIVE_FEED_DOWN_UNTIL
    _LIVE_FEED_DOWN_UNTIL = 0.0


def register_provider(key: str, fn: HistoricalProviderFn) -> None:
    with _LOCK:
        _PROVIDERS[str(key).strip().lower()] = fn


def set_test_provider(fn: Optional[HistoricalProviderFn]) -> None:
    """Install (or clear with ``None``) a deterministic in-process historical
    provider. Test-only hook — makes the temporal tests offline + reproducible."""
    global _TEST_PROVIDER
    with _LOCK:
        _TEST_PROVIDER = fn


def historical_provider_key() -> str:
    return (os.getenv("HISTORICAL_OHLCV_PROVIDER") or "auto").strip().lower()


def _historical_provider() -> Optional[HistoricalProviderFn]:
    if _TEST_PROVIDER is not None:
        return _TEST_PROVIDER
    key = historical_provider_key()
    if key in ("", "none"):
        return None
    if key == "auto":
        # Phase 69: the persistent OHLCV store (``historical_data_store``) is the
        # default provider. When it is empty it yields ``None`` for every request
        # — the same honest gap as before, now closeable by ingestion.
        with _LOCK:
            prov = _PROVIDERS.get("store")
        if prov is None:
            try:
                import historical_data_store
                historical_data_store.register_with_phase68()
            except Exception:
                return None
            with _LOCK:
                prov = _PROVIDERS.get("store")
        return prov
    with _LOCK:
        return _PROVIDERS.get(key)


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------
def _truncate(candles: List[Dict[str, Any]], as_of_epoch: float, tf_sec: int
              ) -> List[Dict[str, Any]]:
    """Keep only candles whose CLOSE (open + timeframe) is <= as_of. Drops the
    still-forming candle. Boundary is inclusive (a candle closing exactly at
    as_of is kept)."""
    out: List[Dict[str, Any]] = []
    for c in candles:
        try:
            open_epoch = float(c["time"])
        except (KeyError, TypeError, ValueError):
            continue
        close_epoch = open_epoch + tf_sec
        if close_epoch <= as_of_epoch + 1e-6:
            out.append(c)
    out.sort(key=lambda x: x["time"])
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def get_candle_window(
    asset: str,
    timeframe: str = "15m",
    as_of: Optional[datetime] = None,
    lookback: int = 250,
) -> Optional[CandleWindow]:
    """Return an as-of-correct candle window, or ``None`` when no real market
    data can be served for the request."""
    asset = _norm_asset(asset)
    timeframe = (timeframe or "15m").strip().lower()
    tf_sec = tf_seconds(timeframe)
    live = as_of is None
    now = datetime.now(timezone.utc)
    as_of_dt = (as_of or now)
    if as_of_dt.tzinfo is None:
        as_of_dt = as_of_dt.replace(tzinfo=timezone.utc)
    as_of_epoch = _epoch(as_of_dt)

    is_recent = live or (now - as_of_dt) <= _LIVE_TOLERANCE

    raw: Optional[List[Dict[str, Any]]] = None
    provenance = "historical_ohlcv"
    source_id = "unknown"

    # A test provider takes the whole path — deterministic, never touches network.
    if _TEST_PROVIDER is not None:
        try:
            hist = _TEST_PROVIDER(asset, timeframe, as_of_epoch, lookback)
        except Exception:
            return None
        if not hist:
            return None
        kept = _truncate(hist, as_of_epoch, tf_sec)
        if len(kept) < _MIN_CANDLES:
            return None
        kept = kept[-lookback:]
        first_open = float(kept[0]["time"])
        last_open = float(kept[-1]["time"])
        last_close = last_open + tf_sec
        return CandleWindow(
            asset=asset, timeframe=timeframe, candles=kept,
            as_of=as_of_dt.isoformat(),
            provenance="live_ohlcv" if live else "historical_ohlcv",
            source_id="provider:test",
            latest_input_timestamp=_iso(last_close),
            calculation_window=(f"{len(kept)}x{timeframe} candles "
                                f"{_iso(first_open)[:19]}Z -> {_iso(last_close)[:19]}Z"),
            requested_lookback=lookback,
        )

    if is_recent and not _live_feed_is_down():
        try:
            import market_data
            candles, upstream = market_data.get_candles_with_source(
                asset, timeframe, count=max(lookback + 30, 60))
        except Exception:
            candles, upstream = [], "unknown"
        if upstream == "synthetic_fallback" or not candles:
            # never treat the offline fallback as real market data
            _mark_live_feed_down()
        else:
            raw = candles
            provenance = "live_ohlcv"
            source_id = f"live:{upstream}"

    if raw is None:
        prov = _historical_provider()
        if prov is None:
            return None
        try:
            hist = prov(asset, timeframe, as_of_epoch, lookback)
        except Exception:
            return None
        if not hist:
            return None
        raw = hist
        provenance = "historical_ohlcv"
        if _TEST_PROVIDER is not None:
            _pkey = "test"
        else:
            _pkey = historical_provider_key()
            if _pkey == "auto":
                _pkey = "store"
        source_id = f"provider:{_pkey}"

    kept = _truncate(raw, as_of_epoch, tf_sec)
    if len(kept) < _MIN_CANDLES:
        return None
    kept = kept[-lookback:]

    first_open = float(kept[0]["time"])
    last_open = float(kept[-1]["time"])
    last_close = last_open + tf_sec
    window = (
        f"{len(kept)}x{timeframe} candles "
        f"{_iso(first_open)[:19]}Z -> {_iso(last_close)[:19]}Z"
    )

    return CandleWindow(
        asset=asset,
        timeframe=timeframe,
        candles=kept,
        as_of=as_of_dt.isoformat(),
        provenance=provenance,
        source_id=source_id,
        latest_input_timestamp=_iso(last_close),
        calculation_window=window,
        requested_lookback=lookback,
    )


__all__ = [
    "CandleWindow",
    "get_candle_window",
    "register_provider",
    "set_test_provider",
    "historical_provider_key",
    "tf_seconds",
    "_reset_live_feed_state",
]
