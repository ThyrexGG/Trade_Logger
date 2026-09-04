# Phase 77 — Large-Bar Reversal Candidate Validation + Volatility Context

> **Research verdict (stated first): `NO_VALIDATED_CANDIDATE`.**
> The Phase 76 large-bar reversal phenomenon is real but tiny. Converted into an
> objective stop-defined fade it captures a **gross OOS expectancy of essentially
> zero** (−0.008 R, bootstrap CI [−0.039, +0.022] — crosses zero) and a
> **negative net expectancy under every pre-registered cost assumption**,
> including a 0.025-ATR round-trip cost (half the Phase 76 proxy). No entry model,
> exit model, regime filter, volatility bucket, session or JPY-cross subset
> rescued it. **Phase 78 is NOT recommended for a large-bar-reversal strategy.**
> Machine-readable artifact: `phase77_large_bar_reversal`
> (`GET /api/research/large-bar-reversal`).

`python -m phase77_large_bar_reversal` · deterministic (`RANDOM_SEED = 42`,
identical `content_hash` on repeat) · content hash `041d5601b743…` · runtime
~83 s.

---

## A. Executive summary

Phase 76 ranked **H8 — large-bar reversal** as the single strongest *directional*
candidate: after a bar whose true range is ≥ 1.5 × ATR(14), forward returns over
1–8 bars lean **against** the bar's direction by roughly 0.05 ATR, on four FX
pairs (AUDJPY, GBPJPY, GBPUSD, EURUSD), a little cleaner on the JPY crosses in
ranging regimes. Phase 76 flagged that its flat "0.05 ATR round-trip" cost proxy
was too crude to settle whether this is tradable.

Phase 77 reproduces the **exact** Phase 76 H8 event set (same ATR, same
threshold, same direction rule — `phase76_event_study._b_range_expansion`,
imported unchanged) and wraps a small, pre-registered, fully deterministic
trading rule around it: fade the large bar, enter next bar, stop just beyond the
bar's extreme (+0.10 ATR), target the pre-event price, time-stop after 8 bars. It
scores that rule out-of-sample against (a) a per-instrument spread + slippage +
commission "broker friction" model and (b) a four-point ATR cost-sensitivity
grid.

**Findings (H8-P1, all 4 pairs, 15m, OOS N = 12 883):**

| Question | Result |
|---|---|
| Gross OOS expectancy | **−0.008 R**, bootstrap CI **[−0.039, +0.022]** — indistinguishable from zero |
| Net OOS expectancy (0.05-ATR proxy) | **−0.128 R**, CI [−0.159, −0.099] |
| Net OOS expectancy (broker friction) | **−1.32 R** (conservative pip model; see §H) |
| Survives the 0.05-ATR cost proxy? | **No** |
| Survives even a 0.025-ATR cost? | **No** (−0.068 R) |
| JPY-cross subset (H8-P2, N 6 051) | gross −0.010 / net −0.129 — **FAIL** |
| Ranging-regime filter (H8-P3, N 2 197) | gross −0.064 / net −0.185 — **FAIL, worse than all-regime** |
| Entering closer to the extreme (retest limit 50 %) | gross **+0.077 R** (best of the family) / net −0.095 — still FAIL |
| Fixed-R exits (0.5 R / 1 R) instead of full reversion | gross −0.29 / −0.18 — much worse |
| Parameter neighbourhood (mult 1.25–2.0, hold 4–12) | all cells negative; net rises toward 0 as the threshold rises but never crosses it |
| Cross-asset class | **NONE** — every pair's OOS net is negative with CI below zero |
| Volatility-context conditioning | **NOT_MATERIAL** — no clean positive sub-population |

The gross reversal signal Phase 76 measured **does still exist** — you can see it
in `retest_limit_50` (gross +0.077 R) and in the fact that pooled gross OOS is a
hair below zero rather than the −0.09 R a random fade would give after paying the
implicit stop/target geometry. Phase 76 is not contradicted. What Phase 77
establishes is that once you place a real stop, pick a real target and pay a
realistic spread, the edge is gone. The natural fade stop sits ~0.15–0.5 ATR from
entry, so `cost_R = cost / risk` is large and the ~0.05-ATR lean cannot cover it.

