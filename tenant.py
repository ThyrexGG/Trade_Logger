# -*- coding: utf-8 -*-
"""
Per-request tenant context (platform plan W8.4).

TradeLogger's data layer is single-table-per-concept. Multi-user isolation is a
``user_id`` column on the journal tables plus a filter on every query. Rather
than thread a ``user_id`` argument through dozens of ``database.*`` functions
and their (frozen) callers, the current user rides in a ``ContextVar`` that the
API middleware sets per request; ``database.py`` reads it as the default.

* passphrase / single-user / tests / CLI  -> the context is never set, so it
  resolves to :data:`LOCAL_USER_ID` ("local"). Every row is stamped ``local``
  and every query filters ``user_id = 'local'`` — i.e. exactly today's
  behaviour, one tenant called "local".
* supabase multi-user  -> ``api/main.py`` calls :func:`bind` with the resolved
  user id right after auth, for the duration of the request.
* the broker-sync loop (W8.6)  -> calls :func:`bind` around each user's cycle.

``ContextVar`` propagates across ``await`` and into the threadpool Starlette
uses for sync route handlers (anyio copies the context), so a plain
``database.get_closed_trades()`` deep inside a request already sees the right
tenant with no signature change.

This module imports nothing from the app — it sits below ``database`` in the
import graph to stay cycle-free.
"""
from __future__ import annotations

import contextvars
from typing import Optional

# The tenant id used whenever no real user is bound: single-user deployments,
# the test suite, offline scripts, and rows that predate multi-user.
LOCAL_USER_ID = "local"

_current: contextvars.ContextVar[str] = contextvars.ContextVar(
    "tl_current_user_id", default=LOCAL_USER_ID
)


def current_user_id() -> str:
    """The tenant every per-user row read/written in this context belongs to."""
    return _current.get() or LOCAL_USER_ID


def resolve(user_id: Optional[str]) -> str:
    """An explicit ``user_id`` wins; otherwise fall back to the bound context."""
    return user_id if user_id else current_user_id()


def bind(user_id: Optional[str]) -> contextvars.Token:
    """Bind the current tenant. Returns a token for :func:`release`."""
    return _current.set(user_id or LOCAL_USER_ID)


def release(token: contextvars.Token) -> None:
    try:
        _current.reset(token)
    except (ValueError, LookupError):
        pass


class use:  # noqa: N801 - used as a context manager: `with tenant.use(uid):`
    """`with tenant.use(user_id): ...` — bind for a block, restore on exit."""

    def __init__(self, user_id: Optional[str]):
        self._uid = user_id
        self._token: Optional[contextvars.Token] = None

    def __enter__(self) -> str:
        self._token = bind(self._uid)
        return current_user_id()

    def __exit__(self, *_exc) -> None:
        if self._token is not None:
            release(self._token)
