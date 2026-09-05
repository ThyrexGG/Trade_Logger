# Phase 96 — Crypto Perpetual Funding-Rate Carry (delta-neutral)

**Status: COMPLETE.** Read-only research. No strategy search, no
parameter fitting, no execution, no broker transmission, no signals
emitted for trading. Perp OHLCV ingestion is free Binance data. Frozen
Phase-74 Gold holdout never read; live automation disabled.

## The one pre-registered question

> Long 1 unit of crypto **spot**, short 1 unit of the same coin's
> **perpetual** future. The price legs cancel (delta-neutral); the
> position earns the funding rate longs pay shorts (positive ~85% of the
> time in crypto's normal regime). Does harvesting it produce a positive,
> cost-surviving, out-of-sample return — **and does it still look
> attractive once the real risk (an exchange-collapse / counterparty
> tail, FTX-style) is priced in?**

No parameter is fitted, tuned, per-coin optimised, or best-of selected.

## Frozen design

| Element | Choice |
|---|---|
| Bar | Weekly, Friday-anchored |
| Universe | 27 coins — the Phase-94 set with both a Binance spot pair and a Binance USD-M perpetual |
| Weekly P&L per coin | `(spot_ret − perp_ret) + funding_received − costs`. `spot_ret − perp_ret` is the **measured** basis-convergence term (real perp prices ingested here as `<BASE>PERP`/1d); `funding_received` is the actual weekly-summed Binance funding rate (short receives it when funding > 0) |
| Signal | trailing 4-week mean funding, annualised (`weekly_sum × 52`) |
| Entry / exit | enter when trailing annualised funding `> +3%`; exit when `≤ 0`; hysteresis; **positive-carry only** (reverse carry needs spot borrow → not retail-accessible → excluded) |
| Sizing | equal weight across eligible coins, each capped at 15% of the book, ≤ 15 concurrent positions (capacity cap; highest-funding coins if more qualify); **no leverage**; idle capital earns 0 |
| Rebalance | Weekly |
| Costs | per-coin one-way bps **per leg** (spot 5/10, perp 3/6) on turnover; ladder ZERO/BASE/ADVERSE/SEVERE = 0/1/2/4× |

## Results — the return stream (BASE costs, 2017-10 → 2026-09, 466 weeks)

| Metric | Value |
|---|---:|
| Sharpe | **+2.94** (ADVERSE costs: +2.61) |
| CAGR | +10.1% |
| Annualised vol | 3.3% |
| Max drawdown | −2.4% (47 weeks) |
| ann. funding income | +10.8% |
| ann. basis drift | **−0.08%** (negligible — perps track spot tightly) |
| ann. cost | −1.1% |
| avg positions / capital deployed | 9.6 / 72% |
| positive calendar years | **7 / 10** |
| weekly skew / kurtosis | +3.5 / +21 |
| first-half → second-half Sharpe | +3.36 → +2.91 (barely decayed) |

**Controls:**

| Control | Result |
|---|---|
| Random-eligibility placebo (N=300) | real Sharpe beats **every** random same-count selection (percentile 1.00) |
| Funding persistence (does trailing funding predict forward funding?) | pooled corr **+0.53**, positive for **27 / 27** coins |
| Delta-neutrality regression (carry P&L on BTC weekly return) | BTC beta **+0.008** — genuinely market-neutral |
| Basis attribution | funding is ~100% of gross; basis is a trivial −0.08%/yr |
| Cost ladder | Sharpe 3.26 / 2.94 / 2.61 / 1.94 across ZERO/BASE/ADVERSE/SEVERE |
| Threshold neighbourhood {2%, 3%, 5%} | reported in artifact; 3% is the frozen design, never selected from |

The return stream is real, persistent, delta-neutral, and cost-robust —
**the strongest signal found anywhere in the 96-phase research program.**

## Results — the tail (the centrepiece)

Exchange-collapse Monte-Carlo: with annual probability `p`, the deployed
carry capital takes a one-off `−sev` haircut in a random week
(`sev = 1.0` = total loss of deployed capital). 4,000 paths per cell.
**The median is deliberately not the headline** — a rare catastrophe
leaves the median path untouched by construction; the loss tail is the
point.

| Cell (annual prob × severity) | 5th-pct total return | prob(ends underwater) | ≥1 collapse in sample |
|---|---:|---:|---:|
| base, no tail | +136% | 0% | — |
| 2% /yr × 50% haircut | +18% | 0.7% | 16% |
| **5% /yr × 50% haircut** (reference) | **+10%** | **4.6%** | 36% |
| 10% /yr × 100% haircut (aggressive) | **−100%** | **48%** | 60% |
| deterministic: total loss on the single worst week | **−100%** | — | — |

**Tail verdict: `FUNDING_CARRY_SURVIVES_TAIL_MARGINAL`** — the carry
holds up under a *modest* counterparty tail (≤ 5%/yr, partial loss: 5th
percentile still positive, ~5% ruin) but **not** under an aggressive one
(10%/yr with total loss: ~half of all outcome paths end in ruin).

## Verdicts

- **Edge: `FUNDING_CARRY_EDGE_PROMISING`.** Clears every bar —
  Sharpe ≥ 1.0, beats the placebo at the 95th percentile, funding
  persistence ≥ 0.2, ADVERSE-cost Sharpe ≥ 0.5, BTC beta < 0.15 —
  **except one**: positive in only 7/10 calendar years (bar: 80%), because
  2022's bear market compressed funding to ~0. A single-criterion miss;
  the design freeze forbids moving the bar to pass it.
- **Tail: `FUNDING_CARRY_SURVIVES_TAIL_MARGINAL`** (above).
- **Overall: `PROFITABLE_SWING_EDGE_PROMISING`** — the **first non-null
  verdict in the research program.** Not `FOUND` (that needs edge
  CONFIRMED + tail SURVIVES_YES); genuinely promising and worth carrying
  into paper trading, with the tail sized deliberately.

## Limitations — why even PROMISING is generous

1. **Survivorship bias (the big one).** The 27-coin universe is drawn
   from *today's* market-cap survivors with ≥ 2 years of history
   (Phase 94's selection). A carry book actually running in 2021 would
   have collected funding on coins that later collapsed (LUNA/UST, and
   others), and the funding rate is often *highest* right before a blow-up
   (the market paying up to be long a doomed asset). The measured Sharpe
   is biased up and the measured tail is biased thin. This is not
   correctable with the data in hand — it is a reason to treat the tail
   MC's aggressive cells as the realistic case, not the pessimistic one.
2. **Perp-margin / liquidation risk is modelled only as a proxy.** A
   sharp rally can liquidate an under-margined short leg at a loss while
   the offsetting spot gain is unrealised. Real desks hold large margin
   buffers (lowering return) or occasionally get liquidated (the tail).
   The exchange-collapse MC stands in for "bad things happen to the
   position"; it is not a precise liquidation model.
3. **Costs may be optimistic for the smaller alts** (10 bps taker
   assumed); and the funding rate itself moves against you as capital
   crowds in — the backtest uses *historical* funding, not
   post-crowding funding.
4. **One regime.** Crypto's funding-positive regime coincides with a
   secular bull market. A prolonged bear (2022 writ large) takes the
   edge to ~0, as the 7/10 positive years already shows.

## Determinism

`determinism.match == True`; all Monte-Carlo seeded.

## Data added

`<BASE>PERP` / `1d` daily OHLCV for all 27 coins (Binance USD-M
`fapi/v1/klines`), ingested with the Phase-74/94 provenance discipline.
Idempotent. This is the only new data; funding history and spot OHLCV
were already in the store from Phase 94.

## API

`GET /api/research/funding-carry` — persisted result (headline metrics,
decomposition, controls, tail grid, verdicts). GET-only; `NOT_COMPUTED`
until `python -m phase96_funding_carry` has run.

## Next phase

**Phase 97 — FX / rate-differential carry** (the diversifier), then
**Phase 98 — portfolio construction + risk-of-ruin sizing** (where the
Phase-96 tail gets sized explicitly against the Phase-95 momentum sleeves).