**This is a clean, useful negative result.** It closes the last open directional
thread from Phase 76 without manufacturing a candidate.

---

## B. Phase 76 findings carried into Phase 77

- Volatility clustering — confirmed, non-directional.
- Session-open volatility seasonality — confirmed, non-directional.
- Compression → expansion breakout — contradicted by the data.
- Time-series momentum, intraday momentum — did not transfer.
- Previous-day-high breakout — insufficient evidence.
- Short-term reversal — real but ~at the cost threshold.
- **H8 large-bar reversal** — strongest directional candidate: signed
  continuation effect `z` ≈ −2.5 to −3.2 at the 1.5× threshold on the four pairs
  (15m), OOS-persistent, ~0.05 ATR magnitude, conditional structure a little
  larger in ranging regimes. Phase 76 status `REAL_BUT_SUB_COST`; it explicitly
  deferred the execution question to this phase.

`ML_READINESS` from Phase 76 was `DATA_READY_BUT_EDGE_UNCLEAR`; Phase 77 does not
change it (§24).

---

## C. Research question

> Does the Phase 76 large-bar reversal phenomenon survive a realistic execution
> model and objective regime conditioning, and therefore deserve deeper
> validation (Phase 78)?

Single question. Not a strategy search. A negative answer is acceptable and, per
§23, must not be answered by adding indicators, filters or ML.

---

## D. H8 mathematical definition (frozen, reproduced from Phase 76)

For timeframe TF (headline **15m**; **1h** carried as a robustness comparison),
on the MT5 mid-price OHLCV series filtered to `source == "mt5"`:

```
true_range_t = max( high_t − low_t, |high_t − close_{t−1}|, |low_t − close_{t−1}| )
ATR_t        = simple moving average of true_range over 14 bars (min_periods 14)
tr_atr_t     = true_range_t / ATR_t
```

**Event** at bar `i` (`i ≥ 20`) iff `tr_atr_i ≥ mult` (baseline `mult = 1.5`,
exact Phase 76 `H8_RANGE_EXPANSION_1_5`; also tested at `mult = 2.0`).

- **Large-bar direction** `bar_dir_i = sign( log(close_i / close_{i−1}) )`.
- **Event magnitude** = `tr_atr_i`.
- **Fade direction** `d = −bar_dir_i` (large bullish bar → SHORT, large bearish
  bar → LONG).

This is `phase76_event_study._b_range_expansion(df, mult)` called directly.
`test_h8_event_matches_phase76_exactly` asserts byte-for-byte agreement of index,
direction and magnitude arrays. Phase 76's forward horizons were {1, 2, 4, 8}
bars; Phase 77's 8-bar time-stop matches the longest.

---

## E. Dataset coverage

MT5 broker spot, single provider (`source == "mt5"`), from the persisted dataset
manifests. `run_instrument` returns `state = OK` for all eight series.

| Instrument | TF | Bars | Span | Events (≥1.5×ATR) | Trades | Dev/OOS boundary (UTC) |
|---|---|---:|---|---:|---:|---|
| AUDJPY | 15m | 100 547 | 2022-08-22 → 2026-09-03 | 12 059 | 10 331 | 2025-06-18 12:00 |
| AUDJPY | 1h  | 62 201 | 2016-09-05 → 2026-09-03 | 7 869 | 7 058 | 2023-09-05 06:00 |
| GBPJPY | 15m | 100 000 | 2022-08-29 → 2026-09-03 | 12 381 | 10 737 | 2025-06-20 05:15 |
| GBPJPY | 1h  | 62 179 | 2016-09-05 → 2026-09-03 | 9 462 | 8 727 | 2023-09-05 13:00 |
| GBPUSD | 15m | 100 067 | 2022-08-29 → 2026-09-03 | 13 401 | 11 561 | 2025-06-20 00:00 |
| GBPUSD | 1h  | 62 203 | 2016-09-05 → 2026-09-03 | 12 198 | 11 277 | 2023-09-05 07:00 |
| EURUSD | 15m | 100 065 | 2022-08-29 → 2026-09-03 | 13 555 | 11 896 | 2025-06-20 00:15 |
| EURUSD | 1h  | 50 053 | 2018-08-19 → 2026-09-03 | 9 657 | 8 956 | 2024-04-08 03:00 |

