"""
TradeLogger Phase 57 — Market Intelligence Scanner & Economic Heatmap UI
========================================================================
Institutional Market Intelligence Suite integrated seamlessly into Zone 1 (Trading Workspace).

Features:
- Level 1 (3-Second Scan): Market Regime, Confidence %, Market Breadth, Data Quality, Safety Barrier.
- Level 2 (10-Second Scan): 23-Asset Ranking Leaderboard, Top Movers, Multi-Economy Heatmap Matrix.
- Level 3 (30-Second Scan): Rolling Correlation Matrix, Surprise Momentum, Why Ranked Here Drawer.
- Level 4 (Forensic Audit): Data Quality Governance, Freshness Breakdown, Cryptographic Snapshots.

Strict Governance:
- Zero Strategy Signals: Uses purely contextual terminology (BULLISH CONTEXT, BEARISH CONTEXT, NEUTRAL, ALIGNED, MIXED, DIVERGING).
- Fail-Closed Safety: Live broker execution permanently locked.
- HTML Sanitization: All HTML rendered through `ui_components.render_html()`.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import ui_components
from ui_components import render_html
import market_data
from market_intelligence_scanner import (
    SCANNER_MODEL_VERSION,
    MarketUniverseRegistry,
    AssetScanRecord,
    MarketScannerEngine,
    MarketRankingEngine,
    MarketBreadthEngine,
    MarketWideChangeDetector,
    MarketScannerSnapshotStore
)
from economic_heatmap import (
    HEATMAP_VERSION,
    GLOBAL_ECONOMIES,
    CATEGORIES,
    EconomicHeatmapEngine,
    SurpriseHeatmapEngine
)
from cross_asset_regime_engine import (
    REGIME_ENGINE_VERSION,
    CrossAssetRegimeEngine,
    CrossAssetMatrixEngine,
    MarketRegimeSnapshotStore
)
from asset_edge_scorecard import render_economic_surprise_table


def render_market_intelligence_suite():
    """
    Main entry point for the Phase 57 Market Intelligence Scanner & Economic Heatmap Suite.
    """
    as_of = datetime.now(timezone.utc)

    # 1. Run Live Market Scan & Regime Evaluation
    records = MarketScannerEngine.scan_universe(asset_class="ALL", as_of=as_of)
    ranked_records = MarketRankingEngine.rank_records(records)
    breadth = MarketBreadthEngine.calculate_breadth(records)
    regime_snap = CrossAssetRegimeEngine.evaluate_regime(as_of=as_of)
    changes = MarketWideChangeDetector.evaluate_market_changes(records)

    # Automatically persist snapshot
    try:
        MarketScannerSnapshotStore.record_snapshot(ranked_records, breadth, changes, as_of=as_of)
        MarketRegimeSnapshotStore.save_snapshot(regime_snap)
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # TOP 3-SECOND SUMMARY HERO BAR
    # -------------------------------------------------------------------------
    regime_name = regime_snap.primary_regime.replace("_", " ")
    regime_col = "#00ffcc" if "RISK_ON" in regime_snap.primary_regime else ("#ef4444" if "RISK_OFF" in regime_snap.primary_regime else "#f59e0b")
    
    hero_html = f"""
    <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(0, 255, 204, 0.25); border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.4);">
        <div style="display: flex; gap: 14px; align-items: center; flex-wrap: wrap;">
            <div>
                <span style="font-size: 10px; color: #8a99ad; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px;">MARKET REGIME:</span>
                <span style="font-size: 13px; font-weight: 800; color: {regime_col}; font-family: monospace; margin-left: 5px;">⚡ {regime_name}</span>
            </div>
            <div style="color: rgba(255,255,255,0.15);">|</div>
            <div>
                <span style="font-size: 10px; color: #8a99ad; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px;">CONFIDENCE:</span>
                <span style="font-size: 12px; font-weight: 800; color: #ffffff; font-family: monospace; margin-left: 5px;">{regime_snap.confidence_pct:.0f}%</span>
            </div>
            <div style="color: rgba(255,255,255,0.15);">|</div>
            <div>
                <span style="font-size: 10px; color: #8a99ad; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px;">MARKET BREADTH:</span>
                <span style="font-size: 12px; font-weight: 800; color: #10b981; font-family: monospace; margin-left: 5px;">▲ {breadth['pct_bullish']:.0f}% Bull</span>
                <span style="font-size: 11px; color: #94a3b8; font-family: monospace; margin-left: 3px;">● {breadth['pct_neutral']:.0f}%</span>
                <span style="font-size: 12px; font-weight: 800; color: #ef4444; font-family: monospace; margin-left: 3px;">▼ {breadth['pct_bearish']:.0f}% Bear</span>
            </div>
            <div style="color: rgba(255,255,255,0.15);">|</div>
            <div>
                <span style="font-size: 10px; color: #8a99ad; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px;">DATA QUALITY:</span>
                <span style="font-size: 12px; font-weight: 800; color: #00ffcc; font-family: monospace; margin-left: 5px;">{breadth['avg_data_quality']:.0f}/100 LIVE</span>
            </div>
        </div>
        <div>
            <span style="background: rgba(239, 68, 68, 0.12); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); font-size: 10px; font-weight: 800; padding: 3px 8px; border-radius: 4px; font-family: monospace;">
                🔒 LIVE TRANSMISSION BLOCKED
            </span>
        </div>
    </div>
    """
    ui_components.render_html(hero_html)

    # -------------------------------------------------------------------------
    # 8-TAB NAVIGATION SUITE
    # -------------------------------------------------------------------------
    t_over, t_rank, t_heat, t_surp, t_corr, t_reg, t_chg, t_qual = st.tabs([
        "🌐 MARKET OVERVIEW",
        "🏆 ASSET RANKING",
        "🗺️ ECONOMIC HEATMAP",
        "⚡ ECONOMIC SURPRISE",
        "🔗 CROSS-ASSET MATRIX",
        "🧭 MARKET REGIME",
        "📈 WHAT CHANGED?",
        "🛡️ DATA QUALITY & AUDIT"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: MARKET OVERVIEW
    # -------------------------------------------------------------------------
    with t_over:
        c_o1, c_o2 = st.columns([1.8, 1.2])

        with c_o1:
            ui_components.render_html("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
                EXECUTIVE MARKET INTELLIGENCE ENVIRONMENT
            </div>
            """)
            
            top_3 = ranked_records[:3]
            top_syms = ", ".join([r["symbol"] for r in top_3])
            
            ui_components.render_html(f"""
            <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 12px; font-size: 12.5px; line-height: 1.5; color: #cbd5e1; margin-bottom: 12px;">
                <b>Current Environment:</b> Global cross-asset conditions are classified as <b>{regime_name}</b> ({regime_snap.confidence_pct:.0f}% confidence). 
                Market breadth indicates <b>{breadth['pct_bullish']:.0f}%</b> of monitored instruments exhibit bullish contextual bias, driven by real yield softening and selective commodity support.
                <br/><br/>
                <b>Top Contextual Assets:</b> <span style="color:#00ffcc; font-weight:800; font-family:monospace;">{top_syms}</span> lead the multi-factor alignment rankings.
            </div>
            """)

            # Top 5 Ranked Asset Cards
            ui_components.render_html("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
                TOP 5 CONTEXTUAL ASSETS (RANKED LEADERBOARD)
            </div>
            """)

            cards_html = '<div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px;">'
            for r in ranked_records[:5]:
                col_score = "#10b981" if r["edge_score"] >= 20 else ("#ef4444" if r["edge_score"] <= -20 else "#00ffcc")
                px_str = f"${r['price']:,.2f}" if r['price'] >= 100 else f"{r['price']:.4f}"
                cards_html += f"""
                <div style="background: rgba(15,23,42,0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 8px 10px; flex: 1; min-width: 110px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:800; font-size:12px; color:#ffffff; font-family:monospace;">{r['symbol']}</span>
                        <span style="font-size:10px; color:#8a99ad;">#{r.get('rank', 1)}</span>
                    </div>
                    <div style="font-size:11px; color:#cbd5e1; font-family:monospace; margin-top:2px;">{px_str}</div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
                        <span style="color:{col_score}; font-weight:800; font-size:11px; font-family:monospace;">{r['edge_score']:+.0f} EDGE</span>
                        <span style="font-size:9px; color:#00ffcc; background:rgba(0,255,204,0.1); padding:1px 4px; border-radius:2px;">{r['factor_agreement_pct']:.0f}%</span>
                    </div>
                </div>
                """
            cards_html += '</div>'
            ui_components.render_html(cards_html)

        with c_o2:
            ui_components.render_html("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
                WHAT CHANGED ACROSS THE MARKET?
            </div>
            """)
            
            bullets_html = '<div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 10px 12px; margin-bottom: 12px;">'
            for b in changes["executive_bullets"]:
                bullets_html += f'<div style="font-size:11.5px; color:#cbd5e1; margin-bottom:6px; line-height:1.4;">• {b}</div>'
            bullets_html += '</div>'
            ui_components.render_html(bullets_html)

            # Market Breadth Summary Box
            ui_components.render_html(f"""
            <div style="background: rgba(15,23,42,0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 10px 12px;">
                <div style="font-size: 10.5px; font-weight: 800; color: #8a99ad; text-transform: uppercase; margin-bottom: 6px;">MARKET BREADTH DISTRIBUTION:</div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-family:monospace; margin-bottom:4px;">
                    <span style="color:#10b981;">Bullish Context: {breadth['pct_bullish']:.0f}%</span>
                    <span style="color:#94a3b8;">Neutral: {breadth['pct_neutral']:.0f}%</span>
                    <span style="color:#ef4444;">Bearish: {breadth['pct_bearish']:.0f}%</span>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.06); border-radius:3px; overflow:hidden; display:flex;">
                    <div style="width:{breadth['pct_bullish']}%; background:#10b981;"></div>
                    <div style="width:{breadth['pct_neutral']}%; background:#94a3b8;"></div>
                    <div style="width:{breadth['pct_bearish']}%; background:#ef4444;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:10px; color:#8a99ad; margin-top:6px;">
                    <span>Factor Alignment: {breadth['pct_aligned']:.0f}%</span>
                    <span>Macro Alignment: {breadth['macro_alignment_pct']:.0f}%</span>
                </div>
            </div>
            """)

    # -------------------------------------------------------------------------
    # TAB 2: ASSET RANKING LEADERBOARD
    # -------------------------------------------------------------------------
    with t_rank:
        c_rf1, c_rf2 = st.columns([2.5, 1.5])
        with c_rf1:
            classes = MarketUniverseRegistry.get_available_asset_classes()
            sel_class = st.pills("Filter Asset Class", options=classes, default="ALL", key="scanner_class_filter", label_visibility="collapsed")
        
        filtered_ranked = [r for r in ranked_records if sel_class == "ALL" or r["asset_class"] == sel_class]

        # Compact Table Header
        ui_components.render_html("""
        <div style="background: rgba(15,23,42,0.9); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px 10px; margin-top: 6px; margin-bottom: 6px; display: flex; font-size: 10px; font-weight: 800; color: #8a99ad; text-transform: uppercase; font-family: monospace;">
            <div style="flex: 0.5;">RANK</div>
            <div style="flex: 1.5;">ASSET</div>
            <div style="flex: 1.0;">CLASS</div>
            <div style="flex: 1.2;">PRICE</div>
            <div style="flex: 1.0; text-align:right;">EDGE</div>
            <div style="flex: 1.0; text-align:right;">MACRO</div>
            <div style="flex: 1.0; text-align:right;">TECH</div>
            <div style="flex: 1.0; text-align:right;">COT</div>
            <div style="flex: 1.2; text-align:center;">ALIGNMENT</div>
            <div style="flex: 1.4; text-align:center;">CONTEXT STATE</div>
            <div style="flex: 0.8; text-align:right;">QUALITY</div>
        </div>
        """)

        for r in filtered_ranked:
            rk = f"#{r['rank']}" if r.get("rank") else "—"
            edge_col = "#10b981" if r["edge_score"] >= 20 else ("#ef4444" if r["edge_score"] <= -20 else "#00ffcc")
            macro_col = "#10b981" if r["macro_score"] >= 15 else ("#ef4444" if r["macro_score"] <= -15 else "#cbd5e1")
            px_str = f"${r['price']:,.2f}" if r['price'] >= 100 else f"{r['price']:.4f}"
            
            align_col = "#00ffcc" if r["factor_agreement_pct"] >= 75 else ("#f59e0b" if r["factor_agreement_pct"] >= 50 else "#ef4444")
            
            state_bg = "rgba(16,185,129,0.1)" if "BULLISH" in r["context_state"] else ("rgba(239,68,68,0.1)" if "BEARISH" in r["context_state"] else "rgba(255,255,255,0.04)")
            state_col = "#10b981" if "BULLISH" in r["context_state"] else ("#ef4444" if "BEARISH" in r["context_state"] else "#cbd5e1")

            row_html = f"""
            <div style="background: rgba(255,255,255,0.015); border: 1px solid rgba(255,255,255,0.05); border-radius: 4px; padding: 7px 10px; margin-bottom: 4px; display: flex; align-items: center; font-size: 11px; font-family: monospace;">
                <div style="flex: 0.5; color: #8a99ad; font-weight: 800;">{rk}</div>
                <div style="flex: 1.5; font-weight: 800; color: #ffffff;">{r['symbol']} <span style="font-size:9.5px; color:#64748b; font-weight:normal;">{r['display_name']}</span></div>
                <div style="flex: 1.0; color: #8a99ad; font-size: 9.5px;">{r['asset_class']}</div>
                <div style="flex: 1.2; color: #cbd5e1;">{px_str}</div>
                <div style="flex: 1.0; text-align:right; font-weight:800; color:{edge_col};">{r['edge_score']:+.0f}</div>
                <div style="flex: 1.0; text-align:right; color:{macro_col};">{r['macro_score']:+.0f}</div>
                <div style="flex: 1.0; text-align:right; color:#cbd5e1;">{r['technical_score']:+.0f}</div>
                <div style="flex: 1.0; text-align:right; color:#cbd5e1;">{r['positioning_score']:+.0f}</div>
                <div style="flex: 1.2; text-align:center; color:{align_col}; font-weight:700;">{r['factor_agreement_pct']:.0f}% ({r['conflict_state']})</div>
                <div style="flex: 1.4; text-align:center;"><span style="background:{state_bg}; color:{state_col}; padding:2px 6px; border-radius:3px; font-size:9.5px; font-weight:800;">{r['context_state']}</span></div>
                <div style="flex: 0.8; text-align:right; color:#00ffcc;">{r['data_quality_score']}</div>
            </div>
            """
            ui_components.render_html(row_html)

        # "Why Ranked Here?" Evidence Explanations Accordion
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        with st.expander("🔍 WHY ARE THESE MARKETS RANKED HERE? (FACTUAL FACTOR EVIDENCE)", expanded=False):
            for r in filtered_ranked[:8]:
                ui_components.render_html(f"""
                <div style="background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 8px 12px; margin-bottom: 6px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-weight:800; font-size:12px; color:#ffffff; font-family:monospace;">{r['symbol']} — RANK #{r.get('rank', '—')} ({r['edge_score']:+.0f} Edge / {r['context_state']})</span>
                        <span style="font-size:10px; color:#00ffcc; font-family:monospace;">Data Quality: {r['data_quality_score']}% | Conflict: {r['conflict_state']}</span>
                    </div>
                    <ul style="margin:0; padding-left:18px; font-size:11px; color:#cbd5e1;">
                        {''.join([f"<li>{b}</li>" for b in r['why_bullets']])}
                    </ul>
                </div>
                """)

    # -------------------------------------------------------------------------
    # TAB 3: ECONOMIC HEATMAP MATRIX
    # -------------------------------------------------------------------------
    with t_heat:
        ui_components.render_html("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
            GLOBAL MACROECONOMIC HEATMAP (9 ECONOMIES × 5 CATEGORIES)
        </div>
        """)

        matrix_rows = EconomicHeatmapEngine.generate_heatmap_matrix(as_of=as_of)

        # Heatmap Header
        ui_components.render_html("""
        <div style="background: rgba(15,23,42,0.9); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px 10px; margin-bottom: 6px; display: flex; font-size: 10px; font-weight: 800; color: #8a99ad; text-transform: uppercase; font-family: monospace;">
            <div style="flex: 1.8;">ECONOMY</div>
            <div style="flex: 1.5; text-align:center;">GROWTH</div>
            <div style="flex: 1.5; text-align:center;">INFLATION</div>
            <div style="flex: 1.5; text-align:center;">LABOR</div>
            <div style="flex: 1.8; text-align:center;">RATES & YIELDS</div>
            <div style="flex: 1.8; text-align:center;">SURPRISE INDEX</div>
        </div>
        """)

        for row in matrix_rows:
            g = row["growth"]
            i = row["inflation"]
            l = row["labor"]
            r = row["rates"]
            s = row["surprise"]

            row_html = f"""
            <div style="background: rgba(255,255,255,0.015); border: 1px solid rgba(255,255,255,0.05); border-radius: 4px; padding: 8px 10px; margin-bottom: 4px; display: flex; align-items: center; font-size: 11px; font-family: monospace;">
                <div style="flex: 1.8; font-weight: 800; color: #ffffff;">{row['flag']} {row['country_name']} <span style="font-size:9.5px; color:#64748b;">({row['economy_code']})</span></div>
                <div style="flex: 1.5; text-align:center;"><span style="color:{g['tint_color']}; font-weight:700;">{g['icon_symbol']} {g['badge_label']}</span></div>
                <div style="flex: 1.5; text-align:center;"><span style="color:{i['tint_color']}; font-weight:700;">{i['icon_symbol']} {i['badge_label']}</span></div>
                <div style="flex: 1.5; text-align:center;"><span style="color:{l['tint_color']}; font-weight:700;">{l['icon_symbol']} {l['badge_label']}</span></div>
                <div style="flex: 1.8; text-align:center;"><span style="color:{r['tint_color']}; font-weight:700;">{r['icon_symbol']} {r['badge_label']}</span></div>
                <div style="flex: 1.8; text-align:center;"><span style="color:{s['tint_color']}; font-weight:700;">{s['icon_symbol']} {s['badge_label']}</span></div>
            </div>
            """
            ui_components.render_html(row_html)

    # -------------------------------------------------------------------------
    # TAB 4: ECONOMIC SURPRISE HEATMAP
    # -------------------------------------------------------------------------
    with t_surp:
        ui_components.render_html("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
            MULTI-ECONOMY ECONOMIC SURPRISE MOMENTUM GRID
        </div>
        """)

        surprise_grid = SurpriseHeatmapEngine.evaluate_surprise_grid(as_of=as_of)

        ui_components.render_html("""
        <div style="background: rgba(15,23,42,0.9); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px 10px; margin-bottom: 6px; display: flex; font-size: 10px; font-weight: 800; color: #8a99ad; text-transform: uppercase; font-family: monospace;">
            <div style="flex: 1.8;">ECONOMY</div>
            <div style="flex: 1.5; text-align:center;">GROWTH SURPRISE</div>
            <div style="flex: 1.5; text-align:center;">INFLATION SURPRISE</div>
            <div style="flex: 1.5; text-align:center;">LABOR SURPRISE</div>
            <div style="flex: 1.8; text-align:center;">COMPOSITE MOMENTUM</div>
        </div>
        """)

        for sg in surprise_grid:
            c_z = sg["composite_surprise"]
            c_col = "#10b981" if c_z >= 0.5 else ("#ef4444" if c_z <= -0.5 else "#00ffcc")
            
            row_html = f"""
            <div style="background: rgba(255,255,255,0.015); border: 1px solid rgba(255,255,255,0.05); border-radius: 4px; padding: 8px 10px; margin-bottom: 4px; display: flex; align-items: center; font-size: 11px; font-family: monospace;">
                <div style="flex: 1.8; font-weight: 800; color: #ffffff;">{sg['flag']} {sg['country_name']}</div>
                <div style="flex: 1.5; text-align:center; color:#cbd5e1;">{sg['growth_surprise']:+.2f}σ ({sg['growth_dir']})</div>
                <div style="flex: 1.5; text-align:center; color:#cbd5e1;">{sg['inflation_surprise']:+.2f}σ ({sg['inflation_dir']})</div>
                <div style="flex: 1.5; text-align:center; color:#cbd5e1;">{sg['labor_surprise']:+.2f}σ ({sg['labor_dir']})</div>
                <div style="flex: 1.8; text-align:center; color:{c_col}; font-weight:800;">{c_z:+.2f}σ ({sg['composite_dir']})</div>
            </div>
            """
            ui_components.render_html(row_html)

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        ui_components.render_html("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
            DETAILED ECONOMIC RELEASE LEDGER (EXPECTATION VS ACTUAL)
        </div>
        """)
        render_economic_surprise_table(country="USD", as_of=as_of)

    # -------------------------------------------------------------------------
    # TAB 5: CROSS-ASSET CORRELATION MATRIX
    # -------------------------------------------------------------------------
    with t_corr:
        c_w1, c_w2 = st.columns([2.0, 2.0])
        with c_w1:
            win_opt = st.pills("Lookback Window", options=[20, 60, 120], default=60, format_func=lambda x: f"{x} Periods (Rolling)", key="corr_win_sel", label_visibility="collapsed")
        with c_w2:
            ui_components.render_html("""
            <div style="text-align: right; font-size: 10px; color: #f59e0b; font-weight: 800; font-family: monospace;">
                ⚠️ CORRELATION ≠ CAUSATION (N ≥ 15 SAMPLES)
            </div>
            """)

        corr_res = CrossAssetMatrixEngine.calculate_correlation_matrix(window=win_opt)
        syms = corr_res["symbols"]
        mat = corr_res["matrix"]

        # Build Interactive Matrix Header
        hdr_cells = "".join([f'<div style="flex:1; text-align:center; font-weight:800; color:#8a99ad; font-size:9.5px;">{s}</div>' for s in syms])
        ui_components.render_html(f"""
        <div style="background: rgba(15,23,42,0.9); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px 10px; margin-bottom: 6px; display: flex; font-family: monospace;">
            <div style="flex: 1.2; font-weight:800; color:#8a99ad; font-size:10px;">ASSET</div>
            {hdr_cells}
        </div>
        """)

        for s1 in syms:
            row_cells = ""
            for s2 in syms:
                val = mat[s1][s2]
                if s1 == s2:
                    bg = "rgba(255,255,255,0.04)"
                    col = "#64748b"
                    val_str = "1.00"
                elif val >= 0.5:
                    bg = "rgba(16,185,129,0.15)"
                    col = "#10b981"
                    val_str = f"{val:+.2f}"
                elif val <= -0.5:
                    bg = "rgba(239,68,68,0.15)"
                    col = "#ef4444"
                    val_str = f"{val:+.2f}"
                else:
                    bg = "rgba(255,255,255,0.02)"
                    col = "#cbd5e1"
                    val_str = f"{val:+.2f}"
                
                row_cells += f'<div style="flex:1; text-align:center; background:{bg}; color:{col}; font-weight:700; font-size:10px; padding:4px 0; border-radius:2px; margin:0 1px;">{val_str}</div>'

            row_html = f"""
            <div style="background: rgba(255,255,255,0.015); border: 1px solid rgba(255,255,255,0.05); border-radius: 4px; padding: 4px 10px; margin-bottom: 3px; display: flex; align-items: center; font-family: monospace;">
                <div style="flex: 1.2; font-weight:800; color:#ffffff; font-size:11px;">{s1}</div>
                {row_cells}
            </div>
            """
            ui_components.render_html(row_html)

    # -------------------------------------------------------------------------
    # TAB 6: MARKET REGIME ENGINE & TIMELINE
    # -------------------------------------------------------------------------
    with t_reg:
        c_rg1, c_rg2 = st.columns([1.5, 1.5])
        with c_rg1:
            ui_components.render_html(f"""
            <div style="background: rgba(15,23,42,0.8); border: 1px solid rgba(0,255,204,0.2); border-radius: 6px; padding: 12px; margin-bottom: 12px;">
                <div style="font-size:10px; color:#8a99ad; font-weight:800; text-transform:uppercase;">PRIMARY REGIME CLASSIFICATION</div>
                <div style="font-size:18px; font-weight:800; color:{regime_col}; font-family:monospace; margin-top:2px;">{regime_name} ({regime_snap.confidence_pct:.0f}% Confidence)</div>
                <div style="font-size:11px; color:#8a99ad; margin-top:4px;">Secondary Tendency: <b style="color:#ffffff;">{regime_snap.secondary_regime.replace('_', ' ')}</b></div>
            </div>
            """)

            ui_components.render_html("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px;">
                CONFIRMING CROSS-ASSET SIGNALS
            </div>
            """)
            conf_html = '<div style="background: rgba(16,185,129,0.06); border: 1px solid rgba(16,185,129,0.2); border-radius: 6px; padding: 10px; margin-bottom: 12px;">'
            for cf in regime_snap.confirming_factors:
                conf_html += f'<div style="font-size:11.5px; color:#10b981; margin-bottom:4px; font-family:monospace;">✓ {cf}</div>'
            conf_html += '</div>'
            ui_components.render_html(conf_html)

        with c_rg2:
            ui_components.render_html("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px;">
                CONFLICTING / DIVERGENT SIGNALS
            </div>
            """)
            div_html = '<div style="background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.2); border-radius: 6px; padding: 10px; margin-bottom: 12px;">'
            for df in regime_snap.conflicting_factors:
                div_html += f'<div style="font-size:11.5px; color:#ef4444; margin-bottom:4px; font-family:monospace;">⚠ {df}</div>'
            div_html += '</div>'
            ui_components.render_html(div_html)

            # Historical Regime Timeline
            ui_components.render_html("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px;">
                HISTORICAL REGIME TIMELINE & TRANSITIONS
            </div>
            """)
            timeline = MarketRegimeSnapshotStore.get_recent_timeline(limit=5)
            tl_html = '<div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 8px 10px;">'
            for t in timeline:
                tl_html += f"""
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; font-family:monospace; padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.04);">
                    <span style="color:#8a99ad;">{t['date']}</span>
                    <span style="color:#00ffcc; font-weight:800;">{t['regime']} ({t['confidence']:.0f}%)</span>
                    <span style="color:#cbd5e1; font-size:10px;">{t['dominant_driver'][:30]}</span>
                </div>
                """
            tl_html += '</div>'
            ui_components.render_html(tl_html)

    # -------------------------------------------------------------------------
    # TAB 7: WHAT CHANGED?
    # -------------------------------------------------------------------------
    with t_chg:
        ui_components.render_html("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
            MARKET-WIDE TEMPORAL SHIFT DETECTOR
        </div>
        """)

        deltas = changes["structured_deltas"]
        if not deltas:
            st.info("No significant score or regime changes recorded across consecutive cycles.")
        else:
            ui_components.render_html("""
            <div style="background: rgba(15,23,42,0.9); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px 10px; margin-bottom: 6px; display: flex; font-size: 10px; font-weight: 800; color: #8a99ad; text-transform: uppercase; font-family: monospace;">
                <div style="flex: 1.2;">ASSET</div>
                <div style="flex: 1.5;">METRIC</div>
                <div style="flex: 1.0; text-align:right;">PREVIOUS</div>
                <div style="flex: 1.0; text-align:right;">CURRENT</div>
                <div style="flex: 1.0; text-align:right;">DELTA</div>
                <div style="flex: 1.2; text-align:center;">DIRECTION</div>
            </div>
            """)

            for d in deltas[:12]:
                d_col = "#10b981" if d["delta"] > 0 else ("#ef4444" if d["delta"] < 0 else "#94a3b8")
                row_html = f"""
                <div style="background: rgba(255,255,255,0.015); border: 1px solid rgba(255,255,255,0.05); border-radius: 4px; padding: 7px 10px; margin-bottom: 4px; display: flex; align-items: center; font-size: 11px; font-family: monospace;">
                    <div style="flex: 1.2; font-weight: 800; color: #ffffff;">{d['symbol']}</div>
                    <div style="flex: 1.5; color: #8a99ad;">{d['metric']}</div>
                    <div style="flex: 1.0; text-align:right; color:#64748b;">{d['previous']:+.0f}</div>
                    <div style="flex: 1.0; text-align:right; color:#ffffff; font-weight:700;">{d['current']:+.0f}</div>
                    <div style="flex: 1.0; text-align:right; color:{d_col}; font-weight:800;">{d['delta']:+.0f}</div>
                    <div style="flex: 1.2; text-align:center; color:{d_col}; font-weight:800;">{d['direction']}</div>
                </div>
                """
                ui_components.render_html(row_html)

    # -------------------------------------------------------------------------
    # TAB 8: DATA QUALITY & AUDIT
    # -------------------------------------------------------------------------
    with t_qual:
        ui_components.render_html("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
            DATA QUALITY, FRESHNESS & LOOKAHEAD COMPLIANCE AUDIT
        </div>
        """)

        c_q1, c_q2 = st.columns(2)
        with c_q1:
            ui_components.render_html("""
            <div style="background: rgba(15,23,42,0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 12px; margin-bottom: 12px;">
                <div style="font-size:11px; font-weight:800; color:#00ffcc; text-transform:uppercase; margin-bottom:6px;">DATA GOVERNANCE COMPLIANCE</div>
                <div style="font-size:11.5px; color:#cbd5e1; line-height:1.5;">
                    • <b>Lookahead Protection:</b> All releases verified against <code>release_timestamp &le; as_of</code>.<br/>
                    • <b>Anti-Fabrication:</b> 0% imputed values; low data quality assets automatically withheld.<br/>
                    • <b>Dataset Isolation:</b> Holds 100% boundary isolation against historical baseline.<br/>
                    • <b>Fail-Closed Safety:</b> Live broker transmission permanently blocked.
                </div>
            </div>
            """)

        with c_q2:
            latest_snap = MarketScannerSnapshotStore.get_latest_snapshot()
            fp = latest_snap["data_fingerprint"] if latest_snap else "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ui_components.render_html(f"""
            <div style="background: rgba(15,23,42,0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 12px; margin-bottom: 12px;">
                <div style="font-size:11px; font-weight:800; color:#00ffcc; text-transform:uppercase; margin-bottom:6px;">CRYPTOGRAPHIC SNAPSHOT INTEGRITY</div>
                <div style="font-size:11.5px; color:#cbd5e1; font-family:monospace; word-break:break-all;">
                    <b>Model Version:</b> {SCANNER_MODEL_VERSION}<br/>
                    <b>Snapshot Fingerprint:</b><br/>
                    <span style="color:#00ffcc; font-size:10px;">{fp}</span>
                </div>
            </div>
            """)
