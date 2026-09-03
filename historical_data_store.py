# -*- coding: utf-8 -*-
"""
Persistent historical OHLCV store (Phase 69) — resolves Phase 68 P1-6.

Phase 68 established that the repo had **no persisted historical OHLCV** and no
offline historical price source, so Phase-67 historical (`as_of`) mode could only
serve MACRO/COT. This module is the store: a single ``historical_candles`` table
(created by ``database.init_db``) plus a small, dialect-safe read/write API and a
provider adapter that plugs into the Phase-68 ``historical_market_data`` registry.

Design rules
  * ONE database — extends the existing ``database.py`` abstraction (SQLite local
    / Postgres cloud), no second DB architecture.
  * Canonical time: ``open_time`` is integer epoch **seconds, UTC**, candle-open.
  * Uniqueness: (asset, timeframe, open_time) is the primary key. Duplicate-safe.
  * Never silently repair bad market data — a candle failing OHLC-consistency
    checks is rejected (and counted), or stored with ``data_quality='suspect'``
    when it is merely gappy.
  * Read-only w.r.t. execution — imports nothing from the execution/broker/risk
    layer.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import database
import research_universe

_LOCK = threading.RLock()

# timeframe -> seconds
TF_SECONDS: Dict[str, int] = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400,
}


def tf_seconds(timeframe: str) -> int:
    return TF_SECONDS.get((timeframe or "").strip().lower(), 900)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_asset(asset: str) -> str:
    return research_universe.normalise(asset)


def _ph(conn) -> str:
    return database.get_sql_placeholder(conn)


# ---------------------------------------------------------------------------
# Validation (§6)
# ---------------------------------------------------------------------------
@dataclass
class CandleValidation:
    ok: bool
    reason: str = ""
    quality: str = "ok"


def validate_candle(c: Dict[str, Any], tf_sec: int) -> CandleValidation:
    """OHLC-consistency gate. A structurally-broken candle is rejected."""
    try:
        o, h, l, cl = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])
        t = int(c["time"])
    except (KeyError, TypeError, ValueError):
        return CandleValidation(False, "MALFORMED_FIELDS")
    if t <= 0:
        return CandleValidation(False, "NON_POSITIVE_OPEN_TIME")
    if any(v <= 0 for v in (o, h, l, cl)):
        return CandleValidation(False, "NON_POSITIVE_PRICE")
    if h < l:
        return CandleValidation(False, "HIGH_LT_LOW")
    if h < max(o, cl) - 1e-9:
        return CandleValidation(False, "HIGH_LT_MAX_OPEN_CLOSE")
    if l > min(o, cl) + 1e-9:
        return CandleValidation(False, "LOW_GT_MIN_OPEN_CLOSE")
    if tf_sec and t % 60 != 0:
        # sub-minute misalignment is a source defect worth flagging, not rejecting
        return CandleValidation(True, "OPEN_TIME_NOT_MINUTE_ALIGNED", "suspect")
    return CandleValidation(True)


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------
@dataclass
class UpsertReport:
    asset: str
    timeframe: str
    source: str
    received: int = 0
    inserted: int = 0
    updated: int = 0
    rejected: int = 0
    reject_reasons: Dict[str, int] = field(default_factory=dict)
    suspect: int = 0
    first_open_time: Optional[int] = None
    last_open_time: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset, "timeframe": self.timeframe, "source": self.source,
            "received": self.received, "inserted": self.inserted,
            "updated": self.updated, "rejected": self.rejected,
            "reject_reasons": self.reject_reasons, "suspect": self.suspect,
            "first_open_time": self.first_open_time, "last_open_time": self.last_open_time,
        }


def upsert_candles(
    asset: str,
    timeframe: str,
    candles: List[Dict[str, Any]],
    source: str,
    source_revision: Optional[str] = None,
) -> UpsertReport:
    """Validate + duplicate-safe upsert. ``candles`` items: {time, open, high,
    low, close, volume}. ``time`` = epoch seconds (candle open, UTC)."""
    database.init_db()
    asset = _norm_asset(asset)
    timeframe = (timeframe or "").strip().lower()
    tf_sec = tf_seconds(timeframe)
    rep = UpsertReport(asset=asset, timeframe=timeframe, source=source)
    rep.received = len(candles or [])

    clean: List[Tuple] = []
    ingested_at = _now_iso()
    seen: set = set()
    for c in candles or []:
        v = validate_candle(c, tf_sec)
        if not v.ok:
            rep.rejected += 1
            rep.reject_reasons[v.reason] = rep.reject_reasons.get(v.reason, 0) + 1
            continue
        t = int(c["time"])
        if t in seen:
            rep.rejected += 1
            rep.reject_reasons["DUPLICATE_IN_BATCH"] = rep.reject_reasons.get("DUPLICATE_IN_BATCH", 0) + 1
            continue
        seen.add(t)
        if v.quality == "suspect":
            rep.suspect += 1
        clean.append((
            asset, timeframe, t,
            float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]),
            float(c.get("volume") or 0.0),
            source, source_revision, v.quality, ingested_at,
        ))

    if not clean:
        _log_ingestion(rep, mode="upsert")
        return rep

    times = [row[2] for row in clean]
    rep.first_open_time, rep.last_open_time = min(times), max(times)

    with _LOCK:
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            existing = _existing_open_times(cur, conn, asset, timeframe, rep.first_open_time, rep.last_open_time)
            ph = _ph(conn)
            cols = ("asset,timeframe,open_time,open,high,low,close,volume,"
                    "source,source_revision,data_quality,ingested_at")
            if database.is_postgres():
                upsert_tail = (
                    " ON CONFLICT (asset,timeframe,open_time) DO UPDATE SET "
                    "open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,"
                    "volume=EXCLUDED.volume,source=EXCLUDED.source,source_revision=EXCLUDED.source_revision,"
                    "data_quality=EXCLUDED.data_quality,ingested_at=EXCLUDED.ingested_at"
                )
                try:
                    from psycopg2.extras import execute_values
                    execute_values(
                        cur,
                        f"INSERT INTO historical_candles ({cols}) VALUES %s" + upsert_tail,
                        clean, page_size=1000,
                    )
                except Exception:
                    cur.executemany(
                        f"INSERT INTO historical_candles ({cols}) VALUES "
                        f"({','.join([ph] * 12)})" + upsert_tail, clean)
            else:
                cur.executemany(
                    f"INSERT OR REPLACE INTO historical_candles ({cols}) VALUES "
                    f"({','.join([ph] * 12)})", clean)
            conn.commit()
        finally:
            conn.close()

    for t in times:
        if t in existing:
            rep.updated += 1
        else:
            rep.inserted += 1

    _log_ingestion(rep, mode="upsert")
    return rep


def _existing_open_times(cur, conn, asset: str, timeframe: str, lo: int, hi: int) -> set:
    ph = _ph(conn)
    cur.execute(
        f"SELECT open_time FROM historical_candles WHERE asset={ph} AND timeframe={ph} "
        f"AND open_time>={ph} AND open_time<={ph}",
        (asset, timeframe, lo, hi),
    )
    return {int(r[0]) for r in cur.fetchall()}


def _log_ingestion(rep: UpsertReport, mode: str) -> None:
    try:
        with _LOCK:
            conn = database.get_connection()
            try:
                cur = conn.cursor()
                ph = _ph(conn)
                cur.execute(
                    f"INSERT INTO historical_ingestion_log (asset,timeframe,source,mode,inserted,updated,"
                    f"rejected,first_open_time,last_open_time,report,ran_at) VALUES "
                    f"({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
                    (rep.asset, rep.timeframe, rep.source, mode, rep.inserted, rep.updated,
                     rep.rejected, rep.first_open_time, rep.last_open_time,
                     json.dumps(rep.to_dict()), _now_iso()),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------
def get_candles(
    asset: str,
    timeframe: str,
    start: Optional[int] = None,
    end: Optional[int] = None,
    limit: Optional[int] = None,
    as_of: Optional[int] = None,
    include_suspect: bool = True,
) -> List[Dict[str, Any]]:
    """Return stored candles as dicts {time,open,high,low,close,volume,source,
    data_quality}, ascending by open_time.

    ``as_of`` (epoch seconds) truncates to candles whose CLOSE
    (``open_time + timeframe``) is <= as_of — the same look-ahead rule as
    ``historical_market_data._truncate``.
    """
    database.init_db()
    asset = _norm_asset(asset)
    timeframe = (timeframe or "").strip().lower()
    tf_sec = tf_seconds(timeframe)

    with _LOCK:
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            ph = _ph(conn)
            clauses = [f"asset={ph}", f"timeframe={ph}"]
            params: List[Any] = [asset, timeframe]
            if start is not None:
                clauses.append(f"open_time>={ph}")
                params.append(int(start))
            if end is not None:
                clauses.append(f"open_time<={ph}")
                params.append(int(end))
            if as_of is not None:
                clauses.append(f"open_time<={ph}")
                params.append(int(as_of) - tf_sec)
            if not include_suspect:
                clauses.append(f"data_quality={ph}")
                params.append("ok")
            sql = (
                "SELECT open_time,open,high,low,close,volume,source,data_quality "
                "FROM historical_candles WHERE " + " AND ".join(clauses) +
                " ORDER BY open_time ASC"
            )
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        finally:
            conn.close()

    out = [
        {
            "time": int(r[0]), "open": float(r[1]), "high": float(r[2]),
            "low": float(r[3]), "close": float(r[4]), "volume": float(r[5] or 0.0),
            "source": r[6], "data_quality": r[7],
        }
        for r in rows
    ]
    if limit is not None and len(out) > limit:
        out = out[-int(limit):]
    return out


# ---------------------------------------------------------------------------
# Coverage & gap detection (§6, §9)
# ---------------------------------------------------------------------------
@dataclass
class Coverage:
    asset: str
    timeframe: str
    count: int
    first_open_time: Optional[int]
    last_open_time: Optional[int]
    expected_bars: Optional[int]
    missing_bars: Optional[int]
    largest_gap_bars: int
    suspect: int
    sources: List[str]

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        for k in ("first_open_time", "last_open_time"):
            v = d[k]
            d[k + "_iso"] = (
                datetime.fromtimestamp(v, tz=timezone.utc).isoformat() if v else None
            )
        return d


def _open_times(asset: str, timeframe: str) -> List[int]:
    """Just the open_time column, ascending — the cheap primitive behind coverage
    / gap analysis (avoids pulling every OHLCV column for a multi-thousand-bar
    series over the wire)."""
    database.init_db()
    with _LOCK:
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            ph = _ph(conn)
            cur.execute(
                f"SELECT open_time FROM historical_candles WHERE asset={ph} AND timeframe={ph} "
                f"ORDER BY open_time ASC",
                (_norm_asset(asset), (timeframe or "").strip().lower()),
            )
            return [int(r[0]) for r in cur.fetchall()]
        finally:
            conn.close()


def _suspect_and_sources(asset: str, timeframe: str) -> Tuple[int, List[str]]:
    with _LOCK:
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            ph = _ph(conn)
            a, tf = _norm_asset(asset), (timeframe or "").strip().lower()
            cur.execute(
                f"SELECT COUNT(*) FROM historical_candles WHERE asset={ph} AND timeframe={ph} "
                f"AND data_quality<>{ph}", (a, tf, "ok"))
            suspect = int(cur.fetchone()[0])
            cur.execute(
                f"SELECT DISTINCT source FROM historical_candles WHERE asset={ph} AND timeframe={ph}",
                (a, tf))
            sources = sorted(r[0] for r in cur.fetchall())
            return suspect, sources
        finally:
            conn.close()


def get_coverage(asset: str, timeframe: str) -> Coverage:
    database.init_db()
    asset = _norm_asset(asset)
    timeframe = (timeframe or "").strip().lower()
    tf_sec = tf_seconds(timeframe)
    times = _open_times(asset, timeframe)
    if not times:
        return Coverage(asset, timeframe, 0, None, None, None, None, 0, 0, [])

    first, last = times[0], times[-1]
    expected = int((last - first) / tf_sec) + 1 if tf_sec else len(times)
    missing = max(expected - len(times), 0)

    largest_gap = 0
    for a, b in zip(times, times[1:]):
        gap = int(round((b - a) / tf_sec)) - 1 if tf_sec else 0
        largest_gap = max(largest_gap, gap)

    suspect, sources = _suspect_and_sources(asset, timeframe)
    return Coverage(asset, timeframe, len(times), first, last, expected, missing,
                    largest_gap, suspect, sources)


def detect_gaps(asset: str, timeframe: str, min_gap_bars: int = 1) -> List[Dict[str, Any]]:
    """List runs of missing bars. A weekend on FX is an expected gap — callers
    that care (ingestion validation) apply calendar awareness; this is the raw
    structural view."""
    timeframe = (timeframe or "").strip().lower()
    tf_sec = tf_seconds(timeframe)
    times = _open_times(asset, timeframe)
    gaps: List[Dict[str, Any]] = []
    for a, b in zip(times, times[1:]):
        missing = int(round((b - a) / tf_sec)) - 1 if tf_sec else 0
        if missing >= min_gap_bars:
            gaps.append({
                "after_open_time": a,
                "before_open_time": b,
                "missing_bars": missing,
                "after_iso": datetime.fromtimestamp(a, tz=timezone.utc).isoformat(),
                "before_iso": datetime.fromtimestamp(b, tz=timezone.utc).isoformat(),
            })
    return gaps


def list_available() -> List[Dict[str, Any]]:
    database.init_db()
    with _LOCK:
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT asset,timeframe,COUNT(*),MIN(open_time),MAX(open_time) "
                "FROM historical_candles GROUP BY asset,timeframe ORDER BY asset,timeframe"
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    return [
        {
            "asset": r[0], "timeframe": r[1], "count": int(r[2]),
            "first_open_time": int(r[3]) if r[3] else None,
            "last_open_time": int(r[4]) if r[4] else None,
            "first_iso": datetime.fromtimestamp(r[3], tz=timezone.utc).isoformat() if r[3] else None,
            "last_iso": datetime.fromtimestamp(r[4], tz=timezone.utc).isoformat() if r[4] else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Weekend-aware gap analysis
# ---------------------------------------------------------------------------
def _saturdays_between(a: int, b: int) -> int:
    """Number of Saturday 00:00 UTC boundaries in the open interval (a, b)."""
    da = datetime.fromtimestamp(a, tz=timezone.utc)
    db = datetime.fromtimestamp(b, tz=timezone.utc)
    # first Saturday strictly after da
    days_ahead = (5 - da.weekday()) % 7
    first_sat = (da + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    if first_sat <= da:
        first_sat += timedelta(days=7)
    count = 0
    t = first_sat
    while t < db:
        count += 1
        t += timedelta(days=7)
    return count


def analyze_gaps(asset: str, timeframe: str) -> Dict[str, Any]:
    """Classify structural gaps into weekend / holiday / anomalous. FX stops
    ~Fri 21:00 UTC → Sun 21:00 UTC (~48 h); a gap no larger than the weekends it
    spans plus a one-day holiday allowance is expected, not a data defect."""
    timeframe = (timeframe or "").strip().lower()
    tf_sec = tf_seconds(timeframe)
    times = _open_times(asset, timeframe)
    per_bar_day = (24 * 3600) / tf_sec if tf_sec else 1
    weekend_bars = (49 * 3600) / tf_sec if tf_sec else 1
    holiday_tol = 1.5 * per_bar_day

    weekend = holiday = anomalous = 0
    largest_anom = 0
    anom_list: List[Dict[str, Any]] = []
    for a, b in zip(times, times[1:]):
        missing = int(round((b - a) / tf_sec)) - 1 if tf_sec else 0
        if missing < 1:
            continue
        wk = _saturdays_between(a, b)
        expected = wk * weekend_bars + holiday_tol
        if missing <= max(expected, per_bar_day * 0.6):
            if wk:
                weekend += 1
            else:
                holiday += 1
        else:
            anomalous += 1
            largest_anom = max(largest_anom, missing)
            if len(anom_list) < 20:
                anom_list.append({
                    "after_iso": datetime.fromtimestamp(a, tz=timezone.utc).isoformat(),
                    "before_iso": datetime.fromtimestamp(b, tz=timezone.utc).isoformat(),
                    "missing_bars": missing, "weekends_spanned": wk,
                })
    return {
        "weekend_gaps": weekend, "holiday_gaps": holiday, "anomalous_gaps": anomalous,
        "largest_anomalous_bars": largest_anom, "examples": anom_list,
    }


# ---------------------------------------------------------------------------
# Data sufficiency gate (§9)
# ---------------------------------------------------------------------------
def data_sufficiency(asset: str, timeframe: str) -> Dict[str, Any]:
    """Returns AVAILABLE / INSUFFICIENT_EVIDENCE (never a 0-trade verdict)."""
    timeframe = (timeframe or "").strip().lower()
    rule = research_universe.sufficiency_rule(timeframe)
    cov = get_coverage(asset, timeframe)
    if rule is None:
        return {
            "state": "NOT_APPLICABLE", "asset": _norm_asset(asset), "timeframe": timeframe,
            "reason": f"no sufficiency rule for timeframe '{timeframe}'",
            "have_bars": cov.count,
        }
    gap = analyze_gaps(asset, timeframe) if cov.count else {
        "anomalous_gaps": 0, "largest_anomalous_bars": 0, "weekend_gaps": 0, "holiday_gaps": 0}
    reasons: List[str] = []
    if cov.count == 0:
        reasons.append("NO_DATA_IN_STORE")
    if cov.count < rule.min_bars:
        reasons.append(f"BELOW_MIN_BARS ({cov.count} < {rule.min_bars})")
    # Only *anomalous* (non-weekend / non-holiday) gaps beyond tolerance fail the gate.
    anomalous_budget = max(2, int(cov.count / 4000))
    if gap["anomalous_gaps"] > anomalous_budget or gap["largest_anomalous_bars"] > rule.max_gap_bars * 8:
        reasons.append(
            f"ANOMALOUS_GAPS ({gap['anomalous_gaps']} gaps, largest "
            f"{gap['largest_anomalous_bars']} bars — beyond weekend/holiday tolerance)")
    state = "AVAILABLE" if not reasons else "INSUFFICIENT_EVIDENCE"
    return {
        "state": state,
        "asset": _norm_asset(asset),
        "timeframe": timeframe,
        "have_bars": cov.count,
        "need_bars": rule.min_bars,
        "warmup_bars": rule.warmup_bars,
        "usable_decision_bars": max(cov.count - rule.warmup_bars, 0),
        "largest_gap_bars": cov.largest_gap_bars,
        "gap_analysis": gap,
        "max_gap_bars": rule.max_gap_bars,
        "reasons": reasons,
        "next_dependency": (
            None if state == "AVAILABLE"
            else f"ingest more {timeframe} history for {_norm_asset(asset)} "
                 f"(python -m market_data_ingest --asset {_norm_asset(asset)} --timeframe {timeframe})"
        ),
        "coverage": cov.to_dict(),
    }


# ---------------------------------------------------------------------------
# Phase-68 provider adapter
# ---------------------------------------------------------------------------
def store_provider(asset: str, timeframe: str, as_of_epoch: float, lookback: int
                   ) -> Optional[List[Dict[str, Any]]]:
    """Adapter for ``historical_market_data.register_provider``. Returns raw
    candles (Phase-68 truncates + shapes them). ``None`` when the store has
    nothing for the request — an honest gap, not a fabricated series."""
    tf_sec = tf_seconds(timeframe)
    rows = get_candles(
        _norm_asset(asset), timeframe,
        end=int(as_of_epoch),
        as_of=int(as_of_epoch),
        limit=max(int(lookback) + 30, 60),
    )
    if len(rows) < 2:
        return None
    return [
        {"time": r["time"], "open": r["open"], "high": r["high"],
         "low": r["low"], "close": r["close"], "volume": r["volume"]}
        for r in rows
    ]


_REGISTERED = False


def register_with_phase68() -> None:
    """Wire the store in as the ``store`` historical provider. Idempotent.
    Safe to call at import time of the ingestion module / API startup."""
    global _REGISTERED
    if _REGISTERED:
        return
    try:
        import historical_market_data
        historical_market_data.register_provider("store", store_provider)
        _REGISTERED = True
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Research artifact persistence (§31, §51) — used by later phases
# ---------------------------------------------------------------------------
def save_artifact(artifact_key: str, kind: str, payload: Dict[str, Any]) -> str:
    database.init_db()
    body = json.dumps(payload, sort_keys=True, default=str)
    import hashlib
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    now = _now_iso()
    with _LOCK:
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            ph = _ph(conn)
            if database.is_postgres():
                cur.execute(
                    f"INSERT INTO research_artifacts (artifact_key,kind,payload,content_hash,created_at,updated_at) "
                    f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph}) "
                    f"ON CONFLICT (artifact_key) DO UPDATE SET kind=EXCLUDED.kind,payload=EXCLUDED.payload,"
                    f"content_hash=EXCLUDED.content_hash,updated_at=EXCLUDED.updated_at",
                    (artifact_key, kind, body, content_hash, now, now),
                )
            else:
                cur.execute(
                    f"INSERT INTO research_artifacts (artifact_key,kind,payload,content_hash,created_at,updated_at) "
                    f"VALUES ({ph},{ph},{ph},{ph},"
                    f"COALESCE((SELECT created_at FROM research_artifacts WHERE artifact_key={ph}),{ph}),{ph}) "
                    f"ON CONFLICT(artifact_key) DO UPDATE SET kind=excluded.kind,payload=excluded.payload,"
                    f"content_hash=excluded.content_hash,updated_at=excluded.updated_at",
                    (artifact_key, kind, body, content_hash, artifact_key, now, now),
                )
            conn.commit()
        finally:
            conn.close()
    return content_hash


def load_artifact(artifact_key: str) -> Optional[Dict[str, Any]]:
    database.init_db()
    with _LOCK:
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            ph = _ph(conn)
            cur.execute(
                f"SELECT payload,content_hash,created_at,updated_at FROM research_artifacts WHERE artifact_key={ph}",
                (artifact_key,),
            )
            row = cur.fetchone()
        finally:
            conn.close()
    if not row:
        return None
    return {
        "payload": json.loads(row[0]),
        "content_hash": row[1],
        "created_at": row[2],
        "updated_at": row[3],
    }


__all__ = [
    "TF_SECONDS", "tf_seconds", "validate_candle", "CandleValidation",
    "UpsertReport", "upsert_candles", "get_candles", "Coverage", "get_coverage",
    "detect_gaps", "list_available", "data_sufficiency", "store_provider",
    "register_with_phase68", "save_artifact", "load_artifact",
]
