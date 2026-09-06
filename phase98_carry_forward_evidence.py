# -*- coding: utf-8 -*-
"""
Phase 98 -- Funding-Carry Forward-Evidence Harness.

Phase 97 produced the first non-null verdict in the research program:
`USABLE_EDGE_FOUND` -- ~25% of capital in delta-neutral crypto funding
carry (multi-venue), rest in cash. Before any capital is risked, the
right discipline is to accumulate GENUINE real-time forward evidence:
does the edge keep behaving the way the 2017-2026 backtest says it
should, on weeks the backtest never saw?

This phase is that harness. It does NOT execute anything. It:

  1. (optionally) refreshes the underlying data by re-running the
     idempotent Phase 94/96 ingestion for recent weeks;
  2. runs the FROZEN Phase-96 carry rules over all history and splits the
     weekly result at a frozen GO-LIVE anchor -- everything on/before the
     anchor is the "backtest reference", everything strictly after is
     "forward" (real-time out-of-sample) evidence;
  3. applies Phase 97's frozen f* = 25% sizing to the forward carry
     returns to show the recommended book's real forward equity curve;
  4. appends an immutable, timestamped snapshot each run
     (`phase98_forward_snapshot__<iso>` artifacts -- never overwritten);
  5. once enough forward weeks have accumulated, compares the forward
     segment to the backtest reference (funding level, Sharpe, basis
     drag) and issues a TRACKING / DIVERGING / CONFIRMING / INSUFFICIENT
     verdict.

Nothing here is fitted or tuned -- every rule and threshold is frozen and
inherited from Phase 96/97. Read-only research: no execution, no broker
transmission, no account mutation, no order/position module import.
Frozen Phase-74 Gold holdout never read.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase94_swing_data_foundation as p94
import phase96_funding_carry as p96
import phase97_portfolio_construction as p97

SCHEMA_VERSION = "phase98.1"
ARTIFACT_KEY = "phase98_carry_forward_evidence"
_SNAPSHOT_PREFIX = "phase98_forward_snapshot__"

# ==========================================================================
# Frozen anchors / thresholds (inherited; nothing tuned)
# ==========================================================================
_GO_LIVE_DATE = "2026-09-04"                 # last Friday with complete daily data at phase creation;
                                            # weeks strictly after this are forward / real-time OOS
_RECOMMENDED_CARRY_FRACTION = 0.25          # Phase 97 f*
_CASH_ANNUAL = p97._CASH_ANNUAL
_WEEKS_PER_YEAR = 52.0

_MIN_FORWARD_WEEKS_TO_ASSESS = 12           # below this: INSUFFICIENT
_MIN_FORWARD_WEEKS_TO_CONFIRM = 26
# forward is "tracking" if its annualised funding / Sharpe stay within these
# bands of the backtest reference (generous -- this is a health check, not a t-test)
_FUNDING_TRACKING_BAND = 0.40               # forward ann funding >= 60% of backtest ann funding
_SHARPE_TRACKING_FLOOR = 0.50               # forward Sharpe >= 0.5 (backtest is ~3)
_DIVERGING_FUNDING_FLOOR = 0.25             # forward ann funding < 25% of backtest -> diverging
_DIVERGING_SHARPE = 0.0                     # forward Sharpe < 0 -> diverging

DESIGN_NOTE: Dict[str, Any] = {
    "purpose": "accumulate genuine real-time forward evidence on the Phase-97 funding-carry edge "
               "before any capital is risked; no execution",
    "go_live_anchor": _GO_LIVE_DATE,
    "rules": "FROZEN Phase-96 carry rules + Phase-97 f*=0.25 sizing; nothing re-fitted",
    "snapshots": f"immutable append-only artifacts '{_SNAPSHOT_PREFIX}<iso>' -- one per run, never "
                 "overwritten",
    "verdict_gates": {
        "insufficient_below_weeks": _MIN_FORWARD_WEEKS_TO_ASSESS,
        "confirm_at_weeks": _MIN_FORWARD_WEEKS_TO_CONFIRM,
        "tracking_needs": f"forward ann funding >= {1 - _FUNDING_TRACKING_BAND:.0%} of backtest AND "
                          f"forward Sharpe >= {_SHARPE_TRACKING_FLOOR}",
        "diverging_if": f"forward ann funding < {_DIVERGING_FUNDING_FLOOR:.0%} of backtest OR forward "
                        f"Sharpe < {_DIVERGING_SHARPE}",
    },
    "holdout": "frozen Phase-74 Gold holdout never read",
}


def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


# ==========================================================================
# Data refresh (idempotent; safe to skip)
# ==========================================================================
def refresh_data(do_spot: bool = True, do_funding: bool = True, do_perp: bool = True) -> Dict[str, Any]:
    """Re-run the idempotent Phase 94/96 ingestion so the forward window
    can grow. Best-effort -- network failures are reported, not raised."""
    out: Dict[str, Any] = {}
    try:
        if do_spot:
            r = p94.ingest_crypto_ohlcv()
            out["spot"] = {"ok": sum(1 for o in r if o.ok), "n": len(r)}
        if do_funding:
            r = p94.ingest_crypto_funding()
            out["funding"] = {"ok": sum(1 for o in r if o.ok), "n": len(r)}
        if do_perp:
            r = p96.ingest_perp_ohlcv()
            out["perp"] = {"ok": sum(1 for o in r if o.ok), "n": len(r)}
    except Exception as e:  # pragma: no cover - network dependent
        out["error"] = f"{e!r}"[:300]
    p96._PANEL_CACHE.clear()
    p95_cache = getattr(__import__("phase95_swing_momentum"), "_PANEL_CACHE", None)
    if isinstance(p95_cache, dict):
        p95_cache.clear()
    return out


# ==========================================================================
# Ledger: split the frozen carry backtest at the go-live anchor
# ==========================================================================
def _seg_metrics(net: np.ndarray, funding: np.ndarray, basis: np.ndarray, cost: np.ndarray,
                 index: pd.DatetimeIndex) -> Dict[str, Any]:
    n = np.asarray(net, float)
    m = np.isfinite(n)
    n, ix = n[m], index[m]
    if n.size == 0:
        return {"state": "EMPTY", "n_weeks": 0}
    years = max(n.size / _WEEKS_PER_YEAR, 1e-9)
    eq = np.cumprod(1.0 + n)
    sd = float(n.std(ddof=1)) if n.size > 1 else 0.0
    out = {
        "state": "OK", "n_weeks": int(n.size),
        "start": ix[0].date().isoformat(), "end": ix[-1].date().isoformat(),
        "cumulative_return": round(float(eq[-1] - 1.0), 5),
        "ann_return": round(float(eq[-1] ** (1.0 / years) - 1.0) if eq[-1] > 0 else -1.0, 4),
        "ann_vol": round(sd * np.sqrt(_WEEKS_PER_YEAR), 4),
        "sharpe": round(float(n.mean() / sd * np.sqrt(_WEEKS_PER_YEAR)), 3) if sd > 0 else None,
        "ann_funding": round(float(np.nansum(funding[m]) / years), 4),
        "ann_basis": round(float(np.nansum(basis[m]) / years), 4),
        "ann_cost": round(float(np.nansum(cost[m]) / years), 4),
        "worst_week": round(float(n.min()), 5), "best_week": round(float(n.max()), 5),
        "positive_weeks_pct": round(float((n > 0).mean()), 3),
    }
    return out


def compute_ledger(cost_key: str = "BASE") -> Dict[str, Any]:
    r = p96.run_carry(cost_key=cost_key)
    idx = r["index"]
    anchor = pd.Timestamp(_GO_LIVE_DATE, tz="UTC")
    pre = idx <= anchor
    fwd = idx > anchor

    def _slice(mask: np.ndarray) -> Dict[str, Any]:
        return _seg_metrics(r["net"][mask], r["funding"][mask], r["basis"][mask],
                            r["cost"][mask], idx[mask])

    backtest = _slice(pre)
    forward = _slice(fwd)

    # recommended-book forward equity: f* carry + (1-f*) cash
    cash_w = (1.0 + _CASH_ANNUAL) ** (1.0 / _WEEKS_PER_YEAR) - 1.0
    fwd_carry = r["net"][fwd]
    book_weekly = _RECOMMENDED_CARRY_FRACTION * np.nan_to_num(fwd_carry) + (1.0 - _RECOMMENDED_CARRY_FRACTION) * cash_w
    book_eq = float(np.cumprod(1.0 + book_weekly)[-1] - 1.0) if book_weekly.size else 0.0

    return {
        "go_live_anchor": _GO_LIVE_DATE,
        "backtest_reference": backtest,
        "forward_evidence": forward,
        "recommended_book_forward": {
            "carry_fraction": _RECOMMENDED_CARRY_FRACTION, "cash_rate": _CASH_ANNUAL,
            "n_weeks": int(book_weekly.size),
            "cumulative_return": round(book_eq, 5),
        },
        "data_through": idx[-1].date().isoformat(),
    }


# ==========================================================================
# Forward vs backtest comparison + verdict
# ==========================================================================
_VALID_VERDICTS = ("FORWARD_EVIDENCE_INSUFFICIENT", "FORWARD_EVIDENCE_TRACKING",
                   "FORWARD_EVIDENCE_DIVERGING", "FORWARD_EVIDENCE_CONFIRMING")


def classify_forward(ledger: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    bt = ledger["backtest_reference"]
    fw = ledger["forward_evidence"]
    nfw = fw.get("n_weeks", 0)
    if fw.get("state") != "OK" or nfw < _MIN_FORWARD_WEEKS_TO_ASSESS:
        return ("FORWARD_EVIDENCE_INSUFFICIENT",
                f"Only {nfw} forward week(s) since the {_GO_LIVE_DATE} go-live anchor; need "
                f"{_MIN_FORWARD_WEEKS_TO_ASSESS} before an assessment. Re-run weekly (with --refresh) "
                f"to accumulate evidence.", {"forward_weeks": nfw})

    bt_funding = bt.get("ann_funding") or 0.0
    fw_funding = fw.get("ann_funding") or 0.0
    fw_sharpe = fw.get("sharpe")
    funding_ratio = (fw_funding / bt_funding) if bt_funding > 0 else 0.0
    comp = {"forward_weeks": nfw, "backtest_ann_funding": bt_funding, "forward_ann_funding": fw_funding,
            "funding_ratio_fwd_over_bt": round(funding_ratio, 3),
            "backtest_sharpe": bt.get("sharpe"), "forward_sharpe": fw_sharpe,
            "forward_ann_basis": fw.get("ann_basis"), "forward_ann_return": fw.get("ann_return")}

    if funding_ratio < _DIVERGING_FUNDING_FLOOR or (fw_sharpe is not None and fw_sharpe < _DIVERGING_SHARPE):
        return ("FORWARD_EVIDENCE_DIVERGING",
                f"Forward funding is {funding_ratio:.0%} of the backtest level"
                + (f" and forward Sharpe {fw_sharpe} is negative" if (fw_sharpe is not None and fw_sharpe < 0) else "")
                + f" over {nfw} weeks -- the edge is not showing up out-of-sample. Do not deploy; "
                  f"re-examine the carry thesis.", comp)

    tracking = (funding_ratio >= (1.0 - _FUNDING_TRACKING_BAND)
                and fw_sharpe is not None and fw_sharpe >= _SHARPE_TRACKING_FLOOR)
    if tracking and nfw >= _MIN_FORWARD_WEEKS_TO_CONFIRM:
        return ("FORWARD_EVIDENCE_CONFIRMING",
                f"Over {nfw} forward weeks the carry has held up: forward annualised funding "
                f"{fw_funding:.1%} ({funding_ratio:.0%} of backtest), forward Sharpe {fw_sharpe}. The "
                f"Phase-97 edge is being confirmed in real time.", comp)
    if tracking:
        return ("FORWARD_EVIDENCE_TRACKING",
                f"Over {nfw} forward weeks the carry is tracking the backtest: forward annualised "
                f"funding {fw_funding:.1%} ({funding_ratio:.0%} of backtest), forward Sharpe "
                f"{fw_sharpe}. Continue accumulating to {_MIN_FORWARD_WEEKS_TO_CONFIRM} weeks.", comp)
    return ("FORWARD_EVIDENCE_TRACKING",
            f"Over {nfw} forward weeks the carry is positive but soft: forward annualised funding "
            f"{fw_funding:.1%} ({funding_ratio:.0%} of backtest), forward Sharpe {fw_sharpe}. Not "
            f"diverging, but below the comfortable tracking band -- watch closely.", comp)


# ==========================================================================
# Immutable snapshot ledger
# ==========================================================================
_SNAPSHOT_HISTORY_CAP = 200


def append_snapshot(ledger: Dict[str, Any], verdict: str, comparison: Dict[str, Any]) -> str:
    """Write an immutable per-run snapshot artifact (keyed by capture time,
    never overwritten) and return its key. The running index of snapshots
    is kept inside the main Phase-98 artifact by ``run()``."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {"schema_version": SCHEMA_VERSION, "captured_at": now, "go_live_anchor": _GO_LIVE_DATE,
               "verdict": verdict, "comparison": comparison,
               "forward_evidence": ledger["forward_evidence"],
               "recommended_book_forward": ledger["recommended_book_forward"],
               "data_through": ledger["data_through"], "git_commit": _git_commit()}
    key = _SNAPSHOT_PREFIX + now.replace(":", "").replace("-", "").replace(".", "").replace("+", "_")
    store.save_artifact(key, "phase98_forward_snapshot", payload)
    return key


