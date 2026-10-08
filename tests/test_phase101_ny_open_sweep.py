# -*- coding: utf-8 -*-
"""Phase 101 engine on a hand-built day: the opening-range low is swept and
reclaimed, so RECLAIM must go long at the reclaim close, stop at the sweep
low, and take the 2R target. No MT5, no cache."""
import pandas as pd

import phase101_ny_open_sweep as p


def _day(rows):
    idx = pd.DatetimeIndex([pd.Timestamp("2026-10-07") + pd.Timedelta(hours=h, minutes=m) for h, m, *_ in rows], name="ny")
    return pd.DataFrame(
        {"open": [r[2] for r in rows], "high": [r[3] for r in rows], "low": [r[4] for r in rows],
         "close": [r[5] for r in rows], "spread": [0.5] * len(rows)},
        index=idx,
    )


def _session():
    rows = []
    # quiet pre-market so ON / LDN levels sit far away and never trigger
    for h in range(2, 9):
        for m in range(0, 60, 5):
            rows.append((h, m, 100, 101, 99, 100))
    rows += [(9, 0, 100, 101, 99, 100), (9, 5, 100, 101, 99, 100), (9, 10, 100, 101, 99, 100),
             (9, 15, 100, 101, 99, 100), (9, 20, 100, 101, 99, 100), (9, 25, 100, 101, 99, 100)]
    rows += [
        (9, 30, 100, 100.5, 99.5, 100),   # opening range 99.5 - 100.5
        (9, 35, 100, 100.2, 97.0, 98.0),  # sweeps the OR low (and the overnight low 99)
        (9, 40, 98, 99.8, 97.5, 99.7),    # closes back above 99.5 -> long at 99.7, stop 97.0 (risk 2.7)
        (9, 45, 99.7, 101, 99.6, 100.8),
        (9, 50, 100.8, 105.2, 100.7, 105),  # 2R target = 99.7 + 5.4 = 105.1 -> hit
    ]
    t = 9 * 60 + 55
    while t < 16 * 60:
        rows.append((t // 60, t % 60, 105, 105.5, 104.5, 105))
        t += 5
    return _day(rows)


def test_reclaim_long_on_opening_range_sweep():
    trades = p.backtest("NQ", "M5", _session())
    t = next(x for x in trades if x.level == "OR" and x.entry_model == "RECLAIM")
    assert t.side == "LONG"
    assert t.entry_time.endswith("09:40:00") and t.entry == 99.7
    assert t.stop == 97.0 and t.target == 105.1
    assert t.exit_reason == "target" and t.r_gross == 2.0
    # costs: spread 0.5 + market-entry slippage 0.5, none on a target exit
    assert abs(t.cost_r - 1.0 / 2.7) < 1e-3


def test_no_trade_when_the_stop_is_inside_the_spread():
    df = _session()
    df["spread"] = 2.0  # risk 2.7 < 2 x spread -> untradeable, skipped
    trades = p.backtest("NQ", "M5", df)
    assert not [x for x in trades if x.level == "OR" and x.entry_model == "RECLAIM"]