Split: chronological **70 / 30 on bar index per instrument**, identical to
Phase 76. A trade belongs to DEV or OOS by the index of its **event bar** vs the
frozen boundary. All Phase 77 parameters are fixed in the module before the OOS
slice is scored (§16). ~10 % of events are skipped by the setup-validity gates
(§G) — mostly bars that closed within 0.15 ATR of their own extreme.

---

## F. Primary hypothesis registry (§15)

| ID | Scope | OOS N | Result |
|---|---|---:|---|
| **H8-P1** | all 4 primary pairs, 15m | 12 883 | gross −0.008 / net −0.128 → **FAIL** |
| **H8-P2** | JPY crosses (AUDJPY, GBPJPY) | 6 051 | gross −0.010 / net −0.129 → **FAIL** |
| **H8-P3** | ranging regime only (all pairs) | 2 197 | gross −0.064 / net −0.185 → **FAIL** |
| **H8-P4** | cost stress (ATR grid + broker) | 12 883 | `DOES_NOT_SURVIVE_REALISTIC_COSTS` |

4 primary hypotheses → Bonferroni α = 0.0125. Everything else (parameter
neighbourhood, entry/exit comparison, session, weekday, volatility bucket) is
**diagnostic** and is not used for selection. No parameter optimisation was
performed; `expected_false_positives_at_0.05 = 0.2`.

---

## G. Execution model

- **Entry** (primary): `next_bar_market` — fill at the open of bar `i+1`. The
  conservative baseline (§7).
- **Setup validity gates** (pre-registered, not tunable):
  1. reversion distance must still exist — skip if `open_{i+1}` has already
     retraced past `open_i` (the target).
  2. stop room must exist — skip if the large bar closed within **0.15 ATR** of
     its own extreme (risk distance would be a rounding error, making any fixed
     cost an absurd R multiple).
- **Stop**: beyond the large-bar extreme by 0.10 ATR (short: `high_i + 0.10·ATR_i`;
  long: `low_i − 0.10·ATR_i`).
- **Target** (primary): `revert_to_event_open` — the large bar's **open** price.
- **Time exit**: flat at the close of bar `i + 8`.
- **Intrabar**: if a bar spans both stop and target, the **stop** is assumed hit
  first (conservative).
- **No look-ahead**: the forward walk starts at the entry bar and only moves
  forward; truncating all bars after the exit bar does not change the trade
  (`test_entry_is_next_bar_open_no_lookahead`).

Observed trade shape (H8-P1 OOS): win rate ≈ 36.7 %, average 1.7 bars held, exit
mix STOP 8 121 / TARGET 4 488 / TIME 274. A far reversion target with a tight
stop ⇒ many small stop-outs, occasional large (+10–18 R) reversion wins,
profit-factor 0.99 gross / 0.82 net-proxy.

---

## H. Cost model (§8)

**Historical bid/ask / tick spread is not available** — the MT5 series are
mid-price OHLCV with no stored spread column. No spread data was invented (§8).
Two lenses:

1. **Broker friction model** (the project's deterministic research-grade
   assumption, `strategy_discovery`): per side `spread 1.5 pip`, `slippage 0.5
   pip`, plus `0.005 %` round-trip commission, applied per instrument via its pip
   size. `cost_price = 1.5·pip + 2·0.5·pip + (0.005/100)·(|entry| + |exit|)`;
   `cost_R = cost_price / risk_distance`. **This is deliberately conservative for
   FX majors** — a 1.5-pip EURUSD spread is wide versus a modern ECN, and because
   the fade risk distance is small the resulting `cost_R` is large (≈ 1 R+). It
   is the pessimistic bound, not the central estimate.
2. **ATR cost-sensitivity grid** (§9): round-trip cost of **0.025 / 0.05 / 0.075
   / 0.10 ATR**, `cost_R = g·ATR_i / risk`. `0.05` is the Phase 76 proxy;
   `0.025` is half of it and brackets a realistic ECN major. **This is the
   headline `r_net`** (0.05) — kept comparable to Phase 76's cost treatment.

H8-P1 OOS mean R by ATR round-trip cost:

