# -*- coding: utf-8 -*-
"""Partial closes are folded into the trade they belong to: one journal entry per position, with its legs."""
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import database
import tenant
from api import trade_groups as tg
from api import weekly_summary as ws
from api.main import app

client = TestClient(app)

DEAL = "00000000-6287-7194-043a-633f000154c4"      # the shape of a real Capital.com deal id
ACC = "CAP1"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "groups.db")
    monkeypatch.setenv("TL_PUSH_ENABLED", "0")
    monkeypatch.setattr(database, "get_db_url", lambda: None)
    monkeypatch.setattr(database, "get_connection", lambda: sqlite3.connect(path, timeout=30))
    monkeypatch.setattr(database, "_PUSH_TABLES_READY", False)
    monkeypatch.setattr(database, "_DB_INITIALIZED", False)
    database.init_db(force=True)
    database.invalidate_db_cache()
    yield path


def _row(trade_id, net, exit_time, account=ACC, **extra):
    return {
        "trade_id": trade_id, "account_id": account, "symbol": "USDJPY", "direction": "LONG", "volume": 2300.0,
        "entry_price": 157.132, "exit_price": 157.287, "commission": 0.0, "swap": 0.0, "gross_profit": net,
        "net_profit": net, "entry_time": "2026-09-21T08:36:24.607", "exit_time": exit_time,
        "duration_minutes": 300.0, "setup_tag": None, "notes": None, "rating": 0, "chart_snapshot_url": None, **extra,
    }


def _four_part_position():
    """The real 21 Sep USDJPY trade: three partials and the last exit, newest first (as the loader returns them)."""
    return [
        _row(DEAL, 2.25, "2026-09-21T13:32:10.395", notes="same setup, testing", setup_tag="London"),
        _row(DEAL + "_1", 1.82, "2026-09-21T09:36:53.921"),
        _row(DEAL + "_2", 0.95, "2026-09-21T09:32:40.733"),
        _row(DEAL + "_3", 1.24, "2026-09-21T08:51:03.655"),
    ]


def test_four_rows_become_one_trade_with_three_partials_and_a_final_exit():
    out = tg.collapse_positions(_four_part_position())
    assert len(out) == 1
    main = out[0]
    assert main["trade_id"] == DEAL and main["notes"] == "same setup, testing" and main["setup_tag"] == "London"
    assert main["net_profit"] == 6.26 and main["gross_profit"] == 6.26
    assert [(l["n"], l["kind"], l["net"]) for l in main["legs"]] == [(1, "partial", 1.24), (2, "partial", 0.95), (3, "partial", 1.82), (4, "final", 2.25)]
    assert [l["trade_id"] for l in main["legs"]][0] == DEAL + "_3"      # legs run oldest to newest
    assert main["legs"][-1]["price"] == 157.287 and main["legs"][-1]["volume"] == 2300.0
    assert main["legs"][0]["price"] is None and main["legs"][0]["volume"] is None   # a partial's own fill is not known
    assert main["position_open"] is False


def test_other_trades_keep_their_place_and_order():
    rows = [_row("MANUAL_x", 5.0, "2026-09-22T10:00:00")] + _four_part_position() + [_row("00000000-1111-2222-3333-444444444444", -3.0, "2026-09-20T10:00:00")]
    out = tg.collapse_positions(rows)
    assert [r["trade_id"] for r in out] == ["MANUAL_x", DEAL, "00000000-1111-2222-3333-444444444444"]
    assert out[0]["legs"] == [] and out[2]["legs"] == []


def test_a_lone_capital_row_and_mt5_trade_ids_are_left_alone():
    """MT5 trade ids also end in _<digits>; they must never be mistaken for a partial-close suffix."""
    mt5 = [_row("fc7431d3b2d44a089bb8fa7b266b5f8d:MT5_263556463_1898902898", 0.5, "2026-09-14T12:56:00+00:00"),
           _row("fc7431d3b2d44a089bb8fa7b266b5f8d:MT5_263556463_1898872681", 1.8, "2026-09-14T12:54:12+00:00")]
    assert [r["legs"] for r in tg.collapse_positions(mt5)] == [[], []]
    assert tg.capital_base("fc7431d3b2d44a089bb8fa7b266b5f8d:MT5_263556463_1898902898") is None
    lone = tg.collapse_positions([_row(DEAL, 1.0, "2026-09-21T10:00:00")])
    assert lone[0]["legs"] == [] and lone[0]["net_profit"] == 1.0


