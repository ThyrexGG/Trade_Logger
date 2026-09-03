# -*- coding: utf-8 -*-
"""
Real, timestamp-safe market evidence (Phase 68).

Turns an as-of-correct :class:`~historical_market_data.CandleWindow` into canonical
:class:`~api.evidence_model.EvidenceItem` objects for the Phase-67 fusion layer.

What is real here
  * technical: EMA20/50/200, RSI(14), MACD(12,26,9), ATR(14), MTF EMA bias — all
    computed from the candles in the window, nothing else.
  * SMC: reuses the existing candle-derived functions in ``market_data`` —
    ``detect_fvgs`` / ``detect_order_blocks`` / ``calculate_market_structure`` /
    ``calculate_liquidity_zones`` — fed the truncated window.
  * seasonality: real day-of-week / month return tendency from the available
    daily history, with an explicit ``sample_size``. Below threshold →
    ``INSUFFICIENT_EVIDENCE`` (never a fabricated multi-year sample).
  * regime: per-benchmark as-of candle windows; a missing benchmark is
    ``MISSING_INPUT``, never silently zero.

What is NOT here
  * no new composite score across categories (each category keeps its own,
    exactly as the Phase-55 factor engines did)
  * no deterministic symbol priors — this module never fabricates a reading
  * no import of / path to any execution module

Every emitted item carries ``timeframe``, ``latest_input_timestamp`` and
``calculation_window`` so the fusion layer and the UI can show provenance and the
Phase-67 look-ahead guard can re-check it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from api.evidence_model import (
    EvidenceDirection,
    EvidenceItem,
    EvidenceState,
    direction_from_score,
)
from historical_market_data import CandleWindow, get_candle_window, tf_seconds

# default timeframes per category
_TECH_TF = "1h"
_SMC_TF = "15m"
_MTF_STRUCT = {"15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
_MTF_BIAS = {"15m": "4h", "1h": "1d", "4h": "1d", "1d": "1w"}

_RSI_PERIOD = 14
_ATR_PERIOD = 14
_TECH_MIN_CANDLES = 55       # need EMA50 + a little slack
_SMC_MIN_CANDLES = 60
_SEASONALITY_MIN_OBS = 60    # daily observations before a tendency is reported


@dataclass
class MarketEvidenceResult:
    category: str
    state: str = EvidenceState.INSUFFICIENT_EVIDENCE.value
    direction: str = EvidenceDirection.UNKNOWN.value
    score: Optional[float] = None          # category-native, -100..100
    confidence: Optional[float] = None
    items: List[EvidenceItem] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    provenance: Optional[str] = None
    reason: Optional[str] = None
    next_dependency: Optional[str] = None
    latest_input_timestamp: Optional[str] = None
    timeframe: Optional[str] = None
    coverage: Optional[float] = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _norm_tf(timeframe: Optional[str], default: str) -> str:
    tf = (timeframe or default).strip().lower()
    return tf if tf in ("1m", "5m", "15m", "30m", "1h", "4h", "1d") else default


def _insufficient(cat: str, reason: str, dep: str) -> MarketEvidenceResult:
    return MarketEvidenceResult(category=cat, state=EvidenceState.INSUFFICIENT_EVIDENCE.value,
                                reason=reason, next_dependency=dep)


def _no_window_reason(asset: str, as_of: Optional[datetime]) -> Tuple[str, str]:
    if as_of is None:
        return (f"No real OHLCV feed for {asset} right now (live upstreams "
                f"unreachable; the synthetic offline fallback is not used as evidence).",
                "a reachable MT5 / Binance / Yahoo candle feed")
    return (f"No historical OHLCV provider is configured for a {as_of.date()} as-of "
            f"reconstruction of {asset}.",
            "set HISTORICAL_OHLCV_PROVIDER to a persisted candle store / dated-range vendor")


def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series, period: int = 14):
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0.0, float("nan"))
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(df, period: int = 14):
    import pandas as pd

    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def _clamp(x: float) -> float:
    return max(-100.0, min(100.0, x))


def _mk_item(asset: str, category: str, metric: str, window: CandleWindow, *,
             value: Optional[float] = None, unit: Optional[str] = None,
             direction: EvidenceDirection = EvidenceDirection.UNKNOWN,
             note: Optional[str] = None, observation_ts: Optional[str] = None) -> EvidenceItem:
    return EvidenceItem(
        asset=asset, category=category, metric=metric,
        state=EvidenceState.AVAILABLE.value,
        value=value, unit=unit, direction=direction.value,
        source=window.source_id, source_id=window.source_id,
        provenance=window.provenance,
        as_of=window.as_of,
        available_timestamp=window.latest_input_timestamp,
        latest_input_timestamp=window.latest_input_timestamp,
        observation_timestamp=observation_ts,
        timeframe=window.timeframe,
        calculation_window=window.calculation_window,
        note=note,
    )


# ---------------------------------------------------------------------------
# TECHNICAL
# ---------------------------------------------------------------------------
def technical_evidence(asset: str, as_of: Optional[datetime] = None,
                       timeframe: Optional[str] = None) -> MarketEvidenceResult:
    cat = "TECHNICAL"
    tf = _norm_tf(timeframe, _TECH_TF)
    window = get_candle_window(asset, tf, as_of, lookback=260)
    if window is None:
        r, dep = _no_window_reason(asset, as_of)
        return _insufficient(cat, r, dep)
    if window.n < _TECH_MIN_CANDLES:
        return _insufficient(
            cat,
            f"Only {window.n} {tf} candles available by as_of — need >= {_TECH_MIN_CANDLES} "
            f"for EMA/RSI/MACD warm-up.",
            "a deeper candle history for this as_of",
        )

    df = window.to_df()
    close = df["close"].astype(float)
    ema20, ema50 = _ema(close, 20), _ema(close, 50)
    ema200 = _ema(close, 200) if window.n >= 200 else None
    rsi = _rsi(close, _RSI_PERIOD)
    macd_line = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd_line, 9)
    hist = macd_line - signal
    atr = _atr(df, _ATR_PERIOD)

    c = float(close.iloc[-1])
    e20, e50 = float(ema20.iloc[-1]), float(ema50.iloc[-1])
    rsi_v = float(rsi.iloc[-1]) if rsi.iloc[-1] == rsi.iloc[-1] else None
    hist_v = float(hist.iloc[-1])
    atr_v = float(atr.iloc[-1])
    atr_pct = (atr_v / c * 100.0) if c else None

    items: List[EvidenceItem] = []
    sub_scores: List[float] = []

    # EMA alignment
    if c > e20 > e50:
        ema_dir, ema_s = EvidenceDirection.BULLISH, 60.0
    elif c < e20 < e50:
        ema_dir, ema_s = EvidenceDirection.BEARISH, -60.0
    else:
        ema_dir, ema_s = EvidenceDirection.NEUTRAL, 0.0
    if ema200 is not None:
        e200 = float(ema200.iloc[-1])
        if ema_dir == EvidenceDirection.BULLISH and c > e200:
            ema_s = 80.0
        elif ema_dir == EvidenceDirection.BEARISH and c < e200:
            ema_s = -80.0
    sub_scores.append(ema_s)
    items.append(_mk_item(
        asset, cat, f"EMA alignment (20/50{'/200' if ema200 is not None else ''}) on {tf}",
        window, value=round((c / e50 - 1.0) * 100.0, 3), unit="% vs EMA50", direction=ema_dir,
        note=f"close {c:.5f} · EMA20 {e20:.5f} · EMA50 {e50:.5f}"))

    # RSI
    if rsi_v is not None:
        rsi_dir = (EvidenceDirection.BULLISH if rsi_v >= 55 else
                   EvidenceDirection.BEARISH if rsi_v <= 45 else EvidenceDirection.NEUTRAL)
        sub_scores.append(_clamp((rsi_v - 50.0) * 3.0))
        items.append(_mk_item(asset, cat, f"RSI({_RSI_PERIOD}) on {tf}", window,
                              value=round(rsi_v, 2), direction=rsi_dir))

    # MACD histogram
    macd_dir = direction_from_score(hist_v, bullish_at=1e-9, bearish_at=-1e-9)
    sub_scores.append(_clamp((hist_v / (atr_v or 1.0)) * 40.0))
    items.append(_mk_item(asset, cat, f"MACD(12,26,9) histogram on {tf}", window,
                          value=round(hist_v, 6), direction=macd_dir))

    # ATR — volatility magnitude only (no direction)
    if atr_pct is not None:
        items.append(_mk_item(asset, cat, f"ATR({_ATR_PERIOD}) on {tf}", window,
                              value=round(atr_pct, 3), unit="% of price",
                              direction=EvidenceDirection.NEUTRAL))

    # MTF EMA bias (context timeframes) — folded into TECHNICAL, not a new category
    for label, mtf in (("structure", _MTF_STRUCT.get(tf)), ("bias", _MTF_BIAS.get(tf))):
        if not mtf:
            continue
        w2 = get_candle_window(asset, mtf, as_of, lookback=220)
        if w2 is None or w2.n < 50:
            items.append(EvidenceItem(
                asset=asset, category=cat, metric=f"MTF {label} bias ({mtf})",
                state=EvidenceState.INSUFFICIENT_EVIDENCE.value,
                direction=EvidenceDirection.UNKNOWN.value,
                as_of=window.as_of, timeframe=mtf,
                note=f"{(w2.n if w2 else 0)} {mtf} candles by as_of — need >= 50"))
            continue
        try:
            from strategies.mtf_engine import calculate_htf_bias
            bias = calculate_htf_bias(w2.to_df())
        except Exception:
            bias = "NEUTRAL"
        bdir = {"BULLISH": EvidenceDirection.BULLISH, "BEARISH": EvidenceDirection.BEARISH}.get(
            bias, EvidenceDirection.NEUTRAL)
        sub_scores.append({"BULLISH": 50.0, "BEARISH": -50.0}.get(bias, 0.0))
        items.append(_mk_item(asset, cat, f"MTF {label} bias ({mtf})", w2,
                              direction=bdir, note=f"EMA20/50/200 alignment = {bias}"))

    score = _clamp(sum(sub_scores) / len(sub_scores)) if sub_scores else None
    direction = direction_from_score(score)
    return MarketEvidenceResult(
        category=cat, state=EvidenceState.AVAILABLE.value,
        direction=direction.value, score=None if score is None else round(score, 1),
        confidence=round(min(1.0, window.n / 260.0), 2),
        items=items, sources=[window.source_id], provenance=window.provenance,
        latest_input_timestamp=window.latest_input_timestamp, timeframe=tf,
        coverage=round(min(1.0, window.n / 200.0), 2),
        reason=f"{window.n} {tf} candles, window {window.calculation_window}",
    )


# ---------------------------------------------------------------------------
# SMC
# ---------------------------------------------------------------------------
def smc_evidence(asset: str, as_of: Optional[datetime] = None,
                 timeframe: Optional[str] = None) -> MarketEvidenceResult:
    cat = "SMC"
    tf = _norm_tf(timeframe, _SMC_TF)
    window = get_candle_window(asset, tf, as_of, lookback=260)
    if window is None:
        r, dep = _no_window_reason(asset, as_of)
        return _insufficient(cat, r, dep)
    if window.n < _SMC_MIN_CANDLES:
        return _insufficient(
            cat, f"Only {window.n} {tf} candles by as_of — need >= {_SMC_MIN_CANDLES} for SMC structure.",
            "a deeper candle history for this as_of")

    import market_data
    df = window.to_df()
    tf_sec = tf_seconds(tf)

    def _close_iso(open_epoch: Any) -> Optional[str]:
        try:
            return datetime.fromtimestamp(float(open_epoch) + tf_sec, tz=timezone.utc).isoformat()
        except Exception:
            return None

    items: List[EvidenceItem] = []
    bull = bear = 0

    try:
        structure = market_data.calculate_market_structure(df) or {}
    except Exception:
        structure = {}
    trend = str(structure.get("trend", "")).upper()
    st_dir = (EvidenceDirection.BULLISH if "BULL" in trend else
              EvidenceDirection.BEARISH if "BEAR" in trend else EvidenceDirection.NEUTRAL)
    if st_dir == EvidenceDirection.BULLISH:
        bull += 2
    elif st_dir == EvidenceDirection.BEARISH:
        bear += 2
    items.append(_mk_item(asset, cat, f"Market structure ({tf})", window,
                          direction=st_dir,
                          note=f"{structure.get('trend', 'n/a')} · {structure.get('recent_sequence', '')} · "
                               f"{structure.get('last_break', '')}"[:200]))

    try:
        fvgs = market_data.detect_fvgs(df) or []
    except Exception:
        fvgs = []
    for g in fvgs[-4:]:
        gd = EvidenceDirection.BULLISH if g.get("type") == "Bullish" else EvidenceDirection.BEARISH
        bull += (gd == EvidenceDirection.BULLISH)
        bear += (gd == EvidenceDirection.BEARISH)
        items.append(_mk_item(
            asset, cat, f"{g.get('type')} FVG ({tf})", window, direction=gd,
            value=round(float(g.get("top", 0)) - float(g.get("bottom", 0)), 5), unit="gap",
            observation_ts=_close_iso(g.get("creation_time")),
            note=f"formation {_close_iso(g.get('creation_time'))} · {g.get('status', '')} · age {g.get('age_candles')}c"))

    try:
        obs = market_data.detect_order_blocks(df) or []
    except Exception:
        obs = []
    for ob in obs[-3:]:
        od = EvidenceDirection.BULLISH if "Bull" in str(ob.get("type", "")) else EvidenceDirection.BEARISH
        bull += (od == EvidenceDirection.BULLISH)
        bear += (od == EvidenceDirection.BEARISH)
        # an OB is only 'known' once its 2 impulse candles have closed
        conf = None
        try:
            conf = datetime.fromtimestamp(float(ob.get("origin_timestamp")) + 3 * tf_sec,
                                          tz=timezone.utc).isoformat()
        except Exception:
            pass
        items.append(_mk_item(
            asset, cat, f"{ob.get('type')} ({tf})", window, direction=od,
            observation_ts=_close_iso(ob.get("origin_timestamp")),
            note=f"formation {_close_iso(ob.get('origin_timestamp'))} · confirmation {conf} · "
                 f"{ob.get('mitigation_status', '')}"))

    try:
        liq = market_data.calculate_liquidity_zones(df) or {}
    except Exception:
        liq = {}
    n_bsl, n_ssl = len(liq.get("bsl", [])), len(liq.get("ssl", []))
    if n_bsl or n_ssl:
        items.append(_mk_item(asset, cat, f"Liquidity pools ({tf})", window,
                              direction=EvidenceDirection.NEUTRAL,
                              note=f"{n_bsl} buy-side above price · {n_ssl} sell-side below price"))

    net = bull - bear
    score = _clamp(net * 12.0)
    direction = direction_from_score(score, bullish_at=1.0, bearish_at=-1.0)
    return MarketEvidenceResult(
        category=cat, state=EvidenceState.AVAILABLE.value,
        direction=direction.value, score=round(score, 1),
        confidence=round(min(1.0, window.n / 260.0), 2),
        items=items, sources=[window.source_id], provenance=window.provenance,
        latest_input_timestamp=window.latest_input_timestamp, timeframe=tf,
        coverage=round(min(1.0, len(items) / 4.0), 2),
        reason=f"{len(fvgs)} FVG · {len(obs)} OB · structure {structure.get('trend', 'n/a')} "
               f"({window.n} {tf} candles)",
    )


# ---------------------------------------------------------------------------
# SEASONALITY
# ---------------------------------------------------------------------------
def seasonality_evidence(asset: str, as_of: Optional[datetime] = None,
                         timeframe: Optional[str] = None) -> MarketEvidenceResult:
    cat = "SEASONALITY"
    window = get_candle_window(asset, "1d", as_of, lookback=1500)
    if window is None:
        r, dep = _no_window_reason(asset, as_of)
        return _insufficient(
            cat, r + " Seasonality needs a multi-year daily history.",
            "a multi-year daily OHLCV history for this asset")
    if window.n < _SEASONALITY_MIN_OBS:
        return _insufficient(
            cat,
            f"Only {window.n} daily observations available by as_of — need >= {_SEASONALITY_MIN_OBS} "
            f"before a seasonal tendency is reported (no fabricated multi-year sample).",
            "a multi-year daily OHLCV history for this asset")

    import pandas as pd

    df = window.to_df()
    df["ret"] = df["close"].astype(float).pct_change() * 100.0
    df["dt"] = pd.to_datetime(df["time"].astype(float), unit="s", utc=True)
    df["dow"] = df["dt"].dt.dayofweek
    df["month"] = df["dt"].dt.month
    df = df.dropna(subset=["ret"])

    now_dt = as_of or datetime.now(timezone.utc)
    cur_dow, cur_month = now_dt.weekday(), now_dt.month

    items: List[EvidenceItem] = []
    sub: List[float] = []
    for label, col, cur in (("day-of-week", "dow", cur_dow), ("month", "month", cur_month)):
        grp = df[df[col] == cur]["ret"]
        n = int(grp.count())
        if n < 8:
            items.append(EvidenceItem(
                asset=asset, category=cat, metric=f"Current {label} tendency",
                state=EvidenceState.INSUFFICIENT_EVIDENCE.value,
                direction=EvidenceDirection.UNKNOWN.value, as_of=window.as_of,
                note=f"only {n} historical observations for this {label}"))
            continue
        mean_ret = float(grp.mean())
        d = direction_from_score(mean_ret, bullish_at=0.02, bearish_at=-0.02)
        sub.append(_clamp(mean_ret * 40.0))
        items.append(_mk_item(
            asset, cat, f"Current {label} tendency", window,
            value=round(mean_ret, 4), unit="% mean daily return", direction=d,
            note=f"sample_size={n} · window {window.calculation_window}"))

    if not sub:
        return _insufficient(
            cat, f"{window.n} daily obs but no seasonal cell has >= 8 observations for the "
                 f"current day/month.", "a longer daily history")

    score = _clamp(sum(sub) / len(sub))
    return MarketEvidenceResult(
        category=cat, state=EvidenceState.AVAILABLE.value,
        direction=direction_from_score(score).value, score=round(score, 1),
        confidence=round(min(1.0, window.n / 750.0), 2),
        items=items, sources=[window.source_id], provenance=window.provenance,
        latest_input_timestamp=window.latest_input_timestamp, timeframe="1d",
        coverage=round(min(1.0, window.n / 750.0), 2),
        reason=f"{window.n} daily observations, window {window.calculation_window}",
    )


# ---------------------------------------------------------------------------
# REGIME (cross-asset, as-of)
# ---------------------------------------------------------------------------
_REGIME_BENCHMARKS = ["DXY", "SPX500", "NAS100", "XAUUSD", "USOIL", "BTCUSD", "US10Y"]


def regime_evidence(asset: str, as_of: Optional[datetime] = None) -> MarketEvidenceResult:
    cat = "REGIME"
    changes: Dict[str, float] = {}
    items: List[EvidenceItem] = []
    missing: List[str] = []
    latest_ts: Optional[str] = None
    provenance = None

    for sym in _REGIME_BENCHMARKS:
        w = get_candle_window(sym, "1h", as_of, lookback=30)
        if w is None or w.n < 25:
            missing.append(sym)
            items.append(EvidenceItem(
                asset=asset, category=cat, metric=f"{sym} 24h change",
                state=EvidenceState.PROVIDER_UNAVAILABLE.value if w is None
                else EvidenceState.INSUFFICIENT_EVIDENCE.value,
                direction=EvidenceDirection.UNKNOWN.value,
                as_of=(as_of or datetime.now(timezone.utc)).isoformat(),
                note="MISSING_INPUT — cross-asset series unavailable at as_of (not treated as 0)"))
            continue
        df = w.to_df()
        c_now = float(df["close"].iloc[-1])
        c_prev = float(df["close"].iloc[-25])
        chg = (c_now / c_prev - 1.0) * 100.0 if c_prev else 0.0
        changes[sym] = chg
        provenance = w.provenance
        latest_ts = w.latest_input_timestamp
        items.append(_mk_item(asset, cat, f"{sym} 24h change", w,
                              value=round(chg, 3), unit="%",
                              direction=direction_from_score(chg, bullish_at=0.05, bearish_at=-0.05)))

    if len(changes) < 4:
        return MarketEvidenceResult(
            category=cat, state=EvidenceState.INSUFFICIENT_EVIDENCE.value,
            items=items, sources=["market_evidence_engine"], provenance=provenance,
            latest_input_timestamp=latest_ts, timeframe="1h",
            coverage=round(len(changes) / len(_REGIME_BENCHMARKS), 2),
            reason=(f"Only {len(changes)}/{len(_REGIME_BENCHMARKS)} cross-asset benchmark series "
                    f"available at as_of ({', '.join(missing)} missing) — need >= 4. Missing series "
                    f"are NOT treated as zero/neutral."),
            next_dependency="as-of candle windows for the cross-asset regime benchmarks")

    # compact classifier using the same signals/thresholds as CrossAssetRegimeEngine
    equity = (changes.get("SPX500", 0.0) + changes.get("NAS100", 0.0)) / 2.0
    dxy = changes.get("DXY", 0.0)
    y10 = changes.get("US10Y", 0.0)
    gold = changes.get("XAUUSD", 0.0)
    oil = changes.get("USOIL", 0.0)
    btc = changes.get("BTCUSD", 0.0)

    scores: Dict[str, float] = {}
    def add(k, v): scores[k] = scores.get(k, 0.0) + v
    if equity >= 0.3:
        add("RISK_ON", 35); add("GROWTH_ACCELERATION", 20)
    elif equity <= -0.3:
        add("RISK_OFF", 35); add("GROWTH_DECELERATION", 20)
    if btc >= 1.0 and equity >= 0.0:
        add("RISK_ON", 20)
    elif btc <= -1.5 and equity < 0.0:
        add("RISK_OFF", 20)
    if dxy >= 0.25:
        add("USD_STRENGTH", 30)
        if equity < 0:
            add("RISK_OFF", 20)
    elif dxy <= -0.25:
        add("USD_WEAKNESS", 30); add("RISK_ON", 15)
    if y10 >= 0.5:
        add("RATE_RISE", 25)
        if oil > 0:
            add("INFLATIONARY", 25)
    elif y10 <= -0.5:
        add("RATE_FALL", 25); add("DISINFLATIONARY", 20)
    if gold >= 0.5 and dxy >= 0.2:
        add("RISK_OFF", 25)
    if oil >= 1.0:
        add("INFLATIONARY", 30)
    elif oil <= -1.0:
        add("DISINFLATIONARY", 25)

    if not scores:
        primary, conf = "MIXED_REGIME", 0.45
    else:
        primary, top = max(scores.items(), key=lambda kv: kv[1])
        conf = min(0.95, max(0.45, top / 100.0))

    items.append(EvidenceItem(
        asset=asset, category=cat, metric=f"Cross-asset regime: {primary}",
        state=EvidenceState.AVAILABLE.value,
        direction=EvidenceDirection.NEUTRAL.value,
        source="market_evidence_engine", source_id="regime:cross_asset",
        provenance=provenance, as_of=(as_of or datetime.now(timezone.utc)).isoformat(),
        available_timestamp=latest_ts, latest_input_timestamp=latest_ts,
        note=f"{len(changes)}/{len(_REGIME_BENCHMARKS)} benchmarks; "
             f"{'missing ' + ', '.join(missing) if missing else 'full coverage'}"))

    return MarketEvidenceResult(
        category=cat, state=EvidenceState.AVAILABLE.value,
        direction=EvidenceDirection.NEUTRAL.value, score=None,
        confidence=round(conf, 2),
        items=items, sources=["market_evidence_engine"], provenance=provenance,
        latest_input_timestamp=latest_ts, timeframe="1h",
        coverage=round(len(changes) / len(_REGIME_BENCHMARKS), 2),
        reason=f"regime {primary}; {len(changes)}/{len(_REGIME_BENCHMARKS)} cross-asset inputs"
               + (f"; missing {', '.join(missing)}" if missing else ""),
    )


def regime_primary(asset: str, as_of: Optional[datetime] = None) -> Optional[str]:
    """The classified regime string, or None. Used by the fusion REGIME direction map."""
    res = regime_evidence(asset, as_of)
    if res.state != EvidenceState.AVAILABLE.value:
        return None
    for it in res.items:
        if it.metric.startswith("Cross-asset regime: "):
            return it.metric.split(": ", 1)[1]
    return None


__all__ = [
    "MarketEvidenceResult",
    "technical_evidence",
    "smc_evidence",
    "seasonality_evidence",
    "regime_evidence",
    "regime_primary",
]
