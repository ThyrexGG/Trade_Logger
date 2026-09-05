# Phase 95 — Swing Momentum: Time-Series + Cross-Sectional

**Status: COMPLETE.** Read-only research. No strategy search, no parameter
fitting, no execution, no broker transmission, no signals emitted for
trading. Frozen Phase-74 Gold holdout never read; live automation disabled.

## The one pre-registered question

> Does a classical, **frozen-rule** momentum book — time-series momentum
> (own-trend following) plus cross-sectional momentum (relative-strength
> long/short) — produce a positive, cost-surviving, out-of-sample
> risk-adjusted return on the retail-accessible FX + metals + crypto daily
> universe assembled in Phase 94?

Every parameter was fixed from standard academic/industry practice
**before any result was computed**. Nothing is tuned, per-asset-optimised,
or "best-of" selected. The predeclared sensitivity neighbourhoods
(lookback, rebalance frequency, cost level) are *reported* but never
chosen from.

## Frozen design

| Element | Choice |
|---|---|
| Bar | Weekly, Friday-anchored (`W-FRI`), close-to-close returns |
| Universe | 13 FX majors/crosses + gold + silver (`FX_METALS`); 27-coin Binance spot universe (`CRYPTO`) — from Phase 94 |
| Momentum lookbacks | 13 / 26 / 52 weeks (≈ 3 / 6 / 12 months), equally weighted |
| Time-series signal | mean over the three lookbacks of `sign(trailing return_L)` → range `[-1, 1]` |
| Cross-sectional signal | within each sleeve, rank by the blended trailing return; `+1` top third, `-1` bottom third, `0` middle; count-neutral |
| Combo | `0.5 · TS_weights + 0.5 · XS_weights` per sleeve |
| Sizing | `w_i = signal_i / σ_i` (σ = trailing 26-week realised vol, annualised, floored at 5%); gross-normalised to `Σ|w| = 1`; then the whole sleeve is ex-ante vol-targeted to **10% annualised** with a causal trailing-26-week portfolio-vol estimate; leverage capped (FX 3×, crypto 2×) |
| Rebalance | Weekly |
| Costs | Per-instrument one-way spread/slippage in bps of notional traded, charged on turnover. FX majors 1.0, FX crosses 2.0, gold 2.5, silver 4.0, BTC/ETH 5.0, other crypto 10.0. Ladder **ZERO / BASE / ADVERSE / SEVERE = 0 / 1 / 2 / 4×** |
| Crypto shorts | Assumed held as perpetual-futures shorts, charged/credited the **actual Binance funding rate** (Phase 94 data). This funding P&L is tracked and reported **separately** and does **not** count toward the momentum verdict — carry is Phase 96, not this phase. |

## Out-of-sample framing

