"""
TradeLogger Phase 62 — Application Performance Profiler & UX Latency Engine
===========================================================================
Institutional performance profiling, interaction latency tracking, and cache
telemetry system. Measures server-side execution breakdown, user interaction
timings, P50/P95/P99 latency metrics, and cache efficiency.

Strict Governance:
- Strategy Contract SHA-256: 7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76 (Frozen)
- Historical Holdout Baseline: N = 82, E[R] = +0.637R, WR = 58.6%, PF = 2.52 (Locked & Unpooled)
- Dataset Isolation: IDs_hist ∩ IDs_paper = ∅, IDs_hist ∩ IDs_shadow = ∅
- Live Safety: LIVE_AUTOMATION_ENABLED = False, LIVE_BROKER_TRANSMISSION = 'BLOCKED' (Fail-Closed)
"""

import time
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd


PROFILER_VERSION = "1.0.0"


# -----------------------------------------------------------------------------
# 1. PERFORMANCE TARGET MATRIX SPECIFICATION (PHASE 62 PART 3)
# -----------------------------------------------------------------------------

PERFORMANCE_TARGETS_MS: Dict[str, float] = {
    "ZONE_SWITCH": 300.0,
    "TAB_SWITCH": 300.0,
    "ASSET_SWITCH": 300.0,
    "TIMEFRAME_SWITCH": 300.0,
    "WATCHLIST_FILTER": 200.0,
    "LAYOUT_SWITCH": 300.0,
    "COMMAND_PALETTE": 100.0,
    "KEYBOARD_SHORTCUT": 300.0,
    "MARKET_INTELLIGENCE_CACHED": 300.0,
    "ASSET_DEEP_DIVE_CACHED": 300.0,
    "FORWARD_EVIDENCE_CACHED": 500.0,
    "COLD_INTELLIGENCE_LOAD": 1500.0,
    "INITIAL_PAGE_LOAD": 2000.0,
}


# -----------------------------------------------------------------------------
# 2. CACHE TELEMETRY TRACKER
# -----------------------------------------------------------------------------

class CacheTelemetryEntry:
    """
    Tracks runtime statistics for a named in-memory cache.
    """
    def __init__(self, name: str, ttl_sec: float = 60.0):
        self.name = name
        self.ttl_sec = ttl_sec
        self.hits: int = 0
        self.misses: int = 0
        self.invalidations: int = 0
        self.total_hit_latency_ms: float = 0.0
        self.total_miss_latency_ms: float = 0.0
        self.current_size: int = 0
        self._lock = threading.Lock()

    def record_hit(self, latency_ms: float = 0.0):
        with self._lock:
            self.hits += 1
            self.total_hit_latency_ms += latency_ms

    def record_miss(self, latency_ms: float = 0.0, new_size: Optional[int] = None):
        with self._lock:
            self.misses += 1
            self.total_miss_latency_ms += latency_ms
            if new_size is not None:
                self.current_size = new_size

    def record_invalidation(self, count: int = 1):
        with self._lock:
            self.invalidations += count
            self.current_size = max(0, self.current_size - count)

    def set_size(self, size: int):
        with self._lock:
            self.current_size = max(0, size)

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate_pct(self) -> float:
        total = self.total_requests
        return (self.hits / total * 100.0) if total > 0 else 100.0

    @property
    def avg_hit_latency_ms(self) -> float:
        return (self.total_hit_latency_ms / self.hits) if self.hits > 0 else 0.0

    @property
    def avg_miss_latency_ms(self) -> float:
        return (self.total_miss_latency_ms / self.misses) if self.misses > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "cache_name": self.name,
                "hits": self.hits,
                "misses": self.misses,
                "total_requests": self.total_requests,
                "hit_rate_pct": round(self.hit_rate_pct, 2),
                "avg_hit_latency_ms": round(self.avg_hit_latency_ms, 3),
                "avg_miss_latency_ms": round(self.avg_miss_latency_ms, 3),
                "invalidations": self.invalidations,
                "current_size": self.current_size,
                "ttl_sec": self.ttl_sec
            }


