# -*- coding: utf-8 -*-
"""
Trade Setup Engine (Phase 72).

Separate from the research engine. Research answers *what historically has an
edge*; this answers *does the current market satisfy that validated edge right
now*.

Hard rule (§72): a setup can only be ``READY`` if a **VALIDATED** strategy exists
for the instrument AND every mandatory condition passes AND entry/SL/TP are
objectively derivable AND no required evidence is stale AND the current regime is
compatible AND MTF timing is valid. Otherwise: ``NO_SETUP`` / ``WATCH`` /
``SETUP_FORMING`` / ``INVALIDATED`` / ``STALE`` / ``INSUFFICIENT_EVIDENCE``.

Phases 70/71 found **no validated strategy** on the available (1h/1d) data, so in
the current repository every instrument honestly returns ``NO_SETUP`` with the
reason named. The machinery is real and lights up when the evidence improves.

Read-only. No import of / path to any execution / broker / risk-gateway module.
The deterministic engine owns the state — AI may explain it but never change it.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import research_universe

# ==========================================================================
# States (§37)
# ==========================================================================
class SetupState(str, Enum):
    NO_SETUP = "NO_SETUP"
    WATCH = "WATCH"
    SETUP_FORMING = "SETUP_FORMING"
    READY = "READY"
    INVALIDATED = "INVALIDATED"
    STALE = "STALE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


# Which market regimes each validated strategy family tolerates.
_REGIME_COMPAT: Dict[str, set] = {
    "LIQUIDITY_SWEEP + MSS + FVG": {"TRENDING", "HIGH_VOLATILITY"},
    "LIQUIDITY_SWEEP reversal": {"RANGING", "HIGH_VOLATILITY"},
    "HTF bias + BOS + FVG continuation": {"TRENDING"},
    "EMA trend pullback": {"TRENDING"},
    "RSI mean reversion": {"RANGING", "LOW_VOLATILITY"},
}

_LONDON = range(7, 12)
_OVERLAP = range(12, 16)
_NY = range(16, 21)


# ==========================================================================
# Validated-strategy resolver (§36) — injectable for tests
# ==========================================================================
@dataclass(frozen=True)
class ValidatedStrategy:
    strategy_id: str
    strategy_version: str
    family: str
    timeframe_stack: str
    sessions: List[str]
    oos_metrics: Dict[str, Any]
    bootstrap_ci: Dict[str, Any]
    wfo_stability: Optional[float]
    source: str                     # "pair_ranking" | "gold_revalidation" | "test"


ValidatedResolver = Callable[[str], Optional[ValidatedStrategy]]
_LOCK = threading.Lock()
_TEST_RESOLVER: Optional[ValidatedResolver] = None


def set_test_resolver(fn: Optional[ValidatedResolver]) -> None:
    """Test hook — inject a validated strategy so the READY path is exercisable
    while the real pipeline has none."""
    global _TEST_RESOLVER
    with _LOCK:
        _TEST_RESOLVER = fn


def _default_resolver(asset: str) -> Optional[ValidatedStrategy]:
    """A strategy is VALIDATED for an asset when the persisted research artifacts
    say so by their own objective rules:
      * pair_ranking leaderboard entry with scorecard == "STRONG"
      * gold_revalidation edge_status == "VALIDATED" (XAUUSD only)
    """
    asset = research_universe.normalise(asset)

    if asset == "XAUUSD":
        try:
            import gold_revalidation
            rv = gold_revalidation.get_revalidation()
            if rv and rv.get("edge_status") == "VALIDATED":
                h1 = (rv.get("per_timeframe") or {}).get("1h", {})
                return ValidatedStrategy(
                    strategy_id=rv.get("strategy_id", "ict_2022_sweep_mss_fvg"),
                    strategy_version="phase71-revalidated",
                    family="LIQUIDITY_SWEEP + MSS + FVG",
                    timeframe_stack="1d bias -> 4h -> 1h",
                    sessions=["LONDON", "LONDON_NY_OVERLAP"],
                    oos_metrics=h1.get("oos_metrics", {}),
                    bootstrap_ci=h1.get("bootstrap_ci", {}),
                    wfo_stability=(rv.get("walk_forward") or {}).get("stability"),
                    source="gold_revalidation",
                )
        except Exception:
            pass

    try:
        import pair_ranking
        import strategy_discovery
        ranking = pair_ranking.get_pair_ranking()
        if ranking:
            for c in ranking.get("candidates", []):
                if c.get("asset") != asset:
                    continue
                if (c.get("scorecard") or {}).get("status") != "STRONG":
                    continue
                sdef = strategy_discovery.get_strategy_definition(c["strategy_id"])
                return ValidatedStrategy(
                    strategy_id=c["strategy_id"],
                    strategy_version=sdef.version if sdef else "?",
                    family=c.get("strategy_family", sdef.family if sdef else ""),
                    timeframe_stack="1d bias -> 4h -> 1h",
                    sessions=["LONDON", "LONDON_NY_OVERLAP", "NEW_YORK"],
                    oos_metrics=c.get("oos_metrics", {}),
                    bootstrap_ci=c.get("bootstrap_ci", {}),
                    wfo_stability=(c.get("walk_forward") or {}).get("stability"),
                    source="pair_ranking",
                )
    except Exception:
        pass
    return None


def _resolve_validated(asset: str) -> Optional[ValidatedStrategy]:
    with _LOCK:
        r = _TEST_RESOLVER
    return (r or _default_resolver)(asset)


# ==========================================================================
# Setup model
# ==========================================================================
@dataclass
class SetupCondition:
    name: str
    mandatory: bool
    passed: Optional[bool]           # None = could not evaluate
    detail: str
    evidence_ref: Optional[str] = None   # points at an evidence category / item

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class TradeSetup:
    asset: str
    state: str
    as_of: str
    generated_at: str
    mode: str                        # "live" | "historical"
    reason: str
    direction: Optional[str] = None
    strategy_id: Optional[str] = None
    strategy_version: Optional[str] = None
    strategy_family: Optional[str] = None
    timeframe_stack: Optional[str] = None
    session: Optional[str] = None
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    failing_conditions: List[str] = field(default_factory=list)
    waiting_for: Optional[str] = None
    strategy_validation: Dict[str, Any] = field(default_factory=dict)
    evidence_provenance: List[str] = field(default_factory=list)
    safety_barrier: Dict[str, Any] = field(default_factory=lambda: {
        "live_automation_enabled": False, "live_broker_transmission": "BLOCKED"})

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


# ==========================================================================
# Evaluation
# ==========================================================================
def _session_now(dt: datetime) -> str:
    h = dt.astimezone(timezone.utc).hour
    if h in _OVERLAP:
        return "LONDON_NY_OVERLAP"
    if h in _LONDON:
        return "LONDON"
    if h in _NY:
        return "NEW_YORK"
    return "ASIA"


def _cat(snap_d: Dict[str, Any], name: str) -> Dict[str, Any]:
    for c in snap_d.get("categories", []):
        if c.get("category") == name:
            return c
    return {}


def evaluate_setup(asset: str, as_of: Optional[datetime] = None) -> TradeSetup:
    asset = research_universe.normalise(asset)
    live = as_of is None
    now = datetime.now(timezone.utc)
    eff = as_of or now
    if eff.tzinfo is None:
        eff = eff.replace(tzinfo=timezone.utc)

    base = TradeSetup(
        asset=asset, state=SetupState.NO_SETUP.value,
        as_of=eff.isoformat(), generated_at=now.isoformat(),
        mode="live" if live else "historical", reason="",
    )

    if not research_universe.is_in_universe(asset):
        base.reason = f"{asset} is not in the research universe"
        return base

    vs = _resolve_validated(asset)
    if vs is None:
        base.reason = (
            f"No validated strategy for {asset}. Phase 70/71 discovery found no "
            f"strategy clearing positive OOS lower-CI + N>=50 + WFO stability on the "
            f"available 1h/1d data. A Trade Setup can only be READY behind a "
            f"VALIDATED strategy (setup rule 72)."
        )
        base.strategy_validation = {"validated_strategy": None, "state": "NONE"}
        return base

    base.strategy_id = vs.strategy_id
    base.strategy_version = vs.strategy_version
    base.strategy_family = vs.family
    base.timeframe_stack = vs.timeframe_stack
    base.strategy_validation = {
        "validated_strategy": vs.strategy_id, "source": vs.source,
        "oos_expectancy_r": vs.oos_metrics.get("expectancy_r"),
        "oos_profit_factor": vs.oos_metrics.get("profit_factor"),
        "oos_win_rate_pct": vs.oos_metrics.get("win_rate_pct"),
        "oos_trades": vs.oos_metrics.get("total_trades"),
        "oos_ci": vs.bootstrap_ci.get("ci_range_str"),
        "wfo_stability": vs.wfo_stability,
    }

    # --- current market evidence (Phase 67) --------------------------------
    try:
        from api import evidence_fusion
        snap = evidence_fusion.get_asset_intelligence(asset, as_of=as_of)
        snap_d = snap.to_dict()
    except Exception as e:  # pragma: no cover - defensive
        base.state = SetupState.INSUFFICIENT_EVIDENCE.value
        base.reason = f"evidence layer unavailable: {e!r}"
        return base

    base.evidence_provenance = [p.get("source", "") for p in snap_d.get("provenance", [])][:5]
    tech = _cat(snap_d, "TECHNICAL")
    smc = _cat(snap_d, "SMC")
    regime = _cat(snap_d, "REGIME")
    session = _session_now(eff)
    base.session = session

    conds: List[SetupCondition] = []

    # 1. HTF bias decisive
    htf_dir = tech.get("direction")
    htf_ok = tech.get("state") == "AVAILABLE" and htf_dir in ("BULLISH", "BEARISH")
    conds.append(SetupCondition(
        "HTF bias decisive", True, htf_ok,
        f"TECHNICAL {tech.get('state')} / direction {htf_dir}", "TECHNICAL"))
    direction = {"BULLISH": "LONG", "BEARISH": "SHORT"}.get(htf_dir)

    # 2. Regime compatible
    reg_name = None
    for it in regime.get("evidence", []):
        if str(it.get("metric", "")).lower().startswith("regime"):
            reg_name = str(it.get("value") or it.get("note") or "").upper()
            break
    compat = _REGIME_COMPAT.get(vs.family, set())
    reg_ok = (regime.get("state") == "AVAILABLE"
              and (not compat or any(r in (reg_name or "") for r in compat)))
    conds.append(SetupCondition(
        "Regime compatible", True, reg_ok if regime.get("state") == "AVAILABLE" else None,
        f"REGIME {regime.get('state')} ({reg_name or 'n/a'}); strategy tolerates {sorted(compat) or 'any'}",
        "REGIME"))

    # 3. MTF alignment — SMC direction agrees with HTF bias
    smc_dir = smc.get("direction")
    mtf_ok = (smc.get("state") == "AVAILABLE" and smc_dir in ("BULLISH", "BEARISH")
              and smc_dir == htf_dir)
    conds.append(SetupCondition(
        "MTF alignment (SMC agrees with HTF)", True,
        mtf_ok if smc.get("state") == "AVAILABLE" else None,
        f"SMC {smc.get('state')} / direction {smc_dir} vs HTF {htf_dir}", "SMC"))

    # 4. SMC trigger present (sweep / MSS / FVG)
    smc_items = [str(it.get("metric", "")) for it in smc.get("evidence", [])]
    has_trigger = any(k in " ".join(smc_items).lower()
                      for k in ("sweep", "mss", "structure shift", "fvg", "order block"))
    trig_ok = smc.get("state") == "AVAILABLE" and has_trigger and smc_dir in ("BULLISH", "BEARISH")
    conds.append(SetupCondition(
        "SMC trigger present", True,
        trig_ok if smc.get("state") == "AVAILABLE" else None,
        f"SMC items: {', '.join(smc_items[:4]) or 'none'}", "SMC"))

    # 5. Session permitted
    sess_ok = session in vs.sessions
    conds.append(SetupCondition(
        "Session permitted", True, sess_ok,
        f"current {session}; strategy trades {vs.sessions}"))

    # 6. Evidence not stale
    stale = [c.get("category") for c in snap_d.get("categories", [])
             if c.get("freshness") == "STALE"]
    fresh_ok = not stale
    conds.append(SetupCondition(
        "Evidence fresh", True, fresh_ok,
        f"stale categories: {stale or 'none'}"))

    base.conditions = [c.to_dict() for c in conds]
    mandatory = [c for c in conds if c.mandatory]
    failed = [c for c in mandatory if c.passed is False]
    unknown = [c for c in mandatory if c.passed is None]
    base.failing_conditions = [c.name for c in failed]

    # --- state machine ---------------------------------------------------
    if stale:
        base.state = SetupState.STALE.value
        base.reason = f"required evidence is stale: {', '.join(stale)}"
        base.waiting_for = "fresh evidence"
        return base

    if unknown and not failed:
        base.state = SetupState.INSUFFICIENT_EVIDENCE.value
        base.reason = "cannot evaluate: " + ", ".join(c.name for c in unknown)
        base.waiting_for = unknown[0].name
        return base

    # a direct contradiction (bias/SMC opposed, or regime incompatible) invalidates
    contradiction = (
        (htf_dir in ("BULLISH", "BEARISH") and smc_dir in ("BULLISH", "BEARISH")
         and smc_dir != htf_dir)
        or (regime.get("state") == "AVAILABLE" and reg_ok is False)
    )

    if not failed:
        # every mandatory condition passed
        entry, sl, tp, rr = _derive_levels(asset, direction, vs, as_of)
        if entry is None:
            base.state = SetupState.SETUP_FORMING.value
            base.reason = "all conditions pass but entry/SL/TP not objectively derivable yet"
            base.waiting_for = "price to reach a defined entry zone"
        else:
            base.state = SetupState.READY.value
            base.direction = direction
            base.entry, base.stop_loss, base.take_profit, base.risk_reward = entry, sl, tp, rr
            base.reason = f"{len(mandatory)}/{len(mandatory)} mandatory conditions satisfied"
        return base

    if contradiction and len(failed) >= 2:
        base.state = SetupState.INVALIDATED.value
        base.reason = "current structure contradicts the validated strategy: " + \
                      ", ".join(c.name for c in failed)
        base.waiting_for = failed[0].name
        return base

    # partial: some pass, some fail
    passed_names = {c.name for c in mandatory if c.passed}
    if "HTF bias decisive" in passed_names and "Regime compatible" in passed_names:
        base.state = SetupState.SETUP_FORMING.value
    elif "HTF bias decisive" in passed_names:
        base.state = SetupState.WATCH.value
    else:
        base.state = SetupState.NO_SETUP.value
    base.direction = direction
    base.waiting_for = failed[0].name
    base.reason = "waiting for: " + ", ".join(c.name for c in failed)
    return base


def _derive_levels(asset: str, direction: Optional[str], vs: ValidatedStrategy,
                   as_of: Optional[datetime]):
    """Objectively derive entry / SL / TP from the current candle window using the
    validated strategy's stop/target model. Returns (entry, sl, tp, rr) or all
    None when a window cannot be resolved (never a fabricated level)."""
    if direction not in ("LONG", "SHORT"):
        return None, None, None, None
    try:
        import historical_market_data as hmd
        win = hmd.get_candle_window(asset, "1h", as_of=as_of, lookback=60)
    except Exception:
        win = None
    if win is None or win.n < 20:
        return None, None, None, None

    closes = [c["close"] for c in win.candles]
    highs = [c["high"] for c in win.candles]
    lows = [c["low"] for c in win.candles]
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
           for i in range(1, len(closes))]
    atr = sum(trs[-14:]) / min(14, len(trs)) if trs else 0.0
    if atr <= 0:
        return None, None, None, None

    entry = round(closes[-1], 5)
    sl_dist = 1.5 * atr
    tp_dist = 2.5 * atr
    if direction == "LONG":
        sl = round(entry - sl_dist, 5)
        tp = round(entry + tp_dist, 5)
    else:
        sl = round(entry + sl_dist, 5)
        tp = round(entry - tp_dist, 5)
    rr = round(tp_dist / sl_dist, 2)
    return entry, sl, tp, rr


def ai_setup_summary(asset: str) -> Dict[str, Any]:
    """Compact, bounded summary for the AI context. AI may explain this; it can
    never change the state."""
    s = evaluate_setup(asset)
    return {
        "asset": s.asset, "state": s.state, "direction": s.direction,
        "strategy": s.strategy_id, "reason": s.reason[:240],
        "waiting_for": s.waiting_for,
        "note": "deterministic engine owns this state; do not override it",
    }


__all__ = [
    "SetupState", "ValidatedStrategy", "set_test_resolver", "SetupCondition",
    "TradeSetup", "evaluate_setup", "ai_setup_summary",
]
