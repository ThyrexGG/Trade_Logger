# -*- coding: utf-8 -*-
"""
Phase 75 — ORB v1 + VWAP v1 systematic strategy research.

Deterministic strategy logic (session / DST / opening range / breakout / stop /
target / time exit / no look-ahead / trade limits) plus the research
infrastructure (deterministic outputs, provider/manifest integrity, OOS
separation, frozen-holdout isolation). Uses synthetic bars — no full data run.
"""
import importlib
import inspect
from datetime import datetime
from zoneinfo import ZoneInfo

import phase75_orb_vwap as p

_NY = ZoneInfo("America/New_York")


def _bar(ny_dt, o, h, l, c, v=1000.0):
    return {
        "ny": __import__("pandas").Timestamp(ny_dt),
        "ny_min": ny_dt.hour * 60 + ny_dt.minute,
        "session_date": ny_dt.date(),
        "Open": float(o), "High": float(h), "Low": float(l), "Close": float(c),
        "Vol": float(v),
    }


def _session(day, specs, start=(9, 30)):
    """specs = list of (o,h,l,c[,v]); bars 15 min apart from `start` NY."""
    import pandas as pd
    out = []
    t = pd.Timestamp(datetime(day.year, day.month, day.day, start[0], start[1]), tz=_NY)
    for s in specs:
        out.append(_bar(t.to_pydatetime(), *s))
        t = t + pd.Timedelta(minutes=15)
    return out


# --- session / DST -----------------------------------------------------
def test_session_open_is_dst_aware():
    jan = datetime(2024, 1, 15, 9, 30, tzinfo=_NY).astimezone(ZoneInfo("UTC"))
    jul = datetime(2024, 7, 15, 9, 30, tzinfo=_NY).astimezone(ZoneInfo("UTC"))
    assert (jan.hour, jan.minute) == (14, 30)   # EST = UTC-5
    assert (jul.hour, jul.minute) == (13, 30)   # EDT = UTC-4
    # the module anchors on America/New_York, never a fixed UTC offset
    src = inspect.getsource(p)
    assert 'ZoneInfo("America/New_York")' in src
    assert "_SESSION_OPEN = (9, 30)" in src


def test_specs_are_frozen_and_documented():
    for spec in (p.ORB_V1_SPEC, p.VWAP_V1_SPEC):
        for key in ("session", "timeframe", "entry", "stop", "target",
                    "time_exit", "trade_limit", "costs"):
            assert key in spec and spec[key]
    assert "NR7" in p.ORB_V1_SPEC["compression_filter"]
    assert "2.5" in p.VWAP_V1_SPEC["bands"]
    assert "NOT applied" in p.VWAP_V1_SPEC["news"]  # honest limitation


# --- ORB v1 ----------------------------------------------------------
def _prior6(range_=5.0):
    # 6 wide pre-open bars so the (narrow) OR bar is NR7
    return [_bar(datetime(2024, 3, 12, 8, 0), 100, 100 + range_, 100 - range_, 100)
            for _ in range(6)]


def test_orb_opening_range_and_nr7_gate():
    day = datetime(2024, 3, 12).date()
    # OR bar 09:30 range 1.0 (narrow); breakout up at 09:45 close 101.5
    bars = _session(day, [
        (100.0, 100.5, 99.5, 100.2),   # OR bar (range 1.0)
        (100.2, 101.6, 100.1, 101.5),  # closes > OR_high 100.5 -> long signalled
        (101.5, 103.0, 101.4, 102.9),  # entry bar (next open 101.5)
        (102.9, 103.5, 102.8, 103.4),
        (103.4, 104.2, 103.3, 104.1),  # target = 101.5 + 2*(101.5-99.5)=105.5 not hit
    ] + [(104.1, 104.2, 103.9, 104.0)] * 21)
    t = p.orb_v1_session(bars, _prior6(), "XAUUSD", 0.1)
    assert t is not None
    assert t.direction == "LONG"
    assert t.entry_price == 101.5           # NEXT bar open, no look-ahead
    assert t.stop == 99.5                   # opposite OR extreme (OR_low)
    assert round(t.target, 1) == 105.5      # entry + 2R
    assert t.risk_dist == 2.0


def test_orb_nr7_filter_blocks_when_or_bar_not_narrowest():
    day = datetime(2024, 3, 12).date()
    bars = _session(day, [(100.0, 110.0, 90.0, 105.0),   # OR bar WIDE (range 20)
                          (105.0, 112.0, 104.0, 111.0)] + [(111, 112, 110, 111)] * 10)
    assert p.orb_v1_session(bars, _prior6(range_=1.0), "XAUUSD", 0.1) is None