| cost (ATR round trip) | 0.025 | 0.05 | 0.075 | 0.10 |
|---|---:|---:|---:|---:|
| mean R | −0.068 | −0.128 | −0.189 | −0.249 |

Negative at every point — including 0.025 ATR. `positive_up_to_atr_cost = null`.

---

## I. Entry models (§7)

Pooled OOS, 4 pairs, 15m:

| entry model | OOS N | gross E[R] | net E[R] (0.05) | bootstrap LB |
|---|---:|---:|---:|---:|
| next_bar_market (primary) | 12 883 | −0.008 | −0.128 | −0.159 |
| retest_limit_25 | 11 896 | +0.009 | −0.132 | −0.166 |
| retest_limit_50 | 10 503 | **+0.077** | −0.095 | −0.138 |
| confirm_delay | 5 516 | −0.043 | −0.110 | −0.139 |

Entering nearer the large-bar extreme (`retest_limit_50`) is the **best gross of
the family** (+0.077 R) and confirms the reversal lean is genuinely there — but
net is still −0.095 R with a CI entirely below zero. `confirm_delay` (wait one
bar for a confirming close) halves the sample and does not help.

## J. Exit models (§10)

Pooled OOS, 4 pairs, 15m:

| exit model | gross E[R] | net E[R] (0.05) | bootstrap LB |
|---|---:|---:|---:|
| revert_to_event_open (primary) | −0.008 | −0.128 | −0.159 |
| fixed_r_0.5 | −0.292 | −0.412 | −0.426 |
| fixed_r_1.0 | −0.183 | −0.303 | −0.321 |

Fixed-R targets are far worse: with a stop only ~0.15–0.5 ATR away, a 0.5 R or
1 R target is a tiny absolute move that the stop reaches first most of the time.
Full reversion to the event open is the least-bad exit and still negative.

---

## K. Range-regime analysis (§11)

Regime = Kaufman 20-bar efficiency ratio at the **event bar** (TRENDING > 0.35,
RANGING < 0.15, else MIXED) — pre-entry information only, the exact Phase 76
`regime` column.

| regime | OOS N | gross E[R] | net E[R] (0.05) | 95 % CI (net) | win % | PF |
|---|---:|---:|---:|---|---:|---:|
| RANGING | 2 197 | −0.064 | **−0.185** | [−0.252, −0.113] | 34.4 | 0.75 |
| MIXED | 2 294 | +0.024 | −0.098 | [−0.173, −0.021] | 35.1 | 0.87 |
| TRENDING | 8 392 | −0.002 | −0.122 | [−0.157, −0.084] | 36.2 | 0.83 |

**Conditioning on RANGING (H8-P3) made it worse**, not better — the opposite of
what Phase 76's forward-return event study suggested. In R terms the ranging
subset has the lowest win rate and profit factor. Phase 76's "reversal is a
little larger in ranging regimes" does not survive as tradable expectancy.

---

## L. Volatility-regime analysis (§12, §22)

Bucket = Phase 76 causal trailing-200-bar ATR percentile at the event bar
(LOW < 0.33, HIGH > 0.66, else NORMAL).

| bucket | OOS N | gross E[R] | net E[R] (0.05) | 95 % CI (net) |
|---|---:|---:|---:|---|
| LOW_VOL | 4 573 | −0.026 | −0.143 | [−0.191, −0.094] |
| NORMAL_VOL | 4 361 | +0.022 | −0.099 | [−0.151, −0.047] |
| HIGH_VOL | 3 949 | −0.019 | −0.143 | [−0.198, −0.089] |

**Volatility-context finding: `NOT_MATERIAL`.** NORMAL_VOL is the least-bad
bucket (gross slightly positive) but net is still −0.099 R with a CI below zero;
LOW and HIGH are indistinguishable from each other. There is no clean positive
sub-population, so **no `FILTER_CANDIDATE` is recorded**.

---

## M. Session analysis (§13, diagnostic only)

Session = Phase 76 UTC-hour windows. OOS, all pairs.

