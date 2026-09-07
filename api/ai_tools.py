# -*- coding: utf-8 -*-
"""
Read-only tool registry for the AI Assistant (Phase W1 — dynamic queries).

The assistant can *request* one of the tools declared here; `dispatch()` runs it
and returns bounded, structured JSON. Every tool is a thin wrapper over a query
the app already exposes elsewhere (analytics, the journal, the macro scorecard).

Security boundary — same as `api/ai_context.py`:
- This module must never import `execution_pipeline`, a broker adapter, the risk
  gateway, or any order-submission / position-mutation path.
- Every tool is READ-ONLY: it runs `SELECT`-style reads and pure computation. No
  tool writes, executes a strategy live, or reaches a broker.
- `dispatch()` is a hard allowlist — a name not in `_TOOLS` is rejected. The
  model cannot call anything that is not declared here.
- Enforced by `tests/test_stage16_ai_tools.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

import analytics
import database

# --- session windows (UTC hour ranges; deliberately coarse) -------------
# FX sessions overlap and are fuzzy — these are pragmatic buckets on the
# trade's ENTRY time in UTC, and the tool output says so.
_SESSIONS: Dict[str, tuple] = {
    "asia": (23, 7),       # Tokyo/Sydney
    "london": (7, 12),     # London-only morning
    "newyork": (12, 21),   # NY session (incl. the London/NY overlap)
}
_WINDOWS = {"today", "week", "month", "quarter", "year", "all"}
_MAX_ROWS = 25


def _f(v: Any) -> float:
    try:
        x = float(v)
        return x if x == x else 0.0  # NaN guard
    except Exception:
        return 0.0


def _s(v: Any) -> Optional[str]:
    if v is None:
        return None
    try:
        if isinstance(v, float) and v != v:
            return None
    except Exception:
        pass
    t = str(v).strip()
    return t or None


def _closed_trades() -> pd.DataFrame:
    df = database.get_closed_trades(ttl_sec=5.0)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True, errors="coerce")
    df["exit_time"] = pd.to_datetime(df["exit_time"], utc=True, errors="coerce")
    return df


def _session_mask(df: pd.DataFrame, session: str) -> pd.Series:
    lo, hi = _SESSIONS[session]
    hrs = df["entry_time"].dt.hour
    if lo < hi:
        return (hrs >= lo) & (hrs < hi)
    return (hrs >= lo) | (hrs < hi)  # wraps midnight


def _window_start(window: str, now: datetime) -> Optional[datetime]:
    if window == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "week":
        return now - timedelta(days=7)
    if window == "month":
        return now - timedelta(days=30)
    if window == "quarter":
        return now - timedelta(days=91)
    if window == "year":
        return now - timedelta(days=365)
    return None  # 'all'


def _metrics_subset(df: pd.DataFrame) -> Dict[str, Any]:
    """Compact slice of `analytics.calculate_performance_metrics`."""
    m = analytics.calculate_performance_metrics(df)
    return {
        "n": int(m.get("total_trades", 0)),
        "wins": int(m.get("winning_trades", 0)),
        "losses": int(m.get("losing_trades", 0)),
        "win_rate_pct": round(_f(m.get("win_rate")), 1),
        "net_pnl_usd": round(_f(m.get("total_net_pnl")), 2),
        "gross_profit_usd": round(_f(m.get("total_gross_profit")), 2),
        "gross_loss_usd": round(_f(m.get("total_gross_loss")), 2),
        "avg_win_usd": round(_f(m.get("avg_win")), 2),
        "avg_loss_usd": round(_f(m.get("avg_loss")), 2),
        "expectancy_usd": round(_f(m.get("expectancy")), 2),
        "profit_factor": round(_f(m.get("profit_factor")), 2),
        "best_trade_usd": round(_f(m.get("best_trade")), 2),
        "worst_trade_usd": round(_f(m.get("worst_trade")), 2),
        "max_drawdown_pct": round(_f(m.get("max_drawdown_pct")), 2),
        "avg_duration_minutes": round(_f(m.get("avg_duration_minutes")), 1),
    }


# --- tools -------------------------------------------------------------

def tool_query_trades(
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    tag: Optional[str] = None,
    session: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Filtered closed-trade stats. All filters optional; omit for the whole book."""
    df = _closed_trades()
    if df.empty:
        return {"n": 0, "note": "No closed trades recorded."}

    applied: Dict[str, Any] = {}
    if symbol:
        sym = str(symbol).upper().strip()
        df = df[df["symbol"].astype(str).str.upper() == sym]
        applied["symbol"] = sym
    if direction:
        d = str(direction).lower().strip()
        if d in ("buy", "long"):
            d = "BUY"
        elif d in ("sell", "short"):
            d = "SELL"
        else:
            d = d.upper()
        df = df[df["direction"].astype(str).str.upper() == d]
        applied["direction"] = d
    if tag:
        tg = str(tag).strip()
        df = df[df["setup_tag"].astype(str).str.strip().str.lower() == tg.lower()]
        applied["tag"] = tg
    if session:
        se = str(session).lower().strip()
        if se not in _SESSIONS:
            return {"error": f"Unknown session '{session}'. Use one of: {', '.join(_SESSIONS)}."}
        df = df[_session_mask(df, se)]
        applied["session"] = f"{se} (UTC entry-hour {_SESSIONS[se][0]:02d}-{_SESSIONS[se][1]:02d})"
    if date_from:
        try:
            start = pd.to_datetime(date_from, utc=True)
            df = df[df["exit_time"] >= start]
            applied["date_from"] = start.date().isoformat()
        except Exception:
            return {"error": f"Bad date_from '{date_from}' — use ISO YYYY-MM-DD."}
    if date_to:
        try:
            end = pd.to_datetime(date_to, utc=True) + timedelta(days=1)
            df = df[df["exit_time"] < end]
            applied["date_to"] = (end - timedelta(days=1)).date().isoformat()
        except Exception:
            return {"error": f"Bad date_to '{date_to}' — use ISO YYYY-MM-DD."}

    if df.empty:
        return {"n": 0, "filters": applied, "note": "No trades match those filters."}

    out = _metrics_subset(df)
    out["filters"] = applied
    by_sym = (
        df.groupby(df["symbol"].astype(str).str.upper())["net_profit"]
        .agg(["count", "sum"])
        .sort_values("count", ascending=False)
        .head(8)
    )
    out["by_symbol"] = [
        {"symbol": k, "trades": int(r["count"]), "net_pnl_usd": round(_f(r["sum"]), 2)}
        for k, r in by_sym.iterrows()
    ]
    return out


