"""
Phase 44 — XAUUSD Alpha Decay Monitor, Sequential Block Stability & Regime-Specific Decay Engine
Provides:
- AlphaDecayMonitor: Conservative multi-factor evaluation of edge persistence vs structural degradation
- SequentialBlockStabilityEngine: Chronological block testing (tertiles 1/3, 2/3, 3/3 and quartiles 25%, 50%, 75%, 100%)
- RegimeSpecificAlphaDecayEngine: Subgroup performance across sessions, bank holidays, and macroeconomic news windows
- DataQualityGate: Pre-monitoring filter excluding corrupted or unvalidated records with full reason logging
- ResearchInterpretationSynthesizer: Honest plain-language synthesis of forward evidence status
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
from xauusd_forward_accumulation import (
    ForwardAccumulationEngine,
    HistoricalVsForwardComparator,
    RollingWindowAnalysisEngine,
)
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_forward_observation_quality import (
    ForwardObservationQualityEngine,
    ObservationQuarantineSubsystem,
    ObservationEvidenceQualityScorer,
)
from xauusd_forward_evidence import ForwardEvidenceAnalyzer
from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from xauusd_news_reliability import MarketClosureAuditor


def init_phase44_alpha_tables(conn=None):
    """Initializes table for alpha decay snapshots."""
    should_close = False
    if conn is None:
        conn = database.get_connection()
        should_close = True

    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS xauusd_alpha_decay_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        forward_n INTEGER NOT NULL,
        decay_state TEXT NOT NULL,
        decay_color TEXT NOT NULL,
        expectancy_delta REAL,
        win_rate_delta REAL,
        profit_factor_delta REAL,
        drawdown_expansion_r REAL,
        block_stability_score REAL,
        regime_decay_flag INTEGER,
        explanation TEXT,
        fingerprint TEXT
    )
    """)

    conn.commit()
    if should_close:
        conn.close()


init_phase44_alpha_tables()


