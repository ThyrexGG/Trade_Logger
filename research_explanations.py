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
    "expectancy": {
        "display_name": "Expectancy (E[R])",
        "short_desc": "Average return per trade measured in multiples of initial risk (1R).",
        "what_is_it": "Average R-multiple earned per completed trade after factoring in winning and losing trades.",
        "detailed_desc": "Expectancy measures the average profit or loss per trade in units of R, where 1R represents the amount initially risked. A strategy with +0.50R expectancy gains an average of 0.50 times the risk per trade after modeled execution friction.",
        "good_or_bad": ">= +0.50R is Strong; +0.25R to +0.50R is Good; 0.00R to +0.25R is Weak Positive; < 0.00R is Negative.",
        "why_it_matters": "Positive expectancy indicates that average winning profits exceeded average losses across closed trades.",
        "what_to_watch": "Verify that expectancy remains positive as the forward sample grows and confidence intervals narrow.",
        "caveat": "A positive point estimate on a small sample does not prove the underlying edge is statistically positive.",
        "good_threshold": 0.25,
        "strong_threshold": 0.40,
        "weak_threshold": 0.10,
        "bad_threshold": 0.00
    },
    "expectancy_r": {
        "display_name": "Expectancy (E[R])",
        "short_desc": "Average return per trade measured in multiples of initial risk (1R).",
        "what_is_it": "Average R-multiple earned per completed trade after factoring in winning and losing trades.",
        "detailed_desc": "Expectancy measures the average profit or loss per trade in units of R, where 1R represents the amount initially risked. A strategy with +0.50R expectancy gains an average of 0.50 times the risk per trade after modeled execution friction.",
        "good_or_bad": ">= +0.50R is Strong; +0.25R to +0.50R is Good; 0.00R to +0.25R is Weak Positive; < 0.00R is Negative.",
        "why_it_matters": "Positive expectancy indicates that average winning profits exceeded average losses across closed trades.",
        "what_to_watch": "Verify that expectancy remains positive as the forward sample grows and confidence intervals narrow.",
        "caveat": "A positive point estimate on a small sample does not prove the underlying edge is statistically positive."
    },
    "forward_expectancy": {
        "display_name": "Forward Expectancy (E[R])",
        "short_desc": "Average realized return per trade on unseen forward Paper/Shadow validation data.",
        "what_is_it": "Average R-multiple earned per trade strictly on data generated after the Phase 21 freeze.",
        "detailed_desc": "The empirical average return in units of initial risk (R) on trades generated strictly after the Phase 21 strategy freeze.",
        "good_or_bad": ">= +0.35R is Good; 0.00R to +0.35R is Weak/Uncertain; < 0.00R is Negative.",
        "why_it_matters": "Determines whether the frozen strategy continues extracting an edge on live unseen market data.",
        "what_to_watch": "Check whether forward expectancy aligns with the historical holdout (+0.637R) or shows severe degradation.",
        "caveat": "Small forward sample sizes (N < 30) exhibit high variance and may reflect short-term market streaks."
    },
    "win_rate": {
        "display_name": "Win Rate (%)",
        "short_desc": "Percentage of closed trades that resulted in a positive realized return.",
        "what_is_it": "The proportion of completed trades that ended in profit rather than a loss.",
        "detailed_desc": "The percentage of closed trades that reached target or closed in profit. Win rate alone does not determine strategy profitability because average win size and average loss size also matter.",
        "good_or_bad": "50% to 65% is standard for 1:2 to 1:3 reward-to-risk strategies. > 70% is uncommon for multi-R targets.",
        "why_it_matters": "Affects trade execution psychology and losing streak frequency.",
        "what_to_watch": "Ensure win rate is evaluated in tandem with average reward-to-risk ratio.",
        "caveat": "A high win rate with poor reward-to-risk (e.g. risking 10R to make 1R) can still produce catastrophic drawdowns."
    },
    "win_rate_pct": {
        "display_name": "Win Rate (%)",
        "short_desc": "Percentage of closed trades that resulted in a positive realized return.",
        "what_is_it": "The proportion of completed trades that ended in profit rather than a loss.",
        "detailed_desc": "The percentage of closed trades that reached target or closed in profit. Win rate alone does not determine strategy profitability because average win size and average loss size also matter.",
        "good_or_bad": "50% to 65% is standard for 1:2 to 1:3 reward-to-risk strategies. > 70% is uncommon for multi-R targets.",
        "why_it_matters": "Affects trade execution psychology and losing streak frequency.",
        "what_to_watch": "Ensure win rate is evaluated in tandem with average reward-to-risk ratio.",
        "caveat": "A high win rate with poor reward-to-risk (e.g. risking 10R to make 1R) can still produce catastrophic drawdowns."
    },
    "profit_factor": {
        "display_name": "Profit Factor",
        "short_desc": "Ratio of gross winning profits to gross losing losses.",
        "what_is_it": "Total gross profit divided by total gross loss across all closed trades.",
        "detailed_desc": "Gross profit divided by gross loss. Values above 1.0 indicate that total winning profit exceeded total losing loss. Values above 2.0 indicate strong structural profitability.",
        "good_or_bad": "> 2.0 is Strong; 1.5 to 2.0 is Good; 1.0 to 1.5 is Marginal; < 1.0 is Losing.",
        "why_it_matters": "Provides an aggregate ratio of system efficiency across all closed trades.",
        "what_to_watch": "Watch for sudden drops below 1.5 which may indicate regime changes or cost friction.",
        "caveat": "Profit factor on small samples can be distorted by one or two outlier winning trades."
    },
    "r_multiple": {
        "display_name": "R-Multiple",
        "short_desc": "Trade outcome normalized as a multiple of initial risk.",
        "what_is_it": "A metric that expresses profit or loss in units of risk. A +3R trade earned 3 times the initial stop-loss amount.",
        "detailed_desc": "Normalizes all trade outcomes so different position sizes and pip stop distances can be compared on an identical mathematical scale.",
        "good_or_bad": "Consistent positive average R (+0.30R to +0.60R) represents healthy strategy mechanics.",
        "why_it_matters": "Eliminates currency distortions and allows objective cross-asset and multi-timeframe comparison.",
        "what_to_watch": "Look for symmetry between planned target R and realized R after slippage.",
        "caveat": "Realized R can be reduced by spread and slippage during volatile news releases."
    },
    "bootstrap_ci": {
        "display_name": "95% Bootstrap Confidence Interval",
        "short_desc": "Resampled range of historical expectancy values supported by the trade sample.",
        "what_is_it": "A statistically resampled range representing where the true average expectancy likely falls with 95% confidence.",
        "detailed_desc": "A non-parametric bootstrap confidence interval constructed by resampling trades 5,000 to 10,000 times. If the lower bound is strictly above zero, the sample provides stronger evidence that positive expectancy is not a random artifact.",
        "good_or_bad": "Lower bound > 0 is Positive Evidence; Interval crossing zero is Uncertain; Upper bound < 0 is Negative.",
        "why_it_matters": "Distinguishes whether an observed positive return is statistically distinct from zero or likely attributable to random variance.",
        "what_to_watch": "Watch if the lower bound crosses above zero as sample size increases.",
        "caveat": "A confidence interval is bounded by the historical sample and assumes the market regime is representative."
    },
    "sample_size": {
        "display_name": "Sample Size (N)",
        "short_desc": "Total number of completed trade observations.",
        "what_is_it": "The total number of closed trades analyzed in the research dataset or forward stream.",
        "detailed_desc": "Sample size determines the statistical reliability of all other metrics. Larger samples reduce standard error and provide narrower confidence intervals.",
        "good_or_bad": "N < 30: Insufficient Data; 30-49: Limited Sample; 50-99: Moderate Sample; 100+: Large Sample.",
        "why_it_matters": "Prevents researchers from drawing false conclusions from small streaks of good or bad luck.",
        "what_to_watch": "Track progress toward the N = 100 benchmark before making formal validation decisions.",
        "caveat": "A large sample in a single market regime can still fail when macro conditions shift."
    },
    "forward_sample_size": {
        "display_name": "Forward Sample Size (N)",
        "short_desc": "Total number of completed forward Paper or Shadow validation trades.",
        "what_is_it": "Count of trades executed strictly after the strategy freeze on live market feeds.",
        "detailed_desc": "Tracks forward evidence accumulation against the predefined validation target of N >= 100 observations.",
        "good_or_bad": "N < 30 is Insufficient Data; N >= 50 is Moderate; N >= 100 is Defensible.",
        "why_it_matters": "Dictates statistical confidence and guards against premature conclusions.",
        "what_to_watch": "Continue collecting forward data without modifying frozen strategy rules.",
        "caveat": "No forward strategy can be declared validated without an adequate sample size spanning diverse market regimes."
    },
    "holdout": {
        "display_name": "Final Holdout Dataset",
        "short_desc": "Untouched chronological dataset reserved for final unbiased validation.",
        "what_is_it": "The final 20% of historical data that was completely hidden during strategy design and tuning.",
        "detailed_desc": "The gold standard of historical backtesting. Because parameters were never fitted to this data, it provides an honest test of generalizability.",
        "good_or_bad": "Positive holdout expectancy (+0.25R to +0.60R) indicates strong generalizability.",
        "why_it_matters": "Protects against overfitting and data snooping biases.",
        "what_to_watch": "Compare forward paper results directly against the holdout baseline.",
        "caveat": "Holdout success is historical evidence; future market dynamics can still evolve."
    },
    "holdout_expectancy_r": {
        "display_name": "Final Holdout Expectancy",
        "short_desc": "Expectancy measured strictly on the final untouched 20% chronological dataset.",
        "what_is_it": "Average R-multiple achieved on the hidden historical holdout data.",
        "detailed_desc": "The final untouched portion of historical data that was completely isolated from parameter tuning. For XAUUSD, this baseline is locked at +0.637R.",
        "good_or_bad": ">= +0.40R is Strong; +0.25R to +0.40R is Good; < 0.00R is Failed.",
        "why_it_matters": "Confirms the strategy extracts value without parameter memorization.",
        "what_to_watch": "Use this as the benchmark against which forward paper expectancy is compared.",
        "caveat": "The holdout result is historical evidence on unseen data, not a guarantee of future live performance."
    },
    "validation": {
        "display_name": "Validation Dataset",
        "short_desc": "Intermediate out-of-sample partition used for model comparison.",
        "what_is_it": "The secondary 20% historical split used to compare different execution models before final holdout testing.",
        "detailed_desc": "Used in the research lab to select the best execution timeframe (1M FVG) before touching the holdout data.",
        "good_or_bad": "Consistency between Training, Validation, and Holdout indicates a robust edge.",
        "why_it_matters": "Provides a multi-tier defense against selection bias.",
        "what_to_watch": "Check for degradation between Training and Validation.",
        "caveat": "Repeated testing on validation data can eventually cause validation overfitting."
    },
    "wfo": {
        "display_name": "Walk-Forward Optimization (WFO)",
        "short_desc": "Percentage of rolling chronological out-of-sample windows that remained profitable.",
        "what_is_it": "A test that slides a training and testing window forward in time to verify stability across multiple market cycles.",
        "detailed_desc": "Walk-Forward Optimization tests whether the strategy continues to perform across rolling out-of-sample chronological windows rather than only on a static split.",
        "good_or_bad": "100% (4/4 windows) is Robust; >= 75% is Pass; < 50% is Fragile.",
        "why_it_matters": "Confirms that profitability is not isolated to a single fortunate multi-month market trend.",
        "what_to_watch": "Look for consistent window expectancy rather than one massive winning window carrying the average.",
        "caveat": "Four to six windows provide a directional stability check but represent a finite sample of market macro regimes."
    },
    "walk_forward": {
        "display_name": "Walk-Forward Optimization (WFO)",
        "short_desc": "Percentage of rolling chronological out-of-sample windows that remained profitable.",
        "what_is_it": "A test that slides a training and testing window forward in time to verify stability across multiple market cycles.",
        "detailed_desc": "Walk-Forward Optimization tests whether the strategy continues to perform across rolling out-of-sample chronological windows rather than only on a static split.",
        "good_or_bad": "100% (4/4 windows) is Robust; >= 75% is Pass; < 50% is Fragile.",
        "why_it_matters": "Confirms that profitability is not isolated to a single fortunate multi-month market trend.",
        "what_to_watch": "Look for consistent window expectancy rather than one massive winning window carrying the average.",
        "caveat": "Four to six windows provide a directional stability check but represent a finite sample of market macro regimes."
    },
    "monte_carlo": {
        "display_name": "Monte Carlo Simulation",
        "short_desc": "Probability of total loss or extreme drawdown estimated over 10,000 randomized trade sequences.",
        "what_is_it": "A statistical simulation that shuffles trade order 10,000 times to test sequence-of-returns risk.",
        "detailed_desc": "Randomly resamples trade outcomes 10,000 times to estimate the distribution of possible equity paths, maximum drawdown depth, and losing streak lengths under shuffled sequences.",
        "good_or_bad": "< 1% probability of severe drawdown is Very Low Risk; < 5% is Low Risk; > 15% is Elevated Risk.",
        "why_it_matters": "Evaluates sequence-of-returns risk and quantifies the probability of experiencing severe drawdowns due to unfortunate trade clustering.",
        "what_to_watch": "Check the 95th-percentile simulated drawdown (7.15R) as a realistic stress reference.",
        "caveat": "Simulation risk assumes future trade outcomes follow a distribution similar to the historical sample."
    },
    "max_drawdown_r": {
        "display_name": "Maximum Drawdown (R)",
        "short_desc": "Peak-to-trough equity decline measured in multiples of initial risk.",
        "what_is_it": "The largest peak-to-trough drop in equity measured in units of risk (R).",
        "detailed_desc": "The largest historical decline from a previous equity high-water mark to a subsequent low. For example, a 4.0R drawdown represents a decline equal to 4 times the initial trade risk.",
        "good_or_bad": "<= 4.0R is Normal; 4.0R-7.15R is Elevated; 7.15R-12.0R is Stress; > 12.0R is Severe.",
        "why_it_matters": "Indicates the emotional and capital resilience required to execute the strategy through adverse streaks.",
        "what_to_watch": "Monitor current forward drawdown against the historical 95th percentile stress level (7.15R).",
        "caveat": "Future drawdowns frequently exceed historical maximum drawdowns as sample size grows over time."
    },
    "drawdown": {
        "display_name": "Drawdown (R)",
        "short_desc": "Current peak-to-trough equity decline measured in multiples of initial risk.",
        "what_is_it": "The current decline from the highest previous account equity level.",
        "detailed_desc": "Tracks how far the current equity path has fallen from its peak in units of R-multiples.",
        "good_or_bad": "<= 4.0R is Normal; 4.0R-7.15R is Elevated; > 7.15R is Stress.",
        "why_it_matters": "Prevents premature strategy panic during mathematically normal historical drawdown streaks.",
        "what_to_watch": "Ensure current drawdown does not exceed the historical stress threshold of 7.15R.",
        "caveat": "Drawdowns are an inevitable mathematical reality of probabilistic trading systems."
    },
    "drawdown_status": {
        "display_name": "Forward Drawdown Status",
        "short_desc": "Evaluation of current forward drawdown against historical Monte Carlo stress distribution.",
        "what_is_it": "Classification of forward equity decline relative to historical stress baselines.",
        "detailed_desc": "Classifies current forward peak-to-trough decline as Normal (<= 4R), Elevated (4R-7.15R), Stress (7.15R-12R), or Severe (> 12R).",
        "good_or_bad": "NORMAL or ELEVATED is expected variance; STRESS requires execution audit; SEVERE triggers strategy review.",
        "why_it_matters": "Prevents premature strategy abandonment during mathematically normal historical drawdown streaks.",
        "what_to_watch": "Watch if losses are caused by normal market variance or execution friction.",
        "caveat": "Historical stress thresholds describe past behavior and do not guarantee future drawdown limits."
    },
    "mae": {
        "display_name": "Maximum Adverse Excursion (MAE)",
        "short_desc": "The deepest drawdown experienced by a trade before closing.",
        "what_is_it": "How far price moved against the position during its lifetime before hitting target or stop loss.",
        "detailed_desc": "Measures the peak unrealized loss during a trade. For XAUUSD, historical average MAE is 0.38R, indicating entries have very tight heat.",
        "good_or_bad": "Lower MAE indicates precision entry timing. Average MAE <= 0.45R is healthy for 1M FVG entries.",
        "why_it_matters": "Helps determine whether stop loss distances are appropriately placed or excessively wide.",
        "what_to_watch": "Watch for sudden increases in forward MAE which signal entry timing degradation.",
        "caveat": "High MAE combined with winning trades indicates the strategy is relying on wide stops to survive poor entries."
    },
    "mae_r": {
        "display_name": "Maximum Adverse Excursion (MAE)",
        "short_desc": "The deepest drawdown experienced by a trade before closing in units of R.",
        "what_is_it": "The deepest adverse price move against the entry price before trade resolution.",
        "detailed_desc": "Quantifies entry timing precision. Low MAE means price moves in the intended direction almost immediately after entry.",
        "good_or_bad": "<= 0.45R is Consistent; 0.45R-0.65R is Watch; > 0.65R is Drifting.",
        "why_it_matters": "Validates that the 1M FVG provides clean structural entry reaction.",
        "what_to_watch": "Compare forward MAE against historical baseline of 0.38R.",
        "caveat": "Sudden spread widening can artificially increase measured MAE."
    },
    "mfe": {
        "display_name": "Maximum Favorable Excursion (MFE)",
        "short_desc": "The peak unrealized profit reached by a trade before exit.",
        "what_is_it": "How far price moved in the profitable direction during the trade lifetime.",
        "detailed_desc": "Measures the maximum profit potential reached. Historical average MFE for XAUUSD is 2.85R.",
        "good_or_bad": "High MFE relative to average win indicates expansion potential. Average MFE >= 2.50R is healthy.",
        "why_it_matters": "Reveals whether profit targets are capturing the available market move or leaving excessive profit on the table.",
        "what_to_watch": "Look for trades reaching 2R/3R MFE that subsequently reverse to stop loss.",
        "caveat": "MFE deterioration indicates the market is offering less expansion range even if win rate stays temporarily stable."
    },
    "mfe_r": {
        "display_name": "Maximum Favorable Excursion (MFE)",
        "short_desc": "The peak unrealized profit reached by a trade in units of R.",
        "what_is_it": "Peak favorable price expansion before position exit.",
        "detailed_desc": "Tracks structural follow-through. For XAUUSD, baseline MFE is 2.85R.",
        "good_or_bad": ">= 2.50R is Consistent; 1.80R-2.50R is Watch; < 1.80R is Drifting.",
        "why_it_matters": "Confirms the 4H DOL is attracting price as expected.",
        "what_to_watch": "Check whether forward trades consistently reach the 2R break-even threshold.",
        "caveat": "MFE can drop during consolidation regimes without invalidating higher-timeframe structure."
    },
    "complexity_score": {
        "display_name": "Complexity-Adjusted Score",
        "short_desc": "Holdout expectancy penalized for each added parameter, filter, and timeframe rule.",
        "what_is_it": "A research score that penalizes strategies requiring excessive indicators, conditional filters, or complex rules.",
        "detailed_desc": "A research score that penalizes strategies requiring excessive indicators, conditional filters, or complex rules. Simpler strategies with fewer degrees of freedom are preferred when performance is similar.",
        "good_or_bad": ">= 0.40 is Strong; 0.20 to 0.40 is Good; < 0.00 is Poor.",
        "good_threshold": 0.20,
        "strong_threshold": 0.40,
        "bad_threshold": 0.00,
        "caveat": "Penalty deductions are heuristic and intended to prevent unnecessary parameter proliferation.",
        "why_it_matters": "Reduces the risk of curve-fitting by favoring parsimonious mechanical rules.",
        "what_to_watch": "Avoid adding arbitrary indicator filters that only marginally improve training results."
    },
    "risk_reward_ratio": {
        "display_name": "Reward-to-Risk Ratio (RR)",
        "short_desc": "Ratio of projected target profit to initial stop loss distance.",
        "what_is_it": "Compares planned reward distance to initial stop-loss risk distance.",
        "detailed_desc": "Compares potential reward to initial risk. For example, 3.0R means the distance from entry to take profit is three times the distance from entry to stop loss.",
        "good_or_bad": ">= 3.0 is Strong; 2.0 to 3.0 is Good; < 1.0 is Sub-optimal.",
        "good_threshold": 2.0,
        "strong_threshold": 3.0,
        "bad_threshold": 1.0,
        "caveat": "Higher theoretical RR targets reduce win rate unless backed by strong multi-timeframe directional order flow.",
        "why_it_matters": "Allows strategies to remain profitable even with win rates below 40%.",
        "what_to_watch": "Ensure planned RR matches the distance to the 4H Draw on Liquidity."
    },
    "holding_time_min": {
        "display_name": "Average Holding Time (min)",
        "short_desc": "Average trade duration in minutes from entry fill to exit resolution.",
        "what_is_it": "Average length of time a position remains open in the market.",
        "detailed_desc": "For XAUUSD True MTF, historical average holding time is 32 minutes, reflecting intraday precision execution.",
        "good_or_bad": "20 to 60 minutes is standard for 1M FVG executions.",
        "why_it_matters": "Indicates market exposure duration and overnight rollover risk.",
        "what_to_watch": "Monitor for trades dragging past session close into the illiquid rollover window.",
        "caveat": "Holding time lengthens during low-volatility holiday periods."
    },
    "missed_entry_rate": {
        "display_name": "Missed Entry Rate (%)",
        "short_desc": "Percentage of valid setups where price moved to target without filling the limit order.",
        "what_is_it": "How often a valid setup ran to target without filling the 1M limit order.",
        "detailed_desc": "Because the strategy uses 1M FVG limit orders, highly aggressive displacement moves can sometimes leave the limit unfilled (8.5% historical rate).",
        "good_or_bad": "<= 15% is Healthy; 15%-30% is Monitor; > 30% indicates execution degradation.",
        "why_it_matters": "Evaluates execution feasibility and trade opportunity capture.",
        "what_to_watch": "Log missed entries in FUTURE_RESEARCH_QUEUE without altering the frozen contract.",
        "caveat": "Missed entries protect capital from chasing extended moves."
    },
    "fvg": {
        "display_name": "Fair Value Gap (FVG)",
        "short_desc": "A 3-candle price imbalance where candle 1 wick and candle 3 wick do not overlap.",
        "what_is_it": "A price imbalance or liquidity void created by aggressive displacement in one direction.",
        "detailed_desc": "In ICT/SMC methodology, fair value gaps represent institutional imbalance where liquidity was offered inefficiently. The strategy uses 1M FVGs as precision limit entry zones.",
        "good_or_bad": "FVGs formed with strong displacement body candles provide higher probability reaction boundaries.",
        "why_it_matters": "Provides a non-discretionary geometric price level for limit order placement.",
        "what_to_watch": "Watch for FVG invalidation if price closes completely through the gap prior to entry.",
        "caveat": "Not all FVGs are filled; strong trends may leave FVGs unmitigated."
    },
    "mss": {
        "display_name": "Market Structure Shift (MSS)",
        "short_desc": "A confirmed candle close breaking the previous structural swing point with displacement.",
        "what_is_it": "A reversal signal where price breaks the prior swing high (bullish) or swing low (bearish).",
        "detailed_desc": "Requires a decisive body close on the 15M timeframe through the recent swing point following a liquidity sweep. Confirms institutional order flow transition.",
        "good_or_bad": "Full candle body closes beyond the swing indicate genuine displacement; wicks indicate potential false breaks.",
        "why_it_matters": "Prevents trading counter-trend before smart money has initiated structural change.",
        "what_to_watch": "Check that the MSS occurs within 3-5 candles of the 15M liquidity sweep.",
        "caveat": "High-impact news can create artificial MSS wicks that quickly fail."
    },
    "sweep": {
        "display_name": "Liquidity Sweep",
        "short_desc": "Price piercing a key session or structural high/low to trigger resting stop orders before reversing.",
        "what_is_it": "When price momentarily trades beyond prior highs/lows (e.g. Asian Range Low) to absorb liquidity.",
        "detailed_desc": "Institutional participants require large counter-party liquidity to fill orders. Sweeping retail stops resting above prior highs or below prior lows creates the necessary volume.",
        "good_or_bad": "Sweeps that immediately reject back inside the range indicate strong accumulation/distribution.",
        "why_it_matters": "Ensures the strategy enters after retail stops have been purged rather than before.",
        "what_to_watch": "Confirm that price sweeps Asian High/Low, Previous Day High (PDH), or Previous Day Low (PDL).",
        "caveat": "A strong trend may continue breaking highs/lows without reversing (true breakout vs sweep)."
    },
    "dol": {
        "display_name": "Draw on Liquidity (DOL)",
        "short_desc": "The higher-timeframe magnetic target where institutional order flow is expected to reach.",
        "what_is_it": "The 4H structural target (e.g. Previous Day High, Equal Highs, or 4H FVG) attracting price.",
        "detailed_desc": "Provides the overall profit target for the trade. The strategy requires that the 4H DOL offers at least 2.0R distance from the entry point.",
        "good_or_bad": "DOL distance >= 3.0R provides favorable reward-to-risk geometry.",
        "why_it_matters": "Gives the trade a clear structural exit objective rather than arbitrary fixed pip targets.",
        "what_to_watch": "Check that the 4H DOL has not already been mitigated prior to entry trigger.",
        "caveat": "If the DOL is closer than 2.0R, the trade is rejected by rule."
    },
    "displacement": {
        "display_name": "Displacement",
        "short_desc": "Aggressive, large-bodied candles indicating institutional volume entering the market.",
        "what_is_it": "Energetic price movement characterized by wide-range candles and fair value gaps.",
        "detailed_desc": "Displacement demonstrates that large institutions are actively moving price in a specific direction rather than passive retail chopping.",
        "good_or_bad": "High displacement body ratio (> 65% of candle range) confirms institutional conviction.",
        "why_it_matters": "Separates genuine structure shifts from low-volume consolidation drifts.",
        "what_to_watch": "Confirm displacement occurs during London Open or London/NY Overlap sessions.",
        "caveat": "Late-stage displacement can indicate climax exhaustion."
    },
    "atr": {
        "display_name": "Average True Range (ATR)",
        "short_desc": "Standard measure of market volatility over a specified lookback period.",
        "what_is_it": "The average price range covered by candles over the last 14 periods.",
        "detailed_desc": "Quantifies current volatility. Used by the execution engine to calibrate minimum stop loss distances and spread filter thresholds.",
        "good_or_bad": "Normal ATR allows clean 1M limit fills; extreme ATR can cause rapid slippage.",
        "why_it_matters": "Adapts risk calculations dynamically to current market expansion speed.",
        "what_to_watch": "Check for volatility spikes during economic news releases.",
        "caveat": "ATR does not indicate direction, only volatility magnitude."
    },
    "slippage": {
        "display_name": "Execution Slippage",
        "short_desc": "Difference between the requested order price and the actual fill price.",
        "what_is_it": "The price difference between where an order was requested and where it actually executed.",
        "detailed_desc": "Modeled at 1.0 pip for 1M limit orders. Higher slippage reduces realized R-multiples and degrades strategy expectancy.",
        "good_or_bad": "<= 1.0 pip is Optimal; 1.0-2.5 pips is Acceptable; > 3.0 pips is Severe Degradation.",
        "why_it_matters": "Directly impacts whether theoretical backtest gains survive in live broker execution.",
        "what_to_watch": "Monitor slippage on stop-loss executions during high-volatility sessions.",
        "caveat": "Market orders suffer much higher slippage than limit orders; this strategy uses limit orders."
    },
    "spread": {
        "display_name": "Bid/Ask Spread",
        "short_desc": "The difference between the broker's buying price and selling price.",
        "what_is_it": "The immediate transaction cost charged by the broker on every trade.",
        "detailed_desc": "For XAUUSD, typical institutional spread is 1.5 to 2.5 pips. Spread widens significantly during rollover (21:00-24:00 UTC) and major news.",
        "good_or_bad": "<= 2.5 pips is Normal; 2.5-4.5 pips is Elevated; > 4.5 pips is Blocked.",
        "why_it_matters": "High spread widens the effective stop loss and reduces realized profit.",
        "what_to_watch": "Ensure execution is blocked during rollover hours when spread spikes.",
        "caveat": "Gold spreads can widen to 10-20 pips during emergency market events."
    },
    "latency": {
        "display_name": "Execution Latency",
        "short_desc": "Time delay in milliseconds between signal generation and order acknowledgment.",
        "what_is_it": "The network and processing delay between identifying a setup and placing the order.",
        "detailed_desc": "Stress tested at 500ms in Phase 20 audit. Limit orders are placed in advance of price reaching the FVG boundary, mitigating latency sensitivity.",
        "good_or_bad": "< 100ms is Excellent; 100-300ms is Normal; > 500ms requires VPS infrastructure.",
        "why_it_matters": "High latency can cause missed limit order fills if price moves rapidly.",
        "what_to_watch": "Monitor WebSocket ping times to market data feeds.",
        "caveat": "Limit orders placed passively are less latency-sensitive than aggressive market orders."
    },
    "fill_rate": {
        "display_name": "Limit Order Fill Rate (%)",
        "short_desc": "Percentage of valid placed limit orders that were successfully filled.",
        "what_is_it": "How often the 1M FVG limit order was actually touched and executed by price.",
        "detailed_desc": "Measures the practical execution efficiency of the limit entry mechanism. If price takes off without retracing, the order expires unfilled.",
        "good_or_bad": ">= 75% is Healthy; 60%-75% is Moderate; < 60% indicates high missed-entry friction.",
        "why_it_matters": "Separates strategy setup quality from execution fill feasibility.",
        "what_to_watch": "If fill rate drops below 65%, review average retracement depth into the 1M FVG.",
        "caveat": "High fill rate on losing trades and low fill rate on winning trades indicates adverse selection."
    },
    "timeout_rate": {
        "display_name": "Order Timeout Rate (%)",
        "short_desc": "Percentage of limit orders that expired after 15 minutes without filling.",
        "what_is_it": "How often placed orders were canceled because price did not retrace within 15 minutes.",
        "detailed_desc": "The strategy enforces a strict 15-minute order lifetime to prevent entering stale setups after market structure has evolved.",
        "good_or_bad": "<= 20% is Optimal; 20%-35% is Normal; > 35% indicates Entry Execution Degradation.",
        "why_it_matters": "High timeout rate means the strategy misses valid moves due to rapid momentum.",
        "what_to_watch": "Log timeout events in FUTURE_RESEARCH_QUEUE without altering the frozen contract.",
        "caveat": "Timeout rate is an execution quality metric, not a strategy failure."
    },
    "missed_entry": {
        "display_name": "Missed Entry Rate (%)",
        "short_desc": "Percentage of valid setups where price moved to target without filling the limit order.",
        "what_is_it": "Setups that formed correctly but where price expanded directly toward the DOL without retracing to our limit price.",
        "detailed_desc": "Historical missed entry rate is 8.5%. In forward feeds, missed entries are tracked separately and never counted as strategy losses.",
        "good_or_bad": "<= 15% is Healthy; 15%-30% is Monitor; > 30% indicates execution degradation.",
        "why_it_matters": "Affects real-world capital turnover and trade opportunity capture.",
        "what_to_watch": "Check whether missed entries occur primarily during high-impact news releases.",
        "caveat": "Missed entries protect capital from chasing extended moves."
    },
    "edge_consistency_score": {
        "display_name": "Edge Consistency Score",
        "short_desc": "Transparent multi-component score (0-100) assessing forward agreement with the frozen contract.",
        "what_is_it": "A composite index evaluating whether forward trading matches the historical research contract.",
        "detailed_desc": "Combines Expectancy Direction (35 pts), Confidence Interval (20 pts), Win Rate Alignment (15 pts), Drawdown Health (15 pts), and Execution Quality (15 pts).",
        "good_or_bad": ">= 80 is Strong Alignment; 60-79 is Moderate Alignment; 40-59 is Marginal; < 40 is Divergent.",
        "why_it_matters": "Provides an inspectable composite index of forward strategy health.",
        "what_to_watch": "Inspect individual point deductions to identify specific areas of friction.",
        "caveat": "Score is capped by sample size adequacy rules."
    },
    "strategy_drift": {
        "display_name": "Strategy Distribution Drift",
        "short_desc": "Comparison of forward excursion profile (MAE/MFE) and holding time against historical baseline.",
        "what_is_it": "Statistical check to detect if forward trade distributions are diverging from historical patterns.",
        "detailed_desc": "Compares rolling MAE, MFE, win rate, and holding duration against the locked Phase 20 holdout baseline.",
        "good_or_bad": "DISTRIBUTIONALLY CONSISTENT (< 60% divergence); WATCH (60%-80%); DRIFTING (> 80%).",
        "why_it_matters": "Early warning indicator for market regime shifts or structural edge decay.",
        "what_to_watch": "Watch if favorable excursion (MFE) drops significantly below 2.50R.",
        "caveat": "Temporary drift can occur during summer liquidity lulls or holiday consolidation."
    },
    "drift_status": {
        "display_name": "Distribution Drift Status",
        "short_desc": "Comparison of forward excursion profile (MAE/MFE) and holding time against historical baseline.",
        "what_is_it": "Classification of forward distribution stability relative to historical baseline.",
        "detailed_desc": "Identifies whether forward trades exhibit similar adverse and favorable excursion distributions as the historical holdout.",
        "good_or_bad": "CONSISTENT is Healthy; WATCH indicates mild divergence; DRIFTING signals structural shift.",
        "why_it_matters": "Provides early detection of edge decay before severe drawdown occurs.",
        "what_to_watch": "Monitor 20-trade rolling MAE/MFE averages.",
        "caveat": "Requires at least N = 20 forward trades to establish statistical validity."
    },
    "regime": {
        "display_name": "Market Regime",
        "short_desc": "The prevailing macro trend, session timing, and volatility environment.",
        "what_is_it": "The broader market context in which trades occur (e.g. Bullish Trend during London/NY Overlap).",
        "detailed_desc": "The strategy tracks 1D macro bias, active trading session, volatility state, and weekday. Subgroups with N < 30 are protected against data mining.",
        "good_or_bad": "Highest historical edge occurs during London Open (07:00-11:00 UTC) and London/NY Overlap (12:00-16:00 UTC).",
        "why_it_matters": "Explains performance variations caused by changing market regime mixtures.",
        "what_to_watch": "Verify that forward trading is concentrated during peak volume sessions.",
        "caveat": "Do not disable or retune regimes based on small forward sub-samples (N < 30)."
    },
    "paper_execution": {
        "display_name": "Paper Execution Mode",
        "short_desc": "Live forward simulation with full order management and persistent database logging.",
        "what_is_it": "Simulated live execution where orders are tracked against live ticks and logged to the database.",
        "detailed_desc": "Processes live tick feeds, places simulated 1M limit orders, monitors fill/timeout events, and logs complete trade lifecycle records.",
        "good_or_bad": "Active and logging without execution errors.",
        "why_it_matters": "Validates the execution pipeline under real-time market data conditions without financial risk.",
        "what_to_watch": "Ensure Paper execution matches Shadow execution with 100% decision parity.",
        "caveat": "Paper simulation assumes broker fills at exact limit price."
    },
    "shadow_execution": {
        "display_name": "Shadow Execution Mode",
        "short_desc": "Decision-only execution stream evaluating signals without database positions.",
        "what_is_it": "A parallel verification pipeline that evaluates every setup decision independently from Paper mode.",
        "detailed_desc": "Runs alongside Paper mode to audit signal generation, risk approval, and rejection logic. Produces zero database positions.",
        "good_or_bad": "100% Parity with Paper mode is required.",
        "why_it_matters": "Proves that the trading logic is deterministic and free from state-dependent race conditions.",
        "what_to_watch": "Any discrepancy triggers a PARITY BREACH alert.",
        "caveat": "Shadow mode does not track simulated fills or exits."
    },
    "stage_1d": {
        "display_name": "1D Macro Bias",
        "short_desc": "Daily timeframe trend and institutional order flow direction.",
        "what_is_it": "Determines the broad directional environment (Bullish, Bearish, or Neutral).",
        "detailed_desc": "Uses daily candle structure and 20/50 EMA alignment to establish high-timeframe direction. If 1D bias is Bullish, the strategy only looks for long setups.",
        "good_or_bad": "Clear directional alignment provides strong market momentum.",
        "why_it_matters": "Trading in alignment with the daily macro bias eliminates low-probability counter-trend noise.",
        "what_to_watch": "Look for daily candle closes breaking major swing points.",
        "caveat": "Daily bias transitions can cause temporary chop during multi-week consolidation."
    },
    "stage_4h": {
        "display_name": "4H Draw on Liquidity (DOL)",
        "short_desc": "4H liquidity pools or structural zones acting as directional price magnets.",
        "what_is_it": "Identifies where price is likely attracted on the 4-hour chart (PDH, PDL, or 4H FVG).",
        "detailed_desc": "Determines the high-probability target for the trade. The strategy requires that the 4H DOL provides at least 2.0R distance from the planned entry.",
        "good_or_bad": "Clear unmitigated 4H liquidity pools offer clean directional magnetism.",
        "why_it_matters": "Ensures every trade has a structurally sound institutional exit target.",
        "what_to_watch": "Verify that the 4H DOL has not already been swept prior to entry setup formation.",
        "caveat": "If the DOL is closer than 2.0R, the trade is rejected by rule."
    },
    "stage_15m": {
        "display_name": "15M Liquidity & Structure",
        "short_desc": "15M liquidity sweep of key session levels followed by Market Structure Shift (MSS).",
        "what_is_it": "Waits for a key session level (e.g. Asian Range Low) to be swept followed by a 15M structure shift.",
        "detailed_desc": "Develops the actual setup through liquidity interaction and confirming structural displacement on closed 15M candles.",
        "good_or_bad": "Decisive 15M candle body close confirms institutional order flow transition.",
        "why_it_matters": "Ensures smart money accumulation/distribution has occurred before looking for entries.",
        "what_to_watch": "Watch for the 15M candle close to confirm the MSS before looking at lower timeframes.",
        "caveat": "Wicks without body closes do not constitute valid structure shifts."
    },
    "stage_5m": {
        "display_name": "5M Confirmation",
        "short_desc": "Optional 5M displacement confirmation within 3 bars of 15M structure shift.",
        "what_is_it": "Refines the structural move and confirms momentum before execution.",
        "detailed_desc": "Refinement layer used to confirm momentum and validate 5M fair value gap formation prior to placing execution orders.",
        "good_or_bad": "Strong 5M displacement confirms continuation toward the 4H DOL.",
        "why_it_matters": "Filters out false 15M wicks and low-momentum consolidation.",
        "what_to_watch": "Check that 5M momentum aligns with the 15M shift direction.",
        "caveat": "5M confirmation is optional in strong expansion regimes."
    },
    "stage_1m": {
        "display_name": "1M Precision Entry",
        "short_desc": "1M limit order entry placed at the boundary of a 1M Fair Value Gap.",
        "what_is_it": "Provides the tightest structural entry trigger and stop-loss placement.",
        "detailed_desc": "The strategy places a limit order at the 1M FVG boundary with stop loss at the structural swing point. Compresses average stop distance to 14.5 pips.",
        "good_or_bad": "Clean retracement into 1M FVG boundary with immediate expansion.",
        "why_it_matters": "Tightens initial risk, dramatically expands realized R-multiples, and avoids entry lag.",
        "what_to_watch": "Order expires after 15 minutes if not filled.",
        "caveat": "Fast expansion moves may leave the 1M FVG unfilled (missed entry)."
    },
    "validation_stage": {
        "display_name": "Validation Governance Gate",
        "short_desc": "Predefined stage-based evaluation: Stage 0 (Monitoring) to Stage 3 (Strong Forward Evidence).",
        "what_is_it": "Predefined quantitative roadmap governing forward strategy validation.",
        "detailed_desc": "Enforces strict sample size and statistical thresholds (Stage 0: N < 30 -> Stage 1: 30-49 -> Stage 2: 50-99 -> Stage 3: N >= 100).",
        "good_or_bad": "Stage 3 with CI lower bound > 0 confers Eligibility for Human Review.",
        "why_it_matters": "Prevents discretionary or emotional transitions to live trading.",
        "what_to_watch": "Track required criteria checklist for the current stage.",
        "caveat": "Reaching Stage 3 confers eligibility for human review only; live trading is never activated automatically."
    }
}


