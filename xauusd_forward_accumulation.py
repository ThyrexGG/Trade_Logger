"""
Phase 44 — XAUUSD Forward Accumulation, Milestones, Rolling Stability & Historical Comparison Engine
Provides:
- ForwardAccumulationEngine: Clean, isolated forward observation accumulation with deterministic checkpoints
- SampleMilestoneEngine: Deterministic tracking for N in [10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 500]
- RollingWindowAnalysisEngine: Multi-window rolling forward analysis (10, 20, 30, 50, 75, 100 trades)
- ExpandingWindowCurveEngine: Chronological cumulative performance curve without curve-fitting
- HistoricalVsForwardComparator: Rigorous comparison against the locked N=82 historical baseline
"""

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set

import numpy as np
import pandas as pd

import database
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_forward_observation_quality import (
    ForwardObservationQualityEngine,
    ObservationQuarantineSubsystem,
    ObservationEvidenceQualityScorer,
)
from xauusd_forward_evidence import ForwardEvidenceAnalyzer
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_market_conditions import FROZEN_CONTRACT_HASH


def init_phase44_database(conn=None):
    """Initializes tables for accumulation checkpoints, milestone events, and rolling snapshots."""
    should_close = False
    if conn is None:
        conn = database.get_connection()
        should_close = True

    cur = conn.cursor()

    # 1. Accumulation Checkpoints
    cur.execute("""
    CREATE TABLE IF NOT EXISTS xauusd_forward_accumulation_checkpoints (
        checkpoint_id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        forward_n INTEGER NOT NULL,
        paper_n INTEGER NOT NULL,
        shadow_n INTEGER NOT NULL,
        completed_observations INTEGER NOT NULL,
        quarantined_observations INTEGER NOT NULL,
        invalidations INTEGER NOT NULL,
        timeouts INTEGER NOT NULL,
        total_r REAL NOT NULL,
        expectancy_r REAL NOT NULL,
        win_rate_pct REAL NOT NULL,
        profit_factor REAL NOT NULL,
        max_drawdown_r REAL NOT NULL,
        dataset_fingerprint TEXT NOT NULL,
        contract_hash TEXT NOT NULL,
        details TEXT
    )
    """)

    # 2. Milestone Events
    cur.execute("""
    CREATE TABLE IF NOT EXISTS xauusd_milestone_events (
        milestone_id TEXT PRIMARY KEY,
        target_n INTEGER NOT NULL UNIQUE,
        reached_timestamp TEXT,
        is_reached INTEGER NOT NULL DEFAULT 0,
        expectancy_r REAL,
        win_rate_pct REAL,
        profit_factor REAL,
        total_r REAL,
        max_drawdown_r REAL,
        ci_95_lower REAL,
        ci_95_upper REAL,
        data_quality_score REAL,
        fingerprint TEXT
    )
    """)

    # 3. Rolling Stability Snapshots
    cur.execute("""
    CREATE TABLE IF NOT EXISTS xauusd_rolling_stability_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        window_size INTEGER NOT NULL,
        trades_count INTEGER NOT NULL,
        expectancy_r REAL,
        median_r REAL,
        win_rate_pct REAL,
        profit_factor REAL,
        total_r REAL,
        max_drawdown_r REAL,
        avg_winner_r REAL,
        avg_loser_r REAL,
        payoff_ratio REAL,
        win_streak INTEGER,
        loss_streak INTEGER
    )
    """)

    conn.commit()
    if should_close:
        conn.close()


init_phase44_database()