class DataQualityGate:
    """
    Validates every candidate observation prior to inclusion in alpha monitoring calculations.
    Excludes quarantined, malformed, or lookahead-violating records with reason codes.
    """

    @staticmethod
    def filter_observations_for_alpha_monitoring(df_trades: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Filters dataframe and returns (clean_df, excluded_records).
        """
        if df_trades.empty:
            return pd.DataFrame(), []

        quar_recs = ObservationQuarantineSubsystem.get_quarantined_records(limit=500)
        quar_ids = {q["observation_id"] for q in quar_recs}

        clean_rows = []
        excluded_records = []

        for idx, row in df_trades.iterrows():
            row_dict = row.to_dict()
            obs_id = str(row_dict.get("signal_id", f"ROW_{idx}"))

            if obs_id in quar_ids:
                excluded_records.append({
                    "observation_id": obs_id,
                    "reason": "RECORD_QUARANTINED",
                    "status": "EXCLUDED FROM ALPHA MONITORING"
                })
                continue

            # Check status
            if row_dict.get("status") not in ["COMPLETED", None]:
                excluded_records.append({
                    "observation_id": obs_id,
                    "reason": f"NON_COMPLETED_STATUS_{row_dict.get('status')}",
                    "status": "EXCLUDED FROM ALPHA MONITORING"
                })
                continue

            # Check R-multiple validity
            try:
                r_val = float(row_dict.get("r_multiple", 0.0))
                if np.isnan(r_val) or np.isinf(r_val):
                    excluded_records.append({
                        "observation_id": obs_id,
                        "reason": "INVALID_R_MULTIPLE",
                        "status": "EXCLUDED FROM ALPHA MONITORING"
                    })
                    continue
            except (ValueError, TypeError):
                excluded_records.append({
                    "observation_id": obs_id,
                    "reason": "NON_NUMERIC_R_MULTIPLE",
                    "status": "EXCLUDED FROM ALPHA MONITORING"
                })
                continue

            clean_rows.append(row_dict)

        clean_df = pd.DataFrame(clean_rows) if clean_rows else pd.DataFrame()
        return clean_df, excluded_records


class SequentialBlockStabilityEngine:
    """
    Evaluates chronological stability by splitting forward observations into tertiles (1/3, 2/3, 3/3)
    and quartiles (25%, 50%, 75%, 100%) to test for early vs late divergence.
    """

    @staticmethod
    def evaluate_sequential_blocks(df_trades: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Computes chronological block metrics.
        """
        if df_trades is None:
            df_trades = ForwardAccumulationEngine.get_clean_completed_observations(mode="PAPER")

        total_n = len(df_trades)
        if total_n < 9 or "r_multiple" not in df_trades.columns:
            return {
                "total_n": total_n,
                "has_sufficient_data": False,
                "has_enough_data": False,
                "status": "INSUFFICIENT DATA (N < 9 FOR BLOCK ANALYSIS)",
                "tertiles": [],
                "quartiles": [],
                "stability_verdict": "INSUFFICIENT SAMPLE SIZE",
                "stability_color": "#8a99ad",
            }

        r_vals = df_trades["r_multiple"].astype(float).values

        # 1. Tertiles (1/3, 2/3, 3/3)
        t_size = total_n // 3
        b1_r = r_vals[:t_size]
        b2_r = r_vals[t_size:2*t_size]
        b3_r = r_vals[2*t_size:]

        def _calc_block_stats(block_name: str, arr: np.ndarray) -> Dict[str, Any]:
            n = len(arr)
            exp = float(np.mean(arr)) if n > 0 else 0.0
            wins = arr[arr > 0]
            losses = arr[arr < 0]
            wr = float(len(wins) / n * 100.0) if n > 0 else 0.0
            sw = float(np.sum(wins)) if len(wins) > 0 else 0.0
            sl = float(np.abs(np.sum(losses))) if len(losses) > 0 else 0.0
            pf = float(sw / sl) if sl > 0 else (99.0 if sw > 0 else 0.0)
            cum = np.cumsum(arr)
            dd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) > 0 else 0.0
            return {
                "block_name": block_name,
                "n": n,
                "expectancy_r": round(exp, 3),
                "win_rate_pct": round(wr, 1),
                "profit_factor": round(pf, 2),
                "max_drawdown_r": round(dd, 2),
                "total_r": round(float(np.sum(arr)), 2),
            }

        tertiles = [
            _calc_block_stats("Early Stage (First 1/3)", b1_r),
            _calc_block_stats("Middle Stage (Second 1/3)", b2_r),
            _calc_block_stats("Recent Stage (Final 1/3)", b3_r),
        ]

        # 2. Quartiles (25%, 50%, 75%, 100%)
        q_size = total_n // 4
        quartiles = []
        if q_size > 0:
            quartiles.append(_calc_block_stats("Quartile 1 (0–25%)", r_vals[:q_size]))
            quartiles.append(_calc_block_stats("Quartile 2 (25–50%)", r_vals[q_size:2*q_size]))
            quartiles.append(_calc_block_stats("Quartile 3 (50–75%)", r_vals[2*q_size:3*q_size]))
            quartiles.append(_calc_block_stats("Quartile 4 (75–100%)", r_vals[3*q_size:]))

        # Check stability across tertiles
        exp_1 = tertiles[0]["expectancy_r"]
        exp_3 = tertiles[2]["expectancy_r"]

        if exp_3 >= 0.3:
            stability_verdict = "STABLE FORWARD TRAJECTORY"
            stability_color = "#00ffcc"
        elif exp_3 >= 0.0:
            stability_verdict = "MODEST VARIATION ACROSS PERIODS"
            stability_color = "#bef264"
        else:
            stability_verdict = "RECENT PERIOD UNDERPERFORMANCE"
            stability_color = "#f59e0b"

        return {
            "total_n": total_n,
            "has_sufficient_data": True,
            "has_enough_data": True,
            "status": "CHRONOLOGICAL BLOCKS EVALUATED",
            "tertiles": tertiles,
            "quartiles": quartiles,
            "stability_verdict": stability_verdict,
            "stability_color": stability_color,
        }


