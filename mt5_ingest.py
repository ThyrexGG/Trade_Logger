# -*- coding: utf-8 -*-
"""
MT5 ingest — the transform/write half of an MT5 sync, with no MetaTrader5
dependency.

Two callers share this:

  * ``mt5_sync.sync_mt5``  — reads the local terminal, then hands the raw
    deals / positions / balance here (the single-user owner path, unchanged
    behaviour).
  * ``api/routers/ingest`` — a friend's ``mt5_push_agent`` POSTs the same
    payload; the request's tenant is already bound, so every write lands on
    that user's rows.

Data only. Nothing here places an order or touches the frozen execution
layer — it just reconstructs closed trades from deal history and stores a
balance / open-position snapshot.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

import database
import tenant

# MT5 deal.type: 0 = buy, 1 = sell. Anything else (balance, credit, correction,
# bonus, commission, ...) is not a trade leg and is dropped.
_TRADE_DEAL_TYPES = {0, 1}

# Reject an implausibly large single push (a misbehaving agent, not a real
# account). ~5 years of an active retail account is well under this.
MAX_DEALS_PER_PUSH = 20000


def clean_symbol(symbol: str) -> str:
    """Normalise broker/prop-firm suffixes so XAUUSD.pro and XAUUSD collapse."""
    s = str(symbol or "")
    for suffix in (".fs", ".pro", ".m", ".raw", ".std", ".ecn"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s.upper()


def _noop(_msg: str) -> None:
    pass


def _ns(uid: str, account_id: str) -> str:
    """Namespace the id-prefix by tenant.

    ``raw_deals.deal_id`` / ``closed_trades.trade_id`` / ``open_positions``
    are global primary keys. Two users on different broker servers can hold
    the same MT5 login number, so a bare ``MT5_<login>_<ticket>`` would let
    one user's push silently overwrite (or be dropped against) another's.
    Prefixing with the tenant id keeps every id globally unique.

    The single-user "local" owner keeps the historical un-prefixed ids so
    existing rows and journal links stay valid.
    """
    return account_id if uid == tenant.LOCAL_USER_ID else f"{uid}:{account_id}"


def _normalise_deal(
    d: Dict[str, Any], account_id: str, ns: str
) -> Optional[Dict[str, Any]]:
    """Coerce one incoming deal dict into the raw_deals schema, or None if it
    is not a tradeable leg. Accepts either the already-mapped form
    (``type`` = "BUY"/"SELL") or the raw MT5 form (``type`` = 0/1)."""
    raw_type = d.get("type")
    if isinstance(raw_type, str):
        t = raw_type.strip().upper()
        if t not in ("BUY", "SELL"):
            return None
    else:
        try:
            if int(raw_type) not in _TRADE_DEAL_TYPES:
                return None
        except (TypeError, ValueError):
            return None
        t = "BUY" if int(raw_type) == 0 else "SELL"

    try:
        ticket = str(d.get("deal_id") or d.get("ticket") or "").strip()
        pos = str(d.get("position_id") or d.get("position") or "").strip()
        if not ticket or not pos:
            return None
        deal_id = ticket if ticket.startswith(ns) else f"{ns}_{ticket}"
        position_id = pos if pos.startswith(ns) else f"{ns}_{pos}"
        return {
            "deal_id": deal_id,
            "account_id": account_id,
            "symbol": str(d.get("symbol") or ""),
            "type": t,
            "volume": float(d.get("volume") or 0.0),
            "price": float(d.get("price") or 0.0),
            "commission": float(d.get("commission") or 0.0),
            "swap": float(d.get("swap") or 0.0),
            "profit": float(d.get("profit") or 0.0),
            "timestamp": int(d.get("timestamp") or d.get("time") or 0),
            "position_id": position_id,
        }
    except (TypeError, ValueError):
        return None


def _normalise_position(
    p: Dict[str, Any], account_id: str, ns: str
) -> Optional[Dict[str, Any]]:
    try:
        ticket = str(p.get("position_id") or p.get("ticket") or "").strip()
        if not ticket:
            return None
        pid = ticket if ticket.startswith(ns) else f"{ns}_{ticket}"
        direction = p.get("direction")
        if direction is None:
            direction = "BUY" if int(p.get("type", 0)) == 0 else "SELL"
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "position_id": pid,
            "account_id": account_id,
            "symbol": clean_symbol(p.get("symbol")),
            "direction": str(direction).upper(),
            "volume": float(p.get("volume") or 0.0),
            "entry_price": float(p.get("entry_price") or p.get("price_open") or 0.0),
            "current_price": float(p.get("current_price") or p.get("price_current") or 0.0),
            "sl": float(p.get("sl") or 0.0),
            "tp": float(p.get("tp") or 0.0),
            "floating_pnl": float(p.get("floating_pnl") or p.get("profit") or 0.0),
            "swap": float(p.get("swap") or 0.0),
            "open_time": str(p.get("open_time") or now_iso),
            "updated_at": now_iso,
        }
    except (TypeError, ValueError):
        return None


def reconstruct_positions(
    position_ids: Iterable[str], account_id: str
) -> int:
    """Group this tenant's raw deals by position id and (re)write the fully
    closed ones into closed_trades. Returns the number written.

    FIFO by position id: the first deal sets the direction; a position is only
    emitted once its exit volume matches its entry volume.
    """
    position_ids = [p for p in dict.fromkeys(position_ids) if p]
    if not position_ids:
        return 0

    uid = tenant.current_user_id()
    conn = database.get_connection()
    cursor = conn.cursor()
    ph = database.get_sql_placeholder(conn)

    # Fetch every leg for this batch of positions in a handful of round-trips
    # (one per 500 ids) instead of one query per position — a historical
    # backfill can touch thousands of positions, and a per-position query
    # loop is what makes the ingest request time out on the free tier.
    by_pos: Dict[str, List[tuple]] = {p: [] for p in position_ids}
    try:
        for i in range(0, len(position_ids), 500):
            batch = position_ids[i:i + 500]
            marks = ", ".join([ph] * len(batch))
            cursor.execute(
                f"""
                SELECT position_id, type, volume, price, commission, swap, profit, timestamp, symbol
                FROM raw_deals
                WHERE user_id = {ph} AND position_id IN ({marks})
                ORDER BY position_id ASC, timestamp ASC
                """,
                (uid, *batch),
            )
            for row in cursor.fetchall():
                by_pos.setdefault(row[0], []).append(row[1:])
    finally:
        conn.close()

    trades_to_save: List[Dict[str, Any]] = []
    for pos_id in position_ids:
        deals = by_pos.get(pos_id) or []
        if not deals:
            continue

        first_deal_type = deals[0][0]  # "BUY" | "SELL"
        trade_direction = "LONG" if first_deal_type == "BUY" else "SHORT"
        symbol = clean_symbol(deals[0][7])

        entries: List[tuple] = []
        exits: List[tuple] = []
        total_commission = total_swap = total_profit = 0.0
        for deal_type, volume, price, commission, swap, profit, ts, _sym in deals:
            total_commission += commission
            total_swap += swap
            total_profit += profit
            (entries if deal_type == first_deal_type else exits).append(
                (volume, price, ts)
            )

        total_entry_vol = sum(e[0] for e in entries)
        total_exit_vol = sum(x[0] for x in exits)
        if total_entry_vol <= 0 or total_exit_vol < total_entry_vol * 0.999:
            # still open — do not write a closed trade yet
            continue

        avg_entry = sum(v * p for v, p, _ in entries) / total_entry_vol
        avg_exit = sum(v * p for v, p, _ in exits) / total_exit_vol
        entry_epoch = entries[0][2]
        exit_epoch = exits[-1][2]
        net_profit = total_profit + total_commission + total_swap

        trades_to_save.append(
            {
                "trade_id": pos_id,
                "account_id": account_id,
                "symbol": symbol,
                "direction": trade_direction,
                "volume": total_entry_vol,
                "entry_price": avg_entry,
                "exit_price": avg_exit,
                "commission": total_commission,
                "swap": total_swap,
                "gross_profit": total_profit,
                "net_profit": net_profit,
                "entry_time": datetime.fromtimestamp(
                    entry_epoch, tz=timezone.utc
                ).isoformat(),
                "exit_time": datetime.fromtimestamp(
                    exit_epoch, tz=timezone.utc
                ).isoformat(),
                "duration_minutes": (exit_epoch - entry_epoch) / 60.0,
                "setup_tag": None,
            }
        )

    if trades_to_save:
        database.save_closed_trades(trades_to_save)
    return len(trades_to_save)


def ingest_mt5_payload(
    account_id: str,
    *,
    balance: Optional[Dict[str, Any]] = None,
    positions: Optional[List[Dict[str, Any]]] = None,
    deals: Optional[List[Dict[str, Any]]] = None,
    logfn: Callable[[str], None] = _noop,
) -> Dict[str, Any]:
    """Persist one MT5 snapshot for the current tenant.

    ``account_id``  e.g. ``MT5_12345678`` — the caller's stable account key.
    ``balance``     {"balance", "equity", "currency"} or None.
    ``positions``   list of open-position dicts (a full snapshot) or None.
    ``deals``       list of deal-history dicts (incremental is fine) or None.

    Returns a summary dict. Raises ValueError on an obviously bad payload.
    """
    account_id = str(account_id or "").strip()
    if not account_id:
        raise ValueError("account_id is required")
    if deals and len(deals) > MAX_DEALS_PER_PUSH:
        raise ValueError(
            f"too many deals in one push ({len(deals)} > {MAX_DEALS_PER_PUSH})"
        )

    database.init_db()
    ns = _ns(tenant.current_user_id(), account_id)
    summary: Dict[str, Any] = {
        "account_id": account_id,
        "balance_saved": False,
        "open_positions": 0,
        "raw_deals": 0,
        "closed_trades": 0,
    }

    if balance:
        try:
            database.save_account_balance(
                account_id,
                float(balance.get("balance", 0.0)),
                float(balance.get("equity", 0.0)),
                str(balance.get("currency") or "USD"),
            )
            summary["balance_saved"] = True
        except (TypeError, ValueError) as exc:
            logfn(f"balance skipped: {exc}")

    if positions is not None:
        norm_pos = [
            np for np in (_normalise_position(p, account_id, ns) for p in positions) if np
        ]
        database.save_open_positions(account_id, norm_pos)
        summary["open_positions"] = len(norm_pos)

    if deals:
        norm_deals: List[Dict[str, Any]] = []
        pos_ids: set = set()
        for d in deals:
            nd = _normalise_deal(d, account_id, ns)
            if nd:
                norm_deals.append(nd)
                pos_ids.add(nd["position_id"])
        if norm_deals:
            database.save_raw_deals(norm_deals)
            summary["raw_deals"] = len(norm_deals)
            summary["closed_trades"] = reconstruct_positions(pos_ids, account_id)

    logfn(
        f"{account_id}: +{summary['raw_deals']} deals, "
        f"{summary['closed_trades']} closed trades, "
        f"{summary['open_positions']} open positions"
    )
    return summary