def tool_analytics_period(window: str = "month") -> Dict[str, Any]:
    """Trading performance over a rolling window: today | week | month | quarter | year | all."""
    w = str(window or "month").lower().strip()
    if w not in _WINDOWS:
        return {"error": f"Unknown window '{window}'. Use one of: {', '.join(sorted(_WINDOWS))}."}
    df = _closed_trades()
    if df.empty:
        return {"window": w, "n": 0, "note": "No closed trades recorded."}
    now = datetime.now(timezone.utc)
    start = _window_start(w, now)
    if start is not None:
        df = df[df["exit_time"] >= start]
    if df.empty:
        return {"window": w, "n": 0, "note": f"No trades closed in the last {w}."}
    out = _metrics_subset(df)
    out["window"] = w
    out["since"] = start.date().isoformat() if start else "inception"
    return out


def tool_tag_record(tag: Optional[str] = None) -> Dict[str, Any]:
    """Realised record per setup tag (win rate + net-P&L expectancy). Omit `tag` for all tags."""
    df = _closed_trades()
    if df.empty:
        return {"tags": [], "note": "No closed trades recorded."}
    rows: Dict[str, Dict[str, Any]] = {}
    for _, r in df.iterrows():
        tg = (_s(r.get("setup_tag")) or "").strip()
        if not tg:
            continue
        net = _f(r.get("net_profit"))
        s = rows.setdefault(tg, {"tag": tg, "n": 0, "wins": 0, "net_total": 0.0})
        s["n"] += 1
        s["net_total"] += net
        if net > 0:
            s["wins"] += 1
    result = []
    for s in rows.values():
        n = s["n"]
        result.append({
            "tag": s["tag"],
            "n": n,
            "wins": s["wins"],
            "win_rate_pct": round(100.0 * s["wins"] / n, 1) if n else None,
            "net_total_usd": round(s["net_total"], 2),
            "expectancy_usd": round(s["net_total"] / n, 2) if n else None,
        })
    result.sort(key=lambda x: x["n"], reverse=True)
    if tag:
        tg = str(tag).strip().lower()
        match = [r for r in result if r["tag"].lower() == tg]
        if not match:
            return {"tag": tag, "n": 0, "note": f"No closed trades tagged '{tag}'."}
        return match[0]
    return {"tags": result}


