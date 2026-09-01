"""
TradeLogger Phase 55 — Asset Edge Scorecard UI
==============================================
Institutional Multi-Factor Market Scorecard & Intelligence Interface.
Integrated seamlessly into Zone 1 (Trading Workspace Cockpit).

Adheres strictly to the Phase 52 Centralized Design System:
- 3-Second Scan: Asset, Price, Edge Score, Directional Bias, Confidence, Data Quality, Safety Lock.
- 10-Second Scan: Factor Breakdown gauges, Factor Conflicts, Market Regime, News Risk.
- 30-Second Scan: Signed "Why This Score?" evidence, Event Countdown, Market Ranking, Historical Snapshots, Methodology.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import ui_components
import market_data
from asset_edge_intelligence import (
    EDGE_MODEL_VERSION,
    ASSET_EDGE_CONFIG,
    AssetEdgeIntelligenceEngine
)


class AssetEdgeScorecardUI:
    """
    Renders the Multi-Factor Asset Edge Scorecard in the Trading Workspace.
    """

    @classmethod
    def render_asset_edge_scorecard(cls, symbol: str = "XAUUSD"):
        """
        Main entrypoint for rendering the Asset Edge Scorecard.
        """
        # 1. Fetch deterministic snapshot
        snapshot = AssetEdgeIntelligenceEngine.evaluate_asset_edge(symbol)
        
        # 2. Record snapshot into database for audit timeline
        try:
            AssetEdgeIntelligenceEngine.record_snapshot(snapshot)
        except Exception:
            pass

        # 3. Sub-Navigation Tabs inside the Market Intelligence Region
        tab_score, tab_rank, tab_hist, tab_method = st.tabs([
            "ASSET EDGE SCORECARD",
            "MARKET RANKING (10 ASSETS)",
            "HISTORICAL EDGE TIMELINE",
            "METHODOLOGY & DATA SOURCES"
        ])

        with tab_score:
            cls.render_single_asset_scorecard(snapshot)

        with tab_rank:
            cls.render_market_ranking_view()

        with tab_hist:
            cls.render_historical_timeline(symbol)

        with tab_method:
            cls.render_methodology_panel(symbol)

    @classmethod
    def render_single_asset_scorecard(cls, snapshot: Dict[str, Any]):
        """
        Renders the comprehensive multi-factor scorecard for the selected instrument.
        """
        sym = snapshot["symbol"]
        score = snapshot["overall_score"]
        bias = snapshot["directional_bias"]
        bias_label = snapshot["bias_label"]
        conf = snapshot["confidence"]
        badge_color = snapshot["badge_color"]
        dq = snapshot["data_quality"]
        conflict = snapshot["conflict_analysis"]
        factors = snapshot["factor_breakdown"]
        why_items = snapshot["why_this_score"]
        upcoming = snapshot["upcoming_event"]

        price = market_data.get_latest_price(sym) or 0.0

        # Mandatory Contextual Intelligence Disclaimer Banner
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.7); border-left: 3px solid #00ffcc; border-radius: 4px; padding: 6px 12px; margin-bottom: 10px; font-size: 10.5px; color: #8a99ad; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
            <span><b>CONTEXTUAL INTELLIGENCE ONLY:</b> Edge Score evaluates directional environment. Strategy setup execution remains strictly independent.</span>
            <span style="color: #00ffcc; font-family: monospace; font-weight: 700;">MODEL v{EDGE_MODEL_VERSION}</span>
        </div>
        """, unsafe_allow_html=True)

        # -------------------------------------------------------------
        # LEVEL 1: 3-SECOND SCAN HERO CARD
        # -------------------------------------------------------------
        with st.container(border=True):
            c_hero1, c_hero2, c_hero3, c_hero4 = st.columns([1.5, 1.2, 1.1, 1.2])

            with c_hero1:
                st.markdown(f"""
                <div style="font-size: 10px; color: #8a99ad; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px;">OVERALL EDGE SCORE</div>
                <div style="display: flex; align-items: baseline; gap: 8px; margin: 2px 0;">
                    <span style="font-size: 28px; font-weight: 900; font-family: monospace; color: {badge_color};">{score:+.0f}</span>
                    <span style="font-size: 12px; font-weight: 800; color: #ffffff;">/ 100</span>
                </div>
                <div style="font-size: 11px; font-weight: 800; color: {badge_color}; text-transform: uppercase;">
                    {bias} — <span style="color: #cbd5e1; font-weight: 600;">{bias_label}</span>
                </div>
                """, unsafe_allow_html=True)

            with c_hero2:
                st.markdown(f"""
                <div style="font-size: 10px; color: #8a99ad; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px;">DATA QUALITY SCORE</div>
                <div style="display: flex; align-items: baseline; gap: 6px; margin: 2px 0;">
                    <span style="font-size: 22px; font-weight: 900; font-family: monospace; color: {dq['color']};">{dq['score']}</span>
                    <span style="font-size: 11px; color: #8a99ad;">/ 100</span>
                </div>
                <div style="font-size: 10.5px; color: {dq['color']}; font-weight: 700;">{dq['rating']}</div>
                <div style="font-size: 9.5px; color: #8a99ad;">{dq['available_factors']}/{dq['total_factors']} Factor Feeds Online</div>
                """, unsafe_allow_html=True)

            with c_hero3:
                st.markdown(f"""
                <div style="font-size: 10px; color: #8a99ad; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px;">FACTOR AGREEMENT</div>
                <div style="font-size: 22px; font-weight: 900; font-family: monospace; color: {'#00ffcc' if conflict['factor_agreement_pct'] >= 70 else ('#bef264' if conflict['factor_agreement_pct'] >= 55 else '#f59e0b')}; margin: 2px 0;">
                    {conflict['factor_agreement_pct']:.0f}%
                </div>
                <div style="font-size: 10.5px; color: #cbd5e1; font-weight: 700;">Confidence: <b style="color:#ffffff;">{conf}</b></div>
                <div style="font-size: 9.5px; color: {'#f59e0b' if conflict['has_conflict'] else '#8a99ad'};">
                    {'Conflicts Detected' if conflict['has_conflict'] else 'Factors Unified'}
                </div>
                """, unsafe_allow_html=True)

            with c_hero4:
                st.markdown(f"""
                <div style="font-size: 10px; color: #8a99ad; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px;">MARKET CONTEXT</div>
                <div style="font-size: 13px; font-weight: 800; color: #ffffff; margin: 3px 0;">{snapshot['session_name']}</div>
                <div style="font-size: 10.5px; color: #38bdf8; font-weight: 700;">Regime: {snapshot['regime_type']}</div>
                <div style="font-size: 9.5px; color: #8a99ad; margin-top: 2px;">Strategy Signal: <b style="color: #f59e0b;">WAITING FOR SETUP</b></div>
                """, unsafe_allow_html=True)

        # -------------------------------------------------------------
        # LEVEL 2: 10-SECOND SCAN FACTOR BREAKDOWN & CONFLICTS
        # -------------------------------------------------------------
        col_fb, col_why = st.columns([1.4, 1.2])

        with col_fb:
            st.markdown("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 6px; margin-bottom: 8px;">
                MULTI-FACTOR PILLAR BREAKDOWN
            </div>
            """, unsafe_allow_html=True)

            with st.container(border=True):
                for f in factors:
                    f_name = f["factor_name"]
                    f_score = f["score"]
                    f_weight = f.get("assigned_weight", 0.0) * 100.0
                    f_dir = f["direction"]
                    f_avail = f.get("data_available", True)

                    if not f_avail:
                        b_color = "#64748b"
                        bar_w = 0
                        score_str = "UNAVAILABLE"
                    else:
                        b_color = "#00ffcc" if f_score >= 25 else ("#bef264" if f_score >= 10 else ("#ef4444" if f_score <= -25 else ("#f59e0b" if f_score <= -10 else "#8a99ad")))
                        bar_w = int(abs(f_score))
                        score_str = f"{f_score:+.0f}"

                    st.markdown(f"""
                    <div style="margin-bottom: 8px; font-size: 11px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                            <span style="color: #ffffff; font-weight: 700;">{f_name}</span>
                            <span style="font-family: monospace; font-weight: 800; color: {b_color};">{score_str} <span style="color:#8a99ad; font-size:9.5px;">({f_weight:.0f}% wt)</span></span>
                        </div>
                        <div style="background: rgba(255,255,255,0.05); border-radius: 3px; height: 5px; width: 100%; overflow: hidden;">
                            <div style="background: {b_color}; height: 100%; width: {bar_w}%;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        with col_why:
            st.markdown("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 6px; margin-bottom: 8px;">
                WHY THIS SCORE? (SIGNED EVIDENCE)
            </div>
            """, unsafe_allow_html=True)

            with st.container(border=True):
                if why_items:
                    for ev in why_items:
                        pts = ev["points"]
                        sign = f"{pts:+.0f}" if pts != 0 else "•"
                        p_color = "#00ffcc" if pts > 0 else ("#ef4444" if pts < 0 else "#8a99ad")
                        bg_tint = "rgba(0,255,204,0.05)" if pts > 0 else ("rgba(239,68,68,0.05)" if pts < 0 else "rgba(255,255,255,0.02)")
                        
                        st.markdown(f"""
                        <div style="background: {bg_tint}; border-left: 2px solid {p_color}; border-radius: 3px; padding: 5px 8px; margin-bottom: 6px; font-size: 10.5px; line-height: 1.3;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-weight: 800; color: {p_color}; font-family: monospace;">{sign} PTS</span>
                                <span style="font-size: 9px; color: #8a99ad; text-transform: uppercase;">{ev['factor']}</span>
                            </div>
                            <div style="color: #cbd5e1; margin-top: 2px;">{ev['reason']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.caption("No strong factor evidence logged.")

        # -------------------------------------------------------------
        # LEVEL 3: CONFLICTS & NEXT HIGH IMPACT EVENT
        # -------------------------------------------------------------
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 6px; margin-bottom: 8px;">
                FACTOR CONFLICT ANALYSIS
            </div>
            """, unsafe_allow_html=True)
            with st.container(border=True):
                if conflict["has_conflict"]:
                    st.markdown(f"""
                    <div style="font-size: 11px; color: #f59e0b; font-weight: 700; margin-bottom: 4px;">
                        ⚠ {conflict['conflict_summary']}
                    </div>
                    """, unsafe_allow_html=True)
                    for pair in conflict.get("conflict_pairs", []):
                        st.markdown(f"<div style='font-size: 10px; color: #94a3b8; font-family: monospace;'>• {pair}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="font-size: 11px; color: #00ffcc; font-weight: 700;">
                        ✓ UNIFIED FACTORS: Technical structure and macroeconomic drivers are aligned in direction.
                    </div>
                    """, unsafe_allow_html=True)

        with col_c2:
            st.markdown("""
            <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 6px; margin-bottom: 8px;">
                NEXT HIGH-IMPACT MACRO EVENT
            </div>
            """, unsafe_allow_html=True)
            with st.container(border=True):
                if upcoming:
                    min_left = upcoming["minutes_away"]
                    time_badge = f"{min_left // 60}h {min_left % 60}m" if min_left >= 60 else f"{min_left}m"
                    u_col = "#ef4444" if min_left <= 30 else ("#f59e0b" if min_left <= 120 else "#38bdf8")
                    
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <b style="color: #ffffff; font-size: 12px;">{upcoming['title']} ({upcoming['country']})</b>
                        <span style="background: {u_col}; color: #000000; font-weight: 800; font-size: 10px; padding: 2px 6px; border-radius: 3px; font-family: monospace;">IN {time_badge}</span>
                    </div>
                    <div style="font-size: 10.5px; color: #94a3b8;">
                        Time: <b style="color:#ffffff;">{upcoming['time_utc']} UTC</b> | Forecast: <b style="color:#00ffcc;">{upcoming['forecast']}</b> | Previous: <b>{upcoming['previous']}</b>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="font-size: 11px; color: #00ffcc; font-weight: 700;">
                        ✓ CLEAN CALENDAR: No high-impact releases scheduled in the immediate 24-hour window.
                    </div>
                    """, unsafe_allow_html=True)

    @classmethod
    def render_market_ranking_view(cls):
        """
        Renders the 10-asset institutional comparative edge table.
        """
        st.markdown("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
            10-INSTRUMENT MULTI-FACTOR MARKET EDGE LEADERBOARD
        </div>
        """, unsafe_allow_html=True)

        rankings = AssetEdgeIntelligenceEngine.evaluate_all_assets()
        df = pd.DataFrame(rankings)

        if not df.empty:
            st.dataframe(
                df[["symbol", "display_name", "asset_class", "price", "overall_score", "directional_bias", "confidence", "data_quality_score", "factor_agreement_pct", "regime", "session"]],
                use_container_width=True,
                column_config={
                    "overall_score": st.column_config.NumberColumn("Edge Score", format="%+d"),
                    "price": st.column_config.NumberColumn("Price", format="%.2f"),
                    "data_quality_score": st.column_config.ProgressColumn("Data Quality", min_value=0, max_value=100, format="%d%%"),
                    "factor_agreement_pct": st.column_config.NumberColumn("Agreement", format="%.0f%%")
                }
            )
        else:
            st.info("Market ranking currently loading feeds.")

    @classmethod
    def render_historical_timeline(cls, symbol: str):
        """
        Renders immutable historical edge scorecard snapshots for the instrument.
        """
        st.markdown(f"""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">
            HISTORICAL EDGE SNAPSHOT LEDGER ({symbol})
        </div>
        """, unsafe_allow_html=True)

        history = AssetEdgeIntelligenceEngine.get_historical_snapshots(symbol, limit=20)

        if history:
            df_hist = pd.DataFrame(history)
            st.dataframe(
                df_hist[["snapshot_id", "timestamp", "overall_score", "direction", "confidence", "data_quality", "technical_score", "smc_score", "macro_score", "factor_agreement", "payload_fingerprint"]],
                use_container_width=True
            )
        else:
            st.info("No prior historical edge snapshots recorded for this instrument yet. Snapshots record automatically upon evaluation.")

    @classmethod
    def render_methodology_panel(cls, symbol: str):
        """
        Renders complete mathematical weighting, model transparency, and data sources list.
        """
        cfg = ASSET_EDGE_CONFIG.get(symbol, ASSET_EDGE_CONFIG["XAUUSD"])
        weights = cfg.get("weights", {})

        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 14px; font-size: 11.5px; line-height: 1.6; color: #cbd5e1;">
            <div style="font-size: 13px; font-weight: 800; color: #00ffcc; text-transform: uppercase; margin-bottom: 8px;">
                Asset Edge Model v{EDGE_MODEL_VERSION} — Methodology & Weighting Architecture
            </div>
            <div>
                <b>1. Objective:</b> Multi-factor market scorecards synthesize 11 quantitative factor families into a normalized directional score between <code>-100</code> (Extreme Bearish) and <code>+100</code> (Extreme Bullish).
            </div>
            <div style="margin-top: 6px;">
                <b>2. Factor Weighting for {symbol} ({cfg.get('display_name')}):</b>
            </div>
            <ul style="margin: 4px 0 8px 18px;">
                <li>Technical Structure: <b>{weights.get('technical', 0)*100:.0f}%</b></li>
                <li>Smart Money & Liquidity (SMC): <b>{weights.get('smc', 0)*100:.0f}%</b></li>
                <li>Dollar & Cross-Asset Yields: <b>{weights.get('dollar_yields', 0)*100:.0f}%</b></li>
                <li>Macroeconomic Environment: <b>{weights.get('macro', 0)*100:.0f}%</b></li>
                <li>Session & Liquidity: <b>{weights.get('session', 0)*100:.0f}%</b></li>
                <li>Market Regime: <b>{weights.get('regime', 0)*100:.0f}%</b></li>
                <li>Inflation Dynamics: <b>{weights.get('inflation', 0)*100:.0f}%</b></li>
                <li>Sentiment & COT Positioning: <b>{weights.get('positioning', 0)*100:.0f}%</b></li>
                <li>Historical Seasonality: <b>{weights.get('seasonality', 0)*100:.0f}%</b></li>
            </ul>
            <div>
                <b>3. Data Quality Gate:</b> If feed data quality drops below <code>40/100</code>, directional score is withheld as <code>UNAVAILABLE — INSUFFICIENT DATA QUALITY</code> to prevent false precision.
            </div>
            <div style="margin-top: 6px;">
                <b>4. Strict Separation:</b> The Asset Edge Scorecard provides macro and technical context. It is <b>NEVER</b> a trade signal and has <b>NO</b> ability to trigger broker orders or modify frozen strategy rules.
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_asset_edge_scorecard(symbol: str = "XAUUSD"):
    """
    Convenience functional wrapper for UI invocation.
    """
    AssetEdgeScorecardUI.render_asset_edge_scorecard(symbol)
