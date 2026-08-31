# PHASE 21 — XAUUSD TRUE MULTI-TIMEFRAME STRATEGY CONTRACT
**Frozen Specification & Deterministic Implementation Standard**
**Status**: **FROZEN & LOCKED FOR FORWARD VALIDATION**  
**Asset**: **XAUUSD (Spot Gold / USD)**  
**Live Automation Status**: **DISABLED (PAPER & SHADOW VALIDATION ONLY)**

---

## 1. Executive Summary & Purpose

The objective of Phase 21 is to **freeze the exact algorithmic and mathematical definitions** of the True Multi-Timeframe ICT/SMC Strategy on XAUUSD. This contract eliminates discretion, establishes unambiguous execution rules, protects the untouched historical holdout ($N=82$), and provides a deterministic baseline for forward Paper and Shadow validation.

### Architecture Overview
$$\text{1D Macro Bias} \longrightarrow \text{4H Draw on Liquidity} \longrightarrow \text{15M Setup} \longrightarrow \text{5M Confirmation} \longrightarrow \text{1M Precision Entry} \longrightarrow \text{Risk Gateway} \longrightarrow \text{Paper / Shadow}$$

---

## 2. 1D Macro Bias (Daily Closed Bars)

### 2.1 Purpose
Establishes the macro institutional order flow direction. Only completed Daily candles ($T_{\text{1D}} \le T_{\text{Execution}} - 24\text{h}$) are permitted to establish bias. Intraday incomplete Daily bars are strictly forbidden.

### 2.2 Mathematical Definition
Let $C_{\text{1D}}[t]$ be the close of the most recently completed Daily candle:
1. **Bullish Bias**:
   - Condition A: $C_{\text{1D}}[t] > \text{EMA}_{\text{20}}(C_{\text{1D}})[t] > \text{EMA}_{\text{50}}(C_{\text{1D}})[t]$
   - Condition B: Daily swing structure formed a Higher High ($HH$) and Higher Low ($HL$) over the last 20 completed Daily bars.
   - Output: `1D_BIAS = BULLISH`
2. **Bearish Bias**:
   - Condition A: $C_{\text{1D}}[t] < \text{EMA}_{\text{20}}(C_{\text{1D}})[t] < \text{EMA}_{\text{50}}(C_{\text{1D}})[t]$
   - Condition B: Daily swing structure formed a Lower Low ($LL$) and Lower High ($LH$) over the last 20 completed Daily bars.
   - Output: `1D_BIAS = BEARISH`
3. **Neutral Bias**:
   - If EMAs cross or structure is conflicting: `1D_BIAS = NEUTRAL`.
   - Action: **NO NEW INTRADAY TRADES PERMITTED** until a decisive Daily candle closes.

---

## 3. 4H Draw on Liquidity (DOL) & Target Hierarchy

### 3.1 Purpose
Identifies the higher-timeframe magnetic liquidity pool or imbalance where price is structurally expected to travel.

### 3.2 Identification & Hierarchy
Computed strictly from completed 4H bars ($T_{\text{4H}} \le \lfloor T / 4\text{h} \rfloor \cdot 4\text{h} - 4\text{h}$):
1. **Target Priority 1 (Major Session / Daily Liquidity)**:
   - Previous Day High ($\text{PDH}$) for Bullish bias / Previous Day Low ($\text{PDL}$) for Bearish bias.
2. **Target Priority 2 (Unmitigated 4H Fair Value Gaps)**:
   - Bullish: 4H Bearish FVG low boundary above current price.
   - Bearish: 4H Bullish FVG high boundary below current price.
3. **Target Priority 3 (Equal Highs / Equal Lows — EQH / EQL)**:
   - Swing peaks/troughs separated by $\le 0.15\text{ pips}$ over the last 30 4H bars.
4. **Minimum Distance Requirement**:
   - The selected 4H DOL must offer at least $\ge 2.0\text{R}$ potential reward from the anticipated entry. If distance $< 2.0\text{R}$, setup is rejected with code `REJECT_DOL_DISTANCE_BELOW_2R`.

---

## 4. 15M Setup Development (Liquidity + Structure)

### 4.1 Mechanical Sequence
1. **Liquidity Sweep**:
   - Price must sweep a prominent level (Asian Range High/Low [00:00–07:00 UTC], PDH, PDL, or 15M Swing High/Low) by $\ge 0.10\text{ pips}$ and close back inside the range within $\le 3$ 15M bars.
2. **Market Structure Shift (MSS)**:
   - Following the sweep, price must break the nearest 15M fractal swing high (for Bullish MSS) or fractal swing low (for Bearish MSS) with a full candle body close ($C_{\text{15M}} > \text{Swing High}$ or $C_{\text{15M}} < \text{Swing Low}$).
3. **Displacement FVG**:
   - The MSS candle must display strong displacement (body $\ge 65\%$ of total candle range) creating a 15M Fair Value Gap of minimum size $\ge 0.50 \cdot \text{ATR}_{\text{15M}}$.
