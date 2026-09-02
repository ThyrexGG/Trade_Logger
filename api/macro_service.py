# -*- coding: utf-8 -*-
"""
Macro Intelligence service layer (Stage 18 B–F).

Read-only orchestration over the authoritative deterministic engines in
`macro_intelligence_engine.py` (surprise / factor-group / economic-strength /
FX relative-strength / gold macro model) plus the Stage 18A provider. No formula
is reimplemented here; this module filters, shapes and — critically — tags every
response with data provenance so seeded/demo data is never presented as real.

There is no import of / path to execution_pipeline, broker_adapter, risk_gateway
or any order path. Everything is GET-shaped and pure.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from api.macro_provider import SUPPORTED_CURRENCIES, get_provider

# Assets with a macro-context view. XAUUSD uses the dedicated engine model;
# the others use a transparent generic driver rollup.
SUPPORTED_ASSETS = ["XAUUSD", "XAGUSD", "USOIL", "SPX500", "NAS100"]
_ASSET_LABEL = {
    "XAUUSD": "Gold", "XAGUSD": "Silver", "USOIL": "Crude Oil",
    "SPX500": "S&P 500", "NAS100": "Nasdaq 100",
}
_FX_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
             "GBPJPY", "EURJPY", "EURGBP"]

_MODEL_DISCLAIMER = (
    "CONTEXTUAL MACRO INTELLIGENCE ONLY — not an entry signal, not predictive, "
    "not an execution instruction. Trading decisions remain the user's responsibility."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_meta() -> Dict[str, Any]:
    p = get_provider()
    return {
        "data_provider": p.name,
        "provider_is_live": bool(p.is_live),
        "provenance": "live" if p.is_live else ("unavailable" if p.name == "none" else "seed_demo"),
    }


# --- events ------------------------------------------------------------
def get_events(
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    window: str = "all",
    country: Optional[str] = None,
    currency: Optional[str] = None,
    impact: Optional[str] = None,
    indicator: Optional[str] = None,
    limit: int = 200,
) -> Dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    if window == "upcoming":
        s, e = today, today + timedelta(days=14)
    elif window == "recent":
        s, e = today - timedelta(days=30), today
    else:
        s = _pdate(start) or (today - timedelta(days=30))
        e = _pdate(end) or (today + timedelta(days=14))

    events = get_provider().get_events(s, e)

    cf = (currency or "").upper().strip()
    co = (country or "").upper().strip()
    im = (impact or "").upper().strip()
    ind = (indicator or "").upper().strip()
    now_iso = _now()

    rows: List[Dict[str, Any]] = []
    for ev in events:
        if cf and (ev.get("currency") or "").upper() != cf:
            continue
        if co and co not in (ev.get("country") or "").upper():
            continue
        if im and (ev.get("impact") or "").upper() != im:
            continue
        if ind and ind not in (ev.get("indicator") or "").upper() and ind not in (ev.get("event") or "").upper():
            continue
        if window == "upcoming" and (ev.get("timestamp") or "") < now_iso and ev.get("actual") is not None:
            continue
        if window == "recent" and ev.get("actual") is None:
            continue
        rows.append({**ev, "surprise": _surprise_lite(ev)})

    rows.sort(key=lambda r: r.get("timestamp") or "")
    truncated = len(rows) > limit
    return {
        **_provider_meta(),
        "available": len(rows) > 0,
        "window": window,
        "range": {"start": s.isoformat(), "end": e.isoformat()},
        "filters_applied": {k: v for k, v in
                            {"country": country, "currency": currency, "impact": impact, "indicator": indicator}.items()
                            if v},
        "count": min(len(rows), limit),
        "total_matched": len(rows),
        "truncated": truncated,
        "events": rows[:limit],
        "disclaimer": _MODEL_DISCLAIMER,
        "timestamp": now_iso,
    }


def _pdate(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    return datetime.strptime(raw.strip(), "%Y-%m-%d").date()


def _surprise_lite(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Attach the Stage 18B surprise verdict to a calendar row (or 'UNAVAILABLE')."""
    from api.surprise_engine import evaluate_surprise
    return evaluate_surprise(
        indicator=ev.get("indicator") or ev.get("event") or "",
        actual=ev.get("actual"), forecast=ev.get("forecast"), previous=ev.get("previous"),
        unit=ev.get("unit"),
    )


