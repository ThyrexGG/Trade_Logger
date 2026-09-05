# PROJECT STATE & ARCHITECTURAL RECORD
**TradeLogger Terminal - Living System Memory**
*Last Updated: 3 September 2026, Session 46 (React SPA Migration Stages 4–11 + Stage 10 gate; FX risk fix; Streamlit retirement eval; Stages 12–14 journal/alerts/analytics; Stage 15 Intelligence Layer; Stage 18 Market & Macro Intelligence foundation)*

> **HOW TO USE THIS FILE**
> Start any new AI session with: *"Read PROJECT_STATE.md and continue where we left off."*
> This file is the single source of truth for the project's current state.

---

## 1. What This Project Is

A professional-grade **trading research, journaling, and execution terminal** built for a liquidity-based, ICT/SMC methodology trader. It is NOT a simple trade log — it is a full research + execution stack:

- **Streamlit Desktop Terminal** (`app.py`) — primary UI with dedicated **4-ZONE OPERATIONAL ARCHITECTURE** and **PERSISTENT TELEMETRY RIBBON**:
  - **Zone 1: TRADING WORKSPACE** (Phase 53 Unified Trading Cockpit with 10-asset Watchlist, MTF Context Hierarchy, Dominant Chart Canvas, Docked Risk Gateway Panel, Active Positions Excursion Strip, Real-Time Signal State, Phase 55 Asset Edge Intelligence Scorecard, Phase 56 Deep Macro Intelligence & Economic Surprise Engine, Phase 57 Market Intelligence Scanner & Regime Engine, and **Phase 58 Unified Market Intelligence Command Center**)
  - **Zone 2: RESEARCH & STRATEGY LAB** (Generic Strategy Research, True MTF Lab, USDJPY Empirical Labs, XAUUSD Adversarial Stress Audit, Strategy Sandbox)
  - **Zone 3: FORWARD EVIDENCE & GOVERNANCE** (Phase 54 Unified Forward Evidence & Governance Cockpit with 4-Tier Cognitive Hierarchy, 7 modular tab views, 14-stage milestone progression, Wilson & Bootstrap CIs, unpooled historical baseline comparison, 8-stage pipeline, 8-link forensic chain, and immutable governance snapshots)
  - **Zone 4: OPERATIONS, JOURNAL & AUDIT** (Daily Command Center, Analytics & Overview, Trade Journal, System Health & Paper Operations)
- **Unified Market Intelligence Command Center & UX/UI Refinement** (`market_intelligence_command_center.py`) — Phase 58 institutional research & trading-context command center layer (`COMMAND_CENTER_VERSION = "1.0.0"`) converging all intelligence from Phases 55–57 into a transparent, explainable decision-support dashboard answering *"What is happening, why, which assets are strongest/weakest, what factors agree/conflict, what changed recently, and what should I investigate next?"*:
  - **Top 3-Second Executive Hero Summary Bar**: Primary regime state with confidence & stability, market breadth (Bullish/Bearish/Neutral/Divergent %), macro environment synthesis (USD/EUR strength, policy trajectory, real yields), and system data quality & integrity badge.
  - **"What Matters Right Now?" Executive Shift Cards**: Real-time actionable factor shifts, regime transitions, economic surprises, and divergence alerts.
  - **6-Tab Progressive Disclosure Navigation Suite**:
    - Tab 1: `🎯 Cross-Asset Opportunity Map` (23-asset normalized leaderboard with multi-column sorting, asset-class filtering, quick symbol selector, and data quality gating withholding scores < 40).
    - Tab 2: `🔍 Asset Context Deep Dive` (6-pillar contextual deep profile: Multi-Factor Edge, Dedicated Macro Model, Economic Surprises, Institutional COT, "What Changed?" factor deltas, and transparent factor conflict detection).
    - Tab 3: `🌐 Global Economic Heatmap` (Dense 9-economy $\times$ 5-category macroeconomic matrix with z-score normalized surprises and freshness auditing).
    - Tab 4: `📊 Cross-Asset Correlations` (20D, 60D, 120D rolling correlation matrices with $N \ge 15$ sample size gates and strict non-causality disclaimers).
    - Tab 5: `📜 Regime Transition Ledger` (Immutable chronological transition ledger with confidence metrics and dominant driver provenance).
    - Tab 6: `🛡️ Data Health & Governance` (Feed freshness matrix, immutable snapshot verification ledger `market_intelligence_command_snapshots` with SHA-256 fingerprints, and model versioning).
- **Market Intelligence Scanner, Economic Heatmap & Cross-Asset Regime Engine** (`market_intelligence_scanner.py`, `economic_heatmap.py`, `cross_asset_regime_engine.py`, `market_intelligence_ui.py`) — Phase 57 multi-asset scanning & contextual regime architecture.
- **Macro Intelligence, Economic Surprise & Deep Asset Research Engine** (`macro_intelligence_engine.py`, `macro_change_detector.py`, `asset_edge_scorecard.py`) — Phase 56 macroeconomic intelligence architecture answering 12 core fundamental questions: canonical `EconomicDataRegistry` (20+ indicators, lookahead protection, revision tracking), `EconomicSurpriseEngine` (expectation vs actual, unit-normalized z-scores, qualitative direction, aggregate surprise momentum), `MacroFactorGroupingEngine` (Growth, Inflation, Labor, Monetary Policy, Sentiment/Positioning), `EconomicStrengthEngine` (-100 to +100 economy score for USD, EUR, GBP, JPY), `ForexRelativeStrengthEngine` (currency pair relative macro strength), `XAUUSDMacroContextModel` (dedicated gold macro model synthesizing Real Rates, USD Pressure, Yield Trajectory, Central Bank Demand, COMEX COT), `FactorContributionMatrix` & `FactorConflictDetector`, `DataFreshnessAuditor` (LIVE, FRESH, AGING, STALE, REVISED), "What Changed?" Engine (`MacroChangeDetector`), and 8-tab Market Intelligence layout in Trading Workspace (`OVERVIEW`, `ECONOMIC SURPRISE`, `MACRO FUNDAMENTALS`, `POSITIONING & COT`, `SEASONALITY`, `WHAT CHANGED?`, `DATA QUALITY & AUDIT`, `MARKET RANKING`).
- **Asset Edge Intelligence & Multi-Factor Market Scorecard** (`asset_edge_intelligence.py`, `asset_edge_scorecard.py`) — Phase 55 deterministic multi-factor market intelligence engine (`EDGE_MODEL_VERSION = "1.0.0"`) synthesizing 11 quantitative factor families (Technicals, SMC, Session/Liquidity, Macro, Dollar/Yields, Positioning, Seasonality, Regime, Growth, Inflation, Labor) into a normalized $[-100, +100]$ directional score, data quality scoring, factor conflict analysis, signed "Why?" evidence breakdown, 10-instrument market ranking, and immutable snapshot ledger (`asset_edge_snapshots`).
- **Forward Evidence & Governance Cockpit** (`forward_evidence_cockpit.py`) — Phase 54 quantitative research terminal cockpit replacing ~2,080 lines of legacy monolithic UI with 7 high-density tab views (Overview & Immediate State, Statistics & Uncertainty, Milestone Progression, Stability & Alpha Decay, Observation Pipeline, Forensics & Reconciliation, Governance Ledger), 4-tier cognitive hierarchy (Level 1–4), conservative Wilson score & bootstrap confidence intervals, and fail-closed live safety barrier.
- **Unified Trading Workspace Cockpit** (`trading_workspace_cockpit.py`) — Phase 53 professional institutional terminal layout with 10-instrument scanable watchlist, 6-timeframe hierarchical bias bar (`1D` &rarr; `4H` &rarr; `1H` &rarr; `15M` &rarr; `5M` &rarr; `1M`), docked risk gateway calculation panel, persistent open-positions strip with MAE/MFE excursion tracking, SMC signal state machine, and Phase 55 scorecard integration.
- **Centralized Design System & 15-State Language** (`ui_components.py`) — Standardized CSS design tokens, persistent telemetry ribbon, 15-state badge generator (`STATES_SPEC`), metric KPI cards, section headers, intentional $N=0$ empty states, and fail-closed safety banners.
- **Macro Intelligence & Economic Surprise Audit** (`PHASE_56_MACRO_INTELLIGENCE_AUDIT.md`) — Complete architectural audit of Phase 56 macroeconomic registry, surprise engine, economy strength scoring, gold macro model, "What Changed?" engine, and 651-test regression verification.
- **Asset Edge Intelligence Audit** (`PHASE_55_ASSET_EDGE_INTELLIGENCE_AUDIT.md`) — Complete audit of Phase 55 11-factor intelligence engine, scoring normalization, data quality gates, and 630-test regression verification.
- **Global IA & Design System Audit** (`PHASE_52_GLOBAL_IA_DESIGN_SYSTEM_AUDIT.md`) — Phase 52 architectural verification, persistent telemetry ribbon, 15-state canonical token mapping, 4-zone routing, and browser QA validation.
- **Unified Trading Workspace Cockpit Audit** (`PHASE_53_TRADING_WORKSPACE_COCKPIT_AUDIT.md`) — Complete audit of Phase 53 multi-pane terminal layout, pre-trade risk calculations, and regression baseline.
- **Genuine Forward Observation Validation & End-to-End Operational Proof** (`xauusd_forward_end_to_end_proof.py`) — 9-stage end-to-end forward pipeline coordinator, first genuine observation supervisor ($N = 0 \to 1$ state machine with `THIS IS NOT STRATEGY VALIDATION` disclaimer), 8-link forensic evidence chain tracer, 8-subsystem operational heartbeat evaluator, 5-state root cause diagnostics, and fail-closed live execution safety barrier.
- **Forward Evidence Accumulation & Statistical Monitoring** (`xauusd_forward_statistical_monitoring.py`) — Canonical forward dataset extraction, 18-point metadata verification, metric maturity classification (`OBSERVED_METRIC`, `STATISTICALLY_INFORMATIVE_METRIC`, `DECISION_ELIGIBLE_METRIC`), Wilson score & bootstrap confidence intervals, side-by-side locked baseline ($N = 82$) comparison, non-invasive alpha decay monitoring, 14-stage milestone progression ($N = 0 \to 500$), and immutable milestone snapshot ledger (`xauusd_phase49_statistical_snapshots`).
- **Forward Signal Lifecycle & Integrity Validation** (`xauusd_forward_lifecycle.py`) — Genuine forward signal detection, provenance validation, 9-stage lifecycle state machine, paper/shadow execution bridge, automated reconciliation, and strict dataset isolation.
- **Forward Evidence Collection & First-Observation Readiness** (`xauusd_forward_evidence_collection.py`) — Atomic observation capture with 17-point context metadata, 11-state evidence eligibility gate, cryptographic SHA-256 fingerprint duplicate/replay protection, 6-state first-observation state machine ($N = 0 \to 1$), forensic snapshot recorder, 3-part explainable research narrative, and plain-language morning research summary.
- **Forward Evidence Accumulation & Research Decision Gate** (`xauusd_forward_decision_gate.py`) — 12-tier evidence classification spectrum ($N = 0$ to $N \ge 500$), 14 deterministic research milestones, deterministic research decision gate, historical holdout ($N = 82$) comparative engine, multi-tier bootstrap confidence intervals (90%, 95%, 99%), and immutable milestone snapshot store.
- **Continuous Forward Research Operations Supervisor** (`xauusd_continuous_forward_ops.py`) — Master operational supervisor, automated weekly forward evidence audits, "What Changed This Week?" delta reports, regime-transition drift detection, incident-based alert deduplication, and "Since You Were Away" forensic audit engine.
- **Long-Term Forward Accumulation & Milestone Engine** (`xauusd_forward_accumulation.py`) — Manages clean completed forward observations, creates deterministic checkpoints with SHA-256 fingerprints, tracks sample milestones, computes multi-window rolling statistics, and generates raw expanding performance curves without curve-fitting.
- **Alpha Decay Monitor & Sequential Stability** (`xauusd_alpha_decay_monitor.py`) — Multi-factor evaluation of edge persistence vs structural degradation, tertile/quartile block stability, regime subgroup stability, and pre-monitoring Data Quality Gate.
- **Overnight Experiment & Morning Audit Subsystem** (`xauusd_overnight_experiment.py`) — Explicit overnight collection sessions, 8-subsystem heartbeats, operational outage logging, mathematical lifecycle reconciliation, idempotent writes, zero-observation explanation hierarchy, and Morning-After Research Audit.
- **Master Research Command Center & Observation Inspector** (`xauusd_master_research_command.py`) — 8-subsystem master research health evaluator, 4-quadrant instant operational dashboard, 360-degree forensic observation inspector, and overnight failure-injection resilience suite.
- **Evidence Governance & Independent Reproducibility** (`xauusd_evidence_reproducibility.py`) — Immutable daily snapshots, snapshot delta comparison, independent zero-deviation metric reconstructor, deterministic Markdown/JSON audit export, and 9-pillar governance matrix.
- **Event Traceability & Non-Causal Attribution** (`xauusd_event_traceability.py`) — Standardized proximity buckets, unified chronological timeline, honest non-causal attribution, and 5-pillar daily review.
- **Forward Observation Quality & Quarantine Subsystem** (`xauusd_forward_observation_quality.py`) — Identity/temporal/context/contract auditing, non-destructive quarantine, lookahead horizon partitioning, 0–100 evidence quality scoring index, and daily quality report.
- **News Reliability & Historical Reconstruction Engine** (`xauusd_news_reliability.py`) — Macroeconomic event reconstruction, missed-event detection, provider comparison with truthful offline status (`FOREX FACTORY FEED: UNAVAILABLE`), and global holiday tracking across 7 financial centers.
- **Daily Trading Command Center & Research Journal** (`xauusd_daily_command_center.py`) — Daily pre-market briefing, pre-flight checklist, live operational telemetry, structured research journal, and non-discretionary execution guidance.
- **Central Risk Gateway & Permanent Live Safety Barrier** (`risk_gateway.py`, `execution_pipeline.py`) — Fail-closed live automation barriers: `LIVE_AUTOMATION_ENABLED = False`, `LIVE_BROKER_TRANSMISSION = "BLOCKED"`.
- **Strategy Contract Immutability Guard** (`xauusd_forward_integrity.py`) — Verifies byte-for-byte immutability of `PHASE_21_XAUUSD_STRATEGY_CONTRACT.md` (SHA-256: `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`).

