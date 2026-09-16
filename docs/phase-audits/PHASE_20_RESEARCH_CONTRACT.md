# PHASE 20 — RESEARCH CONTRACT & MATHEMATICAL STRATEGY SPECIFICATION

**Asset**: **XAUUSD (Spot Gold / USD)**  
**Strategy Version**: **`2.0.0` (True Multi-Timeframe ICT/SMC Model)**  
**Status**: **FROZEN FOR AUDIT**  
**Execution Safety**: **LIVE TRADING AUTOMATION DISABLED**

---

## 1. Mathematical Timeframe Specifications

### 1.1 1D — Macro Directional Context Filter
- **Data Source**: Completed Daily (1D) OHLCV candles strictly prior to the execution timestamp:
  $$\text{Daily Candle Timestamp } T_{\text{Daily}} \le T_{\text{Execution}} - 24\text{ hours}$$
- **Deterministic Indicator / Structure Logic**:
  - **EMA 20 & EMA 50 Slope**:
    $$\text{EMA}_{20}(t) = \alpha_{20} \cdot \text{Close}(t) + (1 - \alpha_{20}) \cdot \text{EMA}_{20}(t-1), \quad \alpha_{20} = \frac{2}{20 + 1}$$
    $$\text{EMA}_{50}(t) = \alpha_{50} \cdot \text{Close}(t) + (1 - \alpha_{50}) \cdot \text{EMA}_{50}(t-1), \quad \alpha_{50} = \frac{2}{50 + 1}$$
  - **Daily Swing Structure**:
    - $\text{Swing High}$: High at bar $i$ where $\text{High}[i] > \max(\text{High}[i-2:i], \text{High}[i+1:i+3])$.
    - $\text{Swing Low}$: Low at bar $i$ where $\text{Low}[i] < \min(\text{Low}[i-2:i], \text{Low}[i+1:i+3])$.
  - **Bias State**:
    $$\text{Bias}_{\text{1D}} = \begin{cases} 
    \text{BULLISH}, & \text{if } \text{Close} > \text{EMA}_{20} > \text{EMA}_{50} \text{ and } \text{Close} > \text{Last Swing Low} \\ 
    \text{BEARISH}, & \text{if } \text{Close} < \text{EMA}_{20} < \text{EMA}_{50} \text{ and } \text{Close} < \text{Last Swing High} \\ 
    \text{NEUTRAL}, & \text{otherwise} 
    \end{cases}$$

### 1.2 4H — Draw on Liquidity & Target Zone
- **Data Source**: Completed 4-Hour (4H) OHLCV candles strictly prior to execution:
  $$T_{\text{4H}} \le \lfloor T_{\text{Execution}} / 4\text{h} \rfloor \cdot 4\text{h} - 4\text{h}$$
- **Draw-on-Liquidity (DOL) Identification**:
  - **Equal Highs/Lows (EQH/EQL)**: Two or more swing extremes within a relative tolerance $\le 0.05\%$ of price.
  - **Unmitigated 4H Fair Value Gap (FVG)**:
    - Bullish FVG: $\text{Low}[i] - \text{High}[i-2] > 0.5 \cdot \text{ATR}_{14}$.
    - Bearish FVG: $\text{Low}[i-2] - \text{High}[i] > 0.5 \cdot \text{ATR}_{14}$.
  - **HTF Dealing Range (Premium / Discount)**:
    $$\text{EQ} = \frac{\text{HTF Swing High} + \text{HTF Swing Low}}{2}$$
    $$\text{Long Trades permitted only when Price} \le \text{EQ} \text{ (Discount)}$$
    $$\text{Short Trades permitted only when Price} \ge \text{EQ} \text{ (Premium)}$$

### 1.3 15M — Setup Development & Liquidity Sweep
- **Data Source**: Completed 15-Minute (15M) OHLCV candles strictly prior to execution:
  $$T_{\text{15M}} \le \lfloor T_{\text{Execution}} / 15\text{m} \rfloor \cdot 15\text{m} - 15\text{m}$$
- **Deterministic Setup Rules**:
  - **Liquidity Sweep**: Price breaches Previous Day High/Low (PDH/PDL), Previous Week High/Low (PWH/PWL), or Asian Range High/Low (00:00–07:00 UTC) by $\ge 0.1\text{ pips}$ and closes back inside the range.
  - **Market Structure Shift (MSS)**: A 15M body close beyond the most recent opposing swing fractal:
    - Bullish MSS: $\text{Close}[i] > \text{Recent Swing High}$.
    - Bearish MSS: $\text{Close}[i] < \text{Recent Swing Low}$.
  - **Displacement Vector**: Impulsive candle where body $\ge 65\%$ of total candle range and $\text{Range} \ge 1.2 \cdot \text{ATR}_{15\text{M}}$.