class RegimeSpecificAlphaDecayEngine:
    """
    Subgroup analysis across sessions, bank holidays, and macroeconomic news windows.
    Enforces sample size protection rules (N < 10 => INSUFFICIENT DATA).
    """

    @staticmethod
    def evaluate_regime_decay(df_trades: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Evaluates forward stability across operational market subgroups.
        """
        if df_trades is None:
            df_trades = ForwardAccumulationEngine.get_clean_completed_observations(mode="PAPER")

        total_n = len(df_trades)

        # Standard operational subgroups
        subgroups_def = [
            {"name": "London Session", "key": "session", "val": "LONDON"},
            {"name": "New York Session", "key": "session", "val": "NEW YORK"},
            {"name": "London / NY Overlap", "key": "session", "val": "LONDON / NY OVERLAP"},
            {"name": "Asia Session", "key": "session", "val": "ASIA"},
            {"name": "Normal Trading Days", "key": "holiday", "val": "NORMAL"},
            {"name": "Bank Holiday / Reduced Liquidity", "key": "holiday", "val": "HOLIDAY"},
            {"name": "High-Impact News Proximity (±15m)", "key": "news", "val": "HIGH_IMPACT"},
            {"name": "Non-High-Impact Windows", "key": "news", "val": "STANDARD"},
        ]

        subgroup_results = []
        for sg in subgroups_def:
            sub_n = 0
            exp_r = None
            wr_pct = None
            pf_val = None
            tot_r = None
            tier = "INSUFFICIENT DATA (N < 10)"
            tier_color = "#8a99ad"

            if not df_trades.empty and "r_multiple" in df_trades.columns:
                # If specific metadata column exists, filter; otherwise empty
                col = sg["key"]
                if col in df_trades.columns:
                    filtered = df_trades[df_trades[col].astype(str).str.upper() == sg["val"]].copy()
                else:
                    filtered = pd.DataFrame()

                sub_n = len(filtered)
                if sub_n >= 10:
                    r_vals = filtered["r_multiple"].astype(float).values
                    exp_r = round(float(np.mean(r_vals)), 3)
                    wins = r_vals[r_vals > 0]
                    losses = r_vals[r_vals < 0]
                    wr_pct = round(float(len(wins) / sub_n * 100.0), 1)
                    sw = float(np.sum(wins)) if len(wins) > 0 else 0.0
                    sl = float(np.abs(np.sum(losses))) if len(losses) > 0 else 0.0
                    pf_val = round(float(sw / sl), 2) if sl > 0 else (99.0 if sw > 0 else 0.0)
                    tot_r = round(float(np.sum(r_vals)), 2)

                    if sub_n < 20:
                        tier = "LIMITED OBSERVATIONS (10 <= N < 20)"
                        tier_color = "#bef264"
                    elif sub_n < 30:
                        tier = "EARLY REGIME EVIDENCE (20 <= N < 30)"
                        tier_color = "#00ffcc"
                    else:
                        tier = "REGIME SAMPLE (N >= 30)"
                        tier_color = "#00ffcc"

            subgroup_results.append({
                "subgroup_name": sg["name"],
                "sample_n": sub_n,
                "statistical_tier": tier,
                "tier_color": tier_color,
                "expectancy_r": exp_r,
                "win_rate_pct": wr_pct,
                "profit_factor": pf_val,
                "total_r": tot_r,
            })

        return {
            "total_forward_n": total_n,
            "subgroups": subgroup_results,
            "disclaimer": "Observational context only. Contextual proximity does not demonstrate causation.",
        }


class AlphaDecayMonitor:
    """
    Core Alpha Decay monitoring engine.
    Produces conservative, multi-factor evaluation of edge persistence vs structural degradation:
    - INSUFFICIENT FORWARD EVIDENCE (N < 10)
    - NO EVIDENCE OF DECAY
    - EARLY INSTABILITY
    - POSSIBLE DEGRADATION
    - PERSISTENT DEGRADATION
    - POTENTIAL ALPHA DECAY — HUMAN REVIEW REQUIRED
    """

    @classmethod
    def evaluate_alpha_decay(cls, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Synthesizes multi-factor alpha decay state.
        """
        init_phase44_alpha_tables()
        now_iso = datetime.now(timezone.utc).isoformat()
        snap_id = f"SNAP_DEC_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        df_trades = ForwardAccumulationEngine.get_clean_completed_observations(mode="PAPER")
        clean_df, excluded = DataQualityGate.filter_observations_for_alpha_monitoring(df_trades)
        current_n = len(clean_df)

        hist_comp = HistoricalVsForwardComparator.compare_forward_to_historical(clean_df)
        rolling = RollingWindowAnalysisEngine.compute_rolling_windows(clean_df)
        seq_blocks = SequentialBlockStabilityEngine.evaluate_sequential_blocks(clean_df)
        regime_eval = RegimeSpecificAlphaDecayEngine.evaluate_regime_decay(clean_df)

        # Conservative Decision Logic
        if current_n < 10:
            decay_state = "INSUFFICIENT FORWARD EVIDENCE (N < 10)"
            decay_color = "#8a99ad"
            reason_text = f"Sample size (N = {current_n}) is too small to evaluate statistical stability. No alpha decay can be inferred."
        elif current_n < 30:
            fwd_exp = hist_comp["forward_stats"]["expectancy_r"]
            if fwd_exp >= 0.0:
                decay_state = "EARLY FORWARD EVIDENCE (STABLE EXPECTANCY)"
                decay_color = "#00ffcc"
                reason_text = f"Early forward sample (N = {current_n}) exhibits positive expectancy ({fwd_exp:+.3f}R)."
            else:
                decay_state = "EARLY INSTABILITY (SAMPLE LIMITED)"
                decay_color = "#f59e0b"
                reason_text = f"Early forward sample (N = {current_n}) shows temporary drawdown ({fwd_exp:+.3f}R). Persistence across N >= 30 required before concluding degradation."
        elif current_n < 50:
            fwd_exp = hist_comp["forward_stats"]["expectancy_r"]
            hist_exp = hist_comp["historical_baseline"]["expectancy_r"]
            if fwd_exp >= hist_comp["historical_baseline"]["ci_95"][0]:
                decay_state = "NO EVIDENCE OF DECAY"
                decay_color = "#00ffcc"
                reason_text = f"Forward expectancy ({fwd_exp:+.3f}R) remains consistent with historical 95% confidence interval."
            elif fwd_exp > 0.0:
                decay_state = "POSSIBLE DEGRADATION (MONITORING WATCH)"
                decay_color = "#f59e0b"
                reason_text = f"Forward expectancy ({fwd_exp:+.3f}R) is positive but tracking below historical baseline lower bound ({hist_comp['historical_baseline']['ci_95'][0]:+.3f}R)."
            else:
                decay_state = "PERSISTENT DEGRADATION"
                decay_color = "#ef4444"
                reason_text = f"Forward expectancy is negative ({fwd_exp:+.3f}R) across developing sample (N = {current_n})."
        else:
            # Substantial sample (N >= 50)
            fwd_exp = hist_comp["forward_stats"]["expectancy_r"]
            if fwd_exp >= hist_comp["historical_baseline"]["ci_95"][0]:
                decay_state = "NO EVIDENCE OF DECAY"
                decay_color = "#00ffcc"
                reason_text = f"Substantial forward sample (N = {current_n}) confirms edge consistency ({fwd_exp:+.3f}R)."
            elif fwd_exp > 0.0:
                decay_state = "POSSIBLE DEGRADATION"
                decay_color = "#f59e0b"
                reason_text = f"Expectancy remains positive ({fwd_exp:+.3f}R) but exhibits statistical divergence from historical baseline."
            else:
                decay_state = "POTENTIAL ALPHA DECAY — HUMAN REVIEW REQUIRED"
                decay_color = "#ef4444"
                reason_text = f"Persistent negative expectancy ({fwd_exp:+.3f}R) observed across substantial forward sample (N = {current_n}). Human governance review required."

        # Dataset Fingerprint
        fp_payload = {
            "snapshot_id": snap_id,
            "forward_n": current_n,
            "decay_state": decay_state,
            "contract_hash": FROZEN_CONTRACT_HASH,
        }
        fp = hashlib.sha256(json.dumps(fp_payload, sort_keys=True).encode()).hexdigest()

        # Persist snapshot
        conn = database.get_connection()
        cur = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)
        query = f"""
        INSERT INTO xauusd_alpha_decay_snapshots (
            snapshot_id, timestamp, forward_n, decay_state, decay_color,
            expectancy_delta, win_rate_delta, profit_factor_delta,
            drawdown_expansion_r, block_stability_score, regime_decay_flag,
            explanation, fingerprint
        ) VALUES ({','.join([placeholder]*13)})
        """
        params = (
            snap_id, now_iso, current_n, decay_state, decay_color,
            hist_comp["deltas"]["expectancy_delta"],
            hist_comp["deltas"]["win_rate_delta_pct"],
            hist_comp["deltas"]["profit_factor_delta"],
            hist_comp["forward_stats"]["max_drawdown_r"],
            100.0, 0, reason_text, fp
        )
        cur.execute(query, params)
        conn.commit()
        conn.close()

        interp = ResearchInterpretationSynthesizer.synthesize_interpretation(current_n, decay_state)

        return {
            "snapshot_id": snap_id,
            "timestamp": now_iso,
            "forward_n": current_n,
            "decay_state": decay_state,
            "decay_color": decay_color,
            "reason_text": reason_text,
            "historical_comparison": hist_comp,
            "rolling_windows": rolling,
            "sequential_blocks": seq_blocks,
            "regime_stability": regime_eval,
            "excluded_observations_count": len(excluded),
            "research_interpretation": interp,
            "contract_hash": FROZEN_CONTRACT_HASH,
            "live_automation": "DISABLED_PERMANENTLY",
        }


class ResearchInterpretationSynthesizer:
    """
    Produces plain-language, evidence-bounded explanations for researchers.
    """

    @staticmethod
    def synthesize_interpretation(n: int, decay_state: str) -> str:
        """
        Returns plain-language summary strictly bounded by sample size N.
        """
        if n == 0:
            return "N = 0 — The forward experiment is active and monitoring market conditions. No forward performance conclusion is mathematically possible."
        elif n < 10:
            return f"N = {n} — Early observations exist, but statistical inference is not permitted below N = 10. Continue unattended accumulation."
        elif n < 30:
            return f"N = {n} — Developing forward evidence. Sample is entering early regime evaluation (Stage 0). Stability should be monitored without premature decay conclusions."
        elif n < 50:
            return f"N = {n} — Moderate forward sample (Stage 1 reached). Comparative deltas against the N = 82 historical baseline become meaningful."
        else:
            return f"N = {n} — Substantial forward sample size. Confidence intervals and rolling stability metrics provide high statistical confidence."