---

## 2. Core Architecture & Backend Files

| File | Phase | Purpose |
| :--- | :--- | :--- |
| `performance_diagnostics.py` | 59 | Sub-millisecond performance telemetry, ProfileTimer context manager, cache hit/miss tracking, and runtime metrics |
| `market_intelligence_command_center.py` | 58, 59 | Unified Command Center: 3s Hero summary, executive shift highlights, 6 progressive disclosure tabs, 6-pillar asset profile engine, snapshot store, memoization |
| `market_intelligence_scanner.py` | 57, 59 | 23-asset normalized universe registry, factor alignment, market scanner, leaderboard ranking, breadth, change detector, snapshot ledger, scan memoization |
| `economic_heatmap.py` | 57 | 9-Economy x 5-Category dense macroeconomic matrix, surprise grid, momentum z-scores, accessible badges and tooltips |
| `cross_asset_regime_engine.py` | 57, 59 | 12-state multi-input contextual regime classifier, 20/60/120 rolling correlation matrices with N>=15 sample size gates, regime snapshot ledger, regime memoization |
| `market_intelligence_ui.py` | 57 | High-density institutional UI suite: Top 3-second summary Hero bar + 8-tab navigation suite |
| `macro_intelligence_engine.py` | 56 | Canonical economic data registry, surprise engine, factor grouping, economy strength scoring, gold macro model, freshness audit |
| `macro_change_detector.py` | 56 | Macroeconomic temporal shift detector, surprise shifts, indicator revisions, transition audit |
| `asset_edge_intelligence.py` | 55 | 11-Factor family multi-factor scoring engine, data quality scoring, factor conflict detector, signed evidence bullets, ranking |
| `asset_edge_scorecard.py` | 55, 56 | Phase 55 multi-factor scorecard UI + Phase 56 8-tab deep macro intelligence layout in Trading Workspace |
| `forward_evidence_cockpit.py` | 54 | Phase 54 quantitative research terminal cockpit (7 modular tab views, 4-tier cognitive hierarchy) |
| `trading_workspace_cockpit.py` | 53 | Phase 53 institutional terminal layout (10-asset watchlist, MTF bias hierarchy, dominant chart, docked risk gateway) |
| `ui_components.py` | 52 | Centralized design tokens, 15-state badge generator, telemetry ribbon, metric cards, section headers, render_html sanitization |
| `app.py` | 1–57 | Master Streamlit terminal (4-Zone Operational Architecture, 15 subviews, persistent telemetry ribbon) |
| `xauusd_forward_end_to_end_proof.py` | 50 | 9-stage pipeline coordinator, N=0->1 supervisor, 8-link forensic chain verifier, operational heartbeat distributor, fail-closed safety barrier |
| `xauusd_forward_statistical_monitoring.py` | 49 | Canonical forward dataset, metric maturity spectrum, conservative CIs, locked baseline comparison, alpha decay monitor, milestone governance |
| `xauusd_forward_lifecycle.py` | 48 | Forward signal detection, provenance validation, 9-stage lifecycle state machine, paper/shadow execution bridge, automated reconciliation |
| `xauusd_forward_evidence_collection.py` | 47 | Observation capture, 11-state eligibility gate, duplicate protection, first-observation state machine, forensics, morning summary |
| `xauusd_forward_decision_gate.py` | 46 | Forward evidence accumulation, 14 sample milestones, 12 evidence tiers, decision gate, comparative engine |
| `xauusd_continuous_forward_ops.py` | 45 | Continuous operations supervisor, weekly research audit, regime transition drift, incident deduplication |
| `xauusd_forward_accumulation.py` | 44 | Clean forward accumulation, checkpoints, 12 sample milestones, 6 rolling windows, expanding curve |
| `xauusd_alpha_decay_monitor.py` | 44 | Conservative alpha decay monitor, sequential blocks, regime stability, data quality gate |
| `xauusd_overnight_experiment.py` | 43 | Overnight collection sessions, 8-subsystem heartbeats, outages, lifecycle reconciliation, morning audit |
| `xauusd_master_research_command.py` | 42 | Master research health hero, 4-quadrant instant dashboard, observation inspector, failure injection |
| `xauusd_evidence_reproducibility.py` | 41 | Immutable daily snapshots, snapshot delta engine, independent metric reconstruction, audit export |
| `xauusd_event_traceability.py` | 40 | Event proximity buckets, chronological timeline, non-causal attribution, 5-pillar daily review |
| `xauusd_forward_observation_quality.py` | 39 | Forward observation quality engine, quarantine table, lookahead auditor, 0–100 evidence quality score |
| `xauusd_news_reliability.py` | 36, 38 | Historical news reconstruction, missed events, provider comparison, 7-center holiday tracking |
| `xauusd_daily_command_center.py` | 35 | Daily pre-flight briefing, checklist, live telemetry, append-only research journal |
| `xauusd_daily_preflight.py` | 34 | Economic calendar providers, fallback calendar, pre-flight readiness checklist |
| `xauusd_market_conditions.py` | 32 | Global bank holiday detector, session tracking, news proximity calculator |
| `xauusd_operational_monitor.py` | 31 | Real-time telemetry, tick/candle freshness, feed continuity classification |
| `xauusd_forward_regime_coverage.py` | 29 | Forward regime coverage, sample size protections ($N < 10, 10-20, 20-30, N \ge 30$), concentration audit |
| `xauusd_forward_stability.py` | 29 | Rolling forward windows (10/20/30/50) & 3-way chronological split (Early, Middle, Recent) |
| `xauusd_forward_execution_stress.py` | 29 | Hypothetical slippage, spread, and fill drop stress models |
| `xauusd_forward_drawdown_audit.py` | 29 | Win/loss streaks, drawdown severity tiers (Normal, Elevated, Stress, Severe), recovery factor |
| `xauusd_forward_reproducibility.py` | 29 | Independent metric reconstruction, dataset fingerprinter, 8 invalidation conditions |
| `xauusd_review_package.py` | 28 | 28-section research audit dossier generator & cryptographic markdown exporter |
| `xauusd_forward_evidence_ledger.py` | 28 | Append-only evidence snapshot ledger (`xauusd_evidence_ledger`) & delta comparison |
| `xauusd_evidence_milestones.py` | 28 | Milestone tracker ($N = 30, 50, 75, 100, 125, 150, 200$), completion metrics |
| `xauusd_review_readiness.py` | 28 | 18-point review readiness checklist & 3-part uncertainty engine (What We Know / Do Not Know / Need Next) |
| `xauusd_research_decision_audit.py` | 28 | Governance decision records (`xauusd_decision_audit_records`) & decision rationale synthesizer |
| `xauusd_forward_evidence.py` | 27 | Forward evidence analyzer, multi-tier bootstrap CIs (90/95/99%), effect size comparator |
| `xauusd_continuous_monitor.py` | 26 | Continuous forward telemetry, rolling expectancy, sequential CUSUM drift detector |
| `xauusd_alert_engine.py` | 26 | Persistent event logging (`xauusd_monitor_events`), severity filtering, explainable alert contract |
| `xauusd_live_state_engine.py` | 25 | Real-time 5-layer MTF pipeline engine (1D, 4H, 15M, 5M, 1M) & Master Decision hero card |
| `research_explanations.py` | 24 | Metric catalog, 15-code rejection hierarchy, 8-point approval trail, strategy vs execution failure classifier |
| `xauusd_research_governance.py` | 23 | Research governance, hypothesis firewall, watch advisors, health matrix, safety barrier |
| `xauusd_forward_statistics.py` | 23 | Forward effect size comparator, cumulative R curves, milestones (2R-7R), holding times |
| `xauusd_execution_quality.py` | 23 | 1M FVG limit execution quality, fill/miss rates, slippage friction |
| `xauusd_forward_integrity.py` | 23 | Strategy freeze guard (`FrozenStrategyMutationException`), forward provenance ledger |
| `xauusd_validation_gate.py` | 22 | 4-stage governance decision gates (Stage 0 to Stage 3), eligibility evaluator |
| `xauusd_drift_detector.py` | 22 | Distribution drift (MAE/MFE/Duration), drawdown tiers, edge consistency score (0-100) |
| `xauusd_forward_validator.py` | 21, 22 | XAUUSD True MTF frozen strategy engine, forward journal persistence, paper/shadow parity |
| `xauusd_audit_engine.py` | 20 | 6-Model execution benchmark, structural SL sensitivity, parameter perturbation surface, 10k Monte Carlo |
| `true_mtf_engine.py` | 19 | True Multi-Timeframe (1D->4H->15M->5M->1M) engine, 18-state machine, 16-asset universe |
| `usdjpy_conditional_validation.py` | 18 | USDJPY regime-conditional validation (5k permutation, 5k Monte Carlo, rolling WFO) |
| `usdjpy_edge_discovery.py` | 17 | USDJPY 27-condition discovery engine, excursion analyzer, holding-time profiler |
| `usdjpy_continuation_research.py` | 16 | USDJPY 12-condition trend-continuation ablation suite |
| `usdjpy_research.py` | 15 | USDJPY 12-condition reversal ablation suite |
| `research_engine.py` | 14 | 3-Layer splitter (Train/Val/Holdout), multiple testing tracker, bootstrap 95% CI estimator |
| `database.py` | 1–57 | Multi-tenant SQLite + PostgreSQL database abstraction with dialect-safe placeholders |
| `risk_gateway.py` | 9, 12A | Central risk gateway (fail-closed, directional correlation, floating daily loss) |
| `execution_pipeline.py` | 9, 12A | Canonical execution state machine (atomic DB mutex claims, risk reservations) |

