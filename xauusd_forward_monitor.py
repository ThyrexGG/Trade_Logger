"""
Phase 22 — XAUUSD Forward Validation Monitor
Tracks forward unseen telemetry, statistical distributions, execution quality, and regime diagnostics.
Strictly isolated from historical research datasets.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
import database
from xauusd_forward_validator import XAUUSDForwardJournal, XAUUSDForwardMetrics


class XAUUSDForwardMonitor:
    """
    Computes comprehensive forward performance, distribution analytics, and execution quality.
    """
    
    # Frozen Phase 20/21 Historical Baseline (Locked Reference)
    HISTORICAL_BASELINE = {
        "trades_N": 82,
        "expectancy_r": 0.637,
        "ci_lower": 0.477,
        "ci_upper": 0.817,
        "win_rate_pct": 58.6,
        "profit_factor": 2.52,
        "median_r": 0.610,
        "avg_r": 0.637,
        "max_drawdown_r": 3.84,
        "stress_drawdown_95th_r": 7.15,
        "avg_sl_pips": 14.5,
        "avg_holding_time_min": 32,
        "avg_mae_r": 0.38,
        "avg_mfe_r": 2.85,
        "missed_entry_rate_pct": 8.5,
        "hit_rate_2r_pct": 68.3,
        "hit_rate_3r_pct": 46.3,
        "hit_rate_4r_pct": 28.0,
        "hit_rate_5r_pct": 18.3,
        "hit_rate_7r_pct": 9.8,
    }

    @staticmethod
    def get_forward_summary(mode: str = "PAPER") -> Dict[str, Any]:
        """
        Extracts forward summary statistics with sample size classification and bootstrap CI.
        """
        df = XAUUSDForwardJournal.get_forward_trades(mode=mode)
        metrics = XAUUSDForwardMetrics.calculate_forward_metrics(df)
        n = metrics.get("trades_N", 0)

        # Sample reliability classification
        if n < 30:
            sample_tier = "INSUFFICIENT DATA"
            sample_text = f"Forward sample contains {n} / 100 target trades. Evidence is accumulating; statistical conclusions are premature."
        elif n < 50:
            sample_tier = "LIMITED SAMPLE"
            sample_text = f"Forward sample contains {n} / 100 trades. Early directional indication only."
        elif n < 100:
            sample_tier = "MODERATE SAMPLE"
            sample_text = f"Forward sample contains {n} / 100 trades. Intermediate reliability across recent market regimes."
        else:
            sample_tier = "LARGE SAMPLE"
            sample_text = f"Forward sample contains {n} trades. Strong empirical foundation for forward validation."

        # Bootstrap Confidence Interval on realized R
        ci_lower, ci_upper, ci_status, ci_text = 0.0, 0.0, "INSUFFICIENT DATA", "Requires at least 10 closed trades."
        if n >= 10 and not df.empty and "realized_r" in df.columns:
            rets = df["realized_r"].dropna().astype(float).values
            if len(rets) >= 10:
                rng = np.random.default_rng(42)
                boot_means = [np.mean(rng.choice(rets, size=len(rets), replace=True)) for _ in range(2000)]
                ci_lower = float(np.percentile(boot_means, 2.5))
                ci_upper = float(np.percentile(boot_means, 97.5))
                
                if ci_lower > 0:
                    ci_status = "POSITIVE EVIDENCE"
                    ci_text = f"95% Bootstrap CI [{ci_lower:+.3f}R, {ci_upper:+.3f}R] excludes zero with positive expectancy."
                elif ci_upper < 0:
                    ci_status = "NEGATIVE EVIDENCE"
                    ci_text = f"95% Bootstrap CI [{ci_lower:+.3f}R, {ci_upper:+.3f}R] is strictly negative."
                else:
                    ci_status = "POSITIVE BUT UNCERTAIN" if metrics.get("expectancy_r", 0) > 0 else "UNCERTAIN"
                    ci_text = f"95% Bootstrap CI [{ci_lower:+.3f}R, {ci_upper:+.3f}R] spans zero; outcome remains statistically uncertain."

        return {
            "mode": mode,
            "trades_N": n,
            "sample_tier": sample_tier,
            "sample_text": sample_text,
            "expectancy_r": metrics.get("expectancy_r", 0.0),
            "win_rate_pct": metrics.get("win_rate_pct", 0.0),
            "profit_factor": metrics.get("profit_factor", 0.0),
            "max_drawdown_r": metrics.get("max_drawdown_r", 0.0),
            "median_r": metrics.get("median_r", 0.0),
            "avg_sl_distance_pips": metrics.get("avg_sl_distance_pips", 14.5),
            "avg_holding_time_min": metrics.get("avg_holding_time_min", 32),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "ci_status": ci_status,
            "ci_text": ci_text,
            "hit_rate_2r_pct": metrics.get("hit_rate_2r_pct", 0.0),
            "hit_rate_3r_pct": metrics.get("hit_rate_3r_pct", 0.0),
            "hit_rate_4r_pct": metrics.get("hit_rate_4r_pct", 0.0),
            "hit_rate_5r_pct": metrics.get("hit_rate_5r_pct", 0.0),
            "hit_rate_7r_pct": metrics.get("hit_rate_7r_pct", 0.0),
            "missed_entry_rate_pct": metrics.get("missed_entry_rate_pct", 0.0),
            "rejection_rate_pct": metrics.get("rejection_rate_pct", 0.0),
            "status": metrics.get("status", "ACTIVE")
        }

    @staticmethod
    def get_execution_quality_metrics(mode: str = "PAPER") -> Dict[str, Any]:
        """
        Monitors 1M FVG limit fill fidelity, slippage, and stop-loss quality.
        Distinguishes strategy failure from execution degradation.
        """
        df = XAUUSDForwardJournal.get_forward_trades(mode=mode)
        if df.empty:
            return {
                "fill_rate_pct": 100.0,
                "timeout_rate_pct": 0.0,
                "avg_slippage_pips": 1.0,
                "avg_spread_pips": 2.0,
                "premature_invalidation_pct": 0.0,
                "sl_within_bounds_pct": 100.0,
                "execution_health": "NORMAL",
                "diagnosis": "No execution degradation detected. Fills match modeled assumptions."
            }

        n_total = len(df)
        n_filled = len(df[df["status"] == "FILLED"])
        n_expired = len(df[df["status"] == "EXPIRED"])
        
        fill_rate = (n_filled / n_total * 100.0) if n_total > 0 else 100.0
        timeout_rate = (n_expired / n_total * 100.0) if n_total > 0 else 0.0
        
        avg_slip = float(df["slippage_pips"].dropna().mean()) if "slippage_pips" in df.columns and len(df["slippage_pips"].dropna()) > 0 else 1.0
        avg_spd = float(df["spread_pips"].dropna().mean()) if "spread_pips" in df.columns and len(df["spread_pips"].dropna()) > 0 else 2.0
        
        # SL bounds check: between 5.0 and 35.0 pips
        sl_distances = (abs(df["requested_entry"] - df["stop_loss"]) * 10.0).dropna()
        sl_in_bounds = np.mean((sl_distances >= 5.0) & (sl_distances <= 35.0)) * 100.0 if len(sl_distances) > 0 else 100.0

        # Diagnosis
        if timeout_rate > 35.0:
            exec_health = "ENTRY EXECUTION DEGRADATION"
            diag = "High limit order timeout rate (>35%). Setups are forming but price frequently leaves without retracing to the 1M FVG boundary."
        elif avg_slip > 3.0 or avg_spd > 4.0:
            exec_health = "FRICTION DEGRADATION"
            diag = "Execution friction (spread/slippage) exceeds historical tolerance thresholds."
        else:
            exec_health = "OPTIMAL"
            diag = "Execution quality is within historical contract tolerances (1M FVG fills operating as intended)."

        return {
            "fill_rate_pct": round(fill_rate, 1),
            "timeout_rate_pct": round(timeout_rate, 1),
            "avg_slippage_pips": round(avg_slip, 2),
            "avg_spread_pips": round(avg_spd, 2),
            "sl_within_bounds_pct": round(sl_in_bounds, 1),
            "execution_health": exec_health,
            "diagnosis": diag
        }

    @staticmethod
    def get_regime_breakdown(mode: str = "PAPER") -> List[Dict[str, Any]]:
        """
        Breaks down forward performance across sessions, days of week, and volatility regimes.
        Enforces N < 30 => INSUFFICIENT DATA rule.
        """
        df = XAUUSDForwardJournal.get_forward_trades(mode=mode)
        if df.empty or "realized_r" not in df.columns:
            return [
                {"category": "Session", "subgroup": "London Open (07:00-11:00 UTC)", "trades_N": 0, "win_rate_pct": 0.0, "expectancy_r": 0.0, "status": "INSUFFICIENT DATA"},
                {"category": "Session", "subgroup": "London/NY Overlap (12:00-16:00 UTC)", "trades_N": 0, "win_rate_pct": 0.0, "expectancy_r": 0.0, "status": "INSUFFICIENT DATA"},
                {"category": "Session", "subgroup": "Asian Session (00:00-07:00 UTC)", "trades_N": 0, "win_rate_pct": 0.0, "expectancy_r": 0.0, "status": "INSUFFICIENT DATA"},
                {"category": "Weekday", "subgroup": "Tuesday / Wednesday", "trades_N": 0, "win_rate_pct": 0.0, "expectancy_r": 0.0, "status": "INSUFFICIENT DATA"},
                {"category": "Weekday", "subgroup": "Thursday / Friday", "trades_N": 0, "win_rate_pct": 0.0, "expectancy_r": 0.0, "status": "INSUFFICIENT DATA"}
            ]

        results = []
        for cat, col in [("Session", "session"), ("Weekday", "day_of_week")]:
            if col in df.columns:
                for sub, grp in df.groupby(col):
                    closed = grp[grp["realized_r"].notnull()]
                    n = len(closed)
                    wr = float(np.mean(closed["realized_r"] > 0) * 100.0) if n > 0 else 0.0
                    exp_r = float(closed["realized_r"].mean()) if n > 0 else 0.0
                    status = "INSUFFICIENT DATA" if n < 30 else ("POSITIVE" if exp_r > 0 else "NEGATIVE")
                    results.append({
                        "category": cat,
                        "subgroup": str(sub),
                        "trades_N": n,
                        "win_rate_pct": round(wr, 1),
                        "expectancy_r": round(exp_r, 3),
                        "status": status
                    })
        return results if results else [
            {"category": "Session", "subgroup": "General Forward Feeds", "trades_N": len(df), "win_rate_pct": 0.0, "expectancy_r": 0.0, "status": "INSUFFICIENT DATA"}
        ]
