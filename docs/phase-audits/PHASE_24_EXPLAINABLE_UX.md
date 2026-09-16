# PHASE 24 — XAUUSD EXPLAINABLE FORWARD VALIDATION & RESEARCH DECISION UX

## 1. Executive Summary

Phase 24 transforms the TradeLogger research interface from a purely statistical display into an **Explainable Research Decision UX**. Every important metric, decision gate, rejection reason, and multi-timeframe transition is translated into clear, human-understandable terms answering four core questions:

1. **WHAT IS IT?** (Plain-language definition)
2. **IS THIS VALUE GOOD OR BAD?** (Context-aware evaluation based on sample size and thresholds)
3. **WHY DOES IT MATTER?** (Real-world trading and mathematical significance)
4. **WHAT SHOULD I DO / WATCH NEXT?** (Immediate research checkpoints and governance actions)

---

## 2. Frozen Strategy Invariant

The **XAUUSD True Multi-Timeframe ICT/SMC Strategy** remains **strictly frozen and immutable** as defined in `PHASE_21_XAUUSD_STRATEGY_CONTRACT.md`.

- **Pipeline**: `1D Macro Bias -> 4H DOL -> 15M Setup -> 5M Confirmation -> 1M FVG Limit Entry -> Risk Gateway -> Paper/Shadow`
- **Baseline Holdout**: $N = 82$, $E[R] = +0.637\text{R}$, $95\%\text{ CI } [+0.477\text{R}, +0.817\text{R}]$, $\text{WR} = 58.6\%$, $\text{PF} = 2.52$, $\text{Max DD } 3.84\text{R}$, $\text{Stress 95th DD } 7.15\text{R}$.
- **Safety Invariant**: `LIVE AUTOMATION: DISABLED PERMANENTLY`. Broker transmission is blocked.

---

## 3. Universal Metric Explanation System

The system introduces `MetricExplanation` and an expanded `METRIC_CATALOG` covering 34+ technical metrics with structured tooltips, plain-language descriptions, and statistical caveats:

| Metric Category | Key Metrics Covered | Plain English Focus |
| :--- | :--- | :--- |
| **Expectancy & Returns** | `expectancy_r`, `forward_expectancy`, `r_multiple`, `profit_factor`, `win_rate_pct` | Average gain in units of risk; winning efficiency |
| **Statistical Rigor** | `bootstrap_ci`, `sample_size`, `forward_sample_size`, `holdout`, `validation`, `wfo`, `monte_carlo` | Distinguishing real edge from sampling luck |
| **Risk & Drawdown** | `max_drawdown_r`, `drawdown_status`, `mae`, `mfe`, `atr` | Peak equity declines; excursion heat vs expansion |
| **SMC/ICT Mechanics** | `fvg`, `mss`, `sweep`, `dol`, `displacement` | Institutional imbalances, structure shifts, and targets |
| **Execution Quality** | `slippage`, `spread`, `latency`, `fill_rate`, `timeout_rate`, `missed_entry` | Order fulfillment reality vs backtest assumptions |
| **Governance & Drift** | `edge_consistency_score`, `strategy_drift`, `drift_status`, `regime`, `validation_stage` | Multi-component health index and stage roadmaps |

### Sample Size & Confidence Overrides
- **Sample Size Override**: If $N < 30$, metrics cannot be classified as `STRONG` or `CONFIRMED`. They are strictly classified as `INSUFFICIENT DATA` or `PROMISING VALUE — INSUFFICIENT DATA`.
- **Confidence Interval Override**: If the $95\%$ Bootstrap CI crosses zero ($CI_{\text{lower}} \le 0.0 \le CI_{\text{upper}}$), positive expectancy is labeled `UNCERTAIN` or `POSITIVE BUT UNCERTAIN`.

---

## 4. Multi-Timeframe (MTF) Pipeline Explainer

The dashboard features an interactive 5-layer MTF explainer detailing the operational state and purpose of each timeframe:

1. **1D — Macro Bias**: Establishes broad daily directional environment (EMA 20/50 + swing structure). Eliminates counter-trend noise.
2. **4H — Draw on Liquidity**: Identifies institutional target (PDH/PDL/FVG) ensuring $\ge 2.0\text{R}$ reward geometry.
3. **15M — Setup (Sweep + MSS)**: Waits for session liquidity absorption and confirming body close displacement.
4. **5M — Confirmation**: Refines momentum and validates fair value gap formation.
5. **1M — Precision Entry**: Places 1M FVG limit order with 14.5 pip average structural stop loss and 15-minute expiration window.

---

## 5. Entry Rejection & Entry Approval Explanations

### Pre-Trade Entry Rejections
When a setup is blocked, the researcher is presented with:
- **WHAT FAILED**: Specific MTF or execution criteria.
- **WHY IT FAILED**: Quantitative reason for the failure.
- **WHAT RULE CAUSED REJECTION**: Explicit strategy contract rule.

*Supported Rejection Codes*: `NO_DAILY_BIAS`, `NO_VALID_4H_DOL`, `DOL_BELOW_2R`, `NO_LIQUIDITY_SWEEP`, `MSS_NOT_CONFIRMED`, `DISPLACEMENT_TOO_WEAK`, `FVG_TOO_SMALL`, `CONFIRMATION_5M_MISSING`, `NO_1M_FVG_FOUND`, `LIMIT_ORDER_EXPIRED`, `SWING_INVALIDATED`, `RISK_GATE_REJECTED`.

### Entry Approvals ("Why Did We Enter?")
Provides a comprehensive breakdown of the 1D, 4H, 15M, 5M, and 1M layers plus risk parameters that authorized trade execution.

---

## 6. Predefined Governance Checkpoints ("WHAT SHOULD I WATCH NEXT?")

The dedicated **Watch Next Advisor** synthesizes real-time telemetry into prioritized research action items:
1. **Sample Size Accumulation**: Progress toward $N = 30$, $N = 50$, and $N = 100$ milestones.
2. **Execution Health**: Tracking limit order fill rate ($\ge 75\%$) and timeout rate ($\le 20\%$).
3. **Drawdown Tracking**: Monitoring peak-to-trough decline against historical $7.15\text{R}$ stress ceiling.
4. **Excursion Stability**: Rolling MAE/MFE drift verification.
5. **Paper/Shadow Parity**: $100\%$ decision match verification.

---

## 7. Research Integrity & Language Governance

- **Zero Emojis**: Clean, professional typography across all UI views and tables.
- **No Fake Certainty**: Words like "guaranteed", "safe", "will make money", "certain", "proven profitable", and "confirmed edge" are strictly prohibited.
- **8-Point Research Integrity Panel**: Strategy Frozen, Holdout Locked, Forward Isolated, Parity $100\%$, Lookahead $0$, Data Quality Healthy, Hypothesis Firewall Active, Live Automation Disabled.
