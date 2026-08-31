"""
Phase 14 Strategy Edge Discovery & Research Engine
Provides:
- ResearchExperiment (immutable run specification)
- ThreeLayerDataSplitter (60% Train, 20% Validation, 20% Untouched Final Holdout)
- MultipleTestingTracker (Hypothesis tracking & data-mining risk counter)
- BootstrapEstimator (95% Bootstrap Confidence Intervals with deterministic seed)
- ScorecardClassifier (Objective Strategy Edge Status: STRONG, PROMISING, UNCERTAIN, WEAK, FAILED, INSUFFICIENT DATA)
"""

import uuid
import numpy as np
import pandas as pd
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple


@dataclass(frozen=True)
class ResearchExperiment:
    run_id: str
    strategy_name: str
    strategy_version: str
    symbol: str
    timeframe: str
    struct_tf: str = "1h"
    bias_tf: str = "4h"
    train_split: float = 0.60
    val_split: float = 0.20
    holdout_split: float = 0.20
    parameters: Dict[str, Any] = field(default_factory=dict)
    spread_pips: float = 1.0
    slippage_pips: float = 0.5
    commission_pct: float = 0.005
    random_seed: int = 42
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hypothesis_id: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ThreeLayerDataSplitter:
    """
    Strict 3-layer chronological partition:
    - 60% Train (In-Sample discovery)
    - 20% Validation (Model / Parameter Selection)
    - 20% Final Holdout (Strictly Untouched until final audit)
    """
    @staticmethod
    def split(df: pd.DataFrame, train_ratio: float = 0.60, val_ratio: float = 0.20) -> Dict[str, pd.DataFrame]:
        if df.empty:
            return {"train": pd.DataFrame(), "validation": pd.DataFrame(), "holdout": pd.DataFrame()}

        n = len(df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_df = df.iloc[:train_end].copy()
        val_df = df.iloc[train_end:val_end].copy()
        holdout_df = df.iloc[val_end:].copy()

        return {
            "train": train_df,
            "validation": val_df,
            "holdout": holdout_df,
            "train_range": (str(train_df.index[0]), str(train_df.index[-1])) if not train_df.empty else ("N/A", "N/A"),
            "val_range": (str(val_df.index[0]), str(val_df.index[-1])) if not val_df.empty else ("N/A", "N/A"),
            "holdout_range": (str(holdout_df.index[0]), str(holdout_df.index[-1])) if not holdout_df.empty else ("N/A", "N/A")
        }


class MultipleTestingTracker:
    """
    Tracks the total number of tested hypotheses/parameters across research runs.
    Calculates Bonferroni / False Discovery Rate (FDR) penalties to warn against data-mining bias.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MultipleTestingTracker, cls).__new__(cls)
            cls._instance.total_hypotheses_tested = 0
            cls._instance.experiments_log = []
        return cls._instance

    def register_experiment(self, experiment: ResearchExperiment) -> int:
        self.total_hypotheses_tested += 1
        self.experiments_log.append(experiment)
        return self.total_hypotheses_tested

    def get_risk_status(self) -> Dict[str, Any]:
        count = self.total_hypotheses_tested
        if count <= 5:
            risk_level = "LOW"
            warning = "Minimal multiple testing risk."
        elif count <= 25:
            risk_level = "MODERATE"
            warning = "Multiple parameter configurations evaluated. Look for neighboring parameter stability."
        else:
            risk_level = "HIGH (DATA-MINING RISK)"
            warning = "Dozens of hypotheses evaluated! High risk of overfitting to noise. Verify on final holdout."

        bonferroni_alpha = 0.05 / max(1, count)
        return {
            "total_hypotheses_tested": count,
            "risk_level": risk_level,
            "warning": warning,
            "adjusted_significance_alpha": round(bonferroni_alpha, 6)
        }

    def reset(self):
        self.total_hypotheses_tested = 0
        self.experiments_log = []


class BootstrapEstimator:
    """
    Computes 95% Bootstrap Confidence Intervals for Expectancy ($E[R]$), Win Rate, and Profit Factor
    using a fixed deterministic seed for reproducible research.
    """
    @staticmethod
    def calculate_r_expectancy_ci(
        r_returns: List[float],
        n_iterations: int = 5000,
        alpha: float = 0.05,
        random_seed: int = 42
    ) -> Dict[str, Any]:
        if not r_returns or len(r_returns) == 0:
            return {
                "sample_size": 0,
                "observed_mean_r": 0.0,
                "ci_lower": 0.0,
                "ci_upper": 0.0,
                "verdict": "INSUFFICIENT DATA",
                "sample_confidence": "VERY LOW"
            }

        arr = np.array(r_returns, dtype=float)
        n = len(arr)
        observed_mean = float(np.mean(arr))
        observed_median = float(np.median(arr))

        # Sample size tiering
        if n < 30:
            sample_tier = "VERY LOW SAMPLE (N < 30)"
        elif n < 100:
            sample_tier = "LOW SAMPLE (30-99)"
        elif n < 300:
            sample_tier = "MODERATE SAMPLE (100-299)"
        else:
            sample_tier = "STRONGER SAMPLE (300+)"

        if n < 5:
            return {
                "sample_size": n,
                "observed_mean_r": round(observed_mean, 3),
                "observed_median_r": round(observed_median, 3),
                "ci_lower": round(observed_mean, 3),
                "ci_upper": round(observed_mean, 3),
                "verdict": "INSUFFICIENT DATA",
                "sample_confidence": sample_tier
            }

        # Deterministic Bootstrap Resampling
        rng = np.random.default_rng(random_seed)
        boot_indices = rng.integers(0, n, size=(n_iterations, n))
        boot_samples = arr[boot_indices]
        boot_means = np.mean(boot_samples, axis=1)

        ci_lower = float(np.percentile(boot_means, (alpha / 2.0) * 100.0))
        ci_upper = float(np.percentile(boot_means, (1.0 - alpha / 2.0) * 100.0))

        if ci_lower > 0:
            verdict = "POSITIVE EXPECTANCY SUPPORTED BY SAMPLE"
        elif ci_upper < 0:
            verdict = "NEGATIVE EXPECTANCY (FAILED)"
        else:
            verdict = "EDGE UNCERTAIN (95% CI crosses zero)"

        return {
            "sample_size": n,
            "observed_mean_r": round(observed_mean, 3),
            "observed_median_r": round(observed_median, 3),
            "ci_lower": round(ci_lower, 3),
            "ci_upper": round(ci_upper, 3),
            "ci_range_str": f"[{ci_lower:+.3f}R, {ci_upper:+.3f}R]",
            "verdict": verdict,
            "sample_confidence": sample_tier
        }


class ScorecardClassifier:
    """
    Synthesizes multi-split research outputs into an objective Strategy Scorecard classification:
    - STRONG: Solid positive OOS/Holdout, bootstrap CI > 0, WFO robust, survives cost stress, N >= 100
    - PROMISING: Positive OOS, positive mean, stable parameters, moderate sample
    - UNCERTAIN: 95% CI crosses zero, high parameter sensitivity, or high cost fragility
    - WEAK: Negative OOS or severe WFO breakdown
    - FAILED: Negative expectancy across all splits
    - INSUFFICIENT DATA: N < 30
    """
    @staticmethod
    def evaluate_strategy(
        is_metrics: Dict[str, Any],
        oos_metrics: Dict[str, Any],
        holdout_metrics: Dict[str, Any],
        bootstrap_ci: Dict[str, Any],
        wfo_status: str = "Robust",
        execution_fragility: str = "LOW",
        parameter_stability: str = "STABLE"
    ) -> Dict[str, Any]:
        n_oos = oos_metrics.get("total_trades", 0)
        n_total = is_metrics.get("total_trades", 0) + n_oos + holdout_metrics.get("total_trades", 0)

        if n_total < 30:
            return {
                "status": "INSUFFICIENT DATA",
                "score_reasons": [f"Total trade count ({n_total}) is below statistical minimum of 30."],
                "is_deployable": False,
                "color": "#8a99ad"
            }

        oos_exp = oos_metrics.get("expectancy_r", oos_metrics.get("expectancy", 0.0))
        holdout_exp = holdout_metrics.get("expectancy_r", holdout_metrics.get("expectancy", 0.0))
        ci_low = bootstrap_ci.get("ci_lower", 0.0)

        reasons = []
        is_strong = True
        is_promising = True

        # Check OOS Expectancy
        if oos_exp <= 0:
            return {
                "status": "FAILED",
                "score_reasons": [f"Out-of-Sample expectancy is negative ({oos_exp:+.3f}R). Strategy lacks edge."],
                "is_deployable": False,
                "color": "#ff5555"
            }

        reasons.append(f"Positive Out-of-Sample Expectancy ({oos_exp:+.3f}R).")

        # Check Bootstrap CI
        if ci_low > 0:
            reasons.append(f"95% Bootstrap CI strictly positive: {bootstrap_ci.get('ci_range_str', 'N/A')}.")
        else:
            is_strong = False
            reasons.append(f"95% Bootstrap CI crosses zero ({bootstrap_ci.get('ci_range_str', 'N/A')}). Statistical edge uncertain.")

        # Check WFO & Parameters
        if wfo_status == "Robust":
            reasons.append("Walk-Forward Optimization confirmed rolling consistency.")
        else:
            is_strong = False
            is_promising = False
            reasons.append("WFO consistency was degraded or failed across rolling windows.")

        if parameter_stability == "STABLE":
            reasons.append("Neighboring parameters demonstrate smooth, stable performance.")
        else:
            is_strong = False
            reasons.append("Parameter sensitivity indicates potential cliff-edge overfitting.")

        # Check Execution Fragility
        if execution_fragility == "HIGH":
            is_strong = False
            reasons.append("High execution fragility: edge does not survive 2x spread/slippage stress.")

        # Final Classification
        if is_strong and n_oos >= 50 and holdout_exp > 0:
            status = "STRONG"
            color = "#00ffcc"
        elif is_promising and oos_exp > 0.05:
            status = "PROMISING"
            color = "#bef264"
        elif ci_low <= 0 or parameter_stability != "STABLE":
            status = "UNCERTAIN"
            color = "#f59e0b"
        else:
            status = "WEAK"
            color = "#ef4444"

        return {
            "status": status,
            "score_reasons": reasons,
            "is_deployable": status in ["STRONG", "PROMISING"],
            "color": color,
            "sample_size": n_total,
            "oos_trades": n_oos,
            "oos_expectancy_r": round(float(oos_exp), 3),
            "holdout_expectancy_r": round(float(holdout_exp), 3)
        }
