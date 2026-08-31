"""
Centralized Explainable Trading Research Engine (Phase 20 UI Enhancement)
Provides structured, context-aware metric explanations, tooltips, interpretations,
sample-size warnings, parameter stability diagnostics, gate failure explanations,
and non-prescriptive risk previews with strictly ZERO emojis.
"""

from typing import Dict, Any, List, Optional, Tuple


# ============================================================================
# 1. CENTRALIZED METRIC DEFINITIONS & THRESHOLDS
# ============================================================================

METRIC_CATALOG: Dict[str, Dict[str, Any]] = {
    "expectancy_r": {
        "display_name": "Expectancy (E[R])",
        "short_desc": "Average return per trade measured in multiples of initial risk (1R).",
        "detailed_desc": "Expectancy measures the average profit or loss per trade in units of R, where 1R represents the amount initially risked. A strategy with +0.50R expectancy gains an average of 0.50 times the risk per trade after modeled execution friction.",
        "good_threshold": 0.25,
        "strong_threshold": 0.40,
        "weak_threshold": 0.10,
        "bad_threshold": 0.00,
        "caveat": "Expectancy alone does not prove a robust edge. Sample size, confidence intervals, drawdown, and out-of-sample performance must also be considered.",
        "why_it_matters": "Positive expectancy indicates that average winning trades outweighed average losing trades after all modeled spread, commission, and slippage costs."
    },
    "bootstrap_ci": {
        "display_name": "95% Bootstrap Confidence Interval",
        "short_desc": "Resampled range of historical expectancy values supported by the trade sample.",
        "detailed_desc": "A non-parametric bootstrap confidence interval constructed by resampling historical trades 5,000 to 10,000 times. If the lower bound is strictly above zero, the historical sample provides stronger evidence that positive expectancy is not a random sampling artifact.",
        "good_threshold": 0.00, # Lower bound > 0.0
        "caveat": "A confidence interval is bounded by the historical sample and assumes the historical market regime is representative.",
        "why_it_matters": "Distinguishes whether an observed positive return is statistically distinct from zero or likely attributable to random variance."
    },
    "holdout_expectancy_r": {
        "display_name": "Final Holdout Expectancy",
        "short_desc": "Expectancy measured strictly on the final untouched 20% chronological dataset.",
        "detailed_desc": "The final untouched portion of historical data that was completely isolated from strategy parameter tuning or model selection. This is one of the strongest tests of whether an observed edge generalizes to unseen market conditions.",
        "good_threshold": 0.25,
        "strong_threshold": 0.40,
        "weak_threshold": 0.10,
        "bad_threshold": 0.00,
        "caveat": "The holdout result is historical evidence on unseen data, not a guarantee of future live performance.",
        "why_it_matters": "Strategies that perform well on training data but collapse on untouched holdout data are overfitted and lack generalizability."
    },
    "wfo": {
        "display_name": "Walk-Forward Optimization (WFO)",
        "short_desc": "Percentage of rolling chronological out-of-sample windows that remained profitable.",
        "detailed_desc": "Walk-Forward Optimization tests whether the strategy continues to perform across rolling out-of-sample chronological windows (e.g. 6-month Train / 2-month OOS) rather than only on a static historical split.",
        "good_threshold": 75.0,
        "strong_threshold": 100.0,
        "bad_threshold": 50.0,
        "caveat": "Four to six windows provide a directional stability check but represent a finite sample of market macro regimes.",
        "why_it_matters": "Confirms that profitability is not isolated to a single fortunate multi-month market trend."
    },
    "monte_carlo": {
        "display_name": "Monte Carlo Simulation",
        "short_desc": "Probability of total loss or extreme drawdown estimated over 10,000 randomized trade sequences.",
        "detailed_desc": "Monte Carlo simulation randomly resamples historical trade outcomes 10,000 times to estimate the distribution of possible equity paths, maximum drawdown depth, and losing streak lengths under shuffled trade sequences.",
        "good_threshold": 1.0, # Prob negative return < 1%
        "caveat": "Simulation risk assumes future trade outcomes follow a distribution similar to the historical sample.",
        "why_it_matters": "Evaluates sequence-of-returns risk and quantifies the probability of experiencing severe drawdowns due to unfortunate trade clustering."
    },
    "max_drawdown_r": {
        "display_name": "Maximum Drawdown (R)",
        "short_desc": "Peak-to-trough equity decline measured in multiples of initial risk.",
        "detailed_desc": "The largest historical decline from a previous equity high-water mark to a subsequent low. For example, a 4.0R drawdown represents a decline equal to 4 times the initial trade risk (or 4% on a 1% risk-per-trade model).",
        "good_threshold": 5.0,
        "warning_threshold": 10.0,
        "bad_threshold": 15.0,
        "caveat": "Future drawdowns frequently exceed historical maximum drawdowns as sample size grows over time.",
        "why_it_matters": "Indicates the emotional and capital resilience required to execute the strategy through adverse streaks."
    },
    "win_rate_pct": {
        "display_name": "Win Rate (%)",
        "short_desc": "Percentage of closed trades that resulted in a positive realized return.",
        "detailed_desc": "The proportion of trades that reached target or closed in profit. Win rate alone does not determine strategy profitability because average win size and average loss size also matter.",
        "good_threshold": 50.0,
        "caveat": "High win rates with poor reward-to-risk (e.g. 90% win rate risking 10R to make 1R) can still produce catastrophic losses.",
        "why_it_matters": "Affects trade execution psychology and losing streak frequency."
    },
    "profit_factor": {
        "display_name": "Profit Factor",
        "short_desc": "Ratio of gross winning profits to gross losing losses.",
        "detailed_desc": "Gross profit divided by gross loss. Values above 1.0 indicate that total winning profit exceeded total losing loss. Values above 2.0 indicate strong structural profitability.",
        "good_threshold": 1.75,
        "strong_threshold": 2.20,
        "bad_threshold": 1.00,
        "caveat": "Profit factor on small samples can be distorted by one or two outlier winning trades.",
        "why_it_matters": "Provides an aggregate ratio of system efficiency across all closed trades."
    },
    "complexity_score": {
        "display_name": "Complexity-Adjusted Score",
        "short_desc": "Holdout expectancy penalized for each added parameter, filter, and timeframe rule.",
        "detailed_desc": "A research score that penalizes strategies requiring excessive indicators, conditional filters, or complex rules. Simpler strategies with fewer degrees of freedom are preferred when performance is similar.",
        "good_threshold": 0.20,
        "strong_threshold": 0.40,
        "bad_threshold": 0.00,
        "caveat": "Penalty deductions are heuristic and intended to prevent unnecessary parameter proliferation.",
        "why_it_matters": "Reduces the risk of curve-fitting by favoring parsimonious mechanical rules."
    },
    "mae": {
        "display_name": "Maximum Adverse Excursion (MAE)",
        "short_desc": "Largest unrealized drawdown experienced by a trade before closing.",
        "detailed_desc": "Measures how far price moved against the entry price during the life of the trade. If losing trades immediately experience -1.0R MAE without any positive movement, entry timing is unrefined.",
        "caveat": "MAE profiles vary significantly between market orders and limit pullback orders.",
        "why_it_matters": "Used to diagnose whether stop loss placement is optimal or excessively wide/tight."
    },
    "mfe": {
        "display_name": "Maximum Favorable Excursion (MFE)",
        "short_desc": "Largest unrealized peak profit reached by a trade before closing.",
        "detailed_desc": "Measures how far price moved in the intended direction. If trades consistently reach +2.0R MFE but end up stopped out at -1.0R, profit-taking or breakeven rules require refinement.",
        "caveat": "High MFE does not help unless the strategy has a mechanism to capture it.",
        "why_it_matters": "Identifies structural profit giveback and informs target calibration."
    },
    "risk_reward_ratio": {
        "display_name": "Reward-to-Risk (RR)",
        "short_desc": "Ratio of projected target profit to initial stop loss distance.",
        "detailed_desc": "Compares potential reward to initial risk. For example, 3.0R means the distance from entry to take profit is three times the distance from entry to stop loss.",
        "good_threshold": 2.0,
        "strong_threshold": 3.0,
        "bad_threshold": 1.0,
        "caveat": "Higher theoretical RR targets reduce win rate unless backed by strong multi-timeframe directional order flow.",
        "why_it_matters": "Allows strategies to remain profitable even with win rates below 40%."
    },
    "slippage": {
        "display_name": "Execution Slippage",
        "short_desc": "Difference between requested order price and actual filled execution price.",
        "detailed_desc": "The variance between the signal price and filled price caused by latency, market volatility, or spread widening. Modeled slippage ensures backtests reflect real-world friction.",
        "caveat": "Slippage can be positive (favorable) on limit orders but is typically adverse on market stop orders.",
        "why_it_matters": "Excessive slippage can erode a theoretical edge on lower-timeframe strategies."
    },
    "latency": {
        "display_name": "Execution Latency",
        "short_desc": "Delay in milliseconds between signal trigger generation and broker order fill.",
        "detailed_desc": "Measures internal processing delay plus network round-trip time. High latency during fast market releases degrades fill quality and increases adverse slippage.",
        "caveat": "Latency impact is higher on 1M precision triggers than on Daily swing models.",
        "why_it_matters": "Ensures that strategy execution remains robust even when broker fills are delayed by 50ms to 1000ms."
    },
    "stage_1d": {
        "display_name": "1D Macro Bias",
        "short_desc": "Daily higher-timeframe directional filter based strictly on completed Daily candles.",
        "detailed_desc": "Determines the higher-timeframe directional context using Daily EMA slope and major swing structure. Only completed Daily candles may be used to prevent lookahead bias.",
        "why_it_matters": "Prevents trading against institutional daily order flow."
    },
    "stage_4h": {
        "display_name": "4H Draw on Liquidity (DOL)",
        "short_desc": "4H target and structural framework establishing the dealing range and targets.",
        "detailed_desc": "Identifies the higher-timeframe draw on liquidity (unmitigated 4H FVGs, equal highs/lows, and dealing range premium/discount) that provide context and targets for intraday setups.",
        "why_it_matters": "Provides high-probability profit targets and directional magnetism."
    },
    "stage_15m": {
        "display_name": "15M Liquidity & Structure",
        "short_desc": "15M liquidity sweep of key session levels followed by Market Structure Shift (MSS).",
        "detailed_desc": "Develops the actual setup through liquidity interaction (sweeping Asian range high/low, PDH, PDL) and confirming structural displacement on closed 15M candles.",
        "why_it_matters": "Ensures smart money accumulation/distribution has occurred before looking for entries."
    },
    "stage_5m": {
        "display_name": "5M Confirmation",
        "short_desc": "Optional 5M displacement confirmation within 3 bars of 15M structure shift.",
        "detailed_desc": "Refinement layer used to confirm momentum and validate 5M fair value gap formation prior to placing execution orders.",
        "why_it_matters": "Filters out false 15M wicks and low-momentum consolidation."
    },
    "stage_1m": {
        "display_name": "1M Precision Entry",
        "short_desc": "1M limit order entry placed at the boundary of a 1M Fair Value Gap.",
        "detailed_desc": "Provides the precision execution trigger. The strategy does not wait for a 15M candle to close before entering, compressing stop loss distance from 42.5 pips to 14.5 pips.",
        "why_it_matters": "Tightens initial risk, dramatically expands realized R-multiples, and avoids entry lag."
    },
    "forward_expectancy": {
        "display_name": "Forward Expectancy (R)",
        "short_desc": "Average realized return per trade on unseen forward Paper/Shadow validation data.",
        "detailed_desc": "The empirical average return in units of initial risk (R) on trades generated strictly after the Phase 21 strategy freeze.",
        "good_threshold": 0.30,
        "strong_threshold": 0.50,
        "bad_threshold": 0.00,
        "caveat": "Forward expectancy on small sample sizes (N < 30) is susceptible to high variance and market regime luck.",
        "why_it_matters": "Determines whether the frozen strategy continues to extract an edge in live unseen market feeds."
    },
    "forward_sample_size": {
        "display_name": "Forward Sample Size (N)",
        "short_desc": "Total number of completed forward Paper or Shadow validation trades.",
        "detailed_desc": "Tracks forward evidence accumulation against the predefined validation target of N >= 100 observations.",
        "good_threshold": 50,
        "strong_threshold": 100,
        "bad_threshold": 30,
        "caveat": "No forward strategy can be declared validated without an adequate sample size spanning diverse market regimes.",
        "why_it_matters": "Dictates statistical confidence and guards against premature conclusions."
    },
    "drift_status": {
        "display_name": "Distribution Drift Status",
        "short_desc": "Comparison of forward excursion profile (MAE/MFE) and holding time against historical baseline.",
        "detailed_desc": "Identifies whether forward trades exhibit similar adverse and favorable excursion distributions as the historical holdout.",
        "why_it_matters": "Early warning system for market regime shifts or structural edge decay."
    },
    "execution_quality": {
        "display_name": "Execution Quality Health",
        "short_desc": "Monitoring of 1M FVG limit fill rate, order lifetime, slippage, and spread friction.",
        "detailed_desc": "Separates strategy failure (setups failing to move in expected direction) from execution degradation (limit orders timing out without fills).",
        "why_it_matters": "Ensures that performance challenges are correctly attributed to execution mechanics versus core strategy invalidation."
    },
    "drawdown_status": {
        "display_name": "Forward Drawdown Status",
        "short_desc": "Evaluation of current forward drawdown against historical Monte Carlo stress distribution.",
        "detailed_desc": "Classifies current forward peak-to-trough decline as Normal (<= 4R), Elevated (4R-7.15R), Stress (7.15R-12R), or Severe (> 12R).",
        "why_it_matters": "Prevents premature strategy abandonment during mathematically normal historical drawdown streaks."
    },
    "edge_consistency_score": {
        "display_name": "Edge Consistency Score",
        "short_desc": "Transparent multi-component score (0-100) assessing forward agreement with the frozen contract.",
        "detailed_desc": "Evaluates expectancy direction, confidence intervals, win rate alignment, drawdown health, and execution quality.",
        "why_it_matters": "Provides an inspectable composite index of forward strategy health."
    },
    "validation_stage": {
        "display_name": "Validation Governance Gate",
        "short_desc": "Predefined stage-based evaluation: Stage 0 (Monitoring) to Stage 3 (Strong Forward Evidence).",
        "detailed_desc": "Enforces strict scientific thresholds before any strategy can be deemed eligible for human review.",
        "why_it_matters": "Prevents discretionary or emotional transitions to live trading."
    }
}