# ============================================================================
# 2. UNIVERSAL METRIC EXPLANATION COMPONENT
# ============================================================================

class MetricExplanation:
    """
    Universal reusable component that structures every metric into the 4 core questions:
    1. WHAT IS IT?
    2. IS THIS VALUE GOOD OR BAD?
    3. WHY DOES IT MATTER?
    4. WHAT SHOULD I DO / WATCH NEXT?
    """
    @staticmethod
    def explain(
        metric_id: str,
        current_value: Any,
        trades_n: Optional[int] = None,
        ci_low: Optional[float] = None,
        ci_high: Optional[float] = None,
        custom_classification: Optional[str] = None,
        custom_status_note: Optional[str] = None
    ) -> Dict[str, Any]:
        catalog_entry = METRIC_CATALOG.get(metric_id, {})
        display_name = catalog_entry.get("display_name", metric_id.replace("_", " ").title())
        what_is_it = catalog_entry.get("what_is_it", catalog_entry.get("detailed_desc", "Technical trading metric."))
        why_it_matters = catalog_entry.get("why_it_matters", "Provides objective performance telemetry.")
        what_to_watch = catalog_entry.get("what_to_watch", "Monitor forward sample progression.")
        caveat = catalog_entry.get("caveat", "Past performance does not guarantee future results.")
        good_or_bad_guide = catalog_entry.get("good_or_bad", "Evaluated against historical baselines.")

        # Determine Classification
        if custom_classification:
            classification = custom_classification
            status_note = custom_status_note or ""
        elif metric_id in ["expectancy", "expectancy_r", "forward_expectancy"]:
            val_float = float(current_value) if current_value is not None else 0.0
            n_val = trades_n if trades_n is not None else 0
            
            if n_val < 30:
                classification = "PROMISING VALUE — INSUFFICIENT DATA" if val_float > 0 else "INSUFFICIENT DATA"
                status_note = f"Current sample (N = {n_val}) is too small to draw statistically defensible conclusions."
            elif ci_low is not None and ci_high is not None and (ci_low <= 0.0 <= ci_high):
                classification = "POSITIVE BUT UNCERTAIN" if val_float > 0 else "UNCERTAIN"
                status_note = "Observed expectancy is positive, but the 95% confidence interval crosses zero."
            elif val_float >= 0.50:
                classification = "STRONG"
                status_note = "High realized expectancy with robust reward-to-risk dynamics."
            elif val_float >= 0.25:
                classification = "GOOD"
                status_note = "Solid realized expectancy exceeding standard friction thresholds."
            elif val_float >= 0.00:
                classification = "WEAK POSITIVE"
                status_note = "Positive but modest expectancy; vulnerable to spread widening."
            else:
                classification = "NEGATIVE"
                status_note = "Negative realized expectancy; average losses exceeded profits."
        elif metric_id in ["max_drawdown_r", "drawdown", "drawdown_status"]:
            val_float = float(current_value) if current_value is not None else 0.0
            if val_float <= 4.0:
                classification = "NORMAL"
                status_note = "Within historical median drawdown range (3.84R)."
            elif val_float <= 7.15:
                classification = "ELEVATED"
                status_note = "Within historical 95th-percentile Monte Carlo stress range (7.15R)."
            elif val_float <= 12.0:
                classification = "STRESS"
                status_note = "Exceeds historical 95th-percentile stress; heightened monitoring required."
            else:
                classification = "SEVERE"
                status_note = "Severe drawdown exceeding historical risk boundaries."
        elif metric_id in ["fill_rate", "limit_fill_rate"]:
            val_float = float(current_value) if current_value is not None else 100.0
            if val_float >= 75.0:
                classification = "HEALTHY"
                status_note = "Limit order execution is performing close to expected behavior."
            elif val_float >= 60.0:
                classification = "MODERATE"
                status_note = "Some missed limit orders due to fast price momentum."
            else:
                classification = "DEGRADED"
                status_note = "High proportion of limit orders timing out without fill."
        else:
            classification = "MONITORED"
            status_note = f"Current observed value: {current_value}"

        return {
            "metric_id": metric_id,
            "display_name": display_name,
            "current_value": current_value,
            "classification": classification,
            "status_note": status_note,
            "what_is_it": what_is_it,
            "good_or_bad": good_or_bad_guide,
            "why_it_matters": why_it_matters,
            "what_to_watch": what_to_watch,
            "caveat": caveat,
            "tooltip_text": f"{what_is_it}\n\nWhy it matters: {why_it_matters}\n\nCaveat: {caveat}"
        }