---

## 3. Database Schema Summary (Phase 1 to Phase 57)

| Table | Key Columns |
| :--- | :--- |
| `market_scanner_snapshots` | `snapshot_id`, `timestamp`, `universe_count`, `breadth_json`, `rankings_json`, `changes_json`, `model_version`, `data_fingerprint`, `created_at` |
| `market_regime_snapshots` | `snapshot_id`, `timestamp`, `primary_regime`, `secondary_regime`, `confidence_pct`, `confirming_json`, `conflicting_json`, `driver_weights_json`, `data_quality_score`, `data_quality_rating`, `model_version`, `data_fingerprint`, `created_at` |
| `asset_edge_snapshots` | `snapshot_id`, `symbol`, `timestamp`, `overall_score`, `bias_direction`, `quality_score`, `factor_scores_json`, `model_version`, `data_fingerprint` |
| `xauusd_phase49_statistical_snapshots` | `snapshot_id`, `timestamp`, `completed_count`, `wilson_lower`, `wilson_upper`, `bootstrap_mean`, `baseline_delta_er`, `data_fingerprint` |
| `xauusd_phase47_observations` | `observation_id`, `signal_id`, `timestamp`, `direction`, `entry_price`, `sl_price`, `tp_price`, `context_json`, `eligibility_status`, `data_fingerprint` |
| `xauusd_evidence_ledger` | `snapshot_id`, `timestamp`, `total_observations`, `completed_trades`, `expectancy_r`, `win_rate`, `profit_factor`, `data_fingerprint` |
| `xauusd_decision_audit_records` | `record_id`, `timestamp`, `decision_type`, `decision_action`, `rationale`, `actor`, `evidence_snapshot_id` |
| `xauusd_quarantined_observations` | `observation_id`, `timestamp`, `quarantine_reason`, `severity`, `status` |
| `xauusd_news_snapshots` | `snapshot_id`, `target_date`, `provider_name`, `provider_status`, `events_count`, `fingerprint`, `events_payload` |
| `closed_trades` | `trade_id`, `account_id`, `symbol`, `type`, `volume`, `entry_time`, `exit_time`, `profit`, `risk_r` |

---

## 4. Phase Milestones & Execution Summary

| Phase | Description | Status | Test Result |
| :--- | :--- | :--- | :--- |
| **Phases 1–12B** | Core Terminal, Execution Pipeline, MTF Strategy Engine, Risk Gateway, USDJPY Labs | ✅ COMPLETE | Full Suite Passed |
| **Phases 13–20** | True MTF Discovery, 16-Asset Universe, XAUUSD Adversarial Audit, Holdout Baseline | ✅ COMPLETE | Full Suite Passed |
| **Phase 21** | Frozen XAUUSD Strategy Contract (SHA-256: `7f135a...`) | ✅ COMPLETE | Contract Locked |
| **Phases 22–29** | Forward Validation, Explainability, Governance, Ledger, Milestones, Stress, Stability | ✅ COMPLETE | Full Suite Passed |
| **Phase 30** | Forward Validation UI Ungating & Database Compatibility | ✅ COMPLETE | 15 Passed |
| **Phase 31** | Forward Operational Verification, Data Lifecycle & Safety Restart Recovery | ✅ COMPLETE | 16 Passed |
| **Phase 32** | Market Conditions, Global Holidays (7 Centers) & Pre-Flight Engine | ✅ COMPLETE | 17 Passed |
| **Phase 33** | Live Market Data Feeds & Web E2E Navigation Audit | ✅ COMPLETE | 20 Passed |
| **Phase 34** | Economic Calendar Provider Architecture & Daily Pre-Flight Checklist | ✅ COMPLETE | 16 Passed |
| **Phase 35** | XAUUSD Daily Command Center, Live Telemetry & Structured Research Journal | ✅ COMPLETE | 13 Passed |
| **Phase 36** | News Reliability, Market Closure Auditing & Decision Audit History | ✅ COMPLETE | 11 Passed |
| **Phase 37** | Forward Operational Monitoring & Non-Loss Setup Lifecycle Provenance | ✅ COMPLETE | 10 Passed |
| **Phase 38** | Historical News Reconstruction, Missed Events & Regime Correlation | ✅ COMPLETE | 28 Passed |
| **Phase 39** | Forward Observation Quality, Quarantine Subsystem & Lookahead Auditor | ✅ COMPLETE | 11 Passed |
| **Phase 40** | News Event Traceability, Chronological Timeline & 5-Pillar Daily Review | ✅ COMPLETE | 8 Passed |
| **Phase 41** | Research Evidence Governance, Immutable Snapshots & Reproducibility | ✅ COMPLETE | 10 Passed |
| **Phase 42** | Master Research Command Center, Observation Inspector & Overnight Hardening | ✅ COMPLETE | 7 Passed |
| **Phase 43** | Overnight Experiment Live Collection, Liveness Heartbeats & Morning Audit | ✅ COMPLETE | 13 Passed |
| **Phase 44** | Long-Term Forward Accumulation, Rolling Stability & Alpha Decay Monitoring | ✅ COMPLETE | 15 Passed |
| **Phase 45** | Continuous Forward Operations, Weekly Audits, Regime Transition Drift & Incident Deduplication | ✅ COMPLETE | 12 Passed |
| **Phase 46** | Forward Evidence Accumulation, 14-Stage Sample Milestones & Research Decision Gate | ✅ COMPLETE | 15 Passed |
| **Phase 47** | Forward Evidence Collection, Real-Time Observation Capture & First-Evidence Readiness | ✅ COMPLETE | 17 Passed |
| **Phase 48** | Forward Signal Lifecycle & Evidence Integrity Validation (Provenance to Outcome) | ✅ COMPLETE | 18 Passed |
| **Phase 49** | Forward Evidence Accumulation & Statistical Monitoring | ✅ COMPLETE | 22 Passed |
| **Phase 50** | Genuine Forward Observation Validation & End-to-End Operational Proof | ✅ COMPLETE | 18 Passed |
| **Phase 51** | UX/UI, Product Experience & Trading Terminal Design Audit | ✅ COMPLETE | Comprehensive Audit & Spec |
| **Phase 52** | Global IA & Centralized Design System Implementation (15-State Language) | ✅ COMPLETE | 14 Passed |
| **Phase 53** | Unified Trading Workspace Cockpit (10-Asset Watchlist & Pre-Trade Gateway) | ✅ COMPLETE | 16 Passed |
| **Phase 54** | Unified Forward Evidence & Governance Cockpit (4-Tier Cognitive Hierarchy) | ✅ COMPLETE | 18 Passed |
| **Phase 55** | Multi-Factor Asset Edge Intelligence & Scorecard Engine (11 Factor Families) | ✅ COMPLETE | 21 Passed |
| **Phase 56** | Macro Intelligence, Economic Surprise & Deep Asset Research Engine | ✅ COMPLETE | 21 Passed |
| **Phase 57** | Market Intelligence Scanner, Economic Heatmap & Cross-Asset Regime Engine | ✅ COMPLETE | 45 Passed |

---

## 5. Non-Negotiable Invariants Status

1. **Strategy Contract Immutability**:
   - `PHASE_21_XAUUSD_STRATEGY_CONTRACT.md` SHA-256: `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` (**VERIFIED & FROZEN**).
2. **Historical Holdout Baseline**:
   - $N = 82$, $E[R] = +0.637\text{R}$, $95\%\text{ CI} = [+0.477\text{R}, +0.817\text{R}]$, $\text{Win Rate} = 58.6\%$, $\text{Profit Factor} = 2.52$ (**PERMANENTLY LOCKED & UNPOOLED**).
3. **Dataset Separation**:
   - $IDs_{hist} \cap IDs_{paper} = \emptyset$, $IDs_{hist} \cap IDs_{shadow} = \emptyset$ (**VERIFIED DISJOINT**).
4. **Live Trading Safety Barrier**:
   - `LIVE_AUTOMATION_ENABLED = False`, `LIVE_BROKER_TRANSMISSION = "BLOCKED"` (**FAIL-CLOSED PERMANENTLY**).
5. **Lookahead Protection**:
   - Macroeconomic actual figures are strictly masked prior to release timestamps.
6. **Data-Snooping Guard**:
   - Forward observations are strictly out-of-sample evidence; zero post-hoc parameter optimization or strategy mutation.
7. **Non-Loss Invariant**:
   - Limit timeouts $\neq$ losses, Invalidations $\neq$ losses, Rejections $\neq$ losses.

---

## 6. Full Test Suite Regression Benchmark

```bash
=========================== test session starts ===========================
platform win32 -- Python 3.14.7, pytest-9.1.1

tests/  (tracked suite: phases 11–62, FastAPI Stage 2/3/3.5, React migration
         adapters Stage 10/11, forex position sizing)
=========== 898 passed, 2 skipped, 0 failed in 75s ===========
```
*(Tracked `tests/` directory: **898 passed, 2 skipped, 0 failed**. A full-tree run
also collects two gitignored root-level scratch files — `test_backtester.py::test_lot_rounding`
and `test_ws.py::test_websocket_stream` — which fail for pre-existing, migration-unrelated
reasons: an untouched backtester rounding assertion and a missing `pytest-asyncio`
registration. See `docs/STAGE_10_FINAL_INTEGRATION_PERFORMANCE_GATE.md` §4.)*

