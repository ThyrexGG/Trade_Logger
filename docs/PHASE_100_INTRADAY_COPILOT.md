# Phase 100 — Intraday Setup Co-Pilot

**Status: COMPLETE.** Read-only decision-support tool. No execution, no
orders, no BUY/SELL output. Frozen Phase-74 Gold holdout never read; live
automation disabled.

## What it is — and what it is not

Phases 70–93 established, across four independent constructions, that
there is **no systematic intraday directional edge** in this data. So this
tool **never tells you to take a trade**. It exists to make discretionary
intraday trading *measurably honest*:

1. **Scan** — flags named structural **conditions** on the latest bar.
2. **Base rate** — for any condition, shows the multi-year forward-outcome
   distribution. Most come out near a coin flip; seeing that plainly is
   the point.
3. **Journal + skill tracker** — logs the setups you take and, after ~30
   resolved, tells you whether *your* selection beats the base rate.
4. **Evaluate** — the interactive card that ties it together for a
   conversation.

## Universe

11 instruments — EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD,
EURJPY, GBPJPY, AUDJPY, XAUUSD — on **15m / 1h / 4h**. (No crypto: the
store has no crypto intraday data.)

## The 16 named conditions

`SWEEP_HIGH`, `SWEEP_LOW` (liquidity sweep — pierce a prior-day / 20-bar
level then close back inside), `RANGE_EXTREME_HIGH/LOW` (close in the
top/bottom 15% of the trailing 20-bar range), `VOL_EXPANSION` /
`VOL_CONTRACTION` (true range ≥ 1.6× / ≤ 0.55× ATR), `SESSION_OPEN_LONDON`
/ `SESSION_OPEN_NY`, `FAILED_BREAKOUT_UP/DOWN`, `PDH_TEST` / `PDL_TEST`
(within 0.25× ATR of the prior-day high/low), `INSIDE_BAR`,
`NARROW_RANGE_7`, `TREND_UP` / `TREND_DOWN`. Each is a frozen, causal pure
function of the bar data.

## Base-rate output

For a condition set on an instrument/timeframe, over ~4–8 years of
history, at horizons {1, 2, 4, 8} bars:

- **up_rate / down_rate** — how often price closed higher / lower
- **median / mean / p25 / p75 forward return**
- **mean |move| in ATR**, **mean favourable / adverse excursion in ATR**
- **verdict**: `NEAR_COIN_FLIP` (|up_rate − 0.5| < 0.04) / `WEAK_SKEW` /
  `NOTABLE_SKEW`, with `__LOW_CONFIDENCE` appended if n < 120
- always: a multiple-testing caveat

**Example (real):** EURUSD 15m, `SWEEP_LOW`, 2,537 historical occurrences —
up-rate 0.50 / 0.51 / 0.52 / 0.54 at h1/h2/h4/h8. `NEAR_COIN_FLIP`. The
"sweep the low then reverse up" setup is, unconditionally, a coin flip on
EURUSD 15m.

## Reward:risk feasibility

`rr_feasibility(base_rate, direction, reward_risk)` — breakeven win rate is
`1 / (1 + RR)`. It compares that to the historical rate price moved your
way in these conditions and returns `PLAUSIBLE_IF_DIRECTION_READ_IS_SOUND`
/ `MARGINAL` / `UNLIKELY_TO_BE_POSITIVE_EXPECTANCY`. **This is a floor
check, not a green light** — it assumes your directional read is as good as
the base rate, which the research says is not reliably true.

## Journal + skill tracker

- `log_setup(instrument, tf, direction, entry, stop, target, tag, thesis)`
  → immutable entry with computed R:R, the conditions + base rate at log
  time, and the current macro-blocker status. Returns a `setup_id`.
- `log_outcome(setup_id, exit_price, note)` → computes realized R
  (signed by direction, in units of the stop distance).
- `skill_report(tag=None)` → for your resolved setups: win rate,
  expectancy in R, total R, and the verdict:
  - `SELECTION_ADDS_EDGE` — your expectancy beat the base-rate reference
    by > 0.15R over ≥ 30 trades. Discretionary skill worth scaling.
  - `MATCHES_BASE_RATE` / `WORSE_THAN_BASE_RATE` — a coin flip would have
    done as well or better. The honest move is to stop or change approach.
  - `INSUFFICIENT_SAMPLE` — under ~30 resolved.

## Data / caching

The shared OHLCV store is a slow remote Postgres (a full-history intraday
pull can exceed its statement timeout). Raw candles are cached to local
parquet under `.cache/phase100/` (gitignored), fetched in bounded time
windows on first use and refreshed **incrementally** (only newer bars).
The `run()` / API path uses only what is already cached and marks the rest
`CACHE_NOT_BUILT`; interactive `evaluate_setup` / `log_setup` will fetch a
single instrument on demand.

Build / refresh the cache:
```
python -m phase100_intraday_copilot --refresh
```
(slow the first time — ~10–40 min for all 33 instrument/timeframe pairs;
fast thereafter).

## Using it with me (interactive)

Describe a setup — "long EURUSD 15m, entry 1.0850, stop 1.0835, target
1.0895, thesis: swept the London low and reclaimed" — and I run
`evaluate_setup`, which returns:

- the conditions active right now
- the base rate for those conditions (all horizons)
- whether your R:R clears the breakeven floor given the base rate
- your track record on that tag
- macro-blocker status
- a blunt summary

We talk through whether it clears *your* criteria. If you take it, log it;
the skill stats accumulate.

## CLI

```
python -m phase100_intraday_copilot --scan 15m
python -m phase100_intraday_copilot --base-rate EURUSD 15m SWEEP_LOW
python -m phase100_intraday_copilot --base-rate XAUUSD 1h VOL_EXPANSION RANGE_EXTREME_HIGH
python -m phase100_intraday_copilot --skill
```

## API

`GET /api/research/intraday-copilot` — the latest persisted universe scan +
sample base rates + skill report. GET-only; `NOT_COMPUTED` until
`python -m phase100_intraday_copilot` has run.

## Determinism

`determinism.match == True` — the scan and base rates are pure functions of
the cached bars.

## The honest bottom line

This tool will not find you an intraday edge, because the research says
there isn't one to find. What it will do is stop you from taking marginal
setups on a hunch, and — over a few months of logged trades — tell you
definitively whether your discretionary judgment adds value. If it does,
that's real and scalable. If it doesn't, you'll have found out cheaply.
