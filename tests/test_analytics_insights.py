# -*- coding: utf-8 -*-
"""api/insights.py — day/hour/holding-time buckets, rules-vs-results, streaks."""
import pandas as pd
from fastapi.testclient import TestClient

from api import insights
from api.main import app


def _df(rows):
    """rows: (entry 'YYYY-MM-DD HH:MM' UTC, minutes held, net, tag)."""
    out = []
    for entry, held, net, tag in rows:
        e = pd.Timestamp(entry)
        out.append({"entry_time": e, "exit_time": e + pd.Timedelta(minutes=held),
                    "duration_minutes": float(held), "net_profit": float(net), "setup_tag": tag})
    return pd.DataFrame(out)


TRADES = _df([
    ("2026-10-05 08:00", 3, 10, "By my rules"),     # Mon
    ("2026-10-05 13:00", 30, -4, "Rushed"),         # Mon
    ("2026-10-06 08:30", 90, 6, "by my rules"),     # Tue (case-insensitive)
    ("2026-10-07 22:00", 300, -8, "Bent my rules"),  # Wed
    ("2026-10-08 09:00", 0, 5, ""),                  # Thu, no holding time recorded
    ("2026-10-08 10:00", 2000, 7, "BREAKOUT"),       # Thu, an old free-text tag
])


def test_weekday_and_hour_buckets_cover_every_trade():
    out = insights.build_insights(TRADES, "UTC")
    assert [b.label for b in out.by_weekday] == list(insights.WEEKDAYS)
    assert sum(b.trades for b in out.by_weekday) == len(TRADES)
    mon = out.by_weekday[0]
    assert (mon.trades, mon.wins, mon.net_profit) == (2, 1, 6.0)
    assert len(out.by_hour) == 24 and out.by_hour[8].trades == 2


def test_times_are_bucketed_on_the_viewers_clock():
    # 22:00 UTC Wednesday is 06:00 Thursday in Manila
    out = insights.build_insights(TRADES, "Asia/Manila")
    assert out.timezone == "Asia/Manila"
    assert out.by_weekday[2].trades == 0 and out.by_weekday[3].trades == 3
    assert out.by_hour[6].trades == 1


def test_an_unknown_timezone_falls_back_to_utc():
    assert insights.build_insights(TRADES, "Not/AZone").timezone == "UTC"
    assert insights.build_insights(TRADES, None).timezone == "UTC"


def test_holding_time_buckets_leave_out_trades_with_no_time():
    out = insights.build_insights(TRADES, "UTC")
    by = {b.key: b.trades for b in out.by_hold}
    assert by == {"lt5m": 1, "5_15m": 0, "15_60m": 1, "1_4h": 1, "4_24h": 1, "gt1d": 1}
    assert out.hold_unknown == 1


def test_rules_rows_split_the_one_tap_answers():
    rows = {r.tag: r for r in insights.build_insights(TRADES, "UTC").rules}
    assert list(rows) == ["By my rules", "Bent my rules", "Rushed", "Not marked"]
    assert (rows["By my rules"].trades, rows["By my rules"].net_profit, rows["By my rules"].avg_per_trade) == (2, 16.0, 8.0)
    assert rows["Rushed"].net_profit == -4.0 and rows["Bent my rules"].net_profit == -8.0
    assert rows["Not marked"].trades == 2           # untagged + a free-text tag
    assert sum(r.trades for r in rows.values()) == len(TRADES)


def test_streaks_and_best_worst_day():
    s = insights.build_insights(TRADES, "UTC").streaks
    # by exit time: +10, -4, +6, -8 (Wed 22:00 + 5h closes Thu 03:00), +5, +7 (closes Fri)
    assert (s.longest_win, s.longest_loss) == (2, 1)
    assert (s.current_kind, s.current_count) == ("win", 2)
    # days (exit date): Mon +6, Tue +6, Thu -8+5=-3, Fri +7
    assert (s.green_days, s.red_days) == (3, 1)
    assert (s.current_day_kind, s.current_day_count) == ("win", 1)
    assert (s.longest_green_days, s.longest_red_days) == (2, 1)
    assert s.best_day.date == "2026-10-09" and s.best_day.net_profit == 7.0
    assert s.worst_day.date == "2026-10-08" and s.worst_day.net_profit == -3.0


def test_a_breakeven_trade_breaks_a_streak():
    df = _df([("2026-10-05 08:00", 5, 1, ""), ("2026-10-05 09:00", 5, 0, ""), ("2026-10-05 10:00", 5, 2, "")])
    s = insights.build_insights(df, "UTC").streaks
    assert s.longest_win == 1 and s.current_count == 1


def test_empty_population_is_all_zeros():
    out = insights.build_insights(pd.DataFrame(), "UTC")
    assert all(b.trades == 0 for b in out.by_weekday + out.by_hour + out.by_hold)
    assert out.streaks.current_kind == "none" and out.streaks.best_day is None


def test_route_returns_insights_that_reconcile_with_the_page():
    client = TestClient(app)
    d = client.get("/api/analytics/performance?tz=Europe/London").json()
    ins = d["insights"]
    assert ins["timezone"] == "Europe/London"
    assert sum(b["trades"] for b in ins["by_weekday"]) == d["matched_trades"]
    assert sum(r["trades"] for r in ins["rules"]) == d["matched_trades"]
    assert sum(b["trades"] for b in ins["by_hold"]) + ins["hold_unknown"] == d["matched_trades"]
    if d["daily_pnl"]:
        best = max(d["daily_pnl"], key=lambda x: x["net_profit"])
        assert ins["streaks"]["best_day"]["net_profit"] == best["net_profit"]


def test_route_empty_window_still_has_insights():
    d = TestClient(app).get("/api/analytics/performance?start=1990-01-01&end=1990-01-02").json()
    assert d["insights"]["streaks"]["current_kind"] == "none"
