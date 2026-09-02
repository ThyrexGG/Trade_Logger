# -*- coding: utf-8 -*-
"""
Phase 62 - Test In-Memory Cache TTL, Thread Safety & Telemetry Integrity
"""
import pytest
import time
import threading
from application_performance_profiler import (
    get_profiler,
    record_cache_hit,
    record_cache_miss,
    record_cache_invalidation
)


def test_cache_telemetry_hit_miss_recording():
    """Verify cache telemetry accurately records hits, misses, and hit rate %."""
    profiler = get_profiler()
    profiler.register_cache("_TEST_CUSTOM_CACHE", ttl_sec=30.0)

    record_cache_miss("_TEST_CUSTOM_CACHE", latency_ms=12.5)
    for _ in range(9):
        record_cache_hit("_TEST_CUSTOM_CACHE", latency_ms=0.05)

    entry = profiler.get_cache_telemetry("_TEST_CUSTOM_CACHE")
    assert entry is not None
    assert entry.hits == 9
    assert entry.misses == 1
    assert entry.total_requests == 10
    assert entry.hit_rate_pct == 90.0
    assert entry.avg_hit_latency_ms < 0.2
    assert entry.avg_miss_latency_ms > 10.0


def test_cache_telemetry_thread_safety():
    """Verify concurrent cache telemetry recording without race conditions."""
    profiler = get_profiler()
    profiler.register_cache("_TEST_THREAD_CACHE", ttl_sec=60.0)

    def worker():
        for _ in range(100):
            record_cache_hit("_TEST_THREAD_CACHE", latency_ms=0.01)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    entry = profiler.get_cache_telemetry("_TEST_THREAD_CACHE")
    assert entry.hits >= 1000


def test_cache_invalidation_tracking():
    """Verify record_cache_invalidation updates count."""
    profiler = get_profiler()
    entry = profiler.register_cache("_TEST_INVAL_CACHE", ttl_sec=45.0)
    entry.set_size(10)
    record_cache_invalidation("_TEST_INVAL_CACHE", count=3)
    assert entry.invalidations >= 3
    assert entry.current_size <= 7


def test_all_core_caches_registered():
    """Verify that all core caches are registered upon profiler initialization."""
    profiler = get_profiler()
    all_stats = profiler.get_all_cache_stats()
    names = [s["cache_name"] for s in all_stats]
    assert "_PRICE_CACHE" in names
    assert "_SCAN_CACHE" in names
    assert "_REGIME_CACHE" in names
