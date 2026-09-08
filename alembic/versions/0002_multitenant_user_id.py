"""multi-tenant: add user_id to the per-user journal tables (W8.3)

Revision ID: 0002_multitenant_user_id
Revises: 0001_baseline
Create Date: 2026-09-08

Workstream W8 opens TradeLogger to a handful of invited users, each tracking
their own trades on the one instance. Seven tables hold per-user data and gain
a nullable ``user_id TEXT`` here (plus an index):

    raw_deals, closed_trades, open_positions, account_metadata,
    price_alerts, journal_entries, journal_screenshots

Nullable on purpose — existing rows are backfilled to the owner in
``0003_multitenant_backfill_owner``, and the app's data layer (W8.4) starts
writing it. A later revision tightens it to NOT NULL once every deployed path
is known to set it.

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
        op.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id TEXT')
        op.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table} (user_id)'
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f'DROP INDEX IF EXISTS idx_{table}_user_id')
        op.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS user_id')
