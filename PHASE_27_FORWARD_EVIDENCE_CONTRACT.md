# PHASE 27 — XAUUSD Forward Validation Evidence Contract & Statistical Review Protocol

## Executive Summary
Phase 27 establishes the formal **Statistical Evidence & Human Review Protocol** for the frozen XAUUSD True Multi-Timeframe ICT/SMC strategy. It defines the mathematical, empirical, and governance standards required to objectively answer:

> **"How much evidence do we actually have that the frozen strategy's forward behavior is consistent with its historical research?"**

---

## 1. Non-Negotiable Research Invariants

1. **Strategy Contract Immutability**:
   * `PHASE_21_XAUUSD_STRATEGY_CONTRACT.md` remains strictly **frozen and immutable**.
   * SHA-256 integrity hash is verified on every evaluation cycle.
   * No automated or post-hoc parameter optimization, threshold adjustment, or SL/TP alteration is permitted.

2. **Locked Historical Holdout Baseline**:
   * The historical holdout reference is permanently locked:
     * $N = 82$ Trades
     * Holdout Expectancy $E[R] = +0.637\text{R}$
     * $95\%\text{ Bootstrap Confidence Interval} = [+0.477\text{R}, +0.817\text{R}]$
     * Win Rate $= 58.6\%$
     * Profit Factor $= 2.52$
     * Median Drawdown $= 3.84\text{R}$, 95th Percentile Stress Drawdown $= 7.15\text{R}$
   * Forward data is **NEVER** pooled into or used to recompute the historical baseline.

3. **Dataset Independence & Isolation**:
   * Historical ($N=82$), Forward Paper, and Forward Shadow datasets remain strictly unpooled.
   * Forward Shadow mode executes in memory with zero database mutation.
   * Paper/Shadow decision parity must remain $100\%$. Any discrepancy halts evaluation with a `PARITY BREACH`.

4. **Permanent Live Safety Barrier**:
   * `LIVE AUTOMATION = DISABLED PERMANENTLY`.
   * `LIVE BROKER TRANSMISSION = BLOCKED`.
   * Reaching Stage 3 criteria grants **ELIGIBLE FOR HUMAN REVIEW** status only. There is no automated promotion mechanism to live trading.

5. **Linguistic & Statistical Precision**:
   * Strictly zero emojis across all UI tabs, buttons, metric cards, and logs.
   * Prohibited certainty terms: "guaranteed", "safe", "will make money", "certain", "proven profitable", "confirmed edge".
   * Mandatory empirical terminology: "observed sample", "statistical uncertainty", "consistent evidence", "insufficient data", "eligible for human review".

---

## 2. Sample Size Reliability Tiers & Evidence Progression

Forward statistical interpretations strictly enforce sample-size power constraints:

| Stage | Sample Size | Classification | Interpretation Constraint |
| :--- | :--- | :--- | :--- |
| **Stage 0** | $N < 30$ | `INSUFFICIENT DATA` | No edge or degradation conclusions permitted. Focus is on data feed quality, execution friction, and pipeline parity. |
| **Stage 1** | $30 \le N < 50$ | `LIMITED SAMPLE` | Early directional indication only. Confidence intervals remain wide; cannot reject baseline consistency. |
| **Stage 2** | $50 \le N < 100$ | `MODERATE SAMPLE` | Intermediate statistical validation across multiple market regimes and volatility cycles. |
| **Stage 3** | $N \ge 100$ | `STRONG EVIDENCE` | Comprehensive sample; eligible for formal human review package if $95\%\text{ CI lower bound} > 0\text{R}$. |

---

## 3. Baseline Consistency Bands

To prevent knee-jerk overreaction to standard variance, forward deviation from $+0.637\text{R}$ is categorized into 4 predefined bands:

* **`CONSISTENT`**: Forward $E[R]$ point estimate is positive and its $95\%\text{ CI}$ substantially overlaps the historical $[+0.477\text{R}, +0.817\text{R}]$ interval.
* **`WATCH`**: Forward $E[R]$ is positive but lower than $+0.40\text{R}$, or sample $N < 30$ prevents strong confirmation.
* **`WARNING`**: Forward $E[R] \le 0.0\text{R}$ with $N \ge 30$, or consecutive drawdown $> 7.15\text{R}$ historical stress ceiling.
* **`CRITICAL`**: Severe drawdown ($> 12.0\text{R}$), persistent negative CUSUM drag ($\le -7.0\text{R}$), or data integrity breach (`INTEGRITY BLOCKED`).

---

## 4. Evidence Classification States

The Research Decision Center outputs one of 6 mutually exclusive states:
1. `COLLECTING` — $N < 30$ forward observations.
2. `EARLY EVIDENCE` — $30 \le N < 50$ with positive expectancy.
3. `FORWARD CONSISTENT` — $N \ge 50$ with forward $E[R] \ge +0.35\text{R}$ and healthy excursion profiles.
4. `FORWARD WATCH` — Early negative drag or execution friction requiring continued observation without parameter mutation.
5. `FORWARD DIVERGENCE` — $N \ge 50$ with persistent negative expectancy or structural breakdown.
6. `INTEGRITY BLOCKED` — Research integrity, contract hash, or pipeline parity anomaly preventing statistical evaluation.

---

## 5. Transparent 100-Point Evidence Score Architecture

The forward evidence score provides an inspectable 0–100 composite index:
* **Statistical Reliability (20 pts)**: Sample size progression toward $N=100$.
* **Expectancy Consistency (20 pts)**: Forward $E[R]$ retention relative to $+0.637\text{R}$ baseline.
* **Confidence Interval Evidence (15 pts)**: Width and lower bound of $95\%\text{ Bootstrap CI}$.
* **Drawdown Health (15 pts)**: Current drawdown proximity to $7.15\text{R}$ stress ceiling.
* **Execution Quality (10 pts)**: 1M FVG limit fill rate ($\ge 85\%$) and timeout rate ($\le 15\%$).
* **Distribution Stability (10 pts)**: Forward MAE ($\le 0.45\text{R}$) and MFE ($\ge 2.50\text{R}$) alignment.
* **Paper / Shadow Parity (5 pts)**: $100\%$ decision match across execution pipelines.
* **Data Feed Integrity (5 pts)**: 0 timestamp gaps and 0 invalid OHLC candle geometries.

---

## 6. Execution vs Strategy Decomposition Protocol

When forward performance diverges from historical expectations, the system decomposes observed variance into:
1. **Strategy Variance**: Losses resulting from filled limit orders where price hit the structural Stop Loss (normal probability).
2. **Missed Entry / Timeout**: Unfilled 1M FVG limit orders after 15 minutes due to rapid price displacement.
3. **Microstructure Friction**: Slippage, spread expansion, or broker execution delay.
4. **Data Feed Anomalies**: Timestamp misalignment or corrupted candle ticks.

---

## 7. Human Review Package Protocol

When Stage 3 criteria are reached ($N \ge 100$, $95\%\text{ CI lower} > 0\text{R}$), the terminal compiles a formal 18-section research review dossier:
* Distinguishes explicitly between `KNOWN` (historical holdout), `OBSERVED` (forward empirical sample), `UNCERTAIN` (statistical error bounds), and `NOT ENOUGH DATA`.
* Only provides `MARK FOR HUMAN REVIEW` action.
* Strictly forbids any live trading activation button or automated bypass.
