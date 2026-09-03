# -*- coding: utf-8 -*-
"""
Phase 62 — PostgreSQL connection-pool correctness tests.

The normal suite runs against SQLite (`PYTEST_CURRENT_TEST` forces the SQLite
path), so the pool code never executes there. These tests drive the Postgres
branch of `database.get_connection()` with a fake `ThreadedConnectionPool` and a
fake connection, verifying:

  * connections are reused, not reconnected
  * `.close()` returns a connection to the pool instead of tearing down the socket
  * double `.close()` is safe
  * the proxy transparently delegates cursor / commit / rollback
  * an idle connection is revalidated (`SELECT 1`) before reuse
  * a dead connection is discarded and another is handed out
  * pool exhaustion falls back to a direct connection (the caller never fails)
  * `close_all_pools()` tears everything down

No real database or network is involved.
"""
import sqlite3

import psycopg2.pool
import pytest

import database


# --- fakes -------------------------------------------------------------

class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._result = None

    def execute(self, sql, params=None):
        self.conn.executed.append(sql)
        if self.conn.fail_on_execute:
            raise RuntimeError("simulated dead connection")
        if "SELECT 1" in sql:
            self._result = (1,)

    def fetchone(self):
        return self._result

    def close(self):
        pass


class FakeConn:
    def __init__(self):
        self.closed = 0
        self.commits = 0
        self.rollbacks = 0
        self.executed = []
        self.fail_on_execute = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = 1


class FakePool:
    def __init__(self, minconn, maxconn, dsn=None):
        self.minconn = minconn
        self.maxconn = maxconn
        self.dsn = dsn
        self._all = [FakeConn() for _ in range(max(minconn, 1))]
        self._free = list(self._all)
        self.closeall_called = False
        self.putconn_calls = 0

    def getconn(self):
        if self._free:
            return self._free.pop(0)
        if len(self._all) < self.maxconn:
            c = FakeConn()
            self._all.append(c)
            return c
        raise psycopg2.pool.PoolError("connection pool exhausted")

    def putconn(self, conn, close=False):
        self.putconn_calls += 1
        if close:
            conn.close()
            return
        self._free.append(conn)

    def closeall(self):
        for c in self._all:
            c.close()
        self.closeall_called = True


@pytest.fixture
def pg_pool(monkeypatch):
    """Force the Postgres path with a fake pool; restore global state after."""
    monkeypatch.setattr(database, "get_db_url", lambda: "postgresql://fake/db")
    monkeypatch.setattr(psycopg2.pool, "ThreadedConnectionPool", FakePool)

    direct = []

    def _fake_direct():
        c = FakeConn()
        direct.append(c)
        return c

    monkeypatch.setattr(database, "_raw_pg_connect", _fake_direct)

    database.close_all_pools()
    for k in database._POOL_STATS:
        database._POOL_STATS[k] = 0
    monkeypatch.setenv("DB_POOL_ENABLED", "1")
    monkeypatch.setenv("DB_POOL_MIN", "1")
    monkeypatch.setenv("DB_POOL_MAX", "3")
    monkeypatch.delenv("DB_POOL_IDLE_PING", raising=False)

    yield {"direct": direct}

    database.close_all_pools()


# --- tests -----------------------------------------------------------------

def test_reuses_same_connection(pg_pool):
    c1 = database.get_connection()
    raw1 = object.__getattribute__(c1, "_conn")
    c1.close()
    c2 = database.get_connection()
    raw2 = object.__getattribute__(c2, "_conn")
    c2.close()
    assert raw1 is raw2
    assert database.pool_stats()["reused"] >= 1


def test_close_returns_to_pool_not_socket(pg_pool):
    c = database.get_connection()
    raw = object.__getattribute__(c, "_conn")
    c.close()
    assert raw.closed == 0  # not torn down
    assert database.pool_stats()["returned"] == 1


def test_double_close_is_safe(pg_pool):
    pool = database._get_pg_pool()
    c = database.get_connection()
    c.close()
    c.close()
    assert pool.putconn_calls == 1


def test_proxy_delegates_cursor_commit_rollback(pg_pool):
    c = database.get_connection()
    raw = object.__getattribute__(c, "_conn")
    cur = c.cursor()
    cur.execute("INSERT INTO t VALUES (1)")
    c.commit()
    c.rollback()
    c.close()
    assert raw.commits == 1
    assert raw.rollbacks == 1
    assert "INSERT INTO t VALUES (1)" in raw.executed


def test_idle_connection_is_revalidated(pg_pool, monkeypatch):
    monkeypatch.setenv("DB_POOL_IDLE_PING", "0")  # always ping recycled conns
    database.get_connection().close()
    before = database.pool_stats()["pings"]
    c = database.get_connection()
    c.close()
    assert database.pool_stats()["pings"] == before + 1


def test_dead_connection_discarded_and_replaced(pg_pool, monkeypatch):
    monkeypatch.setenv("DB_POOL_IDLE_PING", "0")
    first = database.get_connection()
    raw = object.__getattribute__(first, "_conn")
    first.close()
    raw.fail_on_execute = True  # its revalidation SELECT 1 will now blow up

    c = database.get_connection()
    good = object.__getattribute__(c, "_conn")
    c.close()

    assert good is not raw
    assert raw.closed == 1
    assert database.pool_stats()["ping_failures"] >= 1


def test_exhaustion_falls_back_to_direct(pg_pool):
    held = [database.get_connection() for _ in range(3)]  # DB_POOL_MAX = 3
    overflow = database.get_connection()  # pool is empty + at ceiling
    # still usable
    cur = overflow.cursor()
    cur.execute("SELECT 1")
    assert cur.fetchone() == (1,)
    assert database.pool_stats()["overflow_direct"] >= 1
    assert len(pg_pool["direct"]) >= 1
    for h in held:
        h.close()
    overflow.close()


def test_close_all_pools_tears_down(pg_pool):
    pool = database._get_pg_pool()
    database.get_connection().close()
    database.close_all_pools()
    assert pool.closeall_called
    assert database.pool_stats()["pool_open"] is False


def test_sqlite_path_is_not_pooled(monkeypatch):
    monkeypatch.setattr(database, "get_db_url", lambda: None)
    conn = database.get_connection()
    try:
        assert isinstance(conn, sqlite3.Connection)
    finally:
        conn.close()


def test_disabled_flag_bypasses_pool(pg_pool, monkeypatch):
    monkeypatch.setenv("DB_POOL_ENABLED", "0")
    database.close_all_pools()
    conn = database.get_connection()
    # direct FakeConn, not the proxy
    assert isinstance(conn, FakeConn)
    conn.close()