| session | OOS N | gross E[R] | net E[R] (0.05) | 95 % CI (net) |
|---|---:|---:|---:|---|
| LATE_US (21–24 UTC) | 2 269 | **+0.105** | −0.003 | [−0.070, +0.067] |
| NEW_YORK (16–21) | 783 | +0.074 | −0.050 | [−0.176, +0.078] |
| LONDON (07–12) | 2 519 | −0.017 | −0.142 | [−0.211, −0.073] |
| TOKYO (00–07) | (largest) | ~−0.10 | ~−0.16 | below zero |
| LONDON_NY_OVERLAP (12–16) | 2 896 | −0.066 | −0.188 | [−0.251, −0.126] |

The thin **LATE_US** window is the one place the fade is roughly breakeven net
(gross +0.105 R, 44.9 % win rate). **This was not pre-registered**, the net CI
still straddles zero, and §13 forbids building a session-specific strategy on a
p-hacked slice. It is noted only as a direction a *future* pre-registered study
could take, not a Phase 77 candidate.

## N. OOS results (§17)

| Hyp | N(dev) | N(oos) | DEV net E[R] | OOS gross E[R] | OOS net E[R] (0.05) | OOS net E[R] (broker) | median R | win % | PF (net) | 95 % CI (net) | Bonferroni CI | gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| H8-P1 | 31 642 | 12 883 | −0.099 | −0.008 | **−0.128** | −1.32 | −1.07 | 35.7 | 0.82 | [−0.159, −0.099] | [−0.165, −0.090] | FAIL |
| H8-P2 | 15 017 | 6 051 | −0.095 | −0.010 | **−0.129** | −1.00 | −1.07 | 37.0 | 0.82 | [−0.171, −0.087] | [−0.184, −0.076] | FAIL |
| H8-P3 | 5 529 | 2 197 | −0.118 | −0.064 | **−0.185** | −1.72 | −1.07 | 34.4 | 0.75 | [−0.252, −0.113] | [−0.268, −0.092] | FAIL |

Central metric = **net OOS expectancy in R** (§17). Every primary hypothesis is
negative with the whole 95 % CI below zero. DEV and OOS agree in sign and rough
magnitude — this is not an OOS accident, it is a genuine absence of edge.

Average MAE ≈ −1.8 R, average MFE ≈ +2.0 R: trades routinely swing wide in both
directions before resolving — consistent with a noisy mean-reverting path around
a near-zero drift.

---

## O. Bootstrap results (§18)

Deterministic (`research_engine.BootstrapEstimator`, seed 42; resample count
capped for the large pooled vectors, still ≥ 2 000 iterations).

| vector | observed mean | 95 % CI | verdict |
|---|---:|---|---|
| H8-P1 OOS **gross** | −0.008 | **[−0.039, +0.022]** | EDGE UNCERTAIN (CI crosses zero) |
| H8-P1 OOS **net (0.05)** | −0.128 | [−0.159, −0.099] | NEGATIVE EXPECTANCY (FAILED) |
| H8-P2 OOS gross | −0.010 | [−0.052, +0.031] | EDGE UNCERTAIN |
| H8-P2 OOS net | −0.129 | [−0.171, −0.087] | FAILED |
| H8-P3 OOS net | −0.185 | [−0.252, −0.113] | FAILED |

The gross vectors' CIs straddle zero — there is no statistically supported
*gross* edge either, once the phenomenon is squeezed through a stop/target.

---

## P. Parameter robustness (§19)

Small pre-registered neighbourhood only (no sweep):

| large-bar mult | 1.25 | 1.5 | 1.75 | 2.0 |
|---|---:|---:|---:|---:|
| OOS N | 23 569 | 12 883 | 7 220 | 4 227 |
| OOS net mean R (0.05) | −0.168 | −0.128 | −0.074 | −0.027 |
| OOS CI lower | −0.188 | −0.159 | −0.115 | −0.086 |

| time-stop bars | 4 | 8 | 12 |
|---|---:|---:|---:|
| OOS net mean R | −0.135 | −0.128 | −0.123 |

Profile: **`SHARP_OR_ABSENT`** — every neighbourhood cell is negative. Net rises
monotonically toward zero as the large-bar threshold gets more extreme (fewer,
"cleaner" events) but never crosses zero even at 2.0× ATR, and the sample shrinks
5×. There is no positive plateau to overfit to; the edge is simply absent net of
costs. Time-stop is essentially flat — the outcome is decided in the first ~2
bars.

