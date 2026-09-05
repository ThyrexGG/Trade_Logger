# -*- coding: utf-8 -*-
"""
Accounts API — GET (list) / POST (export) / DELETE (remove-with-export-gate).

Uses a uniquely-prefixed, throwaway account_id and cleans up after itself;
never touches a real production account_id.
"""
import os

from fastapi.testclient import TestClient

import database
from api.main import app

database.init_db()
client = TestClient(app)

_TEST_ACCOUNT = "TEST_ACCTMGMT_API_ACCOUNT_1"


def _cleanup(account_id):
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        for table in ("closed_trades", "open_positions", "account_metadata", "raw_deals", "price_alerts"):
            cur.execute(f"DELETE FROM {table} WHERE account_id = {ph}", (account_id,))
        conn.commit()
    finally:
        conn.close()


def _seed(account_id):
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(
            f"INSERT INTO account_metadata (account_id, balance, equity, currency, updated_at) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph})",
            (account_id, 5000.0, 5000.0, "USD", "2026-01-01T00:00:00Z"))
        conn.commit()
    finally:
        conn.close()


def test_get_accounts_lists_a_seeded_account():
    _cleanup(_TEST_ACCOUNT)
    _seed(_TEST_ACCOUNT)
    try:
        r = client.get("/api/accounts")
        assert r.status_code == 200
        assert _TEST_ACCOUNT in r.json()["accounts"]
    finally:
        _cleanup(_TEST_ACCOUNT)


def test_export_endpoint_is_read_only_and_returns_a_path():
    _cleanup(_TEST_ACCOUNT)
    _seed(_TEST_ACCOUNT)
    try:
        r = client.post(f"/api/accounts/{_TEST_ACCOUNT}/export")
        assert r.status_code == 200
        path = r.json()["export_path"]
        assert os.path.isfile(path)
        # exporting must not delete
        r2 = client.get("/api/accounts")
        assert _TEST_ACCOUNT in r2.json()["accounts"]
        os.remove(path)
    finally:
        _cleanup(_TEST_ACCOUNT)


def test_delete_endpoint_requires_a_valid_export_path():
    _cleanup(_TEST_ACCOUNT)
    _seed(_TEST_ACCOUNT)
    try:
        r = client.delete(f"/api/accounts/{_TEST_ACCOUNT}", params={"exported_file_path": "nope.json"})
        assert r.status_code == 400
        r2 = client.get("/api/accounts")
        assert _TEST_ACCOUNT in r2.json()["accounts"]   # nothing deleted
    finally:
        _cleanup(_TEST_ACCOUNT)


def test_delete_endpoint_removes_account_after_valid_export():
    _cleanup(_TEST_ACCOUNT)
    _seed(_TEST_ACCOUNT)
    try:
        export_path = client.post(f"/api/accounts/{_TEST_ACCOUNT}/export").json()["export_path"]
        r = client.delete(f"/api/accounts/{_TEST_ACCOUNT}", params={"exported_file_path": export_path})
        assert r.status_code == 200
        assert r.json()["deleted_rows"]["account_metadata"] == 1
        r2 = client.get("/api/accounts")
        assert _TEST_ACCOUNT not in r2.json()["accounts"]
        os.remove(export_path)
    finally:
        _cleanup(_TEST_ACCOUNT)


def test_delete_endpoint_never_exposed_as_a_get_or_post_mutation_without_the_gate():
    # sanity: the route requires the query param at all
    r = client.delete(f"/api/accounts/{_TEST_ACCOUNT}")
    assert r.status_code == 422  # missing required exported_file_path
