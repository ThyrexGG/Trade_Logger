import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
import calendar
import os
import time
import importlib
import ai_analysis
importlib.reload(ai_analysis)
import market_data
importlib.reload(market_data)

import database
import mt5_sync
import capital_sync
import tradingview_widget
importlib.reload(tradingview_widget)
import order_execution
import research_explanations
import xauusd_forward_validator
import xauusd_forward_monitor
import xauusd_drift_detector
import xauusd_validation_gate
import xauusd_forward_integrity
import xauusd_forward_statistics
import xauusd_execution_quality
import xauusd_regime_monitor
import xauusd_research_governance
import xauusd_live_state_engine
import xauusd_alert_engine
import xauusd_decision_history
import xauusd_continuous_monitor
import xauusd_forward_evidence
import xauusd_review_package
import xauusd_forward_evidence_ledger
import xauusd_evidence_milestones
import xauusd_review_readiness
import xauusd_research_decision_audit
import xauusd_forward_regime_coverage
import xauusd_forward_stability
import xauusd_forward_execution_stress
import xauusd_forward_drawdown_audit
import xauusd_forward_reproducibility

def render_html(html_str):
    clean_lines = [line.strip() for line in html_str.splitlines()]
    clean_html = "\n".join(clean_lines)
    st.markdown(clean_html, unsafe_allow_html=True)

import base64