# ============================================================================
# 3. CONTEXT-AWARE VALUE CLASSIFICATION & INTERPRETATION ENGINE
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

    @staticmethod
    def explain_entry_rejection(reason_code: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Explains why a setup was rejected before execution:
        - WHAT FAILED
        - WHY IT FAILED
        - WHAT RULE CAUSED THE REJECTION
        """
        details = details or {}
        rejection_catalog = {
            "NO_DAILY_BIAS": {
                "what_failed": "1D Macro Trend Alignment",
                "why_it_failed": "Daily candle structure or 20/50 EMA slope is neutral or conflicting with intraday direction.",
                "rule_triggered": "Rule 1.1: Strategy requires unambiguous Daily directional alignment before considering setups."
            },
            "NO_VALID_4H_DOL": {
                "what_failed": "4H Draw on Liquidity Identification",
                "why_it_failed": "No unmitigated Previous Day High/Low, equal highs/lows, or 4H FVG available within session range.",
                "rule_triggered": "Rule 2.1: Strategy requires a clear 4H liquidity target acting as directional magnetism."
            },
            "DOL_BELOW_2R": {
                "what_failed": "Minimum Reward-to-Risk Distance",
                "why_it_failed": f"Distance to 4H DOL provides only {details.get('rr_available', 1.6):.1f}R reward potential.",
                "rule_triggered": "Rule 2.2: Minimum required distance to 4H Draw on Liquidity is 2.0R. Setups below 2.0R are rejected."
            },
            "NO_LIQUIDITY_SWEEP": {
                "what_failed": "15M Session Liquidity Sweep",
                "why_it_failed": "Price did not pierce Asian Range High/Low or Previous Day High/Low before attempting reversal.",
                "rule_triggered": "Rule 3.1: Strategy requires liquidity purge of key session levels before looking for structure shift."
            },
            "MSS_NOT_CONFIRMED": {
                "what_failed": "15M Market Structure Shift (MSS)",
                "why_it_failed": "15M candle wicked through swing point without confirming a full candle body close beyond structure.",
                "rule_triggered": "Rule 3.2: MSS requires a closed 15M candle body beyond the recent swing point."
            },
            "DISPLACEMENT_TOO_WEAK": {
                "what_failed": "Institutional Displacement Magnitude",
                "why_it_failed": "Body candle ratio is below 65% of candle range or ATR expansion is insufficient.",
                "rule_triggered": "Rule 3.3: Structural break must be backed by aggressive institutional volume displacement."
            },
            "FVG_TOO_SMALL": {
                "what_failed": "15M/1M Fair Value Gap Imbalance Size",
                "why_it_failed": "Fair value gap height is below minimum structural threshold (3.0 pips).",
                "rule_triggered": "Rule 4.1: Fair value gaps must represent meaningful institutional order flow inefficiency."
            },
            "CONFIRMATION_5M_MISSING": {
                "what_failed": "5M Momentum Confirmation",
                "why_it_failed": "5M timeframe did not print a confirming displacement bar within 3 candles of 15M MSS.",
                "rule_triggered": "Rule 4.2: 5M momentum confirmation failed to validate the structural shift."
            },
            "NO_1M_FVG_FOUND": {
                "what_failed": "1M Precision FVG Formation",
                "why_it_failed": "Price expanded without creating a valid 1M Fair Value Gap for limit order placement.",
                "rule_triggered": "Rule 5.1: Limit entry must be placed at the precise boundary of a 1M Fair Value Gap."
            },
            "LIMIT_ORDER_EXPIRED": {
                "what_failed": "1M Limit Order Execution Window",
                "why_it_failed": "Price did not retrace to fill the limit order within the 15-minute expiration lifetime.",
                "rule_triggered": "Rule 5.2: Limit orders expire after 15 minutes to avoid entering stale or invalidated setups."
            },
            "SWING_INVALIDATED": {
                "what_failed": "Structural Swing Point Invalidation",
                "why_it_failed": "Price broke the structural stop-loss anchor before retracing to the limit entry price.",
                "rule_triggered": "Rule 6.1: Setup is canceled immediately if the structural swing invalidation level is breached."
            },
            "RISK_GATE_REJECTED": {
                "what_failed": "Central Risk Gateway Validation",
                "why_it_failed": f"Risk check failed: {details.get('risk_reason', 'Account risk threshold or correlation limit exceeded')}.",
                "rule_triggered": "Rule 7.1: Pre-trade risk approval is mandatory before any Paper/Shadow order is created."
            }
        }
        entry = rejection_catalog.get(reason_code, {
            "what_failed": "Pre-Trade Setup Rule",
            "why_it_failed": details.get("message", "Setup did not satisfy all mechanical requirements."),
            "rule_triggered": "Rule Specification: Strategy requires all MTF criteria to pass."
        })
        return {
            "reason_code": reason_code,
            "what_failed": entry["what_failed"],
            "why_it_failed": entry["why_it_failed"],
            "rule_triggered": entry["rule_triggered"],
            "status": "REJECTED (PRE-TRADE FILTER)",
            "summary_text": f"REJECTED — {entry['what_failed']}: {entry['why_it_failed']} ({entry['rule_triggered']})"
        }

    @staticmethod
    def explain_trade_entry(trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Explains why a Paper/Shadow trade was approved and entered across all MTF layers.
        """
        symbol = trade.get("symbol", "XAUUSD")
        side = trade.get("side", "BUY")
        direction_text = "LONG" if side.upper() in ["BUY", "LONG"] else "SHORT"
        
        return {
            "title": f"WHY DID WE ENTER? — {direction_text} {symbol}",
            "direction": direction_text,
            "symbol": symbol,
            "layer_1d": f"1D Macro Bias: {trade.get('bias_1d', 'Bullish Daily Alignment (Price above 20/50 EMAs)')}",
            "layer_4h": f"4H Target (DOL): {trade.get('dol_4h', 'PDH / 4H FVG target providing > 2.5R potential')}",
            "layer_15m": f"15M Structure: {trade.get('setup_15m', 'Asian Low Swept + Confirmed Bullish MSS Body Close')}",
            "layer_5m": f"5M Confirmation: {trade.get('conf_5m', 'Confirmed 5M FVG displacement momentum')}",
            "layer_1m": f"1M Precision Entry: {trade.get('entry_1m', 'Limit order filled at 1M FVG boundary')}",
            "risk_spec": f"Risk Allocation: SL = {trade.get('sl_pips', 14.5):.1f} pips | Target = {trade.get('target_r', 3.0):.1f}R",
            "decision": "PAPER ORDER APPROVED & EXECUTED"
        }

    @staticmethod
    def explain_mtf_stage(stage_id: str, current_state: str, details: Optional[str] = None) -> Dict[str, Any]:
        """
        Provides intuitive MTF stage card data answering purpose, state, and human meaning.
        """
        stage_info = {
            "1D": {
                "name": "1D — MACRO BIAS",
                "purpose": "Determines the broad directional environment and filters counter-trend noise.",
                "meaning_pass": "Daily candle structure and EMA alignment support long setups.",
                "meaning_fail": "Daily structure is conflicting or in consolidation chop."
            },
            "4H": {
                "name": "4H — DRAW ON LIQUIDITY",
                "purpose": "Determines where institutional price is attracted and provides target magnetism.",
                "meaning_pass": "Clear unmitigated target (PDH/PDL/FVG) offers >= 2.0R distance.",
                "meaning_fail": "Target distance is too close (< 2.0R) or already mitigated."
            },
            "15M": {
                "name": "15M — SETUP (SWEEP + MSS)",
                "purpose": "Waits for session liquidity purge followed by structural displacement.",
                "meaning_pass": "Liquidity swept and confirmed MSS body close achieved.",
                "meaning_fail": "Waiting for liquidity sweep or displacement candle close."
            },
            "5M": {
                "name": "5M — CONFIRMATION",
                "purpose": "Refines the structural move and confirms momentum before execution.",
                "meaning_pass": "5M fair value gap confirmed displacement continuation.",
                "meaning_fail": "Waiting for 5M candle displacement validation."
            },
            "1M": {
                "name": "1M — PRECISION ENTRY",
                "purpose": "Provides the tightest structural limit entry and stop loss.",
                "meaning_pass": "1M FVG limit order placed with 14.5 pip average stop loss.",
                "meaning_fail": "No valid 1M FVG formed or order timed out after 15 minutes."
            }
        }
        info = stage_info.get(stage_id, {
            "name": f"{stage_id} — TIMEFRAME",
            "purpose": "Timeframe filter layer.",
            "meaning_pass": "Criteria passed.",
            "meaning_fail": "Criteria waiting."
        })
        is_pass = current_state.upper() in ["PASS", "ACTIVE", "CONFIRMED", "BULLISH", "BEARISH"]
        return {
            "stage_id": stage_id,
            "name": info["name"],
            "purpose": info["purpose"],
            "current_state": current_state,
            "status": "PASS" if is_pass else ("WAITING" if "WAIT" in current_state.upper() else "BLOCKED"),
            "meaning": details or (info["meaning_pass"] if is_pass else info["meaning_fail"])
        }

    @staticmethod
    def explain_risk_concepts() -> Dict[str, Any]:
        """
        Returns plain-language explanations of core risk parameters.
        """
        return {
            "risk_per_trade": {
                "title": "Risk Per Trade (1.0%)",
                "meaning": "A full stop loss execution loses approximately 1.0% of account equity, preserving 99% of capital.",
                "why_important": "Ensures that even a statistically severe losing streak of 10 trades only draws down ~9.6% of equity."
            },
            "r_multiple": {
                "title": "R-Multiple (+3.0R Target)",
                "meaning": "A +3R winning trade earns three times the initial dollar amount risked on the trade.",
                "why_important": "Allows the strategy to remain strongly profitable with a 45%-55% win rate."
            },
            "min_2r_rule": {
                "title": "Why a 2R Minimum Exists",
                "meaning": "The strategy rejects any setup where the 4H Draw on Liquidity is closer than 2.0R.",
                "why_important": "Entering trades with low reward potential degrades the long-term expectancy curve."
            },
            "structural_sl": {
                "title": "Why Structural SL Is Used",
                "meaning": "Stop loss is placed at the actual structural swing point that would prove the setup thesis wrong.",
                "why_important": "Arbitrary fixed pip stops get wicked out by normal market noise; structural stops respect institutional order flow."
            },
            "tight_sl_danger": {
                "title": "Why Extremely Tight SLs Are Dangerous",
                "meaning": "Stop losses under 5 pips on Gold frequently fail due to normal bid/ask spread expansion and noise.",
                "why_important": "The strategy enforces a minimum 5.0 pip stop floor to maintain execution robustness."
            }
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