# --- surprises -------------------------------------------------------
def get_surprises(*, currency: Optional[str] = None, limit: int = 60) -> Dict[str, Any]:
    ev = get_events(window="recent", currency=currency, limit=max(limit, 60))
    scored = [
        {
            "event": r["event"], "indicator": r.get("indicator"), "currency": r.get("currency"),
            "country": r.get("country"), "timestamp": r["timestamp"], "impact": r["impact"],
            "actual": r["actual"], "forecast": r["forecast"], "previous": r["previous"],
            "unit": r.get("unit"), "source": r.get("source"), "provenance": r["provenance"],
            **r["surprise"],
        }
        for r in ev["events"]
        if r["surprise"]["state"] not in ("UNAVAILABLE",)
    ]
    scored.sort(key=lambda s: (abs(s.get("normalized_surprise") or 0.0), s["timestamp"]), reverse=True)
    pos = sum(1 for s in scored if s["direction_bias"] == "POSITIVE")
    neg = sum(1 for s in scored if s["direction_bias"] == "NEGATIVE")
    return {
        **_provider_meta(),
        "available": len(scored) > 0,
        "count": len(scored[:limit]),
        "positive": pos, "negative": neg, "neutral": len(scored) - pos - neg,
        "surprises": scored[:limit],
        "disclaimer": _MODEL_DISCLAIMER,
        "timestamp": _now(),
    }


# --- currencies -----------------------------------------------------
def _currency_has_data(ccy: str) -> bool:
    try:
        from macro_intelligence_engine import EconomicDataRegistry
        return len(EconomicDataRegistry.get_releases_as_of(country=ccy)) > 0
    except Exception:
        return False


def get_currency(ccy: str) -> Dict[str, Any]:
    ccy = ccy.upper().strip()
    meta = _provider_meta()
    if ccy not in SUPPORTED_CURRENCIES:
        return {**meta, "currency": ccy, "available": False, "state": "UNSUPPORTED",
                "reason": f"Supported: {', '.join(SUPPORTED_CURRENCIES)}", "timestamp": _now()}
    if not _currency_has_data(ccy):
        return {**meta, "currency": ccy, "available": False, "state": "INSUFFICIENT_EVIDENCE",
                "reason": f"No economic releases for {ccy} from provider '{meta['data_provider']}'.",
                "score": None, "confidence": None, "direction": "INSUFFICIENT_EVIDENCE",
                "supporting_events": [], "timestamp": _now()}

    from macro_intelligence_engine import EconomicStrengthEngine, EconomicSurpriseEngine
    es = EconomicStrengthEngine.evaluate_economic_strength(ccy)
    surp = EconomicSurpriseEngine.evaluate_country_surprises(ccy)
    score = round(float(es["economic_strength_score"]), 1)
    direction = "BULLISH" if score >= 15 else "BEARISH" if score <= -15 else (
        "MIXED" if surp.get("positive_count") and surp.get("negative_count") else "NEUTRAL")
    groups = {
        name: {"score": round(float(g.get("score", 0.0)), 1), "direction": g.get("direction"),
               "confidence": g.get("confidence"),
               "supporting": g.get("supporting_metrics", [])[:4],
               "conflicting": g.get("conflicting_metrics", [])[:3]}
        for name, g in (es.get("factor_groups") or {}).items()
    }
    return {
        **meta,
        "currency": ccy, "available": True, "state": "OK",
        "score": score,
        "classification": es.get("classification"),
        "confidence": int(es.get("data_quality", 0)),
        "direction": direction,
        "surprise_score": surp.get("surprise_score"),
        "surprise_momentum": surp.get("surprise_momentum"),
        "factor_groups": groups,
        "supporting_events": [
            {"event": s["display_name"], "surprise_state": s["surprise_state"], "direction": s["direction"]}
            for s in surp.get("surprises", [])[:6]
        ],
        "disclaimer": _MODEL_DISCLAIMER,
        "timestamp": _now(),
    }