The rules involve **zero fitting** — no regression, no threshold search,
no model. Therefore the entire post-warmup history (52-week warmup) is
genuine out-of-sample. Stability is reported three ways: full sample, per
calendar year, and first-half / second-half (the "crypto was one big bull
market" concern).

## Results (BASE costs)

| Sleeve | Sub | Sharpe | CAGR | max DD | cost drag/yr | funding P&L/yr | 1st half → 2nd half Sharpe | Verdict |
|---|---|---:|---:|---:|---:|---:|---|---|
| FX_METALS | TS | −0.33 | −4.0% | −33% | 0.65% | — | — | NEGATIVE |
| FX_METALS | XS | −0.31 | −3.8% | −31% | 0.61% | — | — | NEGATIVE |
| FX_METALS | COMBO | −0.33 | −4.0% | −32% | 0.60% | — | — | **NEGATIVE** |
| CRYPTO | TS | +0.39 | +4.0% | −28% | 0.33% | +0.20% | +0.56 → +0.20 | NOT_ESTABLISHED |
| CRYPTO | XS | +0.15 | +1.1% | −32% | 0.72% | +1.61% | +0.77 → −0.36 | NOT_ESTABLISHED |
| CRYPTO | COMBO | +0.30 | +2.8% | −22% | 0.50% | +0.70% | +0.67 → −0.04 | **NOT_ESTABLISHED** |
| COMBINED_BOOK | inv-vol blend | +0.07 | +0.2% | −18% | — | — | — | **NOT_ESTABLISHED** |

*(Exact figures are in the persisted artifact / API. The table is the
headline BASE-cost run; the artifact also carries ADVERSE-cost metrics,
per-year returns, the placebo battery, and the sensitivity grids.)*

### Verdicts

- **FX + metals momentum: `SWING_MOMENTUM_EDGE_NEGATIVE`.** Both
  sub-strategies lose money after minimal costs over the full 2017–2026
  sample. This is consistent with the well-documented decade-long
  drawdown in FX/commodity trend following. Costs are *not* the problem
  (drag ≈ 0.6%/yr); the raw signal has negative expectancy here.
- **Crypto momentum: `SWING_MOMENTUM_EDGE_NOT_ESTABLISHED`.** The combo
  earns a positive full-sample Sharpe (~0.30) but (a) it does **not**
  clear the 90th percentile of the random-sign placebo (real percentile
  ≈ 0.85) and (b) it is front-loaded: first-half Sharpe ~0.67 collapses
  to ~0 (XS: clearly negative) in the second half. The historical crypto
  trend premium has decayed, exactly as the pre-registered prior warned.
- **Combined book: `SWING_MOMENTUM_EDGE_NOT_ESTABLISHED`** (Sharpe ~0.07,
  placebo percentile ~0.47 — indistinguishable from random-sign exposure
  with the same sizing).
- **Overall: `PROFITABLE_SWING_EDGE_NOT_ESTABLISHED`.**

## Controls run

| Control | Purpose | Result |
|---|---|---|
| Random-sign placebo (N=300) | replace each name's signal sign with random ±1, same sizing/vol-target/costs | Crypto combo at ~85th pct (below the 90th-pct bar); combined book at ~47th pct |
| Cross-sectional-shuffle placebo (N=300) | permute the XS signal across names each week | reported in artifact |
| Vol-matched buy-and-hold benchmark | long-only, same inverse-vol sizing | "does momentum beat just owning the basket" check |
| Cost ladder (ZERO/BASE/ADVERSE/SEVERE) | cost sensitivity | monotone drag; FX stays negative at ZERO cost (not a cost story) |
| Lookback neighbourhood {13}/{26}/{52}/{13,26,52} | predeclared, reported only | in artifact — no variant is selected |
| Rebalance neighbourhood weekly/biweekly/monthly | predeclared, reported only | in artifact |
| Per-asset contribution | descriptive breakdown, not a filter | top/bottom-5 contributors per sleeve |

## What this does and does not establish

- It **does** establish, on this universe and sample, that a textbook
  frozen-rule momentum book is **not** a confirmed profitable edge: FX/metals
  momentum is outright negative, and crypto momentum does not separate from
  a random-sign placebo and has decayed within the sample.
- It **does not** establish that momentum "never works" — only that this
  specific frozen construction, on the retail-accessible instruments the
  user can trade, over 2017–2026, does not clear the pre-registered bar.
- It **does not** touch funding-rate carry (Phase 96), FX/rate-differential
  carry (Phase 97), or any portfolio/risk-of-ruin sizing question (Phase 98).
  The separately-tracked crypto funding P&L (positive, +0.2% to +1.6%/yr on
  the short legs) is a *preview* of why Phase 96 is the more promising line,
  not a result of this phase.

## Determinism

`determinism.match == True` — the FX combo sleeve metrics are byte-identical
across two independent recomputations. All randomness (placebos) is seeded.

## API

`GET /api/research/swing-momentum` — returns the persisted result
(verdicts, per-sleeve metrics, controls). GET-only; `NOT_COMPUTED` until
`python -m phase95_swing_momentum` has run.

## Next phase

**Phase 96 — crypto funding-rate carry** (long spot / short perp, collect
funding): the best risk-adjusted candidate in the pre-registered plan, and
the one this phase's incidental funding P&L hints at.
