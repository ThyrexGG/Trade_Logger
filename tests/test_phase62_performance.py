# -*- coding: utf-8 -*-
"""
Phase 62 - Test Server-Side Performance Profiling, Percentile Engine & UX Score
"""
import pytest
import time
from application_performance_profiler import (
    ApplicationPerformanceProfiler,
    get_profiler,
    profile_block,
    measure_interaction,
    PERFORMANCE_TARGETS_MS
)


def test_profiler_singleton_and_init():
    """Verify profiler singleton instance and registered cache inventory."""
    profiler = get_profiler()
    assert profiler is not None
    assert isinstance(profiler, ApplicationPerformanceProfiler)
    assert len(profiler._cache_registries) >= 6


def test_profile_block_context_manager():
    """Verify profile_block accurately measures code execution duration."""
    profiler = get_profiler()
    with profile_block("test_custom_block"):
        time.sleep(0.01)  # 10ms

    stats = profiler.get_section_stats()
    assert "test_custom_block" in stats
    assert stats["test_custom_block"]["count"] >= 1
    assert stats["test_custom_block"]["p50"] >= 5.0  # at least ~5ms recorded


def test_measure_interaction_and_percentiles():
    """Verify measure_interaction records samples and calculates P50, P95, P99."""
    profiler = get_profiler()
    for _ in range(20):
        with measure_interaction("ZONE_SWITCH"):
            time.sleep(0.001)  # 1ms

    stats = profiler.get_interaction_stats()
    assert "ZONE_SWITCH" in stats
    s = stats["ZONE_SWITCH"]
    assert s["count"] >= 20
    assert s["p50"] > 0
    assert s["p95"] >= s["p50"]
    assert s["p99"] >= s["p95"]
    assert s["target_ms"] == PERFORMANCE_TARGETS_MS["ZONE_SWITCH"]
    assert s["status"] in ["PASS", "WARNING", "FAIL"]


def test_ux_performance_score_calculation():
    """Verify UX performance score calculation produces a valid 0-100 score and rating."""
    profiler = get_profiler()
    score_data = profiler.calculate_ux_performance_score()
    assert 0 <= score_data["score"] <= 100
    assert score_data["rating"] in ["EXCELLENT", "GOOD", "FAIR", "POOR"]
    assert score_data["color"].startswith("#")
    assert "breakdown" in score_data
    assert "responsiveness_pts" in score_data["breakdown"]


def test_rerun_lifecycle_recording():
    """Verify rerun lifecycle start, end, and history tracking."""
    profiler = get_profiler()
    profiler.start_rerun()
    with profile_block("zone_render"):
        time.sleep(0.002)
    dt = profiler.end_rerun()
    assert dt >= 1.0
    assert len(profiler._rerun_history) >= 1
    last = profiler._rerun_history[-1]
    assert "total_duration_ms" in last
    assert "sections" in last


def test_reset_telemetry_clears_metrics():
    """Verify reset_telemetry cleans up all sample buckets."""
    profiler = get_profiler()
    with profile_block("temp_sec"):
        pass
    profiler.reset_telemetry()
    assert len(profiler._section_timings) == 0
    assert len(profiler._interaction_timings) == 0
    assert len(profiler._rerun_history) == 0