class ForwardAccumulationEngine:
    """
    Subsystem for reading clean completed forward observations, excluding quarantined records,
    and persisting deterministic accumulation checkpoints.
    """

    @staticmethod
    def get_clean_completed_observations(mode: str = "PAPER") -> pd.DataFrame:
        """
        Retrieves clean, non-quarantined, completed forward observations in strict chronological order.
        """
        df_raw = XAUUSDForwardJournal.get_forward_trades(mode=mode)
        if df_raw.empty:
            return pd.DataFrame()

        quar_recs = ObservationQuarantineSubsystem.get_quarantined_records(limit=500)
        quar_ids = {q["observation_id"] for q in quar_recs}

        # Filter out quarantined records
        if "signal_id" in df_raw.columns:
            df_clean = df_raw[~df_raw["signal_id"].isin(quar_ids)].copy()
        else:
            df_clean = df_raw.copy()

        # Filter completed status only (not timeouts, invalidations, or pending)
        if "status" in df_clean.columns:
            df_clean = df_clean[df_clean["status"] == "COMPLETED"].copy()

        # Sort chronologically by entry_time or created_at
        time_col = "entry_time" if "entry_time" in df_clean.columns else ("created_at" if "created_at" in df_clean.columns else None)
        if time_col and time_col in df_clean.columns:
            df_clean[time_col] = pd.to_datetime(df_clean[time_col], errors="coerce", utc=True)
            df_clean = df_clean.sort_values(by=time_col).reset_index(drop=True)

        return df_clean

    @classmethod
    def create_accumulation_checkpoint(cls, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Calculates and persists a deterministic accumulation checkpoint.
        """
        init_phase44_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        chk_id = f"CHK_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        df_paper = cls.get_clean_completed_observations(mode="PAPER")
        df_shadow = cls.get_clean_completed_observations(mode="SHADOW")
        quar_recs = ObservationQuarantineSubsystem.get_quarantined_records(limit=100)

        n_paper = len(df_paper)
        n_shadow = len(df_shadow)
        n_quar = len(quar_recs)

        if n_paper > 0 and "r_multiple" in df_paper.columns:
            r_vals = df_paper["r_multiple"].astype(float).values
            total_r = float(np.sum(r_vals))
            expectancy_r = float(np.mean(r_vals))
            wins = r_vals[r_vals > 0]
            losses = r_vals[r_vals < 0]
            win_rate_pct = float(len(wins) / len(r_vals) * 100.0) if len(r_vals) > 0 else 0.0
            sum_wins = float(np.sum(wins)) if len(wins) > 0 else 0.0
            sum_losses = float(np.abs(np.sum(losses))) if len(losses) > 0 else 0.0
            profit_factor = float(sum_wins / sum_losses) if sum_losses > 0 else (99.0 if sum_wins > 0 else 0.0)
            
            # Max Drawdown
            cum = np.cumsum(r_vals)
            peak = np.maximum.accumulate(cum)
            dd = peak - cum
            max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0
        else:
            total_r = 0.0
            expectancy_r = 0.0
            win_rate_pct = 0.0
            profit_factor = 0.0
            max_dd = 0.0

        # Dataset Fingerprint
        fp_payload = {
            "symbol": symbol,
            "forward_paper_n": n_paper,
            "forward_shadow_n": n_shadow,
            "total_r": total_r,
            "expectancy_r": expectancy_r,
            "contract_hash": FROZEN_CONTRACT_HASH,
        }
        dataset_fp = hashlib.sha256(json.dumps(fp_payload, sort_keys=True).encode()).hexdigest()

        conn = database.get_connection()
        cur = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)

        query = f"""
        INSERT INTO xauusd_forward_accumulation_checkpoints (
            checkpoint_id, timestamp, forward_n, paper_n, shadow_n,
            completed_observations, quarantined_observations, invalidations,
            timeouts, total_r, expectancy_r, win_rate_pct, profit_factor,
            max_drawdown_r, dataset_fingerprint, contract_hash, details
        ) VALUES ({','.join([placeholder]*17)})
        """
        params = (
            chk_id, now_iso, n_paper, n_paper, n_shadow,
            n_paper, n_quar, 0, 0, total_r, expectancy_r, win_rate_pct,
            profit_factor, max_dd, dataset_fp, FROZEN_CONTRACT_HASH, json.dumps(fp_payload)
        )
        cur.execute(query, params)
        conn.commit()
        conn.close()

        return {
            "checkpoint_id": chk_id,
            "timestamp": now_iso,
            "forward_n": n_paper,
            "paper_n": n_paper,
            "shadow_n": n_shadow,
            "total_r": round(total_r, 3),
            "expectancy_r": round(expectancy_r, 3),
            "win_rate_pct": round(win_rate_pct, 1),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_r": round(max_dd, 2),
            "dataset_fingerprint": dataset_fp,
            "contract_hash": FROZEN_CONTRACT_HASH,
        }

    @staticmethod
    def get_accumulation_history(limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves recent accumulation checkpoints."""
        init_phase44_database()
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute(f"""
        SELECT checkpoint_id, timestamp, forward_n, paper_n, shadow_n,
               total_r, expectancy_r, win_rate_pct, profit_factor,
               max_drawdown_r, dataset_fingerprint
        FROM xauusd_forward_accumulation_checkpoints
        ORDER BY timestamp DESC LIMIT {int(limit)}
        """)
        rows = cur.fetchall()
        conn.close()

        res = []
        for r in rows:
            res.append({
                "checkpoint_id": r[0],
                "timestamp": r[1],
                "forward_n": r[2],
                "paper_n": r[3],
                "shadow_n": r[4],
                "total_r": r[5],
                "expectancy_r": r[6],
                "win_rate_pct": r[7],
                "profit_factor": r[8],
                "max_drawdown_r": r[9],
                "dataset_fingerprint": r[10],
            })
        return res


class SampleMilestoneEngine:
    """
    Tracks and persists progress across deterministic sample size milestones:
    N in [10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 500].
    """

    MILESTONES = [10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 500]

    @classmethod
    def evaluate_all_milestones(cls, symbol: str = "XAUUSD") -> List[Dict[str, Any]]:
        """
        Evaluates milestone achievement status against current clean forward observations.
        """
        df_paper = ForwardAccumulationEngine.get_clean_completed_observations(mode="PAPER")
        current_n = len(df_paper)

        milestone_cards = []
        for m in cls.MILESTONES:
            is_reached = current_n >= m
            if is_reached and "r_multiple" in df_paper.columns:
                sub_df = df_paper.iloc[:m]
                r_vals = sub_df["r_multiple"].astype(float).values
                exp_r = float(np.mean(r_vals))
                wins = r_vals[r_vals > 0]
                losses = r_vals[r_vals < 0]
                wr = float(len(wins) / len(r_vals) * 100.0)
                pf = float(np.sum(wins) / np.abs(np.sum(losses))) if np.sum(losses) != 0 else 99.0
                tot_r = float(np.sum(r_vals))
                cum = np.cumsum(r_vals)
                max_dd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) > 0 else 0.0

                boot = ForwardEvidenceAnalyzer.calculate_bootstrap_confidence_intervals(r_vals.tolist(), n_bootstrap=1000)
                ci_95 = boot.get("ci_95", (0.0, 0.0))
                status_label = f"REACHED (N = {m})"
                status_color = "#00ffcc"
            else:
                exp_r = 0.0
                wr = 0.0
                pf = 0.0
                tot_r = 0.0
                max_dd = 0.0
                ci_95 = (0.0, 0.0)
                status_label = "MILESTONE NOT REACHED"
                status_color = "#8a99ad"

            milestone_cards.append({
                "target_n": m,
                "is_reached": is_reached,
                "current_progress_pct": min(100.0, round(current_n / m * 100.0, 1)),
                "remaining_n": max(0, m - current_n),
                "status_label": status_label,
                "status_color": status_color,
                "expectancy_r": round(exp_r, 3) if is_reached else None,
                "win_rate_pct": round(wr, 1) if is_reached else None,
                "profit_factor": round(pf, 2) if is_reached else None,
                "total_r": round(tot_r, 2) if is_reached else None,
                "max_drawdown_r": round(max_dd, 2) if is_reached else None,
                "ci_95": ci_95 if is_reached else None,
            })

        return milestone_cards


