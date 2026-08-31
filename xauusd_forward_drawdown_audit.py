"""
Phase 29 — XAUUSD Forward Drawdown, Consecutive Loss & Recovery Audit Engine
Tracks streaks, max/average drawdowns, recovery factors, and classifies drawdown states (Normal, Elevated, Stress, Severe).
"""

from typing import Dict, List, Any, Optional
import numpy as np


class ForwardDrawdownAuditor:
    """
    Evaluates forward equity curve drawdowns, win/loss streaks, and recovery metrics.
    """
    STRESS_CEILING_R = 7.15
    SEVERE_CEILING_R = 12.00

    @staticmethod
    def audit_drawdown(returns: List[float]) -> Dict[str, Any]:
        if not returns:
            return {
                "trades_n": 0,
                "current_drawdown_r": 0.0,
                "max_drawdown_r": 0.0,
                "avg_drawdown_r": 0.0,
                "max_consecutive_losses": 0,
                "max_consecutive_wins": 0,
                "current_streak_type": "NONE",
                "current_streak_count": 0,
                "recovery_factor": 0.0,
                "drawdown_status": "NORMAL",
                "color": "#00ffcc",
                "human_meaning": "No forward trade observations recorded yet."
            }

        # 1. Equity curve and drawdown calculation
        cum = np.cumsum([0.0] + returns)
        running_max = np.maximum.accumulate(cum)
        drawdowns = running_max - cum
        
        max_dd = float(np.max(drawdowns))
        current_dd = float(drawdowns[-1])
        avg_dd = float(np.mean(drawdowns[drawdowns > 0])) if np.any(drawdowns > 0) else 0.0
        
        cum_r = float(cum[-1])
        recovery_factor = (cum_r / max_dd) if max_dd > 0 else (cum_r if cum_r > 0 else 0.0)

        # 2. Consecutive wins and losses
        max_wins = 0
        max_losses = 0
        curr_wins = 0
        curr_losses = 0

        for r in returns:
            if r > 0:
                curr_wins += 1
                curr_losses = 0
                max_wins = max(max_wins, curr_wins)
            else:
                curr_losses += 1
                curr_wins = 0
                max_losses = max(max_losses, curr_losses)

        # 3. Current streak
        last_r = returns[-1]
        streak_type = "WINS" if last_r > 0 else "LOSSES"
        streak_count = 0
        for r in reversed(returns):
            if (streak_type == "WINS" and r > 0) or (streak_type == "LOSSES" and r <= 0):
                streak_count += 1
            else:
                break

        # 4. Classification
        if max_dd <= 4.00:
            status = "NORMAL"
            color = "#00ffcc"
            meaning = "Drawdown is within normal variance bounds (Historical median: 3.84R)."
        elif max_dd <= ForwardDrawdownAuditor.STRESS_CEILING_R:
            status = "ELEVATED"
            color = "#f59e0b"
            meaning = f"Drawdown ({max_dd:.2f}R) is larger than typical historical drawdown but remains below the 95th-percentile stress ceiling (7.15R)."
        elif max_dd <= ForwardDrawdownAuditor.SEVERE_CEILING_R:
            status = "STRESS"
            color = "#f97316"
            meaning = f"Drawdown ({max_dd:.2f}R) has exceeded the historical 7.15R stress ceiling. Human review recommended."
        else:
            status = "SEVERE"
            color = "#ef4444"
            meaning = f"Drawdown ({max_dd:.2f}R) has breached the severe 12.0R boundary. Research integrity alert triggered."

        return {
            "trades_n": len(returns),
            "current_drawdown_r": round(current_dd, 2),
            "max_drawdown_r": round(max_dd, 2),
            "avg_drawdown_r": round(avg_dd, 2),
            "cumulative_r": round(cum_r, 2),
            "max_consecutive_losses": max_losses,
            "max_consecutive_wins": max_wins,
            "current_streak_type": streak_type,
            "current_streak_count": streak_count,
            "recovery_factor": round(recovery_factor, 2),
            "drawdown_status": status,
            "color": color,
            "human_meaning": meaning
        }
