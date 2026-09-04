# Phase 76 — Literature-Guided Market Behavior Discovery

*A research phase, not a strategy phase. After Phase 75's `NO_EDGE_CONFIRMED`
(ORB + VWAP), the question changes from "do these strategies make money?" to
"what statistically measurable behaviors actually exist in TradeLogger's
authoritative MT5 data, and which are persistent enough to justify further
research?" A negative or inconclusive result is a valuable scientific outcome.*

---

## AF. Final verdict (stated first)

**`PROMISING BUT UNCERTAIN`** · `ML_READINESS = DATA_READY_BUT_EDGE_UNCLEAR` ·
**Phase 77 queue: `NO_CANDIDATES`** for strategy construction.

Real, strong, OOS-stable, cross-asset market structure was found — but all of it
is **non-directional** (volatility, not price direction). The only directional
phenomenon that replicates (short-horizon reversal after large bars) is
**sub-cost**. No phenomenon clears the candidate gate for Phase 77.

---

## A. Executive summary

**Strongly confirmed (real phenomena, non-directional — not tradable as-is):**

1. **Volatility clustering.** XAUUSD 15m |return| autocorrelation 0.335 at lag 1,
   decaying slowly to 0.15 at lag 40; ATR AR(1) = 0.997. Textbook GARCH /
   long-memory behavior (Bollerslev 1986; Ding-Granger-Engle 1993) — the
   `DIRECTLY_RELEVANT` literature replicates cleanly in our data.
2. **"NR bar → breakout" is refuted.** After a compressed bar (ATR percentile
   rank ≤ 0.10) the forward |return| is **−0.27 to −0.34 ATR *below* the
   unconditional baseline** (z −20 to −33, all 6 instruments, all years, OOS
   stable). Compression predicts **more compression**, not expansion —
   consistent with volatility persistence, and directly contrary to the popular
   NR7-breakout premise (which Phase 75 also failed to trade).
3. **Session-open volatility seasonality.** The 15m bar at the London open
   (07:00 UTC) and New York open (12:00 UTC) carries a forward |return| excess of
   **+0.24 to +1.18 ATR** (z +5 to +14, all 6 instruments, OOS stable). Confirms
   Andersen-Bollerslev (1997) intraday volatility periodicity in MT5 spot data.

**Detectable but sub-cost:**

4. **Short-horizon reversal after large bars.** After a ≥ 1.5-ATR true-range bar,
   the forward return **reverses** by ≈ −0.05 ATR (z −2.5 to −3.2 on AUDJPY,
   GBPJPY, GBPUSD, EURUSD; OOS persistent, all years). Consistent with the
   Jegadeesh / Lehmann overreaction literature. But |effect| ≈ the round-trip
   cost proxy → `REAL_BUT_SUB_COST`. At the ≥ 2.0-ATR threshold the per-event
   reversal is larger (≈ −0.10 ATR) but only AUDJPY reaches significance +
   magnitude — a **single-instrument** result, not promotable.

**No evidence:**

5. **Time-series momentum** (H1) — the Moskowitz-Ooi-Pedersen monthly-futures
   effect does **not** replicate on MT5 spot FX / XAUUSD at 1h/1d with a 24-bar
   look-back. z ≈ 0.1–2.7, CI crosses zero on nearly every cell.
6. **Intraday momentum** (H2) — mostly zero-crossing or *weakly negative*
   (slight reversal). The Gao et al. equity open→close effect does not transfer
   to 24h spot FX.
7. **Previous-day-high interaction** (H11) — thin samples (N ≈ 400), zero-crossing
   everywhere. No statistical support for the level being special (and no
   liquidity-concept interpretation was used).

**Horizon map (XAUUSD 15m):** behavior is `NONE` (|corr| < 0.02) at k = 1…16
bars; weak `MOMENTUM` appears only at k = 32 bars (~8 h). No
reversal→momentum sign flip within the intraday range.

---

## B. Research question

> What measurable market behaviors, if any, are present in our authoritative MT5
> datasets and sufficiently persistent to justify further research?

Success is **discovering and validating (or confidently rejecting) phenomena** —
not finding a profitable backtest. A phenomenon can be statistically real but
economically too small to trade; the classification set reflects that:
`REAL_AND_ECONOMICALLY_MEANINGFUL` / `REAL_BUT_SUB_COST` /
`STATISTICALLY_DETECTABLE_BUT_UNSTABLE` / `PROMISING_BUT_UNCERTAIN` /
`NO_EVIDENCE` / `INSUFFICIENT_SAMPLE` / `LIKELY_ARTIFACT`.