# ============================================================================
# 2. CONTEXT-AWARE VALUE CLASSIFICATION & INTERPRETATION ENGINE
# ============================================================================

class ExplainableResearchClassifier:
    """
    Context-aware evaluator that classifies metrics based on multiple dimensions:
    - Sample size adequacy (N < 30 is always INSUFFICIENT DATA)
    - Bootstrap confidence interval bounds (crosses zero vs strictly above zero)
    - Parameter sensitivity & cost stress survival
    """

    @staticmethod
    def classify_sample_size(n: int) -> Tuple[str, str]:
        """
        Classifies sample size into standard statistical tiers.
        """
        if n < 30:
            return "INSUFFICIENT DATA", "Sample size (N < 30) is too small to draw statistically defensible conclusions."
        elif n < 50:
            return "LIMITED SAMPLE", "Sample size (30 <= N < 50) provides preliminary directional evidence but has wider variance."
        elif n < 100:
            return "MODERATE SAMPLE", "Sample size (50 <= N < 100) provides a defensible statistical baseline for research validation."
        else:
            return "LARGE SAMPLE", "Sample size (N >= 100) provides a robust historical distribution."

    @staticmethod
    def classify_confidence_interval(ci_low: float, ci_high: float) -> Tuple[str, str]:
        """
        Evaluates bootstrap CI relationship to zero.
        """
        if ci_low > 0.0:
            return "POSITIVE EVIDENCE", "The entire 95% confidence interval remains strictly above zero, providing stronger evidence that the historical edge is distinct from zero."
        elif ci_high < 0.0:
            return "NEGATIVE EVIDENCE", "The entire 95% confidence interval remains strictly below zero, confirming negative historical expectancy."
        else:
            return "UNCERTAIN", "Although average expectancy may be positive, the 95% confidence interval crosses zero. The sample does not strongly distinguish the observed result from no edge."

    @staticmethod
    def interpret_expectancy(
        expectancy_r: float,
        trades_n: int,
        ci_low: Optional[float] = None,
        ci_high: Optional[float] = None,
        wfo_pass_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Holistic expectancy classification factoring in sample size and confidence interval.
        NEVER labels a metric as STRONG if N < 30 or CI crosses zero.
        """
        sample_tier, sample_text = ExplainableResearchClassifier.classify_sample_size(trades_n)
        
        # Determine CI status if provided
        ci_status = "UNKNOWN"
        ci_text = ""
        ci_crosses_zero = False
        if ci_low is not None and ci_high is not None:
            ci_status, ci_text = ExplainableResearchClassifier.classify_confidence_interval(ci_low, ci_high)
            ci_crosses_zero = (ci_low <= 0.0 <= ci_high)

        # Baseline expectancy status
        if expectancy_r < 0.0:
            status = "FAILED"
            badge = "FAILED"
            assessment = "Negative historical expectancy. Average losses exceeded average gains."
        elif expectancy_r < 0.10:
            status = "WEAK"
            badge = "WARNING"
            assessment = "Marginal historical expectancy (+0.00R to +0.10R). Vulnerable to real-world friction."
        elif expectancy_r < 0.25:
            status = "PROMISING"
            badge = "WARNING"
            assessment = "Promising historical expectancy (+0.10R to +0.25R). Requires cost stress validation."
        elif expectancy_r < 0.40:
            status = "STRONG"
            badge = "PASS"
            assessment = "Strong historical expectancy (+0.25R to +0.40R) with healthy risk-reward dynamics."
        else:
            status = "VERY STRONG"
            badge = "PASS"
            assessment = "High historical expectancy (>= +0.40R) across the tested historical dataset."

        # STATISTICAL OVERRIDE RULES:
        # 1. If N < 30, it CANNOT be STRONG, VERY STRONG, or PROMISING
        if trades_n < 30:
            status = "INSUFFICIENT DATA"
            badge = "INSUFFICIENT DATA"
            assessment = f"Sample size (N = {trades_n}) is insufficient for statistical confidence regardless of raw expectancy."

        # 2. If CI crosses zero, positive expectancy must be marked UNCERTAIN
        elif ci_crosses_zero and status in ["PROMISING", "STRONG", "VERY STRONG"]:
            status = "UNCERTAIN"
            badge = "WARNING"
            assessment = f"Observed expectancy is positive ({expectancy_r:+.3f}R), but the 95% CI crosses zero, indicating statistical uncertainty."

        # 3. If WFO fails severely (< 50%), downgrade
        if wfo_pass_pct is not None and wfo_pass_pct < 50.0 and status in ["STRONG", "VERY STRONG"]:
            status = "UNSTABLE"
            badge = "WARNING"
            assessment += " However, walk-forward stability failed on more than half of out-of-sample windows."

        return {
            "expectancy_r": expectancy_r,
            "status": status,
            "badge": badge,
            "sample_tier": sample_tier,
            "sample_text": sample_text,
            "ci_status": ci_status,
            "ci_text": ci_text,
            "assessment": assessment,
            "why_it_matters": METRIC_CATALOG["expectancy_r"]["why_it_matters"],
            "caveat": METRIC_CATALOG["expectancy_r"]["caveat"]
        }

    @staticmethod
    def interpret_drawdown(median_dd_r: float, p95_dd_r: float) -> Dict[str, Any]:
        """
        Provides intuitive drawdown explanation with fractional risk examples.
        """
        status = "HEALTHY" if median_dd_r <= 5.0 else ("MODERATE" if median_dd_r <= 10.0 else "ELEVATED")
        return {
            "median_dd_r": median_dd_r,
            "p95_dd_r": p95_dd_r,
            "status": status,
            "typical_drawdown_text": f"Typical simulated drawdown: {median_dd_r:.2f}R",
            "stress_drawdown_text": f"Stress-case (95th percentile) drawdown: {p95_dd_r:.2f}R",
            "interpretation_1pct": f"If risking 1.0% per trade: {median_dd_r:.2f}R ≈ {median_dd_r * 1.0:.2f}% equity drawdown (Stress: {p95_dd_r * 1.0:.2f}%).",
            "interpretation_05pct": f"If risking 0.5% per trade: {median_dd_r:.2f}R ≈ {median_dd_r * 0.5:.2f}% equity drawdown (Stress: {p95_dd_r * 0.5:.2f}%).",
            "note": "These drawdown conversions are illustrative and assume fixed fractional risk."
        }

    @staticmethod
    def interpret_monte_carlo(prob_neg_return_pct: float, prob_20r_dd_pct: float) -> Dict[str, Any]:
        """
        Explains Monte Carlo simulation risk while strictly distinguishing historical simulation vs live risk.
        """
        if prob_neg_return_pct < 1.0 and prob_20r_dd_pct < 1.0:
            status = "VERY LOW HISTORICAL SIMULATION RISK"
            badge = "PASS"
        elif prob_neg_return_pct < 5.0:
            status = "LOW HISTORICAL SIMULATION RISK"
            badge = "PASS"
        elif prob_neg_return_pct < 15.0:
            status = "MODERATE HISTORICAL SIMULATION RISK"
            badge = "WARNING"
        else:
            status = "ELEVATED HISTORICAL SIMULATION RISK"
            badge = "FAILED"

        return {
            "status": status,
            "badge": badge,
            "prob_neg_return_pct": prob_neg_return_pct,
            "prob_20r_dd_pct": prob_20r_dd_pct,
            "meaning": "Across 10,000 simulated trade-order sequences, very few resulted in negative total return or severe drawdown.",
            "mandatory_distinction": "This does NOT mean there is zero real-world probability of losing capital. The simulation is conditional on the historical trade distribution being representative of future market dynamics."
        }

    @staticmethod
    def interpret_parameter_stability(surface_status: str, perturbations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Explains parameter perturbation stability surface (plateau vs fragile cliff).
        """
        is_stable = (surface_status.upper() == "ROBUST_PLATEAU")
        return {
            "status": "STABLE (PLATEAU)" if is_stable else "FRAGILE (OVERFIT RISK)",
            "badge": "PASS" if is_stable else "WARNING",
            "assessment": (
                "Performance remains positive across the tested +/-10% and +/-20% parameter range. This indicates the edge is supported by a broad zone rather than one fragile numerical setting."
                if is_stable else
                "Performance changes substantially when parameters are slightly modified. This increases the risk that historical results depend on curve-fitting."
            ),
            "perturbations": perturbations
        }

    @staticmethod
    def interpret_asset_candidate(
        symbol: str,
        holdout_exp_r: float,
        ci_low: float,
        ci_high: float,
        trades_n: int,
        status: str
    ) -> str:
        """
        Generates dynamic, non-hardcoded interpretation string for the cross-asset leaderboard.
        """
        if trades_n < 30:
            return "Insufficient sample size (N < 30) for statistical validation."
        
        ci_above_zero = (ci_low > 0.0)
        ci_touches_zero = (ci_low <= 0.0 <= ci_high)
        
        if status == "STRONG" and ci_above_zero and holdout_exp_r >= 0.50:
            return "Strongest current historical evidence across all MTF audit criteria."
        elif status == "STRONG" and ci_above_zero:
            return "Strong secondary diversification candidate with positive CI bounds."
        elif status == "PROMISING" and ci_touches_zero:
            return "Positive expectancy but confidence interval touches zero; weaker evidence."
        elif holdout_exp_r < 0.0:
            return "Negative holdout expectancy; strategy fails on this instrument."
        else:
            return f"Moderate historical evidence ({holdout_exp_r:+.3f}R) requiring further validation."

    @staticmethod
    def explain_signal_gate_status(signal_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Explains why a trade is considered or blocked at each gate.
        """
        gates = []
        all_passed = True
        block_reason = None

        gate_checks = [
            ("1D Macro Bias", signal_context.get("bias_1d_pass", True), signal_context.get("bias_1d_val", "BULLISH"), "1D bias conflicts with intraday setup direction."),
            ("4H Draw on Liquidity", signal_context.get("dol_4h_pass", True), signal_context.get("dol_4h_val", "PDH / 4H FVG"), "No clear 4H liquidity draw identified."),
            ("15M Liquidity Sweep", signal_context.get("sweep_15m_pass", True), signal_context.get("sweep_15m_val", "Asian Low Swept"), "Key session high/low was not swept."),
            ("15M Market Structure Shift", signal_context.get("mss_15m_pass", True), signal_context.get("mss_15m_val", "Bullish MSS Confirmed"), "15M displacement break was not confirmed."),
            ("5M Confirmation", signal_context.get("conf_5m_pass", True), signal_context.get("conf_5m_val", "5M FVG Formed"), "5M candle did not confirm displacement."),
            ("1M FVG Limit Trigger", signal_context.get("entry_1m_pass", True), signal_context.get("entry_1m_val", "Limit at 1M FVG Boundary"), "Price did not retrace to 1M FVG boundary within time window."),
            ("Risk Allocation Gate", signal_context.get("risk_pass", True), signal_context.get("risk_val", "0.50% / $10"), "Trade risk exceeds maximum single-trade threshold."),
            ("Directional Correlation Gate", signal_context.get("corr_pass", True), signal_context.get("corr_val", "PASS"), "Correlated currency exposure limit exceeded."),
            ("System Health Evaluator", signal_context.get("health_pass", True), signal_context.get("health_val", "HEALTHY"), "Global kill switch or emergency halt is active.")
        ]

        for name, passed, val_text, fail_msg in gate_checks:
            gates.append({
                "gate_name": name,
                "status": "PASS" if passed else "BLOCKED",
                "value": val_text,
                "message": "Gate criteria satisfied." if passed else fail_msg
            })
            if not passed and all_passed:
                all_passed = False
                block_reason = fail_msg

        return {
            "eligible": all_passed,
            "overall_status": "ELIGIBLE FOR PAPER/SHADOW EXECUTION" if all_passed else "BLOCKED",
            "block_reason": block_reason,
            "gates": gates
        }

    @staticmethod
    def explain_risk_preview(
        risk_amount_usd: float,
        stop_pips: float,
        target_pips: float,
        rr_ratio: float,
        account_balance: float = 2000.0
    ) -> Dict[str, Any]:
        """
        Explains risk parameters clearly and safely without assumptions.
        """
        risk_pct = (risk_amount_usd / account_balance) * 100.0 if account_balance > 0 else 0.5
        reward_amount_usd = risk_amount_usd * rr_ratio

        if rr_ratio >= 3.0:
            assessment = "EXCELLENT"
            assessment_text = f"The projected reward ({reward_amount_usd:.2f} USD) is {rr_ratio:.1f} times the initial risk."
        elif rr_ratio >= 2.0:
            assessment = "GOOD"
            assessment_text = f"The projected reward ({reward_amount_usd:.2f} USD) is {rr_ratio:.1f} times the initial risk."
        elif rr_ratio >= 1.0:
            assessment = "FAIR"
            assessment_text = f"Reward is modest relative to risk ({rr_ratio:.1f}R)."
        else:
            assessment = "SUB-OPTIMAL"
            assessment_text = "Projected reward is less than initial risk."

        return {
            "initial_risk_usd": risk_amount_usd,
            "risk_pct": risk_pct,
            "stop_pips": stop_pips,
            "target_pips": target_pips,
            "projected_reward_usd": reward_amount_usd,
            "rr_ratio": rr_ratio,
            "assessment": assessment,
            "assessment_text": assessment_text,
            "max_loss_explanation": "This is the maximum planned loss if Stop Loss is executed under normal market spread conditions."
        }


# ============================================================================
# 3. HELPER FOR STREAMLIT TOOLTIPS & EXPANDERS
# ============================================================================

def get_tooltip(metric_id: str) -> str:
    """Returns the standardized tooltip text for a metric ID."""
    entry = METRIC_CATALOG.get(metric_id, {})
    return entry.get("detailed_desc", entry.get("short_desc", "Metric definition."))


def get_why_text(metric_id: str) -> str:
    """Returns why the metric matters and its statistical caveat."""
    entry = METRIC_CATALOG.get(metric_id, {})
    why = entry.get("why_it_matters", "")
    caveat = entry.get("caveat", "")
    return f"Why this matters:\n{why}\n\nStatistical caveat:\n{caveat}"
