# -*- coding: utf-8 -*-
"""
Controlled historical OHLCV ingestion (Phase 69).

Populates the ``historical_candles`` store (``historical_data_store``) from
Yahoo Finance. This is the *only* data source wired in Phase 69 — its intraday
depth is shallow (15m/5m ~60 days, 1m ~7 days), so honest multi-year coverage
exists only for **1h / 4h / 1d**. `research_universe.timeframe_is_data_capable`
encodes that; everything below stays explicit about it.

Capabilities (§6): initial backfill, incremental update, duplicate-safe writes,
source provenance, OHLC-consistency validation (in the store), gap detection,
timezone normalization to UTC. Bad records are rejected and counted, never
silently repaired.

Usage:
    python -m market_data_ingest --universe --timeframes 1d,1h
    python -m market_data_ingest --asset XAUUSD --timeframe 1d
    python -m market_data_ingest --incremental --universe
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import historical_data_store as store
import research_universe

# yfinance is optional at import time — ingestion simply reports it is missing.
try:
    import yfinance as yf
except Exception:  # pragma: no cover - environment dependent
    yf = None

import pandas as pd

# canonical timeframe -> (yfinance interval, yfinance period for a full backfill)
_YF_PLAN: Dict[str, Tuple[str, str]] = {
    "1d": ("1d", "10y"),
    "1h": ("1h", "730d"),
    "15m": ("15m", "60d"),
    "5m": ("5m", "60d"),
    "1m": ("1m", "7d"),
}
# 4h is not offered natively by yfinance — resampled from 1h.
_RESAMPLE_FROM = {"4h": ("1h", 4)}


@dataclass
class IngestResult:
    asset: str
    timeframe: str
    ok: bool
    source: str = "yahoo"
    mode: str = "backfill"
    fetched: int = 0
    stored_report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    coverage: Optional[Dict[str, Any]] = None
    gaps: List[Dict[str, Any]] = field(default_factory=list)
    provider_meta: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset, "timeframe": self.timeframe, "ok": self.ok,
            "source": self.source, "mode": self.mode, "fetched": self.fetched,
            "stored": self.stored_report, "error": self.error,
            "coverage": self.coverage, "gap_count": len(self.gaps),
        }


def _to_utc_epoch(ts: pd.Timestamp) -> int:
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return int(ts.timestamp())


def _frame_to_candles(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    cols = {c.lower(): c for c in df.columns}
    need = ("open", "high", "low", "close")
    if not all(k in cols for k in need):
        return []
    out: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        try:
            o, h, l, c = (float(row[cols["open"]]), float(row[cols["high"]]),
                          float(row[cols["low"]]), float(row[cols["close"]]))
        except (TypeError, ValueError):
            continue
        if any(pd.isna(v) for v in (o, h, l, c)):
            continue
        vol = 0.0
        if "volume" in cols:
            try:
                vol = float(row[cols["volume"]])
                if pd.isna(vol):
                    vol = 0.0
            except (TypeError, ValueError):
                vol = 0.0
        out.append({"time": _to_utc_epoch(pd.Timestamp(idx)), "open": o,
                    "high": h, "low": l, "close": c, "volume": vol})
    return out


def _resample(candles: List[Dict[str, Any]], factor: int, src_tf_sec: int
              ) -> List[Dict[str, Any]]:
    """Aggregate `factor` source candles into one, anchored to the bucket
    boundary. Partial trailing bucket is dropped."""
    if not candles:
        return []
    bucket_sec = src_tf_sec * factor
    groups: Dict[int, List[Dict[str, Any]]] = {}
    for c in candles:
        key = (c["time"] // bucket_sec) * bucket_sec
        groups.setdefault(key, []).append(c)
    out: List[Dict[str, Any]] = []
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda x: x["time"])
        if len(g) < factor:
            continue
        out.append({
            "time": key, "open": g[0]["open"],
            "high": max(x["high"] for x in g),
            "low": min(x["low"] for x in g),
            "close": g[-1]["close"],
            "volume": sum(x["volume"] for x in g),
        })
    return out


def _yf_download(yf_symbol: str, interval: str, period: str,
                 start: Optional[datetime] = None) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance not installed")
    kwargs: Dict[str, Any] = {"interval": interval, "progress": False, "auto_adjust": False}
    if start is not None:
        kwargs["start"] = start.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        kwargs["period"] = period
    df = yf.download(yf_symbol, **kwargs)
    return df if df is not None else pd.DataFrame()


def _provider_ingest(asset: str, timeframe: str, provider_name: str,
                     incremental: bool, res: "IngestResult") -> "IngestResult":
    """Phase 74 — ingest through a registered ``historical_provider`` (e.g. mt5)."""
    import historical_provider
    prov = historical_provider.get_provider(provider_name)
    start = None
    if incremental:
        cov = store.get_coverage(asset, timeframe)
        if cov.last_open_time:
            start = datetime.fromtimestamp(
                cov.last_open_time - 5 * store.tf_seconds(timeframe), tz=timezone.utc)
    fr = prov.fetch(asset, timeframe, start=start)
    res.source = prov.name
    res.fetched = len(fr.candles)
    res.provider_meta = fr.to_meta()
    if fr.error and not fr.candles:
        res.error = fr.error
        return res
    # §9/§10 — never silently merge two vendors on the same key. If the series
    # holds candles from a different source, a non-incremental run replaces them.
    if not incremental:
        existing = store.series_sources(asset, timeframe)
        stale = [s for s in existing if s and s != prov.name]
        if stale:
            for s in stale:
                store.clear_series(asset, timeframe, only_source=s)
            res.provider_meta["replaced_sources"] = stale
    rep = store.upsert_candles(asset, timeframe, fr.candles,
                               source=prov.name, source_revision=fr.source_id)
    res.stored_report = rep.to_dict()
    cov = store.get_coverage(asset, timeframe)
    res.coverage = cov.to_dict()
    res.gaps = store.detect_gaps(asset, timeframe, min_gap_bars=2)
    res.ok = rep.rejected < rep.received or rep.received == 0
    return res


def ingest(asset: str, timeframe: str, incremental: bool = False,
           lookback_pad_bars: int = 5, provider: Optional[str] = None) -> IngestResult:
    asset = research_universe.normalise(asset)
    timeframe = (timeframe or "").strip().lower()
    inst = research_universe.get_instrument(asset)
    res = IngestResult(asset=asset, timeframe=timeframe, ok=False,
                       mode="incremental" if incremental else "backfill")

    if inst is None:
        res.error = f"{asset} is not in the research universe"
        return res

    prov_name = provider or os.getenv("HISTORICAL_OHLCV_PROVIDER") or ""
    prov_name = prov_name.strip().lower()
    if prov_name and prov_name not in ("", "none", "auto", "store", "yfinance", "yahoo"):
        return _provider_ingest(asset, timeframe, prov_name, incremental, res)

    if yf is None:
        res.error = "yfinance unavailable in this environment"
        return res

    resample_factor = None
    if timeframe in _RESAMPLE_FROM:
        src_tf, resample_factor = _RESAMPLE_FROM[timeframe]
        yf_interval, yf_period = _YF_PLAN[src_tf]
        effective_tf = src_tf
    elif timeframe in _YF_PLAN:
        yf_interval, yf_period = _YF_PLAN[timeframe]
        effective_tf = timeframe
    else:
        res.error = f"timeframe '{timeframe}' not supported by the yfinance plan"
        return res

    start_dt = None
    if incremental:
        cov = store.get_coverage(asset, timeframe)
        if cov.last_open_time:
            src_tf_sec = store.tf_seconds(effective_tf)
            start_dt = datetime.fromtimestamp(
                cov.last_open_time - lookback_pad_bars * src_tf_sec, tz=timezone.utc)

    try:
        df = _yf_download(inst.yf_symbol, yf_interval, yf_period, start=start_dt)
    except Exception as e:  # pragma: no cover - network dependent
        res.error = f"fetch failed: {e!r}"
        return res

    candles = _frame_to_candles(df)
    if resample_factor:
        candles = _resample(candles, resample_factor, store.tf_seconds(effective_tf))
    res.fetched = len(candles)
    if not candles:
        res.error = "no candles returned from source"
        return res

    source_revision = f"{inst.yf_symbol}:{yf_interval}"
    if resample_factor:
        source_revision += f":resample{resample_factor}"
    rep = store.upsert_candles(
        asset, timeframe, candles, source="yahoo", source_revision=source_revision,
    )
    res.stored_report = rep.to_dict()
    cov = store.get_coverage(asset, timeframe)
    res.coverage = cov.to_dict()
    res.gaps = store.detect_gaps(asset, timeframe, min_gap_bars=2)
    res.ok = rep.rejected < rep.received or rep.received == 0
    return res


def ingest_universe(timeframes: Optional[List[str]] = None, incremental: bool = False,
                    pause_sec: float = 0.6, provider: Optional[str] = None
                    ) -> List[IngestResult]:
    tfs = timeframes or ["1d", "1h", "4h"]
    results: List[IngestResult] = []
    for inst in research_universe.universe():
        for tf in tfs:
            results.append(ingest(inst.symbol, tf, incremental=incremental, provider=provider))
            time.sleep(pause_sec)
    return results


def _print_report(results: List[IngestResult]) -> None:
    print(f"\n{'ASSET':<9} {'TF':<4} {'OK':<3} {'FETCH':>6} {'INS':>6} {'UPD':>6} "
          f"{'REJ':>5} {'BARS':>7}  NOTES")
    print("-" * 78)
    for r in results:
        sr = r.stored_report or {}
        cov = r.coverage or {}
        note = r.error or ""
        if r.gaps:
            note = (note + f" | {len(r.gaps)} gaps").strip(" |")
        print(f"{r.asset:<9} {r.timeframe:<4} {'y' if r.ok else 'N':<3} "
              f"{r.fetched:>6} {sr.get('inserted', 0):>6} {sr.get('updated', 0):>6} "
              f"{sr.get('rejected', 0):>5} {cov.get('count', 0):>7}  {note}")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="TradeLogger historical OHLCV ingestion (Phase 69)")
    p.add_argument("--asset", help="single canonical symbol, e.g. XAUUSD")
    p.add_argument("--timeframe", help="single timeframe, e.g. 1d")
    p.add_argument("--universe", action="store_true", help="ingest the whole research universe")
    p.add_argument("--timeframes", default="1d,1h,4h", help="comma list for --universe")
    p.add_argument("--incremental", action="store_true", help="only fetch since last stored candle")
    p.add_argument("--provider", help="override HISTORICAL_OHLCV_PROVIDER (e.g. mt5, yfinance)")
    args = p.parse_args(argv)

    store.register_with_phase68()
    if (args.provider or os.getenv("HISTORICAL_OHLCV_PROVIDER") or "").strip().lower() == "mt5":
        import mt5_provider  # registers itself

    if args.universe:
        tfs = [t.strip().lower() for t in args.timeframes.split(",") if t.strip()]
        results = ingest_universe(tfs, incremental=args.incremental, provider=args.provider)
    elif args.asset and args.timeframe:
        results = [ingest(args.asset, args.timeframe, incremental=args.incremental,
                          provider=args.provider)]
    else:
        p.error("supply --universe, or both --asset and --timeframe")
        return 2

    _print_report(results)
    ok = all(r.ok for r in results)
    print(f"\n{'ALL OK' if ok else 'SOME FAILURES'} — {sum(1 for r in results if r.ok)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