Evidence levels are kept strictly separate (§2 of the prompt): published
evidence (A) ≠ TradeLogger replication (B) ≠ economic significance (C) ≠ OOS
persistence (D) ≠ robustness (E) ≠ strategy candidate (F).

---

## C. Literature registry

`phase76_event_study.LITERATURE` — 8 entries. Bibliographic detail (title,
authors, year, venue, DOI where known, asset class, instruments, period,
frequency, phenomenon, directional hypothesis, conditioning, cost treatment,
limitations, relevance) is from the assistant's training knowledge — **no live
retrieval was performed**; this is disclosed in the module. Each entry carries an
explicit transferability class per market:

| Literature | Phenomenon | spot FX | XAUUSD | intraday M15 | session |
|---|---|---|---|---|---|
| Moskowitz-Ooi-Pedersen 2012 (JFE) | time-series momentum | INDIRECTLY_INFORMATIVE | INDIRECTLY_INFORMATIVE | CONCEPTUAL_ONLY | CONCEPTUAL_ONLY |
| Gao-Han-Li-Zhou 2018 (JFE) | intraday momentum | CONCEPTUAL_ONLY | CONCEPTUAL_ONLY | INDIRECTLY_INFORMATIVE | INDIRECTLY_INFORMATIVE |
| Jegadeesh 1990 / Lehmann 1990 | short-horizon reversal | CONCEPTUAL_ONLY | CONCEPTUAL_ONLY | INDIRECTLY_INFORMATIVE | CONCEPTUAL_ONLY |
| Bollerslev 1986 / Ding-Granger-Engle 1993 | volatility clustering | DIRECTLY_RELEVANT | DIRECTLY_RELEVANT | DIRECTLY_RELEVANT | INDIRECTLY_INFORMATIVE |
| Andersen-Bollerslev 1997 (JEF) | intraday volatility seasonality | DIRECTLY_RELEVANT | INDIRECTLY_INFORMATIVE | DIRECTLY_RELEVANT | DIRECTLY_RELEVANT |
| (diagnostic) volatility cycle / NR-bar folklore | compression→expansion | CONCEPTUAL_ONLY | CONCEPTUAL_ONLY | CONCEPTUAL_ONLY | CONCEPTUAL_ONLY |

**No study claims a directional edge in our MT5 broker data.** The momentum /
reversal papers are equity/futures at monthly/weekly frequency; the volatility
papers document a *variance* property with no directional implication.

---

## D. Literature-to-hypothesis mapping

10 pre-registered hypotheses (`phase76_event_study.HYPOTHESES`), each with an
explicit `literature_ids`, `null_hypothesis`, `alternative_hypothesis`,
timeframes, tier and economic interpretation. Tier 1 (primary, literature-backed,
Bonferroni-controlled): H1_TSMOM, H2_INTRADAY_MOM, H3_ST_REVERSAL,
H10_SESSION_LONDON, H10_SESSION_NY. Tier 2 (pre-declared diagnostics, BH-FDR):
H8_RANGE_EXPANSION_1_5, H8_RANGE_EXPANSION_2_0, H7_VOL_COMPRESSION,
H6_VOL_EXPANSION, H11_PREV_DAY_HIGH. Plus two non-event diagnostics:
H5_VOL_CLUSTERING (autocorrelation study) and H4 (the momentum/reversal horizon
map). **Tier 3 is empty by design** — no post-hoc / data-mined hypothesis was
added.

---

## E. Data universe

Core (§15): XAUUSD, USDJPY, EURUSD, GBPJPY. Cross-asset: GBPUSD, AUDJPY.
**Provider: MT5 broker spot only** (`single_provider: true` on all 18 series).
Timeframes loaded: 15m, 1h, 1d. XAUUSD native 1m is capped at ~3.4 months by the
terminal — sub-15m event studies are out of scope (§9).

