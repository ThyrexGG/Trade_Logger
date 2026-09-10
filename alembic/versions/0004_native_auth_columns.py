"""native email+password auth: password_hash on users, user_id on sessions (W10)

Revision ID: 0004_native_auth_columns
Revises: 0003_multitenant_backfill_owner
Create Date: 2026-09-10

W10 drops the external identity provider: sign-in is now first-party
email + password, invited via ``TL_SIGNUP_ALLOWLIST``.

  * ``users.password_hash`` — the per-account scrypt hash (``api/auth`` KDF).
    Null for any row created by the earlier Supabase path.
  * ``sessions.user_id`` — ties an opaque session token to an account
    (``NOT NULL DEFAULT 'local'`` keeps the single-user passphrase gate
    behaving exactly as before).

Both tables are created at runtime with ``CREATE TABLE IF NOT EXISTS`` by their
owning modules (``api/identity``, ``api/auth``), and those definitions already
include these columns — so on a box that booted the new code first this
revision is a no-op. ``ALTER TABLE IF EXISTS`` makes it safe to run before the
app has ever started too.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_native_auth_columns"
down_revision: Union[str, Sequence[str], None] = "0003_multitenant_backfill_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS password_hash TEXT")
    op.execute(
        "ALTER TABLE IF EXISTS sessions ADD COLUMN IF NOT EXISTS "
        "user_id TEXT NOT NULL DEFAULT 'local'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS sessions DROP COLUMN IF EXISTS user_id")
    op.execute("ALTER TABLE IF EXISTS users DROP COLUMN IF EXISTS password_hash")
