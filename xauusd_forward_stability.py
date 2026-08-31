"""
Phase 29 — XAUUSD Forward Rolling & Chronological Stability Engine
Evaluates rolling forward windows (10, 20, 30, 50 trades) and time-split chronological stability (Early, Middle, Recent).
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

from xauusd_forward_validator import XAUUSDForwardJournal


class RollingStabilityEngine:
    """
    Evaluates rolling trade windows and chronological time-splits.
    """
    HISTORICAL_BASELINE_EXP_R = 0.637

    @staticmethod
    def evaluate_rolling_stability(returns: List[float], window_sizes: List[int] = [10, 20, 30, 50]) -> Dict[str, Any]:
        """
        Computes rolling statistics for specified window sizes.
        """
        n_total = len(returns)
        windows_summary = []

        for w in window_sizes:
            if n_total < w:
                windows_summary.append({
                    "window_size": w,
                    "status": "INSUFFICIENT DATA",
                    "trades_n": n_total,
                    "latest_expectancy_r": np.mean(returns) if n_total > 0 else 0.0,
                    "latest_win_rate_pct": (sum(1 for r in returns if r > 0) / n_total * 100.0) if n_total > 0 else 0.0,
                    "latest_profit_factor": 0.0,
                    "latest_max_dd_r": 0.0,
                    "classification": "INSUFFICIENT DATA",
                    "explanation": f"Sample size (N = {n_total}) has not yet reached rolling window threshold (W = {w})."
                })
                continue

            # Calculate rolling stats
            rolling_exp = [np.mean(returns[i:i+w]) for i in range(n_total - w + 1)]
            latest_window = returns[-w:]
            latest_exp = float(np.mean(latest_window))
            latest_wr = (sum(1 for r in latest_window if r > 0) / w * 100.0)
            
            pos_sum = sum(r for r in latest_window if r > 0)
            neg_sum = abs(sum(r for r in latest_window if r < 0))
            latest_pf = (pos_sum / neg_sum) if neg_sum > 0 else (99.0 if pos_sum > 0 else 1.0)
            
            # Max DD in latest window
            cum = np.cumsum([0.0] + latest_window)
            running_max = np.maximum.accumulate(cum)
            dds = running_max - cum
            max_dd = float(np.max(dds))

            # Classification
            consecutive_negative_windows = sum(1 for exp in reversed(rolling_exp) if exp <= 0)
            
            if consecutive_negative_windows >= 5:
                classification = "PERSISTENT DEGRADATION"
                color = "#ef4444"
                expl = f"5+ consecutive rolling {w}-trade windows have shown non-positive expectancy."
            elif latest_exp < 0:
                classification = "WATCH"
                color = "#f59e0b"
                expl = f"Latest {w}-trade rolling window is negative ({latest_exp:+.3f}R); monitor for persistence."
            elif latest_exp >= RollingStabilityEngine.HISTORICAL_BASELINE_EXP_R * 0.75:
                classification = "STABLE"
                color = "#00ffcc"
                expl = f"Rolling {w}-trade expectancy ({latest_exp:+.3f}R) retains >= 75% of historical holdout (+0.637R)."
            else:
                classification = "MILD VARIATION"
                color = "#bef264"
                expl = f"Rolling {w}-trade expectancy ({latest_exp:+.3f}R) is positive within normal variance envelope."

            windows_summary.append({
                "window_size": w,
                "status": "VALIDATED",
                "trades_n": w,
                "latest_expectancy_r": round(latest_exp, 3),
                "latest_win_rate_pct": round(latest_wr, 1),
                "latest_profit_factor": round(latest_pf, 2),
                "latest_max_dd_r": round(max_dd, 2),
                "classification": classification,
                "color": color,
                "explanation": expl
            })

        return {
            "total_trades_n": n_total,
            "windows": windows_summary
        }

    @staticmethod
    def evaluate_time_split_stability(returns: List[float]) -> Dict[str, Any]:
        """
        Chronologically splits forward observations into Early, Middle, Recent.
        Never shuffles returns.
        """
        n = len(returns)
        if n < 9:
            return {
                "status": "INSUFFICIENT DATA",
                "explanation": "At least 9 trades required for 3-way chronological split (Early/Middle/Recent).",
                "overall_stability": "INSUFFICIENT DATA",
                "periods": []
            }

        # Divide into 3 roughly equal chronological partitions
        chunk_size = n // 3
        early = returns[:chunk_size]
        middle = returns[chunk_size:2*chunk_size]
        recent = returns[2*chunk_size:]

        periods_data = []
        for name, part in [("Early", early), ("Middle", middle), ("Recent", recent)]:
            n_part = len(part)
            exp_r = float(np.mean(part)) if n_part > 0 else 0.0
            wr = (sum(1 for r in part if r > 0) / n_part * 100.0) if n_part > 0 else 0.0
            
            pos_sum = sum(r for r in part if r > 0)
            neg_sum = abs(sum(r for r in part if r < 0))
            pf = (pos_sum / neg_sum) if neg_sum > 0 else (99.0 if pos_sum > 0 else 1.0)
            
            cum = np.cumsum([0.0] + part)
            running_max = np.maximum.accumulate(cum)
            max_dd = float(np.max(running_max - cum))

            periods_data.append({
                "period": name,
                "trades_n": n_part,
                "expectancy_r": round(exp_r, 3),
                "win_rate_pct": round(wr, 1),
                "profit_factor": round(pf, 2),
                "max_drawdown_r": round(max_dd, 2)
            })

        # Overall trend
        early_exp = periods_data[0]["expectancy_r"]
        recent_exp = periods_data[2]["expectancy_r"]

        if recent_exp > early_exp + 0.20:
            overall = "IMPROVING"
            color = "#00ffcc"
        elif recent_exp < early_exp - 0.35 and recent_exp <= 0:
            overall = "WEAKENING"
            color = "#ef4444"
        else:
            overall = "STABLE"
            color = "#bef264"

        return {
            "status": "VALIDATED",
            "overall_stability": overall,
            "color": color,
            "periods": periods_data
        }