---

## 7. Performance & Latency Engineering (Phase 51-59 Optimization)

- **Phase 59 Measured Subsystem Speedups**:
  - `CrossAssetRegimeEngine.evaluate_regime()`: Warm query dropped from **2,700 ms** to **0.01 ms** (270,000x speedup).
  - `MarketScannerEngine.scan_universe("ALL")` (23 assets): Warm query dropped from **8,422 ms** to **0.00 ms** (>800,000x speedup).
  - `UnifiedMarketIntelligenceAggregator.aggregate_market_state()`: Cold query dropped from **8,803 ms** to **1,052 ms** (8.4x speedup); warm query dropped to **0.01 ms** (880,000x speedup).
- **Sub-Millisecond Thread-Safe In-Memory Memoization**:
  - `_SCAN_CACHE` (4s live TTL, timestamp-keyed historical lookahead-protected cache) in `market_intelligence_scanner.py`.
  - `_REGIME_CACHE` (4s live TTL, timestamp-keyed historical lookahead-protected cache) in `cross_asset_regime_engine.py`.
  - `_AGGREGATOR_CACHE` & `_PROFILE_CACHE` in `market_intelligence_command_center.py`.
  - `_PRICE_CACHE` (4s TTL) and `get_batch_prices()` in `market_data.py` with instant zero-lag price fallbacks.
  - `_YF_TECH_CACHE` (60s TTL) in `ml_trainer.py` for RSI and EMA spread technical indicators, eliminating repeated synchronous HTTP requests during model inference.
- **SQLite Database Composite Indices**:
  - `idx_cmd_snapshots_ts ON market_intelligence_command_snapshots(timestamp DESC)`
  - `idx_regime_snapshots_ts ON market_regime_snapshots(timestamp DESC)`
  - `idx_scanner_snapshots_ts ON market_scanner_snapshots(timestamp DESC)`
- **Lazy Tab Rendering (`st.pills` / `st.session_state`)**: Eliminated monolithic evaluation of all tabs on every rerun pass. Only the active view executes rendering and queries, reducing Python render CPU time by >85%.
- **Transactional Consistency Preserved**: `database.get_open_positions()` and `database.get_closed_trades()` default to fresh DB reads to prevent stale state anomalies during order submission and risk gateway checks.

---

## 8. FastAPI Migration — Stage 3.5 Read-Path Latency Optimization

Adapter-layer only. No change to authoritative Python engines, strategy mathematics,
`evaluate_trade_risk()`, dataset definitions, Strategy Contract SHA-256, or the
FastAPI/Streamlit architecture. Each sub-stage is a single focused commit with
measured before/after (in-process `TestClient`, live Postgres) and a dedicated
`tests/test_stage35*.py` suite.

| Sub-stage | Endpoint(s) | Mechanism | Warm P50 before → after |
| :-- | :-- | :-- | :-- |
| 3.5A | `/api/market/snapshot/{sym}`, `/api/preferences`, `/api/positions` | single-symbol snapshot bypass; `user_preferences._PREFERENCES_CACHE` (thread-safe process cache); `database.get_open_positions(ttl_sec=2.0)` | see Stage 3.5A commit |
| 3.5B | `/api/watchlist` | bounded concurrent price batching + aligned `_PRICE_CACHE` TTL | ~cold → sub-50 ms warm |
| 3.5C | `POST /api/risk/preview` | reuse 2 s open-position cache; opt-in `get_pair_correlation(ttl_sec=300)` memo (preview path only; execution gate stays uncached) | ~1,530 ms → ~2.5 ms |
| 3.5D | `GET /api/forward-evidence/state` | `Phase49MonitoringFacade.get_cached_forward_state_snapshot()` — bounded, thread-safe, process-local, 60 s TTL, explicitly invalidated by `record_milestone_snapshot()`. Read path no longer calls `Phase50Facade.get_phase50_full_state()` (unused by the response) → eliminates ~15.3 s Phase 50 work, ~3.1 s duplicate Phase 49 work, and the per-GET `xauusd_phase50_operational_audits` INSERT | ~14,650 ms → ~2.3 ms (cold ~1.6 s) |

**Stage 3.5D audit-write correction**: the `xauusd_phase50_operational_audits`
INSERT lives in `Phase50E2EOperationalProofEngine.audit_end_to_end_pipeline()` and
represents an operational-pipeline audit event. It was firing on every read poll of
`/api/forward-evidence/state`. It is **not deleted** — it still runs when the
Streamlit Forward Evidence & Governance cockpit calls `load_cockpit_state()` or an
explicit pipeline audit is invoked. The read endpoint simply no longer triggers it,
so UI polling can no longer manufacture duplicate audit records.




---

## 9. React SPA Migration (Stages 4–11) & Stage 10 Final Integration Gate

**Architecture:** `React 19 + TypeScript + Vite + Tailwind (frontend/)` → typed
`fetch` API client → **FastAPI adapter** (`api/`, run on :8000 / :8010 in dev) →
authoritative Python engines → SQLite/Postgres. React is presentation only; the
adapter reproduces no calculation, research, evidence, risk or safety logic.
Streamlit (`app.py`, :8501) remains the operational golden reference and was not
modified by any migration stage.

**Migrated surfaces (all sidebar items `status: 'live'`, no placeholder pages left):**

| Stage | Commit | Surface |
| :-- | :-- | :-- |
| 4 | `f4501ff` | React foundation + health screen |
| 5 | `5fbf8f2` | App shell, 4-zone navigation, Ctrl/Cmd+K command palette, telemetry ribbon |
| 6 | `854af3a` | Watchlist + Market Snapshot (`/workspace`, `/workspace/market`) |
| 7 | `960acb7` | Risk Gateway + lot-size calculator (`/workspace/risk`) — `POST /api/risk/preview`, calculation-only |
| 8 | `0396d5e` | Market Intelligence command center + Asset Intelligence + Opportunity Map + Economic Heatmap (`/research/intelligence`, `/research/intelligence/asset/:symbol`) |
| 9 | `b40450b` | Forward Evidence + Statistical Surveillance + Governance (`/evidence`, `/evidence/{forward,statistics,governance}`) — widened `/api/forward-evidence/state` pass-through |
| 10* | `6af8f7c` | Strategy Lab + Backtesting (`/research/strategy`, `/research/backtest`) — new adapter `GET /api/research/strategy`, `POST /api/research/backtest` (research-only, fail-closed) |
| 11* | `c478dba` | Positions + Journal + Audit + Operations overview + System Health (`/workspace/positions`, `/operations`, `/operations/{journal,audit,system}`) — new adapter `GET /api/operations/{journal,audit,system}` |
| risk fix | `d23a54f` | Currency-aware FX position sizing & margin in `risk_gateway.py` (see below) |
| Gate | *(this session)* | Stage 10 final integration / performance / regression / parity / safety audit — `docs/STAGE_10_FINAL_INTEGRATION_PERFORMANCE_GATE.md` |

\* The user's incremental master-prompt numbering; the roadmap in
`docs/REACT_MIGRATION_AUDIT.md` §6 folds these into its Stages 8–9 plus the final
gate (its "STAGE 10").

**FastAPI adapter endpoints (18 total):** 14 GET (health, watchlist, market
snapshot, preferences, 4× intelligence, positions, forward-evidence state, 3×
operations, research strategy), `PUT /api/preferences` (UI layout only — predates
the migration), `POST /api/risk/preview` (calculation-only), `POST /api/research/backtest`
(research-only). **No order / execute / close / modify / cancel / transmit /
automation endpoint exists.**

**Stage 10 gate result — ✅ PASS:**
- Backend regression: tracked `tests/` = **898 passed, 2 skipped, 0 failed**; the
  2 full-tree failures are gitignored scratch files, pre-existing and unrelated.
- Frontend: `tsc -b` clean; production build clean (431.81 kB JS / 119.20 kB gzip;
  no chart lib, no Axios/React-Query/Redux/Zustand/WebSockets).
- Browser QA: 18/18 routes render with real backend data, **0 console errors, 0
  exceptions**, no body overflow at 1920/1440/1280/390.
- Network QA: no N+1, no fetch loops, no per-keystroke filter requests, no runaway
  polling; hidden-tab polling stops; `AbortController` + request-id race guards;
  StrictMode does not double-submit; no non-GET request on any route load.
- Safety QA: `LIVE_AUTOMATION_ENABLED = False`, `LIVE_BROKER_TRANSMISSION = BLOCKED`
  verified on `/api/health` and `/api/operations/system`; full-DOM execution-control
  scan across all routes found only the Risk Gateway `BUY`/`SELL` `role="radio"`
  calculation-direction toggle (transmits nothing).
- Golden-reference parity: risk preview, positions count, journal count, evidence
  `sample_n`, contract hash and safety flags are byte-identical between the Python
  engine and the FastAPI adapter; `:8501/_stcore/health` → `ok`.
- Performance (dev, warm, median): intelligence / evidence / risk-preview /
  watchlist / snapshot / positions / research-strategy read paths are all
  **3–8 ms**. `/api/operations/audit` (~1.4 s) and `/api/operations/system`
  (~0.7 s) are uncached Stage 11 endpoints — **deferred** to a future Stage 3.5-style
  bounded-TTL-cache sub-stage (frontend already throttles them: 60 s / 20 s poll,
  hidden-paused, 12 s module cache).

### 9.1 Currency-aware FX risk sizing fix (`d23a54f`)

**Root cause:** `risk_gateway.calculate_pre_trade_risk_preview()` treated a
stop-distance P/L denominated in the pair's **quote** currency as USD. For USDJPY
(quote = JPY) this over-stated risk ~160×, sizing 0.01 lots for a 3% / $300 budget
and reporting "$434 / 4.34%"; margin used a hardcoded 1:30 leverage on an
`entry × units` (JPY) notional → the bogus "$5,316" figure.

**Fix (adapter-side helpers in `risk_gateway.py`, reusing `symbol_mapping.CANONICAL_SYMBOLS`
and `instrument_specs.DEFAULT_SPECS` — no per-symbol constants):**
- `quote_ccy_to_usd_factor(symbol, price)` → `1.0` when quote == USD;
  `1.0 / price` when base == USD (USD/XXX); static spec estimate + warning for
  non-USD crosses.
- Sizing: `lots = target_risk_usd / (sl_distance × contract_size × quote→USD factor)`
  referenced at the entry price (consistent with the execution gate).
- Margin: `USD notional × instrument_specs.margin_factor` (0.01 = 1:100 for FX),
  where USD notional is `lots × contract_size` for USD-base pairs.
- `evaluate_trade_risk()` routed through the same helper — identical output for
  USD-base and USD-quote pairs, only non-USD crosses now converted.

