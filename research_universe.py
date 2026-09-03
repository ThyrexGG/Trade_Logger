# -*- coding: utf-8 -*-
"""
Research instrument universe (Phase 69).

The strategy-discovery work must not be hard-coded to a single symbol. This
module is the one canonical list of instruments the discovery / ranking / setup
engines are allowed to consider, plus the per-instrument metadata they need
(Yahoo ticker for ingestion, pip size for R-multiple maths, session windows,
data-sufficiency thresholds).

It deliberately does NOT re-implement broker instrument specs — those live in
``instrument_specs.DEFAULT_SPECS`` and are about order routing. This is research
metadata: what may be studied, and what "enough data" means for it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# Canonical timeframes (UTC internally). M5/M1 are listed so the schema and
# ingestion accept them, but Phase 69's yfinance-only data path can only give
# real depth on 1h / 1d — see ``TIMEFRAME_DATA_NOTE`` and DATA_SUFFICIENCY.
# --------------------------------------------------------------------------
CANONICAL_TIMEFRAMES: Tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h", "1d")

TIMEFRAME_DATA_NOTE: Dict[str, str] = {
    "1d": "yfinance: ~5+ years — sufficient for discovery + WFO + temporal stability",
    "1h": "yfinance: ~2 years — marginal for discovery; usable",
    "4h": "yfinance: resampled from 1h (~2 years)",
    "15m": "yfinance: ~60 days only — INSUFFICIENT for multi-year discovery",
    "5m": "yfinance: ~60 days only — INSUFFICIENT for multi-year discovery",
    "1m": "yfinance: ~7 days only — INSUFFICIENT; native TF of the frozen Gold contract",
}


@dataclass(frozen=True)
class UniverseInstrument:
    symbol: str                 # canonical, e.g. "EURUSD", "XAUUSD"
    display: str
    category: str               # FX_MAJOR | FX_CROSS | METAL
    yf_symbol: str              # Yahoo Finance ticker for ingestion
    pip_size: float             # price move of "1 pip" for this instrument
    quote_ccy: str
    sessions: Tuple[str, ...] = field(default_factory=lambda: ("LONDON", "NEW_YORK"))
    note: str = ""


# --------------------------------------------------------------------------
# The universe. FX via Yahoo "<PAIR>=X" (synthetic spot — no real volume, and
# intraday quality is poor: documented limitation). Gold via "GC=F" (COMEX
# front-month future — the closest freely-available proxy for XAUUSD spot).
# --------------------------------------------------------------------------
_FX_MAJORS = [
    ("EURUSD", "Euro / US Dollar", "EURUSD=X", 0.0001, "USD"),
    ("GBPUSD", "British Pound / US Dollar", "GBPUSD=X", 0.0001, "USD"),
    ("USDJPY", "US Dollar / Japanese Yen", "USDJPY=X", 0.01, "JPY"),
    ("AUDUSD", "Australian Dollar / US Dollar", "AUDUSD=X", 0.0001, "USD"),
    ("NZDUSD", "New Zealand Dollar / US Dollar", "NZDUSD=X", 0.0001, "USD"),
    ("USDCAD", "US Dollar / Canadian Dollar", "USDCAD=X", 0.0001, "CAD"),
    ("USDCHF", "US Dollar / Swiss Franc", "USDCHF=X", 0.0001, "CHF"),
]

_FX_CROSSES = [
    ("EURJPY", "Euro / Japanese Yen", "EURJPY=X", 0.01, "JPY"),
    ("GBPJPY", "British Pound / Japanese Yen", "GBPJPY=X", 0.01, "JPY"),
    ("AUDJPY", "Australian Dollar / Japanese Yen", "AUDJPY=X", 0.01, "JPY"),
]

_METALS = [
    ("XAUUSD", "Spot Gold / US Dollar", "GC=F", 0.1, "USD"),
]


def _build() -> Dict[str, UniverseInstrument]:
    out: Dict[str, UniverseInstrument] = {}
    for sym, disp, yf, pip, ccy in _FX_MAJORS:
        out[sym] = UniverseInstrument(sym, disp, "FX_MAJOR", yf, pip, ccy)
    for sym, disp, yf, pip, ccy in _FX_CROSSES:
        out[sym] = UniverseInstrument(sym, disp, "FX_CROSS", yf, pip, ccy)
    for sym, disp, yf, pip, ccy in _METALS:
        out[sym] = UniverseInstrument(
            sym, disp, "METAL", yf, pip, ccy,
            note="Yahoo GC=F front-month future used as XAUUSD spot proxy",
        )
    return out


_UNIVERSE: Dict[str, UniverseInstrument] = _build()

RESEARCH_UNIVERSE: Tuple[str, ...] = tuple(_UNIVERSE.keys())


# --------------------------------------------------------------------------
# Data sufficiency gate (§9). A strategy test must first pass these — an
# instrument/timeframe below threshold is INSUFFICIENT_EVIDENCE, never a
# "0-trade / neutral" result.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SufficiencyRule:
    min_bars: int
    max_gap_bars: int          # a single gap larger than this is a data defect
    warmup_bars: int           # indicator warm-up consumed before the first decision


DATA_SUFFICIENCY: Dict[str, SufficiencyRule] = {
    "1d": SufficiencyRule(min_bars=400, max_gap_bars=6, warmup_bars=210),
    "4h": SufficiencyRule(min_bars=1200, max_gap_bars=12, warmup_bars=210),
    "1h": SufficiencyRule(min_bars=1500, max_gap_bars=30, warmup_bars=210),
    "15m": SufficiencyRule(min_bars=6000, max_gap_bars=64, warmup_bars=210),
    "5m": SufficiencyRule(min_bars=15000, max_gap_bars=200, warmup_bars=210),
    "1m": SufficiencyRule(min_bars=60000, max_gap_bars=600, warmup_bars=210),
}


def normalise(symbol: str) -> str:
    return (symbol or "").upper().replace("/", "").replace(":", "").replace("_", "").strip()


def is_in_universe(symbol: str) -> bool:
    return normalise(symbol) in _UNIVERSE


def get_instrument(symbol: str) -> Optional[UniverseInstrument]:
    return _UNIVERSE.get(normalise(symbol))


def classify(symbol: str) -> Optional[str]:
    inst = get_instrument(symbol)
    return inst.category if inst else None


def universe(category: Optional[str] = None) -> List[UniverseInstrument]:
    items = list(_UNIVERSE.values())
    if category:
        items = [i for i in items if i.category == category.upper()]
    return items


def yf_symbol(symbol: str) -> Optional[str]:
    inst = get_instrument(symbol)
    return inst.yf_symbol if inst else None


def pip_size(symbol: str) -> float:
    inst = get_instrument(symbol)
    return inst.pip_size if inst else 0.0001


def sufficiency_rule(timeframe: str) -> Optional[SufficiencyRule]:
    return DATA_SUFFICIENCY.get((timeframe or "").strip().lower())


def timeframe_is_data_capable(timeframe: str) -> bool:
    """True only for timeframes yfinance can populate with multi-year depth."""
    return (timeframe or "").strip().lower() in ("1h", "4h", "1d")


__all__ = [
    "CANONICAL_TIMEFRAMES",
    "TIMEFRAME_DATA_NOTE",
    "UniverseInstrument",
    "RESEARCH_UNIVERSE",
    "DATA_SUFFICIENCY",
    "SufficiencyRule",
    "normalise",
    "is_in_universe",
    "get_instrument",
    "classify",
    "universe",
    "yf_symbol",
    "pip_size",
    "sufficiency_rule",
    "timeframe_is_data_capable",
]