---

## Q. Cross-asset generalization (§20)

| | AUDJPY | GBPJPY | GBPUSD | EURUSD |
|---|---:|---:|---:|---:|
| OOS N | 3 022 | 3 029 | 3 467 | 3 365 |
| OOS gross E[R] | +0.006 | −0.027 | −0.008 | −0.002 |
| OOS net E[R] (0.05) | −0.114 | −0.143 | −0.129 | −0.127 |
| OOS bootstrap CI (net) | [−0.177, −0.049] | [−0.201, −0.083] | [−0.185, −0.071] | [−0.188, −0.062] |
| temporal both halves > 0 | no | no | no | no |

**Class: `NONE`.** No instrument shows a positive OOS net effect; AUDJPY's gross
is a marginal +0.006 R (CI crosses zero). The phenomenon is neither universal nor
JPY-specific in a tradable sense.

Timeframe comparison (not a primary hypothesis):

| | 15m | 1h |
|---|---:|---:|
| OOS N | 12 883 | 9 770 |
| OOS gross mean R | −0.008 | **−0.113** |
| OOS net mean R (0.05) | −0.128 | −0.232 |
| OOS CI lower (net) | −0.159 | −0.264 |

On **1h the fade is negative even gross** — the reversal lean does not persist at
the lower resolution, so the better ATR-to-cost ratio there does not help.

---

## R. Economic significance (§21)

- Gross OOS expectancy ≈ **−0.008 R**, bootstrap CI [−0.039, +0.022] — within
  noise of zero.
- The Phase 76 effect (~0.05 ATR / 4 bars) is real (you can see it in
  `retest_limit_50` gross +0.077 R) but, expressed against a stop ~0.15–0.5 ATR
  from entry, it is a fraction of one R and smaller than any realistic round-trip
  cost.
- Trade frequency is high (~13 k OOS events across 4 pairs over ~1.2 years of
  15m OOS data) — this is **not** a small-sample problem, it is an effect-size
  problem.
- The pooled cumulative-R "max drawdown" figures (hundreds to thousands of R) are
  **not** a real equity curve — there is no position sizing and each losing fade
  is ≈ −1 R, so a long losing streak accumulates mechanically. The meaningful
  statement is the per-trade expectancy and its CI, both firmly negative.

Statistical detectability (Phase 76) ≠ economic significance (Phase 77). H8 is
the textbook case: a real micro-lean that a spread eats whole.

---

## S. Failure modes

1. **Cost dominance.** The natural fade stop (just beyond the large-bar extreme)
   is tight; `cost_R = cost / risk` is large. Even a 0.025-ATR round-trip cost ⇒
   net negative.
2. **Exit inefficiency.** Full reversion to the event open is a distant target
   with a ~35 % hit rate; fixed-R targets raise the hit rate but the per-win
   payoff then sits far under the cost line. No exit in the pre-registered family
   is both reachable and profitable after costs.
3. **No robust conditioning.** Ranging regime (worse), volatility bucket (flat),
   session (only a thin un-registered LATE_US slice is near breakeven), weekday
   (Wednesday/Sunday marginally less bad, both un-registered and net-negative),
   JPY-cross subset — none is a usable filter.
4. **Gross edge already marginal / TF-fragile.** Pooled gross OOS ≈ 0 with a CI
   spanning zero on 15m, and negative gross on 1h.

---

## T. Limitations

- **No historical spread/tick data.** Costs are a documented assumption plus an
  ATR grid. Real intrabar limit-fill economics (partial fills, queue position,
  spread widening at extremes) are **not** modelled — that is explicitly Phase 78
  scope, and Phase 78 is not recommended.
- **Mid-price OHLCV.** Entries/exits fill at mid; the cost model is the only
  bid/ask proxy. The broker-friction `cost_R` is a pessimistic bound because the
  fade risk distance is small.
- **15m depth ≈ 4 years** (~100 k bars/instrument); OOS window ≈ 1.2 years.
  Cross-year replication is limited. 1h reaches ~8–10 years but the gross effect
  is negative there.
- **Intrabar stop-first assumption** is conservative and slightly understates the
  strategy; it does not change the sign of the result.