class RollingWindowAnalysisEngine:
    """
    Calculates rolling statistics across standardized forward trade windows:
    Last 10, 20, 30, 50, 75, 100 trades in chronological order.
    """

    WINDOWS = [10, 20, 30, 50, 75, 100]

    @classmethod
    def compute_rolling_windows(cls, df_trades: Optional[pd.DataFrame] = None) -> List[Dict[str, Any]]:
        """
        Calculates rolling performance metrics for each window size.
        """
        if df_trades is None:
            df_trades = ForwardAccumulationEngine.get_clean_completed_observations(mode="PAPER")

        current_n = len(df_trades)
        results = []

        for w in cls.WINDOWS:
            has_enough = current_n >= w
            if has_enough and "r_multiple" in df_trades.columns:
                sub_r = df_trades.tail(w)["r_multiple"].astype(float).values
                exp_r = float(np.mean(sub_r))
                med_r = float(np.median(sub_r))
                wins = sub_r[sub_r > 0]
                losses = sub_r[sub_r < 0]
                wr = float(len(wins) / len(sub_r) * 100.0)
                tot_r = float(np.sum(sub_r))
                sum_wins = float(np.sum(wins)) if len(wins) > 0 else 0.0
                sum_losses = float(np.abs(np.sum(losses))) if len(losses) > 0 else 0.0
                pf = float(sum_wins / sum_losses) if sum_losses > 0 else (99.0 if sum_wins > 0 else 0.0)

                cum = np.cumsum(sub_r)
                max_dd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) > 0 else 0.0
                avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
                avg_loss = float(np.mean(np.abs(losses))) if len(losses) > 0 else 0.0
                payoff = float(avg_win / avg_loss) if avg_loss > 0 else 0.0

                # Streaks
                win_streak = 0
                loss_streak = 0
                cur_w = 0
                cur_l = 0
                for r in sub_r:
                    if r > 0:
                        cur_w += 1
                        cur_l = 0
                        win_streak = max(win_streak, cur_w)
                    elif r < 0:
                        cur_l += 1
                        cur_w = 0
                        loss_streak = max(loss_streak, cur_l)

                interpretation = "ACTIVE WINDOW STATS"
                status_color = "#00ffcc"
            else:
                exp_r = None
                med_r = None
                wr = None
                pf = None
                tot_r = None
                max_dd = None
                avg_win = None
                avg_loss = None
                payoff = None
                win_streak = None
                loss_streak = None
                interpretation = f"INSUFFICIENT DATA (NEED N >= {w})"
                status_color = "#8a99ad"

            results.append({
                "window_name": f"Last {w} Trades",
                "window_size": w,
                "actual_n": current_n if not has_enough else w,
                "has_enough_data": has_enough,
                "expectancy_r": round(exp_r, 3) if exp_r is not None else None,
                "median_r": round(med_r, 3) if med_r is not None else None,
                "win_rate_pct": round(wr, 1) if wr is not None else None,
                "profit_factor": round(pf, 2) if pf is not None else None,
                "total_r": round(tot_r, 2) if tot_r is not None else None,
                "max_drawdown_r": round(max_dd, 2) if max_dd is not None else None,
                "avg_winner_r": round(avg_win, 2) if avg_win is not None else None,
                "avg_loser_r": round(avg_loss, 2) if avg_loss is not None else None,
                "payoff_ratio": round(payoff, 2) if payoff is not None else None,
                "win_streak": win_streak,
                "loss_streak": loss_streak,
                "interpretation": interpretation,
                "status_color": status_color,
            })

        return results


