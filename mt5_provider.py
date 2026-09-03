# -*- coding: utf-8 -*-
"""
MetaTrader 5 historical intraday OHLCV provider (Phase 74).

Uses the local MT5 terminal + the account credentials already in the environment
(``MT5_LOGIN`` / ``MT5_PASSWORD`` / ``MT5_SERVER``) to pull **real broker
historical candles**, including deep 1-minute XAUUSD history that yfinance cannot
supply.

Key correctness points:
  * MT5 ``rates['time']`` is **broker server time**, not UTC. This provider
    detects the server↔UTC offset dynamically (compare a live tick to wall-clock
    UTC, round to the hour) and converts every candle to true UTC epoch seconds.
  * Deep history needs **chunked** ``copy_rates_range`` with download retries —
    a single large request returns "Invalid params" until the terminal has
    fetched the range.
  * ``XAUUSD`` here is the broker's **spot metal** (path ``Precious_Metals`` /
    ``XAUUSD``, 2 digits), NOT GC futures — so it is labelled ``XAUUSD`` /
    ``METAL_SPOT``, not a futures proxy.

Import-safe: the ``MetaTrader5`` package is Windows-only; on any other platform
this provider reports ``PROVIDER_UNAVAILABLE`` and never raises at import.

Read-only. No import of / path to any execution / broker-adapter / risk module.
Credentials are read from the environment only and never returned anywhere.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import research_universe
from historical_provider import (
    FetchResult,
    ProviderCapability,
    ProviderCapabilityState,
    required_depth_days,
)

try:  # Windows-only package
    import MetaTrader5 as _mt5  # type: ignore
    _MT5_IMPORTED = True
except Exception:  # pragma: no cover - platform dependent
    _mt5 = None
    _MT5_IMPORTED = False

_LOCK = threading.RLock()

_TF_SEC = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}

# canonical timeframe -> (mt5 constant name, chunk days for the backward walk)
_TF_PLAN = {
    "1m": ("TIMEFRAME_M1", 14),
    "5m": ("TIMEFRAME_M5", 40),
    "15m": ("TIMEFRAME_M15", 120),
    "1h": ("TIMEFRAME_H1", 365),
    "4h": ("TIMEFRAME_H4", 730),
    "1d": ("TIMEFRAME_D1", 1825),
}

# XAUUSD/XAGUSD are the broker's spot metals; FX are plain pairs on this account.
_VENDOR_SYMBOL = {}  # canonical -> vendor; identity unless overridden

_ASSET_TYPE = {"METAL": "METAL_SPOT", "FX_MAJOR": "FX_SPOT", "FX_CROSS": "FX_SPOT"}


class _State:
    connected = False
    server_utc_offset_sec = 0
    offset_checked_at = 0.0
    depth_cache: Dict[str, ProviderCapability] = {}


_S = _State()


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
def _available() -> bool:
    return _MT5_IMPORTED and _mt5 is not None


def _connect() -> bool:
    if not _available():
        return False
    with _LOCK:
        login = os.getenv("MT5_LOGIN")
        server = os.getenv("MT5_SERVER")
        password = os.getenv("MT5_PASSWORD")
        try:
            if login and server and password:
                ok = _mt5.initialize(login=int(login), server=server,
                                     password=password, timeout=25000)
            else:
                ok = _mt5.initialize(timeout=25000)
        except Exception:
            ok = False
        _S.connected = bool(ok)
        return _S.connected


def _server_offset_sec() -> int:
    """server_time - UTC, seconds, rounded to the hour. Cached for 30 min."""
    now = time.time()
    if _S.offset_checked_at and now - _S.offset_checked_at < 1800:
        return _S.server_utc_offset_sec
    try:
        _mt5.symbol_select("EURUSD", True)
        tick = _mt5.symbol_info_tick("EURUSD") or _mt5.symbol_info_tick("XAUUSD")
        if tick and tick.time:
            raw = tick.time - now
            _S.server_utc_offset_sec = int(round(raw / 3600.0) * 3600)
            _S.offset_checked_at = now
    except Exception:
        pass
    return _S.server_utc_offset_sec


def shutdown() -> None:
    if _available():
        try:
            _mt5.shutdown()
        except Exception:
            pass
        _S.connected = False


# ---------------------------------------------------------------------------
# Symbol mapping (§13)
# ---------------------------------------------------------------------------
def vendor_symbol(canonical: str) -> str:
    return _VENDOR_SYMBOL.get(research_universe.normalise(canonical),
                              research_universe.normalise(canonical))


def _select(vsym: str) -> bool:
    try:
        return bool(_mt5.symbol_select(vsym, True))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------
class MT5Provider:
    name = "mt5"

    def _tf_const(self, timeframe: str):
        plan = _TF_PLAN.get(timeframe)
        return getattr(_mt5, plan[0]) if plan else None

    def capability(self, instrument: str, timeframe: str) -> ProviderCapability:
        inst = research_universe.get_instrument(instrument)
        need = required_depth_days(timeframe)
        if not _available():
            return ProviderCapability(
                self.name, instrument, timeframe,
                ProviderCapabilityState.PROVIDER_UNAVAILABLE, None, need,
                "MetaTrader5 package not importable (Windows-only)")
        if inst is None:
            return ProviderCapability(self.name, instrument, timeframe,
                                      ProviderCapabilityState.INSTRUMENT_NOT_SUPPORTED,
                                      None, need, "not in the research universe")
        if timeframe not in _TF_PLAN:
            return ProviderCapability(self.name, instrument, timeframe,
                                      ProviderCapabilityState.TIMEFRAME_NOT_SUPPORTED,
                                      None, need, f"timeframe '{timeframe}' not supported")

        ck = f"{research_universe.normalise(instrument)}::{timeframe}"
        cached = _S.depth_cache.get(ck)
        if cached and (time.time() - getattr(cached, "_probed_at", 0)) < 3600:
            return cached

        if not (_S.connected or _connect()):
            return ProviderCapability(self.name, instrument, timeframe,
                                      ProviderCapabilityState.PROVIDER_UNAVAILABLE,
                                      None, need, "MT5 terminal not reachable / not logged in")

        vsym = vendor_symbol(instrument)
        if not _select(vsym):
            return ProviderCapability(self.name, instrument, timeframe,
                                      ProviderCapabilityState.INSTRUMENT_NOT_SUPPORTED,
                                      None, need, f"broker symbol '{vsym}' not available")

        earliest, latest, bars = self._probe_depth(vsym, timeframe, enough_days=need * 1.3)
        depth_days = round((latest - earliest).total_seconds() / 86400.0, 1) if earliest and latest else 0.0
        state = (ProviderCapabilityState.OK if depth_days >= need
                 else ProviderCapabilityState.INSUFFICIENT_HISTORICAL_DEPTH)
        cap = ProviderCapability(
            self.name, research_universe.normalise(instrument), timeframe, state,
            depth_days, need,
            "" if state == ProviderCapabilityState.OK
            else f"MT5 terminal holds ~{depth_days:.0f}d of {timeframe}; ~{need:.0f}d needed",
            limitations=[
                f"broker feed (server {server_offset_hours():+d}h) — spot, personal-use license only",
            ],
        )
        cap.__dict__["_probed_at"] = time.time()
        cap.__dict__["earliest_available"] = earliest.isoformat() if earliest else None
        cap.__dict__["latest_available"] = latest.isoformat() if latest else None
        cap.__dict__["probed_bars"] = bars
        cap.__dict__["vendor_symbol"] = vsym
        _S.depth_cache[ck] = cap
        return cap

    def _probe_depth(self, vsym: str, timeframe: str, enough_days: float = 1e9):
        """Backward-walk in chunks to find how far real candles reach. Stops early
        once ``enough_days`` of history is confirmed (capability only needs
        'enough', not the true floor)."""
        tf = self._tf_const(timeframe)
        chunk_days = _TF_PLAN[timeframe][1]
        off = _server_offset_sec()
        now = datetime.now(timezone.utc)
        latest = None
        earliest = None
        total = 0
        end = now
        empty_streak = 0
        for _ in range(40):
            start = end - timedelta(days=chunk_days)
            r = self._range(tf, vsym, start, end, off)
            if not r:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                end = start
                continue
            empty_streak = 0
            total += len(r)
            latest = latest or datetime.fromtimestamp(r[-1]["time"], timezone.utc)
            earliest = datetime.fromtimestamp(r[0]["time"], timezone.utc)
            end = start
            if latest and earliest and (latest - earliest).total_seconds() / 86400.0 >= enough_days:
                break
        return earliest, latest, total

    def _range(self, tf, vsym: str, start: datetime, end: datetime, off: int, retries: int = 4):
        # Request with generous buffers on both sides (the terminal returns only
        # what it holds; the offset sign / DST is then corrected on the returned
        # timestamps, and dedup handles the overlap).
        s = (start - timedelta(days=1)).replace(tzinfo=None)
        e = (end + timedelta(hours=12)).replace(tzinfo=None)
        for _ in range(retries):
            try:
                rates = _mt5.copy_rates_range(vsym, tf, s, e)
            except Exception:
                rates = None
            if rates is not None and len(rates):
                lo = int(start.timestamp())
                hi = int(end.timestamp())
                out = []
                for x in rates:
                    t = int(x["time"]) - off   # server epoch -> true UTC epoch
                    if t < lo or t > hi:
                        continue
                    out.append({
                        "time": t,
                        "open": float(x["open"]), "high": float(x["high"]),
                        "low": float(x["low"]), "close": float(x["close"]),
                        "volume": float(x["tick_volume"]),
                    })
                if out:
                    return out
            time.sleep(2.5)
        return []

    def fetch(self, instrument: str, timeframe: str,
              start: Optional[datetime] = None) -> FetchResult:
        now = datetime.now(timezone.utc)
        cap = self.capability(instrument, timeframe)
        vsym = cap.__dict__.get("vendor_symbol", vendor_symbol(instrument))
        res = FetchResult(
            provider=self.name, instrument=research_universe.normalise(instrument),
            timeframe=timeframe, candles=[],
            requested_start=start.isoformat() if start else None,
            requested_end=now.isoformat(), actual_start=None, actual_end=None,
            retrieved_at=now.isoformat(), timezone="UTC",
            source_id=f"mt5:{vsym}:{timeframe}", completeness=None, capability=cap,
        )
        if cap.state in (ProviderCapabilityState.PROVIDER_UNAVAILABLE,
                         ProviderCapabilityState.INSTRUMENT_NOT_SUPPORTED,
                         ProviderCapabilityState.TIMEFRAME_NOT_SUPPORTED):
            res.error = cap.reason
            return res
        if not (_S.connected or _connect()):
            res.error = "MT5 terminal not reachable"
            return res

        _select(vsym)
        tf = self._tf_const(timeframe)
        off = _server_offset_sec()
        chunk_days = _TF_PLAN[timeframe][1]
        floor = start or (now - timedelta(days=3650))
        all_rows: Dict[int, Dict[str, Any]] = {}
        end = now
        empty_streak = 0
        for _ in range(60):
            if end <= floor:
                break
            cs = max(floor, end - timedelta(days=chunk_days))
            r = self._range(tf, vsym, cs, end, off)
            if not r:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                end = cs
                continue
            empty_streak = 0
            for row in r:
                all_rows[row["time"]] = row
            end = cs

        rows = [all_rows[t] for t in sorted(all_rows)]
        if not rows:
            res.error = "no candles returned from MT5"
            return res
        res.candles = rows
        res.actual_start = datetime.fromtimestamp(rows[0]["time"], timezone.utc).isoformat()
        res.actual_end = datetime.fromtimestamp(rows[-1]["time"], timezone.utc).isoformat()
        span = rows[-1]["time"] - rows[0]["time"]
        tf_sec = _TF_SEC.get(timeframe, 900)
        expected = int(span / tf_sec * (5 / 7)) + 1 if tf_sec else len(rows)
        res.completeness = round(min(1.0, len(rows) / max(expected, 1)), 3)
        return res


def server_offset_hours() -> int:
    return int(_server_offset_sec() / 3600) if (_S.connected or _S.offset_checked_at) else 0


_PROVIDER_SINGLETON = MT5Provider()


def get() -> MT5Provider:
    return _PROVIDER_SINGLETON


def register_self() -> None:
    """Register with the historical_provider registry as ``mt5``."""
    try:
        import historical_provider
        historical_provider.register("mt5", _PROVIDER_SINGLETON)
    except Exception:
        pass


register_self()


__all__ = ["MT5Provider", "get", "register_self", "vendor_symbol", "server_offset_hours",
           "shutdown"]