**Regression-locked:** USDJPY SELL 159.487 / 159.921 / $10k / 3% → **1.10 lots,
$299.33 risk, 2.99%, $1,100 margin**. EURUSD sizing unchanged (0.20 lots, $100,
1.0%, reward $200). Tests: `tests/test_forex_position_sizing.py` (12).

### 9.2 Streamlit Legacy UI Retirement Evaluation — **RECOMMENDATION: KEEP**

Full evaluation: `docs/STAGE_11_STREAMLIT_RETIREMENT_EVALUATION.md` (no source
changed). Streamlit (`app.py`) is **partially superseded, not fully superseded**:

- **11 surfaces FULLY_REPLACED** by React (watchlist, market snapshot, risk
  preview, positions, market/asset intelligence, opportunity map, economic
  heatmap, execution audit, system health, operations overview, app shell).
- **3 PARTIALLY_REPLACED** (Forward Evidence — React 4 pages vs 7-tab cockpit;
  Backtest — `backtester` only, not the 3-layer `research_engine` workflow;
  Journal — React read-only, no annotation write).
- **7 NOT_REPLACED, no React/FastAPI equivalent:** manual paper/shadow order
  entry (Quick Terminal → `execution_pipeline.submit_order`), AI Market Context
  (Ollama local LLM), Price Alerts CRUD, Analytics & Overview, Daily Command
  Center, Research Lab (True MTF / USDJPY empirical labs / edge discovery),
  Adversarial Stress Audits.

**Hard backend coupling:** `streamlit` is a module-level import of
`trading_workspace_cockpit`, `user_preferences`, `market_intelligence_command_center`
— all imported by FastAPI routers. The Streamlit *process* can stop, but
`streamlit>=1.30.0` must stay in `requirements.txt` or the React SPA's backend
fails to import. **Deployment:** the only documented deploy (`deployment_guide.md`)
is `streamlit run app.py`; no React/FastAPI deploy config exists.

**Retirement risk: MEDIUM–HIGH.** Safety is unaffected (all fail-closed logic is
backend, UI-independent; 55 targeted safety/parity tests pass;
`automation_enabled=False`, `broker=BLOCKED` verified). Roadmap invariant #5
("Streamlit Coexistence") keeps `app.py` operational.

**Outcome:** coexistence — React = read-only monitoring/analysis SPA, Streamlit =
power-user console for research / alerts / analytics / paper execution. Next step
is a product-scope decision by the owner (keep the 7 workflows in Streamlit
permanently, or migrate them in bounded units starting with a journal-write
endpoint, then alerts, then analytics). No deletion authorized in this stage.

### 9.3 Stage 12 — Journal edit migration (first bounded migration unit)

Full detail: `docs/STAGE_12_JOURNAL_EDIT_MIGRATION.md`. Migrates the legacy
Streamlit "Log & Review Trade Setup" workflow to the React SPA — the **first**
of the bounded migration units named in §9.2.

- **New endpoint:** `PATCH /api/operations/journal/{trade_id}` — thin adapter
  over the authoritative `database.update_trade_journal`; no SQL duplicated.
- **Editable (annotations only):** `setup_tag`, `notes`, `chart_snapshot_url` —
  exactly the fields the Streamlit form writes. **Immutable** (rejected 422 via
  `extra="forbid"`): symbol, side, prices, volume, timestamps, P&L, ids, rating.
  Unknown trade → 404; empty / all-null payload → 422.
- **React:** `/operations/journal` gains an in-place per-row editor
  (edit / save / cancel, loading + error states, sends only changed fields,
  duplicate-submit guarded). PATCH response is spliced into the cached list —
  no refetch, no polling change. Journal `useJournal` hook now exposes
  `applyEntry`; `JournalResponse.writable` is now `true`.
- **Safety:** the endpoint touches no broker / execution code path. Verified —
  `automation_enabled=False`, `broker_transmission=BLOCKED` unchanged after
  edits; no `execution_orders` row written; `open_positions` unchanged.
- **Tests:** `tests/test_stage12_journal_edit.py` (24 cases: success, 404,
  validation, unknown-field rejection, immutability, round-trip, GET-reflects,
  no-execution). Full suite **921 passed, 2 skipped, 0 failed**. `tsc -b` +
  production build clean (436.50 kB JS / 120.47 kB gzip). Browser smoke: edit
  → PATCH 200 → editor closes → value visible; 0 console errors.
- **Still deferred** (unchanged): Price Alerts, Analytics, Daily Command Center,
  Research Lab, AI Assistant, paper execution. Not migrated here.
- **Pre-existing latent bug noted (out of scope):** `api/routers/positions.py:34`
  does an unguarded `float(pos.get("tp", 0.0))` that raises `TypeError` when an
  open position has a NULL `tp`; only surfaces under random test ordering.

### 9.4 Stage 13 — Price Alerts migration (second bounded migration unit)

Full detail: `docs/STAGE_13_PRICE_ALERTS_MIGRATION.md`. Migrates the Streamlit
"PRICE ALERTS" tab (`app.py:3960–4026`) to the React SPA.

- **New router** `api/routers/alerts.py` — `GET/POST/DELETE /api/alerts`, a thin
  CRUD adapter over the authoritative `price_alerts` table + the canonical
  `database.create_price_alert` / `get_all_price_alerts` / `delete_price_alert`
  helpers. No SQL duplicated, no second alert store.
- **Fields:** `symbol` (validated/normalized via `symbol_mapping.normalize_symbol`
  → canonical; alias `gold`→`XAUUSD`), `target_price` (`>0`, finite),
  `condition` (`ABOVE` = price ≥ target, `BELOW` = price ≤ target), `notes`
  (≤500). Server-maintained `id` / `status` / `created_at` / `triggered_at`
  rejected as unknown fields (`extra="forbid"`). Unknown symbol/condition/field
  → 422; unknown `alert_id` → 404; no PUT/PATCH (405).
- **React:** new nav item `workspace.alerts` → `/workspace/alerts`
  (`PriceAlertsPage` + `components/alerts/AlertsPanel.tsx`): create form
  (symbol `<datalist>` from `supported_symbols`, price, condition, note) + list
  with status tags + per-row delete. `useAlerts` = one GET + 60s hidden-paused
  refresh; create/delete → one request + one `refetch()`; no optimistic state,
  no N+1. `apiDelete` added to `client.ts`; `BellIcon` added.
- **Alert evaluation is unchanged** — still the standalone `auto_sync.py` daemon
  (`get_active_price_alerts` + `alerts.notify_price_alert` +
  `mark_price_alert_triggered`). The router adds no evaluation / polling /
  notification code and `alerts.py` has **zero execution coupling** (verified).
- **Safety:** no `execution_pipeline` / broker / risk-gateway file touched;
  router namespace binds no execution symbol; `automation_enabled=False`,
  `broker=BLOCKED`, `execution_orders`, `open_positions` all unchanged by CRUD.
- **Tests:** `tests/test_stage13_price_alerts.py` (27 cases). Full suite
  **948 passed, 2 skipped, 0 failed**. `tsc -b` + build clean (146 modules,
  446.83 kB JS / 122.43 kB gzip). Browser smoke: create → POST 201 → refetch;
  unsupported symbol → 422 shown; delete → 200 → row gone; 0 console errors.
- **Parity:** Price Alerts CRUD is now fully covered by React/API and **could**
  be removed from `app.py` — **not done** (scope = migration, not retirement).
  Still Streamlit-only: the custom trade-close **notification-rules engine**
  (`alerts.get_alert_rules` / `save_alert_rules`), arbitrary non-canonical
  symbols, alert editing, per-account alerts.
- **Still deferred:** Analytics, Daily Command Center, Research Lab, AI
  Assistant, paper execution.

### 9.5 Stage 14 — Analytics migration (third bounded migration unit)

Full detail: `docs/STAGE_14_ANALYTICS_MIGRATION.md`. Migrates the Streamlit
"ANALYTICS & OVERVIEW" tab (`app.py:1882–2470`) to the React SPA.

- **New router** `api/routers/analytics.py` — one GET endpoint
  `GET /api/analytics/performance?account&symbols&start&end&initial_balance`.
  Every headline metric comes from the authoritative
  `analytics.calculate_performance_metrics` (no formula reimplemented); the
  router only filters the `closed_trades` population (account / symbol / date,
  exactly as the Streamlit page, incl. the `format="mixed"` date parse) and
  shapes derived series: `equity_curve` (real anchors, ≤400 decimated),
  `daily_pnl`, `symbol_breakdown`, `tag_breakdown`, `period_returns`,
  `official_balance` (`database.get_account_balances`), plus `available`
  (accounts / symbols / date range) so the filter UI needs no second request.
- **Validation:** unknown account / symbol → 422; unparseable date → 422;
  `start > end` → 422; `initial_balance <= 0` or non-finite → 422. GET-only
  (POST/PUT/DELETE → 405). `research_analytics.py` is **not** imported (that
  powers a different tab — a Research Lab unit).
- **React:** new nav item `workspace.analytics` → `/workspace/analytics`
  (`AnalyticsPage` + `components/analytics/AnalyticsControls.tsx` +
  `AnalyticsView.tsx`): metric cards, equity `Sparkline` (reused, no new dep),
  period returns, symbol/tag P&L bars, direction split, performance-index bars,
  daily P&L bar series. `useAnalytics` = one aggregated GET, **300ms debounce**
  on filter changes, `AbortController`, last-good retained on a rejected filter,
  **no polling**. No calculation in the browser — only formatting.
- **Parity:** all `calculate_performance_metrics` fields byte-verified equal
  (`test_metrics_match_canonical_function`, unfiltered + filtered). Intentional
  presentation-only diffs: equity spline + synthetic baseline point dropped;
  radar → bars; month-calendar grid → daily-P&L bar series (data still exposed).
  Out of scope: "Sync MT5 / Sync Capital" ingestion buttons, research analytics.
- **Safety:** no `execution_pipeline` / broker / risk file touched; router binds
  no execution symbol; `automation_enabled=False`, `broker=BLOCKED`,
  `execution_orders`, `open_positions` all unchanged.
- **Tests:** `tests/test_stage14_analytics.py` (19 cases). Full suite
  **967 passed, 2 skipped, 0 failed**. `tsc -b` + build clean (151 modules,
  462.07 kB JS / 125.87 kB gzip). Browser smoke: real data + sparkline, symbol
  filter → 1 debounced GET, `start>end` → 422 + warning strip + last-good kept,
  GET-only, 0 console errors; 7-route regression clean.
- **Remaining Streamlit-only:** Daily Command Center, Research Lab
  (incl. `research_analytics.py`), AI Market Context, manual paper execution,
  the notification-rules engine, the sync buttons, the calendar widget.

### 9.6 Stage 15 — Intelligence Layer (command center + research lab + AI assistant)

Full detail: `docs/STAGE_15_INTELLIGENCE_LAYER.md`. Three gated checkpoints,
commits `5397ba2` / `0c2b2fd` / `0f77d24`.