class ExpandingWindowCurveEngine:
    """
    Generates the un-smoothed expanding chronological curve at each completed forward trade.
    """

    @staticmethod
    def compute_expanding_curve(df_trades: Optional[pd.DataFrame] = None) -> List[Dict[str, Any]]:
        """
        Returns cumulative progression for observations 1 to N.
        """
        if df_trades is None:
            df_trades = ForwardAccumulationEngine.get_clean_completed_observations(mode="PAPER")

        if df_trades.empty or "r_multiple" not in df_trades.columns:
            return []

        curve = []
        r_vals = df_trades["r_multiple"].astype(float).values
        time_col = "entry_time" if "entry_time" in df_trades.columns else ("created_at" if "created_at" in df_trades.columns else None)

        cum_r = 0.0
        peak_r = 0.0
        wins_count = 0

        for i, r in enumerate(r_vals, start=1):
            cum_r += r
            peak_r = max(peak_r, cum_r)
            cur_dd = peak_r - cum_r
            if r > 0:
                wins_count += 1
            
            sub_r = r_vals[:i]
            sub_wins = sub_r[sub_r > 0]
            sub_losses = sub_r[sub_r < 0]
            sum_w = float(np.sum(sub_wins)) if len(sub_wins) > 0 else 0.0
            sum_l = float(np.abs(np.sum(sub_losses))) if len(sub_losses) > 0 else 0.0
            pf = float(sum_w / sum_l) if sum_l > 0 else (99.0 if sum_w > 0 else 0.0)

            ts_str = str(df_trades.iloc[i-1][time_col])[:19] if time_col else f"Trade {i}"
            sig_id = str(df_trades.iloc[i-1].get("signal_id", f"OBS_{i:03d}"))

            curve.append({
                "trade_index": i,
                "signal_id": sig_id,
                "timestamp": ts_str,
                "r_multiple": round(float(r), 3),
                "cumulative_r": round(float(cum_r), 3),
                "cumulative_expectancy": round(float(cum_r / i), 3),
                "cumulative_win_rate": round(float(wins_count / i * 100.0), 1),
                "cumulative_profit_factor": round(float(pf), 2),
                "running_peak_r": round(float(peak_r), 3),
                "running_drawdown_r": round(float(cur_dd), 3),
            })

        return curve


