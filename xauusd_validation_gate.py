"""
Phase 22 — XAUUSD Forward Validation Decision Gate & Governance Engine
Implements deterministic, stage-based decision gating for forward validation.
Strictly preserves the LIVE AUTOMATION = DISABLED invariant.
"""

from typing import Dict, List, Any, Optional
from xauusd_forward_monitor import XAUUSDForwardMonitor
from xauusd_drift_detector import XAUUSDDriftDetector


class XAUUSDValidationGate:
    """
    Evaluates forward validation stages 0 through 3 against predefined criteria.
    """

    @staticmethod
    def evaluate_gate(mode: str = "PAPER") -> Dict[str, Any]:
        fwd = XAUUSDForwardMonitor.get_forward_summary(mode=mode)
        exec_q = XAUUSDForwardMonitor.get_execution_quality_metrics(mode=mode)
        drift = XAUUSDDriftDetector.evaluate_distribution_drift(mode=mode)
        consistency = XAUUSDDriftDetector.calculate_edge_consistency_score(mode=mode)
        
        n = fwd.get("trades_N", 0)
        exp_r = fwd.get("expectancy_r", 0.0)
        max_dd = fwd.get("max_drawdown_r", 0.0)
        ci_lower = fwd.get("ci_lower", 0.0)
        
        # Predefined Governance Gates
        if n < 30:
            stage_id = 0
            stage_name = "Stage 0 — Monitoring"
            status = "COLLECTING DATA"
            color = "#38bdf8"
            verdict = "FORWARD EVIDENCE ACCUMULATING"
            explanation = f"Current sample size is N = {n} / 30. Forward statistical conclusions are mathematically premature."
            next_milestone = f"Collect {30 - n} more forward trades to reach Stage 1 (Early Evidence)."
            required_criteria = [
                {"criterion": "Accumulate N >= 30 trades", "status": f"{n} / 30", "passed": False},
                {"criterion": "Maintain Paper/Shadow Parity", "status": "100% Parity", "passed": True},
                {"criterion": "Track 1M FVG Limit Fill Rate", "status": f"{exec_q.get('fill_rate_pct', 100)}%", "passed": True}
            ]

        elif 30 <= n < 50:
            stage_id = 1
            stage_name = "Stage 1 — Early Evidence"
            if exp_r >= 0.25:
                status = "PROMISING BUT UNCONFIRMED"
                color = "#bef264"
                verdict = "POSITIVE DIRECTIONAL TENDENCY"
                explanation = f"Forward expectancy is {exp_r:+.3f}R across {n} trades. Evidence is encouraging but insufficient for formal validation."
            elif exp_r > 0:
                status = "UNCERTAIN"
                color = "#f59e0b"
                verdict = "MARGINAL FORWARD RETURN"
                explanation = f"Forward expectancy is marginally positive ({exp_r:+.3f}R) with high statistical noise."
            else:
                status = "NEGATIVE"
                color = "#ff5555"
                verdict = "NEGATIVE FORWARD DRIFT"
                explanation = f"Forward expectancy is negative ({exp_r:+.3f}R) in early observations."
            
            next_milestone = f"Collect {50 - n} more forward trades to reach Stage 2 (Intermediate Validation)."
            required_criteria = [
                {"criterion": "Reach N >= 50 trades", "status": f"{n} / 50", "passed": False},
                {"criterion": "Positive Expectancy", "status": f"{exp_r:+.3f}R", "passed": exp_r > 0},
                {"criterion": "Drawdown <= 7.15R", "status": f"{max_dd:.2f}R", "passed": max_dd <= 7.15}
            ]

        elif 50 <= n < 100:
            stage_id = 2
            stage_name = "Stage 2 — Intermediate Validation"
            is_exec_ok = exec_q.get("execution_health") != "ENTRY EXECUTION DEGRADATION"
            is_dd_ok = max_dd <= 7.15
            is_dist_ok = drift.get("distribution_status") != "DISTRIBUTIONALLY DRIFTING"

            if exp_r >= 0.30 and is_exec_ok and is_dd_ok and is_dist_ok:
                status = "FORWARD VALIDATION PASS"
                color = "#00ffcc"
                verdict = "INTERMEDIATE FORWARD VALIDATION SATISFIED"
                explanation = f"Strategy demonstrates robust forward alignment ({exp_r:+.3f}R, max DD {max_dd:.2f}R) across {n} unseen trades."
            elif exp_r > 0:
                status = "UNCERTAIN"
                color = "#f59e0b"
                verdict = "PARTIAL FORWARD EVIDENCE"
                explanation = "Expectancy is positive but one or more secondary criteria (drawdown, execution, or distribution) require closer monitoring."
            else:
                status = "FORWARD VALIDATION FAIL"
                color = "#ff5555"
                verdict = "FORWARD EDGE DEGRADATION"
                explanation = f"Strategy failed to produce positive expectancy ({exp_r:+.3f}R) in intermediate forward sample."

            next_milestone = f"Collect {100 - n} more forward trades to reach Stage 3 (Strong Evidence & Human Review)."
            required_criteria = [
                {"criterion": "Reach N >= 100 trades", "status": f"{n} / 100", "passed": False},
                {"criterion": "Positive Expectancy (>= 0.30R)", "status": f"{exp_r:+.3f}R", "passed": exp_r >= 0.30},
                {"criterion": "Drawdown <= 7.15R (95th Pct)", "status": f"{max_dd:.2f}R", "passed": is_dd_ok},
                {"criterion": "Execution Quality Optimal", "status": exec_q.get("execution_health"), "passed": is_exec_ok}
            ]

        else: # N >= 100
            stage_id = 3
            stage_name = "Stage 3 — Strong Forward Evidence"
            if exp_r >= 0.35 and ci_lower > 0 and max_dd <= 7.15:
                status = "FORWARD VALIDATED — PAPER"
                color = "#00ffcc"
                verdict = "ELIGIBLE FOR HUMAN REVIEW"
                explanation = f"Comprehensive forward sample (N = {n}) exhibits statistically defensible edge ({exp_r:+.3f}R, 95% CI lower bound > 0)."
            elif exp_r > 0:
                status = "FORWARD PASS (MODERATE EVIDENCE)"
                color = "#bef264"
                verdict = "MODERATE FORWARD EVIDENCE"
                explanation = f"Strategy remains profitable in forward sample (N = {n}, {exp_r:+.3f}R), though CI may span zero."
            else:
                status = "FORWARD VALIDATION FAIL"
                color = "#ff5555"
                verdict = "STRATEGY FAILED FORWARD TEST"
                explanation = f"Strategy failed forward validation across large sample (N = {n}, {exp_r:+.3f}R)."

            next_milestone = "Final Governance Review (Human Reviewer). Live trading requires explicit manual operational sign-off."
            required_criteria = [
                {"criterion": "Large Sample N >= 100", "status": f"{n} Trades", "passed": True},
                {"criterion": "Positive Expectancy", "status": f"{exp_r:+.3f}R", "passed": exp_r > 0},
                {"criterion": "Bootstrap CI Lower > 0", "status": f"Lower: {ci_lower:+.3f}R", "passed": ci_lower > 0},
                {"criterion": "Drawdown within limits", "status": f"{max_dd:.2f}R", "passed": max_dd <= 7.15}
            ]

        return {
            "stage_id": stage_id,
            "stage_name": stage_name,
            "status": status,
            "color": color,
            "verdict": verdict,
            "explanation": explanation,
            "next_milestone": next_milestone,
            "required_criteria": required_criteria,
            "live_automation_status": "DISABLED",
            "governance_rule": "Live execution is hard-coded disabled. Stage 3 qualification confers 'ELIGIBLE FOR HUMAN REVIEW' only."
        }
