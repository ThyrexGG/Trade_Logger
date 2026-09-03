# -*- coding: utf-8 -*-
"""Phase 69 — research instrument universe."""
import research_universe as ru


def test_universe_contents_and_size():
    assert set(ru.RESEARCH_UNIVERSE) == {
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
        "EURJPY", "GBPJPY", "AUDJPY", "XAUUSD",
    }


def test_not_hardcoded_to_usdjpy():
    # the discovery universe must include Gold and the FX majors, not just USDJPY
    cats = {i.category for i in ru.universe()}
    assert cats == {"FX_MAJOR", "FX_CROSS", "METAL"}
    assert ru.classify("XAUUSD") == "METAL"


def test_normalise_and_membership():
    assert ru.is_in_universe("xau/usd")
    assert ru.is_in_universe("EUR_USD")
    assert not ru.is_in_universe("BTCUSD")
    assert ru.normalise("gbp:jpy") == "GBPJPY"


def test_pip_size_by_family():
    assert ru.pip_size("EURUSD") == 0.0001
    assert ru.pip_size("USDJPY") == 0.01
    assert ru.pip_size("GBPJPY") == 0.01
    assert ru.pip_size("XAUUSD") == 0.1


def test_yf_symbol_mapping():
    assert ru.yf_symbol("EURUSD") == "EURUSD=X"
    assert ru.yf_symbol("XAUUSD") == "GC=F"
    assert ru.yf_symbol("NOPE") is None


def test_sufficiency_rules_present_for_capable_timeframes():
    for tf in ("1d", "1h", "4h"):
        rule = ru.sufficiency_rule(tf)
        assert rule is not None
        assert rule.min_bars > 0
        assert rule.warmup_bars > 0


def test_timeframe_data_note_is_honest_about_intraday():
    assert "INSUFFICIENT" in ru.TIMEFRAME_DATA_NOTE["1m"]
    assert "INSUFFICIENT" in ru.TIMEFRAME_DATA_NOTE["15m"]
    assert "sufficient" in ru.TIMEFRAME_DATA_NOTE["1d"].lower()
