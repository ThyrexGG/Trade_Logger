"""
TradeLogger — Read-only API performance baseline
================================================
Measures the *backend* cost of every navigation-relevant endpoint via an
in-process FastAPI TestClient (so network latency to the user is excluded, but
the DB round-trip, computation and cache behaviour are all real).

Run:   python performance_benchmark.py [--json out.json] [--rounds N]

This is a diagnostic, not a test. It changes nothing, imports no execution
module, and honours the same safety invariants as the app.

Invariants (unchanged by this script):
- LIVE_AUTOMATION_ENABLED = False, LIVE_BROKER_TRANSMISSION = "BLOCKED"
- No lookahead: it only calls read endpoints, which apply their own as_of rules.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone

# Navigation-relevant read endpoints, grouped by the page/area they back.
ENDPOINTS = [
    ("shell",        "GET", "/api/health"),
    ("workspace",    "GET", "/api/watchlist"),
    ("workspace",    "GET", "/api/market/snapshot/XAUUSD"),
    ("workspace",    "GET", "/api/positions"),
    ("command",      "GET", "/api/command-center/overview"),
    ("analytics",    "GET", "/api/analytics/performance"),
    ("intelligence", "GET", "/api/intelligence/summary"),
    ("intelligence", "GET", "/api/intelligence/opportunity-map"),
    ("intelligence", "GET", "/api/intelligence/heatmap"),
    ("macro",        "GET", "/api/macro/overview"),
    ("macro",        "GET", "/api/macro/currencies"),
    ("macro",        "GET", "/api/macro/events"),
    ("macro",        "GET", "/api/macro/assets"),
    ("research",     "GET", "/api/research/strategy"),
    ("evidence",     "GET", "/api/forward-evidence/state"),
    ("operations",   "GET", "/api/operations/journal"),
    ("operations",   "GET", "/api/operations/audit"),
    ("operations",   "GET", "/api/operations/system"),
    ("alerts",       "GET", "/api/alerts"),
    ("ai",           "GET", "/api/ai/status"),
]


def _pct(values, p):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def run(rounds: int = 12) -> dict:
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    results = []

    for area, method, path in ENDPOINTS:
        # cold
        t0 = time.perf_counter()
        r0 = client.request(method, path)
        cold_ms = (time.perf_counter() - t0) * 1000.0

        warm = []
        for _ in range(rounds):
            t0 = time.perf_counter()
            client.request(method, path)
            warm.append((time.perf_counter() - t0) * 1000.0)

        results.append({
            "area": area,
            "endpoint": path,
            "status": r0.status_code,
            "cold_ms": round(cold_ms, 1),
            "warm_p50_ms": round(statistics.median(warm), 1),
            "warm_p95_ms": round(_pct(warm, 95), 1),
            "warm_p99_ms": round(_pct(warm, 99), 1),
            "warm_min_ms": round(min(warm), 1),
            "rounds": rounds,
        })

    slow = [r for r in results if r["warm_p50_ms"] >= 100.0]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "in-process TestClient — excludes user network latency, includes DB round-trip + compute + cache",
        "rounds": rounds,
        "endpoints": results,
        "slow_endpoints_warm_p50_ge_100ms": sorted(slow, key=lambda r: -r["warm_p50_ms"]),
    }


def _print(report: dict) -> None:
    print(f"\nTradeLogger API performance baseline  ({report['generated_at']})")
    print(f"{report['note']}\n")
    print(f"{'area':13} {'endpoint':38} {'cold':>8} {'p50':>8} {'p95':>8} {'p99':>8}")
    print("-" * 88)
    for r in report["endpoints"]:
        print(f"{r['area']:13} {r['endpoint']:38} {r['cold_ms']:8.0f} {r['warm_p50_ms']:8.1f} "
              f"{r['warm_p95_ms']:8.1f} {r['warm_p99_ms']:8.1f}")
    slow = report["slow_endpoints_warm_p50_ge_100ms"]
    if slow:
        print(f"\nWARM p50 >= 100 ms  ({len(slow)}):")
        for r in slow:
            print(f"  {r['endpoint']:38} {r['warm_p50_ms']:8.1f} ms")
    else:
        print("\nAll warm p50 latencies < 100 ms.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="write the full report to this path")
    ap.add_argument("--rounds", type=int, default=12)
    args = ap.parse_args()

    report = run(rounds=args.rounds)
    _print(report)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"\nwrote {args.json}")
    sys.exit(0)
