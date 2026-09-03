# -*- coding: utf-8 -*-
"""
Historical data coverage report (Phase 73, §8).

Composes the persistent-store coverage (``historical_data_store``) with the
provider capability layer (``historical_provider``) into one machine- and
human-readable report per ``instrument x timeframe``.

Sufficiency states:
    SUFFICIENT           — enough real, contiguous data to research this TF
    PARTIAL              — real data present but below the sufficiency bar
    INSUFFICIENT_DATA    — provider itself cannot deliver enough depth
    PROVIDER_UNAVAILABLE — provider outage / not configured (NOT the same as INSUFFICIENT_DATA)
    NO_DATA              — nothing stored and no attempt recorded
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import historical_data_store as store
import historical_provider as provider
import research_universe

TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")


def _row(asset: str, timeframe: str) -> Dict[str, Any]:
    asset = research_universe.normalise(asset)
    cov = store.get_coverage(asset, timeframe)
    cap = provider.get_provider().capability(asset, timeframe)
    rule = research_universe.sufficiency_rule(timeframe)
    suf = store.data_sufficiency(asset, timeframe)
    gap = suf.get("gap_analysis", {})

    have = cov.count
    need = rule.min_bars if rule else None
    span_days = None
    if cov.first_open_time and cov.last_open_time:
        span_days = round((cov.last_open_time - cov.first_open_time) / 86400.0, 1)

    if have == 0:
        if cap.state in (provider.ProviderCapabilityState.PROVIDER_UNAVAILABLE,
                         provider.ProviderCapabilityState.NOT_CONFIGURED):
            state = "PROVIDER_UNAVAILABLE"
        elif cap.state == provider.ProviderCapabilityState.INSUFFICIENT_HISTORICAL_DEPTH:
            # nothing stored AND the wired provider can never reach the bar
            state = "INSUFFICIENT_DATA"
        else:
            state = "NO_DATA"
    elif suf["state"] == "AVAILABLE":
        state = "SUFFICIENT"
    else:
        # real data present but below the sufficiency bar — usable for an
        # explicitly-labelled exploratory read, never for validation
        state = "PARTIAL"

    return {
        "instrument": asset,
        "timeframe": timeframe,
        "earliest": cov.first_open_time and datetime.fromtimestamp(
            cov.first_open_time, tz=timezone.utc).isoformat(),
        "latest": cov.last_open_time and datetime.fromtimestamp(
            cov.last_open_time, tz=timezone.utc).isoformat(),
        "candles": have,
        "expected_min_candles": need,
        "span_days": span_days,
        "anomalous_gaps": gap.get("anomalous_gaps", 0),
        "largest_anomalous_bars": gap.get("largest_anomalous_bars", 0),
        "weekend_gaps": gap.get("weekend_gaps", 0),
        "quality_rejections_note": (
            "rejections tracked per-ingest in historical_ingestion_log; "
            f"{cov.suspect} candles flagged 'suspect' in store"),
        "provider": cap.provider,
        "provider_state": cap.state,
        "provider_reason": cap.reason,
        "provider_limitations": cap.limitations,
        "native_or_derived": "derived (resampled from 1h)" if timeframe == "4h" else "native",
        "sufficiency_state": state,
        "last_ingestion": _last_ingestion(asset, timeframe),
    }


def _last_ingestion(asset: str, timeframe: str):
    import database
    try:
        database.init_db()
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            ph = database.get_sql_placeholder(conn)
            cur.execute(
                f"SELECT ran_at FROM historical_ingestion_log WHERE asset={ph} AND timeframe={ph} "
                f"ORDER BY ran_at DESC LIMIT 1", (asset, timeframe))
            r = cur.fetchone()
            return r[0] if r else None
        finally:
            conn.close()
    except Exception:
        return None


def coverage_report(timeframes=TIMEFRAMES) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for inst in research_universe.universe():
        for tf in timeframes:
            rows.append(_row(inst.symbol, tf))
    summary: Dict[str, int] = {}
    for r in rows:
        summary[r["sufficiency_state"]] = summary.get(r["sufficiency_state"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider.get_provider().name,
        "timeframes": list(timeframes),
        "rows": rows,
        "summary": summary,
        "note": (
            "SUFFICIENT means enough real contiguous data to research the timeframe. "
            "INSUFFICIENT_DATA means the wired provider cannot reach the bar (a data-"
            "availability limit, not a provider outage). PROVIDER_UNAVAILABLE is an outage / "
            "unconfigured vendor. No timeframe is 'available' merely because the schema supports it."
        ),
    }


def human_report(timeframes=TIMEFRAMES) -> str:
    rep = coverage_report(timeframes)
    lines = [f"HISTORICAL DATA COVERAGE  (provider: {rep['provider']}, {rep['generated_at'][:19]}Z)",
             "-" * 92,
             f"{'INSTRUMENT':<10} {'TF':<4} {'CANDLES':>8} {'SPAN(d)':>8} {'STATE':<20} NOTE"]
    for r in rep["rows"]:
        note = r["provider_reason"] or (r["provider_limitations"][0] if r["provider_limitations"] else "")
        lines.append(f"{r['instrument']:<10} {r['timeframe']:<4} {r['candles']:>8} "
                     f"{str(r['span_days'] or '-'):>8} {r['sufficiency_state']:<20} {note[:44]}")
    lines.append("-" * 92)
    lines.append("summary: " + ", ".join(f"{k}={v}" for k, v in sorted(rep["summary"].items())))
    return "\n".join(lines)


def main(_argv=None) -> int:  # pragma: no cover
    print(human_report())
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = ["TIMEFRAMES", "coverage_report", "human_report"]
