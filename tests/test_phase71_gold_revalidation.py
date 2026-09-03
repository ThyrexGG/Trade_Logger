# -*- coding: utf-8 -*-
"""Phase 71 — Gold revalidation baseline (§30/§31)."""
import gold_revalidation as gr
import gold_strategy_baseline as gsb


# --- comparison helper --------------------------------------------------
def test_compare_row_flags_material_difference():
    row = gr._compare_row("expectancy_r", 0.637, 0.10, "R")
    assert row["difference"] == round(0.10 - 0.637, 3)
    assert "materially lower" in row["interpretation"]

    same = gr._compare_row("x", 0.20, 0.15, "R")
    assert "in line" in same["interpretation"]

    dd = gr._compare_row("max_drawdown_r", 4.0, 8.0, "R", better="lower")
    assert "materially worse" in dd["interpretation"]

    missing = gr._compare_row("x", None, 0.1, "R")
    assert missing["difference"] is None


# --- classification ----------------------------------------------------
def _pt(state="AVAILABLE", n=60, exp=0.15, ci_low=0.02, ci_up=0.30):
    return {
        "1h": {
            "state": state,
            "oos_metrics": {"total_trades": n, "expectancy_r": exp},
            "bootstrap_ci": {"ci_lower": ci_low, "ci_upper": ci_up},
            "scorecard": {"status": "PROMISING"},
        }
    }


def test_classify_insufficient_when_small_sample():
    status, reason, verdict = gr._classify(_pt(n=8), {"stability": 0.5})
    assert status == gsb.EdgeStatus.INSUFFICIENT_EVIDENCE.value
    assert "UNVERIFIABLE" in verdict


def test_classify_invalidated_on_negative_ci_upper():
    status, _, verdict = gr._classify(_pt(n=60, exp=-0.2, ci_low=-0.4, ci_up=-0.05),
                                      {"stability": 0.3})
    assert status == gsb.EdgeStatus.INVALIDATED.value


def test_classify_validated_only_with_strong_evidence():
    status, _, verdict = gr._classify(_pt(n=80, exp=0.25, ci_low=0.05), {"stability": 0.8})
    assert status == gsb.EdgeStatus.VALIDATED.value
    assert "timeframe-substituted" in verdict.lower()


def test_classify_degraded_for_weak_positive():
    status, _, verdict = gr._classify(_pt(n=46, exp=0.10, ci_low=-0.05), {"stability": 0.4})
    assert status == gsb.EdgeStatus.DEGRADED.value
    assert "UNVERIFIABLE" in verdict


# --- baseline merge --------------------------------------------------
def test_baseline_merges_persisted_revalidation(monkeypatch):
    fake = {
        "generated_at": "2026-09-03T00:00:00+00:00",
        "strategy_id": gr.REVAL_STRATEGY_ID,
        "timeframe_substitution_note": "1m not available; 1h proxy",
        "edge_status": "DEGRADED",
        "edge_status_reason": "weak positive on 1h proxy",
        "per_timeframe": {
            "1h": {"oos_metrics": {"expectancy_r": 0.106, "total_trades": 46},
                   "bootstrap_ci": {"ci_lower": -0.05}, "scorecard": {"status": "UNCERTAIN"},
                   "session_breakdown": {}},
            "1d": {"oos_metrics": {"expectancy_r": 0.0, "total_trades": 5},
                   "scorecard": {"status": "INSUFFICIENT DATA"}},
        },
        "walk_forward": {"stability": 0.33, "verdict": "UNSTABLE"},
        "comparison": [],
    }
    monkeypatch.setattr(gsb, "_load_revalidation", lambda: fake)
    b = gsb.get_gold_baseline()
    assert b.edge_status == "DEGRADED"
    assert b.revalidated_metrics is not None
    assert b.revalidated_metrics["1h"]["expectancy_r"] == 0.106
    assert b.last_validated_at == "2026-09-03T00:00:00+00:00"
    assert "intraday OHLCV provider" in b.next_dependency


def test_baseline_without_revalidation_is_insufficient(monkeypatch):
    monkeypatch.setattr(gsb, "_load_revalidation", lambda: None)
    b = gsb.get_gold_baseline()
    assert b.edge_status == gsb.EdgeStatus.INSUFFICIENT_EVIDENCE.value
    assert b.revalidated_metrics is None


# --- never touches the holdout --------------------------------------
def test_revalidation_declares_holdout_untouched():
    # the dataclass default and the frozen constants
    from xauusd_forward_accumulation import HistoricalVsForwardComparator as H
    assert H.LOCKED_HISTORICAL_BASELINE["n"] == 82
    assert H.LOCKED_HISTORICAL_BASELINE["expectancy_r"] == 0.637
    r = gr.GoldRevalidation(
        generated_at="t", strategy_id="x", approximated_contract="x",
        timeframe_substitution_note="x", frozen_contract_hash="x",
        per_timeframe={}, walk_forward={}, comparison=[], edge_status="x",
        edge_status_reason="x", verdict="x")
    assert r.holdout_untouched is True


def test_revalidation_never_claims_holdout_equivalence():
    note = gr.revalidate.__doc__ or ""
    # module docstring carries the caveat
    assert "NOT possible" in gr.__doc__ or "not possible" in gr.__doc__