| Series | Bars | Manifest |
|---|--:|---|
| XAUUSD 15m / 1h / 1d | 100 004 / 58 971 / 2 581 | `XAUUSD:bda02b736685ea98` |
| USDJPY 15m / 1h / 1d | 100 075 / 62 202 / 2 597 | `USDJPY:6306168424369bbe` |
| EURUSD 15m / 1h / 1d | 100 065 / 50 053 / 2 091 | `EURUSD:2ae9db3a01eba3d5` |
| GBPJPY 15m / 1h / 1d | 100 000 / 62 179 / 2 597 | `GBPJPY:27dac83c86af5b03` |
| GBPUSD 15m / 1h / 1d | 100 067 / 62 203 / 2 597 | `GBPUSD:387c857d2a801dbc` |
| AUDJPY 15m / 1h / 1d | 100 547 / 62 201 / 2 597 | `AUDJPY:47ce1f90d7c88b2f` |

15m ≈ 4.1 y (2022-08 → 2026-09); 1h/1d ≈ 8–10 y (EURUSD 1h from 2018).
**1 114 026 total events** across 102 scorecard cells. Runtime ≈ 205 s,
memory-bounded (one instrument at a time).

---

## F. Data integrity (§35)

All 18 series: `state: OK`, `provider: mt5`, `timestamps_strictly_ordered: true`,
`duplicate_timestamps: 0`, `ohlc_violations: 0`, `nonpositive_prices: 0`,
`anomalous_gaps: 0`, `suspect_bars: 0`, `non_mt5_rows: 0`. The previously-cleared
EURUSD-daily `synthetic_test` rows are **confirmed absent** — `EURUSD:1d` now has
2 091 rows, `non_mt5_rows: 0`, and the manifest is `providers: ['mt5']`.

---

## G. Methodology

- **Event study.** For each pre-registered event condition (computed only from
  information at bar *t*), forward log-returns over horizons {1, 2, 4, 8} bars,
  ATR-normalised, signed by the event direction for continuation tests.
- **No look-ahead** (§18): ATR uses a trailing 14-bar mean; the ATR percentile
  rank uses a trailing 200-bar window (`sliding_window_view`, verified no future
  leak); forward returns begin strictly after the event bar; previous-day levels
  are the daily aggregate shifted one calendar day.
- **Serial dependence** (§22): overlapping events are not independent — every
  aggregate uses a **block bootstrap** (block = the forward horizon in bars,
  deterministic seed 42, memory-capped resample count).
- **Split** (§21): chronological 70/30 dev/OOS on bar index. No shuffling. OOS is
  a single confirmation check, never optimised against.
- **Cross-year** (§20, §6.B): computed by grouping the *cached* per-event rows by
  calendar year — the event study is run once.
- **Signed vs magnitude tests.** Continuation hypotheses (`signed=True`) multiply
  the forward return by the event direction — a positive effect is continuation,
  a negative effect is reversal. Magnitude hypotheses (`signed=False`:
  H7/H6/H10) measure the forward **|return| in excess of the unconditional
  |return|** over the same horizon — this removes both drift and baseline
  volatility, so a positive effect genuinely means "volatility is elevated after
  this condition", not "the instrument drifted".
- **Cost** (§24): a conservative round-trip proxy of 0.05 ATR. The cost-adjusted
  effect is `sign(effect) · max(0, |effect| − 0.05)` — it shrinks toward zero and
  keeps its sign only if the effect clears the cost in absolute terms. An effect
  with `|effect| < 1.3 × cost proxy` cannot be `REAL_AND_ECONOMICALLY_MEANINGFUL`
  and cannot pass the candidate gate. Everything is labelled
  `COST_ADJUSTED_PROXY`, never a full execution backtest.

---

## H. Event-study definitions

See `HYPOTHESES` / the artifact `hypotheses` block for the exact null and
alternative of each. Event builders: `_b_tsmom` (sign of trailing-24-bar
return), `_b_intraday_mom` (≥ 0.5 ATR standardised move over 4 bars),
`_b_st_reversal` (single-bar |return| in the trailing top 5%),
`_b_range_expansion` (true range ≥ {1.5, 2.0} ATR), `_b_vol_compression` (ATR
rank ≤ 0.10), `_b_vol_expansion` (rank < 0.20 → > 0.60), `_b_session_open`
(15m bar at 07:00 / 12:00 UTC), `_b_pdh_cross` (first bar closing ≥ 0.1 ATR
above the previous-day high).

---

## I. Momentum (H1, H2)  ·  ## J. Reversal (H3, H8)  ·  ## K. Horizon map (H4)