def tool_macro_scorecard(instrument: str) -> Dict[str, Any]:
    """EdgeFinder-style macro scorecard for one instrument (composite bias + category reads)."""
    from api import macro_scorecard

    inst = str(instrument or "").upper().strip()
    if not inst:
        return {"error": "instrument is required."}
    if inst not in macro_scorecard.SUPPORTED_INSTRUMENTS:
        return {
            "error": f"'{inst}' not supported.",
            "supported": macro_scorecard.SUPPORTED_INSTRUMENTS,
        }
    try:
        d = macro_scorecard.get_scorecard(inst, with_market=True)
    except Exception as exc:
        return {"error": f"scorecard unavailable: {type(exc).__name__}"}
    if not d.get("available", True) and d.get("state"):
        return {"instrument": inst, "state": d.get("state"), "reason": d.get("reason")}

    cats = d.get("categories") or []
    cat_out = {}
    for c in cats:
        if not isinstance(c, dict):
            continue
        key = c.get("category") or c.get("name")
        if not key:
            continue
        cat_out[key] = {
            "score": c.get("score"),
            "direction": c.get("direction") or c.get("bias") or c.get("label"),
            "state": c.get("state"),
            "basis": c.get("basis"),
        }
    pb = d.get("price_behavior") or None
    return {
        "instrument": inst,
        "composite_score": d.get("composite_score"),
        "gauge": d.get("gauge"),
        "bias": d.get("bias"),
        "direction": d.get("direction"),
        "confidence": d.get("confidence"),
        "state": d.get("state"),
        "read_basis": d.get("read_basis"),
        "scope_note": d.get("scope_note"),
        "categories": cat_out,
        "price_behavior": (
            {
                "realized_vol_pct": pb.get("realized_vol_pct"),
                "regime": pb.get("regime"),
                "avg_daily_move_recent_pct": pb.get("avg_daily_move_recent_pct"),
                "avg_daily_move_window_pct": pb.get("avg_daily_move_window_pct"),
            }
            if isinstance(pb, dict)
            else None
        ),
        "as_of": d.get("timestamp") or d.get("as_of"),
    }


def tool_journal_search(query: str) -> Dict[str, Any]:
    """Full-text search over journal notes/ideas and per-trade journal notes."""
    q = str(query or "").strip().lower()
    if len(q) < 2:
        return {"error": "query must be at least 2 characters."}
    hits: List[Dict[str, Any]] = []

    try:
        for e in database.list_journal_entries():
            hay = " ".join(
                str(e.get(k) or "") for k in ("kind", "instrument", "title", "body")
            ) + " " + " ".join(e.get("tags") or [])
            if q in hay.lower():
                hits.append({
                    "type": "note",
                    "id": e.get("id"),
                    "kind": e.get("kind"),
                    "instrument": e.get("instrument"),
                    "title": e.get("title"),
                    "excerpt": (str(e.get("body") or "")[:280]) or None,
                    "tags": e.get("tags") or [],
                    "updated_at": e.get("updated_at"),
                })
            if len(hits) >= _MAX_ROWS:
                break
    except Exception:
        pass

    if len(hits) < _MAX_ROWS:
        df = _closed_trades()
        if not df.empty and "notes" in df.columns:
            for _, r in df.iterrows():
                note = _s(r.get("notes"))
                tg = _s(r.get("setup_tag"))
                hay = f"{note or ''} {tg or ''} {r.get('symbol') or ''}".lower()
                if note and q in hay:
                    hits.append({
                        "type": "trade_note",
                        "trade_id": _s(r.get("trade_id")),
                        "symbol": _s(r.get("symbol")),
                        "direction": _s(r.get("direction")),
                        "setup_tag": tg,
                        "net_pnl_usd": round(_f(r.get("net_profit")), 2),
                        "exit_time": r["exit_time"].isoformat() if pd.notna(r["exit_time"]) else None,
                        "excerpt": note[:280],
                    })
                if len(hits) >= _MAX_ROWS:
                    break

    return {"query": query, "count": len(hits), "results": hits[:_MAX_ROWS]}


