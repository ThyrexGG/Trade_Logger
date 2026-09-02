# -*- coding: utf-8 -*-
"""
Forex position-sizing / currency-conversion regression tests.

Root cause fixed: `calculate_pre_trade_risk_preview` (and the `evaluate_trade_risk`
per-trade risk block) treated a stop-distance P/L denominated in the pair's QUOTE
currency as if it were already USD. For USDJPY this over-stated risk by ~160x and
mis-sized the position (0.01 lots instead of ~1.10). Margin used a hardcoded 1:30
leverage on a base*price notional, which for USD-base pairs is a JPY figure.

The fix converts quote-currency P/L to USD via the canonical base/quote registry
and sizes margin off the USD notional * instrument_specs.margin_factor.
"""
import pytest

import risk_gateway as rg
from risk_gateway import (
    calculate_pre_trade_risk_preview,
    quote_ccy_to_usd_factor,
    position_risk_usd,
    position_notional_usd,
)

# The exact inputs from the confirmed UI bug report.
BUG = dict(symbol="USDJPY", side="SELL", entry_price=159.487, stop_loss=159.921,
           requested_risk_pct=3.0, account_balance=10000.0)


# --- 1. the reported bug is fixed ------------------------------------------
def test_usdjpy_bug_case_is_fixed():
    p = calculate_pre_trade_risk_preview(**BUG)
    assert p["is_valid"] is True
    assert p["errors"] == []
    # ~1.10 lots (was 0.01), risk ~ $300 / 3% (was $434 / 4.34%)
    assert p["calculated_lot_size"] == pytest.approx(1.10, abs=0.02)
    assert p["actual_risk_usd"] == pytest.approx(300.0, abs=6.0)
    assert p["actual_risk_pct"] == pytest.approx(3.0, abs=0.10)
    # margin ~ 1.10 * 100k USD notional * 0.01 factor  (was the bogus $5,316.23)
    assert p["estimated_margin_usd"] == pytest.approx(1100.0, abs=40.0)
    assert p["estimated_margin_usd"] < 2000.0


def test_usdjpy_sanity_table_per_lot():
    dist = abs(159.921 - 159.487)
    expected = {0.01: 2.71, 0.10: 27.14, 0.50: 135.69, 1.00: 271.38,
               1.10: 298.52, 1.11: 301.24}
    for lots, want in expected.items():
        got, _ = position_risk_usd("USDJPY", dist, lots, 159.487)
        # conversion referenced at entry vs the table's stop price -> ~0.3% band
        assert got == pytest.approx(want, rel=0.01), f"{lots} lots: {got} vs {want}"


# --- 2. BUY / SELL symmetry ----------------------------------------------
def test_usdjpy_buy_and_sell_size_to_target():
    sell = calculate_pre_trade_risk_preview(symbol="USDJPY", side="SELL",
        entry_price=159.487, stop_loss=159.921, requested_risk_pct=3.0, account_balance=10000.0)
    buy = calculate_pre_trade_risk_preview(symbol="USDJPY", side="BUY",
        entry_price=159.921, stop_loss=159.487, requested_risk_pct=3.0, account_balance=10000.0)
    for p in (sell, buy):
        assert p["is_valid"] is True
        assert p["actual_risk_pct"] == pytest.approx(3.0, abs=0.15)
        assert p["calculated_lot_size"] == pytest.approx(1.10, abs=0.02)


def test_usdjpy_wrong_geometry_still_flagged():
    bad = calculate_pre_trade_risk_preview(symbol="USDJPY", side="SELL",
        entry_price=159.921, stop_loss=159.487, requested_risk_pct=3.0, account_balance=10000.0)
    assert bad["is_valid"] is False
    assert any("must be strictly above" in e for e in bad["errors"])


# --- 3. USD-quoted pair (EURUSD) is untouched ---------------------------
def test_eurusd_sizing_unchanged():
    p = calculate_pre_trade_risk_preview(symbol="EURUSD", side="BUY",
        entry_price=1.0850, stop_loss=1.0800, take_profit_1=1.0950, take_profit_2=1.1000,
        requested_risk_pct=1.0, account_balance=10000.0)
    assert p["calculated_lot_size"] == 0.20
    assert p["actual_risk_usd"] == 100.0
    assert p["actual_risk_pct"] == 1.0
    assert p["reward_tp1_usd"] == 200.0
    assert p["risk_reward_ratio"] == "1:2.00"