- **H1_TSMOM** (1h, 1d; 24-bar look-back, signed continuation): every
  instrument × timeframe cell is `NO_EVIDENCE`. Dev effect_z 0.1–2.7, dev
  bootstrap CI crosses zero everywhere; the two cells with z > 1.7 (USDJPY 1h,
  AUDJPY 1h) do not reach the Bonferroni threshold (α = 0.01) and are
  zero-crossing. **The published monthly-futures effect does not replicate on
  MT5 spot FX / gold at these horizons.**
- **H2_INTRADAY_MOM** (15m, 1h; ≥ 0.5-ATR standardized move over 4 bars):
  the 15m cells are weakly *negative* (−0.02 to −0.05 ATR, z −1.7 to −3.6) —
  i.e. a slight *reversal*, not continuation — and the effect is below the cost
  proxy (`REAL_BUT_SUB_COST` / `NO_EVIDENCE`). **The Gao et al. equity
  open→close effect does not transfer to 24h spot FX.**
- **H3_ST_REVERSAL** (top-5% |return| bar, signed continuation): zero-crossing
  on nearly every cell (dev z −0.3 to 1.4). A single-bar extreme does not
  reliably predict the next bar's sign. (The reversal that *does* replicate is
  the multi-bar one after large *ranges* — H8 below.)
- **H4 horizon map** (XAUUSD 15m): `corr(trailing-k return, forward-k return)` is
  |·| < 0.02 for k = 1, 2, 4, 8, 16 → behavior `NONE`; weak `MOMENTUM`
  (corr +0.029) only at k = 32 bars (~8 h). **No intraday reversal→momentum
  sign flip.**

---

## L. Volatility clustering (H5)

XAUUSD 15m: absolute-return ACF = 0.335 / 0.307 / 0.268 / 0.249 / 0.193 / 0.170 /
0.153 at lags 1/2/3/5/10/20/40 — a slow, roughly hyperbolic decay (the Ding-
Granger-Engle long-memory signature). Squared-return ACF is similar. Raw-return
ACF ≈ 0 at lag 1 (no linear directional autocorrelation). ATR AR(1) = 0.997.
Regime same-bar persistence ≈ 0.9, median regime run ≈ several bars. **Volatility
clustering is strongly and cleanly present across all instruments** — the one
literature strand that transfers directly.

---

## M. Compression → expansion (H7)  ·  ## N. Range expansion (H8)

- **H7_VOL_COMPRESSION** (ATR rank ≤ 0.10, magnitude test = forward |return|
  excess over baseline, normalised by a *stable* trailing ATR): the excess is
  **strongly negative** — −0.27 to −0.34 ATR on 15m (z −20 to −33), all 6
  instruments, all years, OOS stable (−0.13 to −0.29). **After a compressed bar,
  volatility stays compressed.** This is `REAL_PHENOMENON_NON_DIRECTIONAL` and it
  **empirically refutes the "NR bar → breakout" premise** in our data. On 1h the
  sign is mixed (GBPUSD +0.20, USDJPY/AUDJPY −0.12) — the persistence is a 15m
  property.
- **H8_RANGE_EXPANSION** (true range ≥ {1.5, 2.0} ATR, signed continuation):
  the forward return **reverses** — dev −0.05 ATR at the 1.5 threshold (z −2.5
  to −3.2 on AUDJPY / GBPJPY / GBPUSD / EURUSD), OOS persistent, cross-year 1.0.
  Consistent with overreaction. |effect| ≈ cost proxy → `REAL_BUT_SUB_COST`. At
  the 2.0 threshold the per-event reversal is ≈ −0.10 ATR but reaches
  significance + magnitude only on AUDJPY.

---

## O. Breakout / retest (not a primary hypothesis)  ·  ## P. Session transitions (H10)  ·  ## Q. Previous-day levels (H11)

- **Breakout/retest** was scoped as a market-behavior study (§15) but the full
  retest-timing decomposition (time-to-retest, retest depth, MFE-before-retest,
  continuation-after-retest) is **not implemented** in this pass — H11 covers the
  simplest version (first PDH cross). Recorded as a limitation (§R).