def load_snapshot(key: str) -> Optional[Dict[str, Any]]:
    art = store.load_artifact(key)
    return art["payload"] if art else None


def _prior_history() -> List[Dict[str, Any]]:
    prev = get_result()
    hist = (prev or {}).get("snapshot_history") or []
    return [h for h in hist if isinstance(h, dict)]


# ==========================================================================
# Result container
# ==========================================================================
@dataclass
class Phase98Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    design_note: Dict[str, Any]
    refresh: Dict[str, Any]
    ledger: Dict[str, Any]
    verdict: str
    verdict_reason: str
    comparison: Dict[str, Any]
    snapshot_key: str
    snapshot_history: List[Dict[str, Any]]
    determinism: Dict[str, Any]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True
    live_automation_enabled: bool = False
    live_broker_transmission: str = "BLOCKED"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def run(do_refresh: bool = False) -> Phase98Result:
    t0 = datetime.now(timezone.utc)
    refresh = refresh_data() if do_refresh else {"skipped": True}
    ledger = compute_ledger()
    verdict, reason, comparison = classify_forward(ledger)
    snap_key = append_snapshot(ledger, verdict, comparison)
    history = _prior_history()
    history.append({"snapshot_key": snap_key, "captured_at": t0.isoformat(), "verdict": verdict,
                    "forward_weeks": comparison.get("forward_weeks"),
                    "data_through": ledger["data_through"]})
    history = history[-_SNAPSHOT_HISTORY_CAP:]

    l2 = compute_ledger()
    determinism_match = (json.dumps(ledger["forward_evidence"], sort_keys=True, default=str)
                         == json.dumps(l2["forward_evidence"], sort_keys=True, default=str))

    payload = {"ledger": {k: v for k, v in ledger.items()}, "verdict": verdict, "comparison": comparison}
    chash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase98Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=_git_commit(),
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash, design_note=DESIGN_NOTE,
        refresh=refresh, ledger=ledger, verdict=verdict, verdict_reason=reason, comparison=comparison,
        snapshot_key=snap_key, snapshot_history=history, determinism={"match": determinism_match},
        runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase98Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase98_carry_forward_evidence", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    import argparse
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Phase 98 funding-carry forward-evidence harness")
    ap.add_argument("--refresh", action="store_true", help="re-ingest recent crypto data first (idempotent)")
    args = ap.parse_args(_argv)

    print("Phase 98 - funding-carry forward-evidence harness ...", flush=True)
    res = run(do_refresh=args.refresh)
    h = persist(res)
    print(f"\n=== PHASE 98 ({res.runtime_seconds}s) ===")
    print(f"go-live anchor: {_GO_LIVE_DATE}   data through: {res.ledger['data_through']}")
    bt = res.ledger["backtest_reference"]
    fw = res.ledger["forward_evidence"]
    print(f"\nbacktest reference: {bt['n_weeks']} wk  ann funding {bt.get('ann_funding'):+.2%}  "
          f"Sharpe {bt.get('sharpe')}  ann return {bt.get('ann_return'):+.2%}")
    if fw.get("state") == "OK":
        print(f"forward evidence:   {fw['n_weeks']} wk  ann funding {fw.get('ann_funding'):+.2%}  "
              f"Sharpe {fw.get('sharpe')}  ann return {fw.get('ann_return'):+.2%}  "
              f"cum {fw.get('cumulative_return'):+.3%}")
    else:
        print(f"forward evidence:   {fw['n_weeks']} wk (accumulating)")
    rb = res.ledger["recommended_book_forward"]
    print(f"recommended book fwd ({rb['carry_fraction']:.0%} carry + cash): {rb['n_weeks']} wk  "
          f"cum {rb['cumulative_return']:+.3%}")
    print(f"\nVERDICT: {res.verdict}\n  {res.verdict_reason}")
    print(f"\nsnapshot appended: {res.snapshot_key}")
    print(f"snapshot history: {len(res.snapshot_history)} total")
    print(f"determinism match: {res.determinism['match']}")
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "DESIGN_NOTE", "refresh_data", "compute_ledger",
    "classify_forward", "append_snapshot", "load_snapshot", "run", "persist", "get_result", "main",
]