4. **Expiration**:
   - The 15M setup remains valid for a maximum of 8 bars ($120\text{ minutes}$) following the MSS candle close.

---

## 5. 5M Optional Confirmation

### 5.1 Purpose & Execution Rule
- **Default State**: `USE_5M_CONFIRMATION = True`.
- Within $\le 3$ 5M bars after the 15M MSS, a 5M displacement candle must form an aligned 5M FVG.
- If 5M confirmation fails or price immediately reverses through the 15M swing low/high, the setup is invalidated.

---

## 6. 1M Precision Execution Trigger

### 6.1 Model D: 1M FVG Limit Entry
1. **Detection**:
   - Following 15M MSS and 5M confirmation, the engine monitors the 1M stream for the first aligned 1M FVG.
2. **Order Placement**:
   - A Limit Order is placed at the **boundary** of the 1M FVG:
     - Long (BUY): Limit price $= \text{High of Candle 3}$ in the 1M Bullish FVG.
     - Short (SELL): Limit price $= \text{Low of Candle 3}$ in the 1M Bearish FVG.
3. **Fill Requirement**:
   - A simulated or live fill occurs ONLY if a subsequent 1M candle low $\le \text{Limit Price}$ (for BUY) or high $\ge \text{Limit Price}$ (for SELL).
4. **Order Lifetime**:
   - The 1M Limit Order expires if not filled within $15\text{ minutes}$ ($15\text{ 1M bars}$) or if price invalidates the 1M swing anchor.

---

## 7. Stop Loss & Target Contract

### 7.1 Structural Stop Loss (`SL-E`)
- **Long**: $\text{SL} = \text{Swing Low of 1M Setup} - 0.50 \cdot \text{ATR}_{\text{1M}}$.
- **Short**: $\text{SL} = \text{Swing High of 1M Setup} + 0.50 \cdot \text{ATR}_{\text{1M}}$.
- **Safety Bounds**:
  - Minimum Stop Distance: $5.0\text{ pips}$ ($0.50\text{ USD}$ on Gold).
  - Maximum Stop Distance: $35.0\text{ pips}$ ($3.50\text{ USD}$ on Gold).
  - If calculated stop $> 35.0\text{ pips}$, trade is rejected with `REJECT_SL_EXCEEDS_MAX_BOUNDS`.
- **Management**: Fixed stop loss upon fill; breakeven adjustment occurs once trade reaches $+2.0\text{R}$.

### 7.2 Take Profit & R-Multiples
- **Minimum Target**: $2.00\text{R}$ (Hard floor).
- **Primary Target**: Fixed $3.00\text{R}$ or the 4H DOL (whichever provides higher structural congruency up to a maximum cap of $7.00\text{R}$).
- **Target Staging**:
  - Take Profit 1 (50% volume): $+2.00\text{R}$ (SL moved to Breakeven $+0.1\text{R}$).
  - Take Profit 2 (50% volume): $+4.00\text{R}$ to $+7.00\text{R}$ or 4H DOL.

---

## 8. Deterministic Risk Gateway

Before any Paper or Shadow order is submitted, the Canonical Risk Gateway validates:
1. **State Gate**: `GLOBAL_KILL_SWITCH == FALSE` and `SYSTEM_STATE in ['PAPER', 'SHADOW']`.
2. **Exposure Gate**: Max symbol positions $\le 1$ for XAUUSD; Max portfolio aggregate risk $\le 5.0\%$.
3. **Trade Risk Gate**: Per-trade risk strictly $\le 1.0\%$ (Default: $0.50\%$).
4. **Cost & Spread Gate**: Current XAUUSD spread $\le 4.0\text{ pips}$. If spread $> 4.0\text{ pips}$ (e.g. during rollover), order is rejected with `REJECT_SPREAD_TOO_HIGH`.
5. **Session Gate**: Active execution permitted only during London ($07:00\text{--}11:00\text{ UTC}$) and London/NY Overlap ($12:00\text{--}16:00\text{ UTC}$).

---

## 9. Paper vs Shadow Execution Parity

- **Paper Execution**: Routes through `CanonicalExecutionRequest(..., broker="PAPER", mode="PAPER")` $\to$ `PaperAdapter` (Simulates fills, records positions to DB).
- **Shadow Execution**: Routes through `CanonicalExecutionRequest(..., broker="SHADOW", mode="SHADOW")` $\to$ `ShadowAdapter` (Evaluates all gates, zero broker transmission, zero DB position pollution).
- **Parity Invariant**: Decisions must match $100\%$ across both modes.

---

## 10. Research Governance & Anti-Data-Mining Rules

1. **Untouched Holdout**: The Phase 20 Holdout dataset ($N=82$) remains permanently locked.
2. **Hypothesis Tracking**: Cumulative hypotheses logged across all research phases: **108**.
3. **Live Automation Invariant**: **`LIVE AUTOMATION IS STRICTLY DISABLED`**.
