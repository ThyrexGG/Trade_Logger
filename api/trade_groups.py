# -*- coding: utf-8 -*-
"""
Partial closes: fold them into the trade they belong to.

A position that is scaled out of (take some off at 1R, move the stop to break-even, close the rest) reaches
`closed_trades` in two different shapes depending on the broker:

* Capital.com reports every partial close as its own transaction, all sharing the position's deal id. They are
  stored as separate rows: ``<deal>``, ``<deal>_1``, ``<deal>_2`` ... (the suffix is only a de-duplication number).
  Left alone, one trade shows up as several unrelated "trades" that each need notes and a tag.
* MT5 already merges a position into ONE row when its last lot closes (volume-weighted exit price), so the
  partials are invisible even though every exit deal is kept in `raw_deals`.

`collapse_positions` turns either shape into one entry per position: the row of the LAST exit is the main trade
(it carries the notes, tag and screenshots), its net/commission/swap are the position's totals, and `legs`
lists every exit in time order, the earlier ones labelled "partial" and the last one "final". A position that is
still open in the broker is labelled all-partial with `position_open` set.

Read-only: nothing here writes to the database.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Optional, Set

import pandas as pd

import database
import tenant

# Capital.com deal ids are UUID-shaped, MT5 trade ids are "<user>:MT5_<account>_<ticket>". Only the former carry the
# "_<n>" duplicate suffix, so the pattern must not be loosened to "anything ending in _digits".
CAPITAL_DEAL = re.compile(r"^(?P<base>[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?:_(?P<n>\d+))?$", re.IGNORECASE)

# Fields copied from a sibling leg into the main trade when the main one has none (an older note left on a partial).
_ANNOTATIONS = ("notes", "setup_tag", "rating", "chart_snapshot_url")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def _text(value: Any) -> str:
    return "" if value is None or (isinstance(value, float) and value != value) else str(value)


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and value != value) or str(value).strip() in ("", "0")


def _time_key(value: Any) -> float:
    ts = pd.to_datetime(_text(value), errors="coerce", utc=True, format="mixed")
    return float(ts.timestamp()) if not pd.isna(ts) else 0.0


def capital_base(trade_id: str) -> Optional[str]:
    m = CAPITAL_DEAL.match(trade_id or "")
    return m.group("base").lower() if m else None


def _leg(row: Dict[str, Any], n: int, final: bool, with_fill: bool) -> Dict[str, Any]:
    return {
        "trade_id": _text(row.get("trade_id")) or None,
        "n": n,
        "kind": "final" if final else "partial",
        "time": _text(row.get("exit_time")),
        # Capital.com repeats the LAST exit's size and price on every partial row, so only the final leg's fill is
        # trustworthy there; the partials keep just their time and P&L.
        "volume": _num(row.get("volume")) if with_fill else None,
        "price": _num(row.get("exit_price")) if with_fill else None,
        "net": round(_num(row.get("net_profit")), 2),
    }


def _fold_capital(group: List[Dict[str, Any]], is_open: bool) -> Dict[str, Any]:
    group = sorted(group, key=lambda r: (_time_key(r.get("exit_time")), _text(r.get("trade_id"))))
    main = dict(group[-1])
    legs = [_leg(r, i + 1, final=(i == len(group) - 1 and not is_open), with_fill=(i == len(group) - 1 and not is_open)) for i, r in enumerate(group)]
    for field in ("net_profit", "gross_profit", "commission", "swap"):
        main[field] = round(sum(_num(r.get(field)) for r in group), 2)
    for field in _ANNOTATIONS:
        if _blank(main.get(field)):
            donor = next((r for r in reversed(group[:-1]) if not _blank(r.get(field))), None)
            if donor is not None:
                main[field] = donor.get(field)
    main["legs"] = legs
    main["position_open"] = is_open
    return main


def folded_dataframe(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """`df` (a `closed_trades` frame, any tenant) with Capital.com partial-close rows folded into one
    row per position — same columns and dtypes, so it drops straight into any pandas-based stat over
    closed trades (win rate, daily P&L, symbol/tag breakdown, calendar counts) without that stat's own
    code changing. MT5 already stores one row per position, so this only touches Capital's `<deal>_N`
    duplicate rows; a still-open position's partials so far are folded too (their sum is correct either
    way). Net-P&L sums are unaffected by folding either way, only the trade/win/loss COUNTS are.

    One behavior change worth knowing: a position is now dated and located by its LAST exit, so a scale
    -out that started on one day and finished on the next now shows its whole P&L on the finishing day,
    where each partial used to count on the day it actually happened. In your data every partial closes
    within the same day, so this only matters if that changes."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    folded = collapse_positions(df.to_dict("records"))
    for r in folded:
        r.pop("legs", None)
        r.pop("position_open", None)
    return pd.DataFrame(folded, columns=df.columns)


def _open_capital_bases(open_ids: Iterable[str]) -> Set[str]:
    out: Set[str] = set()
    for pid in open_ids:
        pid = str(pid or "")
        base = capital_base(pid[4:] if pid.startswith("CAP_") else pid)
        if base:
            out.add(base)
    return out


