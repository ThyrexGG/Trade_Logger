# Phase 105: The sweep + learned-selection study on forex

Run 2026-10-09. Code: [`phase105_fx_selection.py`](../phase105_fx_selection.py)
(`python -m phase105_fx_selection [--fetch]`, ~60 min). Same engine, features,
walk-forward models and pass bar as [Phase 104](PHASE_104_TJR_SELECTION.md)
(leak-fixed version), run on the user's forex pairs.

## Verdict

**Not passed. On forex the setup loses more than on NQ/ES, mainly because of costs.**

| Session | Every setup | Learned picks (logistic) | Learned picks (boosted) | Random pick, same days |
|---|---|---|---|---|
| **London** 02:00–05:00 NY | −0.22R (8,321) | −0.15R (1,306) | −0.16R (1,388) | −0.15 / −0.16R |
| **New York** 08:00–11:00 NY | −0.19R (10,695) | **−0.07R** (1,627) | −0.14R (1,563) | −0.17 / −0.20R |

Test years 2024–2026; trade counts in brackets. All 95% intervals of the
pooled results are below zero.

- **Before costs it's break-even.** Every setup ≈ −0.01R before costs; learned
  picks ≈ +0.01 to +0.06R.
- **Costs ≈ 0.2R per trade.** The typical stop is only ~9 pips (London) /
  ~10.5 pips (NY), while spread + slippage + the account's $5/lot commission
  is ~1.5–2.5 pips. Roughly a fifth of every risk unit goes to costs.
- **Selection:** in the NY session the logistic model's picks were clearly
  better than random (−0.07R vs −0.17R, placebo p < 0.001), the strongest
  selection signal of Phases 104–105. They still lost money (2024 −0.11R,
  2025 +0.02R, 2026 −0.12R). In London, selection added nothing (p ≈ 0.5).
- **No pair and no level type is positive:** by pair −0.15 to −0.27R; by
  level −0.06R (previous day, London) to −0.38R.

## Practical reading

- **Break-even before costs** means the sweep tells you nothing about
  direction on these pairs either. After real costs it's a steady loss.
- **Tight stops are expensive on forex:** with a 9-pip stop, a 2-pip cost is
  0.2R per trade. Any FX approach with stops this tight needs a much bigger
  edge than these setups have.

## Design (pre-registered)

| | |
|---|---|
| Pairs | USDJPY, GBPUSD, GBPJPY, EURUSD, EURJPY (FundedNext MT5, 1-minute, 2023-04 → 2026-10) |
| SMT sibling | GBPUSD↔EURUSD, USDJPY↔EURJPY, GBPJPY→EURJPY, EURJPY→USDJPY |
| Sessions | London: sweeps/entries 02:00–05:00, flat 07:00 · NY: 08:00–11:00, flat 12:00 (NY time) |
| Previous day | FX day, 17:00 → 17:00 New York |
| Costs | bar spread (medians: EURUSD 0.1, GBPUSD 0.4, USDJPY 0.8, EURJPY 1.1, GBPJPY 1.7 pips) + 0.2 pip slippage per market fill + $5/lot commission (0.5 pip USD-quoted, 0.75 pip JPY) |
| Stop / target | sweep extreme + 0.5 pip; 2R |
| Clock check | US 08:30 releases show a 2–5× jump in 1-minute range in every year on every pair, so the broker clock alignment holds for FX too |
| Pass bar | as Phase 104: pooled mean > 0 with CI above 0, beats random pick (p < 0.05), every test year positive |