def get_currencies() -> Dict[str, Any]:
    rows = [get_currency(c) for c in SUPPORTED_CURRENCIES]
    scored = [r for r in rows if r.get("available")]
    scored.sort(key=lambda r: r["score"], reverse=True)
    return {
        **_provider_meta(),
        "available": len(scored) > 0,
        "currencies": rows,
        "strongest": [{"currency": r["currency"], "score": r["score"], "direction": r["direction"]} for r in scored[:3]],
        "weakest": [{"currency": r["currency"], "score": r["score"], "direction": r["direction"]} for r in reversed(scored[-3:])] if scored else [],
        "insufficient_evidence": [r["currency"] for r in rows if r.get("state") == "INSUFFICIENT_EVIDENCE"],
        "disclaimer": _MODEL_DISCLAIMER,
        "timestamp": _now(),
    }


def get_pairs() -> Dict[str, Any]:
    from macro_intelligence_engine import ForexRelativeStrengthEngine
    from api.macro_provider import _CCY_BY_COUNTRY  # noqa
    out = []
    for pair in _FX_PAIRS:
        base, quote = pair[:3], pair[3:]
        if not (_currency_has_data(base) and _currency_has_data(quote)):
            out.append({"pair": pair, "available": False, "state": "INSUFFICIENT_EVIDENCE",
                        "reason": f"macro data missing for {base if not _currency_has_data(base) else quote}"})
            continue
        try:
            rs = ForexRelativeStrengthEngine.evaluate_relative_strength(pair)
            if not rs.get("is_forex"):
                # engine only maps a subset — derive from currency scores
                b = get_currency(base); q = get_currency(quote)
                diff = round((b["score"] or 0) - (q["score"] or 0), 1)
                out.append({"pair": pair, "available": True, "relative_score": diff,
                            "base": base, "base_score": b["score"], "quote": quote, "quote_score": q["score"],
                            "direction": "BULLISH" if diff >= 15 else "BEARISH" if diff <= -15 else "NEUTRAL"})
            else:
                out.append({"pair": pair, "available": True, "relative_score": rs["relative_score"],
                            "base": rs["base_currency"], "base_score": rs["base_strength"],
                            "quote": rs["quote_currency"], "quote_score": rs["quote_strength"],
                            "direction": rs["direction"], "bias": rs["relative_bias"]})
        except Exception:
            out.append({"pair": pair, "available": False, "state": "ERROR"})
    return {**_provider_meta(), "available": any(p.get("available") for p in out),
            "pairs": out, "disclaimer": _MODEL_DISCLAIMER, "timestamp": _now()}


