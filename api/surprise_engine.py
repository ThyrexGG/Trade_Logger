# -*- coding: utf-8 -*-
"""
Deterministic Economic Surprise Engine (Stage 18B).

Given `actual` vs `forecast` vs `previous` for one indicator, compute a surprise
and a *directional interpretation* — using a per-indicator configuration, NOT
one universal "higher = bullish" rule. Higher CPI is hawkish; higher GDP is
expansionary; higher Unemployment is bearish for the economy. Those must not
collapse to the same verdict.

Pure and deterministic. No historical data is fabricated: `normalized_surprise`
is only produced when a `std_deviation` is configured for the indicator, and
`surprise_pct` only when a percentage comparison is mathematically valid.

States are explicit: POSITIVE / NEGATIVE / NEUTRAL surprise, or INSUFFICIENT /
UNAVAILABLE.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional

# --- indicator configuration -----------------------------------------
# category: family of the indicator
# higher_is: what a higher-than-forecast actual means for the *economy* of the
#            releasing country ("positive" | "negative")
# policy_bias_on_beat: what an upside surprise implies for monetary policy
# pct_valid: whether (actual-forecast)/|forecast| is a meaningful percentage
#            (invalid for rates / index-point levels expressed in the same unit)
# std: typical release-to-forecast standard deviation, for a normalized z-score.
#      Omitted -> no normalized surprise is produced (we do not invent one).
_CFG: Dict[str, Dict[str, Any]] = {
    "CPI":            {"category": "INFLATION", "higher_is": "negative", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.3},
    "CORE_CPI":       {"category": "INFLATION", "higher_is": "negative", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.2},
    "HICP":           {"category": "INFLATION", "higher_is": "negative", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.3},
    "PPI":            {"category": "INFLATION", "higher_is": "negative", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.4},
    "CORE_PPI":       {"category": "INFLATION", "higher_is": "negative", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.3},
    "PCE":            {"category": "INFLATION", "higher_is": "negative", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.25},
    "CORE_PCE":       {"category": "INFLATION", "higher_is": "negative", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.2},
    "WAGE_GROWTH":    {"category": "INFLATION", "higher_is": "negative", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.3},

    "GDP":            {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.8},
    "GDP_GROWTH":     {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.5},
    "MFG_PMI":        {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 1.5},
    "SERVICES_PMI":   {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 1.8},
    "COMPOSITE_PMI":  {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 1.5},
    "RETAIL_SALES":   {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.5},
    "INDUSTRIAL_PROD":{"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.6},
    "DURABLE_GOODS":  {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 1.5},
    "CONSUMER_CONF":  {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "NEUTRAL", "pct_valid": False, "std": 2.5},
    "TRADE_BALANCE":  {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "NEUTRAL", "pct_valid": False, "std": 5.0},

    "NFP":            {"category": "LABOR", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 60.0},
    "ADP":            {"category": "LABOR", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 55.0},
    "JOLTS":          {"category": "LABOR", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.4},
    "UNEMPLOYMENT":   {"category": "LABOR", "higher_is": "negative", "policy_bias_on_beat": "DOVISH", "pct_valid": False, "std": 0.15},
    "JOBLESS_CLAIMS": {"category": "LABOR", "higher_is": "negative", "policy_bias_on_beat": "DOVISH", "pct_valid": False, "std": 15.0},
    "CONTINUING_CLAIMS": {"category": "LABOR", "higher_is": "negative", "policy_bias_on_beat": "DOVISH", "pct_valid": False, "std": 30.0},

    "INTEREST_RATE":  {"category": "MONETARY_POLICY", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": 0.10},
}
_CATEGORY_DEFAULT = {
    "INFLATION": {"category": "INFLATION", "higher_is": "negative", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": None},
    "GROWTH":    {"category": "GROWTH", "higher_is": "positive", "policy_bias_on_beat": "NEUTRAL", "pct_valid": False, "std": None},
    "LABOR":     {"category": "LABOR", "higher_is": "positive", "policy_bias_on_beat": "NEUTRAL", "pct_valid": False, "std": None},
    "RATES":     {"category": "MONETARY_POLICY", "higher_is": "positive", "policy_bias_on_beat": "HAWKISH", "pct_valid": False, "std": None},
}

_NAME_HINTS = [
    ("CORE_PCE", ("CORE PCE",)), ("CORE_CPI", ("CORE CPI", "CORE INFLATION")),
    ("HICP", ("HICP", "HARMONISED", "HARMONIZED")), ("CPI", ("CPI", "CONSUMER PRICE")),
    ("PPI", ("PPI", "PRODUCER PRICE")), ("PCE", ("PCE",)),
    ("NFP", ("NON-FARM", "NONFARM", "NFP", "PAYROLL")), ("ADP", ("ADP",)),
    ("JOBLESS_CLAIMS", ("JOBLESS CLAIMS", "INITIAL CLAIMS")),
    ("CONTINUING_CLAIMS", ("CONTINUING CLAIMS",)),
    ("UNEMPLOYMENT", ("UNEMPLOYMENT",)), ("JOLTS", ("JOLTS", "JOB OPENINGS")),
    ("SERVICES_PMI", ("SERVICES PMI", "SPMI", "ISM SERVICES", "NON-MANUFACTURING")),
    ("MFG_PMI", ("MANUFACTURING PMI", "MPMI", "ISM MANUFACTURING", "ISM MPMI")),
    ("COMPOSITE_PMI", ("COMPOSITE PMI",)),
    ("RETAIL_SALES", ("RETAIL SALES",)), ("GDP", ("GDP", "GROSS DOMESTIC")),
    ("INDUSTRIAL_PROD", ("INDUSTRIAL PRODUCTION",)), ("DURABLE_GOODS", ("DURABLE GOODS",)),
    ("CONSUMER_CONF", ("CONSUMER CONFIDENCE", "CONSUMER SENTIMENT")),
    ("TRADE_BALANCE", ("TRADE BALANCE",)), ("WAGE_GROWTH", ("WAGE", "AVERAGE EARNINGS")),
    ("INTEREST_RATE", ("INTEREST RATE", "RATE DECISION", "FOMC", "BANK RATE", "CASH RATE")),
]


def resolve_indicator(raw: str) -> Optional[str]:
    key = re.sub(r"[^A-Z0-9_]", "_", (raw or "").upper()).strip("_")
    if key in _CFG:
        return key
    up = (raw or "").upper()
    for canon, hints in _NAME_HINTS:
        if any(h in up for h in hints):
            return canon
    return None


def _config_for(indicator: str) -> Optional[Dict[str, Any]]:
    canon = resolve_indicator(indicator)
    if canon:
        return {**_CFG[canon], "indicator": canon}
    return None


def evaluate_surprise(
    *,
    indicator: str,
    actual: Optional[float],
    forecast: Optional[float],
    previous: Optional[float] = None,
    unit: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns:
      surprise            actual - forecast (None if either missing)
      surprise_pct        % vs forecast, only when mathematically valid
      normalized_surprise z-score * 30, only when a std is configured
      direction_bias      POSITIVE | NEGATIVE | NEUTRAL  (effect on the economy)
      policy_bias         HAWKISH | DOVISH | NEUTRAL
      state               POSITIVE_SURPRISE | NEGATIVE_SURPRISE | INLINE |
                          INSUFFICIENT | UNAVAILABLE
      confidence          HIGH (configured std) | LOW (no std) | NONE
    """
    cfg = _config_for(indicator)

    if actual is None or forecast is None:
        return {
            "state": "UNAVAILABLE" if cfg else "UNAVAILABLE",
            "surprise": None, "surprise_pct": None, "normalized_surprise": None,
            "direction_bias": "NEUTRAL", "policy_bias": "NEUTRAL",
            "confidence": "NONE",
            "note": "actual and/or forecast not available",
            "indicator_resolved": cfg["indicator"] if cfg else None,
        }

    surprise = round(actual - forecast, 6)

    if cfg is None:
        # unknown indicator: we can state the raw surprise but not interpret it
        return {
            "state": "INSUFFICIENT",
            "surprise": surprise, "surprise_pct": None, "normalized_surprise": None,
            "direction_bias": "NEUTRAL", "policy_bias": "NEUTRAL", "confidence": "NONE",
            "note": "indicator not in the surprise configuration — direction not interpreted",
            "indicator_resolved": None,
        }

    higher_is = cfg["higher_is"]
    beat = surprise > 0
    miss = surprise < 0
    if abs(surprise) < 1e-9:
        direction_bias = "NEUTRAL"
    elif (beat and higher_is == "positive") or (miss and higher_is == "negative"):
        direction_bias = "POSITIVE"
    else:
        direction_bias = "NEGATIVE"

    policy_bias = "NEUTRAL"
    if cfg["policy_bias_on_beat"] != "NEUTRAL" and abs(surprise) >= 1e-9:
        if beat:
            policy_bias = cfg["policy_bias_on_beat"]
        else:
            policy_bias = "DOVISH" if cfg["policy_bias_on_beat"] == "HAWKISH" else "HAWKISH"

    surprise_pct = None
    if cfg["pct_valid"] and abs(forecast) > 1e-9:
        surprise_pct = round(surprise / abs(forecast) * 100.0, 2)

    normalized = None
    confidence = "LOW"
    state = "INLINE"
    std = cfg.get("std")
    if std and std > 0 and math.isfinite(std):
        z = surprise / std
        normalized = round(max(-100.0, min(100.0, z * 30.0)), 1)
        confidence = "HIGH"
        if abs(z) < 0.35:
            state = "INLINE"
        elif direction_bias == "POSITIVE":
            state = "POSITIVE_SURPRISE"
        elif direction_bias == "NEGATIVE":
            state = "NEGATIVE_SURPRISE"
    else:
        if abs(surprise) < 1e-9:
            state = "INLINE"
        elif direction_bias == "POSITIVE":
            state = "POSITIVE_SURPRISE"
        elif direction_bias == "NEGATIVE":
            state = "NEGATIVE_SURPRISE"

    return {
        "state": state,
        "surprise": surprise,
        "surprise_pct": surprise_pct,
        "normalized_surprise": normalized,
        "direction_bias": direction_bias if state != "INLINE" else "NEUTRAL",
        "policy_bias": policy_bias if state != "INLINE" else "NEUTRAL",
        "category": cfg["category"],
        "confidence": confidence,
        "indicator_resolved": cfg["indicator"],
        "vs_previous": (round(actual - previous, 6) if previous is not None else None),
    }
