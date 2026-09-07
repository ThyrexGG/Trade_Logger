# -*- coding: utf-8 -*-
"""
W6 — Alembic migrations wiring.

These tests never touch a real database. They check that the migration
environment is coherent: one linear head, the baseline is the root, env.py
resolves its URL from the app config (not alembic.ini), and it refuses to run
without a Postgres URL (the local SQLite / pytest path).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytest.importorskip("alembic")

from alembic.config import Config
from alembic.script import ScriptDirectory


def _cfg() -> Config:
    return Config(str(ROOT / "alembic.ini"))


def test_alembic_ini_has_no_hardcoded_url():
    text = (ROOT / "alembic.ini").read_text(encoding="utf-8")
    active = [
        ln for ln in text.splitlines()
        if ln.strip().startswith("sqlalchemy.url") and not ln.strip().startswith("#")
    ]
    assert active == [], f"alembic.ini must not hardcode a DB URL, found: {active}"


def test_single_linear_head():
    script = ScriptDirectory.from_config(_cfg())
    assert len(script.get_heads()) == 1, script.get_heads()


def test_baseline_is_the_root():
    script = ScriptDirectory.from_config(_cfg())
    bases = list(script.get_bases())
    assert bases == ["0001_baseline"], bases


def test_baseline_upgrade_is_noop_and_downgrade_refuses():
    script = ScriptDirectory.from_config(_cfg())
    mod = script.get_revision("0001_baseline").module
    assert mod.upgrade() is None
    with pytest.raises(NotImplementedError):
        mod.downgrade()


def test_env_refuses_without_a_postgres_url():
    """With no DATABASE_URL / ALEMBIC_DATABASE_URL, `alembic current` exits nonzero
    with a clear message rather than silently doing nothing."""
    env = {
        k: v for k, v in os.environ.items()
        if k not in ("DATABASE_URL", "ALEMBIC_DATABASE_URL")
    }
    env["USE_LOCAL_SQLITE"] = "1"
    env.pop("PYTEST_CURRENT_TEST", None)
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=90,
    )
    assert proc.returncode != 0
    assert "no DATABASE_URL" in (proc.stdout + proc.stderr)


def test_offline_sql_generation_reaches_baseline():
    """`alembic upgrade head --sql` with a dummy URL emits the baseline stamp."""
    env = dict(os.environ)
    env["ALEMBIC_DATABASE_URL"] = "postgresql://u:p@localhost/db"
    env.pop("PYTEST_CURRENT_TEST", None)
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=90,
    )
    assert proc.returncode == 0, proc.stderr
    assert "0001_baseline" in proc.stdout
    assert "alembic_version" in proc.stdout