# --- registry + dispatch ---------------------------------------------

_TOOLS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "query_trades": tool_query_trades,
    "analytics_period": tool_analytics_period,
    "tag_record": tool_tag_record,
    "macro_scorecard": tool_macro_scorecard,
    "journal_search": tool_journal_search,
}


def tool_names() -> List[str]:
    return sorted(_TOOLS)


def dispatch(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run one allowlisted read-only tool. Raises KeyError for an unknown name;
    returns `{"error": ...}` for bad arguments rather than raising."""
    fn = _TOOLS.get(str(name))
    if fn is None:
        raise KeyError(f"Unknown tool '{name}' (allowed: {', '.join(tool_names())})")
    clean = {k: v for k, v in (args or {}).items() if v is not None and v != ""}
    try:
        return fn(**clean)
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}


def gemini_tool_declarations() -> List[Any]:
    """The tool schema handed to Gemini. Built lazily so importing this module
    does not require the google-genai SDK."""
    from google.genai import types

    T = types.Type
    S = types.Schema

    def obj(props: Dict[str, Any], required: Optional[List[str]] = None) -> Any:
        return S(type=T.OBJECT, properties=props, required=required or [])

    decls = [
        types.FunctionDeclaration(
            name="query_trades",
            description=(
                "Filtered stats over the user's CLOSED trades: count, win rate, "
                "expectancy, avg win/loss, profit factor, P&L by symbol. Every "
                "argument is optional — omit all for the whole book."
            ),
            parameters=obj({
                "symbol": S(type=T.STRING, description="e.g. EURUSD, XAUUSD"),
                "direction": S(type=T.STRING, description="buy/long or sell/short"),
                "tag": S(type=T.STRING, description="setup tag exactly as logged"),
                "session": S(type=T.STRING, description="asia | london | newyork (coarse UTC entry-hour buckets)"),
                "date_from": S(type=T.STRING, description="ISO date YYYY-MM-DD, inclusive"),
                "date_to": S(type=T.STRING, description="ISO date YYYY-MM-DD, inclusive"),
            }),
        ),
        types.FunctionDeclaration(
            name="analytics_period",
            description="Trading performance over a rolling window.",
            parameters=obj({
                "window": S(type=T.STRING, description="today | week | month | quarter | year | all"),
            }, required=["window"]),
        ),
        types.FunctionDeclaration(
            name="tag_record",
            description=(
                "The user's realised record on a setup tag (win rate + net-P&L "
                "expectancy). Omit `tag` to list every tag."
            ),
            parameters=obj({
                "tag": S(type=T.STRING, description="setup tag; omit for all tags"),
            }),
        ),
        types.FunctionDeclaration(
            name="macro_scorecard",
            description=(
                "EdgeFinder-style macro scorecard for one instrument: composite "
                "bias, per-category reads (growth/jobs/inflation/rates/etc), and "
                "recent price behaviour. Macro CONTEXT only, never a trade signal."
            ),
            parameters=obj({
                "instrument": S(type=T.STRING, description="EURUSD, USDJPY, XAUUSD, DXY, US10Y, JP225, BTCUSD, ETHUSD, ..."),
            }, required=["instrument"]),
        ),
        types.FunctionDeclaration(
            name="journal_search",
            description="Search the user's journal notes/ideas and per-trade notes for a phrase.",
            parameters=obj({
                "query": S(type=T.STRING, description="text to search for"),
            }, required=["query"]),
        ),
    ]
    return [types.Tool(function_declarations=decls)]