- **~10 % of H8 events are dropped** by the setup-validity gates (no stop room /
  no reversion distance). Those are genuinely untradeable as a stop-defined fade;
  including them would only worsen the R statistics.
- MT5 XAUUSD 1m ~3.4-month cap is irrelevant here (H8 is a 15m/1h phenomenon).

---

## U. Final candidate gate (§28)

| Candidate | Asset | Regime | N(oos) | OOS net E[R] (0.05) | OOS gross E[R] | net E[R] broker | PF (net) | bootstrap LB | cost-positive up to | robustness | **Gate** |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| H8 fade | ALL primary | all | 12 883 | −0.128 | −0.008 | −1.32 | 0.82 | −0.159 | none | SHARP_OR_ABSENT | **FAIL** |
| H8 fade | JPY crosses | all | 6 051 | −0.129 | −0.010 | −1.00 | 0.82 | −0.171 | none | SHARP_OR_ABSENT | **FAIL** |
| H8 fade | ALL primary | RANGING | 2 197 | −0.185 | −0.064 | −1.72 | 0.75 | −0.252 | none | SHARP_OR_ABSENT | **FAIL** |
| H8 fade | AUDJPY | all | 3 022 | −0.114 | +0.006 | −1.09 | 0.84 | −0.177 | none | SHARP_OR_ABSENT | **FAIL** |
| H8 fade | GBPJPY | all | 3 029 | −0.143 | −0.027 | −0.90 | 0.79 | −0.201 | none | SHARP_OR_ABSENT | **FAIL** |
| H8 fade | GBPUSD | all | 3 467 | −0.129 | −0.008 | −1.40 | 0.82 | −0.185 | none | SHARP_OR_ABSENT | **FAIL** |
| H8 fade | EURUSD | all | 3 365 | −0.127 | −0.002 | −1.83 | 0.83 | −0.188 | none | SHARP_OR_ABSENT | **FAIL** |

Every cell: **`FAIL`** — negative net OOS expectancy, bootstrap CI entirely below
zero, does not survive the base cost, neighbourhood not stable, not consistent
across sub-periods, cross-asset class `NONE`.
H8-P4 (cost stress): **`DOES_NOT_SURVIVE_REALISTIC_COSTS`**.

---

## V. Phase 78 recommendation

**Do not open Phase 78 for a large-bar-reversal strategy.**

The Phase 76 → Phase 77 chain is now complete: the one directional phenomenon
that survived Phase 76's event study **does not survive execution**. The reversal
lean is real and statistically solid as an *event-study* observation, but it is a
sub-spread effect and there is no pre-registered entry / exit / regime
combination that turns it into positive net expectancy on any instrument, regime,
volatility bucket, session or timeframe tested.

**Volatility context:** conditioning on the volatility bucket did **not** produce
a usable split (`NOT_MATERIAL`), so there is no `VOLATILITY_CONTEXT_SUPPORTED`
label to carry forward from H8. (Phase 76's *non-directional* volatility findings
— clustering, session-open seasonality — remain the better basis for any future
non-trading regime/risk work; that is unchanged by Phase 77.)

**Weak, un-registered curiosities** noted for completeness, explicitly **not**
candidates: `retest_limit_50` entry has the best gross of the family (+0.077 R);
the LATE_US session and Wednesday are the least-bad slices. Each is a single
un-pre-registered cut with a net CI still touching or below zero. Chasing any of
them would be exactly the strategy-shopping §23 forbids.

**Machine learning (§24):** not justified. Phase 77 did not establish a
directional candidate, so `ML_READINESS` stays `DATA_READY_BUT_EDGE_UNCLEAR`.
Only descriptive volatility / regime / session relationships were computed; no
predictive model was trained.

---

## Reproduction

```
python -m phase77_large_bar_reversal          # ~80 s, persists the artifact
pytest tests/test_phase77_large_bar_reversal.py -p no:randomly -q
curl -s localhost:8000/api/research/large-bar-reversal | jq .verdict
```

Deterministic: identical `content_hash` (`041d5601b743…`) on every run. Safety:
frozen holdout hash `7f135a12…76` unchanged and never read; no execution / broker
/ risk import; `LIVE_AUTOMATION_ENABLED = False`.
