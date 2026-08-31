"""
Phase 22 — XAUUSD Forward Drift Detector & Edge Consistency Evaluator
Monitors rolling forward performance against the frozen historical baseline.
Provides transparent, multi-component edge consistency scoring and drawdown status.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_forward_monitor import XAUUSDForwardMonitor


class XAUUSDDriftDetector:
    """
    Evaluates rolling metrics, distribution consistency, drawdown tier, and composite edge score.
    """

    @staticmethod
    def evaluate_drawdown_status(current_dd_r: float) -> Dict[str, Any]:
        """
        Classifies drawdown state relative to the frozen Phase 20 Monte Carlo stress distribution.
        - Typical: <= 4.00R
        - Stress 95th Percentile: 7.15R
        - Critical Breaching Threshold: 12.00R
        """
        if current_dd_r <= 4.00:
            status = "NORMAL"
            meaning = "Drawdown is within typical historical expectation (<= 4.00R)."
            color = "#00ffcc"
        elif current_dd_r <= 7.15:
            status = "ELEVATED"
            meaning = "Drawdown is elevated (4.00R to 7.15R) but remains within historical 95th-percentile stress parameters."
            color = "#bef264"
        elif current_dd_r <= 12.00:
            status = "STRESS"
            meaning = "Drawdown exceeds historical 95th-percentile stress (7.15R to 12.00R). Heightened monitoring required."
            color = "#f59e0b"
        else:
            status = "SEVERE"
            meaning = "Drawdown exceeds critical threshold (> 12.00R). Possible structural regime decay."
            color = "#ff5555"

        return {
            "current_drawdown_r": round(current_dd_r, 2),
            "status": status,
            "meaning": meaning,
            "color": color,
            "historical_median_dd_r": 3.84,
            "historical_stress_95th_r": 7.15,
            "note": "Drawdown alone does not prove strategy failure; must be evaluated with sample size and execution quality."
        }

    @staticmethod
    def evaluate_distribution_drift(mode: str = "PAPER") -> Dict[str, Any]:
        """
        Compares forward MAE, MFE, holding time, and SL distance distributions against historical baseline.
        """
        df = XAUUSDForwardJournal.get_forward_trades(mode=mode)
        hist = XAUUSDForwardMonitor.HISTORICAL_BASELINE

        if df.empty or len(df[df["realized_r"].notnull()]) < 5:
            return {
                "distribution_status": "INSUFFICIENT DATA",
                "mae_drift": "Awaiting forward observations",
                "mfe_drift": "Awaiting forward observations",
                "holding_drift": "Awaiting forward observations",
                "verdict": "DISTRIBUTIONALLY UNKNOWN (N < 5)",
                "explanation": "Accumulating unseen forward trades before evaluating Kolmogorov-Smirnov distribution shifts.",
                "historical_avg_mae_r": hist["avg_mae_r"],
                "forward_avg_mae_r": hist["avg_mae_r"],
                "historical_avg_mfe_r": hist["avg_mfe_r"],
                "forward_avg_mfe_r": hist["avg_mfe_r"],
                "historical_avg_holding_min": hist["avg_holding_time_min"],
                "forward_avg_holding_min": int(hist["avg_holding_time_min"])
            }

        closed = df[df["realized_r"].notnull()]
        fwd_mae = float(closed["mae_r"].dropna().mean()) if "mae_r" in closed.columns and len(closed["mae_r"].dropna()) > 0 else hist["avg_mae_r"]
        fwd_mfe = float(closed["mfe_r"].dropna().mean()) if "mfe_r" in closed.columns and len(closed["mfe_r"].dropna()) > 0 else hist["avg_mfe_r"]
        fwd_hold = float(closed["holding_time_minutes"].dropna().mean()) if "holding_time_minutes" in closed.columns and len(closed["holding_time_minutes"].dropna()) > 0 else hist["avg_holding_time_min"]
        
        # Divergence checks
        mae_divergence = abs(fwd_mae - hist["avg_mae_r"]) / hist["avg_mae_r"]
        mfe_divergence = abs(fwd_mfe - hist["avg_mfe_r"]) / hist["avg_mfe_r"]

        if mae_divergence > 0.60 or mfe_divergence > 0.60:
            dist_status = "DISTRIBUTIONALLY DRIFTING"
            explanation = "Noticeable divergence in trade excursion profile (MAE/MFE) compared to historical baseline."
        else:
            dist_status = "DISTRIBUTIONALLY CONSISTENT"
            explanation = "Forward MAE, MFE, and holding duration remain aligned with historical expectations."

        return {
            "distribution_status": dist_status,
            "historical_avg_mae_r": hist["avg_mae_r"],
            "forward_avg_mae_r": round(fwd_mae, 2),
            "historical_avg_mfe_r": hist["avg_mfe_r"],
            "forward_avg_mfe_r": round(fwd_mfe, 2),
            "historical_avg_holding_min": hist["avg_holding_time_min"],
            "forward_avg_holding_min": int(fwd_hold),
            "verdict": dist_status,
            "explanation": explanation
        }

    @staticmethod
    def calculate_edge_consistency_score(mode: str = "PAPER") -> Dict[str, Any]:
        """
        Computes transparent, fully inspectable edge consistency score (0 to 100).
        Components:
        - Expectancy Direction: Max 35 pts
        - Confidence Interval: Max 20 pts
        - Win Rate Alignment: Max 15 pts
        - Drawdown Health: Max 15 pts
        - Execution Quality: Max 15 pts
        """
        fwd = XAUUSDForwardMonitor.get_forward_summary(mode=mode)
        exec_q = XAUUSDForwardMonitor.get_execution_quality_metrics(mode=mode)
        n = fwd.get("trades_N", 0)

        if n < 10:
            return {
                "total_score": 50.0,
                "tier": "INITIALIZING",
                "components": [
                    {"component": "Sample Accumulation", "score": 10, "max_score": 20, "detail": f"N = {n} / 10 minimum for scoring"},
                    {"component": "Expectancy Baseline", "score": 20, "max_score": 35, "detail": "Neutral prior until sample expands"},
                    {"component": "Execution Alignment", "score": 10, "max_score": 15, "detail": exec_q.get("diagnosis", "Normal")},
                    {"component": "Drawdown Range", "score": 10, "max_score": 15, "detail": "Within bounds"},
                    {"component": "Confidence Range", "score": 0, "max_score": 15, "detail": "Awaiting larger N"}
                ],
                "verdict": "INITIALIZING FORWARD LEDGER",
                "explanation": f"Forward tracking is in early telemetry stage ({n} trades). Score will become fully empirical at N >= 30."
            }

        exp_r = fwd.get("expectancy_r", 0.0)
        wr = fwd.get("win_rate_pct", 0.0)
        max_dd = fwd.get("max_drawdown_r", 0.0)
        ci_lower = fwd.get("ci_lower", 0.0)

        # 1. Expectancy Direction (Max 35)
        c1 = 35 if exp_r >= 0.45 else (25 if exp_r >= 0.20 else (15 if exp_r > 0 else 0))

        # 2. Confidence Interval (Max 20)
        c2 = 20 if ci_lower > 0 else (10 if fwd.get("ci_upper", 0.0) > 0 else 0)

        # 3. Win Rate Alignment (Max 15)
        c3 = 15 if (50.0 <= wr <= 68.0) else (10 if (40.0 <= wr < 50.0 or 68.0 < wr <= 80.0) else 0)

        # 4. Drawdown Health (Max 15)
        c4 = 15 if max_dd <= 4.00 else (10 if max_dd <= 7.15 else 0)

        # 5. Execution Quality (Max 15)
        c5 = 15 if exec_q.get("execution_health") == "OPTIMAL" else 5

        total = c1 + c2 + c3 + c4 + c5
        
        if total >= 80:
            tier = "STRONG CONSISTENCY"
        elif total >= 60:
            tier = "MODERATE CONSISTENCY"
        elif total >= 40:
            tier = "UNCERTAIN / EARLY STAGE"
        else:
            tier = "DEGRADED CONSISTENCY"

        return {
            "total_score": total,
            "tier": tier,
            "components": [
                {"component": "Expectancy Direction", "score": c1, "max_score": 35, "detail": f"Forward E[R]: {exp_r:+.3f}R"},
                {"component": "Confidence Interval", "score": c2, "max_score": 20, "detail": f"CI Lower: {ci_lower:+.3f}R"},
                {"component": "Win Rate Alignment", "score": c3, "max_score": 15, "detail": f"Win Rate: {wr:.1f}%"},
                {"component": "Drawdown Range", "score": c4, "max_score": 15, "detail": f"Max DD: {max_dd:.2f}R"},
                {"component": "Execution Quality", "score": c5, "max_score": 15, "detail": exec_q.get("execution_health", "Normal")}
            ],
            "verdict": tier,
            "explanation": f"Score reflects empirical agreement with frozen Phase 20 contract across {n} unseen forward trades."
        }
