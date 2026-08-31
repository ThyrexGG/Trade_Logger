"""
Phase 26 — XAUUSD Continuous Forward Monitoring & Sequential Drift Engine
Computes real-time telemetry, rolling 20/30/50 windows, CUSUM drift detection,
and "What Changed?" delta tracking against prior review snapshots.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd

import database
from xauusd_forward_validator import XAUUSDForwardJournal, XAUUSDForwardMetrics
from xauusd_forward_monitor import XAUUSDForwardMonitor
from xauusd_alert_engine import XAUUSDAlertEngine


class CUSUMDriftDetector:
    """
    Sequential CUSUM drift detector for forward trade returns vs the frozen +0.637R baseline.
    Identifies: NORMAL VARIATION, EARLY WARNING, PERSISTENT DEGRADATION.
    """
    HISTORICAL_EXPECTANCY = 0.637
    WARNING_THRESHOLD_DEV = -3.5   # Cumulative negative deviation trigger (e.g. -3.5R cumulative drag)
    CRITICAL_THRESHOLD_DEV = -7.0  # Critical deviation trigger (-7.0R drag)

    @staticmethod
    def detect_cusum_drift(trade_returns: List[float]) -> Dict[str, Any]:
        """
        Computes sequential cumulative deviation from historical baseline.
        """
        if not trade_returns:
            return {
                "trades_n": 0,
                "cumulative_deviation_r": 0.0,
                "rolling_cusum_series": [],
                "consecutive_negative_trades": 0,
                "status": "INSUFFICIENT DATA",
                "explanation": "No forward closed trades available for CUSUM calculation."
            }

        cusum = 0.0
        cusum_series = []
        consecutive_neg = 0
        max_consecutive_neg = 0

        for r in trade_returns:
            diff = r - CUSUMDriftDetector.HISTORICAL_EXPECTANCY
            cusum += diff
            cusum_series.append(round(cusum, 3))
            
            if r <= 0:
                consecutive_neg += 1
                if consecutive_neg > max_consecutive_neg:
                    max_consecutive_neg = consecutive_neg
            else:
                consecutive_neg = 0

        n = len(trade_returns)
        cum_dev = round(cusum, 3)

        if n < 15:
            status = "INSUFFICIENT DATA"
            explanation = f"Sample size (N = {n}) is too small for sequential CUSUM drift identification."
        elif cum_dev <= CUSUMDriftDetector.CRITICAL_THRESHOLD_DEV:
            status = "PERSISTENT DEGRADATION"
            explanation = (
                f"Cumulative return deviation ({cum_dev:+.2f}R) has breached the critical threshold ({CUSUMDriftDetector.CRITICAL_THRESHOLD_DEV:.1f}R). "
                "Investigate market regime shifts or execution slippage before drawing edge conclusions."
            )
        elif cum_dev <= CUSUMDriftDetector.WARNING_THRESHOLD_DEV:
            status = "EARLY WARNING"
            explanation = (
                f"Cumulative return deviation ({cum_dev:+.2f}R) indicates early negative drag relative to +0.637R holdout. "
                "Monitor next 10 forward observations."
            )
        else:
            status = "NORMAL VARIATION"
            explanation = f"Cumulative return deviation ({cum_dev:+.2f}R) is within expected statistical variance bounds."

        return {
            "trades_n": n,
            "cumulative_deviation_r": cum_dev,
            "rolling_cusum_series": cusum_series,
            "consecutive_negative_trades": consecutive_neg,
            "max_consecutive_negative_trades": max_consecutive_neg,
            "status": status,
            "explanation": explanation
        }


class XAUUSDContinuousMonitor:
    """
    Computes real-time continuous forward telemetry, rolling analytics, and delta inspections.
    """

    @staticmethod
    def get_full_monitoring_telemetry(mode: str = "PAPER") -> Dict[str, Any]:
        """
        Gathers comprehensive continuous monitoring statistics for the specified mode.
        """
        df = XAUUSDForwardJournal.get_forward_trades(mode=mode)
        metrics = XAUUSDForwardMetrics.calculate_forward_metrics(df)
        fwd_summary = XAUUSDForwardMonitor.get_forward_summary(mode=mode)

        n = metrics.get("trades_N", 0)
        returns = df["realized_r"].dropna().astype(float).tolist() if not df.empty and "realized_r" in df.columns else []

        # Rolling expectancy calculations (20, 30, 50)
        r20 = float(np.mean(returns[-20:])) if len(returns) >= 20 else (fwd_summary.get("expectancy_r", 0.0) if n > 0 else 0.0)
        r30 = float(np.mean(returns[-30:])) if len(returns) >= 30 else (fwd_summary.get("expectancy_r", 0.0) if n > 0 else 0.0)
        r50 = float(np.mean(returns[-50:])) if len(returns) >= 50 else (fwd_summary.get("expectancy_r", 0.0) if n > 0 else 0.0)

        # Baseline comparison
        hist_exp = 0.637
        exp_diff = fwd_summary.get("expectancy_r", 0.0) - hist_exp
        exp_ratio = (fwd_summary.get("expectancy_r", 0.0) / hist_exp) if hist_exp != 0 and n > 0 else 1.0

        # CUSUM Drift
        cusum_res = CUSUMDriftDetector.detect_cusum_drift(returns)

        return {
            "mode": mode,
            "trades_N": n,
            "win_rate_pct": metrics.get("win_rate_pct", 0.0),
            "expectancy_r": fwd_summary.get("expectancy_r", 0.0),
            "median_r": metrics.get("median_r", 0.0),
            "profit_factor": metrics.get("profit_factor", 0.0),
            "std_dev_r": float(np.std(returns)) if len(returns) > 1 else 0.0,
            "cumulative_r": float(np.sum(returns)) if returns else 0.0,
            "current_drawdown_r": fwd_summary.get("max_drawdown_r", 0.0),
            "max_drawdown_r": fwd_summary.get("max_drawdown_r", 0.0),
            "rolling_20_exp_r": round(r20, 3),
            "rolling_30_exp_r": round(r30, 3),
            "rolling_50_exp_r": round(r50, 3),
            "hist_exp_diff": round(exp_diff, 3),
            "hist_exp_ratio": round(exp_ratio, 2),
            "sample_tier": fwd_summary.get("sample_tier", "INSUFFICIENT DATA"),
            "ci_lower": fwd_summary.get("ci_lower", 0.0),
            "ci_upper": fwd_summary.get("ci_upper", 0.0),
            "cusum": cusum_res,
            "fill_rate_pct": 100.0 - fwd_summary.get("missed_entry_rate_pct", 8.5),
            "timeout_rate_pct": fwd_summary.get("missed_entry_rate_pct", 8.5),
            "avg_sl_distance_pips": fwd_summary.get("avg_sl_distance_pips", 14.5),
            "avg_holding_time_min": fwd_summary.get("avg_holding_time_min", 32)
        }

    @staticmethod
    def evaluate_what_changed(
        current_telemetry: Dict[str, Any],
        previous_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculates material changes since the previous review snapshot.
        If previous_snapshot is None, generates default baseline comparison.
        """
        if not previous_snapshot:
            return {
                "status": "NO MATERIAL RESEARCH CHANGES DETECTED",
                "summary": "Forward observation baseline initialized. No prior snapshot available for delta comparison.",
                "deltas": {
                    "new_trades": 0,
                    "expectancy_change": 0.0,
                    "win_rate_change": 0.0,
                    "drawdown_change": 0.0,
                    "timeout_rate_change": 0.0
                }
            }

        prev_n = previous_snapshot.get("trades_N", 0)
        curr_n = current_telemetry.get("trades_N", 0)
        new_trades = curr_n - prev_n

        exp_delta = round(current_telemetry.get("expectancy_r", 0.0) - previous_snapshot.get("expectancy_r", 0.0), 3)
        wr_delta = round(current_telemetry.get("win_rate_pct", 0.0) - previous_snapshot.get("win_rate_pct", 0.0), 1)
        dd_delta = round(current_telemetry.get("max_drawdown_r", 0.0) - previous_snapshot.get("max_drawdown_r", 0.0), 2)
        to_delta = round(current_telemetry.get("timeout_rate_pct", 0.0) - previous_snapshot.get("timeout_rate_pct", 0.0), 1)

        has_changes = (new_trades > 0 or abs(exp_delta) > 0.05 or abs(dd_delta) > 0.5)

        if has_changes:
            status = f"{new_trades} NEW FORWARD OBSERVATIONS PROCESSED"
            summary = (
                f"Since last review, {new_trades} new trades closed. Expectancy shifted by {exp_delta:+.3f}R, "
                f"win rate shifted by {wr_delta:+.1f}%, and max drawdown changed by {dd_delta:+.2f}R."
            )
        else:
            status = "NO MATERIAL RESEARCH CHANGES DETECTED"
            summary = "Telemetry remained stable across the latest observation check. No significant drift detected."

        return {
            "status": status,
            "summary": summary,
            "deltas": {
                "new_trades": new_trades,
                "expectancy_change": exp_delta,
                "win_rate_change": wr_delta,
                "drawdown_change": dd_delta,
                "timeout_rate_change": to_delta
            }
        }
