# -*- coding: utf-8 -*-
"""
Test-suite auth isolation.

The API test suite is written against the historical "wide-open" baseline:
passphrase mode with no password configured, so `auth_enabled()` is False
and every endpoint is reachable without a session. That baseline must not
depend on whatever `TL_AUTH_MODE` a developer happens to have set in their
own local `.env` for real day-to-day use (e.g. `multiuser`, to log in as
themselves) -- several modules (database.py, alerts.py [root], ai_analysis.py,
...) each call `load_dotenv(..., override=True)` at their own import time,
so without this fixture the API test suite starts 401ing the moment a
developer switches their own login over to multiuser mode.

A one-shot correction at collection time is not enough: pytest imports test
modules across the whole `tests/` tree during collection (even ones whose
individual tests are deselected by `-k`), and a module reached for the
first time partway through that -- e.g. something pulling in the root
`alerts.py` via a path this file's own top-level import doesn't happen to
exercise -- can fire its own `load_dotenv(override=True)` after this
module's top-level code has already run, undoing the correction for every
test that follows. So this re-applies the baseline as an autouse fixture
before every single test, not just once.

A test that specifically exercises multiuser/passphrase/supabase auth
behaviour (test_stage28_native_auth.py's `mu` fixture and friends) sets
`TL_AUTH_MODE` itself via `monkeypatch`, which runs *after* this autouse
fixture (same scope, so autouse goes first) and is undone automatically at
the end of that test -- back to the baseline this file establishes, not
whatever a developer's own `.env` says.
"""
import os

import pytest

import api.main  # noqa: F401 -- forces every load_dotenv(override=True) reachable from the app's import graph to fire before the correction below


def _reset_auth_env() -> None:
    os.environ["TL_AUTH_MODE"] = "passphrase"
    os.environ.pop("TL_AUTH_PASSWORD", None)
    os.environ.pop("TL_AUTH_PASSWORD_HASH", None)
    os.environ.pop("TL_AUTH_DISABLED", None)


_reset_auth_env()  # covers collection-time pollution from this file's own import above


@pytest.fixture(autouse=True)
def _auth_baseline():
    """Re-applies the wide-open baseline before every test -- see module
    docstring for why a single correction at import time isn't sufficient."""
    _reset_auth_env()
    yield
