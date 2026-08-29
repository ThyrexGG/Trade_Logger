import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
import calendar
import os
import time

import database
import mt5_sync
import capital_sync
import tradingview_widget
import order_execution

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
    
    /* Hide Streamlit top header white bar, toolbar, share/star buttons */
    [data-testid="stHeader"], header, [data-testid="stToolbar"], .stAppDeployButton, [data-testid="stDecoration"], #MainMenu, footer {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
        opacity: 0 !important;
        pointer-events: none !important;
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

    /* Hide running status widget to keep sync 100% silent and backgrounded */
    div[data-testid="stStatusWidget"],
    .stStatusWidget {
        display: none !important;
        visibility: hidden !important;
    }

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
    .stSpinner > div:first-child {
        display: none !important;
    }
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
        tab_overview, tab_charts, tab_journal, tab_alerts, tab_terminal = st.tabs([
            "ANALYTICS & OVERVIEW",
            "LIVE CHARTS",
            "TRADE JOURNAL",
            "PRICE ALERTS",
            "QUICK TERMINAL"
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

                filtered_df["balance"] = initial_balance + filtered_df["net_profit"].cumsum()
                current_balance = official_broker_bal if official_broker_bal is not None else filtered_df["balance"].iloc[-1]
                total_pnl = filtered_df["net_profit"].sum()
                gain_pct = (total_pnl / initial_balance) * 100

                gross_wins = filtered_df[filtered_df["net_profit"] > 0]["net_profit"].sum()
                gross_losses = abs(filtered_df[filtered_df["net_profit"] <= 0]["net_profit"].sum())
                profit_factor = gross_wins / gross_losses if gross_losses > 0 else (gross_wins if gross_wins > 0 else 1.0)

                peaks = filtered_df["balance"].cummax()
                drawdowns = (peaks - filtered_df["balance"]) / peaks * 100
                max_drawdown = drawdowns.max() if not drawdowns.empty else 0.0
                highest_balance = peaks.max() if not peaks.empty else initial_balance

                trades_pnl = filtered_df["net_profit"].values
                if len(trades_pnl) > 1:
                    std_dev = np.std(trades_pnl)
                    sqn = (np.mean(trades_pnl) / std_dev) * np.sqrt(len(trades_pnl)) if std_dev > 0 else 0.0
                else:
                    sqn = 0.0

                avg_duration = filtered_df["duration_minutes"].mean()
                h_days = int(avg_duration // (24 * 60))
                rem_min = avg_duration % (24 * 60)
                h_hours = int(rem_min // 60)
                h_mins = int(rem_min % 60)
                hold_time_str = f"{h_days}d {h_hours}h {h_mins}m" if h_days > 0 else f"{h_hours}h {h_mins}m"

                total_trades = len(filtered_df)
                winning_trades = len(filtered_df[filtered_df["net_profit"] > 0])
                losing_trades = len(filtered_df[filtered_df["net_profit"] <= 0])
                win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0

                biggest_win = filtered_df["net_profit"].max() if not filtered_df.empty else 0.0
                biggest_loss = filtered_df["net_profit"].min() if not filtered_df.empty else 0.0

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
            sub_c_tv, sub_c_broker = st.tabs([
                "TRADINGVIEW PRO STUDIO", 
                "BROKER CANDLESTICKS (REAL TRADES OVERLAID)"
            ])

            with sub_c_tv:
                col_sym, col_tf, col_custom, col_link = st.columns([1.3, 0.9, 1.2, 1.2])
                with col_sym:
                    selected_tv_preset = st.selectbox(
                        "Select Market Asset",
                        options=list(tradingview_widget.DEFAULT_SYMBOLS.keys()),
                        index=0,
                        key="tv_symbol_preset"
                    )
                    tv_symbol = tradingview_widget.DEFAULT_SYMBOLS[selected_tv_preset]
                with col_tf:
                    tv_interval = st.selectbox(
                        "Chart Timeframe",
                        options=["1", "5", "15", "60", "240", "D"],
                        format_func=lambda x: {"1": "1 Minute", "5": "5 Minutes", "15": "15 Minutes", "60": "1 Hour", "240": "4 Hours", "D": "Daily"}[x],
                        index=2,
                        key="tv_interval_sel"
                    )
                with col_custom:
                    custom_sym = st.text_input("Or Custom Ticker", value="", placeholder="e.g. BINANCE:SOLUSDT", key="tv_custom_sym")
                    if custom_sym.strip():
                        tv_symbol = custom_sym.strip().upper()
                with col_link:
                    render_html(f"""
                    <div style="margin-top: 28px;">
                        <a href="https://www.tradingview.com/chart/?symbol={tv_symbol}" target="_blank" style="display: inline-block; background: rgba(0, 255, 204, 0.12); color: #00ffcc; border: 1px solid rgba(0, 255, 204, 0.35); padding: 8px 12px; border-radius: 6px; font-size: 12px; font-weight: 700; text-decoration: none; width: 100%; text-align: center;">
                            FULLSCREEN VIEW
                        </a>
                    </div>
                    """)

                tradingview_widget.render_tradingview_chart(
                    symbol=tv_symbol, 
                    interval=tv_interval, 
                    height=750
                )

            with sub_c_broker:
                st.markdown("<p style='color:#8a99ad;font-size:13px;margin-bottom:14px;'>Live broker candlestick chart with your actual executed BUY/SELL trade entry/exit arrows, holding lines, profit annotations, and open SL/TP levels plotted directly on the candles.</p>", unsafe_allow_html=True)
                
                col_b1, col_b2, col_b3 = st.columns([1.5, 1, 1])
                with col_b1:
                    broker_sym = st.selectbox(
                        "Broker Symbol",
                        options=["XAUUSD", "GOLD", "US100", "US500", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "USOIL"],
                        index=0,
                        key="sel_broker_chart_sym"
                    )
                with col_b2:
                    broker_tf = st.selectbox(
                        "Timeframe",
                        options=["1m", "5m", "15m", "1h", "4h", "D"],
                        index=3,
                        format_func=lambda x: {"1m": "1 Minute", "5m": "5 Minutes", "15m": "15 Minutes", "1h": "1 Hour", "4h": "4 Hours", "D": "Daily"}[x],
                        key="sel_broker_chart_tf"
                    )
                with col_b3:
                    candle_count = st.selectbox("Candle History", options=[50, 100, 150, 250, 500], index=2, key="sel_broker_candles_cnt")
                    
                tradingview_widget.render_broker_candlestick_overlay(
                    symbol=broker_sym,
                    df_trades=df_trades,
                    df_open=df_open,
                    timeframe=broker_tf,
                    count=candle_count
                )

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
        
        sub_t_price, sub_t_rules = st.tabs(["LIVE PRICE TARGET ALERTS", "PROFIT & LOSS ALERT RULES"])
        
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
                        <span class="search-icon">🔍</span>
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
            
            col_btn_buy, col_btn_sell = st.columns(2)
            with col_btn_buy:
                if st.button("SUBMIT BUY ORDER", type="primary", key="btn_exec_buy", use_container_width=True):
                    with st.spinner("Submitting BUY order..."):
                        if trade_acc == "CAPITAL_REAL":
                            ok, msg = order_execution.execute_capital_trade(epic=term_symbol, direction="BUY", size=term_size, stop_loss=term_sl if term_sl > 0 else None, take_profit=term_tp if term_tp > 0 else None)
                        else:
                            ok, msg = order_execution.execute_mt5_trade(symbol=term_symbol, direction="BUY", volume=term_size, stop_loss=term_sl if term_sl > 0 else None, take_profit=term_tp if term_tp > 0 else None)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            with col_btn_sell:
                if st.button("SUBMIT SELL ORDER", key="btn_exec_sell", use_container_width=True):
                    with st.spinner("Submitting SELL order..."):
                        if trade_acc == "CAPITAL_REAL":
                            ok, msg = order_execution.execute_capital_trade(epic=term_symbol, direction="SELL", size=term_size, stop_loss=term_sl if term_sl > 0 else None, take_profit=term_tp if term_tp > 0 else None)
                        else:
                            ok, msg = order_execution.execute_mt5_trade(symbol=term_symbol, direction="SELL", volume=term_size, stop_loss=term_sl if term_sl > 0 else None, take_profit=term_tp if term_tp > 0 else None)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

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
                        if pos_id.startswith("MT5_"):
                            st.info("To close MT5 positions, manage them directly in your MetaTrader terminal.")
                        else:
                            clean_id = pos_id.replace("CAP_", "")
                            ok, msg = order_execution.close_capital_position(clean_id)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

render_live_dashboard()
