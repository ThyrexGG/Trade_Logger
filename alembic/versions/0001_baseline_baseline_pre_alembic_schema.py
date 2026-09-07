"""baseline (pre-alembic schema)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-07

This is the **baseline marker** for TradeLogger's Postgres schema as it stood
when Alembic was introduced (2026-09-07, workstream W6).

The schema up to this point is built the way it always has been:

* ``database.init_db()`` — ``CREATE TABLE IF NOT EXISTS`` for the core tables
  (raw_deals, closed_trades, open_positions, account_metadata, price_alerts,
  app_settings, execution_orders, execution_audit_log, received_signals,
  journal_entries, journal_screenshots, correlation_matrix, historical_candles,
  historical_ingestion_log, research_artifacts).
* ``api.auth._ensure_sessions_table()`` — the ``sessions`` table.
* Each research module creates its own snapshot/ledger table on first use
  (``macro_intelligence_snapshots``, ``market_regime_snapshots``,
  ``xauusd_*`` audit/forward tables, ``user_terminal_preferences``, …).

That creation code stays in place — it is the source of truth for a **fresh**
database and a harmless no-op on an existing one. Alembic owns only the
*structural* changes that ``CREATE TABLE IF NOT EXISTS`` / ``ADD COLUMN IF NOT
EXISTS`` cannot express safely: renames, type/constraint changes, drops,
backfills.

Deploy flow:

* Existing Supabase DB → ``alembic stamp 0001_baseline`` once (marks this
  revision applied without running anything), then ``alembic upgrade head``.
* Brand-new DB → the app's at-boot creation builds the tables, then
  ``alembic stamp head``; subsequent revisions run via ``alembic upgrade head``.

So this revision deliberately does nothing.
"""
from typing import Sequence, Union


revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: the pre-Alembic schema is the baseline (see module docstring)."""


def downgrade() -> None:
    raise NotImplementedError(
        "0001_baseline is the earliest revision; there is nothing to downgrade to."
    )
