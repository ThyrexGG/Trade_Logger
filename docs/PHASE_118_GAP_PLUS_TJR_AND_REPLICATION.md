# Phases 118 and 117c: combining the gap fade with TJR, and replicating it on the Dow and Russell

Run 2026-10-09. Code: [`phase118_gap_plus_tjr.py`](../phase118_gap_plus_tjr.py),
[`phase117c_replication.py`](../phase117c_replication.py). Follows
[Phase 116–117](PHASE_116_117_CONTEXT_PARTIALS_GAPS.md): fading a big 09:30 gap
toward the previous close from 09:45 was positive in NQ/ES in 2025–26 and ~0 in
2023–24. The user liked it and asked to combine it with TJR's strategy and refine
it. Because the 2025–26 half is no longer a clean holdout, the bar was stricter:
**a refinement counts only if it is positive in both halves and beats the plain fade
in both halves**.

## 118 — TJR pieces added to the gap fade (40 cells, NQ + ES, gap ≥0.5 and ≥0.7)

| Variant | What it adds | Result |
|---|---|---|
| R0 plain fade (reference) | nothing | ≥0.7: NQ +0.06R, ES +0.08R (stop 1:1) |
| R1 + sweep filter | only if a TJR liquidity level on the gap side was swept by 09:45 | 38–83 trades; 2023–24 **worse** than plain (−0.09 to −0.14R vs −0.04R); 2025–26 about the same. Not credited |
| R2 TJR's full 4-step sequence toward the fill | enter only on his sequence, 09:45–10:30, exit at the previous close (full, or half at 1R) | only **12–29 trades**; results swing from −0.6R to +0.6R with intervals spanning ±1R. Not credited |
| Control: TJR sequence **with** the gap | | negative in 2025–26 (−0.2 to −1.1R, 8–18 trades) |

**0 of 40 cells credited.** TJR's filters and entries don't improve the gap fade:
they cut the sample to a handful of trades and make the earlier half worse. The
gap direction is doing the work (the same TJR sequences pointing with the gap lose).

## 117c — does it replicate on other US indices?

Same rules and costs logic on **US30 (Dow)** and **US2000 (Russell 2000)**
(slippage 1.0 / 0.1 points, spreads scaled by each symbol's point size). Pass bar,
fixed in advance: both indices positive after costs in 2025–26 with a drift
t-statistic above 2.

| Big gap ≥0.7, entry 09:45, exit 12:00 | Dow | Russell |
|---|---|---|
| Trades | 124 | 133 |
| Mean per trade, 1:1 stop (2023–24 / 2025–26) | +0.01R / +0.03R | +0.02R / +0.06R |
| Raw drift toward the previous close 2025–26 | +0.08 range (t 1.4) | +0.11 range (t 1.9) |
| Raw drift 2023–24 | +0.03 (t 0.5) | +0.08 (t 1.4) |
| Tight (beyond-the-open) stop, 2025–26 | +0.09R | +0.16R (2023–24: −0.35R) |

**Same direction, about half the size, not enough to pass** (t 1.4 and 1.9 vs the
required 2). Unlike NQ/ES, 2023–24 isn't negative here. Averaged over all four
indices and 3.5 years, the plain 1:1-stop fade is about **+0.05R per trade**
(NQ +0.06, ES +0.08, Dow +0.02, Russell +0.04). The NQ/ES 2025–26 numbers
(+0.13 to +0.18R) look like the top of the range, not the expected value.

## The user's own trades on gap days (18 trades, 24 Sep – 8 Oct 2026)

13 of the 18 were on days with a gap ≥0.5 of the recent range. Seven were toward the
fill, six with the gap. Toward the fill made +$88 (−0.7R), with the gap +$40
(+0.3R). Too few trades to conclude anything; included only so the journal can
keep tracking it.

## Verdict

| Question | Answer |
|---|---|
| Does TJR's setup improve the gap fade? | **No** (0 of 40) |
| Does the gap fade replicate on the Dow and Russell? | **Same direction, half the size, not significant** |
| Realistic size of the plain fade | **~+0.05R per trade** across four indices, 40–55 days a year per index |
| What next? | **Forward-track the plain rule; stop tuning on the same 3.5 years** |

Every further tweak on this data would be fitting noise: with ~100 trades per
index, differences of 0.05R are inside the error. The only clean test left is new
days.

## Rules to forward-track from 2026-10-09 (fixed, no changes while tracking)

1. 09:30 open vs the previous 16:00 close; gap size ≥ 0.7 × the mean RTH range of
   the last 14 sessions.
2. At 09:45, if the gap is still unfilled and price hasn't passed the previous
   close: trade **toward** the previous close.
3. Stop at the same distance as the target (1:1) or beyond the 09:30–09:45 extreme;
   keep the position small, because the 1:1 stop is wide (≈257 NQ points, ≈47 ES).
4. Exit at the previous close, the stop, or 12:00.
5. Log it as a journal note ("Skipped setup" kind for the ones not taken) so the
   result can be scored after 25–50 trades.

## TradingView

`tradingview/big_gap_fade.pine` draws this rule live and on past bars (previous-close
line, BIG-gap label and shading, entry marker with target/stop boxes, results table
and an alert). It is separate from `tjr_sweep_checklist.pine`. See
`tradingview/README.md`.
