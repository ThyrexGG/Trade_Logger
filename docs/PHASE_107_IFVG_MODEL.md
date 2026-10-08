# Phase 107: The user's IFVG model (sweep → inverted FVG → respected-gap entry)

Run 2026-10-09. Code: [`phase107_ifvg_model.py`](../phase107_ifvg_model.py)
(`python -m phase107_ifvg_model`, ~60 min). Rules as the user described them,
with their answers on stop, target, timeframe and equilibrium.

## Verdict

**`NO_EDGE`.** All 32 versions are negative after costs.

| Market | Best version | Mean R | By year |
|---|---|---|---|
| NQ | next gap · stop below 2nd low · all | −0.08 (841) | 2023 −0.26 · 2024 −0.18 · 2025 +0.06 · 2026 +0.03 |
| NQ | next gap · stop below sweep · all | −0.09 (843) | −0.25 · −0.14 · −0.02 · +0.02 |
| ES | IFVG retest · stop below sweep · all | −0.11 (822) | −0.20 · −0.10 · −0.09 · −0.07 |
| FX London | next gap · sweep stop · all | −0.26 (4,237) | |
| FX NY | next gap · sweep stop · all | −0.22 (4,338) | |

- **The equilibrium filter (premium/discount) made it worse everywhere**
  (NQ −0.08 → −0.17R). That matches the user's own trades: only 22% were in
  premium/discount.
- **The next-gap entry beats the IFVG retest on NQ** (−0.08 vs −0.16R).
- **Not better than the opposite direction:** placebo p 0.07–0.90. ES's IFVG
  entries came closest (p 0.08), still not significant.
- **NQ's next-gap versions were slightly positive in 2025–2026** after negative
  2023–2024. Noted as a drift, not an edge; it's only worth watching forward.

## Rules (pre-registered)

1. **Sweep:** a live liquidity level breached (Phase 104 levels).
2. **Inversion:** a 1-minute FVG against the new direction, formed in the 30
   minutes before the sweep, is closed through within 30 minutes.
3. **Entry:** GAP = the next 1-minute FVG in the new direction; IFVG = the
   inverted gap. Price trades back in, and the bar closes respecting it → enter
   at that close. A close through the zone, a new extreme beyond the sweep, or
   30 minutes without a touch cancels it.
4. **Stop:** SWEEP = beyond the sweep extreme; 2ND = beyond the 2nd low/high
   (between the sweep and the inversion).
5. **Exits:** half at +1R, rest at the nearest opposite liquidity ≥ 1.5R (cap
   6R, none → 3R), flat at session end.
6. **Equilibrium:** dealing range = sweep extreme ↔ the opposite extreme of the
   60 minutes before; aligned = longs at/below 50%, shorts at/above.

Markets: NQ, ES (08:30–11:00), FX pairs London and NY. Costs: spread +
slippage + FX commission. One trade per day per instrument.

## Match with the user's trades

Only **4 of 18** user trades had an IFVG-model setup within 10 minutes in the
same direction; in 4 more the model wanted the opposite side. When it matched,
entries and stops were nearly identical (29 Sep: rule stop 89.6 pts vs the
user's 89.8). See [Phase 108](PHASE_108_MY_PATTERN.md) for what the user's
trades actually have in common.
