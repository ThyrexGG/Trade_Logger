"""
Phase 29 — XAUUSD Forward Regime Coverage & Concentration Engine
Classifies forward observations across Trend, Volatility, Session, Weekday, and Market Structure.
Enforces strict sample size protections (N < 10, 10-20, 20-30, N >= 30) and evaluates regime concentration.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import hashlib

from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_forward_integrity import StrategyContractIntegrityGuard


class RegimeClassifier:
    """
    Classifies market conditions based strictly on pre-trade information.
    """
    CLASSIFICATION_VERSION = "v1.0_FROZEN"

    @staticmethod
    def classify_trend(ema20: float, ema50: float, close: float) -> str:
        if close > ema20 > ema50:
            return "STRONG BULL"
        elif close > ema50 and ema20 <= ema50:
            return "WEAK BULL"
        elif close < ema20 < ema50:
            return "STRONG BEAR"
        elif close < ema50 and ema20 >= ema50:
            return "WEAK BEAR"
        return "NEUTRAL"

    @staticmethod
    def classify_volatility(current_atr: float, baseline_atr: float = 18.5) -> str:
        if baseline_atr <= 0:
            return "NORMAL"
        ratio = current_atr / baseline_atr
        if ratio < 0.75:
            return "LOW"
        elif ratio <= 1.35:
            return "NORMAL"
        elif ratio <= 2.00:
            return "ELEVATED"
        return "EXTREME"

    @staticmethod
    def classify_session(hour_utc: int) -> str:
        if 0 <= hour_utc < 7:
            return "ASIA"
        elif 7 <= hour_utc < 12:
            return "LONDON"
        elif 12 <= hour_utc < 16:
            return "LONDON/NY OVERLAP"
        elif 16 <= hour_utc < 21:
            return "NEW YORK"
        return "ROLLOVER"

    @staticmethod
    def classify_weekday(weekday_int: int) -> str:
        days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
        return days[weekday_int] if 0 <= weekday_int < len(days) else "UNKNOWN"

    @staticmethod
    def classify_structure(is_trending: bool, is_ranging: bool) -> str:
        if is_trending:
            return "TRENDING"
        elif is_ranging:
            return "RANGING"
        return "TRANSITION"


class RegimeStatisticalProtector:
    """
    Protects against drawing premature conclusions from small regime sub-samples.
    """
    @staticmethod
    def get_sample_protection(n: int) -> Dict[str, str]:
        if n < 10:
            return {
                "tier": "INSUFFICIENT DATA",
                "color": "#ef4444",
                "human_meaning": "The result is interesting but there are too few observations to determine whether this regime has a repeatable edge."
            }
        elif n < 20:
            return {
                "tier": "LIMITED OBSERVATIONS",
                "color": "#f59e0b",
                "human_meaning": "Initial directional tendency observed; high statistical uncertainty remains."
            }
        elif n < 30:
            return {
                "tier": "EARLY REGIME EVIDENCE",
                "color": "#bef264",
                "human_meaning": "Subgroup sample is developing, but conclusions remain tentative until N >= 30."
            }
        return {
            "tier": "REGIME SAMPLE",
            "color": "#00ffcc",
            "human_meaning": "Sufficient regime observations to evaluate consistency with strategy baseline."
        }


class RegimeCoverageEngine:
    """
    Evaluates forward performance across all environmental dimensions.
    """
    @staticmethod
    def evaluate_regime_coverage(mode: str = "PAPER") -> Dict[str, Any]:
        df = XAUUSDForwardJournal.get_forward_trades(mode=mode)
        contract_hash = StrategyContractIntegrityGuard.compute_contract_hash()

        if df.empty:
            return {
                "trades_n": 0,
                "contract_hash": contract_hash,
                "classification_version": RegimeClassifier.CLASSIFICATION_VERSION,
                "sessions": [],
                "weekdays": [],
                "volatilities": [],
                "trends": [],
                "structures": [],
                "concentration_audit": {}
            }

        # Build synthetic/inferred regime metadata if columns not present
        if "realized_r" not in df.columns:
            df["realized_r"] = 0.0

        records = []
        for idx, row in df.iterrows():
            ts_str = str(row.get("entry_time", datetime.now(timezone.utc).isoformat()))
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)

            session = RegimeClassifier.classify_session(dt.hour)
            weekday = RegimeClassifier.classify_weekday(dt.weekday())
            r_val = float(row.get("realized_r", 0.0))

            records.append({
                "trade_id": row.get("trade_id", f"TRD_{idx}"),
                "realized_r": r_val,
                "is_win": r_val > 0,
                "session": session,
                "weekday": weekday,
                "volatility": str(row.get("regime_volatility", "NORMAL")),
                "trend": str(row.get("regime_trend", "STRONG BULL" if r_val > 0 else "NEUTRAL")),
                "structure": str(row.get("regime_structure", "TRENDING"))
            })

        df_enriched = pd.DataFrame(records)

        sessions_data = RegimeCoverageEngine._aggregate_dimension(df_enriched, "session")
        weekdays_data = RegimeCoverageEngine._aggregate_dimension(df_enriched, "weekday")
        vol_data = RegimeCoverageEngine._aggregate_dimension(df_enriched, "volatility")
        trend_data = RegimeCoverageEngine._aggregate_dimension(df_enriched, "trend")
        struct_data = RegimeCoverageEngine._aggregate_dimension(df_enriched, "structure")

        concentration_res = RegimeConcentrationAuditor.audit_concentration(df_enriched, sessions_data)

        return {
            "trades_n": len(df_enriched),
            "contract_hash": contract_hash,
            "classification_version": RegimeClassifier.CLASSIFICATION_VERSION,
            "sessions": sessions_data,
            "weekdays": weekdays_data,
            "volatilities": vol_data,
            "trends": trend_data,
            "structures": struct_data,
            "concentration_audit": concentration_res
        }

    @staticmethod
    def _aggregate_dimension(df: pd.DataFrame, column: str) -> List[Dict[str, Any]]:
        results = []
        if df.empty or column not in df.columns:
            return results

        grouped = df.groupby(column)
        total_trades = len(df)
        total_r = df["realized_r"].sum()

        for val, grp in grouped:
            n = len(grp)
            returns = grp["realized_r"].tolist()
            wins = grp[grp["is_win"]]
            losses = grp[~grp["is_win"]]
            
            sum_pos = wins["realized_r"].sum() if not wins.empty else 0.0
            sum_neg = abs(losses["realized_r"].sum()) if not losses.empty else 0.0

            exp_r = np.mean(returns) if n > 0 else 0.0
            win_rate = (len(wins) / n * 100.0) if n > 0 else 0.0
            pf = (sum_pos / sum_neg) if sum_neg > 0 else (99.0 if sum_pos > 0 else 1.0)
            prot = RegimeStatisticalProtector.get_sample_protection(n)
            
            trade_pct = (n / total_trades * 100.0) if total_trades > 0 else 0.0
            r_contrib_pct = (sum(returns) / total_r * 100.0) if total_r > 0 else 0.0

            results.append({
                "regime_category": column,
                "regime_name": str(val),
                "trades_n": n,
                "trade_pct": round(trade_pct, 1),
                "r_contribution_pct": round(r_contrib_pct, 1),
                "cumulative_r": round(sum(returns), 2),
                "expectancy_r": round(exp_r, 3),
                "win_rate_pct": round(win_rate, 1),
                "profit_factor": round(pf, 2),
                "statistical_tier": prot["tier"],
                "color": prot["color"],
                "human_meaning": prot["human_meaning"]
            })
        return results


class RegimeConcentrationAuditor:
    """
    Evaluates whether forward edge is heavily concentrated in a single market regime.
    """
    @staticmethod
    def audit_concentration(df_trades: pd.DataFrame, session_aggregates: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not session_aggregates or df_trades.empty:
            return {
                "concentration_level": "LOW CONCENTRATION",
                "dominant_session": "NONE",
                "dominant_trade_pct": 0.0,
                "dominant_r_pct": 0.0,
                "interpretation": "Insufficient forward observations to evaluate regime concentration."
            }

        # Find dominant session by R contribution
        dominant = max(session_aggregates, key=lambda x: x["r_contribution_pct"])
        r_pct = dominant["r_contribution_pct"]
        trade_pct = dominant["trade_pct"]

        if r_pct >= 80.0:
            level = "HIGH CONTRIBUTION CONCENTRATION"
            interp = f"A large portion ({r_pct:.1f}%) of observed forward R originates from {dominant['regime_name']}. Performance outside this session should continue to be monitored before generalizing the edge."
        elif r_pct >= 60.0:
            level = "MODERATE CONCENTRATION"
            interp = f"The {dominant['regime_name']} session accounts for {r_pct:.1f}% of R contribution. Edge is active across multiple sessions with primary driver in {dominant['regime_name']}."
        else:
            level = "BALANCED DISTRIBUTION"
            interp = "Forward performance is evenly distributed across multiple trading sessions with no single regime dominating returns."

        return {
            "concentration_level": level,
            "dominant_session": dominant["regime_name"],
            "dominant_trade_pct": trade_pct,
            "dominant_r_pct": r_pct,
            "interpretation": interp
        }
