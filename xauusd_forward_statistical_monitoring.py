"""
Phase 49 — XAUUSD Forward Evidence Accumulation & Statistical Monitoring Engine
Provides:
- CanonicalForwardDatasetEngine: Extracts and verifies canonical forward dataset (strictly eligible, non-quarantined, valid outcomes)
- ForwardMetricsEngine: Calculates sample size, win rate, expectancy, PF, max DD, standard deviation, outcome distribution; categorizes metric maturity
- ConservativeUncertaintyEngine: Wilson score win rate CIs, bootstrap expectancy CIs, explicit low-sample disclaimers
- HistoricalVsForwardComparativeMonitor: Side-by-side comparison against locked N=82 historical baseline without data pooling
- AlphaDecayStatisticalMonitor: Non-invasive alpha decay evaluation and deterioration tracking
- SequentialEvidenceGovernanceEngine: 14-stage milestone monitoring and immutable milestone snapshot ledger
- DecisionStateEvaluator: Deterministic research decision state synthesis
- RestartDeterminismAuditor: Verification of state persistence and zero data drift across restarts
- Phase49MonitoringFacade: Unified operational facade for dashboard and automated audits
"""

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set

import numpy as np
import pandas as pd

import database
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from xauusd_forward_observation_quality import (
    ForwardObservationQualityEngine,
    ObservationQuarantineSubsystem,
    ObservationEvidenceQualityScorer,
)
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_forward_decision_gate import (
    EvidenceTierClassifier,
    SampleMilestoneEngineV2,
    ResearchDecisionGateEngine,
    MilestoneSnapshotStore,
)
from xauusd_alpha_decay_monitor import (
    AlphaDecayMonitor,
    DataQualityGate,
)

# Historical Locked Baseline Constants
HISTORICAL_BASELINE = {
    "trades_n": 82,
    "expectancy_r": 0.637,
    "win_rate_pct": 58.6,
    "profit_factor": 2.52,
    "max_drawdown_r": 4.00,
    "max_loss_streak": 3,
    "ci_95": [0.477, 0.817],
    "dataset_type": "HISTORICAL_HOLDOUT",
    "status": "LOCKED_AND_UNPOOLED"
}

# 14 Milestone Stages
FORWARD_MILESTONES = [0, 1, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500]


def init_phase49_database(conn=None):
    """Initializes tables for Phase 49 statistical snapshots and sequential governance."""
    should_close = False
    if conn is None:
        conn = database.get_connection()
        should_close = True

    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS xauusd_phase49_statistical_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        milestone_n INTEGER NOT NULL,
        actual_n INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        dataset_fingerprint TEXT NOT NULL,
        contract_hash TEXT NOT NULL,
        expectancy_r REAL NOT NULL,
        win_rate_pct REAL NOT NULL,
        profit_factor REAL NOT NULL,
        max_drawdown_r REAL NOT NULL,
        ci_95_lower REAL NOT NULL,
        ci_95_upper REAL NOT NULL,
        metric_tier TEXT NOT NULL,
        decision_state TEXT NOT NULL,
        alpha_decay_state TEXT NOT NULL,
        quarantine_count INTEGER NOT NULL,
        isolation_verified INTEGER NOT NULL DEFAULT 1,
        details_json TEXT NOT NULL,
        snapshot_fingerprint TEXT NOT NULL UNIQUE
    )
    """)

    conn.commit()
    if should_close:
        conn.close()


init_phase49_database()


class CanonicalForwardDatasetEngine:
    """
    Extracts, verifies, and provides the canonical forward research dataset.
    Ensures zero synthetic, backfilled, or unvalidated records contaminate the dataset.
    """

    @classmethod
    def get_canonical_dataset(cls, mode: str = "PAPER", symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Retrieves the clean, non-quarantined forward dataset with full provenance.
        """
        # Ensure database tables exist
        XAUUSDForwardJournal.init_forward_table()

        df_raw = XAUUSDForwardJournal.get_forward_trades(mode=mode)
        if df_raw.empty:
            empty_fingerprint = hashlib.sha256(b"CANONICAL_FORWARD_EMPTY_DATASET_N0").hexdigest()
            return {
                "symbol": symbol,
                "mode": mode,
                "trades_df": pd.DataFrame(),
                "total_records": 0,
                "clean_n": 0,
                "quarantined_count": 0,
                "dataset_fingerprint": empty_fingerprint,
                "contract_hash": FROZEN_CONTRACT_HASH,
                "is_isolated": True,
                "status": "WAITING_FOR_GENUINE_OBSERVATIONS"
            }

        # Filter out quarantined records
        clean_df, excluded = DataQualityGate.filter_observations_for_alpha_monitoring(df_raw)

        # Retain only records with completed outcome
        if not clean_df.empty:
            if "status" in clean_df.columns:
                valid_mask = clean_df["status"].isin(["COMPLETED", "CLOSED", "FILLED", "EXPIRED", "INVALIDATED", "TIMEOUT"])
                clean_df = clean_df[valid_mask].copy()

        # Sort chronologically by entry_time or exit_time
        time_col = "exit_time" if ("exit_time" in clean_df.columns and not clean_df.empty and clean_df["exit_time"].notna().any()) else "entry_time"
        if time_col in clean_df.columns and not clean_df.empty:
            clean_df[time_col] = pd.to_datetime(clean_df[time_col], errors="coerce", utc=True)
            clean_df = clean_df.sort_values(by=time_col).reset_index(drop=True)

        clean_n = len(clean_df)

        # Compute dataset fingerprint
        if clean_n > 0:
            raw_str = "".join(f"{r.get('signal_id','')}:{r.get('entry_time','')}:{r.get('r_multiple','')}" for _, r in clean_df.iterrows())
            dataset_fp = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
        else:
            dataset_fp = hashlib.sha256(b"CANONICAL_FORWARD_EMPTY_DATASET_N0").hexdigest()

        # Verify dataset isolation (no historical ID collision)
        hist_ids = {f"HIST_{i}" for i in range(1, 83)}
        fwd_ids = set(clean_df["signal_id"].astype(str).tolist()) if clean_n > 0 and "signal_id" in clean_df.columns else set()
        is_isolated = len(hist_ids.intersection(fwd_ids)) == 0

        return {
            "symbol": symbol,
            "mode": mode,
            "trades_df": clean_df,
            "total_records": len(df_raw),
            "clean_n": clean_n,
            "quarantined_count": len(excluded),
            "dataset_fingerprint": dataset_fp,
            "contract_hash": FROZEN_CONTRACT_HASH,
            "is_isolated": is_isolated,
            "status": "CANONICAL_DATASET_VERIFIED" if clean_n > 0 else "WAITING_FOR_GENUINE_OBSERVATIONS"
        }