# -----------------------------------------------------------------------------
# 3. APPLICATION PERFORMANCE PROFILER SINGLETON
# -----------------------------------------------------------------------------

class ApplicationPerformanceProfiler:
    """
    Thread-safe master profiler for server-side breakdown, interaction tracking,
    and cache observability.
    """
    _instance: Optional["ApplicationPerformanceProfiler"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ApplicationPerformanceProfiler, cls).__new__(cls)
                cls._instance._init_profiler()
            return cls._instance

    def _init_profiler(self):
        self._section_timings: Dict[str, List[float]] = {}
        self._interaction_timings: Dict[str, List[float]] = {}
        self._cache_registries: Dict[str, CacheTelemetryEntry] = {}
        self._rerun_history: List[Dict[str, Any]] = []
        self._active_rerun_start: Optional[float] = None
        self._active_rerun_sections: Dict[str, float] = {}
        self._state_lock = threading.Lock()

        # Initialize core caches
        for cache_name, ttl in [
            ("_PRICE_CACHE", 10.0),
            ("_TICK_CACHE", 5.0),
            ("_CANDLE_CACHE", 30.0),
            ("_WATCHLIST_CACHE", 10.0),
            ("_SCAN_CACHE", 60.0),
            ("_REGIME_CACHE", 60.0),
            ("_AGGREGATOR_CACHE", 60.0),
            ("_PROFILE_CACHE", 120.0),
            ("_YF_TECH_CACHE", 60.0),
            ("_HEATMAP_CACHE", 120.0),
            ("_DB_QUERY_CACHE", 15.0)
        ]:
            self.register_cache(cache_name, ttl_sec=ttl)

    # -------------------------------------------------------------------------
    # Server-Side Timing Instrumentation
    # -------------------------------------------------------------------------

    def start_rerun(self) -> float:
        """Marks the start of a Streamlit rerun cycle."""
        with self._state_lock:
            self._active_rerun_start = time.perf_counter()
            self._active_rerun_sections = {}
            return self._active_rerun_start

    def end_rerun(self) -> float:
        """Marks the completion of a Streamlit rerun cycle and records telemetry."""
        with self._state_lock:
            if self._active_rerun_start is None:
                return 0.0
            total_duration_ms = (time.perf_counter() - self._active_rerun_start) * 1000.0
            
            # Record in rerun history
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_duration_ms": round(total_duration_ms, 2),
                "sections": dict(self._active_rerun_sections)
            }
            self._rerun_history.append(entry)
            if len(self._rerun_history) > 500:
                self._rerun_history.pop(0)

            # Record in aggregate section timings
            self._record_section_raw("total_rerun", total_duration_ms)
            self._active_rerun_start = None
            return total_duration_ms

    def _record_section_raw(self, section: str, duration_ms: float):
        if section not in self._section_timings:
            self._section_timings[section] = []
        self._section_timings[section].append(duration_ms)
        if len(self._section_timings[section]) > 1000:
            self._section_timings[section].pop(0)

    def record_section_timing(self, section: str, duration_ms: float):
        """Records the execution time of a specific application section."""
        with self._state_lock:
            self._record_section_raw(section, duration_ms)
            if self._active_rerun_sections is not None:
                self._active_rerun_sections[section] = round(
                    self._active_rerun_sections.get(section, 0.0) + duration_ms, 3
                )

    @contextmanager
    def profile_block(self, section_name: str):
        """Context manager to measure execution latency of a code block."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            self.record_section_timing(section_name, dt_ms)

    # -------------------------------------------------------------------------
    # User Interaction Timing Instrumentation
    # -------------------------------------------------------------------------

    def record_interaction(self, interaction_type: str, duration_ms: float):
        """Records end-to-end user-perceived interaction latency."""
        with self._state_lock:
            if interaction_type not in self._interaction_timings:
                self._interaction_timings[interaction_type] = []
            self._interaction_timings[interaction_type].append(duration_ms)
            if len(self._interaction_timings[interaction_type]) > 1000:
                self._interaction_timings[interaction_type].pop(0)

    @contextmanager
    def measure_interaction(self, interaction_type: str):
        """Context manager to measure end-to-end user interaction latency."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            self.record_interaction(interaction_type, dt_ms)

    # -------------------------------------------------------------------------
    # Cache Telemetry Management
    # -------------------------------------------------------------------------

    def register_cache(self, name: str, ttl_sec: float = 60.0) -> CacheTelemetryEntry:
        with self._state_lock:
            if name not in self._cache_registries:
                self._cache_registries[name] = CacheTelemetryEntry(name, ttl_sec=ttl_sec)
            return self._cache_registries[name]

    def get_cache_telemetry(self, name: str) -> Optional[CacheTelemetryEntry]:
        with self._state_lock:
            return self._cache_registries.get(name)

    def record_cache_hit(self, name: str, latency_ms: float = 0.0):
        entry = self.get_cache_telemetry(name)
        if entry is None:
            entry = self.register_cache(name)
        entry.record_hit(latency_ms)

    def record_cache_miss(self, name: str, latency_ms: float = 0.0, new_size: Optional[int] = None):
        entry = self.get_cache_telemetry(name)
        if entry is None:
            entry = self.register_cache(name)
        entry.record_miss(latency_ms, new_size=new_size)

    def record_cache_invalidation(self, name: str, count: int = 1):
        entry = self.get_cache_telemetry(name)
        if entry:
            entry.record_invalidation(count)

    def get_all_cache_stats(self) -> List[Dict[str, Any]]:
        with self._state_lock:
            return [entry.to_dict() for entry in self._cache_registries.values()]

    def get_overall_cache_hit_rate(self) -> float:
        with self._state_lock:
            total_hits = sum(e.hits for e in self._cache_registries.values())
            total_misses = sum(e.misses for e in self._cache_registries.values())
            total = total_hits + total_misses
            return (total_hits / total * 100.0) if total > 0 else 100.0

    # -------------------------------------------------------------------------
    # Percentile Latency Statistics (P50, P95, P99)
    # -------------------------------------------------------------------------

    @staticmethod
    def calculate_percentiles(samples: List[float]) -> Dict[str, float]:
        """Calculates P50, P95, P99, min, max, mean from sample list."""
        if not samples:
            return {
                "count": 0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "mean": 0.0,
                "min": 0.0,
                "max": 0.0
            }
        arr = np.array(samples)
        return {
            "count": len(samples),
            "p50": round(float(np.percentile(arr, 50)), 2),
            "p95": round(float(np.percentile(arr, 95)), 2),
            "p99": round(float(np.percentile(arr, 99)), 2),
            "mean": round(float(np.mean(arr)), 2),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2)
        }

    def get_interaction_stats(self) -> Dict[str, Dict[str, Any]]:
        """Returns comprehensive P50/P95/P99 latency stats for all interaction types."""
        with self._state_lock:
            res = {}
            for k, samples in self._interaction_timings.items():
                stats = self.calculate_percentiles(samples)
                target = PERFORMANCE_TARGETS_MS.get(k, 300.0)
                stats["target_ms"] = target
                
                # Determine status
                p95 = stats["p95"]
                if p95 <= target:
                    status = "PASS"
                elif p95 <= target * 1.5:
                    status = "WARNING"
                else:
                    status = "FAIL"
                stats["status"] = status
                res[k] = stats
            return res

    def get_section_stats(self) -> Dict[str, Dict[str, Any]]:
        """Returns P50/P95/P99 latency stats for server-side breakdown sections."""
        with self._state_lock:
            res = {}
            for k, samples in self._section_timings.items():
                res[k] = self.calculate_percentiles(samples)
            return res

    # -------------------------------------------------------------------------
    # UX Performance Score (0 - 100)
    # -------------------------------------------------------------------------

    def calculate_ux_performance_score(self) -> Dict[str, Any]:
        """
        Calculates holistic UX Performance Score (0-100) based on:
        - Median & P95 interaction responsiveness (40% weight)
        - Cache efficiency (25% weight)
        - Database query efficiency (15% weight)
        - Rerun efficiency (20% weight)
        """
        interaction_stats = self.get_interaction_stats()
        cache_hit_rate = self.get_overall_cache_hit_rate()
        
        # 1. Responsiveness Score (40 pts)
        if interaction_stats:
            pass_count = sum(1 for s in interaction_stats.values() if s["status"] == "PASS")
            warn_count = sum(1 for s in interaction_stats.values() if s["status"] == "WARNING")
            total = len(interaction_stats)
            resp_ratio = ((pass_count * 1.0) + (warn_count * 0.5)) / max(1, total)
            resp_score = resp_ratio * 40.0
        else:
            resp_score = 38.0  # Default healthy baseline

        # 2. Cache Score (25 pts)
        cache_score = (cache_hit_rate / 100.0) * 25.0

        # 3. Database Score (15 pts)
        db_stats = self._section_timings.get("database_queries", [])
        if db_stats:
            avg_db_ms = np.mean(db_stats)
            if avg_db_ms < 10.0:
                db_score = 15.0
            elif avg_db_ms < 30.0:
                db_score = 12.0
            elif avg_db_ms < 60.0:
                db_score = 8.0
            else:
                db_score = 4.0
        else:
            db_score = 15.0

        # 4. Rerun Efficiency Score (20 pts)
        rerun_stats = self._section_timings.get("total_rerun", [])
        if rerun_stats:
            p95_rerun = np.percentile(rerun_stats, 95)
            if p95_rerun < 300.0:
                rerun_score = 20.0
            elif p95_rerun < 600.0:
                rerun_score = 15.0
            elif p95_rerun < 1000.0:
                rerun_score = 10.0
            else:
                rerun_score = 5.0
        else:
            rerun_score = 19.0

        total_score = min(100, max(0, int(round(resp_score + cache_score + db_score + rerun_score))))
        
        if total_score >= 90:
            rating = "EXCELLENT"
            color = "#00ffcc"
        elif total_score >= 75:
            rating = "GOOD"
            color = "#bef264"
        elif total_score >= 60:
            rating = "FAIR"
            color = "#f59e0b"
        else:
            rating = "POOR"
            color = "#ef4444"

        # Extract P50, P95, P99 across all interactions
        all_samples = []
        for s in self._interaction_timings.values():
            all_samples.extend(s)
        overall_p = self.calculate_percentiles(all_samples)

        return {
            "score": total_score,
            "rating": rating,
            "color": color,
            "p50_ms": overall_p["p50"],
            "p95_ms": overall_p["p95"],
            "p99_ms": overall_p["p99"],
            "cache_hit_rate_pct": round(cache_hit_rate, 1),
            "breakdown": {
                "responsiveness_pts": round(resp_score, 1),
                "cache_pts": round(cache_score, 1),
                "database_pts": round(db_score, 1),
                "rerun_pts": round(rerun_score, 1)
            }
        }

    def reset_telemetry(self):
        """Resets in-memory telemetry for clean benchmark runs."""
        with self._state_lock:
            self._section_timings.clear()
            self._interaction_timings.clear()
            self._rerun_history.clear()
            for c in self._cache_registries.values():
                c.hits = 0
                c.misses = 0
                c.invalidations = 0
                c.total_hit_latency_ms = 0.0
                c.total_miss_latency_ms = 0.0


# Module-level convenience functions
_profiler = ApplicationPerformanceProfiler()

def get_profiler() -> ApplicationPerformanceProfiler:
    return _profiler

def profile_block(name: str):
    return _profiler.profile_block(name)

def measure_interaction(interaction_type: str):
    return _profiler.measure_interaction(interaction_type)

def record_cache_hit(name: str, latency_ms: float = 0.0):
    _profiler.record_cache_hit(name, latency_ms)

def record_cache_miss(name: str, latency_ms: float = 0.0, new_size: Optional[int] = None):
    _profiler.record_cache_miss(name, latency_ms, new_size)

def record_cache_invalidation(name: str, count: int = 1):
    _profiler.record_cache_invalidation(name, count)
