"""multi-tenant: add user_id to the per-user journal tables (W8.3)

Revision ID: 0002_multitenant_user_id
Revises: 0001_baseline
Create Date: 2026-09-08

Workstream W8 opens TradeLogger to a handful of invited users, each tracking
their own trades on the one instance. Seven tables hold per-user data and gain
a nullable ``user_id TEXT`` here (plus an index):

    raw_deals, closed_trades, open_positions, account_metadata,
    price_alerts, journal_entries, journal_screenshots

``NOT NULL DEFAULT 'local'`` — existing rows become tenant ``local`` (the
single-user sentinel, see ``tenant.py``), which is exactly what the data layer
(W8.4) reads and writes when no real user is bound. ``database.init_db()``
performs the identical ``ADD COLUMN`` at boot, so this revision is a no-op on a
box that has already booted the new code; it exists for operators who apply
migrations first.

New tables introduced by W8 (``users``, ``user_settings``,
``broker_connections``) follow the repo's existing pattern — created at
runtime with ``CREATE TABLE IF NOT EXISTS`` by their owning module, exactly
like ``sessions`` — so they are not created here. Alembic owns only the
structural change that ``CREATE TABLE IF NOT EXISTS`` cannot express: adding a
column to an already-populated table.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_multitenant_user_id"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
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


def upgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
            f"user_id TEXT NOT NULL DEFAULT 'local'"
        )
        op.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table} (user_id)'
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f'DROP INDEX IF EXISTS idx_{table}_user_id')
        op.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS user_id')
