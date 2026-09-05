# Phase 97 — Portfolio Construction & Risk-of-Ruin Sizing

**Status: COMPLETE.** Read-only research. No execution, no broker
transmission, no account mutation, no signals emitted. Frozen Phase-74
Gold holdout never read; live automation disabled.

## The question

> Is there a specific capital allocation across the tested sleeves that is
> **USABLE** — meaningfully positive expected return, tolerable ordinary
> drawdown, and an acceptably small probability of ruin once the crypto
> exchange-collapse tail is priced in?

## The sleeves (from Phases 95–96), 2018-08 → 2026-09, 420 weeks

| Sleeve | Standalone Sharpe | Note |
|---|---:|---|
| Crypto funding carry (Phase 96) | **+3.1** | delta-neutral, persistent, exchange-tail exposed |
| Crypto momentum COMBO (Phase 95) | +0.3 | decayed, not established |
| FX + metals momentum COMBO (Phase 95) | −0.2 | negative |

Pairwise correlations are all `|ρ| < 0.10` — the sleeves are essentially
independent.

## Method (all parameters frozen before the result)

1. Re-run each sleeve's weekly net-return series (Phase 95/96 machinery
   unchanged), align on a common weekly calendar.
2. Idle capital earns a frozen **2%/yr** cash rate (conservative T-bill
   proxy for the period).
3. **f\* sizing rule** (deterministic, transparent): the carry fraction is
   the largest grid value such that the *total loss of one exchange
   venue's carry capital* — severity 1.0, the venue simply gone, the
   realistic worst single event — costs at most **12% of the whole book**,
   assuming the carry book is split across **2 venues**. With the carry
   sleeve's ~71% average deployment, one venue holds `f × 0.71 / 2`; the
   12% cap gives **f\* = 25%**.
4. A risk-of-ruin **Monte-Carlo** (4,000 paths/cell) then *validates* the
   drawdown / ruin profile at f\* across an annual-probability × severity ×
   venue-count grid (it is never used to push f\* higher).
5. **Diversification test**: does adding 15% of the non-carry capital to
   crypto or FX momentum improve the combined book vs just holding cash? A
   negative-Sharpe uncorrelated sleeve still loses money — tested, not
   assumed.

## Result

**Recommended allocation: 25% delta-neutral funding carry (spread across
≥ 2 exchange venues) + 75% cash.** Neither momentum sleeve helped the
non-carry capital (both cut the combined Sharpe and deepened drawdown), so
the remainder stays in cash.

| Metric (total capital, historical, no tail applied) | Value |
|---|---:|
| CAGR | **4.2%** |
| — excess over the 2% cash rate | **+2.2%** |
| Annualised vol | 0.9% |
| Max realised drawdown | −0.5% |
| Total return over the sample | +40% |

**Tail / ruin profile of the recommended book** (Monte-Carlo):

| Assumption | median CAGR | P(ruin, final < 0.70×) | P(severe, < 0.50×) |
|---|---:|---:|---:|
| no collapse | +4.2% | 0.0% | 0.0% |
| 4%/yr, 2 venues (planning) | +4.2% | 0.0% | 0.0% |
| 6%/yr, single venue | +4.2% | 0.2% | 0.0% |
| 10%/yr, single venue (harsh) | +4.2% | 0.6% | 0.1% |
| worst realistic single event (one venue gone) | — | **−10% of book** | — |

5th-percentile CAGR under the planning tail is still **+1.9%** (positive).

## Verdict: `USABLE_EDGE_FOUND`

**The first non-null, actionable result in 97 phases of research.**

Allocate ~25% of capital to delta-neutral crypto funding carry across at
least two exchange venues, the rest in cash. Historical total-capital CAGR
4.2% (~2.2% over cash) at a near-zero realised drawdown; a full
single-venue failure costs ~10% of the book; modelled P(ruin) is ~0% on
the planning tail and 0.6% even at a harsh 10%/yr single-venue assumption.

**What it is:** a genuine, survivable, essentially-uncorrelated
positive-expectancy allocation. A ~2%/yr enhancement over cash at very low
risk.

**What it is not:** a wealth engine. The absolute return is modest and
scales with the carry fraction — but so does the exchange tail, and the
12%-single-venue-loss cap is what holds f\* to 25%.

## Limitations (why the true picture is a little worse)

1. **Survivorship bias** (inherited from Phase 96): the 27-coin universe
   is today's survivors. A real carry book would have collected the
   often-highest funding on coins that later collapsed. The real carry
   Sharpe is thinner and the real tail fatter than the numbers above.
2. **Backtested carry returns are unrealistically smooth**: the model
   never sees the weeks where a short leg was liquidated in a squeeze,
   where funding spiked negative on a forced exit, or where an exchange
   had withdrawal halts. A 30–50% haircut to the standalone carry Sharpe
   would be prudent.
3. **The counterparty tail is modelled as a haircut + instant
   continuation.** A real FTX-style failure freezes funds for months to
   years and often coincides with the rest of crypto cratering.
4. **Operational load is real**: running a delta-neutral perp book across
   3 exchanges, monitoring funding, managing margin, weekly rebalancing.
5. **FX / rate-differential carry (the intended diversifier) is
   deferred** — it needs a multi-country short-rate source (FRED API key
   or equivalent) that is not currently configured. When added it should
   improve the book (no crypto-exchange tail, different driver).

## Determinism

`determinism.match == True`; all Monte-Carlo seeded.

## API

`GET /api/research/portfolio-construction` — persisted result (sleeve
metrics, risk-of-ruin grid, f\* sizing, diversification test, recommended
book, verdict). GET-only; `NOT_COMPUTED` until
`python -m phase97_portfolio_construction` has run.

## Next

- **Phase 98 — FX / rate-differential carry** (once a rate-data source is
  available), folded into this allocation as a second uncorrelated sleeve.
- **Phase 99 — paper-trading harness** for the recommended book (6–12
  months, no execution).
