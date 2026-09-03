# Phase 72 — Trade Setup Engine

*Fourth and final checkpoint of the Phase 69–72 master build. Turns "what
historically has an edge" (Phases 70/71) into "does the current market satisfy
that validated edge right now".*

---

## 1. What this phase delivers

| Piece | File |
|---|---|
| Setup engine | `trade_setup.py` — `evaluate_setup(asset, as_of=None)` → `TradeSetup`; `SetupState` enum; injectable validated-strategy resolver; objective condition checklist; state machine; `_derive_levels()` (entry/SL/TP from the live candle window's ATR, never fabricated); `ai_setup_summary()` |
| API | `api/routers/trade_setup.py` — `GET /api/trade-setup`, `/api/trade-setup/{asset}`, `/api/trade-setup/{asset}/conditions` — read-only |
| AI context | `api/ai_context.py` — bounded `trade_setups` snapshot section + a SYSTEM_INSTRUCTION rule that the model may explain but **never** change the state (never call a setup READY, never override NO_SETUP) |
| Frontend | `pages/TradeSetupPage.tsx` (+ hook/api/types) — `/workspace/trade-setup`: 3-second glance (ASSET / DIRECTION / STATE / waiting-for), levels when READY, strategy validation, condition checklist |
| Tests | `tests/test_phase72_trade_setup.py` — 14 tests |
| Docs | this file |

No execution / broker / risk / reconciliation file touched. `trade_setup.py`
imports nothing from the execution layer (asserted). Frozen hash + holdout
untouched.

---

## 2. The hard rule (§72)

A setup is `READY` **only** when:

1. a **VALIDATED** strategy exists for the instrument, AND
2. every mandatory condition passes, AND
3. no required evidence is stale, AND
4. the current regime is compatible, AND
5. MTF timing is valid, AND
6. entry / SL / TP are objectively derivable from the strategy's stop/target model.

Otherwise: `NO_SETUP` / `WATCH` / `SETUP_FORMING` / `INVALIDATED` / `STALE` /
`INSUFFICIENT_EVIDENCE`, each with the failing condition named in `waiting_for`.

### "VALIDATED" is evidence-gated

`_default_resolver` marks a strategy VALIDATED for an asset only when the
persisted research artifacts say so by their own objective rules:

- a `pair_ranking` leaderboard candidate with scorecard `STRONG`, or
- `gold_revalidation` `edge_status == "VALIDATED"` (XAUUSD).

**Phases 70/71 produced neither.** So today `evaluate_setup` returns `NO_SETUP`
for every instrument with the reason:

> *No validated strategy for {asset}. Phase 70/71 discovery found no strategy
> clearing positive OOS lower-CI + N≥50 + WFO stability on the available 1h/1d
> data. A Trade Setup can only be READY behind a VALIDATED strategy.*

This is the correct behaviour (§65, §72). The machinery is real, fully tested on
the READY path (injected validated strategy + favourable evidence), and lights up
automatically when the research evidence improves.

---

## 3. Conditions evaluated

| # | Condition | Source | Mandatory |
|---|---|---|---|
| 1 | HTF bias decisive | Phase-67 `TECHNICAL` category direction (BULLISH/BEARISH) | ✅ |
| 2 | Regime compatible | Phase-67 `REGIME` category + per-family tolerance table | ✅ |
| 3 | MTF alignment | `SMC` direction agrees with `TECHNICAL` bias | ✅ |
| 4 | SMC trigger present | `SMC` evidence names a sweep / MSS / FVG / OB | ✅ |
| 5 | Session permitted | current UTC session ∈ strategy's session list | ✅ |
| 6 | Evidence fresh | no Phase-67 category is `STALE` | ✅ |

Each condition carries `passed` (`true` / `false` / `null` = can't evaluate) and
a `detail` string pointing at the evidence. A `null` on a mandatory condition →
`INSUFFICIENT_EVIDENCE`; a `STALE` category → `STALE`; two contradicting
mandatory fails → `INVALIDATED`.

---

## 4. Levels (§38, §45)

`_derive_levels` computes entry/SL/TP **only when the state is READY** and
**only** from the live as-of candle window's ATR(14): entry = last close, SL =
entry ∓ 1.5·ATR, TP = entry ± 2.5·ATR, R:R = 2.5/1.5. If no candle window
resolves, the state falls back to `SETUP_FORMING` — never a fabricated level. No
risk-gateway import; R:R is the only risk figure shown.

---

## 5. AI (§43)

The AI context gets a compact `trade_setups` array (state / direction / reason /
waiting_for + a "deterministic engine owns this state; do not override it" note).
`SYSTEM_INSTRUCTION` adds: *"you must NEVER report a state other than what this
section says — never call a setup READY, and never override a NO_SETUP / NO
TRADE."* Context block stays ≤ 16 KB.

---

## 6. Safety

`LIVE_AUTOMATION_ENABLED = False`, `LIVE_BROKER_TRANSMISSION = "BLOCKED"` — no
Phase-72 module imports `execution_pipeline`, `broker_adapter`, `risk_gateway`,
`reconciliation` or `order_execution` (`test_phase72_trade_setup.py`). All
endpoints GET-only. The `TRIGGERED` state from §37 is **not** implemented —
there is no order path. Frozen hash + holdout intact.

---

## 7. Tests

`tests/test_phase72_trade_setup.py` (14): no-validated-strategy → NO_SETUP (all
instruments); READY path (injected strategy + favourable evidence + candle
window); SETUP_FORMING when levels not derivable; wrong MTF alignment; incompatible
regime; wrong session; stale evidence → STALE; unknown regime → INSUFFICIENT_EVIDENCE;
contradiction → not READY; AI summary matches the engine + carries "do not
override"; SYSTEM_INSTRUCTION forbids overriding; no execution imports; endpoints
GET-only + safe.

---

## 8. Phase 69–72 — done

| Phase | Deliverable | Verdict |
|---|---|---|
| 69 | Persistent historical data foundation + Gold baseline recovery | data ships empty, populated per-env; 1h/4h/1d real depth |
| 70 | Strategy discovery + pair × strategy ranking | **NO ROBUST EDGE FOUND** on 1h |
| 71 | Gold revalidation baseline | **DEGRADED / UNVERIFIABLE** — 1h proxy weak-positive, native 1m not testable |
| 72 | Trade Setup Engine | every instrument **NO_SETUP** (no validated strategy) — the honest, correct state |

The system can now answer *"which validated strategy has the strongest evidence
of a persistent edge, and does today's market satisfy it?"* — and its honest
current answer is **"none clears the bar on the available data, so: no trade."**
That is a successful outcome (§69): the pipeline is real, the gates are strict,
and nothing is fabricated.