def collapse_positions(
    rows: List[Dict[str, Any]],
    open_position_ids: Iterable[str] = (),
    mt5_legs: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    """One dict per position, in the order of the main rows in `rows`. Rows that are not partials come back
    unchanged apart from `legs` = [] and `position_open` = False."""
    open_bases = _open_capital_bases(open_position_ids)
    mt5_legs = mt5_legs or {}
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in rows:
        base = capital_base(_text(r.get("trade_id")))
        if base:
            groups.setdefault((_text(r.get("account_id")), base), []).append(r)

    out: List[Dict[str, Any]] = []
    done: Set[tuple] = set()
    for r in rows:
        tid = _text(r.get("trade_id"))
        base = capital_base(tid)
        if base:
            key = (_text(r.get("account_id")), base)
            group = groups[key]
            is_open = base in open_bases
            if len(group) == 1 and not is_open:
                out.append({**r, "legs": [], "position_open": False})
                continue
            if key in done:
                continue
            done.add(key)
            out.append(_fold_capital(group, is_open))
        else:
            out.append({**r, "legs": mt5_legs.get(tid, []), "position_open": False})
    # rows were sorted newest-exit-first by the loader; a folded group is emitted at its FIRST-seen row, which is its
    # newest leg, so the order is preserved. A hand-built input order is respected as given.
    return out


# ---------------------------------------------------------------------------------------------------------------
# MT5: the partials live in raw_deals
# ---------------------------------------------------------------------------------------------------------------
def mt5_partial_legs(trade_ids: Iterable[str]) -> Dict[str, List[Dict[str, Any]]]:
    """{trade_id: legs} for the current tenant's MT5 trades that were closed in more than one piece. Only positions
    with more than two deals can have been (entry + at least two exits), so the scan is one cheap GROUP BY."""
    wanted = {t for t in trade_ids if t and not capital_base(t)}
    if not wanted:
        return {}
    uid = tenant.current_user_id()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"SELECT position_id FROM raw_deals WHERE user_id = {ph} GROUP BY position_id HAVING COUNT(*) > 2", (uid,))
        multi = [r[0] for r in cur.fetchall() if r[0] in wanted]
        deals: Dict[str, List[tuple]] = {p: [] for p in multi}
        for i in range(0, len(multi), 500):
            batch = multi[i:i + 500]
            marks = ", ".join([ph] * len(batch))
            cur.execute(
                f"SELECT position_id, type, volume, price, commission, swap, profit, timestamp FROM raw_deals "
                f"WHERE user_id = {ph} AND position_id IN ({marks}) ORDER BY position_id ASC, timestamp ASC",
                (uid, *batch),
            )
            for row in cur.fetchall():
                deals[row[0]].append(row[1:])
    finally:
        conn.close()
    return {pid: legs for pid, legs in ((p, _mt5_position_legs(d)) for p, d in deals.items()) if legs}


def _mt5_position_legs(deals: List[tuple]) -> List[Dict[str, Any]]:
    """Exit legs of one position from its deals (type, volume, price, commission, swap, profit, timestamp), oldest
    first. The entry side's fees are spread over the exits by volume so the legs add up to the trade's net."""
    if not deals:
        return []
    entry_side = deals[0][0]
    entries = [d for d in deals if d[0] == entry_side]
    exits = [d for d in deals if d[0] != entry_side]
    entry_vol = sum(_num(d[1]) for d in entries)
    if len(exits) < 2 or entry_vol <= 0:
        return []
    entry_fees = sum(_num(d[3]) + _num(d[4]) for d in entries)
    legs = []
    for i, (_t, vol, price, comm, swap, profit, ts) in enumerate(exits):
        net = _num(profit) + _num(comm) + _num(swap) + entry_fees * (_num(vol) / entry_vol)
        legs.append({
            "trade_id": None,
            "n": i + 1,
            "kind": "final" if i == len(exits) - 1 else "partial",
            "time": pd.Timestamp(int(ts), unit="s", tz="UTC").isoformat(),
            "volume": _num(vol),
            "price": _num(price),
            "net": round(net, 2),
        })
    return legs


# ---------------------------------------------------------------------------------------------------------------
# Loaders (current tenant)
# ---------------------------------------------------------------------------------------------------------------
def _open_ids() -> List[str]:
    try:
        df = database.get_open_positions(ttl_sec=5.0)
    except Exception:  # noqa: BLE001 - grouping must never break the journal
        return []
    if df is None or df.empty or "position_id" not in df.columns:
        return []
    return [str(p) for p in df["position_id"].tolist()]


def load_positions(df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    """The tenant's closed-trades frame as one dict per position (newest first, as the frame is)."""
    if df is None or df.empty:
        return []
    rows = df.to_dict("records")
    try:
        legs = mt5_partial_legs(_text(r.get("trade_id")) for r in rows)
    except Exception:  # noqa: BLE001
        legs = {}
    return collapse_positions(rows, _open_ids(), legs)


def position_for(row: Dict[str, Any]) -> Dict[str, Any]:
    """The position that `row` (one closed_trades row of the current tenant) belongs to, folded. Reads only that
    position's rows, so it is cheap enough to call after every journal edit."""
    tid = _text(row.get("trade_id"))
    base = capital_base(tid)
    if not base:
        return collapse_positions([row], (), mt5_partial_legs([tid]))[0]
    uid = tenant.current_user_id()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        # `base` is hex digits and hyphens only, so it holds no LIKE wildcard; the exact match is re-checked below.
        cur.execute(
            f"SELECT * FROM closed_trades WHERE user_id = {ph} AND account_id = {ph} AND LOWER(trade_id) LIKE {ph}",
            (uid, _text(row.get("account_id")), base + "%"),
        )
        cols = [c[0] for c in cur.description]
        siblings = [r for r in (dict(zip(cols, x)) for x in cur.fetchall()) if capital_base(_text(r.get("trade_id"))) == base]
    finally:
        conn.close()
    siblings = siblings or [row]
    folded = collapse_positions(siblings, _open_ids())
    return next((p for p in folded if p.get("trade_id") == tid or any(l.get("trade_id") == tid for l in p["legs"])), folded[0])
