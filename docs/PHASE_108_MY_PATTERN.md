# Phase 108: What the user's own trades have in common, coded as a bot

Run 2026-10-09. Code: [`phase108_my_pattern.py`](../phase108_my_pattern.py)
(108a, measures the user's trades) and
[`phase108b_pullback_ifvg.py`](../phase108b_pullback_ifvg.py) (108b, the bot).
Charts of the user's trades: [`phase107b_trade_charts.py`](../phase107b_trade_charts.py)
→ `exports/my_trade_charts/`.

## 108a: the user's 18 NQ/ES trades (24 Sep – 8 Oct 2026)

| Trait | Winners | Losers |
|---|---|---|
| A **pullback gap was inverted** in the minutes before entry | **64%** | 29% |
| Entered 11–53 minutes after 09:30 (median 25) | all | all |
| With the 1-hour trend | 18% | 57% |
| A liquidity level swept first | 55% | 71% |
| Entry in premium/discount | 27% | 14% |

| Attempt that morning | Trades | Total |
|---|---|---|
| 1st | 9 | +$11 |
| 2nd | 6 | +$93 |
| 3rd | 3 | **+$194** (all winners) |

Stops: median ~64 NQ points, usually near the morning extreme. No fixed target;
partial exits in 7 of 16 NQ trades; losers often cut before the full stop.
18 trades is far too few to call any of this a proven edge.

## 108b: the pattern as a bot (pre-registered from 108a + the user's answers)

Pullback-gap inversion on 1-minute bars, entries 09:40–10:30, stop beyond the
last 10 minutes' extreme, half at 1R / rest at the next liquidity level, flat
12:00, max 3 trades a day. Variants: direction ANY vs MORNING (with the
09:30→now move); attempts ALL vs REENTRY (only after an earlier same-direction
signal that morning was stopped out).

| Cell | NQ | ES |
|---|---|---|
| ANY · ALL | −0.12R (1,391) | −0.15R (1,351) |
| **MORNING · ALL** | **−0.07R** (996) | −0.10R (916) |
| ANY · REENTRY | −0.09R (591) | −0.12R (546) |
| MORNING · REENTRY | −0.14R (212) | 0.00R (184) |

**Verdict: `NO_EDGE`.** The morning-direction filter is the most useful single
rule (NQ: −0.12 → −0.07R, 2026 +0.00R). Re-entries alone don't help a bot,
although they were the user's best trades.

### Correction: a look-ahead bug in the first run

The first run counted an earlier signal as "lost" the moment it appeared,
before its stop was hit. That leaked the future, and it made the *opposite* of
the re-entry trade look strongly profitable every year (NQ +0.31R, CI
0.18–0.43). With the loss counted only once the stop is actually hit, that
result disappears (NQ −0.07R). The first run is kept as
`.cache/phase101/phase108/phase108b_result_v1_lookahead.json` for the record.

## Year-by-year, every strategy (best version, after costs, $100 risk per trade)

| Strategy | Mkt | 2023 | 2024 | 2025 | 2026 | Total |
|---|---|---|---|---|---|---|
| Fade the sweep (Ph 104) | NQ | −0.14R | −0.05R | −0.05R | −0.02R | −$5,099 |
| Fade the sweep | ES | −0.26R | −0.15R | −0.01R | −0.02R | −$8,298 |
| Strict TJR 1-min (Ph 103b) | NQ | +0.55R (5) | −0.20R (7) | −0.11R (7) | +0.21R (4) | +$143 |
| Strict TJR 1-min | ES | +0.83R (5) | +0.99R (4) | −0.72R (13) | −0.35R (4) | −$264 |
| Follow + 1h trend (Ph 106) | NQ | −0.12R | −0.07R | −0.20R | −0.02R | −$5,382 |
| Follow + 1h trend | ES | +0.01R | +0.01R | −0.21R | −0.13R | −$4,373 |
| IFVG model (Ph 107) | NQ | −0.26R | −0.17R | **+0.06R** | **+0.03R** | −$6,534 |
| IFVG model | ES | −0.20R | −0.09R | −0.09R | −0.07R | −$8,925 |
| Pattern bot, morning (Ph 108b) | NQ | −0.09R | −0.08R | −0.09R | +0.00R | −$6,508 |
| Pattern bot, morning | ES | −0.10R | −0.11R | −0.07R | −0.12R | −$9,010 |
| FX NY, IFVG model | 5 pairs | −0.27R | −0.23R | −0.17R | −0.20R | −$93,559 |
| FX London, follow + 1h | 5 pairs | −0.34R | −0.28R | −0.19R | −0.30R | −$67,156 |

2023 = from April; 2026 = to 8 Oct. The only multi-year positive stretch is the
NQ IFVG model in 2025–2026, after two losing years. Worth forward-tracking
with the rules unchanged; not tradeable on this evidence.