def test_orb_one_trade_per_session_and_no_reentry():
    day = datetime(2024, 3, 12).date()
    # two separate breakouts in the session — only the first is taken
    bars = _session(day, [
        (100.0, 100.5, 99.5, 100.2),
        (100.2, 101.0, 100.1, 100.9),  # closes > 100.5 -> first breakout
        (100.9, 101.2, 99.4, 99.45),   # entry bar; then stop 99.5 hit here (low 99.4)
        (99.45, 99.6, 99.4, 99.5),
        (99.5, 100.9, 99.4, 100.8),    # another close > OR_high — must NOT re-enter
    ] + [(100.8, 101, 100.6, 100.9)] * 10)
    t = p.orb_v1_session(bars, _prior6(), "XAUUSD", 0.1)
    assert t is not None and t.exit_reason == "STOP"      # exactly one trade
    assert t.session_date == str(day)


def test_orb_time_exit_at_session_close():
    day = datetime(2024, 3, 12).date()
    bars = _session(day, [
        (100.0, 100.5, 99.5, 100.2),
        (100.2, 101.0, 100.1, 100.9),   # breakout
        (100.9, 101.1, 100.6, 100.8),   # entry
    ] + [(100.8, 101.0, 100.55, 100.8)] * 23)  # drift, never hits 99.5 or 104.9
    t = p.orb_v1_session(bars, _prior6(), "XAUUSD", 0.1)
    assert t is not None and t.exit_reason == "TIME"
    assert t.exit_price == 100.8                          # last session bar close


def test_orb_no_lookahead_future_bars_do_not_change_the_trade():
    day = datetime(2024, 3, 12).date()
    base = _session(day, [
        (100.0, 100.5, 99.5, 100.2),
        (100.2, 101.0, 100.1, 100.9),
        (100.9, 101.1, 100.6, 100.8),
    ] + [(100.8, 101.0, 100.55, 100.8)] * 8)
    t1 = p.orb_v1_session(base, _prior6(), "XAUUSD", 0.1)
    # append wildly different later bars — must not change entry/stop/target
    extended = base + [_bar(datetime(2024, 3, 12, 15, 0), 100.8, 200, 50, 60)]
    t2 = p.orb_v1_session(extended, _prior6(), "XAUUSD", 0.1)
    assert (t1.entry_price, t1.stop, t1.target) == (t2.entry_price, t2.stop, t2.target)


# --- VWAP v1 --------------------------------------------------------
def test_vwap_and_sigma_are_cumulative_session_reset():
    day = datetime(2024, 3, 12).date()
    bars = _session(day, [(100 + i * 0.0, 100.2, 99.8, 100.0, 1000) for i in range(10)])
    # flat market -> VWAP == 100, sigma ~ 0 -> no entries
    trades = p.vwap_v1_session(bars, "EURUSD", 0.0001)
    assert trades == []


def test_vwap_entry_needs_poke_and_close_back_inside():
    day = datetime(2024, 6, 3).date()
    # build a noisy first 5 bars so sigma > 0, then a deep poke that closes back inside
    specs = [(100.0, 100.8, 99.2, 100.4, 1500),
             (100.4, 101.0, 99.6, 100.1, 1400),
             (100.1, 100.6, 99.0, 99.4, 1600),
             (99.4, 100.2, 98.8, 100.0, 1500),
             (100.0, 100.5, 99.3, 99.9, 1400),
             (99.9, 100.1, 96.0, 99.7, 3000),   # low pokes far below, closes back up
             (99.7, 101.5, 99.6, 101.2, 1500),  # entry bar (next open 99.7)
             (101.2, 102.0, 100.0, 100.1, 1400)] + [(100.1, 100.3, 99.9, 100.1)] * 6
    bars = _session(day, specs)
    trades = p.vwap_v1_session(bars, "XAUUSD", 0.1)
    assert trades, "engineered poke should produce a mean-reversion entry"
    t = trades[0]
    assert t.direction == "LONG"
    # entry is the OPEN of some bar strictly after the signal (>= 5th bar) — next-bar fill
    by_time = {b["ny"].isoformat(): b for b in bars}
    assert t.entry_time in by_time and t.entry_price == by_time[t.entry_time]["Open"]
    assert bars.index(by_time[t.entry_time]) >= 5   # after warmup + a signal bar
    assert t.risk_dist > 0


def test_vwap_max_two_trades_per_session():
    src = inspect.getsource(p.vwap_v1_session)
    assert "len(trades) < 2" in src


def test_vwap_warmup_blocks_early_entries():
    src = inspect.getsource(p.vwap_v1_session)
    assert "i = 4" in src  # first entry candidate is the 5th bar


def test_vwap_no_lookahead_in_finalise():
    src = inspect.getsource(p._finalise)
    # exit walk starts at the entry bar and only moves forward
    assert "range(entry_idx, len(bars))" in src


