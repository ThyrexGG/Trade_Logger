# -*- coding: utf-8 -*-
"""
Phase 94 -- Swing-Trading Data Foundation.

Phases 70-93 established that intraday directional prediction on the
6-instrument 15m FX/gold universe has no edge. Phase 94 begins a
deliberate pivot to SWING timeframes (daily bars, days-to-months holding
periods) where the documented, out-of-sample-surviving edges actually
live: time-series and cross-sectional momentum, and -- for crypto --
funding-rate carry.

This is a DATA phase, not a strategy phase. It acquires and stores, with
the same provenance / validation / idempotency discipline as Phase 74's
MT5 ingestion:

  1. Crypto daily OHLCV -- a frozen, market-cap-ranked universe of liquid
     coins that have both a Binance spot pair and a Binance USDT-margined
     perpetual (so the same names can be used for both the momentum sleeve
     and the funding-carry sleeve). Source: Binance spot klines
     (``api.binance.com/api/v3/klines``). Stored as ``<BASE>USD`` -- USDT
     is treated as USD for research purposes, disclosed here explicitly.
  2. Crypto perpetual funding-rate history, aggregated to a daily summed
     rate per coin. Source: Binance USD-M futures
     (``fapi.binance.com/fapi/v1/fundingRate``). Stored as a research
     artifact per coin (not an OHLCV series).
  3. Auxiliary daily FX/metals to round out the swing universe:
     ``XAGUSD`` (silver, pairs with gold) and ``EURGBP`` (completes the
     liquid FX majors already in the store from Phase 74). Source:
     Yahoo Finance (already a project dependency).

No strategy logic, no backtesting, no signals, no parameter search, no
live execution, no broker transmission. The frozen Phase-74 Gold holdout
is never read. All fetches are read-only external data acquisition;
re-running is idempotent (the store's upsert is duplicate-safe).

FX policy-rate / swap data for the FX carry sleeve is deferred to the
phase that needs it (FX carry), not acquired speculatively here.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import historical_data_store as store

SCHEMA_VERSION = "phase94.1"
ARTIFACT_KEY = "phase94_swing_data_foundation"
_FUNDING_ARTIFACT_PREFIX = "phase94_funding_daily__"

# --------------------------------------------------------------------------
# Frozen crypto universe -- selection criteria (applied once, then frozen
# here for reproducibility; NOT re-ranked on every run):
#   * ranked by market capitalisation (CoinGecko, top ~60)
#   * has a Binance <BASE>USDT spot pair AND a Binance <BASE>USDT
#     PERPETUAL (needed for the funding-carry sleeve)
#   * excludes stablecoins, wrapped/staked derivatives, and tokenised
#     gold (XAUT/PAXG -- they would just track the XAUUSD series)
#   * excludes names with under ~2 years of history at selection time
#     (insufficient for a 12-month momentum lookback); such names can be
#     added in a later phase once they have the history.
# --------------------------------------------------------------------------
CRYPTO_UNIVERSE: Tuple[str, ...] = (
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ADA", "LINK", "XLM",
    "BCH", "LTC", "DOT", "AVAX", "UNI", "NEAR", "ICP", "HBAR", "SUI", "AAVE",
    "ETC", "ATOM", "FIL", "APT", "ARB", "OP", "INJ",
)
# Historical-only, NOT in the forward universe: XMR (Monero) was delisted
# from Binance spot in Feb 2024 for regulatory reasons -- its OHLCV /
# funding history was ingested for pre-2024 backtesting completeness but it
# is not tradeable there now, so it is excluded from CRYPTO_UNIVERSE above.
CRYPTO_HISTORICAL_ONLY: Tuple[str, ...] = ("XMR",)
_STALE_DAYS = 45   # a daily series whose last bar is older than this is flagged not-current
AUX_FX: Tuple[Tuple[str, str], ...] = (("XAGUSD", "SI=F"), ("EURGBP", "EURGBP=X"))

_BINANCE_SPOT = "https://api.binance.com/api/v3/klines"
_BINANCE_FAPI_FUNDING = "https://fapi.binance.com/fapi/v1/fundingRate"
_BINANCE_FAPI_KLINES = "https://fapi.binance.com/fapi/v1/klines"
_CRYPTO_HISTORY_START_MS = 1_451_606_400_000   # 2016-01-01 UTC (Binance returns from first listing anyway)
_DAY_MS = 86_400_000
_REQ_HEADERS = {"User-Agent": "Mozilla/5.0 (TradeLogger research ingestion)"}
_MAX_RETRIES = 4


# ==========================================================================
# low-level HTTP (deliberately dependency-free: urllib only)
# ==========================================================================
def _get_json(url: str, timeout: int = 25) -> Any:
    last_err: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=_REQ_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (418, 429):        # Binance rate limit / ban
                time.sleep(2.0 * (attempt + 1) + 3.0)
                continue
            if 500 <= e.code < 600:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {_MAX_RETRIES} attempts: {url} :: {last_err!r}")


# ==========================================================================
# Binance spot daily klines -- paginated
# ==========================================================================
def _binance_daily_klines(base: str, start_ms: int = _CRYPTO_HISTORY_START_MS,
                          spot: bool = True) -> List[Dict[str, Any]]:
    symbol = f"{base}USDT"
    endpoint = _BINANCE_SPOT if spot else _BINANCE_FAPI_KLINES
    out: List[Dict[str, Any]] = []
    cursor = start_ms
    while True:
        url = f"{endpoint}?symbol={symbol}&interval=1d&startTime={cursor}&limit=1000"
        rows = _get_json(url)
        if not rows:
            break
        for r in rows:
            open_ms = int(r[0])
            out.append({"time": open_ms // 1000, "open": float(r[1]), "high": float(r[2]),
                       "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])})
        last_open = int(rows[-1][0])
        if len(rows) < 1000:
            break
        cursor = last_open + _DAY_MS
        time.sleep(0.25)
        if cursor > int(time.time() * 1000):
            break
    # drop a possibly-incomplete final (today) bar
    now_day = (int(time.time()) // 86400) * 86400
    out = [c for c in out if c["time"] < now_day]
    return out


# ==========================================================================
# Binance perpetual funding-rate history -> daily summed rate
# ==========================================================================
def _binance_funding_history(base: str, start_ms: int = _CRYPTO_HISTORY_START_MS) -> List[Tuple[int, float]]:
    """Returns [(funding_time_epoch_s, rate), ...] ascending. Binance pays
    funding every 8h (occasionally 4h); we keep every payment and let the
    daily aggregation sum them."""
    symbol = f"{base}USDT"
    out: List[Tuple[int, float]] = []
    cursor = start_ms
    while True:
        url = f"{_BINANCE_FAPI_FUNDING}?symbol={symbol}&startTime={cursor}&limit=1000"
        rows = _get_json(url)
        if not rows:
            break
        for r in rows:
            out.append((int(r["fundingTime"]) // 1000, float(r["fundingRate"])))
        if len(rows) < 1000:
            break
        cursor = int(rows[-1]["fundingTime"]) + 1
        time.sleep(0.25)
        if cursor > int(time.time() * 1000):
            break
    out.sort()
    return out


def _aggregate_funding_daily(payments: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
    by_day: Dict[int, float] = {}
    for ts, rate in payments:
        day = (ts // 86400) * 86400
        by_day[day] = by_day.get(day, 0.0) + rate
    return sorted(by_day.items())


# ==========================================================================
# ingestion entry points
# ==========================================================================
@dataclass
class IngestOutcome:
    kind: str
    asset: str
    ok: bool
    detail: str = ""
    received: int = 0
    stored: int = 0
    first_iso: Optional[str] = None
    last_iso: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def ingest_crypto_ohlcv(bases: Tuple[str, ...] = CRYPTO_UNIVERSE) -> List[IngestOutcome]:
    results: List[IngestOutcome] = []
    for base in bases:
        asset = f"{base}USD"
        try:
            candles = _binance_daily_klines(base, spot=True)
            if not candles:
                results.append(IngestOutcome("crypto_ohlcv", asset, False, "NO_DATA_RETURNED"))
                continue
            rep = store.upsert_candles(asset, "1d", candles, source="binance_spot",
                                       source_revision="api/v3/klines interval=1d")
            cov = store.get_coverage(asset, "1d")
            results.append(IngestOutcome(
                "crypto_ohlcv", asset, True, f"rejected={rep.rejected}",
                received=rep.received, stored=rep.inserted + rep.updated,
                first_iso=(datetime.fromtimestamp(cov.first_open_time, tz=timezone.utc).isoformat()
                          if cov.first_open_time else None),
                last_iso=(datetime.fromtimestamp(cov.last_open_time, tz=timezone.utc).isoformat()
                         if cov.last_open_time else None)))
        except Exception as e:  # pragma: no cover - network dependent
            results.append(IngestOutcome("crypto_ohlcv", asset, False, f"ERROR: {e!r}"[:300]))
    return results


def ingest_crypto_funding(bases: Tuple[str, ...] = CRYPTO_UNIVERSE) -> List[IngestOutcome]:
    results: List[IngestOutcome] = []
    for base in bases:
        asset = f"{base}USD"
        try:
            payments = _binance_funding_history(base)
            if not payments:
                results.append(IngestOutcome("crypto_funding", asset, False, "NO_FUNDING_RETURNED"))
                continue
            daily = _aggregate_funding_daily(payments)
            payload = {
                "symbol": asset, "perp_symbol": f"{base}USDT", "source": "binance_fapi_fundingRate",
                "schema_version": SCHEMA_VERSION, "n_payments": len(payments), "n_days": len(daily),
                "first_date": datetime.fromtimestamp(daily[0][0], tz=timezone.utc).date().isoformat(),
                "last_date": datetime.fromtimestamp(daily[-1][0], tz=timezone.utc).date().isoformat(),
                "daily_summed_funding_rate": [[d, round(r, 10)] for d, r in daily],
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            store.save_artifact(_FUNDING_ARTIFACT_PREFIX + asset, "phase94_funding_daily", payload)
            results.append(IngestOutcome("crypto_funding", asset, True, f"payments={len(payments)}",
                                         received=len(payments), stored=len(daily),
                                         first_iso=payload["first_date"], last_iso=payload["last_date"]))
        except Exception as e:  # pragma: no cover - network dependent
            results.append(IngestOutcome("crypto_funding", asset, False, f"ERROR: {e!r}"[:300]))
    return results


def get_funding_daily(asset: str) -> Optional[Dict[str, Any]]:
    art = store.load_artifact(_FUNDING_ARTIFACT_PREFIX + asset.upper())
    return art["payload"] if art else None


def ingest_aux_fx(pairs: Tuple[Tuple[str, str], ...] = AUX_FX) -> List[IngestOutcome]:
    try:
        import yfinance as yf
    except Exception as e:  # pragma: no cover
        return [IngestOutcome("aux_fx", a, False, f"yfinance unavailable: {e!r}") for a, _ in pairs]
    results: List[IngestOutcome] = []
    for asset, yf_symbol in pairs:
        try:
            df = yf.download(yf_symbol, period="10y", interval="1d", auto_adjust=False,
                            progress=False, threads=False)
            if df is None or df.empty:
                results.append(IngestOutcome("aux_fx", asset, False, "NO_DATA_RETURNED"))
                continue
            if hasattr(df.columns, "get_level_values"):
                df.columns = df.columns.get_level_values(0)
            candles = []
            for idx, row in df.iterrows():
                o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
                if not all(v > 0 for v in (o, h, l, c)):
                    continue
                ts = int(idx.tz_localize("UTC").timestamp()) if idx.tzinfo is None else int(idx.timestamp())
                ts = (ts // 86400) * 86400
                candles.append({"time": ts, "open": o, "high": h, "low": l, "close": c,
                               "volume": float(row.get("Volume", 0.0) or 0.0)})
            rep = store.upsert_candles(asset, "1d", candles, source="yahoo",
                                       source_revision=f"yfinance {yf_symbol} 1d 10y")
            cov = store.get_coverage(asset, "1d")
            results.append(IngestOutcome(
                "aux_fx", asset, True, f"rejected={rep.rejected}", received=rep.received,
                stored=rep.inserted + rep.updated,
                first_iso=(datetime.fromtimestamp(cov.first_open_time, tz=timezone.utc).isoformat()
                          if cov.first_open_time else None),
                last_iso=(datetime.fromtimestamp(cov.last_open_time, tz=timezone.utc).isoformat()
                         if cov.last_open_time else None)))
        except Exception as e:  # pragma: no cover
            results.append(IngestOutcome("aux_fx", asset, False, f"ERROR: {e!r}"[:300]))
    return results


# ==========================================================================
# coverage report -- the persistable artifact / API surface
# ==========================================================================
_SWING_FX_METALS: Tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "EURGBP", "XAUUSD", "XAGUSD",
)
_MIN_MOMENTUM_BARS = 400   # ~12-month lookback + a walk-forward test window


def _is_current(last_open_time: Optional[int]) -> bool:
    if not last_open_time:
        return False
    return (time.time() - last_open_time) <= _STALE_DAYS * 86400


def build_coverage_report() -> Dict[str, Any]:
    fx_metals = []
    for a in _SWING_FX_METALS:
        cov = store.get_coverage(a, "1d")
        n = cov.count or 0
        fx_metals.append({"asset": a, "timeframe": "1d", "bars": n,
                         "first_iso": (datetime.fromtimestamp(cov.first_open_time, tz=timezone.utc).isoformat()
                                      if cov.first_open_time else None),
                         "last_iso": (datetime.fromtimestamp(cov.last_open_time, tz=timezone.utc).isoformat()
                                     if cov.last_open_time else None),
                         "current": _is_current(cov.last_open_time),
                         "momentum_ready": n >= _MIN_MOMENTUM_BARS and _is_current(cov.last_open_time)})
    crypto = []
    for base in CRYPTO_UNIVERSE:
        asset = f"{base}USD"
        cov = store.get_coverage(asset, "1d")
        n = cov.count or 0
        funding = get_funding_daily(asset)
        crypto.append({"asset": asset, "timeframe": "1d", "bars": n,
                      "first_iso": (datetime.fromtimestamp(cov.first_open_time, tz=timezone.utc).isoformat()
                                   if cov.first_open_time else None),
                      "last_iso": (datetime.fromtimestamp(cov.last_open_time, tz=timezone.utc).isoformat()
                                  if cov.last_open_time else None),
                      "current": _is_current(cov.last_open_time),
                      "momentum_ready": n >= _MIN_MOMENTUM_BARS and _is_current(cov.last_open_time),
                      "funding_days": (funding or {}).get("n_days", 0),
                      "funding_ready": bool(funding and funding.get("n_days", 0) >= _MIN_MOMENTUM_BARS)})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "fx_metals_universe": fx_metals,
        "crypto_universe": crypto,
        "summary": {
            "fx_metals_total": len(fx_metals),
            "fx_metals_momentum_ready": sum(1 for r in fx_metals if r["momentum_ready"]),
            "crypto_total": len(crypto),
            "crypto_momentum_ready": sum(1 for r in crypto if r["momentum_ready"]),
            "crypto_funding_ready": sum(1 for r in crypto if r["funding_ready"]),
        },
        "notes": [
            "USDT is treated as USD for crypto research purposes (Binance <BASE>USDT pairs).",
            "Crypto OHLCV source: Binance spot api/v3/klines. Funding source: Binance fapi/v1/fundingRate, "
            "aggregated to a daily summed rate and stored as artifact "
            f"'{_FUNDING_ARTIFACT_PREFIX}<ASSET>'.",
            "XAGUSD / EURGBP source: Yahoo Finance (SI=F futures / EURGBP=X); EURGBP had ~45 thin "
            "holiday rows rejected by the OHLC-consistency gate (~1.7%), leaving ~2,558 usable daily bars. "
            "All other FX/gold daily bars were ingested by Phase 74 from MT5.",
            "XMR (Monero) is in CRYPTO_HISTORICAL_ONLY, not CRYPTO_UNIVERSE: Binance delisted it from spot "
            "in Feb 2024, so its series ends 2024-02-20 and it is not tradeable there now. Its history "
            "remains in the store for pre-2024 backtesting completeness only.",
            "'current' = last daily bar within 45 days of now; 'momentum_ready' now requires both "
            "sufficient bar count AND current data.",
            "This phase performs NO strategy logic, backtesting, or signal generation. Holdout untouched, "
            "live automation disabled, broker transmission blocked.",
        ],
        "holdout_untouched": True,
        "strategy_status": "DATA_ONLY_NO_STRATEGY_NO_LIVE_EXECUTION",
    }


# ==========================================================================
# result container / persistence
# ==========================================================================
@dataclass
class Phase94Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    crypto_ohlcv_outcomes: List[Dict[str, Any]]
    crypto_funding_outcomes: List[Dict[str, Any]]
    aux_fx_outcomes: List[Dict[str, Any]]
    coverage_report: Dict[str, Any]
    runtime_seconds: float = 0.0
    holdout_untouched: bool = True
    strategy_status: str = "DATA_ONLY_NO_STRATEGY_NO_LIVE_EXECUTION"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def run(do_ohlcv: bool = True, do_funding: bool = True, do_aux: bool = True) -> Phase94Result:
    t0 = datetime.now(timezone.utc)
    ohlcv = ingest_crypto_ohlcv() if do_ohlcv else []
    funding = ingest_crypto_funding() if do_funding else []
    aux = ingest_aux_fx() if do_aux else []
    report = build_coverage_report()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()
    return Phase94Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=_git_commit(),
        crypto_ohlcv_outcomes=[o.to_dict() for o in ohlcv],
        crypto_funding_outcomes=[o.to_dict() for o in funding],
        aux_fx_outcomes=[o.to_dict() for o in aux],
        coverage_report=report, runtime_seconds=round(rt, 1),
    )


def persist(result: Optional[Phase94Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase94_swing_data_foundation", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    p = argparse.ArgumentParser(description="Phase 94 swing-trading data foundation ingestion")
    p.add_argument("--crypto", action="store_true", help="ingest crypto daily OHLCV")
    p.add_argument("--funding", action="store_true", help="ingest crypto perp funding-rate history")
    p.add_argument("--aux", action="store_true", help="ingest XAGUSD / EURGBP daily")
    p.add_argument("--report", action="store_true", help="(re)build the coverage report only")
    p.add_argument("--all", action="store_true", help="everything")
    args = p.parse_args(_argv)
    if not any((args.crypto, args.funding, args.aux, args.report, args.all)):
        args.all = True

    do_ohlcv = args.all or args.crypto
    do_funding = args.all or args.funding
    do_aux = args.all or args.aux
    if args.report and not any((args.all, args.crypto, args.funding, args.aux)):
        rep = build_coverage_report()
        store.save_artifact(ARTIFACT_KEY + "_coverage", "phase94_coverage", rep)
        print(json.dumps(rep["summary"], indent=2))
        return 0

    print("Phase 94 - swing-trading data foundation ...", flush=True)
    res = run(do_ohlcv=do_ohlcv, do_funding=do_funding, do_aux=do_aux)
    h = persist(res)
    print(f"\n=== PHASE 94 ({res.runtime_seconds}s) ===")
    for grp, outs in (("crypto OHLCV", res.crypto_ohlcv_outcomes),
                      ("crypto funding", res.crypto_funding_outcomes),
                      ("aux FX", res.aux_fx_outcomes)):
        ok = sum(1 for o in outs if o["ok"])
        print(f"\n{grp}: {ok}/{len(outs)} ok")
        for o in outs:
            flag = "OK " if o["ok"] else "ERR"
            print(f"  [{flag}] {o['asset']:9} {o.get('first_iso') or '-':25} -> {o.get('last_iso') or '-':25} {o['detail']}")
    print(f"\ncoverage summary: {json.dumps(res.coverage_report['summary'], default=str)}")
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "CRYPTO_UNIVERSE", "AUX_FX", "ingest_crypto_ohlcv",
    "ingest_crypto_funding", "ingest_aux_fx", "get_funding_daily", "build_coverage_report",
    "run", "persist", "get_result", "main",
]