# --- assets ---------------------------------------------------------
def get_asset(asset: str) -> Dict[str, Any]:
    asset = asset.upper().strip()
    meta = _provider_meta()
    if asset not in SUPPORTED_ASSETS:
        return {**meta, "asset": asset, "available": False, "state": "UNSUPPORTED",
                "reason": f"Supported: {', '.join(SUPPORTED_ASSETS)}", "timestamp": _now()}

    if not _currency_has_data("USD"):
        return {**meta, "asset": asset, "label": _ASSET_LABEL[asset], "available": False,
                "state": "INSUFFICIENT_EVIDENCE",
                "reason": "No USD macro releases available from the provider.", "timestamp": _now()}

    from macro_intelligence_engine import EconomicStrengthEngine, XAUUSDMacroContextModel

    if asset == "XAUUSD":
        g = XAUUSDMacroContextModel.evaluate_gold_macro_context()
        supporting = [{"factor": k, "score": v["score"], "note": v.get("description", "")}
                      for k, v in g["drivers"].items() if v["score"] > 8]
        opposing = [{"factor": k, "score": v["score"], "note": v.get("description", "")}
                    for k, v in g["drivers"].items() if v["score"] < -8]
        return {
            **meta, "asset": "XAUUSD", "label": "Gold", "available": True, "state": "OK",
            "macro_bias": g["direction"], "score": g["macro_context_score"],
            "bias_label": g["directional_bias"], "confidence": g["data_quality"],
            "drivers": g["drivers"], "supporting_factors": supporting, "opposing_factors": opposing,
            "evidence_count": len(g["drivers"]),
            "disclaimer": _MODEL_DISCLAIMER, "timestamp": _now(),
        }

    # generic driver rollup for the other assets
    usd = EconomicStrengthEngine.evaluate_economic_strength("USD")
    usd_score = float(usd["economic_strength_score"])
    fg = usd.get("factor_groups", {})
    infl = float(fg.get("INFLATION", {}).get("score", 0.0))
    growth = float(fg.get("GROWTH", {}).get("score", 0.0))
    policy = float(fg.get("MONETARY_POLICY", {}).get("score", 0.0))
    sentiment = float(fg.get("SENTIMENT_POSITIONING", {}).get("score", 0.0))

    # transparent per-asset driver weights (sign = effect on the asset)
    weights = {
        "XAGUSD": {"usd_strength": -0.6, "inflation": 0.4, "rates": -0.5, "growth": 0.3, "risk_sentiment": 0.3},
        "USOIL":  {"usd_strength": -0.4, "inflation": 0.3, "rates": -0.2, "growth": 0.6, "risk_sentiment": 0.3},
        "SPX500": {"usd_strength": -0.1, "inflation": -0.4, "rates": -0.6, "growth": 0.7, "risk_sentiment": 0.6},
        "NAS100": {"usd_strength": -0.1, "inflation": -0.5, "rates": -0.8, "growth": 0.6, "risk_sentiment": 0.6},
    }[asset]
    inputs = {
        "usd_strength": usd_score, "inflation": infl, "rates": policy,
        "growth": growth, "risk_sentiment": sentiment,
    }
    contribs = {k: round(inputs[k] * w, 1) for k, w in weights.items()}
    score = round(max(-100.0, min(100.0, sum(contribs.values()))), 1)
    bias = "BULLISH" if score >= 15 else "BEARISH" if score <= -15 else (
        "MIXED" if any(v > 8 for v in contribs.values()) and any(v < -8 for v in contribs.values()) else "NEUTRAL")

    supporting = [{"factor": k, "score": v} for k, v in contribs.items() if v > 5]
    opposing = [{"factor": k, "score": v} for k, v in contribs.items() if v < -5]
    return {
        **meta, "asset": asset, "label": _ASSET_LABEL[asset], "available": True,
        "state": "OK" if abs(score) >= 5 or (supporting or opposing) else "LOW_CONVICTION",
        "macro_bias": bias, "score": score, "confidence": int(usd.get("data_quality", 0)),
        "drivers": contribs, "driver_inputs": inputs,
        "supporting_factors": supporting, "opposing_factors": opposing,
        "evidence_count": len(supporting) + len(opposing),
        "method": "Transparent linear driver rollup from USD economic-strength factor groups. "
                  "Weights are fixed and shown; this is context, not a forecast.",
        "disclaimer": _MODEL_DISCLAIMER, "timestamp": _now(),
    }


def get_assets() -> Dict[str, Any]:
    rows = [get_asset(a) for a in SUPPORTED_ASSETS]
    return {**_provider_meta(), "available": any(r.get("available") for r in rows),
            "assets": rows, "disclaimer": _MODEL_DISCLAIMER, "timestamp": _now()}


# --- overview ------------------------------------------------------
def get_overview() -> Dict[str, Any]:
    meta = _provider_meta()
    ccy = get_currencies()
    upcoming = get_events(window="upcoming", impact=None, limit=40)
    high_impact = [e for e in upcoming["events"] if e["impact"] in ("HIGH", "CRITICAL")][:8]
    surprises = get_surprises(limit=8)

    regime = "INSUFFICIENT_EVIDENCE"
    regime_note = "Not enough currency macro data to classify a regime."
    if ccy["available"] and _currency_has_data("USD"):
        try:
            from macro_intelligence_engine import MacroIntelligenceEngine
            m = MacroIntelligenceEngine.evaluate_macro_context("XAUUSD")
            regime = m.get("economic_classification", "NEUTRAL")
            regime_note = m.get("macro_bias_label", "")
        except Exception:
            pass

    return {
        **meta,
        "available": ccy["available"] or upcoming["available"] or surprises["available"],
        "macro_regime": regime,
        "macro_regime_note": regime_note,
        "strongest_currencies": ccy["strongest"],
        "weakest_currencies": ccy["weakest"],
        "insufficient_currencies": ccy["insufficient_evidence"],
        "upcoming_high_impact": high_impact,
        "latest_surprises": surprises["surprises"][:6],
        "data_freshness": {
            "as_of": _now(),
            "note": "Demo / seeded dataset — realistic shape, not live market data."
            if meta["provenance"] == "seed_demo" else None,
        },
        "confidence": min(
            (ccy["currencies"][0].get("confidence") or 0) if ccy["currencies"] else 0, 100
        ),
        "disclaimer": _MODEL_DISCLAIMER,
        "timestamp": _now(),
    }
