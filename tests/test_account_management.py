# -*- coding: utf-8 -*-
"""
Account management — list/export/remove an account's historical footprint.

Runs against the local SQLite trades.db (pytest auto-routes database.py's
get_connection() to SQLite, per the project's existing test convention).
Every test uses a uniquely-prefixed, throwaway account_id and cleans up
after itself in a finally block — this module never touches a real
production account_id in its own test suite.
"""
import json
import os

import pytest

import account_management as am
import database

database.init_db()

_TEST_ACCOUNT = "TEST_ACCTMGMT_PHASE_ACCOUNT_1"
_TEST_ACCOUNT_2 = "TEST_ACCTMGMT_PHASE_ACCOUNT_2"


def _insert_closed_trade(account_id, trade_id):
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(
            f"INSERT INTO closed_trades (trade_id, account_id, symbol, direction, volume, "
            f"entry_price, exit_price, entry_time, exit_time) VALUES "
            f"({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (trade_id, account_id, "XAUUSD", "BUY", 0.1, 2000.0, 2010.0,
             "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"))
        conn.commit()
    finally:
        conn.close()


def _insert_account_metadata(account_id):
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(
            f"INSERT INTO account_metadata (account_id, balance, equity, currency, updated_at) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph})",
            (account_id, 10000.0, 10000.0, "USD", "2026-01-01T00:00:00Z"))
        conn.commit()
    finally:
        conn.close()


def _cleanup(account_id):
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        for table in am.ACCOUNT_TABLES:
            cur.execute(f"DELETE FROM {table} WHERE account_id = {ph}", (account_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_account():
    _cleanup(_TEST_ACCOUNT)
    _insert_closed_trade(_TEST_ACCOUNT, "TEST_TRADE_1")
    _insert_account_metadata(_TEST_ACCOUNT)
    yield _TEST_ACCOUNT
    _cleanup(_TEST_ACCOUNT)


# --- A. scope discipline -------------------------------------------------------
def test_account_tables_are_exactly_the_five_with_account_id_column():
    assert set(am.ACCOUNT_TABLES) == {"closed_trades", "open_positions", "account_metadata",
                                     "raw_deals", "price_alerts"}


def test_module_never_imports_execution_or_broker_or_env_modules():
    import inspect
    import re
    src = inspect.getsource(am)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "mt5_provider", "dotenv"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"


# --- B. list_accounts ------------------------------------------------------------
def test_list_accounts_reflects_seeded_rows(seeded_account):
    accounts = am.list_accounts()
    assert seeded_account in accounts
    assert accounts[seeded_account]["closed_trades"] == 1
    assert accounts[seeded_account]["account_metadata"] == 1


def test_list_accounts_does_not_include_a_cleaned_up_account():
    _cleanup(_TEST_ACCOUNT_2)
    accounts = am.list_accounts()
    assert _TEST_ACCOUNT_2 not in accounts


# --- C. export_account (read-only) -----------------------------------------------
def test_export_account_is_read_only_and_produces_a_manifest(seeded_account, tmp_path):
    path = am.export_account(seeded_account, output_dir=str(tmp_path))
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["account_id"] == seeded_account
    assert manifest["row_counts"]["closed_trades"] == 1
    assert len(manifest["tables"]["closed_trades"]) == 1
    assert manifest["tables"]["closed_trades"][0]["trade_id"] == "TEST_TRADE_1"
    # exporting must never delete anything
    accounts_after = am.list_accounts()
    assert accounts_after[seeded_account]["closed_trades"] == 1


def test_export_account_with_no_rows_produces_an_empty_manifest(tmp_path):
    _cleanup(_TEST_ACCOUNT_2)
    path = am.export_account(_TEST_ACCOUNT_2, output_dir=str(tmp_path))
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert all(v == 0 for v in manifest["row_counts"].values())


# --- D. remove_account safety gates -----------------------------------------------
def test_remove_account_refuses_without_an_export_file(seeded_account):
    with pytest.raises(ValueError, match="not found"):
        am.remove_account(seeded_account, "this_file_does_not_exist.json")
    # nothing should have been deleted
    assert am.list_accounts()[seeded_account]["closed_trades"] == 1


def test_remove_account_refuses_a_mismatched_export_file(seeded_account, tmp_path):
    _cleanup(_TEST_ACCOUNT_2)
    _insert_account_metadata(_TEST_ACCOUNT_2)
    other_export = am.export_account(_TEST_ACCOUNT_2, output_dir=str(tmp_path))
    with pytest.raises(ValueError, match="refusing to delete"):
        am.remove_account(seeded_account, other_export)
    assert am.list_accounts()[seeded_account]["closed_trades"] == 1
    _cleanup(_TEST_ACCOUNT_2)


def test_remove_account_deletes_all_rows_after_a_matching_export(seeded_account, tmp_path):
    export_path = am.export_account(seeded_account, output_dir=str(tmp_path))
    deleted = am.remove_account(seeded_account, export_path)
    assert deleted["closed_trades"] == 1
    assert deleted["account_metadata"] == 1
    accounts_after = am.list_accounts()
    assert seeded_account not in accounts_after


def test_remove_account_is_idempotent_on_a_second_call(seeded_account, tmp_path):
    export_path = am.export_account(seeded_account, output_dir=str(tmp_path))
    am.remove_account(seeded_account, export_path)
    deleted_again = am.remove_account(seeded_account, export_path)
    assert all(v == 0 for v in deleted_again.values())
