# Phase 99 — FX / Rate-Differential Carry (G10)

**Status: COMPLETE.** Read-only research (FRED macro data only). No
execution, no broker transmission, no account mutation, no signals
emitted. Frozen Phase-74 Gold holdout never read; live automation
disabled.

## The question

> Rank the G10 currencies each month by their 3-month interbank rate; go
> long an equal-weight basket of the 3 highest-yielders, short the 3
> lowest-yielders (dollar-neutral). After realistic G10 spot costs, does
> this classic carry basket earn a positive out-of-sample return — and
> does adding it to the Phase-97 book help?

Every parameter frozen before the result.

## Frozen design

| Element | Choice |
|---|---|
| Universe | USD, EUR, GBP, JPY, CAD, AUD, NZD, CHF |
| Rates | FRED `IR3TIB01<area>M156N` 3-month interbank (monthly, OECD); last value carried forward. **Now cached as artifact `phase99_g10_rates`** |
| Monthly return per currency (vs USD) | `spot_return(ccy/USD) + (rate_ccy − rate_USD)/12` — USD leg = 0 |
| Signal | sort by rate; long top 3 / short bottom 3, equal weight each leg |
| Rebalance | monthly |
| Costs | 1.5 bps one-way per currency leg; ladder 0/1/2/4× |

## Results (BASE costs, 2017-03 → 2026-06, 112 monthly obs)

| Metric | Value |
|---|---:|
| Sharpe | **0.35** (0.35 at ADVERSE — G10 spot costs are negligible) |
| CAGR | +1.7% |
| Annualised vol | 5.2% |
| Max drawdown | −7.9% |
| Monthly hit rate | 62% |
| Positive calendar years | 6 / 10 |
| first-half → second-half Sharpe | **+0.04 → +0.67** |

**Per year:** negative 2018 / 2019 / 2020 (the "carry is dead" era),
positive 2021–2024 as policy rates diverged (Fed hiking cycle), flat 2025,
positive 2026-YTD.

**Controls:**
- Random-currency placebo: real Sharpe at the **92nd percentile**
- Naive G10 basket benchmark: Sharpe **−0.23** (carry clearly beats just
  owning the basket)
- Cost ladder: Sharpe 0.35 → 0.34 across ZERO → SEVERE (cost-insensitive)

## Does it help the Phase-97 book?

Correlation with the crypto funding carry is **+0.07** — genuinely
uncorrelated. But:

| Book | Sharpe | CAGR | max DD |
|---|---:|---:|---:|
| Phase-97 (25% crypto carry + 75% cash) | 2.68 | 4.0% | −0.4% |
| + a 15% FX-carry sleeve (from cash) | **2.27** | 4.0% | −1.1% |

**Adding FX carry makes the book worse.** Its own Sharpe (0.35) is far
below the crypto-carry-plus-cash book's, and its 5.2% volatility dwarfs
the book's ~1%, so even at near-zero correlation the sleeve dominates the
combined risk without adding return.

## Verdict: `FX_CARRY_EDGE_NOT_ESTABLISHED`

G10 rate-differential carry is weakly positive (Sharpe 0.35), beats the
naive basket, and is near-uncorrelated with the crypto carry — but:
1. the edge is **entirely in the recent half** (2021+ rate divergence);
   the 2017–2020 half was flat-to-negative;
2. the sample is thin (~112 monthly observations);
3. it does **not** improve the Phase-97 book — it drags it.

**No change to the program status.** `PROFITABLE_TRADING_EDGE_FOUND`
stays `FOUND` on the strength of the Phase-96/97 crypto funding carry
alone. FX carry is not a usable addition on this evidence.

## Limitations

- Thin sample; a monthly strategy with ~112 points cannot support a strong
  verdict either way.
- FRED interbank rates are month-average and lag 1–5 months for some
  currencies (carried forward) — fine for a slow carry signal, not
  precise.
- Only G10; no EM carry (higher yield, fatter tails, not in scope).
- The last decade was genuinely poor for FX carry — this result is
  consistent with the broad literature, not an implementation failure.

## Determinism

`determinism.match == True`.

## API

`GET /api/research/fx-carry` — persisted result. GET-only; `NOT_COMPUTED`
until `python -m phase99_fx_carry` has run
(`--refresh-rates` to re-fetch from FRED).

## Where this leaves the swing pivot

The swing research program has produced exactly one usable edge:
**delta-neutral crypto perpetual funding carry, ~25% of capital,
multi-venue, cash otherwise (Phase 97)** — now under weekly forward
monitoring (Phase 98). Momentum (Phase 95) and FX carry (this phase) are
both dead ends. The remaining work is operational: run the Phase-98
harness weekly and let the forward evidence accumulate.
