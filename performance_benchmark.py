"""
TradeLogger — Read-only API performance baseline
================================================
Measures the *backend* cost of every navigation-relevant endpoint via an
in-process FastAPI TestClient (so network latency to the user is excluded, but
the DB round-trip, computation and cache behaviour are all real).

Run:
    python performance_benchmark.py [--json out.json] [--rounds N]
                                    [--compare baseline.json] [--lifespan]

    --lifespan   run inside `with TestClient(app)` so the startup warm-up fires,
                 i.e. measure the cold path the deployed uvicorn process gives a
                 real user (first request already primed).

This is a diagnostic, not a test. It changes nothing, imports no execution
module, and honours the same safety invariants as the app.

Invariants (unchanged by this script):
- LIVE_AUTOMATION_ENABLED = False, LIVE_BROKER_TRANSMISSION = "BLOCKED"
- No lookahead: it only calls read endpoints, which apply their own as_of rules.
"""
from __future__ import annotations

import argparse
import contextlib
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


def _measure(client, rounds: int) -> list:
    results = []
    for area, method, path in ENDPOINTS:
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
    return results


def run(rounds: int = 12, lifespan: bool = False) -> dict:
    from fastapi.testclient import TestClient
    from api.main import app
    import database

    client = TestClient(app)
    # `with TestClient(app)` triggers the FastAPI lifespan (startup warm-up),
    # matching what a deployed uvicorn process does before it accepts traffic.
    ctx = client if lifespan else contextlib.nullcontext(client)

    with ctx:
        pool_before = database.pool_stats()
        results = _measure(client, rounds)
        pool_after = database.pool_stats()

    slow = [r for r in results if r["warm_p50_ms"] >= 100.0]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "in-process TestClient — excludes user network latency, includes DB round-trip + compute + cache",
        "rounds": rounds,
        "lifespan_warmup": lifespan,
        "endpoints": results,
        "slow_endpoints_warm_p50_ge_100ms": sorted(slow, key=lambda r: -r["warm_p50_ms"]),
        "db_pool": {
            "enabled": pool_after.get("enabled"),
            "checkouts": pool_after.get("checkouts", 0) - pool_before.get("checkouts", 0),
            "reused": pool_after.get("reused", 0) - pool_before.get("reused", 0),
            "created": pool_after.get("created", 0) - pool_before.get("created", 0),
            "pings": pool_after.get("pings", 0) - pool_before.get("pings", 0),
            "ping_failures": pool_after.get("ping_failures", 0) - pool_before.get("ping_failures", 0),
            "overflow_direct": pool_after.get("overflow_direct", 0) - pool_before.get("overflow_direct", 0),
        },
    }


def compare(before_path: str, after: dict) -> None:
    """Print a before/after warm-p50 + cold delta table from a saved baseline."""
    with open(before_path, encoding="utf-8") as fh:
        before = json.load(fh)
    b = {r["endpoint"]: r for r in before.get("endpoints", [])}
    print(f"\n{'endpoint':38} {'before p50':>11} {'after p50':>11}   "
          f"{'before cold':>11} {'after cold':>11}")
    print("-" * 88)
    for r in after["endpoints"]:
        ep = r["endpoint"]
        if ep not in b:
            continue
        bp, ap = b[ep]["warm_p50_ms"], r["warm_p50_ms"]
        bc, ac = b[ep].get("cold_ms", 0.0), r["cold_ms"]
        print(f"{ep:38} {bp:11.1f} {ap:11.1f}   {bc:11.0f} {ac:11.0f}")


def _print(report: dict) -> None:
    print(f"\nTradeLogger API performance baseline  ({report['generated_at']})")
    print(f"{report['note']}")
    print(f"lifespan warm-up: {report.get('lifespan_warmup', False)}\n")
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
    dp = report.get("db_pool", {})
    if dp:
        print(f"\nDB pool: enabled={dp.get('enabled')} checkouts={dp.get('checkouts')} "
              f"reused={dp.get('reused')} created={dp.get('created')} pings={dp.get('pings')} "
              f"ping_failures={dp.get('ping_failures')} overflow_direct={dp.get('overflow_direct')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="write the full report to this path")
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--compare", default=None, help="baseline JSON to diff against")
    ap.add_argument("--lifespan", action="store_true",
                    help="run inside the FastAPI lifespan (fires the startup warm-up)")
    args = ap.parse_args()

    report = run(rounds=args.rounds, lifespan=args.lifespan)
    _print(report)
    if args.compare:
        compare(args.compare, report)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"\nwrote {args.json}")
    sys.exit(0)