def test_same_deal_id_on_another_account_is_a_different_trade():
    rows = [_row(DEAL, 1.0, "2026-09-21T10:00:00"), _row(DEAL + "_1", 2.0, "2026-09-21T09:00:00", account="OTHER")]
    assert len(tg.collapse_positions(rows)) == 2


def test_position_still_open_at_the_broker_has_only_partials():
    rows = [_row(DEAL + "_1", 0.28, "2026-09-21T07:21:20"), _row(DEAL, 0.5, "2026-09-21T07:10:00")]
    main = tg.collapse_positions(rows, open_position_ids=["CAP_" + DEAL])[0]
    assert main["position_open"] is True and main["net_profit"] == 0.78
    assert [l["kind"] for l in main["legs"]] == ["partial", "partial"]
    # ...and a lone partial of a still-open position is a partial too, not a finished trade
    lone = tg.collapse_positions([_row(DEAL, 0.5, "2026-09-21T07:10:00")], open_position_ids=["CAP_" + DEAL])[0]
    assert lone["position_open"] is True and [l["kind"] for l in lone["legs"]] == ["partial"]


def test_notes_left_on_an_older_partial_are_not_lost():
    rows = [_row(DEAL + "_1", 1.0, "2026-09-21T09:00:00"), _row(DEAL, 0.5, "2026-09-21T07:00:00", notes="took partial", rating=4)]
    main = tg.collapse_positions(rows)[0]
    assert main["trade_id"] == DEAL + "_1" and main["notes"] == "took partial" and main["rating"] == 4


def test_mt5_exit_legs_come_from_the_raw_deals_and_add_up_to_the_trade(db):
    def deal(i, typ, vol, price, comm, profit, ts, pos="MT5_1_500"):
        return {"deal_id": f"d{i}", "account_id": "MT5_1", "symbol": "XAUUSD", "type": typ, "volume": vol, "price": price,
                "commission": comm, "swap": 0.0, "profit": profit, "timestamp": ts, "position_id": pos}
    database.save_raw_deals([
        deal(1, "BUY", 0.10, 4300.0, -0.6, 0.0, 1_000),      # entry, fee on the way in
        deal(2, "SELL", 0.05, 4310.0, 0.0, 50.0, 2_000),      # partial at +1R
        deal(3, "SELL", 0.05, 4305.0, 0.0, 25.0, 3_000),      # the rest
        deal(4, "BUY", 0.10, 4300.0, 0.0, 0.0, 9_000, pos="MT5_1_600"),   # another position, one deal so far
    ])
    legs = tg.mt5_partial_legs(["MT5_1_500", "MT5_1_600"])["MT5_1_500"]
    assert [(l["kind"], l["volume"], l["price"]) for l in legs] == [("partial", 0.05, 4310.0), ("final", 0.05, 4305.0)]
    assert [l["net"] for l in legs] == [49.7, 24.7]           # each leg carries half the entry fee
    assert round(sum(l["net"] for l in legs), 2) == 74.4       # == 75 gross - 0.6 fee: the trade's own net
    assert tg.mt5_partial_legs(["MT5_1_600"]) == {}


def test_a_single_exit_mt5_position_has_no_legs(db):
    database.save_raw_deals([
        {"deal_id": "a", "account_id": "MT5_1", "symbol": "EURUSD", "type": "BUY", "volume": 1.0, "price": 1.1, "commission": 0.0, "swap": 0.0, "profit": 0.0, "timestamp": 1, "position_id": "MT5_1_7"},
        {"deal_id": "b", "account_id": "MT5_1", "symbol": "EURUSD", "type": "SELL", "volume": 1.0, "price": 1.2, "commission": 0.0, "swap": 0.0, "profit": 10.0, "timestamp": 2, "position_id": "MT5_1_7"},
    ])
    assert tg.mt5_partial_legs(["MT5_1_7"]) == {}


def _save_position():
    database.save_closed_trades([{**r, "commission": 0.0, "swap": 0.0} for r in _four_part_position()])
    database.invalidate_db_cache("closed_trades")