- **15A Daily Command Center** — `GET /api/command-center/overview`
  (`api/routers/command_center.py`), a concurrent server-side aggregate that
  re-shapes slices of already-authoritative sources (analytics / positions /
  alerts / intelligence / forward-evidence / research notes / watchlist). No
  formula reimplemented. Failing source → named in `sections_degraded`, never
  500. GET-only. React `/workspace/command-center` (first Workspace item),
  60s hidden-paused refresh.
- **15B Research Lab** — `POST /api/research/audit` (in the `research` router):
  runs one `backtester.run_backtest`, then the canonical `research_analytics.*`
  + `research_engine.*` functions verbatim (R-multiples, 60/20/20 layers,
  bootstrap CI seed 42, scorecard, execution stress, drift, liquidity/session/
  regime/hour/day/confluence attribution). This is `research_analytics.py` —
  distinct from Stage 14's `analytics.py`. `< 4` trades → structured failure.
  POST-only, deterministic, fail-closed barrier. React `/research/audit`
  (nav `research.audit`), explicit-action-only run. `test_research_lab.py`
  unchanged and passing.
- **15C Read-only Gemini AI Assistant** — `POST /api/ai/chat` + `GET /api/ai/status`
  (`api/routers/ai.py`, `api/ai_context.py`, `api/gemini_client.py`). Analytical
  chat over an allowlisted bounded (~12k) read-only snapshot + Gemini
  (server-side `GEMINI_API_KEY`, never returned). **Execution isolation:** the
  AI modules bind no execution/broker/risk symbol and have no import-graph path
  to them (binding + import-graph tests); execution-style prompts produce a text
  reply and zero side effects (`execution_orders`, `open_positions`,
  automation, broker all unchanged). Fixed server-side system instruction,
  user-unoverridable (prompt-injection test). Unset key → graceful
  `ok:false, error_kind:"not_configured"` 200. Provider failures → `ok:false` +
  `error_kind`, never 5xx. React `/workspace/assistant`. Live Gemini call not
  exercised (no key); plumbing covered by stubbed-provider tests.
- **Tests:** `test_stage15a` (10) + `test_stage15b` (15) + `test_stage15c` (20).
  Full suite **1011 passed, 2 skipped, 0 failed**. `tsc -b` + build clean
  (161 modules, 494.56 kB JS / 133.24 kB gzip). 12-route browser regression clean.
- **Safety:** `automation_enabled=false`, `broker=BLOCKED`, `execution_orders`
  = 335 (unchanged), `mode_counts` unchanged, `open_positions` = 2 (unchanged).
  No `execution_pipeline` / `broker_adapter` / `risk_gateway` / `app.py` file
  touched. Stage 11 cache untouched.
- **Not migrated (documented):** XAUUSD news/calendar engine (macro stage),
  command-center note/snapshot writing, `MultipleTestingTracker`. `requirements.txt`
  unchanged (`google-generativeai` already present); `.env.example` gains
  optional `GEMINI_API_KEY`.

### 9.7 Stage 18 — Market & Macro Intelligence foundation (preview)

Full detail: `docs/STAGE_18_MACRO_INTELLIGENCE.md`. Built as a preview to be
refined against reference screenshots.

- **Reuse:** `macro_intelligence_engine.py` (Phase 56, 1609 lines — surprise /
  economic strength / 5 factor groups / FX relative strength / gold macro model,
  covered by `test_phase55_macro` + 13× `test_phase56_*` + `test_phase57_*`)
  is reused **unchanged**. Stage 18 adds only the provider + surprise config +
  service + API + UI + Gemini layers.
- **Provider abstraction** `api/macro_provider.py` — `MacroDataProvider` protocol
  + `normalize_event` (missing fields stay None, malformed dropped, `"225K"`
  parsed). Default `SeedDemoProvider` (env `MACRO_DATA_PROVIDER`) wraps the
  existing seeded registry + `StandardMacroCalendarProvider`. **DATA INTEGRITY:**
  the seed data is synthetic (USD/EUR/GBP/JPY only) → every response tagged
  `provenance:"seed_demo"`, `provider_is_live:false`; CHF/CAD/AUD/NZD →
  `INSUFFICIENT_EVIDENCE` (never a fabricated score); a real feed plugs in with
  one class, no other change.
- **Surprise engine** `api/surprise_engine.py` — deterministic
  `evaluate_surprise()` with an explicit per-indicator config (no universal
  rule: CPI beat → NEGATIVE/HAWKISH, GDP beat → POSITIVE, Unemployment beat →
  NEGATIVE/DOVISH). `normalized_surprise` only when a std is configured;
  `surprise_pct` only when valid. States POSITIVE/NEGATIVE/INLINE/INSUFFICIENT/
  UNAVAILABLE.
- **API** `api/routers/macro.py` (GET-only): `/api/macro/{events,events/upcoming,
  events/recent,surprises,currencies,currencies/{ccy},pairs,assets,assets/{asset},
  overview}`. Bad window/date/start>end/currency/impact/limit → 422; unsupported
  ccy/asset → 404; POST/PUT/DELETE → 405. No secret in any response (test).
- **React** `/research/macro` (nav `research.macro`) — 4 tabs (Overview /
  Economic Calendar / Currency Strength / Asset Macro Context), one batched
  `Promise.allSettled` fetch, permanent provenance banner, insufficient-data
  states. No new dependency.
- **Gemini** `api/ai_context.py` — bounded `macro_intelligence` snapshot section
  (regime, ≤3 strongest/weakest ccy, ≤5 upcoming high-impact, ≤5 surprises,
  asset bias); `SYSTEM_INSTRUCTION` updated: macro = context, possibly demo,
  "never an execution signal". Context block still bounded (~7k of 16k cap).
- **Tests:** `tests/test_stage18_macro.py` (32). Full suite **1043 passed,
  2 skipped, 0 failed**. `tsc -b` + build clean (165 modules, 510.10 kB JS).
  14-route browser regression clean; `/research/macro` GET-only, 0 console errors.
- **Safety:** `automation_enabled=false`, `broker=BLOCKED`, `execution_orders`
  =335, `mode_counts`, `open_positions`=2 all unchanged. No execution/broker/
  risk/Stage-11-cache file touched; macro + AI modules bind no execution symbol
  (binding + import-graph tests).
- **Gap audit (§18I):** implemented = calendar / surprise / currency score /
  factor groups / asset context / rankings / insufficient-evidence. Partial /
  missing (next iteration, all additive): composite integer scorecard + gauges,
  per-instrument 6-category scorecard, "score over time" sparkline
  (`MacroIntelligenceSnapshotStore` exists, unused), per-country economic
  heatmaps, "Technical Signal" sub-score, dedicated COT / Crowd Sentiment
  panels, and a real macro data provider.

## 10. Research Program Status (Phases 76–90) — Directional & Magnitude Information Discovery

