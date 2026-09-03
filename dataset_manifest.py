# -*- coding: utf-8 -*-
"""
Historical dataset manifest (Phase 74, §9/§10/§14).

Every native research run must be able to identify *exactly* which dataset it
used: which provider, which vendor symbol, which date range, how many candles,
what quality. This module builds and persists that manifest, and hashes the
identifying metadata so a run is reproducible.

Provider provenance stays visible: `historical_candles.source` records the
provider per row; the manifest reports the distinct sources per series and never
silently merges two vendors on the same key.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import historical_data_store as store
import research_universe

ARTIFACT_PREFIX = "dataset_manifest"

# vendor symbol / asset-type notes per provider (§13 — GC=F futures vs broker spot)
_PROVIDER_SYMBOL_NOTE = {
    "yahoo": {"XAUUSD": ("GC=F", "GOLD_FUTURES_PROXY",
                         "Yahoo COMEX gold front-month future used as an XAUUSD proxy — "
                         "NOT spot; different session, roll and basis")},
    "mt5": {"*": (None, "BROKER_SPOT",
                  "broker spot feed (MT5 terminal) — personal-use license, do not redistribute")},
}


@dataclass
class SeriesEntry:
    timeframe: str
    provider: str
    vendor_symbol: Optional[str]
    asset_type: str
    earliest: Optional[str]
    latest: Optional[str]
    candle_count: int
    span_days: Optional[float]
    coverage_ratio: Optional[float]
    anomalous_gaps: int
    suspect_candles: int
    sufficiency_state: str
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class DatasetManifest:
    dataset_id: str
    canonical_symbol: str
    generated_at: str
    providers: List[str]
    series: List[Dict[str, Any]]
    content_hash: str
    licensing_note: str
    holdout_isolation: str = (
        "This dataset is independent of the frozen Gold holdout (N=82). The holdout "
        "is never read by any code that builds or consumes this manifest."
    )

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _symbol_note(provider: str, canonical: str):
    table = _PROVIDER_SYMBOL_NOTE.get(provider, {})
    return table.get(canonical) or table.get("*") or (canonical, "SPOT", "")


def build_manifest(canonical_symbol: str,
                   timeframes=("1m", "5m", "15m", "1h", "4h", "1d")) -> DatasetManifest:
    sym = research_universe.normalise(canonical_symbol)
    series: List[SeriesEntry] = []
    providers: set = set()

    for tf in timeframes:
        srcs = store.series_sources(sym, tf)
        if not srcs:
            continue
        cov = store.get_coverage(sym, tf)
        gap = store.analyze_gaps(sym, tf)
        suf = store.data_sufficiency(sym, tf)
        provider = srcs[0] if len(srcs) == 1 else "+".join(srcs)
        providers.update(srcs)
        vsym, asset_type, note = _symbol_note(srcs[0] if srcs else "", sym)
        span = None
        if cov.first_open_time and cov.last_open_time:
            span = round((cov.last_open_time - cov.first_open_time) / 86400.0, 1)
        expected = cov.expected_bars or cov.count
        series.append(SeriesEntry(
            timeframe=tf, provider=provider, vendor_symbol=vsym, asset_type=asset_type,
            earliest=datetime.fromtimestamp(cov.first_open_time, tz=timezone.utc).isoformat()
            if cov.first_open_time else None,
            latest=datetime.fromtimestamp(cov.last_open_time, tz=timezone.utc).isoformat()
            if cov.last_open_time else None,
            candle_count=cov.count, span_days=span,
            coverage_ratio=round(cov.count / expected, 3) if expected else None,
            anomalous_gaps=gap.get("anomalous_gaps", 0),
            suspect_candles=cov.suspect,
            sufficiency_state=suf["state"],
            note=(note + (f" | multiple sources: {srcs}" if len(srcs) > 1 else "")),
        ))

    ident = json.dumps(
        {"symbol": sym, "series": [
            {"tf": s.timeframe, "provider": s.provider, "vsym": s.vendor_symbol,
             "first": s.earliest, "last": s.latest, "n": s.candle_count}
            for s in series]},
        sort_keys=True)
    chash = hashlib.sha256(ident.encode()).hexdigest()

    licensing = (
        "yahoo: free, personal use, redistribution restricted. "
        "mt5: broker feed via the account's own terminal — personal research use only, "
        "the underlying price data must not be redistributed. Neither vendor's raw data is "
        "committed to the repository (candles live in the configured database)."
    )

    return DatasetManifest(
        dataset_id=f"{sym}:{chash[:16]}",
        canonical_symbol=sym,
        generated_at=datetime.now(timezone.utc).isoformat(),
        providers=sorted(providers),
        series=[s.to_dict() for s in series],
        content_hash=chash,
        licensing_note=licensing,
    )


def persist(manifest: DatasetManifest) -> str:
    return store.save_artifact(f"{ARTIFACT_PREFIX}:{manifest.canonical_symbol}",
                               "dataset_manifest", manifest.to_dict())


def get_manifest(canonical_symbol: str) -> Optional[Dict[str, Any]]:
    art = store.load_artifact(f"{ARTIFACT_PREFIX}:{research_universe.normalise(canonical_symbol)}")
    return art["payload"] if art else None


def build_and_persist(canonical_symbol: str, **kw) -> DatasetManifest:
    m = build_manifest(canonical_symbol, **kw)
    persist(m)
    return m


def main(_argv=None) -> int:  # pragma: no cover
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
    m = build_and_persist(sym)
    print(f"\nDATASET MANIFEST — {m.dataset_id}")
    print(f"providers: {m.providers}")
    print(f"{'TF':<4} {'PROVIDER':<10} {'VENDOR':<8} {'TYPE':<18} {'BARS':>8} {'SPAN(d)':>8} "
          f"{'STATE':<12}")
    for s in m.series:
        print(f"{s['timeframe']:<4} {s['provider']:<10} {str(s['vendor_symbol'] or '-'):<8} "
              f"{s['asset_type']:<18} {s['candle_count']:>8} {str(s['span_days'] or '-'):>8} "
              f"{s['sufficiency_state']:<12}")
    print(f"\ncontent_hash: {m.content_hash}")
    print(f"licensing: {m.licensing_note}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = ["DatasetManifest", "SeriesEntry", "build_manifest", "persist",
           "get_manifest", "build_and_persist"]
