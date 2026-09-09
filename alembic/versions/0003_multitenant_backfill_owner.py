"""multi-tenant: hand the single-user "local" rows to a real owner (W8.4)

Revision ID: 0003_multitenant_backfill_owner
Revises: 0002_multitenant_user_id
Create Date: 2026-09-08

After ``0002`` every pre-existing row is tenant ``local`` (the single-user
sentinel). When a box switches to Supabase multi-user auth, those rows should
belong to the owner's real account, not stay under ``local``.

This revision re-stamps ``user_id = 'local'`` rows to the owner id, resolved
from the ``users`` table by ``TL_OWNER_EMAIL`` (or ``-x owner_id=<uuid>``). It
is a **no-op** unless:

  * a real owner id resolves, AND
  * there are ``local`` rows to move.

So on a single-user deployment (no ``users`` row, or ``TL_OWNER_EMAIL`` unset)
running ``alembic upgrade head`` does nothing here — the app keeps working with
the ``local`` tenant. Run it once, after the owner has signed in through
Supabase, to complete the hand-over.
"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

revision: str = "0003_multitenant_backfill_owner"
down_revision: Union[str, Sequence[str], None] = "0002_multitenant_user_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES: tuple[str, ...] = (
    "raw_deals",
    "closed_trades",
    "open_positions",
    "account_metadata",
    "price_alerts",
    "journal_entries",
    "journal_screenshots",
)

LOCAL = "local"


def _resolve_owner_id(bind) -> str | None:
    xargs = context.get_x_argument(as_dictionary=True)
    if xargs.get("owner_id"):
        return xargs["owner_id"].strip()

    import os

    insp = sa.inspect(bind)
    if "users" not in insp.get_table_names():
        return None
    owner_email = (os.getenv("TL_OWNER_EMAIL") or "").strip().lower()
    if owner_email:
        row = bind.execute(
            sa.text("SELECT id FROM users WHERE lower(email) = :e"), {"e": owner_email}
        ).fetchone()
        if row:
            return row[0]
    row = bind.execute(
        sa.text("SELECT id FROM users WHERE role = 'owner' ORDER BY created_at LIMIT 1")
    ).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    if context.is_offline_mode():
        op.execute("-- 0003: data migration, needs a live DB + a real owner; run online")
        return

    bind = op.get_bind()
    owner_id = _resolve_owner_id(bind)
    if not owner_id or owner_id == LOCAL:
        return  # single-user deployment — nothing to hand over

    moved = 0
    for table in _TABLES:
        res = bind.execute(
            sa.text(f"UPDATE {table} SET user_id = :oid WHERE user_id = :loc").bindparams(
                oid=owner_id, loc=LOCAL
            )
        )
        moved += res.rowcount or 0
    op.execute(f"-- 0003: re-owned {moved} 'local' rows to {owner_id}")


def downgrade() -> None:
    raise NotImplementedError(
        "0003 hand-over is not reversible; downgrade 0002 to drop the column."
    )
