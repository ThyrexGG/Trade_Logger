# Phases 109–110: Manual-trading playbook stats and a one-trade-a-day plan

Run 2026-10-09. Code: [`phase109_playbook_stats.py`](../phase109_playbook_stats.py),
[`phase110_daily_plan.py`](../phase110_daily_plan.py). NQ primary, ES cross-check,
1-minute data. Questions fixed before answering; explored on 2023-04 → 2024,
confirmed on 2025 → 2026-10, each against a chance baseline. "Useful" needed
≥ 5 percentage points over chance in both periods with N ≥ 100.

## Answers for 2025 and 2026 (NQ, ES in brackets)

| Question | 2025 | 2026 | Chance / normal | Verdict |
|---|---|---|---|---|
| **Q1 Judas up**: first 30 min took a key high and closed back below by 10:00; the 30-min high holds to 12:00 | 52% (53%) | 46% (35%) | 38–40% (33–35%) | higher, but mostly because price is already further from the high (see below) |
| **Q1 Judas down**: same with a key low; the 30-min low holds to 12:00 | 52% (50%) | 56% (59%) | 43–45% (39–42%) | ES holds up after the distance check; NQ doesn't |
| **Q5** Judas on a big 08:30 news day | 50% / 71% (64% / 60%) | 50% / 40% (33% / 62%) | | 7–11 days a year, too few |
| **Q2** after the first key-level sweep + reclaim, the opposite key level is reached before the sweep extreme breaks | 16% (17%) | 19% (12%) | 17–18% (15–16%) | **same as chance** |
| **Q3** 10:00→12:00 continues the first 30 min | 53% (54%) | 47% (49%) | 50% | coin flip |
| Q3, strong first 30 min (≥ 0.3 ATR) | 57% (56%) | 49% (50%) | 50% | not stable |
| **Q4** pullback IFVG reaches +1R before −1R, all | 49% (51%) | 49% (50%) | 50% | coin flip |
| Q4 with the morning move / against | 52 / 46% (53 / 49%) | 49 / 50% (50 / 50%) | 50% | small in 2025 only |
| Q4 2nd attempt after a stop-out | 48% (51%) | 51% (51%) | 50% | coin flip |
| **Q4 09:40–10:00** | **44% (45%)** | **46% (48%)** | 50% | **worse than chance both years** (but 49–51% in 2023–24) |
| Q4 10:00–10:20 | 54% (54%) | 50% (50%) | 50% | |
| Q4 10:20–11:00 | 49% (52%) | 51% (50%) | 50% | |
| **Q6** small gap (0.1–0.3 ATR) filled by 12:00 / 16:00 | 69 / 72% (72 / 81%) | 70 / 77% (68 / 73%) | | stable, all years |
| **Q6** big gap (≥ 0.3 ATR) filled by 12:00 / 16:00 | 24 / 40% (27 / 43%) | 28 / 34% (24 / 33%) | | stable, all years |

**Distance check on Q1.** Judas days were compared with ordinary days where the
10:00 price sat the same distance from the 30-minute extreme. NQ: +12 points
(2023–24) but −4 points (2025–26). ES lows: +9 / +5 points to noon, +9 / +6 to
the close. Only "ES, key low swept and reclaimed by 10:00 → the morning low
tends to hold" survives, on ~80 days per period.

## Phase 110: one trade a day (rules from 2023–24 only, judged on 2025–26)

At 10:00 take the direction of the first 30 minutes; the first pullback-IFVG
signal in that direction between 10:00 and 11:00; stop beyond the pullback, half
at 1R, rest at liquidity, flat 12:00.

| Plan | Trades on | 2025 | 2026 | 2025–26 total ($100 risk) | Pass |
|---|---|---|---|---|---|
| NQ, every day | 92% of days | +0.00R | −0.08R | −0.04R · −$1,482 | no |
| NQ, strong first 30 min only | 96% of those days | +0.05R | −0.17R | −0.05R · −$755 | no |
| ES, every day | 88% of days | +0.04R | −0.10R | −0.02R · −$962 | no |
| ES, strong first 30 min only | 91% | −0.12R | −0.28R | −0.19R · −$2,210 | no |

## What a manual trader can take from this

1. **Wait until 10:00** for pullback entries: 09:40–10:00 signals were the worst
   in 2025 and 2026 on both markets (44–48% vs 50%), though not in 2023–24.
2. **Don't count on reaching the opposite liquidity:** after a sweep it happens
   only 12–19% of the time, the same as chance. Taking partials early (half at
   1R) fits this.
3. **Small gaps usually fill, big gaps usually don't:** ~70% of 0.1–0.3 ATR gaps
   fill by noon; only ~25% of bigger gaps do. Stable every year.
4. **Entries are a coin flip:** with or against the morning move, 2nd attempt
   or not, the pullback IFVG reaches +1R before −1R about 50% of the time. Any
   edge has to come from trade management (letting winners run, cutting
   losers), not from the entry signal.
5. **On ES, a morning low that swept a key level and was reclaimed by 10:00
   holds a bit more often than normal.** It's a reasonable place for a long's
   stop, but it still breaks ~40–50% of the time.