# --- research infrastructure --------------------------------------
def test_split_is_chronological_by_session_no_overlap():
    trades = [{"session_date": f"2024-{m:02d}-01", "r_net": 0.1, "r_gross": 0.1}
              for m in range(1, 11)]  # 10 distinct session dates
    sp = p._split_by_session(trades)
    d_train = {t["session_date"] for t in sp["train"]}
    d_val = {t["session_date"] for t in sp["validation"]}
    d_oos = {t["session_date"] for t in sp["oos"]}
    assert not (d_train & d_val) and not (d_val & d_oos) and not (d_train & d_oos)
    assert max(d_train) < min(d_val) and max(d_val) < min(d_oos)   # strictly ordered


def test_metrics_shape_and_determinism():
    tr = [{"r_net": r, "r_gross": r, "bars_held": 3}
          for r in (0.5, -1.0, 2.0, -1.0, 1.0, -1.0, 0.8, -1.0)]
    a = p._metrics(tr)
    b = p._metrics(tr)
    assert a == b
    for k in ("n", "total_r", "mean_r", "median_r", "win_rate_pct", "profit_factor",
              "max_drawdown_r", "largest_loss_r", "largest_win_streak",
              "largest_loss_streak", "bars_in_market"):
        assert k in a


def test_classify_never_promotes_tiny_or_negative_samples():
    huge_pos_tiny = [{"r_net": 5.0, "r_gross": 5.0, "bars_held": 1}] * 10
    assert p._classify(huge_pos_tiny, 12)["status"] == "INSUFFICIENT_SAMPLE"
    neg = [{"r_net": -0.5, "r_gross": -0.4, "bars_held": 2,
            "session_date": f"2024-{1 + i // 25:02d}-{1 + i % 25:02d}"} for i in range(120)]
    assert p._classify(neg, 12)["status"] in ("FAILED", "UNCERTAIN", "EXPLORATORY")
    assert p._classify(neg, 12)["status"] != "CANDIDATE"


def test_no_execution_or_broker_imports():
    src = inspect.getsource(p)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
                "order_execution", "live_trading", "live_automation"):
        assert bad not in src


def test_frozen_holdout_is_never_read():
    src = inspect.getsource(p)
    for bad in ("LOCKED_HISTORICAL_BASELINE", "forward_accumulation", "forward_validator",
                "HistoricalVsForwardComparator"):
        assert bad not in src


def test_frozen_hash_and_safety_flags_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine as E
    assert E.LIVE_AUTOMATION_ENABLED is False
    assert E.LIVE_BROKER_TRANSMISSION == "BLOCKED"


def test_multiple_comparison_count_is_12_primary(monkeypatch):
    # stub run_instrument so no data run happens
    def _stub(inst):
        return {"instrument": inst, "state": "OK", "sessions": 100,
                "coverage": {"first_session": "2024-01-01", "last_session": "2024-12-31",
                             "bars": 1000, "source": ["mt5"]},
                "orb_trades": [], "vwap_trades": []}
    monkeypatch.setattr(p, "run_instrument", _stub)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    res = p.run(("XAUUSD", "USDJPY", "EURUSD", "GBPUSD", "GBPJPY", "AUDJPY"))
    assert res.n_primary_hypotheses == 12
    assert res.multiple_testing["bonferroni_alpha"] == round(0.05 / 12, 6)
    assert res.verdict in ("NO_EDGE_CONFIRMED", "EXPLORATORY / INCONCLUSIVE",
                           "CANDIDATE(S) IDENTIFIED")
    assert res.frozen_contract_hash == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_result_is_reproducible(monkeypatch):
    def _stub(inst):
        base = datetime(2024, 1, 1)
        trades = []
        import pandas as pd
        for k in range(200):
            sd = (base + pd.Timedelta(days=k)).date()
            trades.append({"strategy": "orb_v1", "instrument": inst,
                           "session_date": str(sd), "direction": "LONG",
                           "entry_time": str(sd), "exit_time": str(sd),
                           "entry_price": 1.0, "exit_price": 1.0, "stop": 0.99,
                           "target": 1.02, "risk_dist": 0.01,
                           "r_gross": (0.4 if k % 3 else -1.0),
                           "r_net": (0.3 if k % 3 else -1.0),
                           "exit_reason": "TARGET", "bars_held": 4})
        return {"instrument": inst, "state": "OK", "sessions": 200,
                "coverage": {}, "orb_trades": trades, "vwap_trades": []}
    monkeypatch.setattr(p, "run_instrument", _stub)
    monkeypatch.setattr(p.dataset_manifest, "get_manifest", lambda a: None)
    r1 = p.run(("XAUUSD",))
    r2 = p.run(("XAUUSD",))
    assert r1.matrix == r2.matrix
    assert r1.content_hash == r2.content_hash
    assert r1.verdict == r2.verdict


def test_module_imports_clean():
    importlib.reload(p)
    assert hasattr(p, "run") and hasattr(p, "get_result")