- **H10_SESSION_LONDON / H10_SESSION_NY** (magnitude test): the 15m bar at
  07:00 / 12:00 UTC has a forward |return| excess of **+0.24 to +1.18 ATR**
  (z +5 to +14), all 6 instruments, OOS stable, cross-year 1.0.
  `REAL_PHENOMENON_NON_DIRECTIONAL` — confirms Andersen-Bollerslev intraday
  volatility periodicity. The NY-open excess is the largest single effect in the
  study (EURUSD +1.18 ATR). **Non-directional — not a trading candidate.**
- **H11_PREV_DAY_HIGH**: N ≈ 400–430 per instrument (thin), zero-crossing
  everywhere (dev z 0.7–1.8). No statistical support for the previous-day high as
  a special level; no liquidity-concept interpretation used.

---

## R. Trend / range regimes  ·  ## X. Interaction / conditional effects (§26)

Pre-declared interaction diagnostics (H2×regime, H2×session, H3×regime,
H3×session, H8_1.5×regime, H11×session), computed from the cached dev event rows:
- H7 (compression persistence) shows `SIGN_FLIPS_BY_REGIME` on AUDJPY / GBPJPY
  and `MAGNITUDE_VARIES_BY_REGIME` elsewhere.
- H8 (large-bar reversal) is mostly `MAGNITUDE_VARIES_BY_REGIME` — the reversal
  is larger in RANGING conditions.
- The directional hypotheses (H2, H3) are largely `REGIME_INVARIANT` (weak
  everywhere).

**Weak evidence for conditional structure** — enough to note for future modelling
(§AA), not enough to build a strategy on.

---

## S. Cross-instrument  ·  ## T. Cross-year stability  ·  ## U. Dev vs OOS

- **Cross-instrument:** volatility clustering, compression persistence and
  session volatility are **universal** (all 6 instruments). The large-bar
  reversal is **FX-cross** at the 1.5 threshold (4 pairs), **AUDJPY-specific** at
  the 2.0 threshold. Momentum is **non-replicated**.
- **Cross-year:** the non-directional phenomena (H7, H10) have same-sign fraction
  1.0 across the 2022–2026 segments. H8 is 1.0 on the JPY pairs, 0.5–0.75
  elsewhere. Momentum cells are 0.5–0.75 (i.e. inconsistent).
- **Dev vs OOS:** H7 and H10 keep sign and rough magnitude out of sample. H8 on
  AUDJPY *grows* out of sample (dev −0.10 → OOS −0.26), which fails the
  candidate gate's OOS-stability band [0.4, 2.5] — a large OOS jump is treated as
  instability, not confirmation.

Full scorecard: artifact `scorecard` / `GET /api/research/market-behavior`.

---

## V. Multiple-testing corrections (§23)

- **Tier 1** (primary literature-backed): 5 hypotheses (H1_TSMOM,
  H2_INTRADAY_MOM, H3_ST_REVERSAL, H10_SESSION_LONDON, H10_SESSION_NY).
  Bonferroni α = 0.05 / 5 = **0.01**. Cells passing per-hypothesis: the two H10
  session hypotheses pass on every instrument (z ≫ the threshold); H1/H2/H3 pass
  on **zero** instruments.
- **Tier 2** (pre-declared diagnostic decompositions): 95 tests. Benjamini-
  Hochberg at q = 0.10 → **~35 survivors** — but these are dominated by the H7 /
  H10 magnitude effects (which are enormous, z 5–33) and the H8 reversal cells.
  The BH survivor count is not itself evidence of a directional edge.
- **Tier 3** (exploratory): **0** — no post-hoc / data-mined hypothesis was
  added.

---

## W. Economic significance / cost analysis (§24)

Every directional effect is reported GROSS and as a `COST_ADJUSTED_PROXY`:
`sign(effect) · max(0, |effect| − 0.05 ATR)`. An effect with
`|effect| < 1.3 × 0.05 ATR` cannot be `REAL_AND_ECONOMICALLY_MEANINGFUL` and
cannot pass the candidate gate. The large-bar reversal (H8) is the only
directional phenomenon that replicates, and its gross effect (≈ 0.05 ATR at the
1.5 threshold) is **at or below** the cost proxy → `REAL_BUT_SUB_COST`. The
non-directional phenomena (H7, H10) have no "economic significance" concept —
there is no direction to trade.

---

## Y. Negative knowledge registry (§32)