def test_journal_endpoint_returns_one_entry_per_position(db):
    _save_position()
    body = client.get("/api/operations/journal").json()
    assert body["total_trades"] == 1 and (body["wins"], body["losses"]) == (1, 0)
    assert body["total_net_profit"] == 6.26
    e = body["entries"][0]
    assert e["trade_id"] == DEAL and e["net_profit"] == 6.26 and len(e["legs"]) == 4 and e["position_open"] is False


def test_tag_stats_count_the_position_once(db):
    _save_position()
    body = client.get("/api/operations/journal/tag-stats").json()
    assert body["total_trades"] == 1 and body["untagged"]["n"] == 0
    assert body["tags"] == [{"tag": "London", "n": 1, "wins": 1, "win_rate": 1.0, "net_total": 6.26, "expectancy": 6.26}]


def test_saving_notes_returns_the_entry_with_its_legs_intact(db):
    _save_position()
    r = client.patch(f"/api/operations/journal/{DEAL}", json={"notes": "clean"})
    assert r.status_code == 200
    e = r.json()["entry"]
    assert e["notes"] == "clean" and e["net_profit"] == 6.26 and len(e["legs"]) == 4


def test_annotating_an_old_partial_row_id_answers_with_the_main_trade(db):
    _save_position()
    r = client.patch(f"/api/operations/journal/{DEAL}_1", json={"rating": 3})
    assert r.status_code == 200
    assert r.json()["entry"]["trade_id"] == DEAL and r.json()["entry"]["net_profit"] == 6.26


# ------------------------------------------------------------------------------------------------
# folded_dataframe: the same grouping, shaped for Analytics / Command Center / the weekly summary
# ------------------------------------------------------------------------------------------------
def test_folded_dataframe_merges_partials_and_keeps_the_frame_shape():
    df = pd.DataFrame(_four_part_position() + [_row("MANUAL_x", 5.0, "2026-09-22T10:00:00")])
    out = tg.folded_dataframe(df)
    assert list(out.columns) == list(df.columns)          # same columns, so it drops into any existing pandas code
    assert len(out) == 2 and "legs" not in out.columns and "position_open" not in out.columns
    main = out[out["trade_id"] == DEAL].iloc[0]
    assert main["net_profit"] == 6.26 and main["exit_time"] == "2026-09-21T13:32:10.395"   # dated by its last exit


def test_folded_dataframe_is_a_noop_on_a_plain_frame():
    df = pd.DataFrame([_row("MT5_1_500", 10.0, "2026-09-20T10:00:00"), _row("MANUAL_x", -2.0, "2026-09-20T11:00:00")])
    out = tg.folded_dataframe(df)
    assert out["trade_id"].tolist() == df["trade_id"].tolist() and out["net_profit"].tolist() == df["net_profit"].tolist()


def test_folded_dataframe_handles_none_and_empty():
    assert tg.folded_dataframe(None).empty
    assert tg.folded_dataframe(pd.DataFrame()).empty


def test_analytics_and_command_center_count_positions_not_partial_rows(db):
    _save_position()
    perf = client.get("/api/analytics/performance").json()
    assert perf["metrics"]["total_trades"] == 1 and perf["matched_trades"] == 1
    assert perf["metrics"]["total_net_pnl"] == 6.26
    day = client.get("/api/analytics/day", params={"date": "2026-09-21"}).json()
    assert day["count"] == 1 and day["trades"][0]["trade_id"] == DEAL and day["trades"][0]["net_profit"] == 6.26

    cc = client.get("/api/command-center/overview").json()
    assert cc["account_summary"]["all_time_trades"] == 1
    assert cc["account_summary"]["all_time_net_pnl"] == 6.26
    if cc["daily_performance"]:
        assert cc["daily_performance"]["trades"] in (0, 1)   # 1 only if "today" happens to be 2026-09-21 in this run


def test_weekly_summary_counts_one_trade_for_the_scaled_out_position(db):
    with tenant.use("alice"):
        _save_position()
        s = ws.summarize(date(2026, 9, 21) - timedelta(days=date(2026, 9, 21).weekday()))
        assert s["trades"] == 1 and s["net"] == 6.26 and s["best_trade"] == {"symbol": "USDJPY", "net": 6.26}
