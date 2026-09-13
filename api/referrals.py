# -*- coding: utf-8 -*-
"""
Referral-bonus claims (self-report + owner review).

Someone who signs up with TradeLogger's 5ers referral link gets a reward
tracked here — a "free month of Pro" once that tier exists, and/or an
early-access perk once one is built. Nothing here grants either thing
automatically: there's no way to verify a signup against a small
affiliate's dashboard without a real API integration, so this is a
self-report (`claim_referral`) that the owner reviews by eye against the
5ers affiliate dashboard and marks verified/rejected (`set_claim_status`).

The reward itself is recorded as a promise, not enforced here — there is
no Pro tier or feature-flag system yet to enforce it against. Verifying a
claim is the commitment to honor it later, not the payout itself.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import database
import tenant

_claims_ready = False
_claims_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_claims_table() -> None:
    global _claims_ready
    if _claims_ready:
        return
    with _claims_lock:
        if _claims_ready:
            return
        conn = database.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS referral_claims (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    partner_id TEXT NOT NULL,
                    note TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
        _claims_ready = True


def claim_referral(partner_id: str, note: Optional[str] = None) -> Dict[str, Any]:
    """Records the current user's self-reported claim for one partner. Returns
    the existing claim untouched if they've already claimed this partner —
    never creates a duplicate, so clicking twice is harmless."""
    ensure_claims_table()
    uid = tenant.current_user_id()
    existing = get_claim(partner_id)
    if existing is not None:
        return existing

    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        claim_id = uuid.uuid4().hex
        cur.execute(
            f"INSERT INTO referral_claims (id, user_id, partner_id, note, status, created_at) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
            (claim_id, uid, partner_id, note, "pending", _now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return get_claim(partner_id)  # type: ignore[return-value]


def get_claim(partner_id: str) -> Optional[Dict[str, Any]]:
    """The current user's claim for one partner, if any."""
    ensure_claims_table()
    uid = tenant.current_user_id()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(
            f"SELECT id, user_id, partner_id, note, status, created_at, reviewed_at, reviewed_by "
            f"FROM referral_claims WHERE user_id = {ph} AND partner_id = {ph}",
            (uid, partner_id),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "id": row[0], "user_id": row[1], "partner_id": row[2], "note": row[3],
        "status": row[4], "created_at": row[5], "reviewed_at": row[6], "reviewed_by": row[7],
    }


def list_my_claims() -> List[Dict[str, Any]]:
    ensure_claims_table()
    uid = tenant.current_user_id()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(
            f"SELECT id, user_id, partner_id, note, status, created_at, reviewed_at, reviewed_by "
            f"FROM referral_claims WHERE user_id = {ph} ORDER BY created_at DESC",
            (uid,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r[0], "user_id": r[1], "partner_id": r[2], "note": r[3],
            "status": r[4], "created_at": r[5], "reviewed_at": r[6], "reviewed_by": r[7],
        }
        for r in rows
    ]


def list_all_claims(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Owner-only view (enforced by the router, not here) — every claim
    across every user, newest first, optionally filtered by status."""
    ensure_claims_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        if status:
            cur.execute(
                f"SELECT rc.id, rc.user_id, u.email, rc.partner_id, rc.note, rc.status, "
                f"rc.created_at, rc.reviewed_at, rc.reviewed_by "
                f"FROM referral_claims rc LEFT JOIN users u ON u.id = rc.user_id "
                f"WHERE rc.status = {ph} ORDER BY rc.created_at DESC",
                (status,),
            )
        else:
            cur.execute(
                "SELECT rc.id, rc.user_id, u.email, rc.partner_id, rc.note, rc.status, "
                "rc.created_at, rc.reviewed_at, rc.reviewed_by "
                "FROM referral_claims rc LEFT JOIN users u ON u.id = rc.user_id "
                "ORDER BY rc.created_at DESC"
            )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r[0], "user_id": r[1], "email": r[2], "partner_id": r[3], "note": r[4],
            "status": r[5], "created_at": r[6], "reviewed_at": r[7], "reviewed_by": r[8],
        }
        for r in rows
    ]


def set_claim_status(claim_id: str, status: str, reviewed_by: str) -> Dict[str, Any]:
    if status not in ("pending", "verified", "rejected"):
        raise ValueError(f"Invalid status: {status}")
    ensure_claims_table()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(
            f"UPDATE referral_claims SET status = {ph}, reviewed_at = {ph}, reviewed_by = {ph} "
            f"WHERE id = {ph}",
            (status, _now_iso(), reviewed_by, claim_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise ValueError(f"No such claim: {claim_id}")
        conn.commit()
    finally:
        conn.close()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(
            f"SELECT id, user_id, partner_id, note, status, created_at, reviewed_at, reviewed_by "
            f"FROM referral_claims WHERE id = {ph}",
            (claim_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return {
        "id": row[0], "user_id": row[1], "partner_id": row[2], "note": row[3],
        "status": row[4], "created_at": row[5], "reviewed_at": row[6], "reviewed_by": row[7],
    }