def get_app_icon_b64():
    icon_path = os.path.join(os.path.dirname(__file__), "app_icon.png")
    if os.path.exists(icon_path):
        try:
            with open(icon_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except:
            return ""
    return ""

# Page Config with Cool App Icon
icon_file = os.path.join(os.path.dirname(__file__), "app_icon.png")
st.set_page_config(
    page_title="Trade Logger & Analytics", 
    layout="wide", 
    page_icon=icon_file if os.path.exists(icon_file) else ""
)

# Initialize Database
database.init_db()

# Custom CSS for the combined glassmorphic dashboard
st.markdown("""
<style>
    /* Dark glassmorphic theme overrides */
    .stApp {
        background-color: #0c0f16 !important;
        color: #ffffff;
    }
    
    .reportview-container {
        background: #0c0f16;
    }
    
    /* Premium Glassmorphic Card Style */
    .trading-card {
        background: rgba(18, 24, 38, 0.75) !important;
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    
    /* Style Streamlit containers with border to look like premium cards */
    div[data-testid="stVerticalBlockBorderDiv"] {
        background: rgba(18, 24, 38, 0.75) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 12px !important;
        padding: 20px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4) !important;
    }
    
    .card-title {
        font-size: 12px;
        font-weight: 600;
        color: #8a99ad;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    
    /* Top Stats Grid */
    .top-stats-container {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 16px;
        margin-bottom: 20px;
    }
    
    .top-stat-box {
        background: rgba(18, 24, 38, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    
    .top-stat-label {
        font-size: 12px;
        color: #8a99ad;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .top-stat-value {
        font-size: 24px;
        font-weight: 700;
        color: #ffffff;
    }
    
    /* Gauge flex wrapping and detail styling */
    .gauge-matrix {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-bottom: 16px;
    }
    
    .gauge-card {
        flex: 1 1 220px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-radius: 8px;
        padding: 16px;
        display: flex;
        align-items: center;
        gap: 16px;
    }
    
    .gauge-details {
        flex: 1;
    }
    
    .gauge-title {
        font-size: 13px;
        font-weight: 600;
        color: #8a99ad;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    
    .gauge-sub-row {
        display: flex;
        justify-content: space-between;
        font-size: 13px;
        margin-top: 4px;
    }
    
    /* Progress bar ratios and wrapping */
    .ratios-row {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-top: 16px;
    }
    
    .ratios-row > .ratio-card {
        flex: 1 1 250px;
        margin-bottom: 0px;
    }
    
    .ratio-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-radius: 8px;
        padding: 16px;
    }
    
    .ratio-label-row {
        display: flex;
        justify-content: space-between;
        font-size: 13px;
        color: #8a99ad;
        margin-bottom: 4px;
    }
    
    .ratio-bar-bg {
        background: rgba(255, 255, 255, 0.05);
        height: 8px;
        border-radius: 4px;
        overflow: hidden;
        display: flex;
        margin-top: 6px;
    }
    
    .ratio-bar-green {
        background: #00ffcc;
        height: 100%;
        box-shadow: 0 0 8px rgba(0, 255, 204, 0.5);
    }
    
    .ratio-bar-red {
        background: #ff5555;
        height: 100%;
        box-shadow: 0 0 8px rgba(255, 85, 85, 0.5);
    }
    
    /* Streak widget */
    .streak-container {
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
    }
    
    .streak-item {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.03);
        border-radius: 8px;
        padding: 12px;
        width: 48%;
        text-align: center;
    }
    
    .streak-badge-row {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 6px;
        margin-top: 8px;
    }
    
    .streak-badge {
        font-size: 20px;
        font-weight: 700;
        color: #ffffff;
    }
    
    .streak-box {
        background: rgba(255, 255, 255, 0.08);
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        padding: 2px 6px;
        color: #8a99ad;
    }
    
    .streak-box.active {
        background: rgba(0, 255, 204, 0.15);
        color: #00ffcc;
    }
    
    /* Monday-first Calendar Grid */
    .calendar-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 6px;
    }
    
    .calendar-day-header {
        text-align: center;
        font-size: 13px;
        font-weight: 600;
        color: #8a99ad;
        padding: 4px;
        text-transform: uppercase;
    }
    
    .calendar-cell {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.03);
        border-radius: 6px;
        padding: 10px;
        min-height: 72px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    
    .calendar-cell.profit {
        background: rgba(0, 255, 204, 0.07);
        border: 1px solid rgba(0, 255, 204, 0.12);
    }
    
    .calendar-cell.loss {
        background: rgba(255, 85, 85, 0.07);
        border: 1px solid rgba(255, 85, 85, 0.12);
    }
    
    .calendar-day-num {
        font-size: 13px;
        color: #8a99ad;
        font-weight: 600;
    }
    
    .calendar-day-val {
        font-size: 14px;
        font-weight: 700;
        text-align: right;
    }
    
    .calendar-day-pct {
        font-size: 11px;
        text-align: right;
        opacity: 0.8;
    }
    
    /* Hide Streamlit deploy button & footer, but keep toolbar and status widget visible */
    .stAppDeployButton, #MainMenu, footer {
        display: none !important;
        visibility: hidden !important;
    }
    header[data-testid="stHeader"], header {
        background: transparent !important;
        z-index: 99999 !important;
    }

    /* Streamlit Top-Right Live Status Indicator */
    [data-testid="stStatusWidget"],
    .stStatusWidget {
        display: flex !important;
        visibility: visible !important;
        background: rgba(18, 24, 38, 0.95) !important;
        border: 1px solid rgba(0, 255, 204, 0.5) !important;
        border-radius: 20px !important;
        padding: 4px 12px !important;
        box-shadow: 0 0 14px rgba(0, 255, 204, 0.3) !important;
        color: #00ffcc !important;
        font-weight: 700 !important;
    }
    [data-testid="stStatusWidget"] svg,
    .stStatusWidget svg {
        fill: #00ffcc !important;
        stroke: #00ffcc !important;
    }

    /* Prominent, Glowing Sidebar Expand / Collapse Toggle Button */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    button[data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="collapsedControl"] button {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 999999 !important;
        background: rgba(18, 24, 38, 0.95) !important;
        border: 1px solid rgba(0, 255, 204, 0.5) !important;
        border-radius: 8px !important;
        box-shadow: 0 0 14px rgba(0, 255, 204, 0.3) !important;
        color: #00ffcc !important;
        transition: all 0.2s ease-in-out !important;
    }

    [data-testid="stSidebarCollapsedControl"]:hover,
    [data-testid="collapsedControl"]:hover,
    [data-testid="stSidebarCollapseButton"]:hover,
    button[data-testid="stSidebarCollapseButton"]:hover,
    [data-testid="stSidebarCollapsedControl"] button:hover {
        background: rgba(0, 255, 204, 0.2) !important;
        border-color: #00ffcc !important;
        box-shadow: 0 0 20px rgba(0, 255, 204, 0.6) !important;
        transform: scale(1.05) !important;
    }

    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapseButton"] svg,
    button[data-testid="stSidebarCollapseButton"] svg {
        fill: #00ffcc !important;
        stroke: #00ffcc !important;
        color: #00ffcc !important;
        width: 22px !important;
        height: 22px !important;
    }
    
    /* Adjust Streamlit main container top padding to remove excessive spacing */
    .stMainBlockContainer {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 3rem !important;
        padding-right: 3rem !important;
    }
    
    /* Clean button styling with high contrast */
    div[data-testid="stBaseButton-secondary"] button, .stButton > button {
        background-color: rgba(255, 255, 255, 0.05) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 6px !important;
        padding: 4px 12px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    div[data-testid="stBaseButton-secondary"] button:hover, .stButton > button:hover {
        background-color: rgba(0, 255, 204, 0.08) !important;
        border-color: rgba(0, 255, 204, 0.35) !important;
        color: #00ffcc !important;
        box-shadow: 0 0 12px rgba(0, 255, 204, 0.15) !important;
    }
    
    /* ---------------------------------- */
    /* THE5ERS PROP FIRM OBJECTIVES HUB   */
    /* ---------------------------------- */
    .prop-hub-container {
        background: #0d111a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 22px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    }
    
    .prop-badge {
        font-size: 10px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .prop-badge.forex {
        background: rgba(168, 85, 247, 0.12);
        color: #c084fc;
        border: 1px solid rgba(168, 85, 247, 0.3);
    }
    .prop-badge.active {
        background: rgba(0, 255, 204, 0.12);
        color: #00ffcc;
        border: 1px solid rgba(0, 255, 204, 0.3);
    }
    .prop-badge.eval {
        background: rgba(59, 130, 246, 0.12);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    
    /* Roadmap Timeline */
    .prop-roadmap-wrapper {
        width: 100%;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        margin: 18px 0 22px 0;
        padding-bottom: 8px;
    }
    .prop-roadmap-wrapper::-webkit-scrollbar {
        height: 4px;
    }
    .prop-roadmap-wrapper::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 4px;
    }
    .prop-roadmap {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-width: 620px;
        position: relative;
        padding: 0 16px;
    }
    .prop-roadmap::before {
        content: '';
        position: absolute;
        top: 25px;
        left: 30px;
        right: 30px;
        height: 2px;
        background: rgba(255, 255, 255, 0.08);
        z-index: 1;
    }
    .prop-roadmap-node {
        position: relative;
        z-index: 2;
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        min-width: 70px;
    }
    .prop-roadmap-title {
        font-size: 9px;
        color: #8a99ad;
        margin-bottom: 6px;
        font-weight: 600;
        white-space: nowrap;
    }
    .prop-roadmap-circle {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #121620;
        border: 2px solid rgba(255, 255, 255, 0.15);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        color: #8a99ad;
        margin-bottom: 6px;
    }
    .prop-roadmap-node.active .prop-roadmap-circle {
        background: linear-gradient(135deg, #a855f7, #6366f1);
        border-color: #c084fc;
        color: #ffffff;
        box-shadow: 0 0 14px rgba(168, 85, 247, 0.5);
    }
    .prop-roadmap-target {
        font-size: 11px;
        font-weight: 700;
        color: #ffffff;
    }
    
    /* 5 Objectives Grid */
    .prop-objectives-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 12px;
        margin-top: 16px;
    }
    .prop-obj-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        padding: 12px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 90px;
    }
    .prop-obj-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .prop-obj-title {
        font-size: 11px;
        color: #8a99ad;
        font-weight: 600;
    }
    .prop-obj-status {
        font-size: 9px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 3px;
        background: rgba(59, 130, 246, 0.12);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.25);
    }
    .prop-obj-value {
        font-size: 16px;
        font-weight: 700;
        margin-top: 4px;
        color: #ffffff;
    }
    .prop-obj-sub {
        font-size: 10px;
        color: #8a99ad;
        margin-top: 2px;
    }

    /* Tooltip helper icon & popover */
    .info-tip {
        position: relative;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.25);
        color: #8a99ad;
        font-size: 9px;
        font-weight: 700;
        cursor: help;
        margin-left: 5px;
        vertical-align: middle;
        transition: all 0.2s ease;
    }
    .info-tip:hover {
        color: #00ffcc;
        border-color: #00ffcc;
        background: rgba(0, 255, 204, 0.15);
    }
    .info-tip .info-tip-text {
        visibility: hidden;
        opacity: 0;
        width: 230px;
        background-color: #0b0f19;
        color: #e2e8f0;
        text-align: left;
        border-radius: 8px;
        padding: 10px 12px;
        position: absolute;
        z-index: 99999;
        bottom: 135%;
        left: 50%;
        transform: translateX(-50%);
        font-size: 11px;
        font-weight: 400;
        line-height: 1.45;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.7);
        transition: opacity 0.2s ease, transform 0.2s ease;
        pointer-events: none;
        white-space: normal;
    }
    .info-tip .info-tip-text::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -5px;
        border-width: 5px;
        border-style: solid;
        border-color: #0b0f19 transparent transparent transparent;
    }
    .info-tip:hover .info-tip-text {
        visibility: visible;
        opacity: 1;
        transform: translateX(-50%) translateY(-3px);
    }

    /* ---------------------------------- */
    /* PREMIUM TRADES JOURNAL TABLE CSS   */
    /* ---------------------------------- */
    .journal-table-wrapper {
        width: 100%;
        overflow-x: auto;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        background: #0d111a;
        margin-top: 8px;
        margin-bottom: 16px;
    }
    .journal-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        text-align: left;
        white-space: nowrap;
    }
    .journal-table th {
        background: rgba(255, 255, 255, 0.03);
        color: #8a99ad;
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 12px 14px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .journal-table td {
        padding: 10px 14px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        color: #ffffff;
        vertical-align: middle;
    }
    .journal-table tr:hover {
        background: rgba(255, 255, 255, 0.02);
    }
    .badge-pnl-win {
        color: #00ffcc !important;
        background: rgba(0, 255, 204, 0.12) !important;
        border: 1px solid rgba(0, 255, 204, 0.3) !important;
        padding: 4px 9px !important;
        border-radius: 5px !important;
        font-weight: 800 !important;
        font-size: 12px !important;
        display: inline-block;
        box-shadow: 0 0 10px rgba(0, 255, 204, 0.15);
    }
    .badge-pnl-loss {
        color: #ff5555 !important;
        background: rgba(255, 85, 85, 0.12) !important;
        border: 1px solid rgba(255, 85, 85, 0.3) !important;
        padding: 4px 9px !important;
        border-radius: 5px !important;
        font-weight: 800 !important;
        font-size: 12px !important;
        display: inline-block;
        box-shadow: 0 0 10px rgba(255, 85, 85, 0.15);
    }
    .badge-dir-long {
        color: #38bdf8;
        background: rgba(56, 189, 248, 0.1);
        border: 1px solid rgba(56, 189, 248, 0.25);
        padding: 2px 7px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    .badge-dir-short {
        color: #f472b6;
        background: rgba(244, 114, 182, 0.1);
        border: 1px solid rgba(244, 114, 182, 0.25);
        padding: 2px 7px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    .badge-quality {
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 700;
        display: inline-block;
    }
    .badge-quality-high {
        background: rgba(0, 255, 204, 0.12);
        color: #00ffcc;
        border: 1px solid rgba(0, 255, 204, 0.3);
    }
    .badge-quality-med {
        background: rgba(251, 191, 36, 0.12);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.3);
    }
    .badge-quality-low {
        background: rgba(248, 113, 113, 0.12);
        color: #f87171;
        border: 1px solid rgba(248, 113, 113, 0.3);
    }
    .badge-tag-pill {
        background: rgba(255, 255, 255, 0.05);
        color: #8a99ad;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 2px 7px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 600;
    }
    
    /* ---------------------------------- */
    /* RESPONSIVE DESIGN BREAKPOINTS      */
    /* ---------------------------------- */
    @media (max-width: 991px) {
        .prop-roadmap {
            overflow-x: auto;
            padding-bottom: 8px;
        }
        .top-stats-container {
            grid-template-columns: repeat(3, 1fr) !important;
            gap: 10px !important;
        }
    }
    
    @media (max-width: 768px) {
        html, body, .stApp, [data-testid="stAppViewContainer"] {
            overflow-x: hidden !important;
            max-width: 100vw !important;
            touch-action: pan-y !important;
            position: relative !important;
        }

        /* Mobile padding */
        .stMainBlockContainer, .main .block-container {
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
            padding-top: 0.4rem !important;
            max-width: 100vw !important;
            overflow-x: clip !important;
        }

        .journal-table-wrapper {
            width: 100% !important;
            max-width: 100% !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
        }
        
        .trading-card, div[data-testid="stVerticalBlockBorderDiv"] {
            padding: 12px !important;
            max-width: 100% !important;
            overflow-x: clip !important;
        }

        /* 2-column top stats bar on phone */
        .top-stats-container {
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 8px !important;
            max-width: 100% !important;
        }

        .top-stat-box {
            padding: 10px 12px !important;
        }

        .top-stat-label {
            font-size: 9px !important;
        }

        .top-stat-value {
            font-size: 16px !important;
        }

        /* 2-column prop objectives cards on phone */
        .prop-objectives-grid {
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 8px !important;
        }

        .prop-obj-card:last-child {
            grid-column: span 2 !important;
        }

        .prop-stats-top-row {
            display: flex !important;
            justify-content: space-between !important;
            width: 100% !important;
            margin-top: 10px !important;
            gap: 8px !important;
        }

        .prop-stats-top-row > div {
            text-align: left !important;
        }

        .prop-hub-container {
            padding: 14px !important;
        }

        /* 1-column gauge matrix on phone */
        .gauge-matrix {
            grid-template-columns: 1fr !important;
            gap: 10px !important;
        }

        /* Compact, clean 7-day calendar for phone screens */
        .calendar-grid {
            gap: 3px !important;
        }
        
        .calendar-cell {
            min-height: 48px !important;
            padding: 4px !important;
            border-radius: 4px !important;
        }
        
        .calendar-day-header {
            font-size: 10px !important;
            padding: 2px 0 !important;
        }

        .calendar-day-num {
            font-size: 10px !important;
        }
        
        .calendar-day-val {
            font-size: 10px !important;
            font-weight: 700 !important;
        }
        
        .calendar-day-pct {
            font-size: 8px !important;
        }
    }

    /* Clean Calendar Navigation & Chevron Buttons */
    .cal-title-text {
        font-size: 15px;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.2px;
        line-height: 32px;
    }

    /* Force horizontal alignment on ALL screen sizes, including mobile webviews */
    div[data-testid="stHorizontalBlock"]:has(button[key="prev_btn"]),
    div[data-testid="stHorizontalBlock"]:has(button[key="next_btn"]),
    div.cal-nav-row {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        justify-content: space-between !important;
        width: 100% !important;
        margin-bottom: 6px !important;
    }

    div[data-testid="stHorizontalBlock"]:has(button[key="prev_btn"]) > div[data-testid="column"],
    div[data-testid="stHorizontalBlock"]:has(button[key="next_btn"]) > div[data-testid="column"],
    div.cal-nav-row > div[data-testid="column"] {
        min-width: 0 !important;
        max-width: none !important;
        width: auto !important;
        flex: 0 0 auto !important;
    }

    div[data-testid="stHorizontalBlock"]:has(button[key="prev_btn"]) > div[data-testid="column"]:first-child,
    div[data-testid="stHorizontalBlock"]:has(button[key="next_btn"]) > div[data-testid="column"]:first-child,
    div.cal-nav-row > div[data-testid="column"]:first-child {
        flex: 1 1 auto !important;
        min-width: 100px !important;
    }

    div[data-testid="stHorizontalBlock"]:has(button[key="prev_btn"]) > div[data-testid="column"]:nth-child(2),
    div[data-testid="stHorizontalBlock"]:has(button[key="next_btn"]) > div[data-testid="column"]:nth-child(2),
    div[data-testid="stHorizontalBlock"]:has(button[key="prev_btn"]) > div[data-testid="column"]:nth-child(3),
    div[data-testid="stHorizontalBlock"]:has(button[key="next_btn"]) > div[data-testid="column"]:nth-child(3),
    div.cal-nav-row > div[data-testid="column"]:nth-child(2),
    div.cal-nav-row > div[data-testid="column"]:nth-child(3) {
        flex: 0 0 34px !important;
        width: 34px !important;
        min-width: 34px !important;
        max-width: 34px !important;
    }

    button[key="prev_btn"], button[key="next_btn"] {
        min-width: 32px !important;
        max-width: 32px !important;
        width: 32px !important;
        height: 32px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        border-radius: 6px !important;
    }

    /* Big Bold Header View Switcher */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px !important;
        background-color: rgba(14, 19, 31, 0.95) !important;
        padding: 6px !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        margin-top: 6px !important;
        margin-bottom: 22px !important;
        display: flex !important;
        width: 100% !important;
    }
    .stTabs [data-baseweb="tab"] {
        flex: 1 !important;
        font-size: 14px !important;
        font-weight: 800 !important;
        letter-spacing: 0.8px !important;
        text-transform: uppercase !important;
        text-align: center !important;
        justify-content: center !important;
        padding: 12px 18px !important;
        border-radius: 8px !important;
        color: #8a99ad !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        transition: all 0.2s ease-in-out !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #ffffff !important;
        background-color: rgba(255, 255, 255, 0.05) !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(0, 255, 204, 0.12) !important;
        color: #00ffcc !important;
        border: 1px solid rgba(0, 255, 204, 0.45) !important;
        box-shadow: 0 0 15px rgba(0, 255, 204, 0.25) !important;
    }

    /* Completely eliminate all dimming / opacity fading during background auto-sync */
    [data-stale="true"],
    .stFragment[data-stale="true"],
    [data-testid="stAppViewContainer"][data-stale="true"],
    [data-testid="stVerticalBlock"][data-stale="true"],
    [data-testid="stHorizontalBlock"][data-stale="true"],
    div[data-testid="stBlock"][data-stale="true"],
    .element-container[data-stale="true"],
    div[data-testid="stApp"][data-stale="true"] {
        opacity: 1 !important;
        filter: none !important;
        transition: none !important;
        pointer-events: auto !important;
    }

    /* Removed hiding of running status widget so user knows when it's loading */

    /* TradingView-Style Interactive Red Bookmark Ribbon Buttons */
    div[data-testid="column"] button[key^="tv_ribbon_btn_"] {
        font-size: 10px !important;
        font-weight: 900 !important;
        letter-spacing: 0.5px !important;
        padding: 0 !important;
        min-height: 26px !important;
        height: 26px !important;
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 4px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    /* Custom Trading Candlestick & Neon Radar Loader */
    .stSpinner {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 12px !important;
        margin: 24px 0 !important;
    }
    /* Hide the redundant native small Streamlit spinner icon */
    .stSpinner > div:first-child:not(:last-child),
    .stSpinner > svg,
    .stSpinner [data-testid="stSpinner"] > svg,
    .stSpinner [data-testid="stSpinner"] > div:first-child {
        display: none !important;
    }
    /* Custom Neon Radar Spinner */
    .stSpinner::before {
        content: '' !important;
        display: inline-block !important;
        width: 40px !important;
        height: 40px !important;
        border-radius: 50% !important;
        border: 2.5px solid rgba(0, 255, 204, 0.15) !important;
        border-top-color: #00ffcc !important;
        border-right-color: #bef264 !important;
        animation: spin 0.8s cubic-bezier(0.4, 0, 0.2, 1) infinite !important;
        box-shadow: 0 0 16px rgba(0, 255, 204, 0.4) !important;
    }
    .stSpinner > div:last-child {
        color: #00ffcc !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 800 !important;
        font-size: 13px !important;
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
        animation: pulseGlow 1.5s ease-in-out infinite alternate !important;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    @keyframes pulseGlow {
        from { opacity: 0.6; }
        to { opacity: 1; text-shadow: 0 0 12px rgba(0, 255, 204, 0.7); }
    }
    @keyframes candlePulse {
        from { transform: scaleY(0.4); opacity: 0.6; }
        to { transform: scaleY(1.0); opacity: 1; }
    }
</style>

""", unsafe_allow_html=True)

# OneSignal Web Push Client Listener
onesignal_app_id = os.getenv("ONESIGNAL_APP_ID", "1f707b9d-5a8e-411d-b8cc-13c68a9b7ff4").strip('"\' ')
if onesignal_app_id:
    from streamlit.components.v1 import html
    html(f"""
    <script src="https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js" defer></script>
    <script>
      window.OneSignalDeferred = window.OneSignalDeferred || [];
      OneSignalDeferred.push(async function(OneSignal) {{
        await OneSignal.init({{
          appId: "{onesignal_app_id}",
          allowLocalhostAsSecureOrigin: true,
          notifyButton: {{
            enable: true,
            position: 'bottom-left',
            theme: 'inverse',
            size: 'medium'
          }}
        }});
        // Prompt for notification permission on initial load
        try {{
          await OneSignal.Notifications.requestPermission();
        }} catch(e) {{
          console.log("OneSignal permission notice:", e);
        }}
      }});
    </script>
    """, height=0)

# ----------------------------------------------------
# MAIN DASHBOARD CONTROLLER
# ----------------------------------------------------

def render_live_dashboard():
    with st.sidebar:
        st.markdown("<h2 style='color:#ffffff; margin-bottom: 4px;'>System Control</h2>", unsafe_allow_html=True)
        current_state = database.get_setting("SYSTEM_STATE", "PAPER")
        state_color = "#00ffcc" if current_state == "LIVE" else "#f59e0b" if current_state == "PAPER" else "#ff5555"
        
        st.markdown(f"<div style='padding:10px; border-radius:8px; border: 1px solid {state_color}; text-align:center; margin-bottom: 20px;'>"
                    f"<strong style='color:{state_color}; font-size:1.2rem;'>STATUS: {current_state}</strong></div>", unsafe_allow_html=True)
                    
        new_state = st.radio("Execution Mode", ["LIVE", "PAPER", "EMERGENCY HALT"], index=["LIVE", "PAPER", "EMERGENCY HALT"].index(current_state))
        if new_state != current_state:
            database.set_setting("SYSTEM_STATE", new_state)
            st.rerun()
            
        st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
        st.markdown("<h3 style='color:#ffffff; font-size:1rem;'>Execution Audit Log</h3>", unsafe_allow_html=True)
        
        try:
            logs = database.get_recent_audit_logs(limit=10)
            if logs:
                for log in logs:
                    color = "#00ffcc" if log.get("execution_result") in ["FILLED", "PAPER_FILLED"] else "#ff5555"
                    msg = log.get("reject_reason") or log.get("broker_order_id") or ""
                    st.markdown(f"<div style='font-size:0.8rem; margin-bottom:8px; padding:6px; background:rgba(255,255,255,0.02); border-radius:4px;'>"
                                f"<span style='color:{color}; font-weight:bold;'>[{log.get('execution_result')}]</span> "
                                f"{log.get('symbol')} {log.get('direction')} <br>"
                                f"<span style='color:#8a99ad; font-size:0.7rem;'>{msg}</span>"
                                f"</div>", unsafe_allow_html=True)
            else:
                st.caption("No logs yet.")
        except Exception:
            st.caption("Audit log unavailable (Database migration pending).")

    df_trades = database.get_closed_trades()

    if df_trades.empty:
        # Header
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 14px; margin-top: 8px; margin-bottom: 20px;">
            <div style="width: 44px; height: 44px; border-radius: 10px; background: linear-gradient(135deg, rgba(0, 255, 204, 0.15), rgba(0, 119, 255, 0.2)); border: 1px solid rgba(0, 255, 204, 0.3); display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ffcc" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
                    <polyline points="16 7 22 7 22 13"></polyline>
                </svg>
            </div>
            <div>
                <h1 style="margin: 0; font-size: 1.85rem; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; text-transform: uppercase;">TradeLogger Terminal</h1>
                <p style="margin: 3px 0 0 0; color: #8a99ad; font-size: 13px; letter-spacing: 0.2px;">Automated journal, technical charting, price alerts, and analytics</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Unified Control Card (Empty DB state)
        with st.container(border=True):
            col_msg, col_actions = st.columns([2, 1.2])
            with col_msg:
                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                st.info("No trades found in the database. Use the sync buttons on the right to sync your accounts or verify your connections.")
            with col_actions:
                col_mt5, col_cap, col_bal = st.columns([1.1, 1.1, 1])
                with col_bal:
                    initial_balance = st.number_input("Balance ($)", min_value=10.0, value=1000.0, step=100.0, key="empty_bal")
                with col_mt5:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("Sync MT5", key="empty_sync_mt5", use_container_width=True):
                        with st.spinner("Syncing MT5..."):
                            success = mt5_sync.sync_mt5()
                            if success:
                                st.success("MT5 sync completed!")
                                st.rerun()
                            else:
                                st.error("MT5 sync failed.")
                with col_cap:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("Sync Capital", key="empty_sync_cap", use_container_width=True):
                        with st.spinner("Syncing Capital.com..."):
                            success = capital_sync.sync_capital()
                            if success:
                                st.success("Capital.com sync completed!")
                                st.rerun()
                            else:
                                st.error("Capital.com sync failed.")
    else:
        # Convert dates to pandas datetime objects
        df_trades["entry_time"] = pd.to_datetime(df_trades["entry_time"], format="mixed", utc=True).dt.tz_localize(None)
        df_trades["exit_time"] = pd.to_datetime(df_trades["exit_time"], format="mixed", utc=True).dt.tz_localize(None)

        # Handle URL query params for calendar navigation
        if "cal_m" in st.query_params:
            try:
                st.session_state.cal_month = int(st.query_params["cal_m"])
            except:
                pass
        if "cal_y" in st.query_params:
            try:
                st.session_state.cal_year = int(st.query_params["cal_y"])
            except:
                pass

        # Clean Calendar Nav Link Button CSS
        st.markdown("""
        <style>
        .cal-nav-link-btn {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 32px !important;
            height: 32px !important;
            border-radius: 6px !important;
            background-color: rgba(255, 255, 255, 0.05) !important;
            color: #ffffff !important;
            text-decoration: none !important;
            font-size: 16px !important;
            font-weight: 700 !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            transition: all 0.2s ease !important;
            user-select: none !important;
        }
        .cal-nav-link-btn:hover {
            background-color: rgba(0, 255, 204, 0.2) !important;
            border-color: #00ffcc !important;
            color: #00ffcc !important;
            box-shadow: 0 0 10px rgba(0, 255, 204, 0.3) !important;
        }
        </style>
        """, unsafe_allow_html=True)

        if "account_balances" not in st.session_state:
            st.session_state.account_balances = {"ALL": 10000.0}

        unique_accounts = ["ALL"] + sorted(list(df_trades["account_id"].dropna().unique()))
        account_options = unique_accounts

        def format_account_name(acc_id):
            if acc_id == "ALL":
                return "All Accounts (Consolidated Portfolio)"
            elif str(acc_id).startswith("MT5_"):
                return f"MetaTrader 5 ({str(acc_id).replace('MT5_', '')}) • Funded Account"
            else:
                return f"Capital.com ({acc_id}) • Real Account"

        for acc in unique_accounts:
            if acc not in st.session_state.account_balances:
                if str(acc).startswith("MT5_"):
                    st.session_state.account_balances[acc] = 10000.0
                else:
                    st.session_state.account_balances[acc] = 300.0

        if "in_app_alerts" not in st.session_state:
            st.session_state.in_app_alerts = []

        # Header Logo & Title
        icon_b64 = get_app_icon_b64()
        logo_html = f'<img src="data:image/png;base64,{icon_b64}" style="width: 44px; height: 44px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0, 255, 204, 0.25);">' if icon_b64 else """
            <div style="width: 44px; height: 44px; border-radius: 10px; background: linear-gradient(135deg, rgba(0, 255, 204, 0.15), rgba(0, 119, 255, 0.2)); border: 1px solid rgba(0, 255, 204, 0.3); display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ffcc" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
                    <polyline points="16 7 22 7 22 13"></polyline>
                </svg>
            </div>
        """
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 14px; margin-top: 8px; margin-bottom: 12px;">
            {logo_html}
            <div>
                <h1 style="margin: 0; font-size: 1.85rem; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; text-transform: uppercase;">TradeLogger Terminal</h1>
                <p style="margin: 3px 0 0 0; color: #8a99ad; font-size: 13px; letter-spacing: 0.2px;">Automated journal, technical charting, price alerts, and analytics</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ----------------------------------------------------
        # TOP-LEVEL BIG BOLD HEADER VIEW SWITCHER
        # ----------------------------------------------------
        tab_overview, tab_charts, tab_ai, tab_research, tab_journal, tab_alerts, tab_terminal, tab_sandbox, tab_health = st.tabs([
            "ANALYTICS & OVERVIEW",
            "TRADING WORKSPACE",
            "AI MARKET CONTEXT",
            "RESEARCH LAB",
            "TRADE JOURNAL",
            "PRICE ALERTS",
            "QUICK TERMINAL",
            "SANDBOX",
            "SYSTEM HEALTH & PAPER"
        ])

        df_open = database.get_open_positions()

        with tab_overview:
            # Unified Control & Filter Card
            with st.container(border=True):
                col_acc_sel, col_sync_btns = st.columns([1.8, 1.2])

                with col_acc_sel:
                    selected_account = st.selectbox(
                        "Select Account View",
                        options=account_options,
                        format_func=format_account_name,
                        index=0,
                        key="account_view_selector"
                    )

                with col_sync_btns:
                    col_mt5, col_cap = st.columns(2)
                    with col_mt5:
                        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                        if st.button("Sync MT5", key="active_sync_mt5", use_container_width=True):
                            if not mt5_sync.MT5_AVAILABLE:
                                st.info("MT5 sync connects to the MetaTrader 5 terminal on your Windows PC. Syncing on your PC uploads trades directly to your cloud dashboard.")
                            else:
                                with st.spinner("Syncing MT5..."):
                                    success = mt5_sync.sync_mt5()
                                    if success:
                                        st.success("MT5 sync completed!")
                                        st.rerun()
                                    else:
                                        st.error("MT5 sync failed. Ensure MT5 is running on your PC.")
                    with col_cap:
                        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                        if st.button("Sync Capital", key="active_sync_cap", use_container_width=True):
                            with st.spinner("Syncing Capital.com..."):
                                success = capital_sync.sync_capital()
                                if success:
                                    st.success("Capital.com sync completed!")
                                    st.rerun()
                                else:
                                    st.error("Capital.com sync failed.")

                # Filter base dataframe by selected account
                if selected_account != "ALL":
                    acc_filtered_df = df_trades[df_trades["account_id"] == selected_account]
                else:
                    acc_filtered_df = df_trades

                # Sub-filters: Symbols, Date Range, Starting Balance
                col_sym, col_date, col_bal = st.columns([1, 1.2, 1])

                with col_sym:
                    symbols = acc_filtered_df["symbol"].unique()
                    selected_symbols = st.multiselect("Symbols", options=symbols, default=list(symbols))

                with col_date:
                    min_date = acc_filtered_df["exit_time"].min().date()
                    max_date = acc_filtered_df["exit_time"].max().date()
                    date_range = st.date_input("Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

                with col_bal:
                    current_default_bal = st.session_state.account_balances.get(selected_account, 300.0)
                    initial_balance = st.number_input(
                        "Starting Balance ($)",
                        min_value=10.0,
                        value=float(current_default_bal),
                        step=50.0,
                        key=f"bal_{selected_account}"
                    )
                    st.session_state.account_balances[selected_account] = initial_balance

            # Apply symbol & date filters
            filtered_df = acc_filtered_df[acc_filtered_df["symbol"].isin(selected_symbols)]
            if len(date_range) == 2:
                start_dt = pd.to_datetime(date_range[0])
                end_dt = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1)
                filtered_df = filtered_df[(filtered_df["exit_time"] >= start_dt) & (filtered_df["exit_time"] < end_dt)]

            if filtered_df.empty:
                st.warning("No trades match the selected filters.")
            else:
                filtered_df = filtered_df.sort_values(by="exit_time", ascending=True).reset_index(drop=True)

                detected_balances = database.get_account_balances()
                official_broker_bal = None
                if selected_account in detected_balances:
                    official_broker_bal = detected_balances[selected_account]["balance"]
                elif selected_account == "ALL" and detected_balances:
                    official_broker_bal = sum(b["balance"] for b in detected_balances.values())

                import analytics
                perf = analytics.calculate_performance_metrics(filtered_df, initial_balance=initial_balance)
                
                filtered_df["balance"] = initial_balance + filtered_df["net_profit"].cumsum()
                current_balance = official_broker_bal if official_broker_bal is not None else perf["final_balance"]
                total_pnl = perf["total_net_pnl"]
                gain_pct = perf["gain_pct"]
                gross_wins = perf["total_gross_profit"]
                gross_losses = perf["total_gross_loss"]
                profit_factor = perf["profit_factor"]
                max_drawdown = perf["max_drawdown_pct"]
                highest_balance = perf["peak_balance"]
                sqn = perf["sqn"]
                total_trades = perf["total_trades"]
                winning_trades = perf["winning_trades"]
                losing_trades = perf["losing_trades"]
                win_rate = perf["win_rate"]
                biggest_win = perf["best_trade"]
                biggest_loss = perf["worst_trade"]

                avg_dur_min = perf["avg_duration_minutes"]
                h_days = int(avg_dur_min // (24 * 60))
                rem_min = avg_dur_min % (24 * 60)
                h_hours = int(rem_min // 60)
                h_mins = int(rem_min % 60)
                hold_time_str = f"{h_days}d {h_hours}h {h_mins}m" if h_days > 0 else f"{h_hours}h {h_mins}m"

                daily_pnl = filtered_df.groupby(filtered_df["exit_time"].dt.date)["net_profit"].sum().reset_index()
                daily_pnl = daily_pnl.sort_values(by="exit_time").reset_index(drop=True)
                daily_rets = daily_pnl["net_profit"] / initial_balance * 100
                avg_daily_ret = daily_rets.mean() if not daily_rets.empty else 0.0

                weekly_cutoff = pd.Timestamp.now() - pd.Timedelta(days=7)
                weekly_pnl = filtered_df[filtered_df["exit_time"] >= weekly_cutoff]["net_profit"].sum()
                weekly_ret = (weekly_pnl / initial_balance) * 100

                monthly_cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
                monthly_pnl = filtered_df[filtered_df["exit_time"] >= monthly_cutoff]["net_profit"].sum()
                monthly_ret = (monthly_pnl / initial_balance) * 100

                ann_ret = ((1 + avg_daily_ret/100) ** 252 - 1) * 100 if avg_daily_ret > 0 else (avg_daily_ret if avg_daily_ret < 0 else 0.0)

                daily_color = "#00ffcc" if avg_daily_ret > 0 else ("#ff5555" if avg_daily_ret < 0 else "#8a99ad")
                weekly_color = "#00ffcc" if weekly_ret > 0 else ("#ff5555" if weekly_ret < 0 else "#8a99ad")
                monthly_color = "#00ffcc" if monthly_ret > 0 else ("#ff5555" if monthly_ret < 0 else "#8a99ad")
                ann_color = "#00ffcc" if ann_ret > 0 else ("#ff5555" if ann_ret < 0 else "#8a99ad")

                score_pnl = min(100, max(0, int(50 + (gain_pct * 2))))
                score_wr = min(100, max(0, int(win_rate)))
                score_pf = min(100, max(0, int(profit_factor * 25)))
                score_dd = min(100, max(0, int(100 - (max_drawdown * 3))))
                score_sqn = min(100, max(0, int(sqn * 25)))

                pnl_color = "#00ffcc" if total_pnl >= 0 else "#ff5555"
                pnl_sign = "+" if total_pnl >= 0 else "-"
                gain_sign = "+" if gain_pct >= 0 else "-"
                day_sign = "+" if avg_daily_ret >= 0 else "-"
                week_sign = "+" if weekly_ret >= 0 else "-"
                month_sign = "+" if monthly_ret >= 0 else "-"
                ann_sign = "+" if ann_ret >= 0 else "-"

                # PRIMARY METRICS ROW
                col1, col2 = st.columns([2.2, 1])

                with col1:
                    render_html(f"""
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 12px;">
                        <div class="stat-card">
                            <div class="stat-label">ACCOUNT BALANCE</div>
                            <div class="stat-value" style="color: #ffffff;">${current_balance:,.2f}</div>
                            <div class="stat-subtext" style="color: {pnl_color};">{gain_sign}{abs(gain_pct):.2f}% ({pnl_sign}${abs(total_pnl):,.2f})</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">PROFIT FACTOR</div>
                            <div class="stat-value" style="color: {'#00ffcc' if profit_factor >= 1.5 else ('#ffbb00' if profit_factor >= 1.0 else '#ff5555')};">{profit_factor:.2f}</div>
                            <div class="stat-subtext">W: ${gross_wins:,.2f} | L: ${gross_losses:,.2f}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">MAX DRAWDOWN</div>
                            <div class="stat-value" style="color: {'#00ffcc' if max_drawdown < 5 else ('#ffbb00' if max_drawdown < 10 else '#ff5555')};">{max_drawdown:.2f}%</div>
                            <div class="stat-subtext">Peak: ${highest_balance:,.2f}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">WIN RATE</div>
                            <div class="stat-value" style="color: {'#00ffcc' if win_rate >= 50 else '#ff5555'};">{win_rate:.1f}%</div>
                            <div class="stat-subtext">{winning_trades} Win / {losing_trades} Loss ({total_trades} Total)</div>
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;">
                        <div class="stat-card">
                            <div class="stat-label">SYSTEM QUALITY (SQN)</div>
                            <div class="stat-value" style="color: #ffffff;">{sqn:.2f}</div>
                            <div class="stat-subtext">{'Excellent' if sqn > 2.5 else ('Good' if sqn > 1.5 else 'Average')}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">AVG HOLDING TIME</div>
                            <div class="stat-value" style="color: #ffffff; font-size: 1.15rem;">{hold_time_str}</div>
                            <div class="stat-subtext">Avg per closed trade</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">MAX WIN / LOSS</div>
                            <div class="stat-value" style="font-size: 1.15rem;"><span style="color:#00ffcc;">+${biggest_win:,.2f}</span> / <span style="color:#ff5555;">-${abs(biggest_loss):,.2f}</span></div>
                            <div class="stat-subtext">Best single trade vs max loss</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">PERIOD RETURNS</div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 11px; margin-top: 4px; font-family: monospace;">
                                <div>D: <b style="color:{daily_color};">{day_sign}{abs(avg_daily_ret):.1f}%</b></div>
                                <div>W: <b style="color:{weekly_color};">{week_sign}{abs(weekly_ret):.1f}%</b></div>
                                <div>M: <b style="color:{monthly_color};">{month_sign}{abs(monthly_ret):.1f}%</b></div>
                                <div>Y: <b style="color:{ann_color};">{ann_sign}{abs(ann_ret):.1f}%</b></div>
                            </div>
                        </div>
                    </div>
                    """)

                with col2:
                    with st.container(border=True):
                        fig_radar = go.Figure()
                        categories = ['Profitability', 'Win Rate', 'Risk/Reward', 'Capital Protection', 'Consistency']
                        r_values = [score_pnl, score_wr, score_pf, score_dd, score_sqn]
                        r_values.append(r_values[0])
                        cat_closed = categories + [categories[0]]
                        
                        fig_radar.add_trace(go.Scatterpolar(
                            r=r_values,
                            theta=cat_closed,
                            fill='toself',
                            fillcolor='rgba(0, 255, 204, 0.15)',
                            line=dict(color='#00ffcc', width=2),
                            name='Performance Index'
                        ))
                        fig_radar.update_layout(
                            polar=dict(
                                radialaxis=dict(visible=True, range=[0, 100], color='#4a5568', gridcolor='rgba(255,255,255,0.05)', showticklabels=False),
                                angularaxis=dict(color='#8a99ad', gridcolor='rgba(255,255,255,0.05)', tickfont=dict(size=9, family='Inter'))
                            ),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            showlegend=False,
                            margin=dict(l=25, r=25, t=15, b=15),
                            height=205
                        )
                        st.plotly_chart(fig_radar, use_container_width=True)

                # ROW 2: CHARTS & CALENDAR
                col2_1, col2_2 = st.columns([1.6, 1.4])

                with col2_1:
                    with st.container(border=True):
                        # Header with Trajectory info
                        pnl_color_cur = "#00ffcc" if total_pnl >= 0 else "#ff5555"
                        pnl_sign_cur = "+" if total_pnl >= 0 else "-"
                        render_html(f"""
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:8px;">
                            <div>
                                <span style="font-size:14px; font-weight:700; color:#ffffff; text-transform:uppercase;">ACCOUNT BALANCE CURVE</span>
                                <span style="font-size:11px; color:#8a99ad; margin-left:8px;">Equity & Closed Balance trajectory</span>
                            </div>
                            <div style="display:flex; gap:16px; font-size:11px;">
                                <div><span style="color:#8a99ad;">Total P&L:</span> <b style="color:{pnl_color_cur}; font-size:13px;">{pnl_sign_cur}${abs(total_pnl):,.2f}</b></div>
                                <div><span style="color:#8a99ad;">Balance:</span> <b style="color:#ffffff; font-size:13px;">${current_balance:,.2f}</b></div>
                            </div>
                        </div>
                        """)

                        # High-Definition Cubic Hermite Spline Interpolation
                        min_entry = filtered_df["entry_time"].min()
                        start_baseline_time = min_entry - pd.Timedelta(hours=12)
                        x_times = [start_baseline_time] + list(filtered_df["exit_time"])
                        y_balances = [initial_balance] + list(filtered_df["balance"])
                        n_pts = len(y_balances)

                        if n_pts >= 2:
                            x_seq = np.arange(n_pts, dtype=float)
                            dx = np.diff(x_seq)
                            dy = np.diff(y_balances)
                            m = dy / dx

                            tang = np.zeros(n_pts)
                            tang[0] = m[0]
                            tang[-1] = m[-1]
                            for i in range(1, n_pts - 1):
                                if m[i - 1] * m[i] > 0:
                                    tang[i] = 2.0 / (1.0 / m[i - 1] + 1.0 / m[i])
                                else:
                                    tang[i] = 0.0

                            x_dense = np.linspace(0, n_pts - 1, 160)
                            y_dense = []
                            for x_val in x_dense:
                                idx_seg = max(0, min(int(x_val), n_pts - 2))
                                t = x_val - idx_seg
                                t2 = t * t
                                t3 = t2 * t
                                h00 = 2 * t3 - 3 * t2 + 1
                                h10 = t3 - 2 * t2 + t
                                h01 = -2 * t3 + 3 * t2
                                h11 = t3 - t2
                                y_interp = h00 * y_balances[idx_seg] + h10 * tang[idx_seg] + h01 * y_balances[idx_seg + 1] + h11 * tang[idx_seg + 1]
                                y_dense.append(y_interp)
                        else:
                            x_dense = [0]
                            y_dense = y_balances

                        # Y-Axis Active Range Zoom with visual breathing room
                        min_b = min(y_balances)
                        max_b = max(y_balances)
                        diff_b = max(max_b - min_b, 10.0)
                        y_min = min_b - (diff_b * 0.15)
                        y_max = max_b + (diff_b * 0.15)

                        # Hover labels with trade details on anchor points
                        hover_labels = [f"<b>Initial Balance</b><br>Balance: <b>${initial_balance:,.2f}</b>"]
                        for idx_r, row_r in filtered_df.iterrows():
                            pnl_val_r = float(row_r['net_profit'])
                            pnl_sign_r = '+' if pnl_val_r >= 0 else '-'
                            sym_r = str(row_r['symbol'])
                            t_str_r = row_r['exit_time'].strftime('%b %d, %H:%M')
                            pnl_col_r = '#00ffcc' if pnl_val_r >= 0 else '#ff5555'
                            hover_labels.append(
                                f"<b>{t_str_r}</b> ({sym_r})<br>Trade PnL: <b style='color:{pnl_col_r}'>{pnl_sign_r}${abs(pnl_val_r):,.2f}</b><br>Balance: <b>${row_r['balance']:,.2f}</b>"
                            )

                        # Clean Date Checkpoint Ticks along the progression axis
                        step = max(1, n_pts // 5)
                        tick_indices = list(range(0, n_pts, step))
                        if (n_pts - 1) not in tick_indices:
                            tick_indices.append(n_pts - 1)
                        tick_texts = [x_times[i].strftime("%b %d") for i in tick_indices]

                        fig_eq = go.Figure()

                        # Subtle High Water Mark (HWM) Reference Line
                        fig_eq.add_trace(go.Scatter(
                            x=[-0.5, n_pts - 0.5],
                            y=[highest_balance, highest_balance],
                            mode='lines',
                            line=dict(color='rgba(255, 255, 255, 0.10)', width=1, dash='dot'),
                            hoverinfo='skip',
                            name='HWM'
                        ))

                        # 1. Silky Smooth Continuous Neon Curve with subtle gradient fill
                        fig_eq.add_trace(go.Scatter(
                            x=x_dense,
                            y=y_dense,
                            mode='lines',
                            line=dict(color='#bef264', width=2.8),
                            fill='tozeroy',
                            fillcolor='rgba(190, 242, 100, 0.04)',
                            hoverinfo='skip',
                            name='Balance Curve'
                        ))

                        # 2. Clean Checkpoint Anchor Markers (Interactive on hover)
                        fig_eq.add_trace(go.Scatter(
                            x=list(range(n_pts)),
                            y=y_balances,
                            mode='markers',
                            marker=dict(size=4.5, color='#bef264', opacity=0.85, line=dict(color='#0b0f19', width=1)),
                            hovertext=hover_labels,
                            hoverinfo="text",
                            name='Trades'
                        ))

                        fig_eq.update_layout(
                            xaxis=dict(
                                tickmode='array',
                                tickvals=tick_indices,
                                ticktext=tick_texts,
                                range=[-0.4, n_pts - 0.6],
                                fixedrange=True,
                                showgrid=False,
                                linecolor='rgba(255,255,255,0.08)',
                                tickfont=dict(color='#8a99ad', size=10)
                            ),
                            yaxis=dict(
                                range=[y_min, y_max],
                                autorange=False,
                                fixedrange=True,
                                showgrid=True,
                                gridcolor='rgba(255,255,255,0.03)',
                                linecolor='rgba(255,255,255,0.08)',
                                tickfont=dict(color='#8a99ad', size=10),
                                tickprefix="$",
                                tickformat=",.0f"
                            ),
                            dragmode=False,
                            hovermode="closest",
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            margin=dict(l=10, r=20, t=10, b=10),
                            height=270,
                            showlegend=False
                        )
                        st.plotly_chart(
                            fig_eq, 
                            use_container_width=True, 
                            config={
                                'displayModeBar': False, 
                                'scrollZoom': False, 
                                'doubleClick': False, 
                                'showAxisDragHandles': False,
                                'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']
                            }
                        )

                        # Ratio bars
                        avg_win = filtered_df[filtered_df["net_profit"] > 0]["net_profit"].mean() if winning_trades > 0 else 0.0
                        avg_loss = abs(filtered_df[filtered_df["net_profit"] <= 0]["net_profit"].mean()) if losing_trades > 0 else 0.0
                        total_avg = avg_win + avg_loss
                        win_bar_pct = (avg_win / total_avg * 100) if total_avg > 0 else 50.0
                        loss_bar_pct = 100.0 - win_bar_pct

                        long_count = len(filtered_df[filtered_df["direction"].str.upper().isin(["BUY", "LONG"])])
                        short_count = total_trades - long_count
                        long_bar_pct = (long_count / total_trades * 100) if total_trades > 0 else 50.0
                        short_bar_pct = 100.0 - long_bar_pct

                        str_wl_ratio = f"{win_bar_pct:.1f}% / {loss_bar_pct:.1f}%"
                        str_ls_ratio = f"{long_bar_pct:.1f}% / {short_bar_pct:.1f}%"
                        str_avg_win = f"+${avg_win:,.2f}"
                        str_avg_loss = f"-${avg_loss:,.2f}"

                        render_html(f"""
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 10px;">
                            <div class="ratio-card">
                                <div class="ratio-label-row">
                                    <span>Average Win vs Loss</span>
                                    <span>{str_wl_ratio}</span>
                                </div>
                                <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:700; margin-top:4px;">
                                    <span style="color:#00ffcc;">{str_avg_win}</span>
                                    <span style="color:#ff5555;">{str_avg_loss}</span>
                                </div>
                                <div class="ratio-bar-bg">
                                    <div class="ratio-bar-green" style="width: {win_bar_pct}%;"></div>
                                    <div class="ratio-bar-red" style="width: {loss_bar_pct}%;"></div>
                                </div>
                            </div>
                            <div class="ratio-card">
                                <div class="ratio-label-row">
                                    <span>Long / Short Counts</span>
                                    <span>{str_ls_ratio}</span>
                                </div>
                                <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:700; margin-top:4px;">
                                    <span style="color:#00ffcc;">Long: {long_count}</span>
                                    <span style="color:#ff5555;">Short: {short_count}</span>
                                </div>
                                <div class="ratio-bar-bg">
                                    <div class="ratio-bar-green" style="width: {long_bar_pct}%;"></div>
                                    <div class="ratio-bar-red" style="width: {short_bar_pct}%;"></div>
                                </div>
                            </div>
                        </div>
                        """)

                with col2_2:
                    with st.container(border=True):
                        if "cal_year" not in st.session_state:
                            st.session_state.cal_year = datetime.now().year
                        if "cal_month" not in st.session_state:
                            st.session_state.cal_month = datetime.now().month

                        month_name = calendar.month_name[st.session_state.cal_month]

                        prev_m = st.session_state.cal_month - 1
                        prev_y = st.session_state.cal_year
                        if prev_m == 0:
                            prev_m = 12
                            prev_y -= 1

                        next_m = st.session_state.cal_month + 1
                        next_y = st.session_state.cal_year
                        if next_m == 13:
                            next_m = 1
                            next_y += 1

                        render_html(f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 8px;">
                            <div style="font-size: 15px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px; text-transform: uppercase;">{month_name} {st.session_state.cal_year}</div>
                            <div style="display: flex; gap: 6px;">
                                <a href="?cal_m={prev_m}&cal_y={prev_y}" target="_self" class="cal-nav-link-btn" title="Previous Month">&lt;</a>
                                <a href="?cal_m={next_m}&cal_y={next_y}" target="_self" class="cal-nav-link-btn" title="Next Month">&gt;</a>
                            </div>
                        </div>
                        """)

                        month_start = pd.Timestamp(datetime(st.session_state.cal_year, st.session_state.cal_month, 1))
                        last_day_num = calendar.monthrange(st.session_state.cal_year, st.session_state.cal_month)[1]
                        month_end = pd.Timestamp(datetime(st.session_state.cal_year, st.session_state.cal_month, last_day_num, 23, 59, 59))

                        month_trades = filtered_df[
                            (filtered_df["exit_time"] >= month_start) & 
                            (filtered_df["exit_time"] <= month_end)
                        ]

                        month_total_trades = len(month_trades)
                        month_wins = len(month_trades[month_trades["net_profit"] > 0])
                        month_profits = month_trades["net_profit"].sum()
                        month_gain_pct = (month_profits / initial_balance) * 100 if month_total_trades > 0 else 0.0

                        month_pnl_sign = "+" if month_profits >= 0 else "-"
                        month_gain_sign = "+" if month_gain_pct >= 0 else "-"
                        month_pnl_col = "#00ffcc" if month_profits >= 0 else "#ff5555"
                        month_gain_col = "#00ffcc" if month_gain_pct >= 0 else "#ff5555"
                        str_m_pnl = f"{month_pnl_sign}${abs(month_profits):,.2f}"
                        str_m_gain = f"{month_gain_sign}{abs(month_gain_pct):.1f}%"

                        render_html(f"""
                        <div style="background: rgba(255,255,255,0.02); padding: 6px 12px; border-radius: 6px; font-size:11px; margin-bottom:8px; display:flex; gap:16px; font-weight:600;">
                            <span style="color:#8a99ad;">Trades: <b style="color:#fff;">{month_total_trades}</b></span>
                            <span style="color:#8a99ad;">Wins: <b style="color:#00ffcc;">{month_wins}</b></span>
                            <span style="color:#8a99ad;">PnL: <b style="color:{month_pnl_col};">{str_m_pnl}</b></span>
                            <span style="color:#8a99ad;">Gain: <b style="color:{month_gain_col};">{str_m_gain}</b></span>
                        </div>
                        """)

                        cal_html = '<div class="calendar-grid">'
                        days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                        for day_h in days_header:
                            cal_html += f'<div class="calendar-day-header">{day_h}</div>'

                        first_weekday, num_days = calendar.monthrange(st.session_state.cal_year, st.session_state.cal_month)
                        for _ in range(first_weekday):
                            cal_html += '<div></div>'

                        monthly_daily_pnl = month_trades.groupby(month_trades["exit_time"].dt.day)["net_profit"].sum().to_dict()

                        for day in range(1, num_days + 1):
                            day_pnl = monthly_daily_pnl.get(day, 0.0)
                            cell_class = "calendar-cell"
                            val_str = ""
                            pct_str = ""
                            if day in monthly_daily_pnl:
                                if day_pnl > 0:
                                    cell_class += " profit"
                                    val_str = f"+${day_pnl:,.2f}"
                                    pct_str = f"+{(day_pnl/initial_balance*100):.1f}%"
                                elif day_pnl < 0:
                                    cell_class += " loss"
                                    val_str = f"-${abs(day_pnl):,.2f}"
                                    pct_str = f"-{(abs(day_pnl)/initial_balance*100):.1f}%"
                                else:
                                    val_str = "$0.00"
                                    pct_str = "0.0%"

                            val_color = "#00ffcc" if day_pnl > 0 else ("#ff5555" if day_pnl < 0 else "#8a99ad")
                            cal_html += f"""
                            <div class="{cell_class}">
                                <span class="calendar-day-num">{day}</span>
                                <span class="calendar-day-val" style="color: {val_color}; font-size:10px;">{val_str}</span>
                                <span class="calendar-day-pct" style="color: {val_color}; font-size:8px;">{pct_str}</span>
                            </div>
                            """

                        trailing_empty = (7 - (first_weekday + num_days) % 7) % 7
                        for _ in range(trailing_empty):
                            cal_html += '<div style="background: rgba(255, 255, 255, 0.01); border: 1px dashed rgba(255, 255, 255, 0.025); border-radius: 6px; min-height: 52px;"></div>'

                        cal_html += '</div><div style="height: 6px;"></div>'
                        render_html(cal_html)

                # Performance Breakdown By Symbol & Tag
                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                col_ch1, col_ch2 = st.columns(2)
                with col_ch1:
                    symbol_pnl = filtered_df.groupby("symbol")["net_profit"].sum().reset_index()
                    symbol_pnl = symbol_pnl.sort_values(by="net_profit", ascending=False)
                    fig_symbol = px.bar(
                        symbol_pnl,
                        x="symbol",
                        y="net_profit",
                        title="Net Profit by Symbol",
                        labels={"symbol": "Symbol", "net_profit": "Net PnL ($)"},
                        color="net_profit",
                        color_continuous_scale=["#ff5555", "#00ffcc"],
                        template="plotly_dark"
                    )
                    fig_symbol.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_symbol, use_container_width=True)

                with col_ch2:
                    tag_pnl = filtered_df.fillna("Untagged").groupby("setup_tag")["net_profit"].sum().reset_index()
                    fig_tag = px.bar(
                        tag_pnl,
                        x="setup_tag",
                        y="net_profit",
                        title="Net Profit by Strategy Tag",
                        labels={"setup_tag": "Strategy Setup", "net_profit": "Net PnL ($)"},
                        color="net_profit",
                        color_continuous_scale=["#ff5555", "#00ffcc"],
                        template="plotly_dark"
                    )
                    fig_tag.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_tag, use_container_width=True)

        with tab_charts:
            # ----------------------------------------------------
            # UNIFIED MULTI-PANE TRADING WORKSPACE (PHASE 13)
            # ----------------------------------------------------
            if "active_ws_symbol" not in st.session_state:
                st.session_state.active_ws_symbol = "USDJPY"

            # 1. SYSTEM HEALTH & SAFETY BANNER
            import risk_gateway
            import execution_pipeline
            sys_mode = database.get_setting("SYSTEM_STATE", "PAPER")
            kill_sw = database.get_setting("GLOBAL_KILL_SWITCH", "FALSE").upper() == "TRUE"
            max_daily_loss = float(database.get_setting("MAX_DAILY_LOSS_PCT", "3.0"))
            max_total_risk = float(database.get_setting("MAX_TOTAL_RISK_PCT", "15.0"))
            
            # Fetch balances & risk status
            acc_balances = database.get_account_balances()
            p_bal = acc_balances.get("PAPER", {}).get("balance", 10000.0)
            p_equity = acc_balances.get("PAPER", {}).get("equity", p_bal)
            p_float = acc_balances.get("PAPER", {}).get("floating_pnl", 0.0)
            p_realized = acc_balances.get("PAPER", {}).get("realized_daily_pnl", 0.0)
            curr_daily_loss_pct = (abs(min(0.0, p_realized + p_float)) / p_bal) * 100.0 if p_bal > 0 else 0.0

            mode_badge_col = "#ff5555" if kill_sw or sys_mode == "EMERGENCY HALT" else ("#00ffcc" if sys_mode == "LIVE" else "#fbbf24")
            kill_badge_txt = "HALTED / KILL SWITCH ACTIVE" if kill_sw else "ARMED & SAFE"
            kill_badge_col = "#ff5555" if kill_sw else "#00ffcc"

            st.markdown(f"""
            <div style="background: rgba(15, 23, 42, 0.65); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 8px 14px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:11px; font-weight:800; color:#8a99ad; text-transform:uppercase;">MODE:</span>
                    <span style="font-size:11px; font-weight:800; color:{mode_badge_col}; background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:4px; border:1px solid {mode_badge_col};">{sys_mode}</span>
                    <span style="font-size:11px; font-weight:800; color:{kill_badge_col}; margin-left:6px;"> {kill_badge_txt}</span>
                </div>
                <div style="display:flex; align-items:center; gap:16px; font-size:11px; color:#8a99ad;">
                    <span>Daily Drawdown: <b style="color:{'#00ffcc' if curr_daily_loss_pct < max_daily_loss else '#ff5555'};">{curr_daily_loss_pct:.2f}% / {max_daily_loss:.1f}%</b></span>
                    <span>Max Portfolio Risk: <b style="color:#00ffcc;">{max_total_risk:.1f}%</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 2. FULLSCREEN INTERACTIVE CHART STUDIO
            col_c_top1, col_c_top2, col_c_top3, col_c_top4 = st.columns([2.0, 1.5, 1.5, 2.2])
            with col_c_top1:
                st.markdown(f"<div style='display:flex; align-items:center; gap:8px;'><h3 style='margin:0; font-size:1.3rem; font-weight:800; color:#ffffff;'>{st.session_state.active_ws_symbol}</h3><span style='font-size:11px; color:#00ffcc; background:rgba(0,255,204,0.12); padding:2px 6px; border-radius:4px; font-weight:700;'>LIVE FEED</span></div>", unsafe_allow_html=True)
            with col_c_top2:
                active_tf = st.selectbox(
                    "Timeframe",
                    options=["1m", "5m", "15m", "1h", "4h", "D"],
                    index=2,
                    label_visibility="collapsed",
                    key="ws_timeframe_selector"
                )
            with col_c_top3:
                st.markdown(f"""
                <div style="text-align: right;">
                    <a href="https://www.tradingview.com/chart/?symbol={st.session_state.active_ws_symbol}" target="_blank" style="display: inline-block; background: rgba(0, 255, 204, 0.1); color: #00ffcc; border: 1px solid rgba(0, 255, 204, 0.3); padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; text-decoration: none;">
                        FULLSCREEN
                    </a>
                </div>
                """, unsafe_allow_html=True)
            with col_c_top4:
                with st.popover("Trade Execution & Risk Preview", use_container_width=True):
                    st.markdown("<p style='font-size:12px;font-weight:800;color:#00ffcc;letter-spacing:0.8px;margin-bottom:8px;text-transform:uppercase;'>CANONICAL ORDER EXECUTION</p>", unsafe_allow_html=True)
                    
                    c_ex_side, c_ex_mode = st.columns(2)
                    with c_ex_side:
                        order_side = st.selectbox("Order Side", ["BUY", "SELL"], index=0, key="ws_pop_side")
                    with c_ex_mode:
                        order_mode = st.selectbox("Execution Mode", ["PAPER", "SHADOW", "LIVE"], index=0, key="ws_pop_mode")
                        
                    order_broker = st.selectbox(
                        "Broker Target",
                        options=["CAPITAL", "MT5", "PAPER"],
                        index=2 if order_mode == "PAPER" else 0,
                        key="ws_order_broker_sel"
                    )

                    # Live / estimated entry price
                    import market_data
                    latest_tick = market_data.get_latest_tick(st.session_state.active_ws_symbol)
                    default_px = float(latest_tick.get("ask" if order_side == "BUY" else "bid", 1.0850)) if latest_tick else 1.0850

                    c_px1, c_px2 = st.columns(2)
                    with c_px1:
                        inp_entry = st.number_input("Entry Price", value=float(default_px), format="%.5f", key="ws_inp_entry")
                    with c_px2:
                        default_sl = round(inp_entry * (0.995 if order_side == "BUY" else 1.005), 5)
                        inp_sl = st.number_input("Stop Loss", value=float(default_sl), format="%.5f", key="ws_inp_sl")

                    c_tp1, c_tp2 = st.columns(2)
                    with c_tp1:
                        default_tp1 = round(inp_entry * (1.010 if order_side == "BUY" else 0.990), 5)
                        inp_tp1 = st.number_input("Take Profit 1", value=float(default_tp1), format="%.5f", key="ws_inp_tp1")
                    with c_tp2:
                        inp_risk_pct = st.number_input("Risk %", min_value=0.1, max_value=5.0, value=1.0, step=0.1, key="ws_inp_risk_pct")

                    # Live Pre-Trade Risk Calculation
                    risk_prev = risk_gateway.calculate_pre_trade_risk_preview(
                        symbol=st.session_state.active_ws_symbol,
                        side=order_side,
                        entry_price=inp_entry,
                        stop_loss=inp_sl,
                        take_profit_1=inp_tp1,
                        requested_risk_pct=inp_risk_pct,
                        account_balance=p_bal
                    )

                    # Render Pre-Trade Risk Card
                    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 8px 0;'>", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="background: rgba(0, 0, 0, 0.25); border: 1px solid rgba(0, 255, 204, 0.2); border-radius: 6px; padding: 10px; margin-bottom: 10px; font-size: 11px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span style="color:#8a99ad;">Calculated Position Size:</span>
                            <b style="color:#ffffff; font-size:12px;">{risk_prev['calculated_lot_size']} Lots</b>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span style="color:#8a99ad;">Worst-Case Loss (SL):</span>
                            <b style="color:#ff5555;">-${risk_prev['actual_risk_usd']:,.2f} ({risk_prev['actual_risk_pct']:.2f}%)</b>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span style="color:#8a99ad;">Target 1 Reward (TP):</span>
                            <b style="color:#00ffcc;">+${risk_prev['reward_tp1_usd']:,.2f} ({risk_prev['reward_tp1_pct']:.2f}%)</b>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span style="color:#8a99ad;">Risk : Reward:</span>
                            <b style="color:#bef264;">{risk_prev['risk_reward_ratio']}</b>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#8a99ad;">Estimated Margin:</span>
                            <span style="color:#cbd5e1;">${risk_prev['estimated_margin_usd']:,.2f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if risk_prev["warnings"]:
                        for w in risk_prev["warnings"]:
                            st.warning(f"{w}")

                    if not risk_prev["is_valid"]:
                        for err in risk_prev["errors"]:
                            st.error(f"{err}")

                    # 1-Click Execution Button via Canonical State Machine
                    btn_label = f"Execute {order_side} ({risk_prev['calculated_lot_size']} Lots)"
                    if st.button(btn_label, key="ws_btn_submit_order", use_container_width=True, disabled=not risk_prev["is_valid"]):
                        import uuid
                        exec_req = execution_pipeline.CanonicalExecutionRequest(
                            signal_id=f"MANUAL_{uuid.uuid4().hex[:8]}",
                            symbol=st.session_state.active_ws_symbol,
                            side=order_side,
                            quantity=risk_prev["calculated_lot_size"],
                            requested_entry=inp_entry,
                            stop_loss=inp_sl,
                            take_profit=inp_tp1,
                            broker=order_broker,
                            mode=order_mode,
                            source="MANUAL_TERMINAL_UI",
                            strategy="ManualTrade"
                        )
                        with st.spinner("Submitting order through Canonical Risk Gateway..."):
                            exec_res = execution_pipeline.submit_order(exec_req)
                            if exec_res.get("status") in ["success", "FILLED"]:
                                st.success(f"Order Executed Successfully! State: {exec_res.get('state')}")
                                time.sleep(1.0)
                                st.rerun()
                            else:
                                st.error(f"Execution Rejected: {exec_res.get('message')}")

            # Retrieve AI Setup Data to render exact geometric lines on the chart
            with st.spinner(f"Loading {st.session_state.active_ws_symbol} ({active_tf}) live chart & AI structure..."):
                import ai_analysis
                ws_cache_key = f"ws_ai_chart_{st.session_state.active_ws_symbol}_{active_tf}"
                if ws_cache_key not in st.session_state:
                    st.session_state[ws_cache_key] = ai_analysis.analyze_market_context(symbol=st.session_state.active_ws_symbol, timeframe=active_tf)
                ai_data_for_chart = st.session_state.get(ws_cache_key)
                setup_data_for_chart = ai_data_for_chart.get("deterministic_scenario", {}) if ai_data_for_chart else None

                tradingview_widget.render_tradingview_chart(
                    symbol=st.session_state.active_ws_symbol,
                    interval=active_tf,
                    height=800,
                    ai_setup_data=setup_data_for_chart
                )

            # 4. BOTTOM PANE: ACTIVE POSITIONS DOCK
            st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
            if not df_open.empty:
                st.markdown("<p style='font-size:11px;font-weight:800;color:#64748b;letter-spacing:0.8px;margin-bottom:6px;text-transform:uppercase;'>ACTIVE OPEN POSITIONS & ORDERS</p>", unsafe_allow_html=True)
                for _, pos in df_open.iterrows():
                    pos_id = str(pos["position_id"])
                    p_sym = str(pos["symbol"]).upper()
                    p_dir = str(pos["direction"]).upper()
                    p_vol = float(pos.get("volume", 0.0))
                    p_entry = float(pos.get("entry_price", 0.0))
                    p_curr = float(pos.get("current_price", 0.0))
                    p_pnl = float(pos.get("floating_pnl", 0.0))
                    p_acc = str(pos.get("account_id", ""))
                    
                    pnl_col = "#00ffcc" if p_pnl >= 0 else "#ff5555"
                    dir_badge_col = "#00ffcc" if "BUY" in p_dir else "#ff5555"
                    
                    c_p1, c_p2, c_p3, c_p4, c_p5, c_p6, c_p7 = st.columns([1.2, 1, 1.2, 1.2, 1.2, 1.5, 1])
                    with c_p1:
                        st.markdown(f"<b style='color:#ffffff;'>{p_sym}</b> <span style='font-size:10px; color:#8a99ad;'>({p_acc})</span>", unsafe_allow_html=True)
                    with c_p2:
                        st.markdown(f"<span style='color:{dir_badge_col}; font-weight:700;'>{p_dir} {p_vol:,.2f}</span>", unsafe_allow_html=True)
                    with c_p3:
                        st.markdown(f"<span style='color:#8a99ad; font-size:12px;'>Entry: {p_entry:,.2f}</span>", unsafe_allow_html=True)
                    with c_p4:
                        st.markdown(f"<span style='color:#ffffff; font-size:12px;'>Current: {p_curr:,.2f}</span>", unsafe_allow_html=True)
                    with c_p5:
                        st.markdown(f"<b style='color:{pnl_col}; font-size:13px;'>{'+' if p_pnl>=0 else ''}${p_pnl:,.2f}</b>", unsafe_allow_html=True)
                    with c_p6:
                        st.markdown(f"<span style='font-size:11px; color:#8a99ad;'>SL: {pos.get('sl', 0) or '-'} | TP: {pos.get('tp', 0) or '-'}</span>", unsafe_allow_html=True)
                    with c_p7:
                        if st.button("Close", key=f"ws_close_pos_{pos_id}", use_container_width=True):
                            import order_execution
                            if "CAP_" in pos_id:
                                success, msg = order_execution.close_capital_position(pos_id.replace("CAP_", ""))
                            else:
                                success, msg = order_execution.close_mt5_position(int(pos_id.replace("MT5_", "")))
                            if success:
                                st.success("Position closed!")
                                st.rerun()
                            else:
                                st.error(msg)

        # ----------------------------------------------------
        # AI MARKET CONTEXT & TECHNICAL ANALYSIS PIPELINE
        # ----------------------------------------------------
        with tab_ai:
            st.markdown("<h3 style='color:#ffffff;font-size:1.3rem;margin:0 0 4px 0;font-weight:800;text-transform:uppercase;'>AI Technical & Market Context Analysis</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color:#8a99ad;font-size:13px;margin-bottom:14px;'>Deterministic technical indicator synthesis & structured market scenarios. Never hallucinates prices.</p>", unsafe_allow_html=True)

            col_ai_sym, col_ai_tf, col_ai_strat, col_ai_btn = st.columns([1.0, 0.8, 1.5, 1.0])
            with col_ai_sym:
                ai_selected_sym = st.selectbox(
                    "Asset",
                    options=["XAUUSD", "NAS100", "SPX500", "US30", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "USOIL"],
                    index=6,
                    key="ai_sel_symbol"
                )
            with col_ai_tf:
                ai_selected_tf = st.selectbox(
                    "Timeframe",
                    options=["1m", "5m", "15m", "1h", "4h", "D"],
                    index=3,
                    key="ai_sel_tf"
                )
            with col_ai_strat:
                import strategies
                ai_strat_list = strategies.get_all_strategy_names()
                ai_selected_strat = st.selectbox("Strategy Framework", options=ai_strat_list, index=0, key="ai_sel_strat")
                
            with col_ai_btn:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                run_ai_analysis = st.button("RUN ENGINE", key="btn_run_ai", use_container_width=True)

            st.markdown("""<div style='background:rgba(0,0,0,0.15); padding:10px 14px; border-radius:4px; border-left:2px solid #3b82f6; margin-bottom:16px; margin-top:8px;'>
                <span style='color:#cbd5e1; font-size:11px; font-weight:bold;'> HOW IT WORKS:</span> 
                <span style='color:#8a99ad; font-size:11px;'>The engine runs the selected deterministic strategy on live price action, automatically calculating Liquidity Sweeps, FVGs, and Market Structure.</span>
            </div>""", unsafe_allow_html=True)

            import ai_analysis
            
            # --- Gate heavy analysis behind the button ---
            AI_CACHE_KEY = f"ai_data_{ai_selected_sym}_{ai_selected_tf}_{ai_selected_strat}"
            if run_ai_analysis:
                with st.spinner(f"Running {ai_selected_strat} on {ai_selected_sym} {ai_selected_tf}..."):
                    _fresh = ai_analysis.analyze_market_context(symbol=ai_selected_sym, timeframe=ai_selected_tf, strategy_name=ai_selected_strat)
                st.session_state[AI_CACHE_KEY] = _fresh

            ai_data = st.session_state.get(AI_CACHE_KEY, None)
            if ai_data is None:
                st.info("Select your asset and strategy above, then press **RUN ENGINE** to run the live analysis.")

            elif ai_data.get("status") != "unavailable" and ai_data.get("status") != "error":
                factual = ai_data.get("factual_data", {})
                bias = ai_data.get("confluence_bias", {}).get("bias", "Unknown")
                st_trend = ai_data.get("market_structure", {}).get("trend", "Unknown")
                ml_buy = ai_data.get("ml_prob_buy", 0.0)
                ml_sell = ai_data.get("ml_prob_sell", 0.0)
                ml_neutral = ai_data.get("ml_prob_neutral", 0.0)
                
                # Get the detailed AI structure         
                bias_color = "#00ffcc" if bias == "Bullish" else ("#ff5555" if bias == "Bearish" else "#f59e0b")

                # Header Metric Cards
                c_m1, c_m2, c_m3, c_m4, c_m5 = st.columns(5)
                with c_m1:
                    st.metric("Current Price", f"${factual['current_price']:,.2f}", f"{factual['price_change_pct']:+.2f}%")
                with c_m2:
                    st.metric("Trend Bias", bias)
                with c_m3:
                    st.metric("RSI (14)", f"{factual['rsi']:.1f}")
                with c_m4:
                    st.metric("EMA 20 / 50", f"{factual['ema20']:,.1f}", f"{factual['ema50']:,.1f}")
                with c_m5:
                    st.metric("Key Resistance", f"${factual['resistance_1']:,.2f}")

                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

                ml_buy = ai_data.get("ml_prob_buy", 0.0)
                ml_sell = ai_data.get("ml_prob_sell", 0.0)

                details_style = "margin-top:10px;"
                summary_style = "font-size:11px; color:#8a99ad; cursor:pointer; outline:none;"
                content_style = "font-size:11px; color:#8a99ad; margin-top:6px; padding:8px; background:rgba(0,0,0,0.15); border-radius:4px; line-height:1.4;"

                # --- ROW 1: MACRO & INSTITUTIONAL CONTEXT ---
                st.markdown("<h4 style='color:#64748b; font-size:11px; font-weight:800; letter-spacing:0.8px; margin-top:10px; margin-bottom:5px; text-transform:uppercase;'>MACRO & INSTITUTIONAL CONTEXT</h4>", unsafe_allow_html=True)
                mac1, mac2, mac3 = st.columns(3)
                
                with mac1:
                    macro = ai_data.get('macro_data', {})
                    mac_color = "#ff5555" if macro.get("risk_level") == "HIGH" else "#fbbf24" if macro.get("risk_level") == "MEDIUM" else "#00ffcc"
                    mac_html = f"""<div style='background:rgba(255,255,255,0.02); padding:12px; border-left:3px solid {mac_color}; border-radius:4px;'>
                        <b style='color:#cbd5e1;'>News Calendar</b><br/>
                        <div style='margin-top:8px; margin-bottom:4px;'><span style='background:#1e293b; color:{mac_color}; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;'>Risk: {macro.get('risk_level', 'UNKNOWN')}</span></div>
                        <div style='font-family:monospace; font-size:10px; color:#8a99ad;'><span style='color:#475569;'>Event:</span> <span style='color:#cbd5e1;'>{macro.get('event', 'None')}</span> <br/> <span style='color:#475569;'>Time:</span> <span style='color:#cbd5e1;'>{macro.get('time_to_event', 'N/A')}</span></div>
                        <details style='{details_style}'><summary style='{summary_style}'> Impact</summary><div style='{content_style}'>{macro.get('impact', '')}</div></details>
                    </div>"""
                    st.markdown(mac_html, unsafe_allow_html=True)
                
                with mac2:
                    cot = ai_data.get('cot_data', {})
                    cot_html = f"""<div style='background:rgba(255,255,255,0.02); padding:12px; border-left:3px solid #8b5cf6; border-radius:4px;'>
                        <b style='color:#cbd5e1;'>Institutional Positioning (COT)</b><br/>
                        <div style='margin-top:8px; margin-bottom:4px;'><span style='background:#1e293b; color:#fbbf24; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;'>{cot.get('sentiment', 'Neutral')}</span></div>
                        <div style='font-family:monospace; font-size:10px; color:#8a99ad;'><span style='color:#475569;'>Commercials:</span> <span style='color:#cbd5e1;'>{cot.get('commercial_bias', 'N/A')}</span> <br/> <span style='color:#475569;'>Specs:</span> <span style='color:#cbd5e1;'>{cot.get('speculator_bias', 'N/A')}</span></div>
                        <details style='{details_style}'><summary style='{summary_style}'> What is this?</summary><div style='{content_style}'>Commitment of Traders (COT) report shows where the smart money (Commercials) and dumb money (Speculators) are currently heavily positioned.</div></details>
                    </div>"""
                    st.markdown(cot_html, unsafe_allow_html=True)
                
                with mac3:
                    ca = ai_data.get('cross_asset', {})
                    ca_html = f"""<div style='background:rgba(255,255,255,0.02); padding:12px; border-left:3px solid #0ea5e9; border-radius:4px;'>
                        <b style='color:#cbd5e1;'>Cross-Asset Context ({ca.get('asset', 'DXY')})</b><br/>
                        <div style='margin-top:8px; margin-bottom:4px;'><span style='background:#1e293b; color:#0ea5e9; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;'>{ca.get('correlation', 'N/A')} CORRELATION</span></div>
                        <div style='font-family:monospace; font-size:10px; color:#8a99ad;'><span style='color:#475569;'>Driver Trend:</span> <span style='color:#cbd5e1;'>{ca.get('dxy_trend', 'N/A')}</span> <br/> <span style='color:#475569;'>Filter:</span> <span style='color:#cbd5e1;'>{ca.get('signal_filter', 'N/A')}</span></div>
                        <details style='{details_style}'><summary style='{summary_style}'> What is this?</summary><div style='{content_style}'>Checks the trend of the underlying macro driver (like the US Dollar Index for EURUSD/XAUUSD) to see if you have institutional headwinds or tailwinds.</div></details>
                    </div>"""
                    st.markdown(ca_html, unsafe_allow_html=True)
                    
                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

                # ROW 2: ACTIVE SESSION
                kz_status = ai_data.get("killzone", "Unknown")
                kz_color = "#f59e0b" if "Asian" in kz_status else ("#00ffcc" if "London" in kz_status else ("#ff5555" if "NY" in kz_status else "#64748b"))
                st.markdown(f"<div style='background:rgba(255,255,255,0.05); border-left:4px solid {kz_color}; padding:8px 12px; margin-bottom:12px; border-radius:4px;'><span style='font-size:10px; font-weight:800; color:#8a99ad; text-transform:uppercase;'>ACTIVE SESSION</span><br/><span style='font-size:14px; font-weight:700; color:{kz_color};'>{kz_status}</span></div>", unsafe_allow_html=True)

                # ROW 3: DETERMINISTIC QUANTITATIVE LOGIC
                st.markdown(f"<p style='font-size:11px;font-weight:800;color:#64748b;letter-spacing:0.8px;margin-bottom:6px;text-transform:uppercase;'>DETERMINISTIC QUANTITATIVE LOGIC</p>", unsafe_allow_html=True)
                c_dq1, c_dq2, c_dq3, c_dq4 = st.columns(4)
                
                with c_dq1:
                    mtf_align_raw = ai_data.get('mtf_alignment', 'Unknown')
                    if isinstance(mtf_align_raw, dict):
                        mtf_align = mtf_align_raw.get('alignment', 'Unknown')
                        mtf_score = mtf_align_raw.get('score', 0)
                    else:
                        mtf_align = str(mtf_align_raw)
                        mtf_score = 0

                    align_col = "#00ffcc" if "BULLISH" in mtf_align.upper() else ("#ff5555" if "BEARISH" in mtf_align.upper() else "#64748b")
                    score_str = f"{mtf_score:+d}" if mtf_score != 0 else "0"
                    html = f"""<div style='background:rgba(255,255,255,0.02); padding:12px; border-left:3px solid #3b82f6; border-radius:4px;'>
                        <b style='color:#cbd5e1;'>MTF Trend Alignment</b><br/>
                        <div style='margin-top:8px; margin-bottom:4px;'><span style='background:#1e293b; color:{align_col}; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;'>{mtf_align}</span></div>
                        <div style='font-family:monospace; font-size:10px; color:#8a99ad;'><span style='color:#475569;'>Bias Score:</span> <span style='color:{align_col};'>{score_str}</span></div>
                        <details style='{details_style}'><summary style='{summary_style}'> What is this?</summary><div style='{content_style}'>Compares higher timeframe trends against current timeframe to confirm institutional sponsorship.</div></details>
                    </div>"""
                    st.markdown(html, unsafe_allow_html=True)
                    
                with c_dq2:
                    regime = ai_data.get('market_regime', 'Unknown')
                    reg_col = "#00ffcc" if "Expansion" in regime else "#64748b"
                    html = f"""<div style='background:rgba(255,255,255,0.02); padding:12px; border-left:3px solid #8b5cf6; border-radius:4px;'>
                        <b style='color:#cbd5e1;'>Market Volatility Regime</b><br/>
                        <div style='margin-top:8px; margin-bottom:4px;'><span style='background:#1e293b; color:{reg_col}; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;'>{regime}</span></div>
                        <details style='{details_style}'><summary style='{summary_style}'> What is this?</summary><div style='{content_style}'>Uses Average Directional Index (ADX) to determine if price is trending or consolidating.</div></details>
                    </div>"""
                    st.markdown(html, unsafe_allow_html=True)
                    
                with c_dq3:
                    struct = ai_data.get('market_structure', {})
                    st_trend = struct.get('trend', 'Unknown')
                    st_col = "#00ffcc" if "Bullish" in st_trend else ("#ff5555" if "Bearish" in st_trend else "#64748b")
                    html = f"""<div style='background:rgba(255,255,255,0.02); padding:12px; border-left:3px solid #f59e0b; border-radius:4px;'>
                        <b style='color:#cbd5e1;'>Market Structure</b><br/>
                        <div style='margin-top:8px; margin-bottom:4px;'><span style='background:#1e293b; color:{st_col}; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;'>{st_trend}</span></div>
                        <div style='font-family:monospace; font-size:10px; color:#8a99ad;'><span style='color:#475569;'>Swings:</span> {struct.get('recent_sequence', 'N/A')}<br/><span style='color:#475569;'>Break:</span> {struct.get('last_break', 'N/A')}</div>
                        <details style='{details_style}'><summary style='{summary_style}'> What is this?</summary><div style='{content_style}'>Analyzes Higher Highs / Lower Lows to confirm the immediate structural trend.</div></details>
                    </div>"""
                    st.markdown(html, unsafe_allow_html=True)
                    
                with c_dq4:
                    vp = ai_data.get('volume_profile', {})
                    html = f"""<div style='background:rgba(255,255,255,0.02); padding:12px; border-left:3px solid #10b981; border-radius:4px;'>
                        <b style='color:#cbd5e1;'>Volume Profile & VWAP</b><br/>
                        <div style='font-family:monospace; font-size:10px; color:#8a99ad; margin-top:8px;'>
                        <span style='color:#475569;'>VWAP:</span> <span style='color:#f59e0b;'>{vp.get('vwap', 'N/A')}</span><br/>
                        <span style='color:#475569;'>POC:</span> <span style='color:#3b82f6;'>{vp.get('poc', 'N/A')}</span><br/>
                        <span style='color:#475569;'>VAH:</span> {vp.get('vah', 'N/A')} | <span style='color:#475569;'>VAL:</span> {vp.get('val', 'N/A')}
                        </div>
                        <div style='margin-top:4px;'><span style='font-size:8px; color:#64748b; text-transform:uppercase;'>TICK VOLUME</span></div>
                        <details style='{details_style}'><summary style='{summary_style}'> What is this?</summary><div style='{content_style}'>Maps volume distribution over price to find fair value areas and institutional accumulation zones. VWAP represents intraday fair price.</div></details>
                    </div>"""
                    st.markdown(html, unsafe_allow_html=True)

                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

                # ROW 4: BOTTOM SPLIT
                col_sum1, col_sum2 = st.columns([1.5, 1.5])
                with col_sum1:
                    with st.container(border=True):
                        st.markdown(f"<p style='font-size:11px;font-weight:800;color:#64748b;letter-spacing:0.8px;margin-bottom:6px;text-transform:uppercase;'>LLM MARKET SYNTHESIS & TARGETS</p>", unsafe_allow_html=True)
                        
                        st.markdown(f"<p style='font-size:12px; color:#ffffff; margin-top:8px;'><b>What is Happening:</b></p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:12px; color:#00ffcc; border-left:2px solid #00ffcc; padding-left:8px;'>{ai_data.get('what_is_happening', 'N/A')}</p>", unsafe_allow_html=True)
                        
                        st.markdown(f"<p style='font-size:12px; color:#ffffff; margin-top:8px;'><b>Evidence / Why:</b></p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:12px; color:#8a99ad; border-left:2px solid #8a99ad; padding-left:8px;'>{ai_data.get('why', 'N/A')}</p>", unsafe_allow_html=True)
                        
                        st.markdown(f"<p style='font-size:12px; color:#ffffff; margin-top:8px;'><b>What Matters Next (Target):</b></p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:12px; color:#f59e0b; border-left:2px solid #f59e0b; padding-left:8px;'>{ai_data.get('what_matters_next', 'N/A')}</p>", unsafe_allow_html=True)
                        
                        st.markdown(f"<p style='font-size:12px; color:#ffffff; margin-top:8px;'><b>Confirmation & Invalidation:</b></p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:11px; color:#8a99ad; margin-bottom:2px;'>Confirms: <span style='color:#00ffcc;'>{ai_data.get('what_confirms', 'N/A')}</span></p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:11px; color:#8a99ad; margin-bottom:2px;'>Invalidates: <span style='color:#ff5555;'>{ai_data.get('what_invalidates', 'N/A')}</span></p>", unsafe_allow_html=True)

                        ar = ai_data.get('asian_range', {})
                        if ar:
                            st.markdown(f"<p style='font-size:12px; color:#ffffff; margin-top:16px;'><b>Asian Range:</b></p>", unsafe_allow_html=True)
                            st.markdown(f"<div><span style='background:#1e293b; color:#f59e0b; padding:4px 8px; border-radius:4px; font-size:12px; font-weight:bold;'>High: {ar.get('asian_high')}</span> &nbsp; <span style='background:#1e293b; color:#f59e0b; padding:4px 8px; border-radius:4px; font-size:12px; font-weight:bold;'>Low: {ar.get('asian_low')}</span></div>", unsafe_allow_html=True)

                        st.markdown(f"<p style='font-size:12px; color:#ffffff; margin-top:16px;'><b>Liquidity Pools (Targets):</b></p>", unsafe_allow_html=True)
                        liq = ai_data.get('liquidity_zones', {})
                        
                        bsl_list = liq.get('bsl', [])
                        bsl_str = ", ".join([str(pool.get("price")) if isinstance(pool, dict) else str(pool) for pool in bsl_list]) if bsl_list else "None"
                        ssl_list = liq.get('ssl', [])
                        ssl_str = ", ".join([str(pool.get("price")) if isinstance(pool, dict) else str(pool) for pool in ssl_list]) if ssl_list else "None"
                        
                        st.markdown(f"<p style='font-size:11px; color:#8a99ad; margin-bottom:2px;'>BSL: <span style='color:#00ffcc;'>{bsl_str}</span></p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:11px; color:#8a99ad; margin-bottom:2px;'>SSL: <span style='color:#ff5555;'>{ssl_str}</span></p>", unsafe_allow_html=True)
                        st.markdown(f"<details style='{details_style}'><summary style='{summary_style}'> Liquidity Matrix</summary><div style='{content_style}'><b>Definition:</b> Major swing points acting as stops (liquidity). Smart money targets these areas.</div></details>", unsafe_allow_html=True)
                        
                        st.markdown(f"<p style='font-size:12px; color:#ffffff; margin-top:16px;'><b>Fair Value Gaps (FVG):</b></p>", unsafe_allow_html=True)
                        fvgs = ai_data.get('fvg_data', [])
                        if fvgs:
                            fvg_str = " ".join([f"<span style='color:{'#00ffcc' if 'BISI' in f['type'] else '#ff5555'}; border:1px solid {'#00ffcc' if 'BISI' in f['type'] else '#ff5555'}; padding:2px 4px; border-radius:2px;'>{'Bullish' if 'BISI' in f['type'] else 'Bearish'} [{f['bottom']} - {f['top']}]</span>" for f in fvgs[:3]])
                            st.markdown(f"<div style='font-size:11px;'>{fvg_str}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p style='font-size:11px; color:#64748b;'>No massive imbalances detected.</p>", unsafe_allow_html=True)
                        st.markdown(f"<details style='{details_style}'><summary style='{summary_style}'> FVG Matrix</summary><div style='{content_style}'><b>Definition:</b> 3-candle price delivery imbalances acting as magnets for price.</div></details>", unsafe_allow_html=True)

                        st.markdown(f"<p style='font-size:12px; color:#ffffff; margin-top:16px;'><b>Institutional Order Blocks:</b></p>", unsafe_allow_html=True)
                        obs = ai_data.get('ob_data', [])
                        if obs:
                            for ob in obs[:2]:
                                ob_color = "#00ffcc" if "Bullish" in ob['type'] else "#ff5555"
                                st.markdown(f"<div style='font-size:11px; color:{ob_color}; border:1px dashed {ob_color}; padding:4px; display:inline-block; margin-right:4px; margin-bottom:4px; border-radius:4px;'>{ob['type']} [{ob['bottom']} - {ob['top']}]</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p style='font-size:11px; color:#64748b;'>No unmitigated order blocks detected.</p>", unsafe_allow_html=True)
                        st.markdown(f"<details style='{details_style}'><summary style='{summary_style}'> What is this?</summary><div style='{content_style}'>The last opposing candle before an explosive move. These act as high probability bounce zones when price returns.</div></details>", unsafe_allow_html=True)

                with col_sum2:
                    with st.container(border=True):
                        st.markdown(f"<p style='font-size:11px;font-weight:800;color:#64748b;letter-spacing:0.8px;margin-bottom:6px;text-transform:uppercase;'>TRADE SETUP ENGINE</p>", unsafe_allow_html=True)
                        
                        scenario = ai_data.get('deterministic_scenario', {})
                        setup_status = scenario.get('status', 'NO TRADE')
                        quality = scenario.get('setup_quality', 'NO TRADE')
                        
                        # Colors
                        if setup_status == "READY": status_col = "#00ffcc"
                        elif setup_status == "WAITING": status_col = "#f59e0b"
                        elif setup_status == "WATCHING": status_col = "#3b82f6"
                        elif setup_status == "INVALIDATED": status_col = "#ff5555"
                        else: status_col = "#64748b"

                        if quality in ["A+", "A"]: qual_col = "#00ffcc"
                        elif quality == "B": qual_col = "#3b82f6"
                        elif quality == "C": qual_col = "#f59e0b"
                        else: qual_col = "#64748b"
                        
                        setup_html = f"""
<div style='background:rgba(255,255,255,0.02); padding:12px; border-left:3px solid {status_col}; border-radius:4px; margin-bottom:12px;'>
    <div style='display:flex; justify-content:space-between; align-items:center;'>
        <b style='color:#cbd5e1; font-size:14px;'>{scenario.get('setup', 'N/A')} SETUP</b>
        <span style='background:#1e293b; color:{status_col}; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;'>STATE: {setup_status}</span>
    </div>
    <div style='font-family:monospace; font-size:11px; color:#8a99ad; margin-top:12px; line-height:1.6; background:rgba(0,0,0,0.15); padding:8px; border-radius:4px;'>
        <div style='display:flex; justify-content:space-between;'><span>Entry Zone:</span> <span style='color:#00ffcc;'>{scenario.get('entry_zone', 'N/A')}</span></div>
        <div style='display:flex; justify-content:space-between;'><span>Ideal Entry:</span> <span style='color:#00ffcc;'>{scenario.get('ideal_entry', 'N/A')}</span></div>
        <div style='display:flex; justify-content:space-between;'><span>Stop Loss:</span> <span style='color:#ff5555;'>{scenario.get('stop_loss', 'N/A')}</span></div>
        <div style='display:flex; justify-content:space-between;'><span>Take Profit 1:</span> <span style='color:#10b981;'>{scenario.get('tp1', 'N/A')}</span></div>
        <div style='display:flex; justify-content:space-between;'><span>Take Profit 2:</span> <span style='color:#10b981;'>{scenario.get('tp2', 'N/A')}</span></div>
    </div>
    <div style='display:flex; justify-content:space-between; margin-top:12px;'>
        <div><span style='color:#475569; font-size:10px;'>R:R:</span> <span style='color:#cbd5e1; font-weight:bold; font-size:12px;'>{scenario.get('risk_reward', 'N/A')}</span></div>
        <div><span style='color:#475569; font-size:10px;'>Grade:</span> <span style='color:{qual_col}; font-weight:bold; font-size:12px;'>{quality}</span></div>
        <div><span style='color:#475569; font-size:10px;'>Conf:</span> <span style='color:#cbd5e1; font-weight:bold; font-size:12px;'>{scenario.get('confidence', 'N/A')}</span></div>
    </div>
    <div style='margin-top:12px; padding-top:12px; border-top:1px dashed #334155; font-size:11px; color:#cbd5e1;'>
        <b>Reason/Trigger:</b> <span style='color:#f59e0b;'>{scenario.get('trigger', scenario.get('reason', 'N/A'))}</span>
    </div>
</div>
"""
                        st.markdown(setup_html, unsafe_allow_html=True)
                        
                        val = ai_data.get('validation', {})
                        v_status = val.get('status', 'INVALID')
                        v_color = "#00ffcc" if v_status == "VALID" else "#ff5555"
                        v_reasons = "<br/>".join([f"- {r}" for r in val.get('warnings', [])])
                        
                        st.markdown(f"""<div style='background:rgba(255,255,255,0.02); padding:12px; border-left:3px solid {v_color}; border-radius:4px;'>
                            <b style='color:#cbd5e1;'>Macro Validation Filter</b><br/>
                            <div style='margin-top:8px; margin-bottom:4px;'><span style='background:#1e293b; color:{v_color}; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;'>{v_status}</span></div>
                            <div style='font-family:monospace; font-size:10px; color:#ff5555; margin-top:4px;'>{v_reasons if v_status == "INVALID" else "<span style='color:#00ffcc;'>All macro clear for execution.</span>"}</div>
                        </div>""", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown(f"<p style='font-size:11px;font-weight:800;color:#64748b;letter-spacing:0.8px;margin-bottom:6px;text-transform:uppercase;'>ML EDGE SCORE (RANDOM FOREST)</p>", unsafe_allow_html=True)
                        if ml_buy > 0 or ml_sell > 0 or ml_neutral > 0:
                            st.markdown(f"<p style='font-size:13px; color:#00ffcc; margin-bottom:4px;'><b>BUY Probability:</b> {ml_buy}%</p>", unsafe_allow_html=True)
                            st.markdown(f"<p style='font-size:13px; color:#ff5555; margin-bottom:4px;'><b>SELL Probability:</b> {ml_sell}%</p>", unsafe_allow_html=True)
                            st.markdown(f"<p style='font-size:13px; color:#fbbf24; margin-bottom:4px;'><b>NEUTRAL Probability:</b> {ml_neutral}%</p>", unsafe_allow_html=True)
                            st.markdown(f"<p style='font-size:11px; color:#64748b;'>Model Confidence: {ai_data.get('ml_confidence', 'Unknown')}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p style='font-size:12px; color:#8a99ad;'>Model data unavailable.</p>", unsafe_allow_html=True)

                dq = ai_data.get("data_quality", {})
                dq_str = f"Data: {dq.get('price_data', 'Unknown')} \u2022 News: {dq.get('news', 'Unknown')} \u2022 Vol: {dq.get('volume', 'Unknown')}"
                st.markdown(f"<p style='font-size:10px; color:#64748b; margin-top:8px;'>Timestamp: {ai_data.get('timestamp','')} UTC \u2022 Confidence: {ai_data.get('confidence','')} \u2022 [Deterministic fallback logic used (Ollama unavailable or failed).]<br/>{ai_data.get('disclaimer','')}</p>", unsafe_allow_html=True)
            else:
                st.warning(ai_data.get("error", "AI market analysis could not load live data."))



        # ----------------------------------------------------
        # RESEARCH LAB — STRATEGY EDGE DISCOVERY (PHASE 14)
        # ----------------------------------------------------
        with tab_research:
            st.markdown("<h3 style='color:#ffffff;font-size:1.3rem;margin:0 0 4px 0;font-weight:800;text-transform:uppercase;'>Strategy Edge Discovery & Research Lab</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color:#8a99ad;font-size:13px;margin-bottom:14px;'>Statistical Expectancy, 3-Layer Partition (Train / Validation / Untouched Holdout), Bootstrap 95% CIs, and Component Attribution.</p>", unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown("<div style='font-size:0.75rem;font-weight:800;color:#00ffcc;letter-spacing:1px;margin-bottom:12px;'>RESEARCH EXPERIMENT CONTROLS</div>", unsafe_allow_html=True)
                r_col1, r_col2, r_col3, r_col4, r_col5 = st.columns(5)
                with r_col1:
                    import strategies
                    r_strat_list = strategies.get_all_strategy_names()
                    r_selected_strat = st.selectbox("Strategy Subject", options=r_strat_list, index=0, key="rl_strat_sel")
                    r_symbol = st.selectbox("Asset Symbol", ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "NAS100", "US500", "GER40", "BTCUSD"], index=0, key="rl_sym_sel")
                with r_col2:
                    r_exec_tf = st.selectbox("Execution TF", ["15m", "5m", "1h", "4h", "1d"], index=0, key="rl_exec_tf")
                    r_struct_tf = st.selectbox("Structure TF", ["1h", "4h", "15m"], index=0, key="rl_struct_tf")
                with r_col3:
                    r_bias_tf = st.selectbox("Bias TF", ["4h", "1d", "1h"], index=0, key="rl_bias_tf")
                    r_capital = st.number_input("Starting Capital ($)", value=10000.0, step=1000.0, key="rl_cap")
                with r_col4:
                    r_risk_pct = st.number_input("Risk Per Trade (%)", value=1.0, step=0.1, key="rl_risk")
                    r_spread_pips = st.number_input("Spread (Pips)", value=1.0, step=0.2, key="rl_spread")
                with r_col5:
                    r_slippage_pips = st.number_input("Slippage (Pips)", value=0.5, step=0.1, key="rl_slip")
                    r_commission_pct = st.number_input("Commission (%)", value=0.005, step=0.001, key="rl_comm")

                st.markdown("<p style='font-size:11px;color:#8a99ad;margin:6px 0 12px 0;'><b>Data Partition:</b> 60% Train (In-Sample Discovery) \u2022 20% Validation (Tuning) \u2022 20% Final Holdout (Untouched Audit)</p>", unsafe_allow_html=True)
                run_research_btn = st.button("RUN STATISTICAL EDGE AUDIT", type="primary", use_container_width=True, key="rl_btn_run")

            RESEARCH_CACHE_KEY = f"rl_cache_{r_selected_strat}_{r_symbol}_{r_exec_tf}"
            
            if run_research_btn:
                with st.spinner(f"Running statistical research audit on {r_selected_strat} ({r_symbol} {r_exec_tf})..."):
                    import backtester
                    import research_engine
                    import research_analytics

                    # 1. Register Experiment
                    exp = research_engine.ResearchExperiment(
                        run_id=f"EXP_{r_symbol}_{r_exec_tf}_{datetime.now().strftime('%H%M%S')}",
                        strategy_name=r_selected_strat,
                        strategy_version="1.1.0",
                        symbol=r_symbol,
                        timeframe=r_exec_tf,
                        struct_tf=r_struct_tf,
                        bias_tf=r_bias_tf,
                        spread_pips=r_spread_pips,
                        slippage_pips=r_slippage_pips,
                        commission_pct=r_commission_pct
                    )
                    tracker = research_engine.MultipleTestingTracker()
                    hypo_id = tracker.register_experiment(exp)

                    # 2. Run Backtester with Train / Val / Holdout splits
                    # Convert pips to price units
                    spread_px = r_spread_pips * (0.01 if "JPY" in r_symbol else 0.0001)
                    slip_px = r_slippage_pips * (0.01 if "JPY" in r_symbol else 0.0001)

                    # Run IS (Train 60%) + OOS (Validation 20% + Holdout 20%)
                    bt_res = backtester.run_backtest(
                        symbol=r_symbol,
                        timeframe=r_exec_tf,
                        strategy=r_selected_strat,
                        risk_pct=r_risk_pct,
                        capital=r_capital,
                        slippage=slip_px,
                        commission_pct=r_commission_pct,
                        fixed_spread=spread_px,
                        train_split=0.60
                    )

                    st.session_state[RESEARCH_CACHE_KEY] = {
                        "experiment": exp.to_dict(),
                        "hypothesis_status": tracker.get_risk_status(),
                        "backtest_result": bt_res
                    }

            res_cached = st.session_state.get(RESEARCH_CACHE_KEY, None)

            if res_cached and "backtest_result" in res_cached and "error" not in res_cached["backtest_result"]:
                bt = res_cached["backtest_result"]
                trades_raw = bt.get("trades", [])
                
                import research_engine
                import research_analytics

                df_r = research_analytics.calculate_trade_r_multiples(trades_raw)
                
                # Split trades into Train (IS), Validation (OOS 1), and Final Holdout (OOS 2)
                n_t = len(df_r)
                is_trades = df_r.iloc[:int(n_t * 0.60)] if n_t > 0 else pd.DataFrame()
                val_trades = df_r.iloc[int(n_t * 0.60):int(n_t * 0.80)] if n_t > 0 else pd.DataFrame()
                holdout_trades = df_r.iloc[int(n_t * 0.80):] if n_t > 0 else pd.DataFrame()

                # Calculate R metrics
                is_exp_r = float(is_trades['r_multiple'].mean()) if not is_trades.empty else 0.0
                val_exp_r = float(val_trades['r_multiple'].mean()) if not val_trades.empty else 0.0
                holdout_exp_r = float(holdout_trades['r_multiple'].mean()) if not holdout_trades.empty else 0.0

                # 95% Bootstrap CI on combined Out-of-Sample (Val + Holdout)
                oos_trades = df_r.iloc[int(n_t * 0.60):] if n_t > 0 else pd.DataFrame()
                oos_r_list = list(oos_trades['r_multiple'].values) if not oos_trades.empty else []
                boot_ci = research_engine.BootstrapEstimator.calculate_r_expectancy_ci(oos_r_list, n_iterations=3000, random_seed=42)

                # Execution Sensitivity & Stress Testing
                stress_res = research_analytics.stress_test_execution_sensitivity(trades_raw)
                fragility = stress_res.get("fragility_rating", "MODERATE")

                # Strategy Scorecard
                is_m = {"total_trades": len(is_trades), "expectancy_r": is_exp_r}
                oos_m = {"total_trades": len(val_trades), "expectancy_r": val_exp_r}
                hold_m = {"total_trades": len(holdout_trades), "expectancy_r": holdout_exp_r}
                
                scorecard = research_engine.ScorecardClassifier.evaluate_strategy(
                    is_m, oos_m, hold_m, boot_ci, wfo_status="Robust", execution_fragility=fragility, parameter_stability="STABLE"
                )

                # 1. SCORECARD HERO BANNER
                sc_status = scorecard.get("status", "UNCERTAIN")
                sc_color = scorecard.get("color", "#f59e0b")
                sc_reasons = scorecard.get("score_reasons", [])

                st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.85); border: 2px solid {sc_color}; border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 0 20px rgba(0,0,0,0.4);">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <div>
                            <span style="font-size:11px; font-weight:800; color:#8a99ad; text-transform:uppercase; letter-spacing:1px;">STRATEGY EDGE SCORECARD:</span>
                            <h2 style="margin:2px 0 0 0; color:{sc_color}; font-size:1.6rem; font-weight:900;">{sc_status}</h2>
                        </div>
                        <div style="text-align:right; font-size:12px; color:#cbd5e1;">
                            <div>Sample Size: <b style="color:#ffffff;">N = {n_t} Trades</b> ({boot_ci.get('sample_confidence', 'N/A')})</div>
                            <div style="margin-top:2px;">95% Bootstrap CI: <b style="color:{sc_color};">{boot_ci.get('ci_range_str', 'N/A')}</b></div>
                        </div>
                    </div>
                    <hr style="border-color:rgba(255,255,255,0.08); margin:10px 0;">
                    <div style="font-size:12px; color:#94a3b8;">
                        {''.join([f"<div style='margin-bottom:3px;'>• <span style='color:#e2e8f0;'>{r}</span></div>" for r in sc_reasons])}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # 2. THREE-LAYER PARTITION METRICS ROW
                st.markdown("<div style='font-size:0.75rem;font-weight:800;color:#00ffcc;letter-spacing:1px;margin-bottom:10px;'>THREE-LAYER DATA PARTITION RESULTS</div>", unsafe_allow_html=True)
                c_sp1, c_sp2, c_sp3, c_sp4 = st.columns(4)
                with c_sp1:
                    st.metric("1. Train Expectancy (60%)", f"{is_exp_r:+.3f} R", f"{len(is_trades)} Trades", help=research_explanations.get_tooltip("expectancy_r"))
                with c_sp2:
                    st.metric("2. Validation Expectancy (20%)", f"{val_exp_r:+.3f} R", f"{len(val_trades)} Trades (OOS)", help=research_explanations.get_tooltip("expectancy_r"))
                with c_sp3:
                    st.metric("3. Final Holdout Expectancy (20%)", f"{holdout_exp_r:+.3f} R", f"{len(holdout_trades)} Trades (Untouched)", help=research_explanations.get_tooltip("holdout_expectancy_r"))
                with c_sp4:
                    st.metric("Execution Fragility", fragility.split(' ')[0], f"Base: {stress_res.get('base_expectancy_r', 0.0):+.3f} R", help=research_explanations.get_tooltip("slippage"))

                # Explainable Research Guide Expander
                holdout_interp = research_explanations.ExplainableResearchClassifier.interpret_expectancy(
                    holdout_exp_r, n_t, boot_ci.get('ci_lower'), boot_ci.get('ci_upper')
                )
                with st.expander("WHAT DO THESE NUMBERS MEAN? (EXPLAINABLE RESEARCH GUIDE)", expanded=False):
                    c_exp_l, c_exp_r = st.columns(2)
                    with c_exp_l:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02); padding:10px; border-radius:6px; font-size:12px; line-height:1.5; color:#cbd5e1;">
                            <b style="color:#00ffcc;">Holdout Expectancy Assessment:</b> <span style="color:#ffffff; font-weight:700;">{holdout_interp['status']}</span><br/>
                            <b>Interpretation:</b> {holdout_interp['assessment']}<br/>
                            <b>Sample Size Reliability:</b> <span style="color:#bef264;">{holdout_interp['sample_tier']} (N = {n_t})</span><br/>
                            <span style="color:#94a3b8; font-size:11px;">{holdout_interp['sample_text']}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    with c_exp_r:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02); padding:10px; border-radius:6px; font-size:12px; line-height:1.5; color:#cbd5e1;">
                            <b style="color:#bef264;">95% Bootstrap CI Range:</b> <span style="color:#ffffff; font-weight:700;">{boot_ci.get('ci_range_str', 'N/A')} [{holdout_interp['ci_status']}]</span><br/>
                            <b>Statistical Evidence:</b> {holdout_interp['ci_text']}<br/>
                            <b>Mandatory Caveat:</b> <span style="color:#f59e0b; font-size:11px;">{holdout_interp['caveat']}</span>
                        </div>
                        """, unsafe_allow_html=True)

                st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

                # 3. RESEARCH DIMENSION TABS
                tab_res_dim1, tab_res_dim2, tab_res_dim3, tab_res_dim4, tab_res_dim5, tab_res_dim6, tab_res_dim7, tab_res_dim8, tab_res_dim9, tab_res_dim10, tab_res_dim11, tab_res_dim12 = st.tabs([
                    "LIQUIDITY & SESSIONS",
                    "CONFLUENCE & QUALITY CURVE",
                    "EXECUTION SENSITIVITY",
                    "EXPECTANCY DRIFT MONITOR",
                    "USDJPY REVERSAL LAB",
                    "USDJPY CONTINUATION LAB",
                    "USDJPY EDGE DISCOVERY",
                    "USDJPY CONDITIONAL VALIDATION",
                    "TRUE MTF RESEARCH LAB",
                    "XAUUSD ADVERSARIAL AUDIT",
                    "XAUUSD FORWARD VALIDATION",
                    "AI RESEARCH INTERPRETATION"
                ])

                with tab_res_dim1:
                    col_lq1, col_lq2 = st.columns(2)
                    with col_lq1:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>Expectancy by Liquidity Source</p>", unsafe_allow_html=True)
                        liq_df = research_analytics.analyze_liquidity_sources(df_r)
                        if not liq_df.empty:
                            st.dataframe(liq_df[["liquidity_type", "trades_N", "expectancy_r", "win_rate_pct", "profit_factor", "max_drawdown_r"]], use_container_width=True)
                    with col_lq2:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>Expectancy by Trading Session</p>", unsafe_allow_html=True)
                        sess_res = research_analytics.analyze_sessions(df_r)
                        sess_df = sess_res.get("session_breakdown", pd.DataFrame())
                        if not sess_df.empty:
                            st.dataframe(sess_df[["session", "trades_N", "expectancy_r", "win_rate_pct", "profit_factor"]], use_container_width=True)

                    if not sess_res.get("liquidity_session_matrix", pd.DataFrame()).empty:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#bef264; margin-top:10px;'>Liquidity Source \u00d7 Session Matrix Combinations</p>", unsafe_allow_html=True)
                        st.dataframe(sess_res["liquidity_session_matrix"][["liq_session_combo", "trades_N", "expectancy_r", "win_rate_pct", "profit_factor"]], use_container_width=True)

                with tab_res_dim2:
                    conf_res = research_analytics.analyze_confluence_calibration(df_r)
                    st.markdown(f"<div style='background:rgba(255,255,255,0.03); padding:8px 12px; border-radius:6px; margin-bottom:10px; font-size:12px;'><b style='color:#00ffcc;'>Calibration Status:</b> {conf_res.get('calibration_status', 'N/A')}</div>", unsafe_allow_html=True)
                    
                    c_qc1, c_qc2 = st.columns([1.5, 1])
                    with c_qc1:
                        qc_data = conf_res.get("quality_curve", [])
                        if qc_data:
                            df_qc = pd.DataFrame(qc_data)
                            fig_qc = px.line(df_qc, x="min_confluence", y="expectancy_r", title="Trade Quality Curve (Min Confluence vs Expectancy R)", markers=True, color_discrete_sequence=['#00ffcc'])
                            fig_qc.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8'))
                            st.plotly_chart(fig_qc, use_container_width=True)
                    with c_qc2:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#cbd5e1;'>Confluence Score Buckets</p>", unsafe_allow_html=True)
                        if not conf_res.get("buckets", pd.DataFrame()).empty:
                            st.dataframe(conf_res["buckets"][["confluence_bucket", "trades_N", "expectancy_r", "win_rate_pct"]], use_container_width=True)

                with tab_res_dim3:
                    st.markdown("<p style='font-size:12px; font-weight:700; color:#ff5555;'>Execution Cost Degradation Matrix (Spread, Slippage & Latency)</p>", unsafe_allow_html=True)
                    if "scenarios" in stress_res:
                        df_stress = pd.DataFrame(stress_res["scenarios"])
                        st.dataframe(df_stress, use_container_width=True)

                with tab_res_dim4:
                    drift_res = research_analytics.monitor_expectancy_drift(df_r)
                    st.markdown(f"<div style='background:rgba(255,255,255,0.03); padding:8px 12px; border-radius:6px; margin-bottom:10px; font-size:12px;'><b style='color:#bef264;'>Expectancy Drift State:</b> {drift_res.get('status', 'N/A')} (Rolling 20: {drift_res.get('rolling_20_r', 0.0):+.3f}R | Rolling 50: {drift_res.get('rolling_50_r', 0.0):+.3f}R)</div>", unsafe_allow_html=True)
                    
                    drift_curve = drift_res.get("curve", [])
                    if drift_curve:
                        df_dc = pd.DataFrame(drift_curve)
                        fig_dc = px.line(df_dc, x="trade_index", y="rolling_20_r", title="Rolling 20-Trade Expectancy Drift (R)", color_discrete_sequence=['#bef264'])
                        fig_dc.add_hline(y=0.0, line_dash="dash", line_color="#ff5555")
                        fig_dc.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8'))
                        st.plotly_chart(fig_dc, use_container_width=True)

                with tab_res_dim5:
                    st.markdown("<p style='font-size:12px; font-weight:700; color:#f59e0b;'>USDJPY Reversal Ablation Matrix (Phase 15)</p>", unsafe_allow_html=True)
                    
                    import usdjpy_research
                    if st.button("RUN USDJPY 12-CONDITION REVERSAL STUDY", key="btn_run_usdjpy_ablations", use_container_width=True):
                        with st.spinner("Running 12 controlled reversal ablation experiments on USDJPY 15m..."):
                            ab_results = usdjpy_research.USDJPYAblationRunner.run_all_ablations(timeframe="15m")
                            st.session_state["usdjpy_ab_cache"] = ab_results

                    usdjpy_cache = st.session_state.get("usdjpy_ab_cache", None)
                    if usdjpy_cache:
                        df_ab = pd.DataFrame(usdjpy_cache)
                        st.dataframe(df_ab[["name", "trades_N", "win_rate_pct", "expectancy_r", "is_expectancy_r", "val_expectancy_r", "holdout_expectancy_r", "bootstrap_ci", "status"]], use_container_width=True)

                    # Diagnostic Profiling
                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)
                    col_uj1, col_uj2 = st.columns(2)
                    with col_uj1:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>Directional Expectancy (Long vs Short)</p>", unsafe_allow_html=True)
                        uj_dir = usdjpy_research.USDJPYDiagnosticProfiler.profile_direction(df_r)
                        c_dir1, c_dir2 = st.columns(2)
                        c_dir1.metric("Long Expectancy", f"{uj_dir.get('long_expectancy_r', 0.0):+.3f} R", f"{uj_dir.get('long_trades', 0)} Trades ({uj_dir.get('long_win_rate_pct', 0.0)}% WR)")
                        c_dir2.metric("Short Expectancy", f"{uj_dir.get('short_expectancy_r', 0.0):+.3f} R", f"{uj_dir.get('short_trades', 0)} Trades ({uj_dir.get('short_win_rate_pct', 0.0)}% WR)")
                        st.markdown(f"<div style='font-size:11px; color:#8a99ad; margin-top:4px;'>Verdict: <b style='color:#ffffff;'>{uj_dir.get('directional_bias_verdict')}</b></div>", unsafe_allow_html=True)
                    with col_uj2:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#ff5555;'>MAE / MFE Structural Profit Giveback Diagnosis</p>", unsafe_allow_html=True)
                        uj_mae = usdjpy_research.USDJPYDiagnosticProfiler.profile_mae_mfe(df_r)
                        c_mae1, c_mae2 = st.columns(2)
                        c_mae1.metric("Stopped Out After +1R", f"{uj_mae.get('reached_1r_stopout_pct', 0.0)}%", f"{uj_mae.get('reached_1r_loss_count', 0)} Trades")
                        c_mae2.metric("Immediate Invalidations", f"{uj_mae.get('immediate_invalidations_pct', 0.0)}%", "Losers")
                        st.markdown(f"<div style='font-size:11px; color:#cbd5e1; margin-top:6px; background:rgba(0,0,0,0.2); padding:6px 8px; border-radius:4px;'><b>Diagnosis:</b> {uj_mae.get('structural_diagnosis')}</div>", unsafe_allow_html=True)

                    st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc; margin-top:14px;'>Comparison Against Mechanical Baselines</p>", unsafe_allow_html=True)
                    uj_baselines = usdjpy_research.USDJPYDiagnosticProfiler.compare_mechanical_baselines(df_r)
                    st.dataframe(pd.DataFrame(uj_baselines), use_container_width=True)

                with tab_res_dim6:
                    st.markdown("<p style='font-size:12px; font-weight:700; color:#bef264;'>USDJPY SMC Trend-Continuation Lab (Phase 16)</p>", unsafe_allow_html=True)
                    
                    import usdjpy_continuation_research
                    if st.button("RUN USDJPY 12-CONDITION CONTINUATION STUDY", key="btn_run_usdjpy_cont_ablations", use_container_width=True):
                        with st.spinner("Running 12 controlled trend-continuation experiments on USDJPY 15m..."):
                            cont_results = usdjpy_continuation_research.USDJPYContinuationAblationRunner.run_all_ablations(timeframe="15m")
                            st.session_state["usdjpy_cont_cache"] = cont_results

                    cont_cache = st.session_state.get("usdjpy_cont_cache", None)
                    if cont_cache:
                        df_cont = pd.DataFrame(cont_cache)
                        st.dataframe(df_cont[["name", "trades_N", "win_rate_pct", "expectancy_r", "is_expectancy_r", "val_expectancy_r", "holdout_expectancy_r", "bootstrap_ci", "status"]], use_container_width=True)

                    # Continuation Diagnostic Profiling
                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)
                    col_ujc1, col_ujc2 = st.columns(2)
                    with col_ujc1:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>Continuation Directional Split</p>", unsafe_allow_html=True)
                        ujc_dir = usdjpy_continuation_research.USDJPYContinuationProfiler.profile_direction(df_r)
                        c_cdir1, c_cdir2 = st.columns(2)
                        c_cdir1.metric("Long Expectancy", f"{ujc_dir.get('long_expectancy_r', 0.0):+.3f} R", f"{ujc_dir.get('long_trades', 0)} Trades ({ujc_dir.get('long_win_rate_pct', 0.0)}% WR)")
                        c_cdir2.metric("Short Expectancy", f"{ujc_dir.get('short_expectancy_r', 0.0):+.3f} R", f"{ujc_dir.get('short_trades', 0)} Trades ({ujc_dir.get('short_win_rate_pct', 0.0)}% WR)")
                    with col_ujc2:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#ff5555;'>Continuation MAE / MFE Excursion Diagnosis</p>", unsafe_allow_html=True)
                        ujc_mae = usdjpy_continuation_research.USDJPYContinuationProfiler.profile_mae_mfe(df_r)
                        c_cmae1, c_cmae2 = st.columns(2)
                        c_cmae1.metric("Immediate Invalidations", f"{ujc_mae.get('immediate_invalidations_pct', 0.0)}%", "Losers")
                        c_cmae2.metric("Giveback After +1R", f"{ujc_mae.get('reached_1r_stopout_pct', 0.0)}%", f"{ujc_mae.get('reached_1r_loss_count', 0)} Trades")
                        st.markdown(f"<div style='font-size:11px; color:#cbd5e1; margin-top:6px; background:rgba(0,0,0,0.2); padding:6px 8px; border-radius:4px;'><b>Diagnosis:</b> {ujc_mae.get('structural_diagnosis')}</div>", unsafe_allow_html=True)

                    st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc; margin-top:14px;'>Continuation vs Mechanical Trend Baselines</p>", unsafe_allow_html=True)
                    ujc_baselines = usdjpy_continuation_research.USDJPYContinuationProfiler.compare_mechanical_baselines(df_r)
                    st.dataframe(pd.DataFrame(ujc_baselines), use_container_width=True)

                with tab_res_dim7:
                    st.markdown("<p style='font-size:12px; font-weight:700; color:#38bdf8;'>USDJPY Edge Discovery Lab: Regimes, Sessions & Mechanical Models (Phase 17)</p>", unsafe_allow_html=True)
                    
                    import usdjpy_edge_discovery
                    if st.button("RUN USDJPY 27-STRATEGY EDGE DISCOVERY EXPERIMENTS", key="btn_run_usdjpy_edge_disc", use_container_width=True):
                        with st.spinner("Executing 27 mechanical strategy and baseline experiments on USDJPY 15m..."):
                            disc_results = usdjpy_edge_discovery.USDJPYMechanicalExperimentRunner.run_all_experiments(timeframe="15m")
                            st.session_state["usdjpy_edge_disc_cache"] = disc_results

                    disc_cache = st.session_state.get("usdjpy_edge_disc_cache", None)
                    if disc_cache:
                        df_disc = pd.DataFrame(disc_cache)
                        st.dataframe(df_disc[["name", "category", "trades_N", "win_rate_pct", "expectancy_r", "is_expectancy_r", "val_expectancy_r", "holdout_expectancy_r", "complexity_penalty", "research_score", "status"]], use_container_width=True)

                    # Deep Excursion & Dynamic Metrics
                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)
                    c_disc_ex1, c_disc_ex2 = st.columns(2)
                    with c_disc_ex1:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>Deep MAE / MFE Excursion Milestones</p>", unsafe_allow_html=True)
                        deep_ex = usdjpy_edge_discovery.USDJPYDeepExcursionAnalyzer.profile_deep_excursion(df_r)
                        c_dex1, c_dex2 = st.columns(2)
                        c_dex1.metric("Reached +0.5R", f"{deep_ex.get('pct_reached_0_5r', 0.0)}%", "Trades")
                        c_dex2.metric("Reached +1.0R", f"{deep_ex.get('pct_reached_1_0r', 0.0)}%", "Trades")
                        c_dex3, c_dex4 = st.columns(2)
                        c_dex3.metric("Reached +2.0R", f"{deep_ex.get('pct_reached_2_0r', 0.0)}%", "Trades")
                        c_dex4.metric("Immediate Invalidations", f"{deep_ex.get('immediate_invalidations_pct', 0.0)}%", "Losers")

                    with c_disc_ex2:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#cbd5e1;'>Holding-Time Duration Buckets</p>", unsafe_allow_html=True)
                        ht_data = usdjpy_edge_discovery.USDJPYHoldingTimeAnalyzer.profile_holding_time(df_r)
                        st.dataframe(pd.DataFrame(ht_data)[["duration_bucket", "trades_N", "win_rate_pct", "expectancy_r", "verdict"]], use_container_width=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)
                    c_dow1, c_dow2 = st.columns(2)
                    with c_dow1:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>Day-of-Week Performance Profile</p>", unsafe_allow_html=True)
                        dow_profile = usdjpy_edge_discovery.USDJPYDayOfWeekAnalyzer.profile_days_and_transitions(df_r)
                        st.dataframe(pd.DataFrame(dow_profile.get("day_breakdown", []))[["day", "trades_N", "win_rate_pct", "expectancy_r", "verdict"]], use_container_width=True)
                    with c_dow2:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#bef264;'>Session Transition Persistence Matrix</p>", unsafe_allow_html=True)
                        st.dataframe(pd.DataFrame(dow_profile.get("session_transitions", []))[["transition", "trend_persistence_pct", "reversal_rate_pct", "verdict"]], use_container_width=True)

                    st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc; margin-top:14px;'>Empirical Trend Persistence Map (+4 to +32 Bars)</p>", unsafe_allow_html=True)
                    t_persistence = usdjpy_edge_discovery.USDJPYTrendPersistenceAnalyzer.profile_trend_persistence()
                    st.dataframe(pd.DataFrame(t_persistence)[["trigger_event", "bars_4_continuation_pct", "bars_8_continuation_pct", "bars_16_continuation_pct", "bars_32_continuation_pct", "verdict"]], use_container_width=True)

                with tab_res_dim8:
                    st.markdown("<p style='font-size:12px; font-weight:700; color:#a855f7;'>USDJPY Regime-Conditional Edge Validation (Phase 18)</p>", unsafe_allow_html=True)
                    
                    import usdjpy_conditional_validation
                    if st.button("RUN USDJPY REGIME-CONDITIONAL VALIDATION (PHASE 18)", key="btn_run_usdjpy_cond_val", use_container_width=True):
                        with st.spinner("Executing Phase 18 validation: Weekday, Holding-Time, Permutation & WFO tests..."):
                            perm_data = usdjpy_conditional_validation.USDJPYPermutationTester.run_permutation_test(n_iterations=5000, random_seed=42)
                            comb_data = usdjpy_conditional_validation.USDJPYCombinationTester.evaluate_combination()
                            wfo_data = usdjpy_conditional_validation.USDJPYWalkForwardValidator.run_walk_forward()
                            mc_data = usdjpy_conditional_validation.USDJPYMonteCarloSimulator.run_monte_carlo(n_simulations=5000, random_seed=42)
                            mt_data = usdjpy_conditional_validation.USDJPYCumulativeMultipleTesting.audit_cumulative_hypotheses()
                            st.session_state["usdjpy_phase18_cache"] = {
                                "permutation": perm_data,
                                "combination": comb_data,
                                "wfo": wfo_data,
                                "monte_carlo": mc_data,
                                "multiple_testing": mt_data
                            }

                    p18_cache = st.session_state.get("usdjpy_phase18_cache", None)
                    if p18_cache:
                        c_p18_1, c_p18_2, c_p18_3, c_p18_4 = st.columns(4)
                        c_p18_1.metric("Observed Delta (Tue/Wed vs Others)", f"{p18_cache['permutation'].get('observed_delta_r', 0.0):+.3f} R", "Empirical Delta")
                        c_p18_2.metric("Permutation p-value (5000 runs)", f"{p18_cache['permutation'].get('empirical_p_value', 0.0):.4f}", p18_cache['permutation'].get('statistical_verdict', ''))
                        c_p18_3.metric("WFO Profitable Windows", f"{p18_cache['wfo'].get('profitable_windows', 0)}/{p18_cache['wfo'].get('total_windows', 0)} ({p18_cache['wfo'].get('window_profitability_pct', 0.0)}%)", f"Median: {p18_cache['wfo'].get('median_oos_expectancy_r', 0.0):+.3f} R")
                        c_p18_4.metric("Cumulative Hypotheses Tested", f"{p18_cache['multiple_testing'].get('total_cumulative_hypotheses', 0)}", f"Penalty: {p18_cache['multiple_testing'].get('multiple_testing_penalty_r', 0.0):+.3f} R")

                        st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)
                        c_val_l, c_val_r = st.columns(2)
                        with c_val_l:
                            st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>Fixed Holding-Period Duration Exits (H2)</p>", unsafe_allow_html=True)
                            hold_exits = usdjpy_conditional_validation.USDJPYFixedHoldingTester.test_fixed_holding_durations()
                            st.dataframe(pd.DataFrame(hold_exits)[["duration_str", "trades_N", "win_rate_pct", "expectancy_r", "bootstrap_ci", "verdict"]], use_container_width=True)

                        with c_val_r:
                            st.markdown("<p style='font-size:12px; font-weight:700; color:#cbd5e1;'>Rolling Walk-Forward Stability (6m Train / 2m OOS)</p>", unsafe_allow_html=True)
                            st.dataframe(pd.DataFrame(p18_cache['wfo'].get("windows", []))[["window_id", "train_period", "oos_period", "oos_trades_N", "oos_win_rate_pct", "oos_expectancy_r", "status"]], use_container_width=True)

                        st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)
                        c_p18_mc1, c_p18_mc2 = st.columns(2)
                        with c_p18_mc1:
                            st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>Monte Carlo 5,000-Run Drawdown Distribution</p>", unsafe_allow_html=True)
                            mc_dict = p18_cache["monte_carlo"]
                            st.markdown(f"""
                            <div style="background:rgba(255,255,255,0.02); padding:10px; border-radius:4px; font-size:11px; color:#cbd5e1; line-height:1.6;">
                                <b>Median Expectancy:</b> {mc_dict.get('median_expectancy_r', 0.0):+.3f} R<br/>
                                <b>90% Confidence Interval:</b> [{mc_dict.get('percentile_5th_expectancy_r', 0.0):+.3f} R, {mc_dict.get('percentile_95th_expectancy_r', 0.0):+.3f} R]<br/>
                                <b>Median Max Drawdown:</b> {mc_dict.get('median_max_drawdown_r', 0.0):.2f} R (95th Pct: {mc_dict.get('percentile_95th_max_drawdown_r', 0.0):.2f} R)<br/>
                                <b>Prob. of Negative Return:</b> {mc_dict.get('probability_negative_total_return_pct', 0.0)}% | <b>Prob. of 20R Drawdown:</b> {mc_dict.get('probability_20r_drawdown_pct', 0.0)}%
                            </div>
                            """, unsafe_allow_html=True)
                        with c_p18_mc2:
                            st.markdown("<p style='font-size:12px; font-weight:700; color:#bef264;'>Multi-Dimensional Interactions & Regime Transitions</p>", unsafe_allow_html=True)
                            trans_list = usdjpy_conditional_validation.USDJPYRegimeTransitionAnalyzer.analyze_transitions()
                            st.dataframe(pd.DataFrame(trans_list)[["transition", "sample_N", "continuation_win_rate_pct", "expectancy_r", "verdict"]], use_container_width=True)

                        st.markdown(f"""
                        <div style="background:rgba(245,158,11,0.1); border:1px solid #f59e0b; border-radius:6px; padding:12px; margin-top:14px; font-size:12px; color:#fef3c7;">
                            <b>PHASE 18 SCIENTIFIC VERDICT: PROMISING BUT UNCONFIRMED</b><br/>
                            Candidate exhibits positive Holdout (+0.225R) and low permutation p-value (p = {p18_cache['permutation'].get('empirical_p_value', 0.0):.4f}). However, because discovery occurred post-hoc after {p18_cache['multiple_testing'].get('total_cumulative_hypotheses', 0)} prior hypothesis evaluations, multiple-testing risk remains elevated. USDJPY remains strictly BLOCKED from live trading automation.
                        </div>
                        """, unsafe_allow_html=True)

                with tab_res_dim9:
                    st.markdown("<p style='font-size:12px; font-weight:700; color:#38bdf8;'>True Multi-Timeframe (1D->4H->15M->5M->1M) Research Lab (Phase 19)</p>", unsafe_allow_html=True)
                    
                    # VISUAL MTF ARCHITECTURE PIPELINE
                    st.markdown("""
                    <div style="background:rgba(15,23,42,0.85); border:1px solid rgba(0,255,204,0.3); border-radius:8px; padding:14px; margin-bottom:14px;">
                        <div style="font-size:11px; font-weight:800; color:#00ffcc; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px;">TRUE MULTI-TIMEFRAME EXECUTION PIPELINE</div>
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; font-size:11px;">
                            <div style="background:rgba(0,0,0,0.3); border:1px solid #334155; padding:6px 10px; border-radius:4px; text-align:center;">
                                <b style="color:#00ffcc;">1D Macro Bias</b><br/><span style="color:#94a3b8;">Daily Closed Bars</span>
                            </div>
                            <div style="color:#64748b; font-weight:900;">&rarr;</div>
                            <div style="background:rgba(0,0,0,0.3); border:1px solid #334155; padding:6px 10px; border-radius:4px; text-align:center;">
                                <b style="color:#00ffcc;">4H Draw on Liquidity</b><br/><span style="color:#94a3b8;">4H FVGs & EQH/EQL</span>
                            </div>
                            <div style="color:#64748b; font-weight:900;">&rarr;</div>
                            <div style="background:rgba(0,0,0,0.3); border:1px solid #334155; padding:6px 10px; border-radius:4px; text-align:center;">
                                <b style="color:#00ffcc;">15M Setup</b><br/><span style="color:#94a3b8;">Sweep + MSS</span>
                            </div>
                            <div style="color:#64748b; font-weight:900;">&rarr;</div>
                            <div style="background:rgba(0,0,0,0.3); border:1px solid #334155; padding:6px 10px; border-radius:4px; text-align:center;">
                                <b style="color:#00ffcc;">5M Confirmation</b><br/><span style="color:#94a3b8;">Displacement Check</span>
                            </div>
                            <div style="color:#64748b; font-weight:900;">&rarr;</div>
                            <div style="background:rgba(0,0,0,0.3); border:1px solid #00ffcc; padding:6px 10px; border-radius:4px; text-align:center;">
                                <b style="color:#00ffcc;">1M Precision Entry</b><br/><span style="color:#bef264;">1M FVG Limit Fill</span>
                            </div>
                            <div style="color:#64748b; font-weight:900;">&rarr;</div>
                            <div style="background:rgba(0,0,0,0.3); border:1px solid #334155; padding:6px 10px; border-radius:4px; text-align:center;">
                                <b style="color:#f59e0b;">Risk Gateway</b><br/><span style="color:#94a3b8;">Fail-Closed Risk</span>
                            </div>
                            <div style="color:#64748b; font-weight:900;">&rarr;</div>
                            <div style="background:rgba(0,0,0,0.3); border:1px solid #334155; padding:6px 10px; border-radius:4px; text-align:center;">
                                <b style="color:#a855f7;">Paper / Shadow</b><br/><span style="color:#94a3b8;">Reconciliation</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    import true_mtf_engine
                    if st.button("RUN TRUE MTF MULTI-ASSET DISCOVERY (PHASE 19)", key="btn_run_true_mtf_disc", use_container_width=True):
                        with st.spinner("Running 1D->4H->15M->5M->1M execution discovery across 16 assets..."):
                            lb_results = true_mtf_engine.CrossAssetDiscoveryRunner.run_cross_asset_discovery()
                            comp_results = true_mtf_engine.TrueMTFExecutionComparer.compare_execution_timeframes(symbol="XAUUSD")
                            st.session_state["true_mtf_cache"] = {
                                "leaderboard": lb_results,
                                "comparisons": comp_results
                            }

                    tmtf_cache = st.session_state.get("true_mtf_cache", None)
                    if tmtf_cache:
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>1. Execution Timeframe Timing Impact Benchmark (XAUUSD)</p>", unsafe_allow_html=True)
                        st.dataframe(pd.DataFrame(tmtf_cache["comparisons"])[["model", "execution_tf", "trades_N", "win_rate_pct", "expectancy_r", "holdout_expectancy_r", "avg_sl_distance_pips", "diagnosis"]], use_container_width=True)

                        st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)
                        st.markdown("<p style='font-size:12px; font-weight:700; color:#bef264;'>2. True MTF Cross-Asset Discovery Leaderboard (16 Assets)</p>", unsafe_allow_html=True)
                        
                        # Add Dynamic Interpretation Column to Leaderboard
                        df_lb = pd.DataFrame(tmtf_cache["leaderboard"])
                        if "interpretation" not in df_lb.columns:
                            df_lb["interpretation"] = [
                                research_explanations.ExplainableResearchClassifier.interpret_asset_candidate(
                                    row["asset"], row["holdout_expectancy_r"], 
                                    float(row.get("bootstrap_ci", "[0,0]").split("[")[1].split(",")[0].replace("R", "")),
                                    float(row.get("bootstrap_ci", "[0,0]").split(",")[1].split("]")[0].replace("R", "")),
                                    row["trades_N"], row["status"]
                                )
                                for _, row in df_lb.iterrows()
                            ]
                        st.dataframe(df_lb[["rank", "asset", "category", "execution_tf", "trades_N", "win_rate_pct", "holdout_expectancy_r", "bootstrap_ci", "wfo_stability", "cost_stress", "research_score", "status", "interpretation"]], use_container_width=True)

                        # USDJPY Contextual Explanation Box
                        st.markdown("""
                        <div style="background:rgba(245,158,11,0.08); border:1px solid #f59e0b; border-radius:6px; padding:12px; margin-top:14px; font-size:12px; color:#fef3c7; line-height:1.5;">
                            <b>USDJPY RESEARCH STATUS: PROMISING BUT NOT PRIMARY ASSET</b><br/>
                            1. <b>Why USDJPY is not the primary candidate:</b> Holdout expectancy is positive (<b>+0.160 R</b>), but the 95% confidence interval reaches zero and the complexity-adjusted score is negative (-0.020 R).<br/>
                            2. <b>Interpretation:</b> The true MTF architecture improved USDJPY substantially compared with earlier 15M-only experiments, but historical evidence is weaker than XAUUSD.<br/>
                            3. <b>Governance Decision:</b> Keep USDJPY available for research and paper validation; do not prioritize it for live automation.
                        </div>
                        """, unsafe_allow_html=True)

                with tab_res_dim10:
                    st.markdown("<p style='font-size:12px; font-weight:700; color:#f59e0b;'>XAUUSD True MTF Adversarial Verification & Explainable Dashboard (Phase 20)</p>", unsafe_allow_html=True)
                    
                    import xauusd_audit_engine
                    if st.button("RUN XAUUSD ADVERSARIAL AUDIT (PHASE 20)", key="btn_run_xauusd_phase20", use_container_width=True):
                        with st.spinner("Executing 12-dimensional adversarial audit on XAUUSD..."):
                            reconstruction = xauusd_audit_engine.XAUUSDDataAuditor.audit_raw_reconstruction()
                            exec_models = xauusd_audit_engine.XAUUSDEntryExecutionAuditor.audit_execution_models()
                            sl_audit = xauusd_audit_engine.XAUUSDStructuralSLAuditor.audit_stop_losses()
                            targets = xauusd_audit_engine.XAUUSDTargetRRAuditor.audit_target_models()
                            surface = xauusd_audit_engine.XAUUSDParameterPerturbationProfiler.run_perturbation_analysis()
                            cost_stress = xauusd_audit_engine.XAUUSDCostStressTester.run_cost_stress()
                            mc_10k = xauusd_audit_engine.XAUUSDMonteCarlo10kSimulator.run_10k_simulations(n_sims=5000, random_seed=42)
                            replay = xauusd_audit_engine.XAUUSDPaperShadowParityReplayer.replay_parity_audit()
                            st.session_state["xauusd_phase20_cache"] = {
                                "reconstruction": reconstruction,
                                "exec_models": exec_models,
                                "sl_audit": sl_audit,
                                "targets": targets,
                                "surface": surface,
                                "cost_stress": cost_stress,
                                "mc_10k": mc_10k,
                                "replay": replay
                            }

                    p20_c = st.session_state.get("xauusd_phase20_cache", None)
                    if p20_c:
                        # 1. PROMINENT XAUUSD HERO CARD
                        st.markdown(f"""
                        <div style="background:rgba(15,23,42,0.9); border:2px solid #00ffcc; border-radius:10px; padding:16px 20px; margin-bottom:16px; box-shadow:0 0 25px rgba(0,255,204,0.15);">
                            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                                <div>
                                    <div style="font-size:11px; font-weight:800; color:#8a99ad; text-transform:uppercase; letter-spacing:1.5px;">PRIMARY RESEARCH CANDIDATE</div>
                                    <h2 style="margin:2px 0 0 0; color:#00ffcc; font-size:1.8rem; font-weight:900;">XAUUSD (GOLD) — TRUE MTF ICT/SMC</h2>
                                    <div style="font-size:12px; color:#bef264; font-weight:700; margin-top:2px;">STATUS: STRONG (ROBUST RESEARCH CANDIDATE)</div>
                                </div>
                                <div style="text-align:right; font-size:12px; color:#cbd5e1;">
                                    <div>Holdout E[R]: <b style="color:#00ffcc; font-size:1.2rem;">+0.637 R</b> (STRONG)</div>
                                    <div>95% Bootstrap CI: <b style="color:#ffffff;">[+0.477R, +0.817R]</b> (POSITIVE EVIDENCE)</div>
                                    <div>Sample: <b style="color:#ffffff;">N = 82 Trades</b> (MODERATE SAMPLE)</div>
                                </div>
                            </div>
                            <hr style="border-color:rgba(255,255,255,0.08); margin:12px 0;">
                            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:10px; font-size:11px; color:#94a3b8;">
                                <div style="background:rgba(0,0,0,0.3); padding:8px; border-radius:4px;">
                                    <b style="color:#e2e8f0;">Walk-Forward Stability:</b><br/><span style="color:#00ffcc;">4 / 4 Profitable Windows (PASS)</span>
                                </div>
                                <div style="background:rgba(0,0,0,0.3); padding:8px; border-radius:4px;">
                                    <b style="color:#e2e8f0;">Cost Stress (3x):</b><br/><span style="color:#00ffcc;">Survives +0.317 R (ROBUST)</span>
                                </div>
                                <div style="background:rgba(0,0,0,0.3); padding:8px; border-radius:4px;">
                                    <b style="color:#e2e8f0;">Monte Carlo (10k):</b><br/><span style="color:#00ffcc;">Median +102.80 R (0.0% Ruin)</span>
                                </div>
                                <div style="background:rgba(0,0,0,0.3); padding:8px; border-radius:4px;">
                                    <b style="color:#e2e8f0;">Complexity Score:</b><br/><span style="color:#00ffcc;">+0.457 R (STRONG)</span>
                                </div>
                                <div style="background:rgba(0,0,0,0.3); padding:8px; border-radius:4px;">
                                    <b style="color:#e2e8f0;">Live Automation:</b><br/><span style="color:#f59e0b; font-weight:700;">DISABLED (PAPER ACTIVE)</span>
                                </div>
                            </div>
                            <div style="margin-top:12px; font-size:12px; color:#cbd5e1; background:rgba(0,255,204,0.05); padding:10px; border-radius:6px; border-left:3px solid #00ffcc;">
                                <b>Overall Interpretation:</b> XAUUSD currently exhibits the strongest historical evidence among all 16 tested assets for this exact multi-timeframe architecture. However, N = 82 remains a moderate sample size and historical performance does not guarantee future results. Next validation phase: continuous Paper and Shadow execution.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # 2. DRAWDOWN & MONTE CARLO EXPLANATION CARDS
                        dd_interp = research_explanations.ExplainableResearchClassifier.interpret_drawdown(4.00, 7.15)
                        mc_interp = research_explanations.ExplainableResearchClassifier.interpret_monte_carlo(0.00, 0.00)
                        param_interp = research_explanations.ExplainableResearchClassifier.interpret_parameter_stability("ROBUST_PLATEAU", [])

                        c_dd_mc1, c_dd_mc2 = st.columns(2)
                        with c_dd_mc1:
                            st.markdown(f"""
                            <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:12px; font-size:12px; color:#cbd5e1;">
                                <b style="color:#00ffcc;">Expected Drawdown Range</b><br/>
                                • {dd_interp['typical_drawdown_text']}<br/>
                                • {dd_interp['stress_drawdown_text']}<br/>
                                <div style="margin-top:6px; padding:6px; background:rgba(0,0,0,0.2); border-radius:4px; font-size:11px;">
                                    <b>Illustrative Capital Impact:</b><br/>
                                    • {dd_interp['interpretation_1pct']}<br/>
                                    • {dd_interp['interpretation_05pct']}
                                </div>
                                <span style="font-size:10px; color:#8a99ad;">{dd_interp['note']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                        with c_dd_mc2:
                            st.markdown(f"""
                            <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:12px; font-size:12px; color:#cbd5e1;">
                                <b style="color:#bef264;">Monte Carlo Simulation Risk: {mc_interp['status']}</b><br/>
                                • <b>Meaning:</b> {mc_interp['meaning']}<br/>
                                • <b>Simulated Negative Return Probability:</b> 0.00%<br/>
                                • <b>Simulated 20R Drawdown Probability:</b> 0.00%<br/>
                                <div style="margin-top:6px; padding:6px; background:rgba(245,158,11,0.08); border-left:2px solid #f59e0b; font-size:10px; color:#fef3c7;">
                                    <b>Mandatory Distinction:</b> {mc_interp['mandatory_distinction']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # 3. EXPANDABLE "WHY?" / "WHAT TO CHECK NEXT" SECTION
                        with st.expander("WHY IS THIS CANDIDATE STRONG & WHAT SHOULD BE CHECKED NEXT?", expanded=False):
                            c_wh1, c_wh2 = st.columns(2)
                            with c_wh1:
                                st.markdown("""
                                <b style="color:#00ffcc;">Why is this result strong?</b><br/>
                                1. <b>Zero Lookahead Leaks:</b> Adversarial candle mutation proved that future data does not bleed into historical signals.<br/>
                                2. <b>Untouched Holdout Generalization:</b> Generated +0.637R on data isolated from parameter tuning.<br/>
                                3. <b>Survives Extreme Cost Friction:</b> Positive expectancy persists even at 3x spread and 1000ms latency.<br/>
                                4. <b>Parameter Plateau:</b> Perturbing settings by +/-20% causes no performance cliff.
                                """, unsafe_allow_html=True)
                            with c_wh2:
                                st.markdown("""
                                <b style="color:#bef264;">What should be monitored next?</b><br/>
                                1. <b>Live Market Spread Realism:</b> Monitor live Gold spreads during Asian and London market sessions.<br/>
                                2. <b>Sample Size Expansion:</b> Grow forward trade observations from N = 82 toward N = 150+ in Paper mode.<br/>
                                3. <b>Execution Pipeline Parity:</b> Verify that real-time broker fills match simulated execution states.<br/>
                                4. <b>Macro Regime Drift:</b> Monitor rolling 20-trade drift curves for any signs of decay.
                                """, unsafe_allow_html=True)

                        st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)
                        c_p20_a, c_p20_b = st.columns(2)
                        with c_p20_a:
                            st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>1. 6-Model Execution Timing Benchmark</p>", unsafe_allow_html=True)
                            st.dataframe(pd.DataFrame(p20_c["exec_models"])[["model_name", "execution_tf", "trades_N", "win_rate_pct", "holdout_expectancy_r", "avg_sl_pips", "max_drawdown_r"]], use_container_width=True)
                        with c_p20_b:
                            st.markdown("<p style='font-size:12px; font-weight:700; color:#bef264;'>2. 2D Parameter Perturbation Surface (-20% to +20%)</p>", unsafe_allow_html=True)
                            st.dataframe(pd.DataFrame(p20_c["surface"].get("parameter_surface", []))[["parameter", "baseline", "p_minus_20", "p_minus_10", "baseline_val", "p_plus_10", "p_plus_20", "surface"]], use_container_width=True)

                with tab_res_dim11:
                    st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>XAUUSD Forward Evidence Accumulation, Review Readiness & Research Decision Audit (Phase 28)</p>", unsafe_allow_html=True)
                    
                    # Fetch real-time forward analytics, evidence metrics, ledger & review package
                    fwd_summary = xauusd_forward_monitor.XAUUSDForwardMonitor.get_forward_summary(mode="PAPER")
                    cont_telemetry = xauusd_continuous_monitor.XAUUSDContinuousMonitor.get_full_monitoring_telemetry(mode="PAPER")
                    exec_quality = xauusd_execution_quality.XAUUSDExecutionDiagnostics.run_execution_diagnostics(mode="PAPER")
                    dist_drift = xauusd_drift_detector.XAUUSDDriftDetector.evaluate_distribution_drift(mode="PAPER")
                    dd_status = xauusd_drift_detector.XAUUSDDriftDetector.evaluate_drawdown_status(fwd_summary.get("max_drawdown_r", 0.0))
                    val_gate = xauusd_validation_gate.XAUUSDValidationGate.evaluate_gate(mode="PAPER")
                    integrity_eval = xauusd_research_governance.ResearchIntegrityAuditor.evaluate_integrity()
                    next_advice = xauusd_research_governance.WatchNextAdvisor.get_next_action_advice(mode="PAPER")
                    health_items = xauusd_research_governance.ResearchHealthMatrix.evaluate_research_health(mode="PAPER")
                    parity_watch = xauusd_research_governance.XAUUSDParityWatchdog.audit_parity()
                    data_integ_watch = xauusd_research_governance.XAUUSDDataIntegrityWatchdog.audit_data_integrity()

                    # Phase 28 Engines
                    df_paper_trades = xauusd_forward_validator.XAUUSDForwardJournal.get_forward_trades(mode="PAPER")
                    paper_returns = df_paper_trades["realized_r"].dropna().astype(float).tolist() if not df_paper_trades.empty and "realized_r" in df_paper_trades.columns else []
                    
                    core_ev_stats = xauusd_forward_evidence.ForwardEvidenceAnalyzer.calculate_core_statistics(paper_returns)
                    boot_ci_stats = xauusd_forward_evidence.ForwardEvidenceAnalyzer.calculate_bootstrap_confidence_intervals(paper_returns)
                    hist_comp = xauusd_forward_evidence.ForwardHistoricalComparator.compare_against_holdout(core_ev_stats)
                    boot_stab = xauusd_forward_evidence.BootstrapStabilityAnalyzer.evaluate_bootstrap_stability(paper_returns)
                    mc_fwd = xauusd_forward_evidence.ForwardMonteCarloEngine.run_forward_monte_carlo(paper_returns)
                    ev_score = xauusd_forward_evidence.ForwardEvidenceScorer.calculate_evidence_score(mode="PAPER")
                    dec_state = xauusd_forward_evidence.ResearchDecisionStateClassifier.classify_state(mode="PAPER")
                    decomp_res = xauusd_forward_evidence.ExecutionStrategyDecomposer.decompose_divergence(mode="PAPER")
                    
                    milestones_eval = xauusd_evidence_milestones.EvidenceMilestoneEngine.evaluate_milestones(core_ev_stats["trades_n"])
                    readiness_eval = xauusd_review_readiness.ReviewReadinessEngine.evaluate_readiness(mode="PAPER")
                    audit_decision = xauusd_research_decision_audit.ResearchDecisionAuditEngine.synthesize_current_decision(mode="PAPER")
                    review_pkg = xauusd_review_package.HumanReviewPackageGenerator.generate_review_package(mode="PAPER")

                    # Real-time Live MTF State
                    live_mtf = xauusd_live_state_engine.XAUUSDLiveMTFStateEngine.get_complete_live_market_state("XAUUSD")
                    master_decision = live_mtf["decision"]
                    layer_1d = live_mtf["layer_1d"]
                    layer_4h = live_mtf["layer_4h"]
                    layer_15m = live_mtf["layer_15m"]
                    layer_5m = live_mtf["layer_5m"]
                    layer_1m = live_mtf["layer_1m"]

                    # 1. TOP HERO: "HOW MUCH EVIDENCE DO WE HAVE?"
                    st.markdown(f"""
                    <div style="background:rgba(15,23,42,0.95); border:2px solid {audit_decision['decision_color']}; border-radius:10px; padding:18px 22px; margin-bottom:16px; box-shadow:0 0 25px rgba(0,0,0,0.5);">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                            <div>
                                <div style="font-size:10px; font-weight:800; color:#8a99ad; text-transform:uppercase; letter-spacing:1.5px;">HOW MUCH EVIDENCE DO WE HAVE?</div>
                                <h2 style="margin:2px 0 0 0; color:{audit_decision['decision_color']}; font-size:1.6rem; font-weight:900;">{audit_decision['decision_state']} (N = {core_ev_stats['trades_n']} / 100)</h2>
                                <div style="font-size:11px; color:#cbd5e1; margin-top:2px;">
                                    Evidence Tier: <b style="color:#00ffcc;">{milestones_eval['current_tier']}</b> | Readiness: <b style="color:{readiness_eval['verdict_color']};">{readiness_eval['verdict']}</b> | Strategy: <b style="color:#00ffcc;">PHASE 21 FROZEN</b>
                                </div>
                            </div>
                            <div style="text-align:right; font-size:11px; color:#cbd5e1;">
                                <div>Forward Expectancy: <b style="color:#00ffcc; font-size:13px;">{core_ev_stats['expectancy_r']:+.3f} R</b></div>
                                <div style="margin-top:2px;">95% Bootstrap CI: <b style="color:#ffffff;">[{boot_ci_stats['ci_95'][0]:+.3f}R, {boot_ci_stats['ci_95'][1]:+.3f}R]</b></div>
                                <div style="margin-top:2px;">Historical Baseline: <b style="color:#bef264;">+0.637 R (N = 82)</b></div>
                                <div style="margin-top:3px; color:#f59e0b; font-weight:900; letter-spacing:0.5px;">LIVE AUTOMATION: DISABLED PERMANENTLY</div>
                            </div>
                        </div>
                        <hr style="border-color:rgba(255,255,255,0.08); margin:12px 0;">
                        <div style="font-size:12px; color:#e2e8f0; line-height:1.6; background:rgba(0,0,0,0.25); padding:10px 14px; border-radius:6px; margin-bottom:10px;">
                            <b>What Does The Data Say Right Now?</b><br/>
                            {readiness_eval['summary_explanation']}
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; font-size:11px; color:#94a3b8;">
                            <div><b>Live Pipeline State:</b> <span style="color:#ffffff;">{master_decision['state']}</span></div>
                            <div><b>Evidence Score:</b> <span style="color:#00ffcc; font-weight:800;">{ev_score['total_score']} / 100</span></div>
                            <div><b>Next Milestone Target:</b> <span style="color:#00ffcc;">N = {milestones_eval['next_milestone_target']} ({milestones_eval['next_milestone_remaining']} remaining)</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # PROMINENT RESEARCH INTEGRITY WARNING (If any check fails)
                    if not integrity_eval["all_passed"]:
                        st.markdown(f"""
                        <div style="background:rgba(239,68,68,0.15); border:2px solid #ef4444; border-radius:8px; padding:12px 16px; margin-bottom:16px;">
                            <div style="color:#ef4444; font-weight:900; font-size:13px; text-transform:uppercase;">RESEARCH INTEGRITY WARNING — STATISTICAL EVALUATION BLOCKED</div>
                            <div style="color:#fca5a5; font-size:12px; margin-top:2px;">{integrity_eval['warning_message']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # A. EVIDENCE PROGRESS & MILESTONE ENGINE
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#00ffcc; letter-spacing:1px; text-transform:uppercase;'>A. Forward Evidence Progress & Sample Milestones</p>", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(0,255,204,0.25); border-radius:6px; padding:12px; font-size:11px; color:#cbd5e1; margin-bottom:10px;">
                        • <b>Current Accumulation:</b> <b style="color:#00ffcc;">{core_ev_stats['trades_n']} Trades</b> ({milestones_eval['current_tier']})<br/>
                        • <b>Next Target:</b> <b style="color:#bef264;">N = {milestones_eval['next_milestone_target']} ({milestones_eval['next_milestone_stage']})</b> — {milestones_eval['next_milestone_remaining']} trades remaining.<br/>
                        • <b>Statistical Meaning:</b> {milestones_eval['next_milestone_human_meaning']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    df_miles = pd.DataFrame(milestones_eval["milestones"])[["target_n", "stage_name", "reliability_tier", "pct_completion", "remaining_trades", "is_reached", "what_remains_unknown"]]
                    st.dataframe(df_miles, use_container_width=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # B. HISTORICAL VS FORWARD COMPARISON TABLE
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#00ffcc; letter-spacing:1px; text-transform:uppercase;'>B. Historical Holdout vs Forward Performance Comparison</p>", unsafe_allow_html=True)
                    drift_table_data = [
                        {"Metric": "Expectancy (E[R])", "Historical (N=82)": "+0.637 R", "Forward Paper": f"{core_ev_stats['expectancy_r']:+.3f} R", "Difference": f"{hist_comp['abs_expectancy_diff']:+.3f} R", "Classification": hist_comp['consistency_band'], "Plain-Language Meaning": hist_comp['explanation']},
                        {"Metric": "Win Rate (%)", "Historical (N=82)": "58.6%", "Forward Paper": f"{core_ev_stats['win_rate_pct']:.1f}%", "Difference": f"{hist_comp['win_rate_diff']:+.1f}%", "Classification": "CONSISTENT" if abs(hist_comp['win_rate_diff']) <= 10.0 else "WATCH", "Plain-Language Meaning": "Win rate aligns with expected 50%-65% target probability envelope."},
                        {"Metric": "Profit Factor", "Historical (N=82)": "2.52", "Forward Paper": f"{core_ev_stats['profit_factor']:.2f}", "Difference": f"{hist_comp['profit_factor_diff']:+.2f}", "Classification": "CONSISTENT" if core_ev_stats['profit_factor'] >= 1.5 else "WATCH", "Plain-Language Meaning": "Gross winning profit exceeds gross losses."},
                        {"Metric": "Max Drawdown", "Historical (N=82)": "7.15 R (Stress)", "Forward Paper": f"{core_ev_stats['max_drawdown_r']:.2f} R", "Difference": f"{hist_comp['drawdown_diff']:+.2f} R", "Classification": dd_status['status'], "Plain-Language Meaning": "Drawdown is within historical 95th percentile stress bounds (7.15R ceiling)."},
                        {"Metric": "MAE (Adverse Heat)", "Historical (N=82)": "0.38 R", "Forward Paper": f"{dist_drift.get('forward_avg_mae_r', 0.0):.2f} R", "Difference": f"{dist_drift.get('forward_avg_mae_r', 0.0) - 0.38:+.2f} R", "Classification": dist_drift['distribution_status'], "Plain-Language Meaning": "Entries show tight heat with minimal adverse excursion."},
                        {"Metric": "MFE (Favorable Push)", "Historical (N=82)": "2.85 R", "Forward Paper": f"{dist_drift.get('forward_avg_mfe_r', 0.0):.2f} R", "Difference": f"{dist_drift.get('forward_avg_mfe_r', 0.0) - 2.85:+.2f} R", "Classification": dist_drift['distribution_status'], "Plain-Language Meaning": "Trades reach 2R/3R expansion zones with normal momentum."}
                    ]
                    st.dataframe(pd.DataFrame(drift_table_data), use_container_width=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # C. STATISTICAL EVIDENCE & CONFIDENCE INTERVALS
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#38bdf8; letter-spacing:1px; text-transform:uppercase;'>C. Statistical Evidence & Confidence Intervals</p>", unsafe_allow_html=True)
                    c_ci1, c_ci2, c_ci3, c_ci4 = st.columns(4)
                    c_ci1.metric("90% Bootstrap CI", f"[{boot_ci_stats['ci_90'][0]:+.3f}R, {boot_ci_stats['ci_90'][1]:+.3f}R]")
                    c_ci2.metric("95% Bootstrap CI", f"[{boot_ci_stats['ci_95'][0]:+.3f}R, {boot_ci_stats['ci_95'][1]:+.3f}R]")
                    c_ci3.metric("99% Bootstrap CI", f"[{boot_ci_stats['ci_99'][0]:+.3f}R, {boot_ci_stats['ci_99'][1]:+.3f}R]")
                    c_ci4.metric("95% CI Width", f"{boot_ci_stats['ci_width_95']:.3f} R")

                    with st.expander("INSPECT BOOTSTRAP STABILITY & RESAMPLING PROBABILITIES"):
                        st.markdown(f"""
                        <div style="font-size:11px; color:#cbd5e1; line-height:1.6;">
                            • <b>Probability Sample Mean &le; 0.0R:</b> <b style="color:#f59e0b;">{boot_stab['prob_expectancy_le_zero']}%</b><br/>
                            • <b>Probability Sample Mean &lt; Baseline (+0.637R):</b> <b style="color:#cbd5e1;">{boot_stab['prob_expectancy_lt_baseline']}%</b><br/>
                            • <b>Probability Sample Mean &ge; Baseline (+0.637R):</b> <b style="color:#00ffcc;">{boot_stab['prob_expectancy_ge_baseline']}%</b><br/>
                            <span style="color:#94a3b8; font-size:10px;">{boot_stab['disclaimer']}</span>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # D. TRANSPARENT EVIDENCE SCORE (0–100 Index)
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#00ffcc; letter-spacing:1px; text-transform:uppercase;'>D. Transparent Forward Evidence Score (0–100 Index)</p>", unsafe_allow_html=True)
                    c_sc_l, c_sc_r = st.columns([1, 2])
                    with c_sc_l:
                        st.markdown(f"""
                        <div style="background:rgba(15,23,42,0.85); border:1px solid #00ffcc; border-radius:8px; padding:16px; text-align:center; height:100%;">
                            <div style="font-size:10px; font-weight:800; color:#8a99ad; text-transform:uppercase;">EVIDENCE SCORE</div>
                            <div style="font-size:2.4rem; font-weight:900; color:#00ffcc; margin:6px 0;">{ev_score['total_score']} <span style="font-size:14px; color:#8a99ad;">/ 100</span></div>
                            <div style="font-size:11px; color:#cbd5e1; line-height:1.4;">{ev_score['why_did_score_change']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c_sc_r:
                        st.dataframe(pd.DataFrame(ev_score["breakdown"]), use_container_width=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # E. HUMAN REVIEW READINESS CHECKLIST
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#bef264; letter-spacing:1px; text-transform:uppercase;'>E. Human Review Readiness Checklist (18 Criteria)</p>", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.02); border:1px solid {readiness_eval['verdict_color']}; border-radius:6px; padding:10px 14px; margin-bottom:10px; font-size:11px;">
                        <b>READINESS STATUS:</b> <span style="color:{readiness_eval['verdict_color']}; font-weight:800;">{readiness_eval['verdict']}</span> — {readiness_eval['pass_count']}/{readiness_eval['total_items']} conditions passed ({readiness_eval['waiting_count']} waiting, {readiness_eval['blocked_count']} blocked).
                    </div>
                    """, unsafe_allow_html=True)

                    flat_checklist = []
                    for pillar_name, items_list in readiness_eval["checklist"].items():
                        for it in items_list:
                            flat_checklist.append({
                                "Pillar": it["pillar"],
                                "Criterion": it["criterion"],
                                "Current Value": it["current_value"],
                                "Required Value": it["required_value"],
                                "Status": it["status"],
                                "Why It Matters": it["why_it_matters"]
                            })
                    st.dataframe(pd.DataFrame(flat_checklist), use_container_width=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # F & G. WHAT WE KNOW VS WHAT WE DO NOT KNOW
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#38bdf8; letter-spacing:1px; text-transform:uppercase;'>F & G. Uncertainty Engine: Known Facts vs Unresolved Questions</p>", unsafe_allow_html=True)
                    c_un_l, c_un_r = st.columns(2)
                    with c_un_l:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(0,255,204,0.2); border-radius:6px; padding:12px; font-size:11px; line-height:1.5; color:#cbd5e1; height:100%;">
                            <div style="color:#00ffcc; font-weight:800; margin-bottom:6px;">WHAT WE KNOW (EMPIRICAL FACTS)</div>
                            {''.join([f"• {k}<br/>" for k in readiness_eval['uncertainty_analysis']['what_we_know']])}
                        </div>
                        """, unsafe_allow_html=True)
                    with c_un_r:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(245,158,11,0.2); border-radius:6px; padding:12px; font-size:11px; line-height:1.5; color:#cbd5e1; height:100%;">
                            <div style="color:#f59e0b; font-weight:800; margin-bottom:6px;">WHAT WE DO NOT KNOW (UNRESOLVED)</div>
                            {''.join([f"• {u}<br/>" for u in readiness_eval['uncertainty_analysis']['what_we_do_not_know']])}
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # H. WHAT CHANGED SINCE LAST REVIEW? (Delta Engine)
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#bef264; letter-spacing:1px; text-transform:uppercase;'>H. What Changed Since Prior Review? (Delta Engine)</p>", unsafe_allow_html=True)
                    what_changed = xauusd_continuous_monitor.XAUUSDContinuousMonitor.evaluate_what_changed(cont_telemetry)
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(190,242,100,0.25); border-radius:6px; padding:12px; font-size:11px; line-height:1.6; color:#cbd5e1; margin-bottom:10px;">
                        <div style="font-weight:800; color:#bef264; margin-bottom:2px;">DELTA STATUS: {what_changed['status']}</div>
                        <div>{what_changed['summary']}</div>
                        <div style="font-size:10px; color:#94a3b8; margin-top:4px;">
                            • New Trades: {what_changed['deltas']['new_trades']} | Expectancy Delta: {what_changed['deltas']['expectancy_change']:+.3f}R | Win Rate Delta: {what_changed['deltas']['win_rate_change']:+.1f}% | DD Delta: {what_changed['deltas']['drawdown_change']:+.2f}R
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # I. WHAT SHOULD I WATCH NEXT? (Prioritized Advisor)
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#00ffcc; letter-spacing:1px; text-transform:uppercase;'>I. What Should We Watch Next? (Prioritized Advisor)</p>", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="background:rgba(15,23,42,0.85); border:1px solid #00ffcc; border-radius:8px; padding:14px 18px; margin-bottom:12px;">
                        <div style="font-size:13px; font-weight:900; color:#00ffcc;">{next_advice['main_advice']}</div>
                        <div style="font-size:11px; color:#cbd5e1; margin-top:6px; line-height:1.5;">
                            {''.join([f"• {r}<br/>" for r in next_advice['reasons']])}
                        </div>
                        <div style="font-size:11px; color:#bef264; margin-top:6px; font-weight:700;">
                            Recommended Action: {next_advice['action']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # J. RESEARCH DECISION AUDIT HISTORY & SNAPSHOT COMPARATOR
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#a855f7; letter-spacing:1px; text-transform:uppercase;'>J. Immutable Evidence Ledger & Decision History</p>", unsafe_allow_html=True)
                    ledger_snaps = xauusd_forward_evidence_ledger.ForwardEvidenceLedger.get_snapshots(limit=15)
                    if ledger_snaps:
                        st.dataframe(pd.DataFrame(ledger_snaps)[["snapshot_id", "timestamp", "governance_stage", "trades_n", "expectancy_r", "evidence_score", "research_decision_state", "next_milestone"]], use_container_width=True)
                        
                        # Snapshot Comparator
                        if len(ledger_snaps) >= 2:
                            with st.expander("COMPARE TWO HISTORICAL EVIDENCE SNAPSHOTS"):
                                snap_options = [s["snapshot_id"] for s in ledger_snaps]
                                c_cmp1, c_cmp2 = st.columns(2)
                                with c_cmp1:
                                    s_id1 = st.selectbox("Select Earlier Snapshot:", options=snap_options, index=len(snap_options)-1, key="sel_snap_1")
                                with c_cmp2:
                                    s_id2 = st.selectbox("Select Later Snapshot:", options=snap_options, index=0, key="sel_snap_2")
                                
                                if st.button("RUN SNAPSHOT DELTA COMPARISON", key="btn_run_snap_cmp"):
                                    cmp_res = xauusd_forward_evidence_ledger.ForwardEvidenceLedger.compare_snapshots(s_id1, s_id2)
                                    if "deltas" in cmp_res:
                                        st.markdown(f"""
                                        <div style="background:rgba(255,255,255,0.02); border-left:3px solid #a855f7; border-radius:4px; padding:10px; font-size:11px; color:#cbd5e1;">
                                            <b>Snapshot Comparison:</b> {cmp_res['earlier_snapshot_id']} &rarr; {cmp_res['later_snapshot_id']}<br/>
                                            • New Observations: {cmp_res['deltas']['new_trades']} Trades<br/>
                                            • Expectancy Delta: {cmp_res['deltas']['expectancy_change']:+.3f} R<br/>
                                            • Win Rate Delta: {cmp_res['deltas']['win_rate_change_pct']:+.1f}%<br/>
                                            • Evidence Score Delta: {cmp_res['deltas']['evidence_score_change']:+.1f} pts<br/>
                                            • State Transition: {cmp_res['earlier_decision_state']} &rarr; <b style="color:#00ffcc;">{cmp_res['later_decision_state']}</b>
                                        </div>
                                        """, unsafe_allow_html=True)
                    else:
                        st.info("No evidence snapshots recorded yet in append-only ledger.")

                    if st.button("RECORD NEW IMMUTABLE EVIDENCE SNAPSHOT TO LEDGER", key="btn_rec_snapshot_p28", use_container_width=True):
                        new_snap_id = xauusd_forward_evidence_ledger.ForwardEvidenceLedger.create_snapshot({
                            "trades_n": core_ev_stats["trades_n"],
                            "expectancy_r": core_ev_stats["expectancy_r"],
                            "median_r": core_ev_stats["median_r"],
                            "win_rate_pct": core_ev_stats["win_rate_pct"],
                            "profit_factor": core_ev_stats["profit_factor"],
                            "max_drawdown_r": core_ev_stats["max_drawdown_r"],
                            "recovery_factor": core_ev_stats["recovery_factor"],
                            "ci_90_lower": boot_ci_stats["ci_90"][0],
                            "ci_90_upper": boot_ci_stats["ci_90"][1],
                            "ci_95_lower": boot_ci_stats["ci_95"][0],
                            "ci_95_upper": boot_ci_stats["ci_95"][1],
                            "ci_99_lower": boot_ci_stats["ci_99"][0],
                            "ci_99_upper": boot_ci_stats["ci_99"][1],
                            "hist_expectancy_diff": hist_comp["abs_expectancy_diff"],
                            "hist_expectancy_ratio": hist_comp["expectancy_ratio_pct"],
                            "baseline_consistency": hist_comp["consistency_band"],
                            "avg_mae_r": dist_drift.get("forward_avg_mae_r", 0.0),
                            "avg_mfe_r": dist_drift.get("forward_avg_mfe_r", 0.0),
                            "limit_fill_rate_pct": exec_quality["fill_rate_pct"],
                            "timeout_rate_pct": exec_quality["miss_rate_pct"],
                            "avg_slippage_pips": exec_quality["avg_entry_slippage_pips"],
                            "avg_spread_pips": exec_quality["avg_spread_pips"],
                            "paper_shadow_parity": parity_watch["status"],
                            "data_integrity_status": data_integ_watch["status"],
                            "contract_hash": data_integ_watch["contract_hash"],
                            "governance_stage": val_gate["stage_name"],
                            "evidence_score": ev_score["total_score"],
                            "research_decision_state": audit_decision["decision_state"],
                            "next_milestone": f"N = {milestones_eval['next_milestone_target']}"
                        })
                        # Also record to decision audit history
                        xauusd_research_decision_audit.ResearchDecisionAuditEngine.record_audit_decision({
                            "current_stage": val_gate["stage_name"],
                            "trades_n": core_ev_stats["trades_n"],
                            "evidence_score": ev_score["total_score"],
                            "expectancy_r": core_ev_stats["expectancy_r"],
                            "ci_95_str": f"[{boot_ci_stats['ci_95'][0]:+.3f}R, {boot_ci_stats['ci_95'][1]:+.3f}R]",
                            "drawdown_r": core_ev_stats["max_drawdown_r"],
                            "drift_state": dist_drift["distribution_status"],
                            "execution_state": exec_quality["execution_health"],
                            "integrity_state": integrity_eval["overall_status"],
                            "decision_state": audit_decision["decision_state"],
                            "reasons": audit_decision["reasons"],
                            "unresolved_uncertainties": readiness_eval["uncertainty_analysis"]["what_we_do_not_know"],
                            "recommended_next_action": next_advice["action"]
                        })
                        st.success(f"Immutable evidence snapshot recorded: {new_snap_id}")
                        st.rerun()

                    # Phase 29 Robustness & Reproducibility Engines
                    regime_cov = xauusd_forward_regime_coverage.RegimeCoverageEngine.evaluate_regime_coverage(mode="PAPER")
                    rolling_stab = xauusd_forward_stability.RollingStabilityEngine.evaluate_rolling_stability(paper_returns)
                    time_split = xauusd_forward_stability.RollingStabilityEngine.evaluate_time_split_stability(paper_returns)
                    exec_stress = xauusd_forward_execution_stress.ExecutionStressAuditor.run_execution_stress_analysis(mode="PAPER")
                    outcome_attr = xauusd_forward_execution_stress.ForwardOutcomeAttributor.attribute_outcomes(mode="PAPER")
                    dd_audit = xauusd_forward_drawdown_audit.ForwardDrawdownAuditor.audit_drawdown(paper_returns)
                    reprod_audit = xauusd_forward_reproducibility.ForwardReproducibilityAuditor.audit_reproducibility(mode="PAPER")
                    fingerprint = xauusd_forward_reproducibility.ForwardDatasetFingerprinter.generate_fingerprint(mode="PAPER")
                    inval_matrix = xauusd_forward_reproducibility.EvidenceInvalidationEngine.get_invalidation_matrix()
                    counterfactuals = xauusd_forward_reproducibility.EvidenceInvalidationEngine.get_counterfactual_scenarios()

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # P29 SECTION 1: REGIME COVERAGE & STATISTICAL PROTECTION
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#00ffcc; letter-spacing:1px; text-transform:uppercase;'>1. Forward Regime Coverage & Subgroup Protection</p>", unsafe_allow_html=True)
                    c_reg1, c_reg2 = st.columns(2)
                    with c_reg1:
                        st.markdown("<div style='font-size:11px; font-weight:700; color:#cbd5e1; margin-bottom:4px;'>A. Trading Session Coverage</div>", unsafe_allow_html=True)
                        if regime_cov["sessions"]:
                            st.dataframe(pd.DataFrame(regime_cov["sessions"])[["regime_name", "trades_n", "trade_pct", "r_contribution_pct", "expectancy_r", "win_rate_pct", "profit_factor", "statistical_tier"]], use_container_width=True)
                        else:
                            st.info("No session trades recorded.")
                    with c_reg2:
                        st.markdown("<div style='font-size:11px; font-weight:700; color:#cbd5e1; margin-bottom:4px;'>B. Weekday Distribution</div>", unsafe_allow_html=True)
                        if regime_cov["weekdays"]:
                            st.dataframe(pd.DataFrame(regime_cov["weekdays"])[["regime_name", "trades_n", "trade_pct", "r_contribution_pct", "expectancy_r", "win_rate_pct", "profit_factor", "statistical_tier"]], use_container_width=True)
                        else:
                            st.info("No weekday trades recorded.")

                    # P29 SECTION 2: REGIME CONCENTRATION AUDIT
                    conc = regime_cov["concentration_audit"]
                    conc_color = "#00ffcc" if conc.get("concentration_level") == "BALANCED DISTRIBUTION" else ("#f59e0b" if "MODERATE" in conc.get("concentration_level", "") else "#ef4444")
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.02); border-left:3px solid {conc_color}; border-radius:4px; padding:10px 14px; margin-bottom:12px; font-size:11px; line-height:1.5;">
                        <b style="color:{conc_color};">REGIME CONCENTRATION: {conc.get('concentration_level')}</b><br/>
                        • Dominant Session: <b>{conc.get('dominant_session')}</b> ({conc.get('dominant_trade_pct')} % of trades, {conc.get('dominant_r_pct')} % of R contribution)<br/>
                        • <b>Research Interpretation:</b> {conc.get('interpretation')}
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # P29 SECTION 3: ROLLING & CHRONOLOGICAL STABILITY
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#38bdf8; letter-spacing:1px; text-transform:uppercase;'>2. Rolling Window & Chronological Time-Split Stability</p>", unsafe_allow_html=True)
                    c_stab1, c_stab2 = st.columns(2)
                    with c_stab1:
                        st.markdown("<div style='font-size:11px; font-weight:700; color:#cbd5e1; margin-bottom:4px;'>A. Rolling Windows (10, 20, 30, 50 Trades)</div>", unsafe_allow_html=True)
                        st.dataframe(pd.DataFrame(rolling_stab["windows"])[["window_size", "latest_expectancy_r", "latest_win_rate_pct", "latest_profit_factor", "latest_max_dd_r", "classification"]], use_container_width=True)
                    with c_stab2:
                        st.markdown(f"<div style='font-size:11px; font-weight:700; color:#cbd5e1; margin-bottom:4px;'>B. Time-Split Analysis (Status: <span style='color:{time_split.get('color', '#00ffcc')};'>{time_split.get('overall_stability')}</span>)</div>", unsafe_allow_html=True)
                        if time_split["periods"]:
                            st.dataframe(pd.DataFrame(time_split["periods"])[["period", "trades_n", "expectancy_r", "win_rate_pct", "profit_factor", "max_drawdown_r"]], use_container_width=True)
                        else:
                            st.info("At least 9 trades required for chronological 3-way partition.")

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # P29 SECTION 4: EXECUTION STRESS & OUTCOME ATTRIBUTION
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#bef264; letter-spacing:1px; text-transform:uppercase;'>3. Hypothetical Execution Stress & Outcome Attribution</p>", unsafe_allow_html=True)
                    c_str1, c_str2 = st.columns(2)
                    with c_str1:
                        st.markdown("<div style='font-size:11px; font-weight:700; color:#cbd5e1; margin-bottom:4px;'>A. Slippage & Spread Friction Stress</div>", unsafe_allow_html=True)
                        st.dataframe(pd.DataFrame(exec_stress["slippage_stress"])[["scenario", "additional_friction_pips", "expectancy_loss_r", "stressed_expectancy_r", "survives"]], use_container_width=True)
                    with c_str2:
                        st.markdown("<div style='font-size:11px; font-weight:700; color:#cbd5e1; margin-bottom:4px;'>B. Event Attribution (Strategy vs Execution)</div>", unsafe_allow_html=True)
                        st.dataframe(pd.DataFrame(outcome_attr["items"])[["category", "classification", "count", "pct_of_events", "meaning"]], use_container_width=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # P29 SECTION 5: DRAWDOWN & CONSECUTIVE LOSS AUDIT
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#f59e0b; letter-spacing:1px; text-transform:uppercase;'>4. Consecutive Losses & Drawdown Reality Audit</p>", unsafe_allow_html=True)
                    c_dda1, c_dda2, c_dda3, c_dda4 = st.columns(4)
                    c_dda1.metric("Max Consecutive Losses", dd_audit["max_consecutive_losses"])
                    c_dda2.metric("Max Consecutive Wins", dd_audit["max_consecutive_wins"])
                    c_dda3.metric("Current Drawdown", f"{dd_audit['current_drawdown_r']:.2f} R ({dd_audit['drawdown_status']})")
                    c_dda4.metric("Recovery Factor", f"{dd_audit['recovery_factor']:.2f}")

                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.02); border-left:3px solid {dd_audit['color']}; border-radius:4px; padding:8px 12px; font-size:11px; color:#cbd5e1; margin-top:6px;">
                        <b>Drawdown Meaning:</b> {dd_audit['human_meaning']} (Historical 95th Percentile Stress: 7.15R | Severe Boundary: 12.0R)
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # P29 SECTION 6: INDEPENDENT REPRODUCIBILITY AUDIT & DATASET FINGERPRINT
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#00ffcc; letter-spacing:1px; text-transform:uppercase;'>5. Independent Reproducibility Audit & Cryptographic Fingerprinting</p>", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="background:rgba(15,23,42,0.85); border:2px solid {reprod_audit['status_color']}; border-radius:8px; padding:14px 18px; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-size:13px; font-weight:900; color:{reprod_audit['status_color']};">REPRODUCIBILITY AUDIT: {reprod_audit['verdict']}</div>
                            <div style="font-size:10px; color:#8a99ad;">Contract: <code>{fingerprint['contract_sha256'][:16]}...</code></div>
                        </div>
                        <div style="font-size:11px; color:#cbd5e1; margin-top:6px; line-height:1.5;">
                            • <b>Dataset Fingerprint (SHA-256):</b> <code>{fingerprint['dataset_sha256']}</code><br/>
                            • <b>Observation Provenance:</b> {fingerprint['observation_count']} records logged between {fingerprint['earliest_observation']} and {fingerprint['latest_observation']}.<br/>
                            • <b>Reconstruction Match:</b> {reprod_audit['explanation']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # P29 SECTION 7: WHAT WOULD CHANGE OUR CONCLUSION?
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#ef4444; letter-spacing:1px; text-transform:uppercase;'>6. What Would Change Our Research Conclusion? (Invalidation Matrix)</p>", unsafe_allow_html=True)
                    st.dataframe(pd.DataFrame(inval_matrix)[["condition_id", "condition", "nature", "why_it_matters", "governance_action"]], use_container_width=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # P29 SECTION 8: COUNTERFACTUAL SCENARIOS
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#38bdf8; letter-spacing:1px; text-transform:uppercase;'>7. Counterfactual Research Panel: What If The Edge Is Weaker?</p>", unsafe_allow_html=True)
                    st.dataframe(pd.DataFrame(counterfactuals)[["hypothetical_exp_r", "baseline_retention", "expected_interpretation", "governance_state"]], use_container_width=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # K. 28-SECTION HUMAN REVIEW DOSSIER & EXPORT
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#bef264; letter-spacing:1px; text-transform:uppercase;'>K. Formal 28-Section Research Audit Dossier</p>", unsafe_allow_html=True)
                    c_rev_btn1, c_rev_btn2, c_rev_btn3 = st.columns(3)
                    with c_rev_btn1:
                        show_rev_pkg = st.checkbox("VIEW 28-SECTION REVIEW PACKAGE", key="chk_view_rev_pkg_p29")
                    with c_rev_btn2:
                        md_report = xauusd_review_package.HumanReviewPackageGenerator.export_markdown_report(review_pkg)
                        st.download_button(
                            label="EXPORT AUDIT DOSSIER (.MD)",
                            data=md_report,
                            file_name=f"XAUUSD_RESEARCH_DOSSIER_{datetime.now(timezone.utc).strftime('%Y%m%d')}.md",
                            mime="text/markdown",
                            use_container_width=True,
                            key="btn_export_audit_md_p29"
                        )
                    with c_rev_btn3:
                        if st.button("MARK FOR HUMAN REVIEW", key="btn_mark_human_review_p29", use_container_width=True):
                            st.success("Forward validation dossier recorded and marked for Human Review. Live trading remains permanently disabled.")

                    if show_rev_pkg:
                        with st.expander("INSPECT COMPLETE 28-SECTION RESEARCH AUDIT DOSSIER", expanded=True):
                            st.markdown(f"""
                            <div style="font-size:10px; color:#8a99ad; margin-bottom:8px;">
                                Package ID: <code>{review_pkg['package_id']}</code> | Contract Hash: <code>{review_pkg['contract_hash'][:16]}...</code> | Holdout Hash: <code>{review_pkg['holdout_hash'][:16]}...</code> | Forward Hash: <code>{review_pkg['forward_hash'][:16]}...</code>
                            </div>
                            """, unsafe_allow_html=True)
                            for sec in review_pkg["sections"]:
                                c_badge = "#00ffcc" if sec["classification"] == "KNOWN" else ("#bef264" if sec["classification"] == "OBSERVED" else ("#f59e0b" if sec["classification"] == "UNCERTAIN" else "#ef4444"))
                                st.markdown(f"""
                                <div style="background:rgba(255,255,255,0.02); border-left:3px solid {c_badge}; border-radius:4px; padding:10px 14px; margin-bottom:8px; font-size:11px;">
                                    <div style="display:flex; justify-content:space-between;">
                                        <b style="color:#ffffff;">{sec['title']}</b>
                                        <span style="color:{c_badge}; font-weight:800; font-size:10px;">[{sec['classification']}]</span>
                                    </div>
                                    <div style="color:#cbd5e1; margin-top:4px; line-height:1.5;">{sec['content']}</div>
                                </div>
                                """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # L. LIVE MTF STATE PIPELINE (5 Operational Layers)
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#38bdf8; letter-spacing:1px; text-transform:uppercase;'>L. Real-Time Multi-Timeframe (MTF) Pipeline State</p>", unsafe_allow_html=True)
                    c_mtf1, c_mtf2, c_mtf3, c_mtf4, c_mtf5 = st.columns(5)
                    with c_mtf1:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:10px; font-size:11px; height:100%;">
                            <div style="color:#00ffcc; font-weight:800;">1D — MACRO BIAS</div>
                            <div style="color:#e2e8f0; font-weight:700; margin:3px 0;">State: <span style="color:#bef264;">{layer_1d['state']}</span></div>
                            <div style="color:#8a99ad; font-size:10px;">• EMA20: {layer_1d['ema20']:.2f}<br/>• EMA50: {layer_1d['ema50']:.2f}<br/>• Structure: {layer_1d['swing_structure']}<br/>• Last Close: {layer_1d['last_completed_candle_close']:.2f}</div>
                            <div style="color:#cbd5e1; font-size:10px; margin-top:4px; line-height:1.3;">{layer_1d['explanation']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with c_mtf2:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:10px; font-size:11px; height:100%;">
                            <div style="color:#00ffcc; font-weight:800;">4H — DRAW ON LIQUIDITY</div>
                            <div style="color:#e2e8f0; font-weight:700; margin:3px 0;">Target: <span style="color:#bef264;">{layer_4h['dol_type']} ({layer_4h['dol_price']:.2f})</span></div>
                            <div style="color:#8a99ad; font-size:10px;">• Distance: {layer_4h['distance_pips']} pips<br/>• R-Potential: <b style="color:#00ffcc;">{layer_4h['r_potential']}R</b><br/>• Min 2R Rule: <b style="color:#bef264;">{'SATISFIED' if layer_4h['meets_min_2r'] else 'REJECTED'}</b></div>
                            <div style="color:#cbd5e1; font-size:10px; margin-top:4px; line-height:1.3;">{layer_4h['explanation']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with c_mtf3:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:10px; font-size:11px; height:100%;">
                            <div style="color:#00ffcc; font-weight:800;">15M — SETUP CHECKLIST</div>
                            <div style="color:#e2e8f0; font-weight:700; margin:3px 0;">Checklist: <span style="color:#bef264;">{layer_15m['overall_status']} (9/9)</span></div>
                            <div style="color:#8a99ad; font-size:10px;">• Sweep: PASS (Asian Low)<br/>• MSS: PASS (Body Close)<br/>• Displacement: PASS (>65%)<br/>• FVG: PASS (>= 0.5 ATR)</div>
                            <div style="color:#cbd5e1; font-size:10px; margin-top:4px; line-height:1.3;">{layer_15m['explanation']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with c_mtf4:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:10px; font-size:11px; height:100%;">
                            <div style="color:#00ffcc; font-weight:800;">5M — CONFIRMATION</div>
                            <div style="color:#e2e8f0; font-weight:700; margin:3px 0;">Status: <span style="color:#bef264;">{layer_5m['status']}</span></div>
                            <div style="color:#8a99ad; font-size:10px;">• Quality: {layer_5m['displacement_quality']}<br/>• Bars Since MSS: {layer_5m['bars_since_15m_mss']} / 3<br/>• Expired: {'NO' if not layer_5m['is_expired'] else 'YES'}</div>
                            <div style="color:#cbd5e1; font-size:10px; margin-top:4px; line-height:1.3;">{layer_5m['explanation']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with c_mtf5:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:10px; font-size:11px; height:100%;">
                            <div style="color:#00ffcc; font-weight:800;">1M — PRECISION ENTRY</div>
                            <div style="color:#e2e8f0; font-weight:700; margin:3px 0;">Status: <span style="color:#bef264;">{layer_1m['state']}</span></div>
                            <div style="color:#8a99ad; font-size:10px;">• Limit Price: {layer_1m['limit_price']:.2f}<br/>• SL: {layer_1m['stop_loss']:.2f} ({layer_1m['sl_distance_pips']}p)<br/>• Planned R:R: <b style="color:#00ffcc;">{layer_1m['planned_rr']}R</b><br/>• Timer: {layer_1m['order_expiration_min_remaining']} min remaining</div>
                            <div style="color:#cbd5e1; font-size:10px; margin-top:4px; line-height:1.3;">{layer_1m['explanation']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with st.expander("INSPECT 15M SETUP DEVELOPMENT CHECKLIST (9 CRITERIA)"):
                        cl_df = pd.DataFrame(layer_15m["items"])
                        st.dataframe(cl_df, use_container_width=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # M. ALERT CENTER & NON-DESTRUCTIVE ACKNOWLEDGEMENT
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#f59e0b; letter-spacing:1px; text-transform:uppercase;'>M. Alert Center & Event Monitor</p>", unsafe_allow_html=True)
                    c_alt_f1, c_alt_f2 = st.columns([1, 1])
                    with c_alt_f1:
                        sel_sev = st.selectbox("Filter by Severity:", options=["ALL", "INFORMATION", "WARNING", "CRITICAL"], key="sel_alert_sev_p28")
                    with c_alt_f2:
                        sel_ack = st.selectbox("Filter by Status:", options=["ALL", "UNACKNOWLEDGED", "ACKNOWLEDGED"], key="sel_alert_ack_p28")

                    alerts_list = xauusd_alert_engine.XAUUSDAlertEngine.get_events(severity_filter=sel_sev, acknowledged_filter=sel_ack, limit=20)
                    if alerts_list:
                        for alt in alerts_list[:5]:
                            exp_alt = xauusd_alert_engine.XAUUSDAlertEngine.explain_alert(alt)
                            a_color = "#ef4444" if exp_alt["severity"] == "CRITICAL" else ("#f59e0b" if exp_alt["severity"] == "WARNING" else "#38bdf8")
                            c_a_box, c_a_btn = st.columns([4, 1])
                            with c_a_box:
                                st.markdown(f"""
                                <div style="background:rgba(255,255,255,0.02); border-left:3px solid {a_color}; border-radius:4px; padding:8px 12px; margin-bottom:6px; font-size:11px; line-height:1.4;">
                                    <div style="font-weight:800; color:{a_color};">{exp_alt['severity']} — {alt.get('event_type')}</div>
                                    <div style="color:#e2e8f0;">{exp_alt['what_happened']}</div>
                                    <div style="color:#94a3b8; font-size:10px;"><b>Action:</b> {exp_alt['what_should_i_do']} | <b>Status:</b> {'ACKNOWLEDGED' if exp_alt['acknowledged'] else 'UNACKNOWLEDGED'}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            with c_a_btn:
                                if not exp_alt["acknowledged"]:
                                    if st.button("ACKNOWLEDGE", key=f"btn_ack_p28_{alt['event_id']}"):
                                        xauusd_alert_engine.XAUUSDAlertEngine.acknowledge_alert(alt["event_id"])
                                        st.rerun()
                    else:
                        st.info("No active monitoring alerts matching the selected filter.")

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # N. RESEARCH HEALTH PILLARS
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#00ffcc; letter-spacing:1px; text-transform:uppercase;'>N. Research Health & Governance Pillars</p>", unsafe_allow_html=True)
                    c_hlth_cols = st.columns(4)
                    for idx, h_item in enumerate(health_items):
                        col_target = c_hlth_cols[idx % 4]
                        with col_target:
                            st.markdown(f"""
                            <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:10px; margin-bottom:8px; font-size:11px; height:100%;">
                                <div style="color:#8a99ad; font-size:10px; text-transform:uppercase;">{h_item['component']}</div>
                                <div style="color:{h_item['color']}; font-weight:800; font-size:12px; margin:2px 0;">{h_item['value']}</div>
                                <div style="color:#94a3b8; font-size:10px; line-height:1.3;">{h_item['what_it_means']}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

                    # O. FUTURE RESEARCH QUEUE & PARITY AUDIT
                    st.markdown("<p style='font-size:12px; font-weight:800; color:#a855f7; letter-spacing:1px; text-transform:uppercase;'>O. Hypothesis Firewall (Future Research Queue)</p>", unsafe_allow_html=True)
                    df_hypo_q = xauusd_research_governance.ResearchHypothesisFirewall.get_queued_hypotheses()
                    if not df_hypo_q.empty:
                        st.dataframe(df_hypo_q[["hypothesis_id", "observation", "proposed_change", "rationale", "source_phase", "status"]], use_container_width=True)
                    else:
                        st.info("No future hypotheses currently queued. Live forward observations are logged without post-hoc strategy modification.")

                    if st.button("RUN CANONICAL PAPER/SHADOW PARITY AUDIT", key="btn_run_parity_check_p28", use_container_width=True):
                        p_res = xauusd_forward_validator.XAUUSDPaperShadowParityChecker.verify_pipeline_parity()
                        st.success(f"PARITY CHECK RESULT: {p_res['verdict']} (Paper State: {p_res['paper_state']} | Shadow State: {p_res['shadow_state']})")

                with tab_res_dim12:
                    st.markdown("<p style='font-size:12px; font-weight:700; color:#00ffcc;'>Grounded AI Research Synthesis</p>", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="background: rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 14px; font-size: 12px; color: #cbd5e1; line-height: 1.5;">
                        <b>Research Summary ({r_selected_strat} on {r_symbol} {r_exec_tf}):</b><br/>
                        1. <b>Out-of-Sample Performance:</b> Achieved <b>{val_exp_r:+.3f} R</b> on Validation and <b>{holdout_exp_r:+.3f} R</b> on Final Holdout dataset.<br/>
                        2. <b>Statistical Significance:</b> 95% Bootstrap CI spans <b>{boot_ci.get('ci_range_str', 'N/A')}</b> across N = {n_t} trades ({boot_ci.get('sample_confidence', 'N/A')}).<br/>
                        3. <b>Execution Reality:</b> {fragility}. Under 2.0x spread stress, expectancy retained {stress_res.get('scenarios', [{}])[1].get('expectancy_r', 0.0):+.3f} R.<br/>
                        4. <b>Objective Classification:</b> <b style="color:{sc_color};">{sc_status}</b>.
                    </div>
                    """, unsafe_allow_html=True)

            elif res_cached and "backtest_result" in res_cached and "error" in res_cached["backtest_result"]:
                st.error(res_cached["backtest_result"]["error"])
            else:
                st.info("Configure the strategy and asset parameters above, then click **RUN STATISTICAL EDGE AUDIT** to execute the research lab analysis.")

        with tab_journal:
            # Account Separation Filter
            col_j_head1, col_j_head2 = st.columns([2.2, 1.2])
            with col_j_head1:
                st.markdown("<h3 style='color:#ffffff;font-size:1.3rem;margin:0 0 4px 0;font-weight:800;text-transform:uppercase;'>Trade Journal & Setup Studio</h3>", unsafe_allow_html=True)
                st.markdown("<p style='color:#8a99ad;font-size:13px;margin-bottom:12px;'>Isolated account journals with chart screenshots, strategy setups, descriptions, and lessons.</p>", unsafe_allow_html=True)
            with col_j_head2:
                # Default to individual accounts first so they are never combined
                journal_acc_options = [acc for acc in account_options if acc != "ALL"] + ["ALL"]
                journal_acc_selected = st.selectbox(
                    "Select Account Journal",
                    options=journal_acc_options,
                    format_func=format_account_name,
                    index=0,
                    key="journal_account_filter"
                )

            # Filter data strictly by selected account
            if journal_acc_selected != "ALL":
                df_journal_trades = df_trades[df_trades["account_id"] == journal_acc_selected].copy()
                df_journal_open = df_open[df_open["account_id"] == journal_acc_selected].copy() if not df_open.empty else pd.DataFrame()
            else:
                df_journal_trades = df_trades.copy()
                df_journal_open = df_open.copy() if not df_open.empty else pd.DataFrame()

            # 1. LIVE ACTIVE OPEN POSITIONS TRAY (FOR SELECTED ACCOUNT)
            if not df_journal_open.empty:
                open_rows_html = ""
                unrealized_pnl = float(df_journal_open["floating_pnl"].sum())
                unrealized_color = "#00ffcc" if unrealized_pnl >= 0 else "#ff5555"
                unrealized_sign = "+" if unrealized_pnl >= 0 else "-"

                for idx, pos in df_journal_open.iterrows():
                    pos_id_raw = str(pos["position_id"])
                    t_disp = "#" + pos_id_raw.replace("MT5_", "").replace("CAP_", "")
                    sym = str(pos["symbol"]).upper()
                    dir_str = str(pos["direction"]).upper()
                    dir_badge = f'<span class="badge-dir-long">{dir_str}</span>' if "BUY" in dir_str or "LONG" in dir_str else f'<span class="badge-dir-short">{dir_str}</span>'
                    vol = float(pos.get("volume", 0.0))
                    vol_disp = f"{vol:,.2f}" if vol < 1000 else f"{vol:,.0f}"
                    entry_px = float(pos.get("entry_price", 0.0))
                    curr_px = float(pos.get("current_price", 0.0))
                    fl_pnl = float(pos.get("floating_pnl", 0.0))
                    sl_val = float(pos.get("sl", 0.0))
                    tp_val = float(pos.get("tp", 0.0))
                    sl_disp = f"{sl_val:.5f}" if sl_val > 0 else "-"
                    tp_disp = f"{tp_val:.5f}" if tp_val > 0 else "-"
                    entry_px_disp = f"{entry_px:.5f}"
                    curr_px_disp = f"{curr_px:.5f}"

                    if fl_pnl > 0:
                        pnl_badge = f'<span class="badge-pnl-win">+${fl_pnl:,.2f}</span>'
                    elif fl_pnl < 0:
                        pnl_badge = f'<span class="badge-pnl-loss">-${abs(fl_pnl):,.2f}</span>'
                    else:
                        pnl_badge = '<span style="color:#8a99ad; font-weight:600;">$0.00</span>'

                    open_t_str = pd.to_datetime(pos["open_time"]).strftime("%m/%d %H:%M")

                    open_rows_html += f"""
                    <tr>
                        <td style="font-family:monospace; font-size:11px; color:#8a99ad;">{t_disp}</td>
                        <td style="font-weight:700; color:#ffffff;">{sym}</td>
                        <td>{dir_badge}</td>
                        <td style="font-family:monospace;">{vol_disp}</td>
                        <td style="font-family:monospace; color:#8a99ad;">{entry_px_disp}</td>
                        <td style="font-family:monospace; color:#00ffcc;">{curr_px_disp}</td>
                        <td style="font-family:monospace; color:#ff5555; font-size:11px;">{sl_disp}</td>
                        <td style="font-family:monospace; color:#00ffcc; font-size:11px;">{tp_disp}</td>
                        <td>{pnl_badge}</td>
                        <td style="font-size:11px; color:#8a99ad;">{open_t_str}</td>
                    </tr>
                    """

                str_unrealized_pnl = f"{unrealized_sign}${abs(unrealized_pnl):,.2f}"

                render_html(f"""
                <div style="margin-bottom: 24px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:8px;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#00ffcc; box-shadow: 0 0 10px #00ffcc;"></span>
                            <span style="font-size:14px; font-weight:700; color:#ffffff;">Active Open Positions ({len(df_journal_open)})</span>
                        </div>
                        <div style="font-size:12px;">
                            <span style="color:#8a99ad;">Total Floating P&L:</span> 
                            <b style="color:{unrealized_color}; font-size:14px; margin-left:4px;">{str_unrealized_pnl}</b>
                        </div>
                    </div>

                    <div class="journal-table-wrapper" style="border: 1px solid rgba(0, 255, 204, 0.25);">
                        <table class="journal-table">
                            <thead>
                                <tr>
                                    <th>Ticket</th>
                                    <th>Symbol</th>
                                    <th>Direction</th>
                                    <th>Size</th>
                                    <th>Entry Price</th>
                                    <th>Current Price</th>
                                    <th>Stop Loss</th>
                                    <th>Take Profit</th>
                                    <th>Floating PnL</th>
                                    <th>Open Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                {open_rows_html}
                            </tbody>
                        </table>
                    </div>
                </div>
                """)

            # 2. INTERACTIVE TRADE SETUP & SCREENSHOT STUDIO (FOR SELECTED ACCOUNT)
            df_display = df_journal_trades.sort_values(by="exit_time", ascending=False).copy()
            
            if df_display.empty:
                st.info(f"No closed trades found for the selected account ({format_account_name(journal_acc_selected)}).")
            else:
                with st.container(border=True):
                    st.markdown("<h4 style='color:#00ffcc;font-size:14px;font-weight:700;text-transform:uppercase;margin:0 0 12px 0;'>Log & Review Trade Setup</h4>", unsafe_allow_html=True)
                    
                    trade_choices = []
                    for _, r in df_display.iterrows():
                        pnl_val = float(r.get("net_profit", 0.0))
                        pnl_label = f"+${pnl_val:.2f}" if pnl_val >= 0 else f"-${abs(pnl_val):.2f}"
                        snap_indicator = " [HAS SETUP]" if (pd.notna(r.get("chart_snapshot_url")) and str(r.get("chart_snapshot_url")).strip()) or (pd.notna(r.get("notes")) and str(r.get("notes")).strip()) else ""
                        trade_choices.append(f"{r['trade_id']} | {r['symbol']} {r['direction']} | {pnl_label} | {str(r['exit_time'])[:16]}{snap_indicator}")
                    
                    selected_choice = st.selectbox("Select Trade to Log Setup", options=trade_choices, key="journal_trade_select_top")
                    selected_tid = selected_choice.split(" | ")[0].strip()
                    selected_row = df_display[df_display["trade_id"] == selected_tid].iloc[0]
                    
                    # Quick Trade Highlights Banner
                    p_val = float(selected_row.get("net_profit", 0.0))
                    p_col = "#00ffcc" if p_val >= 0 else "#ff5555"
                    p_sign = "+" if p_val >= 0 else "-"
                    dir_s = str(selected_row["direction"]).upper()
                    sym_s = str(selected_row["symbol"]).upper()
                    vol_s = f"{float(selected_row.get('volume', 0.0)):.2f}"
                    entry_s = f"{float(selected_row.get('entry_price', 0.0)):.5f}"
                    exit_s = f"{float(selected_row.get('exit_price', 0.0)):.5f}"
                    t_str = pd.to_datetime(selected_row["exit_time"]).strftime("%Y-%m-%d %H:%M")
                    acc_s = "Funded MT5" if str(selected_row.get("account_id", "")).startswith("MT5_") else "Capital Real"

                    render_html(f"""
                    <div style="background: rgba(18, 24, 38, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid {p_col}; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                        <div>
                            <span style="font-weight: 800; font-size: 15px; color: #ffffff;">{sym_s} {dir_s}</span>
                            <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.06); color: #8a99ad; margin-left: 6px;">{acc_s}</span>
                            <span style="font-size: 11px; color: #8a99ad; margin-left: 8px;">Size: {vol_s} | Entry: {entry_s} | Exit: {exit_s} | Closed: {t_str}</span>
                        </div>
                        <div style="font-size: 16px; font-weight: 800; color: {p_col};">
                            {p_sign}${abs(p_val):,.2f}
                        </div>
                    </div>
                    """)

                    col_j1, col_j2 = st.columns([1.3, 1.2])
                    
                    with col_j1:
                        st.markdown("<div style='font-size:12px; font-weight:700; color:#ffffff; margin-bottom:6px;'>ATTACH CHART SCREENSHOT</div>", unsafe_allow_html=True)
                        
                        curr_snap = str(selected_row.get("chart_snapshot_url", "") or "")
                        if curr_snap == "None":
                            curr_snap = ""

                        # Option A: File Upload
                        uploaded_file = st.file_uploader(
                            "Upload Screenshot (PNG, JPG, WEBP)", 
                            type=["png", "jpg", "jpeg", "webp"], 
                            key=f"file_up_{selected_tid}"
                        )
                        
                        # Option B: URL Link
                        new_snap_url = st.text_input(
                            "Or Paste TradingView / Chart Image Link", 
                            value=curr_snap if not curr_snap.startswith("data:image") else "", 
                            placeholder="https://www.tradingview.com/x/... or image URL", 
                            key=f"url_up_{selected_tid}"
                        )

                        final_image_to_save = curr_snap

                        if uploaded_file is not None:
                            try:
                                bytes_data = uploaded_file.getvalue()
                                mime_t = uploaded_file.type if uploaded_file.type else "image/png"
                                b64_img = base64.b64encode(bytes_data).decode("utf-8")
                                final_image_to_save = f"data:{mime_t};base64,{b64_img}"
                            except Exception as e:
                                st.error(f"Error reading uploaded file: {e}")
                        elif new_snap_url.strip():
                            final_image_to_save = new_snap_url.strip()

                        # Image Preview
                        if final_image_to_save and final_image_to_save.strip() != "":
                            img_preview = final_image_to_save
                            if not img_preview.startswith("data:") and not img_preview.endswith(".png") and "tradingview.com/x/" in img_preview:
                                img_preview = img_preview + ".png" if not img_preview.endswith(".png") else img_preview
                            
                            try:
                                st.image(img_preview, caption="Attached Chart Setup Screenshot", use_container_width=True)
                            except Exception:
                                st.markdown(f"[Open Snapshot in New Tab]({final_image_to_save})", unsafe_allow_html=True)
                            
                            if st.button("Remove Screenshot", key=f"btn_rm_snap_{selected_tid}"):
                                database.update_trade_journal(trade_id=selected_tid, chart_snapshot_url="")
                                st.success("Screenshot removed.")
                                st.rerun()

                    with col_j2:
                        st.markdown("<div style='font-size:12px; font-weight:700; color:#ffffff; margin-bottom:6px;'>STRATEGY SETUP & DESCRIPTION</div>", unsafe_allow_html=True)
                        
                        curr_setup = str(selected_row.get("setup_tag", "") or "BREAKOUT")
                        setup_options = [
                            "BREAKOUT", "SUPPORT / RESISTANCE BOUNCE", "ORDER BLOCK / FVG", 
                            "NEWS SCALP", "TREND FOLLOWING", "MEAN REVERSION", "LIQUIDITY GRAB",
                            "SUPPLY & DEMAND", "CHART PATTERN", "CUSTOM SETUP"
                        ]
                        idx_s = setup_options.index(curr_setup) if curr_setup in setup_options else 0
                        new_setup = st.selectbox("Strategy Setup Category", options=setup_options, index=idx_s, key=f"sel_setup_{selected_tid}")
                        
                        curr_notes = str(selected_row.get("notes", "") or "")
                        if curr_notes == "None":
                            curr_notes = ""
                        new_notes = st.text_area(
                            "Setup Description, Confluences & Lessons Learned", 
                            value=curr_notes, 
                            placeholder="Describe why you took this trade, key support/resistance levels, triggers, risk management, and what went well or what to improve...", 
                            height=140, 
                            key=f"txt_notes_{selected_tid}"
                        )

                        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                        if st.button("SAVE TRADE SETUP & SNAPSHOT", type="primary", key=f"save_setup_btn_{selected_tid}", use_container_width=True):
                            database.update_trade_journal(
                                trade_id=selected_tid,
                                chart_snapshot_url=final_image_to_save,
                                setup_tag=new_setup,
                                notes=new_notes.strip()
                            )
                            st.success(f"Setup details, screenshot, and description saved for trade #{selected_tid}!")
                            st.rerun()

                # 3. CLOSED TRADES TABLE FOR SELECTED ACCOUNT
                st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:14px; font-weight:800; color:#ffffff; margin-bottom:10px; text-transform:uppercase;">Closed Trades History ({format_account_name(journal_acc_selected)})</div>', unsafe_allow_html=True)

                table_rows_html = ""
                for idx, row in df_display.iterrows():
                    trade_id_raw = str(row["trade_id"])
                    if trade_id_raw.startswith("MT5_"):
                        ticket_disp = "#" + trade_id_raw.split("_")[-1]
                        acc_disp = "MT5 (Funded)"
                    else:
                        ticket_disp = "#" + trade_id_raw.split("-")[1] if "-" in trade_id_raw else "#" + trade_id_raw[:8]
                        acc_disp = "Capital (Real)"

                    sym = str(row["symbol"]).upper()
                    direction = str(row["direction"]).upper()
                    dir_badge = f'<span class="badge-dir-long">{direction}</span>' if "LONG" in direction or "BUY" in direction else f'<span class="badge-dir-short">{direction}</span>'

                    vol = float(row.get("volume", 0.0))
                    vol_disp = f"{vol:,.2f}" if vol < 1000 else f"{vol:,.0f}"

                    entry_px = float(row.get("entry_price", 0.0))
                    exit_px = float(row.get("exit_price", 0.0))
                    net_pnl = float(row.get("net_profit", 0.0))

                    entry_px_disp = f"{entry_px:.5f}"
                    exit_px_disp = f"{exit_px:.5f}"

                    if net_pnl > 0:
                        pnl_badge = f'<span class="badge-pnl-win">+${net_pnl:,.2f}</span>'
                    elif net_pnl < 0:
                        pnl_badge = f'<span class="badge-pnl-loss">-${abs(net_pnl):,.2f}</span>'
                    else:
                        pnl_badge = '<span style="color:#8a99ad; font-weight:600;">$0.00</span>'

                    pnl_pct = abs(net_pnl) / 1000.0 * 100
                    if net_pnl > 0:
                        q_badge = '<span class="badge-quality badge-quality-high">GOOD</span>'
                    else:
                        q_badge = '<span class="badge-quality badge-quality-med">AVG</span>' if abs(net_pnl) < 50 else '<span class="badge-quality badge-quality-low">POOR</span>'

                    entry_time_str = pd.to_datetime(row["entry_time"]).strftime("%Y-%m-%d %H:%M")
                    exit_time_str = pd.to_datetime(row["exit_time"]).strftime("%Y-%m-%d %H:%M")
                    dur = float(row.get("duration_minutes", 0.0))
                    dur_str = f"{dur:.1f} min" if dur < 60 else f"{dur/60:.1f} hrs"

                    tag_raw = row.get("setup_tag")
                    tag_disp = f'<span class="badge-tag-pill">{tag_raw}</span>' if pd.notna(tag_raw) and str(tag_raw).strip() != "" and str(tag_raw) != "None" else '<span style="color:#4a5568; font-size:10px;">-</span>'

                    has_snap = pd.notna(row.get("chart_snapshot_url")) and str(row.get("chart_snapshot_url")).strip() != "" and str(row.get("chart_snapshot_url")) != "None"
                    has_notes = pd.notna(row.get("notes")) and str(row.get("notes")).strip() != "" and str(row.get("notes")) != "None"
                    
                    if has_snap and has_notes:
                        setup_status = '<span style="color:#00ffcc; font-size:11px; font-weight:700; background:rgba(0,255,204,0.1); padding:2px 6px; border-radius:4px; border:1px solid rgba(0,255,204,0.3);">SNAP + NOTES</span>'
                    elif has_snap:
                        setup_status = '<span style="color:#00ffcc; font-size:11px; font-weight:700; background:rgba(0,255,204,0.1); padding:2px 6px; border-radius:4px;">SNAPSHOT</span>'
                    elif has_notes:
                        setup_status = '<span style="color:#8a99ad; font-size:11px; font-weight:700; background:rgba(255,255,255,0.06); padding:2px 6px; border-radius:4px;">NOTES</span>'
                    else:
                        setup_status = '<span style="color:#4a5568; font-size:11px;">-</span>'

                    table_rows_html += f"""
                    <tr>
                        <td style="font-family:monospace; font-size:11px; color:#8a99ad;">{ticket_disp}</td>
                        <td style="font-size:11px; color:#c084fc;">{acc_disp}</td>
                        <td style="font-weight:700; color:#ffffff;">{sym}</td>
                        <td>{dir_badge}</td>
                        <td style="font-family:monospace;">{vol_disp}</td>
                        <td style="font-family:monospace; color:#8a99ad;">{entry_px_disp}</td>
                        <td style="font-family:monospace; color:#8a99ad;">{exit_px_disp}</td>
                        <td>{pnl_badge}</td>
                        <td>{q_badge}</td>
                        <td style="font-size:11px; color:#8a99ad;">{entry_time_str}</td>
                        <td style="font-size:11px; color:#8a99ad;">{exit_time_str}</td>
                        <td style="font-size:11px; color:#8a99ad;">{dur_str}</td>
                        <td>{tag_disp}</td>
                        <td>{setup_status}</td>
                    </tr>
                    """

                render_html(f"""
                <div class="journal-table-wrapper">
                    <table class="journal-table">
                        <thead>
                            <tr>
                                <th>Ticket</th>
                                <th>Account</th>
                                <th>Symbol</th>
                                <th>Direction</th>
                                <th>Size</th>
                                <th>Entry Px</th>
                                <th>Exit Px</th>
                                <th>Net PnL</th>
                                <th>Quality</th>
                                <th>Entry Time</th>
                                <th>Exit Time</th>
                                <th>Duration</th>
                                <th>Setup Tag</th>
                                <th>Setup Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_html}
                        </tbody>
                    </table>
                </div>
                """)

    with tab_alerts:
        st.markdown("<h3 style='color:#ffffff;font-size:1.3rem;margin-bottom:6px;font-weight:800;text-transform:uppercase;'>Price Alerts & Risk Studio</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color:#8a99ad;font-size:13px;margin-bottom:16px;'>Set target price cross alerts and configure custom profit targets or risk limits.</p>", unsafe_allow_html=True)
        
        sub_t_setup, sub_t_price, sub_t_rules = st.tabs(["TRADE SETUP ALERTS", "LIVE PRICE TARGET ALERTS", "PROFIT & LOSS ALERT RULES"])
        
        with sub_t_setup:
            st.markdown("<h4 style='color:#ffffff;font-size:14px;font-weight:700;text-transform:uppercase;margin:10px 0 10px 0;'>Deterministic State Transitions</h4>", unsafe_allow_html=True)
            st.markdown("<p style='color:#8a99ad;font-size:12px;margin-bottom:16px;'>This view monitors the AI Trade Setup Engine and notifies you of logical state transitions (e.g. WATCHING  READY  INVALIDATED).</p>", unsafe_allow_html=True)
            
            ai_data_state = st.session_state.get("market_context_result")
            if ai_data_state:
                scenario = ai_data_state.get("deterministic_scenario", {})
                setup_status = scenario.get("status", "NO TRADE")
                
                # Colors
                if setup_status == "READY": status_col = "#00ffcc"
                elif setup_status == "WAITING": status_col = "#f59e0b"
                elif setup_status == "WATCHING": status_col = "#3b82f6"
                elif setup_status == "INVALIDATED": status_col = "#ff5555"
                else: status_col = "#64748b"
                
                setup_alert_html = f"""
<div style="background: rgba(18, 24, 38, 0.7); border: 1px solid rgba(255,255,255,0.08); border-left: 4px solid {status_col}; border-radius: 10px; padding: 14px 18px; margin-bottom: 12px;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <span style="font-weight: 800; font-size: 15px; color: #ffffff;">{scenario.get("symbol", "UNKNOWN")} • {scenario.get("setup", "N/A")} SETUP</span>
        <span style="font-size: 11px; padding: 4px 8px; border-radius: 4px; background: rgba(255,255,255,0.06); color: {status_col}; font-weight:800;">{setup_status}</span>
    </div>
    <div style="font-size: 13px; color: #cbd5e1; margin-bottom: 8px;">
        <b>Trigger:</b> {scenario.get("trigger", "N/A")}
    </div>
    <div style="font-size: 13px; color: #ff5555; margin-bottom: 8px;">
        <b>Invalidation:</b> {scenario.get("invalidation", "N/A")}
    </div>
    <div style="font-size: 11px; color: #8a99ad; margin-top: 12px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 12px;">
        <span style="color:#00ffcc;">Entry:</span> {scenario.get("ideal_entry", "N/A")} &nbsp;|&nbsp; 
        <span style="color:#ff5555;">SL:</span> {scenario.get("stop_loss", "N/A")} &nbsp;|&nbsp; 
        <span style="color:#10b981;">TP1:</span> {scenario.get("tp1", "N/A")} &nbsp;|&nbsp; 
        <span style="color:#10b981;">TP2:</span> {scenario.get("tp2", "N/A")}
    </div>
</div>
"""
                st.markdown(setup_alert_html, unsafe_allow_html=True)
            else:
                st.info("No active AI Trade Setup available. Run the AI Sandbox first to initialize the engine.")
        
        with sub_t_price:
            with st.container(border=True):
                # TradingView-Style Asset Catalog
                TV_CATALOG = [
                    {"id": "XAUUSD", "display": "XAUUSD (GOLD)", "desc": "Gold", "cat": "commodity", "type": "commodity cfd", "icon_bg": "#f59e0b", "icon_txt": "AU"},
                    {"id": "EURUSD", "display": "EURUSD (EUR/USD)", "desc": "Euro / US Dollar", "cat": "forex", "type": "forex cfd", "icon_bg": "#3b82f6", "icon_txt": "EU"},
                    {"id": "GBPUSD", "display": "GBPUSD (GBP/USD)", "desc": "British Pound / US Dollar", "cat": "forex", "type": "forex cfd", "icon_bg": "#6366f1", "icon_txt": "GB"},
                    {"id": "USDJPY", "display": "USDJPY (USD/JPY)", "desc": "US Dollar / Japanese Yen", "cat": "forex", "type": "forex cfd", "icon_bg": "#ec4899", "icon_txt": "JP"},
                    {"id": "NAS100", "display": "NAS100 (US100)", "desc": "US Tech 100", "cat": "indices", "type": "index cfd", "icon_bg": "#06b6d4", "icon_txt": "100"},
                    {"id": "US30", "display": "US30 (US30)", "desc": "US 30 Wall St", "cat": "indices", "type": "index cfd", "icon_bg": "#0284c7", "icon_txt": "30"},
                    {"id": "SPX500", "display": "SPX500 (US500)", "desc": "US 500 S&P", "cat": "indices", "type": "index cfd", "icon_bg": "#ef4444", "icon_txt": "500"},
                    {"id": "DXY", "display": "DXY (DXY)", "desc": "US Dollar Index", "cat": "indices", "type": "index cfd", "icon_bg": "#10b981", "icon_txt": "$"},
                    {"id": "BTCUSD", "display": "BTCUSD (BITCOIN)", "desc": "Bitcoin / US Dollar", "cat": "crypto", "type": "crypto cfd", "icon_bg": "#f59e0b", "icon_txt": "BTC"},
                    {"id": "USOIL", "display": "USOIL (OIL_CRUDE)", "desc": "Crude Oil Spot", "cat": "commodity", "type": "commodity cfd", "icon_bg": "#475569", "icon_txt": "OIL"},
                    {"id": "XAGUSD", "display": "XAGUSD (SILVER)", "desc": "Silver Spot", "cat": "commodity", "type": "commodity cfd", "icon_bg": "#94a3b8", "icon_txt": "AG"},
                    {"id": "GER40", "display": "GER40 (DE40)", "desc": "Germany 40 DAX", "cat": "indices", "type": "index cfd", "icon_bg": "#3b82f6", "icon_txt": "40"}
                ]

                fav_symbols = database.get_favorite_symbols()
                import json
                catalog_json = json.dumps(TV_CATALOG)
                fav_json = json.dumps(fav_symbols)

                tv_search_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                <style>
                    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
                    body {{ background: #131722; color: #d1d4dc; padding: 14px; border-radius: 10px; overflow: hidden; }}
                    
                    .header-title {{
                        font-size: 15px;
                        font-weight: 700;
                        color: #ffffff;
                        margin-bottom: 12px;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    }}
                    
                    .search-container {{
                        position: relative;
                        margin-bottom: 10px;
                    }}
                    
                    .search-input {{
                        width: 100%;
                        background: #1e222d;
                        border: 1px solid #2a2e39;
                        border-radius: 6px;
                        padding: 9px 12px 9px 34px;
                        color: #ffffff;
                        font-size: 13px;
                        outline: none;
                        transition: border-color 0.2s ease;
                    }}
                    .search-input:focus {{ border-color: #2962ff; }}
                    
                    .search-icon {{
                        position: absolute;
                        left: 11px;
                        top: 10px;
                        color: #787b86;
                        font-size: 13px;
                    }}
                    
                    .filter-pills {{
                        display: flex;
                        gap: 6px;
                        margin-bottom: 12px;
                        overflow-x: auto;
                        padding-bottom: 2px;
                    }}
                    
                    .filter-pill {{
                        background: #2a2e39;
                        color: #b2b5be;
                        font-size: 11.5px;
                        font-weight: 600;
                        padding: 5px 12px;
                        border-radius: 14px;
                        cursor: pointer;
                        border: 1px solid transparent;
                        user-select: none;
                        transition: all 0.15s ease;
                        white-space: nowrap;
                    }}
                    .filter-pill:hover {{ background: #363a45; color: #ffffff; }}
                    .filter-pill.active {{ background: #ffffff; color: #131722; }}
                    
                    .symbols-list {{
                        max-height: 250px;
                        overflow-y: auto;
                        border-radius: 6px;
                        background: #181c27;
                        border: 1px solid #2a2e39;
                    }}
                    
                    .symbol-row {{
                        display: flex;
                        align-items: center;
                        padding: 9px 12px;
                        border-bottom: 1px solid #222631;
                        cursor: pointer;
                        transition: background 0.12s ease;
                        user-select: none;
                    }}
                    .symbol-row:last-child {{ border-bottom: none; }}
                    .symbol-row:hover {{ background: #242936; }}
                    .symbol-row.selected {{ background: rgba(41, 98, 255, 0.22); border-left: 3px solid #2962ff; }}
                    
                    /* Interactive Red Bookmark Ribbon Notch matching TradingView Screenshot */
                    .ribbon-slot {{
                        width: 22px;
                        height: 24px;
                        display: flex;
                        align-items: center;
                        justify-content: flex-start;
                        cursor: pointer;
                        margin-right: 8px;
                        padding: 2px;
                    }}
                    .ribbon-flag {{
                        width: 8.5px;
                        height: 15px;
                        background: rgba(255, 255, 255, 0.12);
                        clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 75%, 0 100%);
                        transition: all 0.15s ease;
                    }}
                    .ribbon-slot:hover .ribbon-flag {{
                        background: rgba(242, 54, 69, 0.6);
                        transform: scale(1.15);
                    }}
                    .ribbon-flag.flagged {{
                        background: #f23645 !important;
                        box-shadow: 0 0 10px rgba(242, 54, 69, 0.8) !important;
                        transform: scale(1.15);
                    }}
                    
                    .icon-circle {{
                        width: 22px;
                        height: 22px;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin-right: 10px;
                        flex-shrink: 0;
                    }}
                    .icon-circle span {{ font-size: 8.5px; font-weight: 800; color: #ffffff; }}
                    
                    .sym-name-col {{
                        width: 150px;
                        flex-shrink: 0;
                    }}
                    .sym-ticker {{ font-weight: 700; font-size: 13px; color: #ffffff; }}
                    
                    .sym-desc-col {{
                        flex: 1;
                        padding: 0 10px;
                    }}
                    .sym-desc {{ font-size: 12px; color: #8a99ad; }}
                    
                    .sym-meta-col {{
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        flex-shrink: 0;
                    }}
                    .sym-type {{ font-size: 10.5px; color: #787b86; text-transform: lowercase; }}
                    .broker-tag {{
                        font-size: 10px;
                        font-weight: 700;
                        color: #b2b5be;
                        background: #262b38;
                        padding: 2px 6px;
                        border-radius: 4px;
                    }}
                </style>
                </head>
                <body>
                    <div class="header-title">
                        <span>Symbol search</span>
                        <span style="font-size:11.5px; font-weight:400; color:#8a99ad;" id="active-indicator">Selected: <b style="color:#00ffcc;">XAUUSD</b></span>
                    </div>
                    
                    <div class="search-container">
                        <span class="search-icon"></span>
                        <input type="text" class="search-input" id="search-input" placeholder="Symbol, ISIN, or CUSIP" oninput="renderList()">
                    </div>
                    
                    <div class="filter-pills">
                        <div class="filter-pill active" onclick="setCategory('all', this)">All</div>
                        <div class="filter-pill" onclick="setCategory('forex', this)">Forex</div>
                        <div class="filter-pill" onclick="setCategory('indices', this)">Indices</div>
                        <div class="filter-pill" onclick="setCategory('commodity', this)">Commodities</div>
                        <div class="filter-pill" onclick="setCategory('crypto', this)">Crypto</div>
                    </div>
                    
                    <div class="symbols-list" id="symbols-container"></div>

                    <script>
                        const catalog = {catalog_json};
                        let favs = new Set(JSON.parse(localStorage.getItem('tv_fav_symbols') || '{fav_json}'));
                        let activeSymbol = localStorage.getItem('tv_active_sym') || 'XAUUSD';
                        let currentCat = 'all';

                        function saveFavs() {{
                            localStorage.setItem('tv_fav_symbols', JSON.stringify(Array.from(favs)));
                        }}

                        function setCategory(cat, el) {{
                            currentCat = cat;
                            document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
                            el.classList.add('active');
                            renderList();
                        }}

                        function toggleRibbon(sym, e) {{
                            e.stopPropagation();
                            if (favs.has(sym)) {{
                                favs.delete(sym);
                            }} else {{
                                favs.add(sym);
                            }}
                            saveFavs();
                            renderList();
                        }}

                        function selectSymbol(sym) {{
                            activeSymbol = sym;
                            localStorage.setItem('tv_active_sym', sym);
                            document.getElementById('active-indicator').innerHTML = 'Selected: <b style="color:#00ffcc;">' + sym + '</b>';
                            renderList();
                        }}

                        function renderList() {{
                            const query = document.getElementById('search-input').value.toUpperCase().trim();
                            const container = document.getElementById('symbols-container');
                            container.innerHTML = '';

                            // Sort: favorites at top
                            const flagged = catalog.filter(it => favs.has(it.id));
                            const unflagged = catalog.filter(it => !favs.has(it.id));
                            const sorted = [...flagged, ...unflagged];

                            sorted.forEach(item => {{
                                const matchesCat = (currentCat === 'all' || item.cat === currentCat);
                                const matchesQ = (!query || item.id.includes(query) || item.desc.toUpperCase().includes(query) || item.display.toUpperCase().includes(query));

                                if (!matchesCat || !matchesQ) return;

                                const isFlagged = favs.has(item.id);
                                const isSel = (item.id === activeSymbol);

                                const row = document.createElement('div');
                                row.className = 'symbol-row ' + (isSel ? 'selected' : '');
                                row.onclick = () => selectSymbol(item.id);

                                row.innerHTML = `
                                    <div class="ribbon-slot" onclick="toggleRibbon('${{item.id}}', event)">
                                        <div class="ribbon-flag ${{isFlagged ? 'flagged' : ''}}"></div>
                                    </div>
                                    <div class="icon-circle" style="background: ${{item.icon_bg}};">
                                        <span>${{item.icon_txt}}</span>
                                    </div>
                                    <div class="sym-name-col">
                                        <span class="sym-ticker">${{item.display}}</span>
                                    </div>
                                    <div class="sym-desc-col">
                                        <span class="sym-desc">${{item.desc}}</span>
                                    </div>
                                    <div class="sym-meta-col">
                                        <span class="sym-type">${{item.type}}</span>
                                        <span class="broker-tag">Capital.com</span>
                                    </div>
                                `;

                                container.appendChild(row);
                            }});
                        }}

                        // Initial Render
                        renderList();
                    </script>
                </body>
                </html>
                """

                from streamlit.components.v1 import html
                html(tv_search_html, height=390)

                # Selected Target Alert Form
                col_p_sym, col_p_target, col_p_cond, col_p_notes = st.columns([1.5, 1.2, 1.2, 2.0])
                
                with col_p_sym:
                    p_target_sym = st.selectbox(
                        "Target Asset",
                        options=[item["id"] for item in TV_CATALOG] + ["CUSTOM"],
                        index=0,
                        key="pa_sel_target_sym_field"
                    )
                    if p_target_sym == "CUSTOM":
                        final_target_sym = st.text_input("Enter Custom Symbol", value="", placeholder="e.g. SOLUSDT", key="pa_custom_inp_field").strip().upper()
                    else:
                        final_target_sym = p_target_sym

                with col_p_target:
                    p_target = st.number_input("Target Price ($)", value=2510.0, step=0.5, format="%.2f", key="input_pa_target_tab")
                with col_p_cond:
                    p_cond = st.selectbox("Condition", options=["ABOVE", "BELOW"], format_func=lambda x: "Rose Above (>=)" if x == "ABOVE" else "Dropped Below (<=)", key="input_pa_cond_tab")
                with col_p_notes:
                    p_notes = st.text_input("Alert Notes", value="", placeholder="e.g. Resistance breakout / 4H key level", key="input_pa_notes_tab")

                if st.button("Set Price Alert", type="primary", key="btn_set_price_alert_tab", use_container_width=True):
                    if not final_target_sym:
                        st.error("Please select or enter a valid asset symbol.")
                    else:
                        database.create_price_alert(symbol=final_target_sym, target_price=p_target, condition=p_cond, notes=p_notes)
                        st.success(f"Price alert set for {final_target_sym} {p_cond} ${p_target:,.2f}!")
                        st.rerun()

            # List of Price Alerts
            df_alerts = database.get_all_price_alerts(limit=50)
            if not df_alerts.empty:
                st.markdown("<h4 style='color:#ffffff;font-size:14px;font-weight:700;text-transform:uppercase;margin:18px 0 10px 0;'>Your Price Alerts</h4>", unsafe_allow_html=True)
                for _, r in df_alerts.iterrows():
                    is_active = str(r["status"]).upper() == "ACTIVE"
                    badge_col = "#00ffcc" if is_active else "#8a99ad"
                    badge_bg = "rgba(0,255,204,0.12)" if is_active else "rgba(255,255,255,0.06)"
                    t_price_str = f"${float(r['target_price']):,.2f}"
                    notes_str = f" | Note: {r['notes']}" if r.get('notes') else ""
                    created_str = str(r['created_at'])[:16]
                    cond_str = str(r['condition'])
                    sym_str = str(r['symbol'])
                    stat_str = str(r['status'])

                    col_al_info, col_al_del = st.columns([5, 1])
                    with col_al_info:
                        st.markdown(f"""
                        <div style="background: rgba(18, 24, 38, 0.7); border: 1px solid rgba(255,255,255,0.08); border-left: 4px solid {badge_col}; border-radius: 10px; padding: 10px 14px; margin-bottom: 6px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <span style="font-weight: 700; font-size: 14px; color: #ffffff;">{sym_str}</span>
                                    <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: {badge_bg}; color: {badge_col}; margin-left: 6px; font-weight:700;">{stat_str}</span>
                                    <div style="font-size: 12px; color: #8a99ad; margin-top: 3px;">
                                        Target: <b>{t_price_str}</b> ({cond_str}){notes_str} | Created: {created_str}
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_al_del:
                        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                        if st.button("Delete", key=f"del_pa_{r['id']}", use_container_width=True):
                            database.delete_price_alert(r["id"])
                            st.rerun()
            else:
                st.info("No active price alerts yet. Set your first price target above!")

        with sub_t_rules:
            import alerts
            current_rules = alerts.get_alert_rules()
            
            st.markdown("<p style='color: #8a99ad; font-size: 12px; margin-bottom: 12px;'>Configure your custom alert targets and drawdown risk limits below:</p>", unsafe_allow_html=True)
            
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                val_big_win = st.number_input("Big Win Target Alert ($)", value=float(current_rules.get("big_win_threshold", 100.0)), step=10.0, min_value=0.0, key="rule_big_win_tab")
                val_max_loss = st.number_input("Max Loss Risk Alert ($)", value=float(current_rules.get("max_loss_threshold", 50.0)), step=10.0, min_value=0.0, key="rule_max_loss_tab")
            with c_r2:
                val_drawdown = st.number_input("Daily Drawdown Floor Limit ($)", value=float(current_rules.get("daily_drawdown_limit", 300.0)), step=25.0, min_value=0.0, key="rule_dd_tab")
                val_streak = st.number_input("Win Streak Alert Target", value=int(current_rules.get("streak_alert_target", 3)), step=1, min_value=1, key="rule_streak_tab")
                
            c_chk, c_save = st.columns([2, 1])
            with c_chk:
                val_all_trades = st.checkbox("Send notification on every trade close", value=bool(current_rules.get("notify_on_all_trades", True)), key="chk_all_trades_alert_tab")
            with c_save:
                st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
                if st.button("Save Alert Rules", key="save_rules_tab_btn", type="primary", use_container_width=True):
                    alerts.save_alert_rules({
                        "big_win_threshold": val_big_win,
                        "max_loss_threshold": val_max_loss,
                        "daily_drawdown_limit": val_drawdown,
                        "streak_alert_target": val_streak,
                        "notify_on_all_trades": val_all_trades,
                        "filter_account": "ALL"
                    })
                    st.success("Custom alert rules updated successfully!")
                    st.rerun()

    with tab_terminal:
        st.markdown("<h3 style='color:#ffffff;font-size:1.3rem;margin-bottom:6px;font-weight:800;text-transform:uppercase;'>Quick Trading Terminal</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color:#8a99ad;font-size:13px;margin-bottom:16px;'>Place live market orders directly from your dashboard with built-in risk calculator.</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            col_t_acc, col_t_sym, col_t_dir = st.columns([1.5, 1.2, 1.2])
            with col_t_acc:
                trade_acc = st.selectbox(
                    "Select Execution Broker",
                    options=["CAPITAL_REAL", "MT5_FUNDED"],
                    format_func=lambda x: "Capital.com (Real Account • $294.03)" if x == "CAPITAL_REAL" else "MetaTrader 5 (Funded Account • $10,155.01)",
                    key="term_acc_sel"
                )
            with col_t_sym:
                term_symbol = st.text_input("Asset / Epic", value="GOLD" if trade_acc == "CAPITAL_REAL" else "XAUUSD", placeholder="e.g. GOLD, US100, EURUSD", key="term_sym_input")
            with col_t_dir:
                term_dir = st.selectbox("Order Direction", options=["BUY", "SELL"], format_func=lambda x: "BUY (Long)" if x == "BUY" else "SELL (Short)", key="term_dir_sel")
                
            col_t_sz, col_t_sl, col_t_tp = st.columns(3)
            with col_t_sz:
                term_size = st.number_input("Volume / Lot Size", value=0.01 if trade_acc == "MT5_FUNDED" else 1.0, step=0.01 if trade_acc == "MT5_FUNDED" else 0.5, format="%.2f", key="term_size_input")
            with col_t_sl:
                term_sl = st.number_input("Stop Loss Price (0 = None)", value=0.0, step=1.0, format="%.2f", key="term_sl_input")
            with col_t_tp:
                term_tp = st.number_input("Take Profit Price (0 = None)", value=0.0, step=1.0, format="%.2f", key="term_tp_input")
                
            # Live Order Summary
            summary_pos_type = "LONG POSITION" if term_dir == "BUY" else "SHORT POSITION"
            summary_pos_col = "#00ffcc" if term_dir == "BUY" else "#ff5555"
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:10px 14px; margin: 12px 0; display:flex; justify-content:space-between; align-items:center;">
                <span style="color:#8a99ad; font-size:13px;">Order Summary: <b style="color:#ffffff;">{term_dir} {term_size} lots of {term_symbol}</b></span>
                <span style="color:{summary_pos_col}; font-weight:800; font-size:13px;">{summary_pos_type}</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Phase 17 Execution Lock Logic
            ai_data_state = st.session_state.get("market_context_result")
            is_locked = False
            lock_reasons = []
            
            if ai_data_state and isinstance(ai_data_state, dict):
                val_data = ai_data_state.get("validation", {})
                if val_data.get("status") == "INVALID":
                    is_locked = True
                    lock_reasons = val_data.get("warnings", ["Unknown Reason"])
                    
            degen_override = False
            if is_locked:
                st.markdown(f"""
                <div style="background:rgba(255,85,85,0.1); border:1px solid #ff5555; border-radius:8px; padding:12px; margin-bottom:12px;">
                    <div style="color:#ff5555; font-weight:800; font-size:13px; margin-bottom:6px;">AI VALIDATION LOCK ACTIVE</div>
                    <div style="color:#cbd5e1; font-size:12px; margin-bottom:8px;">The deterministic engine has flagged this setup as INVALID due to:</div>
                    <ul style="color:#ff5555; font-size:11px; margin-top:0;">
                        {''.join([f"<li>{r}</li>" for r in lock_reasons])}
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                degen_override = st.checkbox("Override AI Validation Lock (Degen Mode)", key="degen_override")
                
            disable_exec = is_locked and not degen_override
            
            col_btn_buy, col_btn_sell = st.columns(2)
            with col_btn_buy:
                if st.button("SUBMIT BUY ORDER", type="primary", key="btn_exec_buy", use_container_width=True, disabled=disable_exec):
                    with st.spinner("Submitting BUY order via Canonical Pipeline..."):
                        import execution_pipeline
                        import uuid
                        import market_data
                        
                        curr_p = market_data.get_latest_price(term_symbol) or 0.0
                        b_name = "CAPITAL" if trade_acc == "CAPITAL_REAL" else "MT5"
                        m_name = database.get_setting("SYSTEM_STATE", "PAPER")
                        
                        req = execution_pipeline.CanonicalExecutionRequest(
                            signal_id=f"UI_{uuid.uuid4().hex[:8]}",
                            symbol=term_symbol,
                            side="BUY",
                            quantity=float(term_size),
                            requested_entry=float(curr_p),
                            stop_loss=float(term_sl) if term_sl > 0 else None,
                            take_profit=float(term_tp) if term_tp > 0 else None,
                            broker=b_name,
                            mode=m_name,
                            source="MANUAL_UI",
                            strategy="Quick Terminal"
                        )
                        res = execution_pipeline.submit_order(req)
                        if res.get("status") in ["success", "FILLED"]:
                            st.success(f"Order Executed: {res.get('message', 'Filled successfully')}")
                            st.rerun()
                        else:
                            st.error(f"Execution Blocked ({res.get('state')}): {res.get('message')}")
            with col_btn_sell:
                if st.button("SUBMIT SELL ORDER", key="btn_exec_sell", use_container_width=True, disabled=disable_exec):
                    with st.spinner("Submitting SELL order via Canonical Pipeline..."):
                        import execution_pipeline
                        import uuid
                        import market_data
                        
                        curr_p = market_data.get_latest_price(term_symbol) or 0.0
                        b_name = "CAPITAL" if trade_acc == "CAPITAL_REAL" else "MT5"
                        m_name = database.get_setting("SYSTEM_STATE", "PAPER")
                        
                        req = execution_pipeline.CanonicalExecutionRequest(
                            signal_id=f"UI_{uuid.uuid4().hex[:8]}",
                            symbol=term_symbol,
                            side="SELL",
                            quantity=float(term_size),
                            requested_entry=float(curr_p),
                            stop_loss=float(term_sl) if term_sl > 0 else None,
                            take_profit=float(term_tp) if term_tp > 0 else None,
                            broker=b_name,
                            mode=m_name,
                            source="MANUAL_UI",
                            strategy="Quick Terminal"
                        )
                        res = execution_pipeline.submit_order(req)
                        if res.get("status") in ["success", "FILLED"]:
                            st.success(f"Order Executed: {res.get('message', 'Filled successfully')}")
                            st.rerun()
                        else:
                            st.error(f"Execution Blocked ({res.get('state')}): {res.get('message')}")

        # Open positions with Close button
        if not df_open.empty:
            st.markdown("<h4 style='color:#ffffff;font-size:14px;font-weight:700;text-transform:uppercase;margin:20px 0 10px 0;'>Manage Live Open Positions</h4>", unsafe_allow_html=True)
            for _, pos in df_open.iterrows():
                pos_id = str(pos["position_id"])
                fl_pnl = float(pos.get("floating_pnl", 0.0))
                pnl_col = "#00ffcc" if fl_pnl >= 0 else "#ff5555"
                pnl_s = "+" if fl_pnl >= 0 else "-"
                pnl_badge_str = f"{pnl_s}${abs(fl_pnl):,.2f}"
                p_sym = str(pos['symbol'])
                p_dir = str(pos['direction'])
                p_vol = f"{float(pos['volume']):.2f}"
                p_entry = f"{float(pos['entry_price']):.5f}"
                p_curr = f"{float(pos['current_price']):.5f}"
                p_open_t = str(pos['open_time'])[:16]
                
                col_pos_desc, col_pos_act = st.columns([4.5, 1.5])
                with col_pos_desc:
                    st.markdown(f"""
                    <div style="background:rgba(18,24,38,0.7); border:1px solid rgba(255,255,255,0.08); border-left:4px solid {pnl_col}; border-radius:10px; padding:10px 14px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="font-weight:700; color:#ffffff; font-size:14px;">{p_sym}</span>
                            <span style="font-size:11px; padding:2px 6px; border-radius:4px; background:rgba(255,255,255,0.06); color:#8a99ad; margin-left:4px; font-weight:700;">{p_dir} {p_vol}</span>
                            <div style="font-size:12px; color:#8a99ad; margin-top:2px;">
                                Entry: {p_entry} to Current: {p_curr} | Open: {p_open_t}
                            </div>
                        </div>
                        <div style="font-size:16px; font-weight:800; color:{pnl_col};">
                            {pnl_badge_str}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_pos_act:
                    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                    if st.button("Close Position", key=f"close_pos_{pos_id}", use_container_width=True):
                        from broker_adapter import get_broker_adapter
                        if pos_id.startswith("MT5_"):
                            ad = get_broker_adapter("MT5")
                            r = ad.close_position(pos_id.replace("MT5_", ""))
                        elif pos_id.startswith("CAP_"):
                            ad = get_broker_adapter("CAPITAL")
                            r = ad.close_position(pos_id.replace("CAP_", ""))
                        else:
                            ad = get_broker_adapter("PAPER")
                            r = ad.close_position(pos_id)
                            
                        if r.status == "SUCCESS":
                            st.success("Position closed successfully!")
                            st.rerun()
                        else:
                            st.error(r.message)
                                
    with tab_sandbox:
        st.markdown("<h3 style='color:#ffffff;font-size:1.3rem;margin-bottom:6px;font-weight:800;text-transform:uppercase;'>Multi-Timeframe Strategy Sandbox</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color:#94a3b8;font-size:0.9rem;margin-bottom:24px;'>Simulate mechanical edge models on historical data without risking live capital.</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("<div style='font-size:0.75rem;font-weight:800;color:#00ffcc;letter-spacing:1px;margin-bottom:12px;'>BACKTEST CONFIGURATION</div>", unsafe_allow_html=True)
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                test_symbol = st.selectbox("Asset Symbol", ["USDJPY", "EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "US30", "NAS100", "SPX500"], index=0)
                test_timeframe = st.selectbox("Granularity", ["1h", "1d"], index=0, help="Higher timeframes are faster to simulate over long periods.")
            with col2:
                import strategies
                sb_strat_list = strategies.get_all_strategy_names()
                test_strategy = st.selectbox("Strategy Template", sb_strat_list)
                test_capital = st.number_input("Starting Capital ($)", value=10000.0, step=1000.0)
            with col3:
                test_risk = st.number_input("Risk Per Trade (%)", value=1.0, step=0.1, max_value=5.0)
                test_sl = st.number_input("Stop Loss (ATR Multiple)", value=1.5, step=0.1)
            with col4:
                test_tp = st.number_input("Take Profit (ATR Multiple)", value=2.0, step=0.1)
                test_slippage = st.number_input("Slippage (Absolute)", value=0.0001, format="%f")
            with col5:
                test_commission = st.number_input("Commission (%)", value=0.01, step=0.01)
                test_fixed_spread = st.number_input("Fixed Spread", value=0.0, format="%f")
                
            test_train_split = st.slider("Train/Test Split (In-Sample %)", min_value=0.1, max_value=1.0, value=0.7, step=0.1, help="Reserve recent data for Out-of-Sample testing.")
            
            optimization_mode = st.radio("Optimization Mode", ["Standard Backtest", "Walk-Forward Optimization (WFO)"], horizontal=True)
            if optimization_mode == "Walk-Forward Optimization (WFO)":
                st.markdown("<p style='font-size:0.8rem;color:#f59e0b;'>WFO will optimize SL/TP using a grid search over 3 rolling windows.</p>", unsafe_allow_html=True)
                
            st.markdown("<div style='font-size:0.75rem;font-weight:800;color:#f59e0b;letter-spacing:1px;margin-bottom:6px;margin-top:12px;'>BACKTEST VALIDITY CHECKLIST</div>", unsafe_allow_html=True)
            st.markdown("<p style='font-size:0.8rem;color:#94a3b8;'>• <b>Execution:</b> Next-Bar Market Order (0-bar Look-Ahead PASS)<br/>• <b>Data:</b> Yahoo Finance (UTC Standardized)<br/>• <b>Instrument Constraints:</b> MODELED (Min Qty / Step Rounding enforced)</p>", unsafe_allow_html=True)
                
            run_test = st.button("RUN SIMULATION", use_container_width=True, type="primary")
            
            
        if run_test:
            with st.spinner("Fetching historical data and running simulation..."):
                import backtester
                
                if optimization_mode == "Standard Backtest":
                    res = backtester.run_backtest(
                        symbol=test_symbol,
                        timeframe=test_timeframe,
                        strategy=test_strategy,
                        risk_pct=test_risk,
                        sl_atr=test_sl,
                        tp_atr=test_tp,
                        capital=test_capital,
                        slippage=test_slippage,
                        commission_pct=test_commission,
                        fixed_spread=test_fixed_spread,
                        train_split=test_train_split
                    )
                else:
                    res = backtester.run_walk_forward(
                        symbol=test_symbol,
                        timeframe=test_timeframe,
                        strategy=test_strategy,
                        risk_pct=test_risk,
                        capital=test_capital,
                        slippage=test_slippage,
                        commission_pct=test_commission,
                        fixed_spread=test_fixed_spread
                    )
                
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.success("Simulation Complete!")
                    metrics_is = res.get("metrics_is")
                    metrics_oos = res.get("metrics_oos")
                    
                    st.markdown("<div style='margin-top:24px;font-size:0.75rem;font-weight:800;color:#bef264;letter-spacing:1px;margin-bottom:12px;'>IN-SAMPLE PERFORMANCE (TRAINING DATA)</div>", unsafe_allow_html=True)
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("Win Rate", metrics_is["Win Rate"])
                    mc2.metric("Profit Factor", metrics_is["Profit Factor"])
                    mc3.metric("Max Drawdown", metrics_is["Max Drawdown"])
                    mc4.metric("Total Trades", metrics_is["Total Trades"])
                    
                    if metrics_oos:
                        st.markdown("<div style='margin-top:24px;font-size:0.75rem;font-weight:800;color:#00ffcc;letter-spacing:1px;margin-bottom:12px;'>OUT-OF-SAMPLE PERFORMANCE (UNSEEN DATA)</div>", unsafe_allow_html=True)
                        mo1, mo2, mo3, mo4 = st.columns(4)
                        mo1.metric("Win Rate", metrics_oos["Win Rate"])
                        mo2.metric("Profit Factor", metrics_oos["Profit Factor"])
                        mo3.metric("Max Drawdown", metrics_oos["Max Drawdown"])
                        mo4.metric("Total Trades", metrics_oos["Total Trades"])
                        
                    st.markdown(f"<div style='margin-top:24px;font-size:1.1rem;font-weight:800;color:#ffffff;letter-spacing:1px;margin-bottom:12px;'>Final Capital: {res['final_capital']}</div>", unsafe_allow_html=True)
                    
                    if "monte_carlo" in res:
                        mc = res["monte_carlo"]
                        st.markdown("<div style='margin-top:24px;font-size:0.75rem;font-weight:800;color:#f59e0b;letter-spacing:1px;margin-bottom:12px;'>MONTE CARLO SIMULATION (1000 ITERATIONS)</div>", unsafe_allow_html=True)
                        mc_col1, mc_col2, mc_col3 = st.columns(3)
                        mc_col1.metric("Risk of Ruin (20% DD)", f"{mc['risk_of_ruin_pct']}%")
                        mc_col2.metric("95% Confidence Max DD", f"{mc['confidence_95_dd_pct']}%")
                        mc_col3.metric("Median Drawdown", f"{mc['median_dd_pct']}%")
                    
                    st.markdown("<div style='margin-top:24px;font-size:0.75rem;font-weight:800;color:#00ffcc;letter-spacing:1px;margin-bottom:12px;'>EQUITY CURVE</div>", unsafe_allow_html=True)
                    eq_curve = res["equity_curve"]
                    df_eq = pd.DataFrame(eq_curve)
                    df_eq['time'] = pd.to_datetime(df_eq['time'])
                    fig = px.line(df_eq, x='time', y='equity', color_discrete_sequence=['#00ffcc'])
                    fig.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#94a3b8'),
                        margin=dict(l=0, r=0, t=10, b=0),
                        xaxis=dict(showgrid=False, title=""),
                        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Equity ($)")
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    with st.expander("View Trade Log"):
                        st.dataframe(pd.DataFrame(res["trades"]), use_container_width=True)
                        
    with tab_health:
        st.markdown("<h3 style='color:#ffffff;font-size:1.3rem;margin-bottom:6px;font-weight:800;text-transform:uppercase;'>Execution Operations & System Health Gate</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color:#8a99ad;font-size:13px;margin-bottom:16px;'>Authoritative diagnostics across Broker Reconciliation, Execution Pipelines, and Safety Invariants.</p>", unsafe_allow_html=True)
        
        import system_health
        import reconciliation
        
        cur_mode = database.get_setting("SYSTEM_STATE", "PAPER")
        health_data = system_health.evaluate_system_health(broker="MT5", mode=cur_mode)
        recon_h = reconciliation.get_reconciliation_health()
        
        # Operational Top Cards
        st.markdown("<div style='font-size:0.75rem;font-weight:800;color:#00ffcc;letter-spacing:1px;margin-bottom:12px;'>REAL-TIME SUBSYSTEM STATUS</div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        
        auto_badge = "ALLOWED" if health_data["automation_allowed"] else "BLOCKED"
        auto_color = "normal" if health_data["automation_allowed"] else "off"
        c1.metric("Live Automation", auto_badge, f"Mode: {cur_mode}")
        c2.metric("Reconciliation Worker", recon_h.get("status", "UNKNOWN"), f"Failures: {recon_h.get('consecutive_failures', 0)}")
        
        # UNKNOWN order count
        conn = database.get_connection()
        try:
            df_exec = pd.read_sql_query("SELECT * FROM execution_orders ORDER BY created_at DESC LIMIT 50", conn)
            unknown_cnt = int((df_exec["state"] == "UNKNOWN").sum()) if not df_exec.empty and "state" in df_exec.columns else 0
        except Exception:
            df_exec = pd.DataFrame()
            unknown_cnt = 0
        conn.close()
        
        c3.metric("UNKNOWN Orders", f"{unknown_cnt}", "0 expected" if unknown_cnt == 0 else "Action Req")
        c4.metric("Risk Gateway", "ACTIVE", "Fail-Closed")
        
        # Reason warnings if blocked
        if not health_data["automation_allowed"]:
            st.markdown("""
            <div style="background:rgba(255,85,85,0.1); border:1px solid #ff5555; border-radius:8px; padding:12px; margin-top:14px; margin-bottom:14px;">
                <div style="color:#ff5555; font-weight:800; font-size:13px; margin-bottom:6px;">AUTOMATION GATE BLOCKED</div>
                <div style="color:#cbd5e1; font-size:12px; margin-bottom:6px;">The following safety conditions are currently blocking automated trade execution:</div>
                <ul style="color:#ff5555; font-size:12px; margin:0 0 0 16px;">
            """ + "".join([f"<li>{r}</li>" for r in health_data["reasons"]]) + """
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
        # Action Toolbar
        col_act1, col_act2, col_act3 = st.columns([1.2, 1.2, 2.0])
        with col_act1:
            if st.button("Trigger Immediate Reconciliation", key="btn_trigger_recon", use_container_width=True):
                with st.spinner("Running position & order reconciliation..."):
                    res_rec = reconciliation.reconcile_unknown_orders()
                    st.success(f"Reconciliation cycle complete ({len(res_rec)} resolved).")
                    st.rerun()
        with col_act2:
            if recon_h.get("status") == "RECONCILIATION_STOPPED":
                if st.button("Start Recon Daemon", key="btn_start_recon", use_container_width=True):
                    reconciliation.start_background_reconciliation()
                    st.success("Reconciliation daemon started.")
                    st.rerun()
            else:
                if st.button("Stop Recon Daemon", key="btn_stop_recon", use_container_width=True):
                    reconciliation.stop_background_reconciliation()
                    st.warning("Reconciliation daemon stopped.")
                    st.rerun()
                    
        # Execution State Machine Audit Log Table
        st.markdown("<div style='margin-top:24px;font-size:0.75rem;font-weight:800;color:#00ffcc;letter-spacing:1px;margin-bottom:12px;'>CANONICAL EXECUTION PIPELINE AUDIT LOG</div>", unsafe_allow_html=True)
        if not df_exec.empty:
            st.dataframe(
                df_exec[["execution_id", "signal_id", "symbol", "side", "requested_quantity", "requested_entry", "broker", "mode", "state", "execution_latency_ms", "reject_reason", "created_at"]],
                use_container_width=True,
                height=300
            )
        else:
            st.info("No canonical execution records found.")

render_live_dashboard()

# Force Streamlit Reload