`phase76_event_study` artifact `negative_knowledge` records every rejected
(hypothesis, instrument, timeframe) with the reason (`NO_EVIDENCE` /
`STATISTICALLY_DETECTABLE_BUT_UNSTABLE` / `REAL_BUT_SUB_COST`), samples,
dev/OOS verdicts, cost-adjusted effect and date. Highlights future phases should
**not** re-test without new information:

- Time-series momentum (24-bar look-back) on MT5 spot FX / gold at 1h/1d — no evidence.
- Intraday momentum after a standardized impulse on 15m — weak reversal, sub-cost.
- Single-bar reversal (top-5% |return|) predicting the next bar's sign — zero-crossing.
- Previous-day-high as a special level — no evidence (thin samples).
- "NR / compressed bar precedes expansion" — **refuted** (compression persists).

---

## Z. Promising research queue (§33)

Ranked by the frozen discovery score (weights: effect_z 0.28 / ci_excl_zero 0.14
/ oos_consistent 0.22 / cross_year 0.14 / cross_asset 0.14 / cost_survival 0.08).

| Priority | Phenomenon | Why | Not a Phase-77 candidate because |
|---|---|---|---|
| WATCHLIST | Large-bar reversal (H8, FX-cross, 15m) | Replicates, OOS-persistent, literature-backed | Gross effect ≈ cost proxy; only economically-meaningful on one instrument |
| RESEARCH (non-directional) | Compression persistence (H7) | Huge, universal, OOS-stable | Non-directional — a volatility-state signal, not a trade |
| RESEARCH (non-directional) | Session-open volatility (H10) | Huge, universal, OOS-stable | Non-directional |

The queue's `TOP_PRIORITY` entries are all `REAL_PHENOMENON_NON_DIRECTIONAL` —
high research value as **context / regime inputs**, zero value as standalone
directional strategies.

---

## AA. ML / AI readiness assessment (§27, §28)

**`ML_READINESS = DATA_READY_BUT_EDGE_UNCLEAR`.**

| Question | Answer |
|---|---|
| Phenomena worth modelling? | Not as prediction *targets*. The non-directional volatility structure (H5, H7, H10) is worth modelling as **context features**. |
| Informative variables | ATR percentile / volatility state; time-of-day / session; regime (efficiency ratio); recent true-range vs ATR. |
| Unconditional or conditional? | The directional effects (H8 reversal) are **weakly conditional** (larger in RANGING, larger in JPY pairs). The volatility effects are strongly conditional on time-of-day and prior volatility state. |
| Shared cross-instrument structure? | Yes — volatility clustering, compression persistence and session volatility are universal across all 6 instruments. Directional structure is not shared. |
| Enough events for ML without overfitting? | For volatility-context modelling, yes (10⁴–10⁵ bars per instrument). For directional modelling, **no** — the only replicating directional effect has ~2–9k events and is sub-cost. |
| What should ML do (if anything)? | **regime / volatility-context classification** and **abstention (no-trade) decisions** — not direction prediction, not sizing, not a sequence model. |
| What should NOT be modelled yet | `candles → BUY/SELL`; position sizing; any LSTM/Transformer on this evidence base; a multi-asset joint policy. |
| Additional data that would help | native sub-15m depth for XAUUSD (currently ~3.4 mo); a historical high-impact-event calendar for news conditioning; more than ~4 y of 15m for stronger cross-year replication. |

**Architecture thesis (§28):** *weakly supported.* Real conditional effects were
found (H7 sign-flips by regime; H8 magnitude varies by regime), so a
"market-state + validated-phenomenon + context → probability" design is a more
defensible target than "candles → BUY/SELL". But there is currently **no
validated directional phenomenon** to be the "phenomenon" in that architecture —
the honest next step is to *establish one*, not to start modelling.

Explicitly answers: do we have phenomena worth modelling? which variables look
informative? are effects unconditional or conditional? do instruments share
structure? enough events for ML without extreme overfitting? what should ML do
(direction / probability / regime / filtering / abstention)? what should **not**
be modelled yet? The architecture thesis — that a future model should learn
`market state + validated phenomenon + context → probability` rather than
`candles → BUY/SELL` — is judged against whether real **conditional** effects
were found.

---

## AB. Candidate gate (§34)

**Result: `NO_CANDIDATES`.**