class HistoricalVsForwardComparator:
    """
    Rigorously benchmarks forward accumulation against the locked N=82 historical holdout baseline.
    """

    LOCKED_HISTORICAL_BASELINE = {
        "n": 82,
        "expectancy_r": 0.637,
        "win_rate_pct": 58.6,
        "profit_factor": 2.52,
        "ci_95": (0.477, 0.817),
        "max_drawdown_r": 4.0,
        "contract_hash": FROZEN_CONTRACT_HASH,
    }

    @classmethod
    def compare_forward_to_historical(cls, df_trades: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Calculates deltas between locked historical baseline and forward evidence.
        """
        if df_trades is None:
            df_trades = ForwardAccumulationEngine.get_clean_completed_observations(mode="PAPER")

        forward_n = len(df_trades)
        hist = cls.LOCKED_HISTORICAL_BASELINE

        if forward_n < 10 or "r_multiple" not in df_trades.columns:
            return {
                "forward_n": forward_n,
                "historical_n": hist["n"],
                "has_sufficient_data": False,
                "verdict": "INSUFFICIENT DATA (N < 10)",
                "verdict_color": "#8a99ad",
                "explanation": f"Forward sample size (N = {forward_n}) is below minimum statistical threshold (N >= 10) to compute meaningful comparative deltas.",
                "historical_baseline": hist,
                "forward_stats": {
                    "expectancy_r": 0.0,
                    "win_rate_pct": 0.0,
                    "profit_factor": 0.0,
                    "max_drawdown_r": 0.0,
                    "total_r": 0.0,
                },
                "deltas": {
                    "expectancy_delta": 0.0,
                    "win_rate_delta_pct": 0.0,
                    "profit_factor_delta": 0.0,
                }
            }

        r_vals = df_trades["r_multiple"].astype(float).values
        fwd_exp = float(np.mean(r_vals))
        wins = r_vals[r_vals > 0]
        losses = r_vals[r_vals < 0]
        fwd_wr = float(len(wins) / len(r_vals) * 100.0)
        sum_w = float(np.sum(wins)) if len(wins) > 0 else 0.0
        sum_l = float(np.abs(np.sum(losses))) if len(losses) > 0 else 0.0
        fwd_pf = float(sum_w / sum_l) if sum_l > 0 else (99.0 if sum_w > 0 else 0.0)

        cum = np.cumsum(r_vals)
        fwd_dd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) > 0 else 0.0
        fwd_tot_r = float(np.sum(r_vals))

        exp_delta = fwd_exp - hist["expectancy_r"]
        wr_delta = fwd_wr - hist["win_rate_pct"]
        pf_delta = fwd_pf - hist["profit_factor"]

        # Classification
        if fwd_exp >= hist["ci_95"][0]:
            verdict = "CONSISTENT WITH HISTORICAL BASELINE"
            verdict_color = "#00ffcc"
            exp_text = f"Forward expectancy ({fwd_exp:+.3f}R) lies within or above the historical 95% CI [{hist['ci_95'][0]:+.3f}R, {hist['ci_95'][1]:+.3f}R]."
        elif fwd_exp > 0.0:
            verdict = "POSITIVE EXPECTANCY (MODEST VARIATION)"
            verdict_color = "#bef264"
            exp_text = f"Forward expectancy ({fwd_exp:+.3f}R) remains positive but is tracking slightly below the historical 95% CI lower bound."
        else:
            verdict = "NEGATIVE FORWARD EXPECTANCY (DEGRADATION WATCH)"
            verdict_color = "#ef4444"
            exp_text = f"Forward expectancy ({fwd_exp:+.3f}R) is currently negative. Continued accumulation required to evaluate persistence."

        return {
            "forward_n": forward_n,
            "historical_n": hist["n"],
            "has_sufficient_data": True,
            "verdict": verdict,
            "verdict_color": verdict_color,
            "explanation": exp_text,
            "historical_baseline": hist,
            "forward_stats": {
                "expectancy_r": round(fwd_exp, 3),
                "win_rate_pct": round(fwd_wr, 1),
                "profit_factor": round(fwd_pf, 2),
                "max_drawdown_r": round(fwd_dd, 2),
                "total_r": round(fwd_tot_r, 2),
            },
            "deltas": {
                "expectancy_delta": round(exp_delta, 3),
                "win_rate_delta_pct": round(wr_delta, 1),
                "profit_factor_delta": round(pf_delta, 2),
            }
        }