def test_eurusd_buy_sell_symmetric():
    buy = calculate_pre_trade_risk_preview(symbol="EURUSD", side="BUY",
        entry_price=1.1000, stop_loss=1.0950, requested_risk_pct=2.0, account_balance=20000.0)
    sell = calculate_pre_trade_risk_preview(symbol="EURUSD", side="SELL",
        entry_price=1.0950, stop_loss=1.1000, requested_risk_pct=2.0, account_balance=20000.0)
    assert buy["calculated_lot_size"] == sell["calculated_lot_size"]
    assert buy["actual_risk_usd"] == sell["actual_risk_usd"] == pytest.approx(400.0, abs=1.0)


# --- 4. another USD-base pair (USDCHF) ---------------------------------
def test_usdchf_converts_via_price():
    p = calculate_pre_trade_risk_preview(symbol="USDCHF", side="BUY",
        entry_price=0.9000, stop_loss=0.8950, requested_risk_pct=1.0, account_balance=10000.0)
    # risk per lot = 0.0050 * 100000 / 0.9000 CHF->USD ~= 555.56 ; target $100 -> ~0.18 lots
    assert p["calculated_lot_size"] == pytest.approx(0.18, abs=0.02)
    assert p["actual_risk_pct"] == pytest.approx(1.0, abs=0.15)


# --- 5. conversion-factor helper ------------------------------------------
def test_quote_ccy_to_usd_factor():
    assert quote_ccy_to_usd_factor("EURUSD", 1.08)[0] == 1.0
    assert quote_ccy_to_usd_factor("XAUUSD", 2400.0)[0] == 1.0
    f, w = quote_ccy_to_usd_factor("USDJPY", 160.0)
    assert f == pytest.approx(1.0 / 160.0)
    assert w is None
    # cross pair -> best-effort estimate + a warning
    f2, w2 = quote_ccy_to_usd_factor("EURJPY", 170.0)
    assert f2 > 0 and w2 is not None


# --- 6. margin / notional --------------------------------------------
def test_notional_usd_by_pair_family():
    # USD base -> notional is lots*contract_size USD, no price multiply
    assert position_notional_usd("USDJPY", 1.0, 159.487) == pytest.approx(100_000.0)
    # USD quote -> notional is price*lots*contract_size
    assert position_notional_usd("EURUSD", 1.0, 1.0850) == pytest.approx(108_500.0)


def test_margin_uses_instrument_spec_factor():
    p = calculate_pre_trade_risk_preview(symbol="USDJPY", side="SELL",
        entry_price=159.487, stop_loss=159.921, requested_risk_pct=3.0, account_balance=10000.0)
    lots = p["calculated_lot_size"]
    assert p["estimated_margin_usd"] == pytest.approx(lots * 100_000.0 * 0.01, rel=0.02)


# --- 7. execution gate uses the same conversion ----------------------
def test_execution_gate_usdjpy_risk_is_usd(monkeypatch):
    import database
    monkeypatch.setattr(database, "get_account_balances",
                        lambda *a, **k: {"PAPER": {"balance": 10000.0, "equity": 10000.0, "floating_pnl": 0.0}})
    monkeypatch.setattr(database, "get_open_positions", lambda *a, **k: __import__("pandas").DataFrame())
    res = rg.evaluate_trade_risk({
        "symbol": "USDJPY", "side": "SELL", "volume": 1.10,
        "entry_price": 159.487, "stop_loss": 159.921, "mode": "PAPER", "broker": "PAPER",
    })
    tr = res["trade_risk"]
    # 1.10 lots at 0.434 distance -> ~ $299 USD (NOT ~$47,740 JPY-as-USD)
    assert tr["risk_amount_usd"] == pytest.approx(300.0, abs=8.0)
    assert tr["risk_pct"] == pytest.approx(3.0, abs=0.15)


def test_execution_gate_eurusd_risk_unchanged(monkeypatch):
    import database
    monkeypatch.setattr(database, "get_account_balances",
                        lambda *a, **k: {"PAPER": {"balance": 10000.0, "equity": 10000.0, "floating_pnl": 0.0}})
    monkeypatch.setattr(database, "get_open_positions", lambda *a, **k: __import__("pandas").DataFrame())
    res = rg.evaluate_trade_risk({
        "symbol": "EURUSD", "side": "BUY", "volume": 0.20,
        "entry_price": 1.0850, "stop_loss": 1.0800, "mode": "PAPER", "broker": "PAPER",
    })
    assert res["trade_risk"]["risk_amount_usd"] == pytest.approx(100.0, abs=0.5)