*Note: this section summarizes a separate, parallel research track (a
sequence of individually documented `docs/PHASE_76..90_*.md` reports) that
this architectural record had not previously reflected — sections 1-9
above stop at Stage 18/Phase 57 of the product-feature track. This section
exists specifically to satisfy the requirement that authoritative
project-state documentation reflect the current, actual research
conclusion rather than a full historical rewrite of the intervening
phases (see each phase's own `docs/PHASE_*.md` for full detail).*

- **Directional discovery: `EXHAUSTED_WITH_CURRENT_INFORMATION_FRONTIER`.**
  Four independent, methodologically distinct constructions all found no
  directional edge: Phase 83 (five pre-registered market-structure/regime
  interactions), Phase 86 (momentum + tick-volume filter, tested across 7
  thresholds), Phase 87 (a same-feed cross-market USD-strength proxy built
  from 10 already-owned MT5 instruments), and Phase 88 (a genuinely
  independent external dataset — DXY, VIX, US10Y yield, COMEX gold
  futures, WTI crude futures via Yahoo Finance — tested via 6
  hypothesis-driven candidates). Economic-surprise data and genuine
  historical order-flow data were both confirmed unavailable in this
  repository (not fabricated as a substitute). This conclusion should not
  be reopened without genuinely new, authorized external information.
- **Magnitude signal: `CONFIRMED`.** MT5 tick-volume (`volume_rank`,
  loaded since Phase 76, never tested until Phase 84) provides real,
  causal, walk-forward-validated incremental information about *future
  price-movement magnitude* (not direction) beyond a volatility-only
  baseline (Phase 89: pooled ΔR² ≈ +0.0342, positive in every fold, on all
  6 canonical instruments, surviving a dedicated within-apparatus
  placebo). Phase 89's own red-team audit found this likely has a partly
  market-wide (cross-asset volatility-clustering) component, not a purely
  per-instrument one — a disclosed refinement, not an invalidation.
- **Phase 90 economic status: `RISK_MANAGEMENT_EDGE_PROMISING`.** A
  volatility-targeting position-sizing/eligibility rule conditioned on
  `volume_rank`, applied under a direction held fixed and identical
  between conditions ("always long" — an explicitly documented non-signal
  scaffold, never a trading recommendation), improved pooled walk-forward
  expectancy and drawdown, cleared its own placebo, and was stable across
  BASE/ADVERSE/SEVERE cost stress — but the benefit was concentrated in 3
  of 6 instruments (GBPJPY, AUDJPY, USDJPY positive; EURUSD, GBPUSD,
  XAUUSD flat-to-negative), so it is not yet broad enough to confirm a
  general edge. `PROFITABLE_TRADING_EDGE_FOUND = NOT_ESTABLISHED`.
- **Holdout: `UNTOUCHED`.** The frozen Phase-74 Gold holdout
  (`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`) has
  never been read by any module in the Phase 76-90 research program.
- **Live automation: `DISABLED`.** `Broker transmission: BLOCKED`.
  Unchanged throughout the entire research program.
- **Current research frontier (superseded by Phase 91 below)**: see
  Section 11 for the updated status.

## 11. Research Program Status (Phase 91) — Magnitude Economic Divergence & Cross-Instrument Attribution

- **Research question answered**: why Phase 90's risk-management economic
  benefit was positive on only 3 of 6 instruments (GBPJPY, AUDJPY,
  USDJPY), and why that split was the *inverse* of Phase 89's own
  predictive-strength ranking (the 3 positive instruments had the
  *weakest* raw `corr(volume_rank, T2)`, 0.34-0.40, while the 3 negative
  instruments had the strongest, 0.52-0.59 — a perfect, non-overlapping
  separation).
- **Mechanism found (quantified, corroborating, but not fully
  conclusive)**: `corr(T1, T2)` — the correlation between the fixed
  "always long" realized return and the predicted forward magnitude — is
  materially more negative for the 3 economically-positive instruments
  (mean ≈ −0.171) than for the 3 negative ones (mean ≈ −0.019), an 8.8×
  difference. Decomposing Phase 90's combined treatment further: the
  eligibility **filter**, not the volatility-targeting **sizing** rule,
  drives essentially all of the pooled economic benefit (filter-only
  improves expectancy on 5 of 6 instruments; sizing-only is actively
  harmful on 5 of 6, including all 3 of the economically-positive
  instruments in isolation). XAUUSD is the sole instrument where even the
  filter is counterproductive, plausibly linked to its own unusually
  large baseline "always long" drift (+0.041, 4-10x the other five
  instruments) within this sample period. The 3/3 split also maps exactly
  onto quote currency (JPY-quoted vs. not) — reported as a clean
  structural correlate, not asserted as the causal mechanism itself.
- **Verdict: `ECONOMIC_DIVERGENCE_PARTIALLY_EXPLAINED`** (not the
  strongest `EXPLAINED` category) because per-instrument fold-level sign
  consistency across the 3 walk-forward folds is imperfect for 4 of 6
  instruments — only GBPJPY and EURUSD are perfectly consistent fold to
  fold, even though all 6 instruments' *pooled* sign matches their group.
- **Status of prior findings**: directional research remains
  `EXHAUSTED_WITH_CURRENT_INFORMATION_FRONTIER` (unchanged, not
  reopened). Magnitude signal remains `CONFIRMED` (unchanged). Phase 90's
  economic status remains `RISK_MANAGEMENT_EDGE_PROMISING` (not upgraded
  or downgraded by this phase — Phase 91 explains it, does not re-test
  it). `PROFITABLE_TRADING_EDGE_FOUND = NOT_ESTABLISHED` (unchanged).
- **Holdout: `UNTOUCHED`.** Frozen Gold holdout hash
  (`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`)
  confirmed unchanged; never read by any module in the Phase 76-91
  research program.
- **Live automation: `DISABLED`.** `Broker transmission: BLOCKED`.
  Unchanged throughout the entire research program.
- **Current research frontier**: proven — the eligibility-filter
  component of Phase 90's risk-management layer is the actual source of
  its positive economic contribution; sizing alone is net-harmful in
  isolation on 5 of 6 instruments; a quantified T1-T2 correlation
  asymmetry and a clean predictive-strength/economic-benefit inversion
  both corroborate why the benefit concentrates where it does. Unproven —
  full period-by-period (fold-level) consistency of the mechanism;
  whether the JPY-quote structural correlate has any causal role; why the
  filter itself fails specifically for XAUUSD; any directional trading
  strategy; standalone profitability of any construction tested;
  production readiness of the risk-management layer. See Section 12 below
  for the follow-up that directly answered this — directional discovery
  is explicitly not to be reopened to pursue it.

## 12. Research Program Status (Phase 92) — Standalone Magnitude Eligibility Filter Validation

- **Research question answered**: does the volume-informed magnitude
  eligibility filter constitute a genuine, standalone risk-management
  effect, independent of Phase 90's sizing rule? Sizing was removed
  **completely** (never imported, never applied — verified by a dedicated
  source-scan test) and the frozen Phase-90 filter alone (unit exposure)
  was re-tested against a fixed-size/no-filter baseline under **genuine
  walk-forward** (Phase 80's 3-fold apparatus), not the single 70/30
  split Phase 91's own decomposition used.
- **Result**: the isolated filter beats two independently-implemented
  equal-retention placebo controls (randomized-draw and shuffled-label)
  at the 100th percentile pooled, beats a deterministic return-independent
  generic exposure-reduction control on both expectancy and drawdown, and
  is robust to small predeclared perturbations of both the eligibility
  threshold (0.20/0.25/0.30) and the target horizon (3/4/5 bars).
  Drawdown improves in every walk-forward fold; expectancy improves in 2
  of 3 folds (essentially flat, not negative, in the third).
- **Important, more conservative findings than Phase 89/90's headline
  framing, disclosed honestly rather than smoothed over**: (a) the pooled
  placebo win is disproportionately carried by the JPY-quoted subgroup —
  individually only GBPJPY decisively beats its own placebo, and
  XAUUSD's isolated filter falls *below* its own placebo distribution;
  (b) 3 of 6 instruments' filter benefit is classified as substantially
  **direction-correlated** under the fixed always-long scaffold (removing
  observations that are disproportionately adverse for "always long"),
  not demonstrated to be a direction-agnostic property; (c) an ordinary
  volatility-only filter (no `volume_rank`) already captures most of the
  pooled benefit — the volume-specific incremental value beyond
  volatility is modest and concentrated mainly in GBPJPY; (d) the
  cost-robustness result is a structural/mechanical property of comparing
  two per-trade-cost-shifted means (cost cancels exactly in the delta),
  not deep empirical evidence of survival under increasing real friction
  — disclosed explicitly as a limitation of the test's own construction.
- **XAUUSD fails outright** (0/3 folds positive, and its removed
  observations are actually *better* for the always-long direction than
  its retained ones) — kept in every table, never discarded.
- **Verdicts** (four independent classifications, none forced positive):
  `FILTER_INFORMATION_EFFECT_CONFIRMED`, `RISK_MANAGEMENT_FILTER_CONFIRMED`,
  `FILTER_ECONOMIC_EDGE_PROMISING` (not CONFIRMED — one fold is flat),
  `PHASE_90_EFFECT_REDUCED_TO_FILTER` (reproduces Phase 91's core claim
  that filtering, not sizing, carries Phase 90's benefit).
- **Status of prior findings**: directional research remains
  `EXHAUSTED_WITH_CURRENT_INFORMATION_FRONTIER` (unchanged, not
  reopened). Magnitude signal remains `CONFIRMED` (unchanged). Phase 90's
  `RISK_MANAGEMENT_EDGE_PROMISING` and Phase 91's
  `ECONOMIC_DIVERGENCE_PARTIALLY_EXPLAINED` are both unchanged by this
  phase — Phase 92 isolates and stress-tests the filter component, it
  does not re-grade the prior verdicts. `PROFITABLE_TRADING_EDGE_FOUND =
  NOT_ESTABLISHED` (unchanged — neither the baseline nor the isolated
  filter treatment is net-profitable in absolute terms; the filter
  narrows, but does not close, that gap).
- **Holdout: `UNTOUCHED`.** Frozen Gold holdout hash
  (`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`)
  confirmed unchanged; never read by any module in the Phase 76-92
  research program.
- **Live automation: `DISABLED`.** `Broker transmission: BLOCKED`.
  Unchanged throughout the entire research program.
- **Current research frontier**: proven — the eligibility filter alone
  (no sizing) is a real, placebo-surviving, threshold/horizon-robust
  effect at the pooled level, and reproduces Phase 91's filter-vs-sizing
  attribution under genuine walk-forward. Unproven — a uniform,
  direction-agnostic risk-management property (largely direction-
  correlated for 3 of 6 instruments); genuine volume-specific information
  beyond ordinary volatility (established only for GBPJPY); universal
  applicability (XAUUSD fails outright); quote-currency causality;
  genuine cost robustness beyond the disclosed structural invariance;
  production readiness or standalone profitability of any construction.
  See Section 13 below for the follow-up that answered this — directional
  discovery is explicitly not to be reopened to pursue it.

## 13. Research Program Status (Phase 93) — Magnitude / Volatility / Volume Mechanism Isolation

- **Research question answered**: which information component actually
  powers the Phase-92 standalone eligibility filter — magnitude,
  volatility, volume, their interaction, mere exposure reduction, or
  directional contamination? Answered by information ablation only: eight
  treatments (baseline / canonical / magnitude-only / volatility-only /
  volume-only / magnitude+volume / magnitude+volatility / full) run
  through the SAME frozen Phase-90 machinery, varying ONLY the feature
  set. Phase 89's frozen Baseline B was partitioned by a predeclared,
  disclosed criterion into a raw-realized-magnitude group (`atr_ret`,
  `rv`, `tr_atr`, `abs_ret_1`) and a percentile-rank volatility-regime
  group (`atr_rank`, `rv_rank`) — a split new to this phase (prior phases
  treated Baseline B as one atomic block).
- **Result: `Scenario A` — magnitude-only is the minimum sufficient
  mechanism; volume is unnecessary.** The magnitude-only filter not only
  reproduces but EXCEEDS the canonical filter's pooled walk-forward
  expectancy effect (+0.01883R vs +0.01163R), generalizes BETTER (5 of 6
  instruments consistent vs 4 of 6 — it is the only treatment that moves
  EURUSD and GBPUSD off flat/negative to clearly positive), beats its own
  randomized-retention placebo on more instruments individually (EURUSD
  0.52→0.84, GBPUSD 0.65→0.86), and produces the LARGEST drawdown
  improvement of any treatment. Volatility-rank features alone explain a
  material but non-dominant ~55%. Canonical reproduction was exact
  (max_abs_diff = 0.0). Determinism confirmed.
- **Volume finding: `VOLUME_INCREMENTAL_VALUE_NOT_ESTABLISHED`.** Adding
  `volume_rank` to the magnitude features degrades the pooled effect by
  −0.00738R, is positive on only 2 of 6 instruments (both JPY-quoted),
  and SPECIFICALLY DESTROYS the EURUSD/GBPUSD magnitude signal (the exact
  instruments magnitude-only rescues). A volume-only filter is nearly
  worthless (pooled −0.00097R, placebo percentile 0.62, 6/6
  direction-contaminated). This substantially reduces the "volume-
  informed magnitude" framing that ran from Phase 89 through Phase 92 —
  the isolable information is MAGNITUDE, not volume.
- **Hypothesis E (mere exposure reduction) REJECTED**: for every
  treatment the deterministic same-retention generic-reduction control
  lands within ~0.0002R of the unfiltered baseline; the information
  filters beat it by ~0.02R.
- **Six independent verdicts, none forced**:
  `MAGNITUDE_EFFECT_CONFIRMED`, `VOLATILITY_EXPLANATION_PARTIAL`,
  `VOLUME_INCREMENTAL_VALUE_NOT_ESTABLISHED`, `FILTER_MECHANISM_CONFIRMED`,
  `DIRECTIONALLY_DEPENDENT` (4 of 6 instruments' benefit is
  direction-correlated Case B/D even under magnitude-only — the JPY-pair
  benefit is substantially "removing adverse-for-always-long
  observations", NOT a demonstrated direction-agnostic risk property),
  `CROSS_INSTRUMENT_PARTIAL` (XAUUSD fails outright in every single
  treatment — its filter-removed observations are FAVOURABLE for
  always-long, direct evidence against a universal magnitude-risk
  hypothesis; XAUUSD kept in every table, never excluded).
- **Status of prior findings**: directional research remains
  `EXHAUSTED_WITH_CURRENT_INFORMATION_FRONTIER` (unchanged, not
  reopened). Magnitude signal remains `CONFIRMED` — and is now the sole
  isolated information component (volume demoted). Phase 90's
  `RISK_MANAGEMENT_EDGE_PROMISING`, Phase 91's
  `ECONOMIC_DIVERGENCE_PARTIALLY_EXPLAINED`, and Phase 92's four verdicts
  are all unchanged (Phase 93 isolates the mechanism, it does not
  re-grade prior phases). `PROFITABLE_TRADING_EDGE_FOUND = NOT_ESTABLISHED`
  (unchanged — no treatment, baseline or filter, is net-profitable in
  absolute terms).
- **Holdout: `UNTOUCHED`.** Frozen Gold holdout hash
  (`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`)
  confirmed unchanged; never read by any module in the Phase 76-93
  research program.
- **Live automation: `DISABLED`.** `Broker transmission: BLOCKED`.
  Unchanged throughout the entire research program.
- **Current research frontier**: proven — the Phase-92 filter effect is
  carried by the raw realized-magnitude features alone; volume is
  unnecessary and harmful; mere exposure reduction explains none of it.
  Unproven — direction-neutrality (the mechanism is still
  direction-dependent for 4 of 6 instruments); universal applicability
  (XAUUSD fails everywhere); why XAUUSD's high-magnitude periods are
  favourable for always-long beyond "secular uptrend in-sample";
  quote-currency causality; genuine cost robustness; standalone
  profitability; production readiness. See
  `docs/PHASE_93_MECHANISM_ISOLATION.md` "Next Research Question" for the
  recommended next step (a direction-neutral re-test restricted to the
  four magnitude features, evaluated on absolute-movement / adverse-
  excursion distribution rather than always-long P&L, with XAUUSD's
  Case-D behaviour as the falsification target) — NOT an escalation
  toward a trading strategy or risk-management candidate, and directional
  discovery is explicitly not to be reopened to pursue it.

## 14. Research Program Direction Change (Phase 94+) — Swing-Trading Pivot

- **Decision**: after Phases 70–93 exhaustively established that intraday
  directional prediction on the canonical 15m FX/gold universe has no edge
  (four independent constructions all null; the ICT/SMC gold strategy
  failed Phase 74 independent revalidation at −0.092R over 1,067 trades),
  the research program has formally **stopped the intraday directional
  search** and pivoted to **swing timeframes** (daily bars, days-to-months
  holds) and the documented, out-of-sample-surviving edge families:
  time-series momentum, cross-sectional momentum, and — for crypto —
  perpetual funding-rate carry. The user's tradeable universe is FX +
  gold + crypto (spot and perps).
- **Phase 94 (data foundation) — COMPLETE**
  (`phase94_swing_data_foundation.py`). Acquired, with the same
  provenance / validation / idempotency discipline as Phase 74:
  (a) daily OHLCV for a frozen 27-coin market-cap-ranked crypto universe
  (`CRYPTO_UNIVERSE`; Binance spot; BTC/ETH from 2017, 0 rejected
  candles); (b) per-coin perpetual funding-rate history aggregated to a
  daily summed rate (Binance USD-M futures; stored as
  `phase94_funding_daily__<ASSET>` artifacts); (c) XAGUSD + EURGBP daily
  (Yahoo Finance) to complete the FX-majors + metals set already in the
  store from Phase 74. XMR is `CRYPTO_HISTORICAL_ONLY` (Binance delisted
  spot Feb 2024). **Total swing universe: 40 instruments (13 FX+metals +
  27 crypto), all momentum-ready (≥400 current daily bars); all 27 crypto
  funding-ready.** No strategy logic, no backtest, no signals.
  `GET /api/research/swing-data-foundation`,
  `docs/PHASE_94_SWING_DATA_FOUNDATION.md`, 12 tests.
- **Planned sequence**: Phase 95 time-series + cross-sectional momentum
  (the core edge) → Phase 96 crypto funding-rate carry → Phase 97 FX/gold
  carry → Phase 98 portfolio construction + risk-of-ruin sizing →
  Phase 99 paper-trading harness (6–12 months, no execution).
- **Unchanged**: holdout `UNTOUCHED` (never read Phases 76–94); live
  automation `DISABLED`; broker transmission `BLOCKED`; no production
  deployment; `PROFITABLE_TRADING_EDGE_FOUND = NOT_ESTABLISHED` (the swing
  edges are hypotheses to be validated, not established results — realistic
  prior is Sharpe ~0.5–0.9 for the diversified program, with the crypto
  sleeves higher-return / higher-variance / higher-uncertainty).

## 15. Research Program Status (Phase 95) — Swing Momentum (TS + XS)

- **Module**: `phase95_swing_momentum.py`. First strategy phase of the
  swing pivot. Tests **one pre-registered, zero-fitting question**: does a
  frozen-rule momentum book (time-series + cross-sectional) earn a
  positive, cost-surviving, OOS risk-adjusted return on the Phase-94
  daily universe?
- **Frozen design** (fixed before any result; never tuned or "best-of"
  selected): weekly `W-FRI` bars; 13/26/52-week lookbacks; TS signal =
  mean of `sign(trailing return_L)`; XS signal = count-neutral tertiles
  within each sleeve; inverse-vol sizing gross-normalised to 1, then
  ex-ante 10%-annualised sleeve vol target (causal), leverage capped
  (FX 3×, crypto 2×); weekly rebalance; per-instrument one-way retail
  costs (FX majors 1 bp … other crypto 10 bp) on a
  ZERO/BASE/ADVERSE/SEVERE = 0/1/2/4× ladder; crypto shorts held as perp
  shorts and charged/credited **actual Binance funding**, which is
  tracked **separately** and does **not** count toward the momentum
  verdict.
- **OOS framing**: zero fitting ⇒ the whole post-52-week history is OOS;
  reported full-sample, per calendar year, and first/second half.
- **Result (BASE costs)**:
  - **FX + metals**: TS and XS both **negative** Sharpe (~−0.33) over
    2017–2026 → `SWING_MOMENTUM_EDGE_NEGATIVE`. Costs are not the cause
    (drag ≈ 0.6%/yr; still negative at ZERO cost) — the raw signal has
    negative expectancy on this universe/sample (the documented
    decade-long FX/commodity trend drawdown).
  - **Crypto**: combo Sharpe ~+0.30 full sample, but does **not** clear
    the 90th pct of the random-sign placebo (real pct ≈ 0.85) and is
    front-loaded (1st-half Sharpe ~0.67 → ~0 second half; XS clearly
    negative recently) → `SWING_MOMENTUM_EDGE_NOT_ESTABLISHED`. The
    historical crypto trend premium has decayed, as the pre-registered
    prior warned.
  - **Combined inv-vol book**: Sharpe ~+0.07, placebo pct ~0.47 →
    `SWING_MOMENTUM_EDGE_NOT_ESTABLISHED`.
  - **Overall**: `PROFITABLE_SWING_EDGE_NOT_ESTABLISHED`.
- **Controls**: random-sign placebo (N=300), XS-shuffle placebo (N=300),
  vol-matched buy-and-hold benchmark, cost ladder, predeclared
  lookback/rebalance neighbourhoods (reported, never selected from),
  per-asset contribution. `determinism.match == True`.
- **Preview only, not a Phase-95 result**: the separately-tracked crypto
  funding P&L on short legs is positive (+0.2% to +1.6%/yr) — a hint that
  Phase 96 (funding carry) is the more promising line.
- `GET /api/research/swing-momentum`,
  `docs/PHASE_95_SWING_MOMENTUM.md`, 22 tests. Holdout `UNTOUCHED`; live
  automation `DISABLED`; broker transmission `BLOCKED`;
  `PROFITABLE_TRADING_EDGE_FOUND = NOT_ESTABLISHED` (unchanged).
- **Next**: Phase 96 — crypto funding-rate carry.

## 16. Research Program Status (Phase 96) — Crypto Funding-Rate Carry

- **Module**: `phase96_funding_carry.py`. Delta-neutral carry: long 1u
  crypto spot, short 1u the coin's perpetual, harvest the funding longs
  pay shorts. ONE pre-registered, zero-fitting question: does it earn a
  positive cost-surviving OOS return **and survive an exchange-collapse
  tail?**
- **Data added**: `<BASE>PERP` / `1d` daily OHLCV for all 27 Phase-94
  coins (Binance USD-M `fapi/v1/klines`), Phase-74/94 provenance
  discipline, idempotent. Only new data; funding history + spot were
  already in the store.
- **Frozen design**: weekly bars; per-coin weekly P&L =
  `(spot_ret − perp_ret) + funding_received − costs` with the basis term
  MEASURED from real perp prices; signal = trailing 4-week mean funding
  annualised; enter > +3% ann., exit ≤ 0, hysteresis; positive-carry
  only (reverse needs spot borrow — excluded); equal-weight eligible,
  15% per-coin cap, ≤15 positions, no leverage; weekly rebalance;
  per-leg retail costs on a 0/1/2/4× ladder.
- **Return stream (BASE costs, 2017–2026, 466 wk)**: Sharpe **+2.94**
  (ADVERSE +2.61), CAGR +10.1%, ann vol 3.3%, max DD −2.4%; ann funding
  +10.8%, ann basis **−0.08%** (negligible), ann cost −1.1%; positive
  **7/10** years; halves Sharpe 3.36 → 2.91 (barely decayed). Controls:
  beats **every** random-eligibility placebo (pctl 1.00); funding
  persistence pooled corr **+0.53**, positive 27/27 coins; BTC beta
  **+0.008** (genuinely delta-neutral).
- **Tail (exchange-collapse Monte-Carlo, 4000 paths/cell, judged on the
  LOSS tail not the median)**: reference cell (5%/yr collapse, 50%
  haircut) → 5th-pct total return still +10%, ~5% ruin. Aggressive cell
  (10%/yr, total loss) → **48% of paths end in ruin**, 5th pct −100%.
  Deterministic worst single week = −100%.
- **Verdicts**: EDGE `FUNDING_CARRY_EDGE_PROMISING` (clears every bar
  except positive-years 7/10 vs 80% — 2022 compressed funding to ~0;
  design freeze forbids moving the bar). TAIL
  `FUNDING_CARRY_SURVIVES_TAIL_MARGINAL` (fine under a modest
  counterparty tail, ~50% ruin under an aggressive one). **OVERALL
  `PROFITABLE_SWING_EDGE_PROMISING` — the first non-null verdict in the
  96-phase program.**
- **Why even PROMISING is generous**: (1) **survivorship bias** — the
  27-coin universe is today's survivors; a real 2021 carry book would
  have collected the (often highest) funding on coins that later
  collapsed (LUNA/UST etc.); measured Sharpe biased up, measured tail
  biased thin. (2) perp-margin/liquidation risk modelled only as a proxy.
  (3) costs optimistic for small alts; historical (pre-crowding) funding.
  (4) one regime (funding-positive == secular bull).
- `GET /api/research/funding-carry`, `docs/PHASE_96_FUNDING_CARRY.md`,
  PROJECT_STATE §16, 21 tests. `determinism.match == True`. Holdout
  `UNTOUCHED`; live automation `DISABLED`; broker transmission `BLOCKED`.
  `PROFITABLE_TRADING_EDGE_FOUND` moves from `NOT_ESTABLISHED` to
  **`PROMISING`** (funding carry, tail-sized).
- **Next**: Phase 97 FX/rate-differential carry (diversifier) → Phase 98
  portfolio construction + risk-of-ruin sizing (where the Phase-96 tail
  is sized explicitly against the Phase-95 momentum sleeves).