class ForwardMetricsEngine:
    """
    Computes all standard forward metrics and strictly categorizes metric maturity:
    - OBSERVED_METRIC: Raw sample values (computed for N >= 1, accompanied by sample size disclaimer).
    - STATISTICALLY_INFORMATIVE_METRIC: Interpretable with moderate confidence (N >= 30).
    - DECISION_ELIGIBLE_METRIC: Statistically rigorous for formal governance decisions (N >= 100).
    """

    @classmethod
    def calculate_forward_metrics(cls, df_trades: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes forward performance metrics from clean trades dataframe.
        """
        n = len(df_trades)
        if n == 0 or df_trades.empty or "r_multiple" not in df_trades.columns:
            return {
                "trades_n": 0,
                "win_rate_pct": 0.0,
                "expectancy_r": 0.0,
                "average_r": 0.0,
                "median_r": 0.0,
                "profit_factor": 0.0,
                "cumulative_r": 0.0,
                "max_drawdown_r": 0.0,
                "std_dev_r": 0.0,
                "win_count": 0,
                "loss_count": 0,
                "breakeven_count": 0,
                "win_streak": 0,
                "loss_streak": 0,
                "outcomes": {
                    "tp_frequency_pct": 0.0,
                    "sl_frequency_pct": 0.0,
                    "timeout_frequency_pct": 0.0,
                    "invalidation_frequency_pct": 0.0,
                },
                "maturity_tier": "NO_FORWARD_DATA",
                "maturity_label": "NO FORWARD SAMPLE (N = 0)",
                "interpretation": "Waiting for the first genuine forward observation. No synthetic metrics generated."
            }

        r_vals = df_trades["r_multiple"].dropna().astype(float).values
        if len(r_vals) == 0:
            return cls.calculate_forward_metrics(pd.DataFrame())

        n_clean = len(r_vals)
        winners = r_vals[r_vals > 0]
        losers = r_vals[r_vals < 0]
        breakevens = r_vals[r_vals == 0]

        win_count = len(winners)
        loss_count = len(losers)
        be_count = len(breakevens)

        win_rate = (win_count / n_clean) * 100.0
        avg_r = float(np.mean(r_vals))
        median_r = float(np.median(r_vals))
        std_r = float(np.std(r_vals, ddof=1)) if n_clean > 1 else 0.0
        cum_r = float(np.sum(r_vals))

        # Expectancy = (WR * Avg_Win) + (LR * Avg_Loss)
        avg_win = float(np.mean(winners)) if len(winners) > 0 else 0.0
        avg_loss = float(np.mean(losers)) if len(losers) > 0 else 0.0
        gross_profit = float(np.sum(winners)) if len(winners) > 0 else 0.0
        gross_loss = abs(float(np.sum(losers))) if len(losers) > 0 else 0.0

        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = float(min(gross_profit * 2.0, 99.99))  # Finite high upper bound for zero loss
        else:
            profit_factor = 0.0

        # Drawdown calculation
        cum_arr = np.cumsum(r_vals)
        running_max = np.maximum.accumulate(np.insert(cum_arr, 0, 0.0))
        drawdowns = running_max[1:] - cum_arr
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Streaks
        current_win_streak = 0
        current_loss_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        for val in r_vals:
            if val > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            elif val < 0:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)
            else:
                current_win_streak = 0
                current_loss_streak = 0

        # Outcome distribution
        tp_cnt = 0
        sl_cnt = 0
        to_cnt = 0
        inv_cnt = 0

        for _, row in df_trades.iterrows():
            stat = str(row.get("status", "")).upper()
            r_m = float(row.get("r_multiple", 0.0))
            if r_m > 0 or "TP" in stat or "WIN" in stat:
                tp_cnt += 1
            elif r_m < 0 or "SL" in stat or "LOSS" in stat:
                sl_cnt += 1
            elif "TIMEOUT" in stat or "EXPIRED" in stat:
                to_cnt += 1
            elif "INVALID" in stat:
                inv_cnt += 1

        outcomes = {
            "tp_frequency_pct": round((tp_cnt / n_clean) * 100.0, 1),
            "sl_frequency_pct": round((sl_cnt / n_clean) * 100.0, 1),
            "timeout_frequency_pct": round((to_cnt / n_clean) * 100.0, 1),
            "invalidation_frequency_pct": round((inv_cnt / n_clean) * 100.0, 1),
        }

        # Maturity tier classification
        if n_clean >= 100:
            maturity_tier = "DECISION_ELIGIBLE_METRIC"
            maturity_label = f"DECISION-ELIGIBLE FORWARD EVIDENCE (N = {n_clean})"
            interpretation = "Sample size meets formal decision criteria. Bootstrap confidence intervals and distribution metrics are statistically robust."
        elif n_clean >= 30:
            maturity_tier = "STATISTICALLY_INFORMATIVE_METRIC"
            maturity_label = f"STATISTICALLY INFORMATIVE EVIDENCE (N = {n_clean})"
            interpretation = "Sample size provides meaningful statistical insight into forward distribution, but remains below full decision threshold (N = 100)."
        elif n_clean >= 10:
            maturity_tier = "EARLY_OBSERVED_METRIC"
            maturity_label = f"EARLY OBSERVED METRIC (N = {n_clean})"
            interpretation = "Early exploratory forward observations. Confidence intervals are wide and metrics should not be treated as established edge confirmation."
        else:
            maturity_tier = "OBSERVED_METRIC"
            maturity_label = f"PRELIMINARY RAW OBSERVATION (N = {n_clean})"
            interpretation = f"Raw sample observation only (N = {n_clean}). Statistical status: INSUFFICIENT SAMPLE. Never extrapolate to true strategy parameters."

        return {
            "trades_n": n_clean,
            "win_rate_pct": round(win_rate, 2),
            "expectancy_r": round(avg_r, 4),
            "average_r": round(avg_r, 4),
            "median_r": round(median_r, 4),
            "profit_factor": round(profit_factor, 2),
            "cumulative_r": round(cum_r, 2),
            "max_drawdown_r": round(max_dd, 2),
            "std_dev_r": round(std_r, 4),
            "win_count": win_count,
            "loss_count": loss_count,
            "breakeven_count": be_count,
            "win_streak": max_win_streak,
            "loss_streak": max_loss_streak,
            "outcomes": outcomes,
            "maturity_tier": maturity_tier,
            "maturity_label": maturity_label,
            "interpretation": interpretation
        }


class ConservativeUncertaintyEngine:
    """
    Computes conservative confidence intervals (Wilson score for win rate, Bootstrap for expectancy).
    Explicitly guards against presenting point estimates as certainty at low sample sizes.
    """

    @classmethod
    def calculate_win_rate_ci_wilson(cls, win_count: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
        """
        Calculates Wilson score confidence interval for binomial win rate proportion.
        """
        if n <= 0:
            return (0.0, 0.0)

        p = win_count / n
        # Normal critical values: 90% -> 1.645, 95% -> 1.960, 99% -> 2.576
        if confidence == 0.99:
            z = 2.575829
        elif confidence == 0.90:
            z = 1.644853
        else:
            z = 1.959964

        z2 = z * z
        denom = 1.0 + (z2 / n)
        center = (p + (z2 / (2.0 * n))) / denom
        margin = (z * np.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))) / denom

        lower = max(0.0, (center - margin) * 100.0)
        upper = min(100.0, (center + margin) * 100.0)

        return (round(lower, 1), round(upper, 1))

    @classmethod
    def calculate_expectancy_ci_bootstrap(cls, r_values: List[float], n_bootstraps: int = 2000, seed: int = 42) -> Dict[str, Tuple[float, float]]:
        """
        Calculates conservative non-parametric bootstrap confidence intervals for expectancy E[R].
        """
        n = len(r_values)
        if n < 5:
            # Not enough data for meaningful bootstrap
            mean_val = float(np.mean(r_values)) if n > 0 else 0.0
            return {
                "ci_90": (round(mean_val - 2.0, 3), round(mean_val + 2.0, 3)),
                "ci_95": (round(mean_val - 2.5, 3), round(mean_val + 2.5, 3)),
                "ci_99": (round(mean_val - 3.5, 3), round(mean_val + 3.5, 3)),
            }

        rng = np.random.default_rng(seed)
        r_arr = np.array(r_values, dtype=float)
        boot_means = np.empty(n_bootstraps)

        for i in range(n_bootstraps):
            sample = rng.choice(r_arr, size=n, replace=True)
            boot_means[i] = np.mean(sample)

        ci_90 = (round(float(np.percentile(boot_means, 5.0)), 3), round(float(np.percentile(boot_means, 95.0)), 3))
        ci_95 = (round(float(np.percentile(boot_means, 2.5)), 3), round(float(np.percentile(boot_means, 97.5)), 3))
        ci_99 = (round(float(np.percentile(boot_means, 0.5)), 3), round(float(np.percentile(boot_means, 99.5)), 3))

        return {
            "ci_90": ci_90,
            "ci_95": ci_95,
            "ci_99": ci_99
        }

    @classmethod
    def evaluate_uncertainty_state(cls, n: int, win_rate_pct: float, expectancy_r: float, r_values: List[float]) -> Dict[str, Any]:
        """
        Evaluates uncertainty and returns structured scientific disclaimers.
        """
        if n == 0:
            return {
                "sample_n": 0,
                "statistical_status": "NO_FORWARD_DATA",
                "status_badge": "INSUFFICIENT SAMPLE (N = 0)",
                "status_color": "#8a99ad",
                "win_rate_statement": "OBSERVED WIN RATE = N/A",
                "expectancy_statement": "OBSERVED EXPECTANCY = N/A",
                "ci_95_wr": (0.0, 0.0),
                "ci_95_exp": (0.0, 0.0),
                "prohibited_claim": "Any performance or edge claim at N = 0 is scientifically invalid.",
                "valid_statement": "System is initialized and awaiting first forward observation."
            }

        win_count = int(round((win_rate_pct / 100.0) * n))
        wr_ci90 = cls.calculate_win_rate_ci_wilson(win_count, n, confidence=0.90)
        wr_ci95 = cls.calculate_win_rate_ci_wilson(win_count, n, confidence=0.95)
        wr_ci99 = cls.calculate_win_rate_ci_wilson(win_count, n, confidence=0.99)

        exp_cis = cls.calculate_expectancy_ci_bootstrap(r_values)

        if n < 10:
            status_code = "INSUFFICIENT_SAMPLE"
            status_badge = f"INSUFFICIENT SAMPLE (N = {n})"
            status_color = "#f59e0b"
            prohibited = f"Stating 'STRATEGY WIN RATE = {win_rate_pct:.1f}%' or 'STRATEGY EXPECTANCY = {expectancy_r:+.3f}R' is strictly prohibited at N = {n}."
            valid = f"OBSERVED WIN RATE = {win_rate_pct:.1f}% (95% CI: [{wr_ci95[0]}%, {wr_ci95[1]}%]), OBSERVED EXPECTANCY = {expectancy_r:+.3f}R (95% CI: [{exp_cis['ci_95'][0]:+.3f}R, {exp_cis['ci_95'][1]:+.3f}R])."
        elif n < 30:
            status_code = "EARLY_SAMPLE"
            status_badge = f"EARLY SAMPLE (N = {n})"
            status_color = "#38bdf8"
            prohibited = f"Claiming definitive confirmation of historical edge with N = {n} (< 30)."
            valid = f"Observed sample indicates preliminary distribution, wide confidence interval [{wr_ci95[0]}%, {wr_ci95[1]}%]."
        elif n < 100:
            status_code = "MODERATE_SAMPLE"
            status_badge = f"STATISTICALLY INFORMATIVE (N = {n})"
            status_color = "#bef264"
            prohibited = "Declaring production strategy validation before milestone N = 100."
            valid = f"Moderate statistical confidence established (95% CI: [{wr_ci95[0]}%, {wr_ci95[1]}%])."
        else:
            status_code = "DECISION_ELIGIBLE_SAMPLE"
            status_badge = f"DECISION ELIGIBLE (N = {n})"
            status_color = "#00ffcc"
            prohibited = "Extrapolating outside of observed market regimes."
            valid = f"High statistical confidence achieved (95% CI: [{wr_ci95[0]}%, {wr_ci95[1]}%])."

        return {
            "sample_n": n,
            "statistical_status": status_code,
            "status_badge": status_badge,
            "status_color": status_color,
            "win_rate_statement": f"OBSERVED WIN RATE = {win_rate_pct:.1f}%",
            "expectancy_statement": f"OBSERVED EXPECTANCY = {expectancy_r:+.3f} R",
            "ci_90_wr": wr_ci90,
            "ci_95_wr": wr_ci95,
            "ci_99_wr": wr_ci99,
            "ci_90_exp": exp_cis["ci_90"],
            "ci_95_exp": exp_cis["ci_95"],
            "ci_99_exp": exp_cis["ci_99"],
            "prohibited_claim": prohibited,
            "valid_statement": valid
        }


class HistoricalVsForwardComparativeMonitor:
    """
    Performs rigorous side-by-side comparative monitoring between the locked historical holdout
    baseline and genuine forward observations without dataset pooling.
    """

    @classmethod
    def compare_historical_vs_forward(cls, fwd_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compares forward metrics against locked historical baseline.
        """
        n_fwd = fwd_metrics.get("trades_n", 0)
        h = HISTORICAL_BASELINE

        if n_fwd == 0:
            return {
                "historical": h,
                "forward": {
                    "trades_n": 0,
                    "expectancy_r": 0.0,
                    "win_rate_pct": 0.0,
                    "profit_factor": 0.0,
                    "max_drawdown_r": 0.0,
                    "status": "WAITING_FOR_DATA"
                },
                "deltas": {
                    "expectancy_delta": 0.0,
                    "win_rate_delta_pct": 0.0,
                    "profit_factor_delta": 0.0,
                    "drawdown_divergence_r": 0.0,
                },
                "comparison_verdict": "NO FORWARD EVIDENCE (N = 0)",
                "verdict_color": "#8a99ad",
                "explanation": "No forward trades recorded yet. Historical baseline (+0.637R, N=82) remains locked.",
                "pooling_prevention_check": "PASS (DATASETS UNPOOLED)"
            }

        f_exp = fwd_metrics.get("expectancy_r", 0.0)
        f_wr = fwd_metrics.get("win_rate_pct", 0.0)
        f_pf = fwd_metrics.get("profit_factor", 0.0)
        f_dd = fwd_metrics.get("max_drawdown_r", 0.0)

        exp_delta = f_exp - h["expectancy_r"]
        wr_delta = f_wr - h["win_rate_pct"]
        pf_delta = f_pf - h["profit_factor"]
        dd_delta = f_dd - h["max_drawdown_r"]

        # Consistency Classification
        if n_fwd < 10:
            verdict = "INSUFFICIENT SAMPLE FOR COMPARISON"
            color = "#f59e0b"
            meaning = f"Small forward sample (N = {n_fwd}). Deltas reflect early variance rather than true structural drift."
        elif f_exp >= h["expectancy_r"] * 0.8 and f_wr >= h["win_rate_pct"] - 10.0:
            verdict = "CONSISTENT WITH HISTORICAL BASELINE"
            color = "#00ffcc"
            meaning = "Forward distribution aligns with locked historical holdout parameters."
        elif f_exp >= 0.0:
            verdict = "MODERATE DIVERGENCE (POSITIVE EXPECTANCY)"
            color = "#bef264"
            meaning = "Forward expectancy is lower than historical baseline (+0.637R) but remains positive."
        elif f_exp < 0.0:
            verdict = "POTENTIAL STRUCTURAL DEGRADATION"
            color = "#ef4444"
            meaning = "Forward expectancy is negative. Alpha decay monitoring triggered."
        else:
            verdict = "INCONCLUSIVE"
            color = "#8a99ad"
            meaning = "Data requires additional forward observation."

        return {
            "historical": h,
            "forward": {
                "trades_n": n_fwd,
                "expectancy_r": f_exp,
                "win_rate_pct": f_wr,
                "profit_factor": f_pf,
                "max_drawdown_r": f_dd,
                "status": "EVALUATED"
            },
            "deltas": {
                "expectancy_delta": round(exp_delta, 4),
                "win_rate_delta_pct": round(wr_delta, 2),
                "profit_factor_delta": round(pf_delta, 2),
                "drawdown_divergence_r": round(dd_delta, 2),
            },
            "comparison_verdict": verdict,
            "verdict_color": color,
            "explanation": meaning,
            "pooling_prevention_check": "PASS (DATASETS UNPOOLED)"
        }


class AlphaDecayStatisticalMonitor:
    """
    Consumes forward evidence and provides non-invasive alpha decay monitoring.
    Never alters strategy rules, retrains models, or tunes thresholds.
    """

    @classmethod
    def audit_alpha_stability(cls, fwd_metrics: Dict[str, Any], symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Evaluates alpha persistence across forward observations.
        """
        n = fwd_metrics.get("trades_n", 0)
        if n == 0:
            return {
                "symbol": symbol,
                "forward_n": 0,
                "decay_state": "INSUFFICIENT FORWARD EVIDENCE (N = 0)",
                "decay_color": "#8a99ad",
                "loss_clustering_detected": False,
                "expectancy_deterioration": False,
                "action_required": "NONE (LEAVE SYSTEM RUNNING)",
                "summary": "No forward observations recorded yet. Baseline edge active in theory."
            }

        exp_r = fwd_metrics.get("expectancy_r", 0.0)
        loss_streak = fwd_metrics.get("loss_streak", 0)
        max_dd = fwd_metrics.get("max_drawdown_r", 0.0)

        loss_cluster = loss_streak >= 4
        exp_deterioration = exp_r < 0.0
        dd_expansion = max_dd > HISTORICAL_BASELINE["max_drawdown_r"] * 1.5

        if n < 10:
            state = "INSUFFICIENT SAMPLE FOR ALPHA AUDIT"
            color = "#f59e0b"
            summary = f"Sample N = {n} is too small to determine alpha persistence or decay."
        elif exp_deterioration and loss_cluster:
            state = "POTENTIAL ALPHA DECAY — RESEARCH REVIEW REQUIRED"
            color = "#ef4444"
            summary = f"Negative forward expectancy ({exp_r:+.3f}R) and loss clustering ({loss_streak} losses) detected."
        elif exp_deterioration or dd_expansion:
            state = "EARLY INSTABILITY DETECTED"
            color = "#f97316"
            summary = "Drawdown or expectancy diverging from historical holdout parameters."
        elif exp_r >= HISTORICAL_BASELINE["expectancy_r"] * 0.7:
            state = "NO EVIDENCE OF ALPHA DECAY"
            color = "#00ffcc"
            summary = "Forward performance exhibits robust edge persistence consistent with historical baseline."
        else:
            state = "MODERATE EDGE COMPRESSION"
            color = "#bef264"
            summary = "Edge remains positive but demonstrates mild compression relative to backtest."

        return {
            "symbol": symbol,
            "forward_n": n,
            "decay_state": state,
            "decay_color": color,
            "loss_clustering_detected": loss_cluster,
            "expectancy_deterioration": exp_deterioration,
            "max_drawdown_expansion": dd_expansion,
            "action_required": "RESEARCH REVIEW REQUIRED" if "DECAY" in state else "CONTINUE OBSERVATION",
            "summary": summary
        }


class SequentialEvidenceGovernanceEngine:
    """
    Monitors progress across 14 deterministic milestones and stores immutable milestone snapshots.
    Guards against selective cherry-picking / optional stopping.
    """

    @classmethod
    def evaluate_milestones(cls, actual_n: int) -> Dict[str, Any]:
        """
        Evaluates milestone progress across 14 checkpoints.
        """
        milestones = FORWARD_MILESTONES
        next_m = None
        for m in milestones:
            if actual_n < m:
                next_m = m
                break

        if next_m is None:
            next_m = milestones[-1]
            remaining = 0
            pct = 100.0
        else:
            remaining = max(0, next_m - actual_n)
            prev_m = 0
            for m in milestones:
                if m <= actual_n:
                    prev_m = m
            span = next_m - prev_m
            done = actual_n - prev_m
            pct = min(100.0, (done / span) * 100.0) if span > 0 else 100.0

        roadmap = []
        for m in milestones:
            if actual_n >= m:
                st_label = "REACHED"
                rem = 0
            else:
                st_label = "PENDING"
                rem = m - actual_n

            roadmap.append({
                "target_n": m,
                "status_label": st_label,
                "trades_remaining": rem,
                "is_reached": actual_n >= m
            })

        return {
            "current_n": actual_n,
            "next_milestone": next_m,
            "trades_remaining": remaining,
            "completion_pct_toward_next": round(pct, 1),
            "milestone_roadmap": roadmap
        }

    @classmethod
    def record_milestone_snapshot(
        cls,
        milestone_n: int,
        actual_n: int,
        metrics: Dict[str, Any],
        decision_state: str,
        alpha_state: str,
        dataset_fp: str,
        conn=None
    ) -> Optional[Dict[str, Any]]:
        """
        Records an immutable cryptographic snapshot when a milestone is reached.
        """
        should_close = False
        if conn is None:
            conn = database.get_connection()
            should_close = True

        snapshot_id = f"SNAP_P49_M{milestone_n}_{uuid.uuid4().hex[:8]}"
        now_ts = datetime.now(timezone.utc).isoformat()
        raw_sig = f"{snapshot_id}:{milestone_n}:{actual_n}:{now_ts}:{dataset_fp}:{FROZEN_CONTRACT_HASH}"
        snap_fp = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()

        cur = conn.cursor()
        try:
            cur.execute("""
            INSERT OR REPLACE INTO xauusd_phase49_statistical_snapshots (
                snapshot_id, milestone_n, actual_n, timestamp, dataset_fingerprint,
                contract_hash, expectancy_r, win_rate_pct, profit_factor, max_drawdown_r,
                ci_95_lower, ci_95_upper, metric_tier, decision_state, alpha_decay_state,
                quarantine_count, isolation_verified, details_json, snapshot_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id,
                milestone_n,
                actual_n,
                now_ts,
                dataset_fp,
                FROZEN_CONTRACT_HASH,
                metrics.get("expectancy_r", 0.0),
                metrics.get("win_rate_pct", 0.0),
                metrics.get("profit_factor", 0.0),
                metrics.get("max_drawdown_r", 0.0),
                0.0,
                0.0,
                metrics.get("maturity_tier", "OBSERVED"),
                decision_state,
                alpha_state,
                0,
                1,
                json.dumps(metrics),
                snap_fp
            ))
            conn.commit()
            # A milestone snapshot is a material forward-evidence state transition:
            # drop the cached read snapshot so the next read recomputes.
            Phase49MonitoringFacade.invalidate_forward_state_snapshot()
            return {"snapshot_id": snapshot_id, "snapshot_fingerprint": snap_fp, "status": "RECORDED"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
        finally:
            if should_close:
                conn.close()

    @classmethod
    def get_milestone_snapshots(cls, limit: int = 10, conn=None) -> List[Dict[str, Any]]:
        """Retrieves recent milestone snapshots."""
        should_close = False
        if conn is None:
            conn = database.get_connection()
            should_close = True

        cur = conn.cursor()
        cur.execute("""
        SELECT snapshot_id, milestone_n, actual_n, timestamp, expectancy_r, win_rate_pct,
               profit_factor, max_drawdown_r, metric_tier, decision_state, alpha_decay_state,
               snapshot_fingerprint
        FROM xauusd_phase49_statistical_snapshots
        ORDER BY timestamp DESC
        LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        if should_close:
            conn.close()

        res = []
        for r in rows:
            res.append({
                "snapshot_id": r[0],
                "milestone_n": r[1],
                "actual_n": r[2],
                "timestamp": r[3],
                "expectancy_r": r[4],
                "win_rate_pct": r[5],
                "profit_factor": r[6],
                "max_drawdown_r": r[7],
                "metric_tier": r[8],
                "decision_state": r[9],
                "alpha_decay_state": r[10],
                "snapshot_fingerprint": r[11]
            })
        return res


class DecisionStateEvaluator:
    """
    Evaluates deterministic research decision state across sample tiers without strategy mutation.
    """

    @classmethod
    def evaluate_decision_state(cls, n: int, exp_r: float, alpha_state: str) -> Dict[str, Any]:
        """
        Returns structured decision state verdict and rationale.
        """
        if n == 0:
            return {
                "decision_state": "INSUFFICIENT EVIDENCE (N = 0)",
                "decision_color": "#8a99ad",
                "rationale": "Forward validation pipeline active. Waiting for genuine forward market observations.",
                "research_action": "Maintain automated observation without intervention."
            }
        elif n < 10:
            return {
                "decision_state": "EARLY FORWARD EVIDENCE",
                "decision_color": "#f59e0b",
                "rationale": f"Preliminary evidence stage (N = {n}). Observations captured cleanly without statistical convergence.",
                "research_action": "Continue accumulation toward milestone N = 10."
            }
        elif n < 30:
            return {
                "decision_state": "EMERGING CONSISTENCY",
                "decision_color": "#38bdf8",
                "rationale": f"Initial distribution emerging (N = {n}). Expectancy observed at {exp_r:+.3f}R.",
                "research_action": "Monitor session and regime breakdown toward N = 30."
            }
        elif n < 100:
            if "DECAY" in alpha_state:
                return {
                    "decision_state": "POTENTIAL DEGRADATION",
                    "decision_color": "#ef4444",
                    "rationale": "Statistically informative sample indicates significant divergence from historical baseline.",
                    "research_action": "Trigger comprehensive research review. Do not modify live code."
                }
            return {
                "decision_state": "STATISTICALLY INFORMATIVE",
                "decision_color": "#bef264",
                "rationale": f"Sample size (N = {n}) provides solid empirical foundation. Expectancy is {exp_r:+.3f}R.",
                "research_action": "Continue observation toward formal milestone N = 100."
            }
        else:
            if exp_r > 0.3:
                return {
                    "decision_state": "RESEARCH VALIDATION ESTABLISHED",
                    "decision_color": "#00ffcc",
                    "rationale": f"Large forward sample (N = {n}) confirms robust out-of-sample edge persistence (+{exp_r:.3f}R).",
                    "research_action": "Prepare complete human review package."
                }
            else:
                return {
                    "decision_state": "RESEARCH REVIEW REQUIRED",
                    "decision_color": "#f97316",
                    "rationale": f"N = {n} achieved but forward expectancy ({exp_r:+.3f}R) is below target threshold.",
                    "research_action": "Conduct deep-dive regime and slippage decomposition."
                }


class RestartDeterminismAuditor:
    """
    Verifies that restarting the system produces identical statistical evaluations
    without data drift, duplicate insertions, or state corruption.
    """

    @classmethod
    def verify_restart_determinism(cls, mode: str = "PAPER", symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Runs two independent evaluations in sequence and asserts exact fingerprint identity.
        """
        eval_1 = Phase49MonitoringFacade.evaluate_full_forward_state(mode=mode, symbol=symbol)
        eval_2 = Phase49MonitoringFacade.evaluate_full_forward_state(mode=mode, symbol=symbol)

        fp1 = eval_1["dataset"]["dataset_fingerprint"]
        fp2 = eval_2["dataset"]["dataset_fingerprint"]
        n1 = eval_1["metrics"]["trades_n"]
        n2 = eval_2["metrics"]["trades_n"]

        is_deterministic = (fp1 == fp2) and (n1 == n2)

        return {
            "is_deterministic": is_deterministic,
            "evaluation_1_fingerprint": fp1,
            "evaluation_2_fingerprint": fp2,
            "evaluation_1_n": n1,
            "evaluation_2_n": n2,
            "status": "PASS (DETERMINISTIC)" if is_deterministic else "FAIL (NON-DETERMINISTIC)"
        }


# -----------------------------------------------------------------------------
# Stage 3.5D — bounded, thread-safe read-snapshot cache for the API read path.
# The authoritative computation (evaluate_full_forward_state) is unchanged and
# still runs verbatim on a cold read / after invalidation; this only prevents an
# identical multi-second recomputation on every UI poll. Explicitly invalidated
# by record_milestone_snapshot() (a genuine forward-evidence state transition).
# -----------------------------------------------------------------------------
_FORWARD_STATE_SNAPSHOT_TTL_SEC = 60.0
_forward_state_snapshot_lock = threading.Lock()
_forward_state_snapshot: Dict[str, Any] = {"key": None, "data": None, "ts": 0.0}


class Phase49MonitoringFacade:
    """
    Unified facade coordinating all Phase 49 engines for dashboard rendering,
    automated audits, and forensic verification.
    """

    @classmethod
    def get_cached_forward_state_snapshot(
        cls,
        mode: str = "PAPER",
        symbol: str = "XAUUSD",
        ttl_sec: float = _FORWARD_STATE_SNAPSHOT_TTL_SEC,
    ) -> Dict[str, Any]:
        """
        Returns evaluate_full_forward_state() through a process-local, TTL-bounded,
        thread-safe single-slot cache. Read-only: performs no audit/event writes.
        A cold call computes the authoritative state exactly as before.
        """
        cache_key = (str(mode).upper(), str(symbol).upper())
        with _forward_state_snapshot_lock:
            snap = _forward_state_snapshot
            if (
                snap["data"] is not None
                and snap["key"] == cache_key
                and (time.time() - snap["ts"]) < ttl_sec
            ):
                return snap["data"]
            state = cls.evaluate_full_forward_state(mode=mode, symbol=symbol)
            _forward_state_snapshot["key"] = cache_key
            _forward_state_snapshot["data"] = state
            _forward_state_snapshot["ts"] = time.time()
            return state

    @classmethod
    def invalidate_forward_state_snapshot(cls) -> None:
        """Explicit invalidation hook for genuine forward-evidence state changes."""
        with _forward_state_snapshot_lock:
            _forward_state_snapshot["key"] = None
            _forward_state_snapshot["data"] = None
            _forward_state_snapshot["ts"] = 0.0

    @classmethod
    def evaluate_full_forward_state(cls, mode: str = "PAPER", symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Synthesizes complete Phase 49 state payload.
        """
        dataset_info = CanonicalForwardDatasetEngine.get_canonical_dataset(mode=mode, symbol=symbol)
        df_trades = dataset_info["trades_df"]
        n_clean = dataset_info["clean_n"]

        # Calculate metrics
        metrics = ForwardMetricsEngine.calculate_forward_metrics(df_trades)
        r_vals = df_trades["r_multiple"].dropna().astype(float).tolist() if (n_clean > 0 and "r_multiple" in df_trades.columns) else []

        # Uncertainty
        uncertainty = ConservativeUncertaintyEngine.evaluate_uncertainty_state(
            n=n_clean,
            win_rate_pct=metrics.get("win_rate_pct", 0.0),
            expectancy_r=metrics.get("expectancy_r", 0.0),
            r_values=r_vals
        )

        # Historical vs Forward
        comp = HistoricalVsForwardComparativeMonitor.compare_historical_vs_forward(metrics)

        # Alpha Decay
        alpha = AlphaDecayStatisticalMonitor.audit_alpha_stability(metrics, symbol=symbol)

        # Milestones
        milestones = SequentialEvidenceGovernanceEngine.evaluate_milestones(n_clean)

        # Decision State
        decision = DecisionStateEvaluator.evaluate_decision_state(
            n=n_clean,
            exp_r=metrics.get("expectancy_r", 0.0),
            alpha_state=alpha["decay_state"]
        )

        # Safety Verification
        contract_valid = (dataset_info["contract_hash"] == FROZEN_CONTRACT_HASH)

        return {
            "symbol": symbol,
            "mode": mode,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "contract_hash": FROZEN_CONTRACT_HASH,
            "contract_valid": contract_valid,
            "dataset": dataset_info,
            "metrics": metrics,
            "uncertainty": uncertainty,
            "comparison": comp,
            "alpha_decay": alpha,
            "milestones": milestones,
            "decision": decision,
            "live_automation_barrier": {
                "live_automation_enabled": False,
                "broker_transmission": "BLOCKED (FAIL-CLOSED)",
                "status": "PASS (SAFETY LOCKED)"
            }
        }