### 1.4 5M — Optional Confirmation Refinement
- **Data Source**: Completed 5-Minute (5M) OHLCV candles:
  $$T_{\text{5M}} \le \lfloor T_{\text{Execution}} / 5\text{m} \rfloor \cdot 5\text{m} - 5\text{m}$$
- **Confirmation State**:
  - Enabled when `USE_5M_CONFIRMATION = True`.
  - Requires a 5M displacement candle in the direction of the 15M MSS within $\le 3$ bars (15 minutes) of the 15M MSS.
  - If absent and `USE_5M_CONFIRMATION = True`, the setup expires without triggering an entry.

### 1.5 1M — Precision Execution Trigger
- **Data Source**: Live 1-Minute (1M) OHLCV bar at timestamp $T_{\text{Execution}}$.
- **Deterministic Trigger**:
  - Formation of a 1M FVG in the direction of the setup.
  - Limit order placed at the upper boundary (for Long) or lower boundary (for Short) of the 1M FVG:
    $$\text{Entry}_{\text{Long}} = \text{FVG}_{\text{High}}, \quad \text{Entry}_{\text{Short}} = \text{FVG}_{\text{Low}}$$
  - **Midpoint / Consequent Encroachment (CE) alternative**:
    $$\text{Entry}_{\text{CE}} = \frac{\text{FVG}_{\text{High}} + \text{FVG}_{\text{Low}}}{2}$$
  - **Maximum Price Deviation Gate**: $|\text{Fill Price} - \text{Requested Price}| \le 2.0\text{ pips}$. If exceeded, order is rejected (`PRICE_DEVIATION_EXCEEDED`).

---

## 2. Structural Stop Loss & Target Models

### 2.1 Stop Loss Models (Predeclared)
- **`SL-A` (1M Swing)**: Placed $0.5\text{ pips}$ beyond the lowest/highest point of the 1M displacement swing.
- **`SL-B` (5M Swing)**: Placed $1.0\text{ pip}$ beyond the recent 5M swing fractal.
- **`SL-C` (15M Swing)**: Placed $2.0\text{ pips}$ beyond the 15M structural swing.
- **`SL-D` (Swept Liquidity)**: Placed $1.0\text{ pip}$ beyond the absolute high/low of the swept liquidity level.
- **`SL-E` (Structure + Volatility Buffer — Default)**:
  $$\text{SL}_{\text{Long}} = \text{1M Swing Low} - 0.5 \cdot \text{ATR}_{1\text{M}}$$
  $$\text{SL}_{\text{Short}} = \text{1M Swing High} + 0.5 \cdot \text{ATR}_{1\text{M}}$$

### 2.2 Dynamic Target & RR Models (Predeclared)
- **`Target Model A`**: Fixed $2.0\text{R}$.
- **`Target Model B`**: Fixed $3.0\text{R}$ (Default baseline).
- **`Target Model C`**: Fixed $4.0\text{R}$.
- **`Target Model D` (2R/4R Split)**: $50\%$ off at $2.0\text{R}$ (move SL to breakeven), remaining $50\%$ off at $4.0\text{R}$.
- **`Target Model E` (2R/3R/5R Staged)**: $33\%$ at $2.0\text{R}$, $33\%$ at $3.0\text{R}$, $34\%$ at $5.0\text{R}$.
- **`Target Model F` (Structural HTF Target)**: Exit at unmitigated 4H FVG or EQH/EQL with a minimum requirement of $\text{RR} \ge 2.0\text{R}$.

---

## 3. Setup Expiration & Timeout Contracts

- **Maximum Setup Lifetime**: 240 minutes (4 hours) from the 15M liquidity sweep.
- **Maximum Bars Waiting for 1M Trigger**: 15 bars (15 minutes) after 5M confirmation. If no 1M FVG retracement occurs within 15 minutes, state transitions to `EXPIRED`.
- **Session Timeout**: If a trade is not filled by the end of the London/NY overlap session (16:00 UTC), order is cancelled (`SESSION_EXPIRED`).

---

## 4. Execution Governance & Invariants

1. **Deterministic Execution**: Every rule, threshold, and parameter must be 100% reproducible with zero lookahead or stochastic components.
2. **Safety Gating**: Live broker order submission remains **STRICTLY DISABLED**.
3. **Canonical Pipeline Gating**: All order execution validation must pass through `execution_pipeline.submit_order()` with risk limits, symbol mapping, instrument specifications, and reconciliation verification.
