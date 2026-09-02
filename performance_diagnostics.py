"""
TradeLogger Phase 59 — Performance Observability & Diagnostic Engine
====================================================================
Provides lightweight, zero-overhead performance instrumentation, timing metrics,
cache hit/miss tracking, and calculation reuse telemetry.

Strict Invariants:
- Strategy Contract SHA-256: 7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76
- Historical Holdout Baseline: N = 82, E[R] = +0.637R, WR = 58.6%, PF = 2.52 (Locked & Unpooled)
- Live Safety: LIVE_AUTOMATION_ENABLED = False, LIVE_BROKER_TRANSMISSION = 'BLOCKED'
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field

PERFORMANCE_ENGINE_VERSION = "1.0.0"

_LOCK = threading.Lock()
_METRICS: Dict[str, Dict[str, Any]] = {}
_CACHE_STATS: Dict[str, Dict[str, int]] = {
    "market_data": {"hits": 0, "misses": 0},
    "market_scanner": {"hits": 0, "misses": 0},
    "regime_engine": {"hits": 0, "misses": 0},
    "command_center": {"hits": 0, "misses": 0},
    "asset_profiles": {"hits": 0, "misses": 0}
}


class PerformanceDiagnostics:
    """
    Centralized lightweight diagnostic and telemetry collector.
    """

    @classmethod
    def record_duration(cls, component: str, duration_ms: float) -> None:
        """Records the execution duration of a component."""
        with _LOCK:
            if component not in _METRICS:
                _METRICS[component] = {
                    "count": 0,
                    "total_ms": 0.0,
                    "min_ms": float("inf"),
                    "max_ms": 0.0,
                    "last_ms": 0.0,
                    "last_timestamp": ""
                }
            m = _METRICS[component]
            m["count"] += 1
            m["total_ms"] += duration_ms
            m["min_ms"] = min(m["min_ms"], duration_ms)
            m["max_ms"] = max(m["max_ms"], duration_ms)
            m["last_ms"] = duration_ms
            m["last_timestamp"] = datetime.now(timezone.utc).isoformat()

    @classmethod
    def record_cache_hit(cls, cache_name: str) -> None:
        """Increments cache hit counter."""
        with _LOCK:
            if cache_name not in _CACHE_STATS:
                _CACHE_STATS[cache_name] = {"hits": 0, "misses": 0}
            _CACHE_STATS[cache_name]["hits"] += 1

    @classmethod
    def record_cache_miss(cls, cache_name: str) -> None:
        """Increments cache miss counter."""
        with _LOCK:
            if cache_name not in _CACHE_STATS:
                _CACHE_STATS[cache_name] = {"hits": 0, "misses": 0}
            _CACHE_STATS[cache_name]["misses"] += 1

    @classmethod
    def get_metrics_summary(cls) -> Dict[str, Any]:
        """Returns a snapshot of performance metrics."""
        with _LOCK:
            summary = {}
            for comp, m in _METRICS.items():
                avg_ms = round(m["total_ms"] / m["count"], 2) if m["count"] > 0 else 0.0
                summary[comp] = {
                    "count": m["count"],
                    "avg_ms": avg_ms,
                    "min_ms": round(m["min_ms"], 2) if m["min_ms"] != float("inf") else 0.0,
                    "max_ms": round(m["max_ms"], 2),
                    "last_ms": round(m["last_ms"], 2),
                    "last_timestamp": m["last_timestamp"]
                }
            return {
                "components": summary,
                "cache_stats": {
                    k: {
                        "hits": v["hits"],
                        "misses": v["misses"],
                        "hit_ratio_pct": round((v["hits"] / (v["hits"] + v["misses"])) * 100.0, 1) if (v["hits"] + v["misses"]) > 0 else 0.0
                    }
                    for k, v in _CACHE_STATS.items()
                },
                "version": PERFORMANCE_ENGINE_VERSION,
                "snapshot_time": datetime.now(timezone.utc).isoformat()
            }

    @classmethod
    def reset(cls) -> None:
        """Resets all metrics for clean profiling passes."""
        with _LOCK:
            _METRICS.clear()
            for k in _CACHE_STATS:
                _CACHE_STATS[k]["hits"] = 0
                _CACHE_STATS[k]["misses"] = 0


class ProfileTimer:
    """
    Context manager for zero-boilerplate performance timing.
    Usage:
        with ProfileTimer("market_scanner"):
            records = MarketScannerEngine.scan_universe()
    """
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.t0 = 0.0
        self.duration_ms = 0.0

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.perf_counter() - self.t0) * 1000.0
        PerformanceDiagnostics.record_duration(self.component_name, self.duration_ms)


# Phase 62 Re-exports & Helper
try:
    import application_performance_profiler
    render_performance_command_center = application_performance_profiler.render_performance_command_center
    get_profiler = application_performance_profiler.get_profiler
except ImportError:
    pass
