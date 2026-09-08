"""multi-tenant: backfill existing journal rows to the owner (W8.3)

Revision ID: 0003_multitenant_backfill_owner
Revises: 0002_multitenant_user_id
Create Date: 2026-09-08

Every row that predates W8 belongs to the person who has been running the
single-user instance. This revision stamps those rows (``user_id IS NULL``)
with the owner's id.

The owner is resolved from the ``users`` table by ``TL_OWNER_EMAIL`` — so the
deploy order is:

    1. ship W8.1, set TL_AUTH_MODE=supabase + TL_OWNER_EMAIL, owner signs in
       once (creates the owner's users row),
    2. then run ``alembic upgrade head``.

An explicit override is honoured for unusual cases:
``alembic -x owner_id=<uuid> upgrade head``.

If there is nothing to backfill (a fresh database) this is a no-op. If there
*are* orphan rows but no owner can be resolved, it fails loudly rather than
guessing.
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


def _resolve_owner_id(bind) -> str | None:
    # 1. explicit -x owner_id=...
    xargs = context.get_x_argument(as_dictionary=True)
    if xargs.get("owner_id"):
        return xargs["owner_id"].strip()

    # 2. users row matching TL_OWNER_EMAIL (or the single row flagged role=owner)
    import os

    owner_email = (os.getenv("TL_OWNER_EMAIL") or "").strip().lower()
    insp = sa.inspect(bind)
    if "users" not in insp.get_table_names():
        return None
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
        # Data-dependent: it counts orphan rows and looks up the owner. There is
        # nothing meaningful to emit as static SQL — run it against a live DB.
        op.execute("-- 0003 multitenant backfill: data migration, run online (no --sql)")
        return

    bind = op.get_bind()

    orphan_total = 0
    for table in _TABLES:
        n = bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE user_id IS NULL")
        ).scalar()
        orphan_total += int(n or 0)

    if orphan_total == 0:
        return  # fresh DB — nothing predates multi-tenant

    owner_id = _resolve_owner_id(bind)
    if not owner_id:
        raise SystemExit(
            f"0003 backfill: {orphan_total} rows have no user_id but no owner could "
            "be resolved. Set TL_OWNER_EMAIL and have the owner sign in once so a "
            "users row exists, or pass `-x owner_id=<uuid>`."
        )

    for table in _TABLES:
        op.execute(
            sa.text(f"UPDATE {table} SET user_id = :oid WHERE user_id IS NULL").bindparams(
                oid=owner_id
            )
        )


def downgrade() -> None:
    # Not reversible — we cannot tell which rows were NULL before the backfill.
    raise NotImplementedError(
        "0003 backfill is not reversible; downgrade 0002 to drop the column entirely."
    )