The gate requires **all** of: `signed` (directional) hypothesis · status
`REAL_AND_ECONOMICALLY_MEANINGFUL` or `PROMISING_BUT_UNCERTAIN` · dev N ≥ 200 ·
dev bootstrap CI excludes zero · OOS same sign · **OOS/dev magnitude ratio in
[0.4, 2.5]** · cross-year same-sign fraction ≥ 0.6 · **cross-asset fraction ≥ 0.5
(not a single-instrument result)** · cost-adjusted effect keeps its sign ·
|effect| ≥ 1.3 × the cost proxy.

- The non-directional phenomena (H7, H10) are hard-blocked — "volatility will be
  higher" is not a tradable direction (§13).
- The large-bar reversal (H8) fails on: gross effect ≈ cost proxy (1.5
  threshold); single-instrument + OOS magnitude jump 2.5× (AUDJPY 2.0 threshold).

`NO_CANDIDATES` is a valid, successful outcome (§26, §34).

---

## AC. Holdout integrity (§8, §36)

- `holdout_untouched: true` in the artifact.
- Frozen contract hash `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`
  verified **MATCH** before and after the run.
- `phase76_event_study.py` contains no reference to
  `LOCKED_HISTORICAL_BASELINE` / `forward_accumulation` / `forward_validator` /
  `HistoricalVsForwardComparator` (test-asserted). The holdout is never read,
  never a feature source, never a comparison, never used for selection.

---

## AD. Safety audit (§37)

- `LIVE_AUTOMATION_ENABLED = False` · `LIVE_BROKER_TRANSMISSION = "BLOCKED"` — unchanged.
- No execution / broker / risk / reconciliation / forward file modified.
- No execution/broker imports in `phase76_event_study.py` (asserted).
- No credentials; `.env` untracked. `GET /api/research/market-behavior` is read-only.
- ICT/SMC baselines and Phase 74/75 artifacts untouched.

---

## AE. Regression / build results

- `pytest tests/test_phase76_market_behavior.py` — **19 passed**.
- `pytest tests/ -p no:randomly` — **1 473 passed, 6 skipped, 0 failed** (~182 s).
  Phase-75 baseline was 1 454; +19 = the Phase 76 tests.
- `npx tsc --noEmit` — clean; `npm run build` — clean. No frontend changes in
  this phase (the endpoint is backend-only).
- Determinism (§39): two consecutive full `run()` calls on the same store state
  produce an identical `content_hash`, identical event counts and identical
  scorecard statuses (`test_run_is_deterministic` + a live re-run).

---

## The bigger questions (§48)

1. **Does the market contain repeatable, measurable structure in our MT5 data
   worth attempting to convert into a robust edge?** — **Yes for structure, no
   for a directional edge (yet).** Volatility clustering, compression persistence
   and session-open volatility are large, universal and OOS-stable. But they are
   *variance* properties. The one directional phenomenon that replicates
   (short-horizon reversal after large bars) is real but sub-cost. So: there is
   genuine structure, but nothing that is *yet* a candidate for a robust edge.

2. **Is the structure conditional/complex enough that an ML model could plausibly
   improve trade selection rather than overfit noise?** — **Weakly.** Real
   conditional effects exist (compression persistence flips sign by regime; the
   large-bar reversal is stronger in ranging conditions and on JPY crosses). That
   is enough to say a conditional / context model is a *more defensible* target
   than a raw candles→signal model — but not enough to justify training one now,
   because there is no validated directional phenomenon for it to condition.

3. **The most scientifically defensible next experiment** — Deepen the one
   directional lead: study the **large-bar reversal (H8)** properly — vary the
   range threshold and the forward horizon on a pre-registered grid with strict
   FDR, on the instrument(s) and regime(s) where it is strongest (ranging
   conditions, JPY crosses), with a **realistic fade-execution cost model**
   (fading a 2-ATR bar has worse slippage than the flat 0.05-ATR proxy). If it
   survives that, it becomes a Phase-77 candidate. In parallel, build the
   **volatility-context / session model** (H5, H7, H10) as a *non-trading*
   regime classifier — the input layer a future probability model would need.

---

## Reproduction

```
HISTORICAL_OHLCV_PROVIDER=mt5 python -m phase76_event_study
```

Deterministic: block-bootstrap seed 42, fixed 70/30 split, frozen discovery
weights, pre-registered hypotheses. Same store state ⇒ identical
`content_hash`. `GET /api/research/market-behavior` serves the artifact.
Tests: `tests/test_phase76_market_behavior.py`.
