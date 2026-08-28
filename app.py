import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
import calendar
import os

import database
import mt5_sync
import capital_sync

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
    page_icon=icon_file if os.path.exists(icon_file) else "📈"
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
# MAIN DASHBOARD WITH 30-SECOND REAL-TIME AUTO-REFRESH
# ----------------------------------------------------
@st.fragment(run_every=30)
def render_live_dashboard():
    df_trades = database.get_closed_trades()

# ----------------------------------------------------
# MAIN DASHBOARD WITH 30-SECOND REAL-TIME AUTO-REFRESH
# ----------------------------------------------------
@st.fragment(run_every=30)
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
                <h1 style="margin: 0; font-size: 1.85rem; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">TradeLogger Analytics</h1>
                <p style="margin: 3px 0 0 0; color: #8a99ad; font-size: 13px; letter-spacing: 0.2px;">Automated journal & performance analytics for multi-broker accounts</p>
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
        # Convert dates to pandas datetime objects (handles mixed timezone and ISO formats)
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
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            color: #ffffff !important;
            font-size: 18px !important;
            font-weight: 700 !important;
            text-decoration: none !important;
            line-height: 1 !important;
            cursor: pointer !important;
            transition: all 0.2s ease-in-out !important;
            user-select: none !important;
        }
        .cal-nav-link-btn:hover {
            background-color: rgba(0, 255, 204, 0.12) !important;
            border-color: rgba(0, 255, 204, 0.4) !important;
            color: #00ffcc !important;
            box-shadow: 0 0 10px rgba(0, 255, 204, 0.2) !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Initialize per-account initial balances in session state
        if "account_balances" not in st.session_state:
            st.session_state.account_balances = {
                "ALL": 10300.0,
            }

        unique_accounts = sorted(list(df_trades["account_id"].unique()))
        account_options = unique_accounts + (["ALL"] if len(unique_accounts) > 1 else [])

        def format_account_name(acc_id):
            if acc_id == "ALL":
                return "All Accounts (Combined View)"
            elif str(acc_id).startswith("MT5_"):
                return f"MetaTrader 5 ({str(acc_id).replace('MT5_', '')}) • Funded Account"
            else:
                return f"Capital.com ({acc_id}) • Real Account"

        # Populate default starting balances per account
        for acc in unique_accounts:
            if acc not in st.session_state.account_balances:
                if str(acc).startswith("MT5_"):
                    st.session_state.account_balances[acc] = 10000.0
                else:
                    st.session_state.account_balances[acc] = 300.0

        # Header with Cool App Icon
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
        <div style="display: flex; align-items: center; gap: 14px; margin-top: 8px; margin-bottom: 20px;">
            {logo_html}
            <div>
                <h1 style="margin: 0; font-size: 1.85rem; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">TradeLogger Analytics</h1>
                <p style="margin: 3px 0 0 0; color: #8a99ad; font-size: 13px; letter-spacing: 0.2px;">Automated journal & performance analytics for multi-broker accounts</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Unified Control & Filter Card (Active State)
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
                col_mt5, col_cap, col_test = st.columns([1, 1, 1])
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
                with col_test:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("Test Alert", key="active_test_alert", use_container_width=True):
                        with st.spinner("Sending test alert..."):
                            import alerts
                            alerts.notify_trade_closed({
                                "symbol": "XAUUSD",
                                "direction": "BUY",
                                "net_profit": 125.50,
                                "duration_minutes": 34.2,
                                "account_id": "MT5_26633147",
                                "entry_price": 2501.20,
                                "exit_price": 2513.75
                            })
                            # Trigger direct client-side notification for Phone App + Browser
                            from streamlit.components.v1 import html
                            html("""
                            <script>
                                // 1. Native Flutter App Bridge (Checks both iframe and parent window)
                                const flutterBridge = window.TradeAlert || (window.parent && window.parent.TradeAlert);
                                if (flutterBridge) {
                                    flutterBridge.postMessage(JSON.stringify({
                                        title: "Trade Closed: XAUUSD (+$125.50)",
                                        body: "Funded MT5 • BUY • PnL: +$125.50 • Duration: 34.2m"
                                    }));
                                }
                                
                                // 2. Browser Desktop Notification (Checks both iframe and parent window)
                                const notifApi = window.Notification || (window.parent && window.parent.Notification);
                                if (notifApi) {
                                    if (notifApi.permission === "granted") {
                                        new notifApi("Trade Closed: XAUUSD (+$125.50)", {
                                            body: "Funded MT5 • BUY • PnL: +$125.50 • Duration: 34.2m"
                                        });
                                    } else if (notifApi.permission !== "denied") {
                                        notifApi.requestPermission().then(function (perm) {
                                            if (perm === "granted") {
                                                new notifApi("Trade Closed: XAUUSD (+$125.50)", {
                                                    body: "Funded MT5 • BUY • PnL: +$125.50 • Duration: 34.2m"
                                                });
                                            }
                                        });
                                    }
                            </script>
                            """, height=0)
                            st.toast("🟢 Trade Closed: XAUUSD (+$125.50)\nFunded MT5 • BUY • Duration: 34.2m", icon="🔔")
                            st.success("Test alert dispatched! Windows banner, mobile push, and in-app toast triggered.")

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
            # Chronological sort for balance calculations
            filtered_df = filtered_df.sort_values(by="exit_time", ascending=True).reset_index(drop=True)

            # Fetch live detected account balances directly from broker APIs
            detected_balances = database.get_account_balances()
            official_broker_bal = None
            if selected_account in detected_balances:
                official_broker_bal = detected_balances[selected_account]["balance"]
            elif selected_account == "ALL" and detected_balances:
                official_broker_bal = sum(b["balance"] for b in detected_balances.values())

            # ------------------
            # METRICS COMPUTATION
            # ------------------
            filtered_df["balance"] = initial_balance + filtered_df["net_profit"].cumsum()
            # Use official broker balance directly if available (accounts for rebates & deposits), else use cumulative
            current_balance = official_broker_bal if official_broker_bal is not None else filtered_df["balance"].iloc[-1]
            total_pnl = filtered_df["net_profit"].sum()
            gain_pct = (total_pnl / initial_balance) * 100

            # Gross profit/loss
            gross_wins = filtered_df[filtered_df["net_profit"] > 0]["net_profit"].sum()
            gross_losses = abs(filtered_df[filtered_df["net_profit"] <= 0]["net_profit"].sum())
            profit_factor = gross_wins / gross_losses if gross_losses > 0 else (gross_wins if gross_wins > 0 else 1.0)

            # Drawdowns
            peaks = filtered_df["balance"].cummax()
            drawdowns = (peaks - filtered_df["balance"]) / peaks * 100
            max_drawdown = drawdowns.max() if not drawdowns.empty else 0.0
            highest_balance = peaks.max() if not peaks.empty else initial_balance

            # SQN
            trades_pnl = filtered_df["net_profit"].values
            if len(trades_pnl) > 1:
                std_dev = np.std(trades_pnl)
                sqn = (np.mean(trades_pnl) / std_dev) * np.sqrt(len(trades_pnl)) if std_dev > 0 else 0.0
            else:
                sqn = 0.0

            # Holding Time
            avg_duration = filtered_df["duration_minutes"].mean()
            h_days = int(avg_duration // (24 * 60))
            rem_min = avg_duration % (24 * 60)
            h_hours = int(rem_min // 60)
            h_mins = int(rem_min % 60)
            hold_time_str = f"{h_days}d {h_hours}h {h_mins}m" if h_days > 0 else f"{h_hours}h {h_mins}m"

            # Win ratio
            total_trades = len(filtered_df)
            winning_trades = len(filtered_df[filtered_df["net_profit"] > 0])
            losing_trades = len(filtered_df[filtered_df["net_profit"] <= 0])
            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0

            # Max win and loss calculations
            biggest_win = filtered_df["net_profit"].max() if not filtered_df.empty else 0.0
            biggest_loss = filtered_df["net_profit"].min() if not filtered_df.empty else 0.0

            # Streaks
            current_streak_trades = 0
            max_streak_trades = 0
            temp_streak = 0
            for pnl in trades_pnl:
                if pnl > 0:
                    temp_streak += 1
                    max_streak_trades = max(max_streak_trades, temp_streak)
                else:
                    temp_streak = 0
            for pnl in reversed(trades_pnl):
                if pnl > 0:
                    current_streak_trades += 1
                else:
                    break

            daily_pnl = filtered_df.groupby(filtered_df["exit_time"].dt.date)["net_profit"].sum().reset_index()
            daily_pnl = daily_pnl.sort_values(by="exit_time").reset_index(drop=True)
            daily_outcomes = daily_pnl["net_profit"].values
            current_streak_days = 0
            max_streak_days = 0
            temp_streak = 0
            for pnl in daily_outcomes:
                if pnl > 0:
                    temp_streak += 1
                    max_streak_days = max(max_streak_days, temp_streak)
                else:
                    temp_streak = 0
            for pnl in reversed(daily_outcomes):
                if pnl > 0:
                    current_streak_days += 1
                else:
                    break

            # Period returns
            daily_rets = daily_pnl["net_profit"] / initial_balance * 100
            avg_daily_ret = daily_rets.mean() if not daily_rets.empty else 0.0

            # Use timezone-naive timestamps to match the naive exit_time column in database
            weekly_cutoff = pd.Timestamp.now() - pd.Timedelta(days=7)
            weekly_pnl = filtered_df[filtered_df["exit_time"] >= weekly_cutoff]["net_profit"].sum()
            weekly_ret = (weekly_pnl / initial_balance) * 100

            monthly_cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
            monthly_pnl = filtered_df[filtered_df["exit_time"] >= monthly_cutoff]["net_profit"].sum()
            monthly_ret = (monthly_pnl / initial_balance) * 100

            ann_ret = ((1 + avg_daily_ret/100) ** 252 - 1) * 100 if avg_daily_ret > 0 else (avg_daily_ret if avg_daily_ret < 0 else 0.0)

            # Dynamic color coding: Green for positive, Red for negative
            daily_color = "#00ffcc" if avg_daily_ret > 0 else ("#ff5555" if avg_daily_ret < 0 else "#8a99ad")
            weekly_color = "#00ffcc" if weekly_ret > 0 else ("#ff5555" if weekly_ret < 0 else "#8a99ad")
            monthly_color = "#00ffcc" if monthly_ret > 0 else ("#ff5555" if monthly_ret < 0 else "#8a99ad")
            ann_color = "#00ffcc" if ann_ret > 0 else ("#ff5555" if ann_ret < 0 else "#8a99ad")

            # Radar Scores
            stability_score = win_rate
            risk_score = max(0.0, min(100.0, 100.0 - max_drawdown * 8))
            exit_score = max(0.0, min(100.0, profit_factor * 25))
            tempo_score = max(10.0, min(100.0, 100.0 - (avg_duration / 60.0) * 10))
            entry_score = max(0.0, min(100.0, win_rate * 1.1))
            wave_score = int(np.mean([stability_score, risk_score, exit_score, tempo_score, entry_score]))

            # Session Metrics
            filtered_df["session_date"] = filtered_df["exit_time"].dt.strftime("%d/%m/%Y")
            session_pnls = filtered_df.groupby("session_date")["net_profit"].sum()
            most_active_sess = filtered_df["session_date"].value_counts().idxmax() if not filtered_df.empty else "-"
            most_prof_sess = session_pnls.idxmax() if not session_pnls.empty else "-"
            least_prof_sess = session_pnls.idxmin() if not session_pnls.empty else "-"

            # Fetch live open positions from database
            try:
                df_open = database.get_open_positions(selected_account)
            except Exception:
                df_open = pd.DataFrame()

            unrealized_pnl = float(df_open["floating_pnl"].sum()) if not df_open.empty and "floating_pnl" in df_open.columns else 0.0
            open_trades_count = len(df_open)
            unrealized_color = "#00ffcc" if unrealized_pnl > 0 else ("#ff5555" if unrealized_pnl < 0 else "#ffffff")
            unrealized_sign = "+" if unrealized_pnl > 0 else ("-" if unrealized_pnl < 0 else "")

            # ------------------
            # THE5ERS PROP FIRM EVALUATION & OBJECTIVES HUB (Only for MT5 Funded Account)
            # ------------------
            is_mt5 = str(selected_account).startswith("MT5_")

            if is_mt5:
                target_profit_goal = initial_balance * 0.10
                max_daily_loss_limit = initial_balance * 0.05
                max_total_loss_limit = initial_balance * 0.10

                today_pnl_val = daily_outcomes[-1] if len(daily_outcomes) > 0 else 0.0
                daily_loss_remaining = max(0.0, max_daily_loss_limit + (today_pnl_val if today_pnl_val < 0 else 0.0))
                max_loss_remaining = max(0.0, max_total_loss_limit + (total_pnl if total_pnl < 0 else 0.0))
                profitable_days_count = len([p for p in daily_outcomes if p > 0])

                goal_pnl_sign = "+" if total_pnl >= 0 else "-"
                goal_pnl_color = "#00ffcc" if total_pnl >= 0 else "#ff5555"
                daily_pnl_color = "#00ffcc" if today_pnl_val >= 0 else "#ff5555"
                daily_pnl_sign = "+" if today_pnl_val >= 0 else "-"

                account_order_id = "1000782405"
                account_disp_num = str(selected_account).replace("MT5_", "")
                broker_name = "Five Percent Online MetaTrader"
                program_name = "$10K High Stakes 10%"

                render_html(f"""
                <div class="prop-hub-container">
                    <!-- Header Row -->
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:14px;">
                        <div>
                            <div style="display:flex; gap:6px; margin-bottom:8px;">
                                <span class="prop-badge forex">Forex</span>
                                <span class="prop-badge active">● Active</span>
                                <span class="prop-badge eval">Evaluation</span>
                            </div>
                            <div style="font-size:22px; font-weight:800; color:#ffffff; letter-spacing:-0.4px;">{program_name}</div>
                            <div style="font-size:11px; color:#8a99ad; margin-top:3px;">Order ID #{account_order_id} • Account #{account_disp_num} • {broker_name}</div>
                        </div>

                        <div class="prop-stats-top-row" style="display:flex; gap:28px; text-align:right;">
                            <div>
                                <div style="font-size:10px; color:#8a99ad; text-transform:uppercase; font-weight:600;">Balance</div>
                                <div style="font-size:20px; font-weight:800; color:#ffffff;">${current_balance:,.2f}</div>
                            </div>
                            <div>
                                <div style="font-size:10px; color:#8a99ad; text-transform:uppercase; font-weight:600;">Unrealized</div>
                                <div style="font-size:20px; font-weight:800; color:{unrealized_color};">{unrealized_sign}${abs(unrealized_pnl):,.2f}</div>
                            </div>
                            <div>
                                <div style="font-size:10px; color:#8a99ad; text-transform:uppercase; font-weight:600;">Daily P&L</div>
                                <div style="font-size:20px; font-weight:800; color:{daily_pnl_color};">{daily_pnl_sign}${abs(today_pnl_val):,.2f}</div>
                            </div>
                        </div>
                    </div>

                    <!-- Scale Up Roadmap with smooth touch scrolling -->
                    <div class="prop-roadmap-wrapper">
                        <div class="prop-roadmap">
                            <div class="prop-roadmap-node active">
                                <span class="prop-roadmap-title">1st Evaluation</span>
                                <div class="prop-roadmap-circle">1</div>
                                <span class="prop-roadmap-target">${initial_balance:,.0f}</span>
                            </div>
                            <div class="prop-roadmap-node">
                                <span class="prop-roadmap-title">2nd Evaluation</span>
                                <div class="prop-roadmap-circle">2</div>
                                <span class="prop-roadmap-target">${initial_balance:,.0f}</span>
                            </div>
                            <div class="prop-roadmap-node">
                                <span class="prop-roadmap-title">Funded!</span>
                                <div class="prop-roadmap-circle">F</div>
                                <span class="prop-roadmap-target">${initial_balance:,.0f}</span>
                            </div>
                            <div class="prop-roadmap-node">
                                <span class="prop-roadmap-title">Scale Up</span>
                                <div class="prop-roadmap-circle">↑</div>
                                <span class="prop-roadmap-target">${initial_balance*1.25:,.0f}</span>
                            </div>
                            <div class="prop-roadmap-node">
                                <span class="prop-roadmap-title">Scale Up</span>
                                <div class="prop-roadmap-circle">↑</div>
                                <span class="prop-roadmap-target">${initial_balance*1.5:,.0f}</span>
                            </div>
                            <div class="prop-roadmap-node">
                                <span class="prop-roadmap-title">Scale Up</span>
                                <div class="prop-roadmap-circle">↑</div>
                                <span class="prop-roadmap-target">${initial_balance*2.0:,.0f}</span>
                            </div>
                            <div class="prop-roadmap-node">
                                <span class="prop-roadmap-title">Scale Up</span>
                                <div class="prop-roadmap-circle">↑</div>
                                <span class="prop-roadmap-target">${initial_balance*2.5:,.0f}</span>
                            </div>
                            <div class="prop-roadmap-node">
                                <span class="prop-roadmap-title">Scale Up</span>
                                <div class="prop-roadmap-circle">↑</div>
                                <span class="prop-roadmap-target">${initial_balance*3.0:,.0f}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Trading Objectives Header -->
                    <div style="font-size:13px; font-weight:700; color:#ffffff; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                        <span>Trading Objectives</span>
                        <span style="font-size:10px; color:#8a99ad; text-decoration:underline;">Rules & Compliance</span>
                    </div>

                    <!-- 5 Objective Cards Grid -->
                    <div class="prop-objectives-grid">
                        <!-- Card 1: Profitable Days -->
                        <div class="prop-obj-card">
                            <div class="prop-obj-header">
                                <span class="prop-obj-title">Profitable Days <span class="info-tip">?<span class="info-tip-text">Requires a minimum of 3 profitable trading days with at least 0.5% profit each day.</span></span></span>
                                <span class="prop-obj-status">In progress</span>
                            </div>
                            <div>
                                <div class="prop-obj-value">{profitable_days_count} / 3</div>
                                <div class="prop-obj-sub">Min 3 required</div>
                            </div>
                        </div>

                        <!-- Card 2: Unrealized Profit -->
                        <div class="prop-obj-card">
                            <div class="prop-obj-header">
                                <span class="prop-obj-title">Unrealized <span class="info-tip">?<span class="info-tip-text">Live floating profit or loss across currently open positions.</span></span></span>
                                <span class="prop-obj-status" style="{'background:rgba(0,255,204,0.1); color:#00ffcc; border-color:rgba(0,255,204,0.25);' if open_trades_count>0 else ''}">{'● Live' if open_trades_count>0 else '0 Open'}</span>
                            </div>
                            <div>
                                <div class="prop-obj-value" style="color:{unrealized_color};">{unrealized_sign}${abs(unrealized_pnl):,.2f}</div>
                                <div class="prop-obj-sub">{open_trades_count} Open Trade{'s' if open_trades_count != 1 else ''}</div>
                            </div>
                        </div>

                        <!-- Card 3: Profit Goal -->
                        <div class="prop-obj-card">
                            <div class="prop-obj-header">
                                <span class="prop-obj-title">Profit Goal <span class="info-tip">?<span class="info-tip-text">The 10% target required to pass the High Stakes evaluation phase ($1,000 target on $10k account).</span></span></span>
                                <span class="prop-obj-status">In progress</span>
                            </div>
                            <div>
                                <div class="prop-obj-value" style="color:{goal_pnl_color};">{goal_pnl_sign}${abs(total_pnl):,.2f}</div>
                                <div class="prop-obj-sub">Goal: ${target_profit_goal:,.0f} (10%)</div>
                            </div>
                        </div>

                        <!-- Card 4: Max Daily Loss -->
                        <div class="prop-obj-card">
                            <div class="prop-obj-header">
                                <span class="prop-obj-title">Max Daily Loss <span class="info-tip">?<span class="info-tip-text">Maximum daily drawdown limit of 5% ($500) based on midnight balance/equity. Resets every trading day at 00:00 server time.</span></span></span>
                                <span class="prop-obj-status" style="background:rgba(0,255,204,0.1); color:#00ffcc; border-color:rgba(0,255,204,0.25);">Safe</span>
                            </div>
                            <div>
                                <div class="prop-obj-value" style="color:#00ffcc;">${daily_loss_remaining:,.2f} Left</div>
                                <div class="prop-obj-sub">Limit: ${max_daily_loss_limit:,.0f} (5%)</div>
                            </div>
                        </div>

                        <!-- Card 5: Max Loss -->
                        <div class="prop-obj-card">
                            <div class="prop-obj-header">
                                <span class="prop-obj-title">Max Loss <span class="info-tip">?<span class="info-tip-text">The maximum total drawdown allowed across the entire evaluation (10% of starting balance - $1,000). This is your absolute floor - do not breach it.</span></span></span>
                                <span class="prop-obj-status" style="background:rgba(0,255,204,0.1); color:#00ffcc; border-color:rgba(0,255,204,0.25);">Safe</span>
                            </div>
                            <div>
                                <div class="prop-obj-value" style="color:#00ffcc;">${max_loss_remaining:,.2f} Left</div>
                                <div class="prop-obj-sub">Limit: ${max_total_loss_limit:,.0f} (10%)</div>
                            </div>
                        </div>
                    </div>
                </div>
                """)

            # ------------------
            # TOP STATS BAR
            # ------------------
            sign_pnl = "+" if total_pnl >= 0 else "-"
            color_pnl = "#00ffcc" if total_pnl >= 0 else "#ff5555"
            render_html(f"""
            <div class="top-stats-container">
                <div class="top-stat-box">
                    <div class="top-stat-label">Gross Profit (Loss) <span class="info-tip">?<span class="info-tip-text">Total cumulative gains from winning trades vs losses from losing trades.</span></span></div>
                    <div class="top-stat-value" style="color: #00ffcc;">${gross_wins:,.2f}</div>
                </div>
                <div class="top-stat-box">
                    <div class="top-stat-label">Net Profit <span class="info-tip">?<span class="info-tip-text">Total realized profit or loss after subtracting all broker commissions and swap fees.</span></span></div>
                    <div class="top-stat-value" style="color: {color_pnl};">{sign_pnl}${abs(total_pnl):,.2f}</div>
                </div>
                <div class="top-stat-box">
                    <div class="top-stat-label">Balance <span class="info-tip">?<span class="info-tip-text">Current realized account balance (Initial Capital + Net P&L).</span></span></div>
                    <div class="top-stat-value">${current_balance:,.2f}</div>
                </div>
                <div class="top-stat-box">
                    <div class="top-stat-label">Avg Holding Time <span class="info-tip">?<span class="info-tip-text">Average duration trades stay open from entry execution to final exit.</span></span></div>
                    <div class="top-stat-value" style="font-size: 18px; line-height: 28px;">{hold_time_str}</div>
                </div>
                <div class="top-stat-box">
                    <div class="top-stat-label">SQN <span class="info-tip">?<span class="info-tip-text">System Quality Number. Measures trading edge consistency. Above 2.0 is Good, above 3.0 is Excellent.</span></span></div>
                    <div class="top-stat-value" style="color: {'#00ffcc' if sqn >= 1.5 else ('#ff5555' if sqn < 0 else '#ffffff')};">{sqn:.2f}</div>
                </div>
                <div class="top-stat-box">
                    <div class="top-stat-label">Max Drawdown <span class="info-tip">?<span class="info-tip-text">Maximum percentage peak-to-trough decline experienced in account equity.</span></span></div>
                    <div class="top-stat-value" style="color: #ff5555;">{max_drawdown:.2f}%</div>
                </div>
            </div>
            """)

            # ------------------
            # LIVE ACTIVE OPEN POSITIONS BANNER / TRAY (Prominent Hero Placement)
            # ------------------
            if not df_open.empty:
                open_rows_hero = ""
                for idx, pos in df_open.iterrows():
                    pos_id_raw = str(pos["position_id"])
                    t_disp = "#" + pos_id_raw.replace("MT5_", "").replace("CAP_", "")
                    acc_label = "Funded MT5" if pos_id_raw.startswith("MT5_") else "Capital Real"
                    sym = str(pos["symbol"]).upper()
                    dir_str = str(pos["direction"]).upper()
                    dir_badge = f'<span class="badge-dir-long">↑ {dir_str}</span>' if "BUY" in dir_str or "LONG" in dir_str else f'<span class="badge-dir-short">↓ {dir_str}</span>'
                    vol = float(pos.get("volume", 0.0))
                    vol_disp = f"{vol:,.2f}" if vol < 1000 else f"{vol:,.0f}"
                    entry_px = float(pos.get("entry_price", 0.0))
                    curr_px = float(pos.get("current_price", 0.0))
                    fl_pnl = float(pos.get("floating_pnl", 0.0))
                    sl_val = float(pos.get("sl", 0.0))
                    tp_val = float(pos.get("tp", 0.0))
                    sl_disp = f"{sl_val:.5f}" if sl_val > 0 else "—"
                    tp_disp = f"{tp_val:.5f}" if tp_val > 0 else "—"

                    pnl_badge = f'<span class="badge-pnl-win" style="font-size:13px;">+${fl_pnl:,.2f}</span>' if fl_pnl > 0 else (f'<span class="badge-pnl-loss" style="font-size:13px;">-${abs(fl_pnl):,.2f}</span>' if fl_pnl < 0 else '<span style="color:#8a99ad; font-weight:600;">$0.00</span>')
                    open_t_str = pd.to_datetime(pos["open_time"]).strftime("%b %d, %H:%M")

                    open_rows_hero += f"""
                    <tr>
                        <td style="font-family:monospace; font-size:11px; color:#8a99ad;">{t_disp}</td>
                        <td style="font-size:11px; color:#c084fc;">{acc_label}</td>
                        <td style="font-weight:700; color:#ffffff; font-size:13px;">{sym}</td>
                        <td>{dir_badge}</td>
                        <td style="font-family:monospace;">{vol_disp}</td>
                        <td style="font-family:monospace; color:#8a99ad;">{entry_px:.5f}</td>
                        <td style="font-family:monospace; color:#00ffcc;">{curr_px:.5f}</td>
                        <td style="font-family:monospace; color:#ff5555; font-size:11px;">{sl_disp}</td>
                        <td style="font-family:monospace; color:#00ffcc; font-size:11px;">{tp_disp}</td>
                        <td>{pnl_badge}</td>
                        <td style="font-size:11px; color:#8a99ad;">{open_t_str}</td>
                    </tr>
                    """

                render_html(f"""
                <div style="margin-top:16px; margin-bottom: 20px; background: rgba(13, 17, 26, 0.7); border: 1px solid rgba(0, 255, 204, 0.35); border-radius: 12px; padding: 14px 18px; box-shadow: 0 4px 20px rgba(0,255,204,0.06);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#00ffcc; box-shadow: 0 0 12px #00ffcc;"></span>
                            <span style="font-size:15px; font-weight:800; color:#ffffff; letter-spacing:-0.2px;">LIVE OPEN POSITIONS ({len(df_open)})</span>
                        </div>
                        <div style="display:flex; align-items:center; gap:16px;">
                            <span style="font-size:12px; color:#8a99ad;">Total Floating P&L:</span>
                            <span style="font-size:16px; font-weight:800; color:{unrealized_color};">{unrealized_sign}${abs(unrealized_pnl):,.2f}</span>
                        </div>
                    </div>

                    <div class="journal-table-wrapper" style="border: 1px solid rgba(255, 255, 255, 0.08); max-height: 250px;">
                        <table class="journal-table">
                            <thead>
                                <tr>
                                    <th>Ticket</th>
                                    <th>Account</th>
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
                                {open_rows_hero}
                            </tbody>
                        </table>
                    </div>
                </div>
                """)

            # ------------------
            # ROW 1 GRID
            # ------------------
            col_hero_chart, col_hero_side = st.columns([2.0, 1.0])

            with col_hero_chart:
                # Wide Hero Account Balance & Equity Curve (Silky Smooth The5ers Progression Style)
                min_entry = filtered_df["entry_time"].min()
                start_baseline_time = min_entry - pd.Timedelta(hours=12)
                x_times = [start_baseline_time] + list(filtered_df["exit_time"])
                y_balances = [initial_balance] + list(filtered_df["balance"])
                n_pts = len(y_balances)

                # Generate silky smooth cubic Hermite curve over progression sequence
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

                # Y-Axis Active Range Zoom
                min_b = min(y_balances)
                max_b = max(y_balances)
                diff_b = max(max_b - min_b, 10.0)
                y_min = min_b - (diff_b * 0.15)
                y_max = max_b + (diff_b * 0.15)

                # Hover text with trade details on anchor points
                hover_labels = [f"<b>Initial Deposit</b><br>Balance: <b>${initial_balance:,.2f}</b>"]
                for idx, row in filtered_df.iterrows():
                    pnl_val = row['net_profit']
                    pnl_sign = '+' if pnl_val >= 0 else '-'
                    sym = row['symbol']
                    t_str = row['exit_time'].strftime('%b %d, %H:%M')
                    hover_labels.append(
                        f"<b>{t_str}</b> ({sym})<br>Trade PnL: <b style='color:{'#00ffcc' if pnl_val>=0 else '#ff5555'}'>{pnl_sign}${abs(pnl_val):,.2f}</b><br>Balance: <b>${row['balance']:,.2f}</b>"
                    )

                # Clean Date Checkpoint Ticks along the progression axis
                step = max(1, n_pts // 5)
                tick_indices = list(range(0, n_pts, step))
                if (n_pts - 1) not in tick_indices:
                    tick_indices.append(n_pts - 1)
                    
                tick_texts = [x_times[i].strftime("%b %d") for i in tick_indices]

                fig_balance = go.Figure()

                # High Water Mark subtle reference line
                fig_balance.add_trace(go.Scatter(
                    x=[-0.5, n_pts - 0.5],
                    y=[highest_balance, highest_balance],
                    mode='lines',
                    line=dict(color='rgba(255, 255, 255, 0.10)', width=1, dash='dot'),
                    hoverinfo='skip',
                    name='HWM'
                ))

                # 1. Silky Smooth Continuous Neon Curve & Subtle Ambient Fill
                fig_balance.add_trace(go.Scatter(
                    x=x_dense,
                    y=y_dense,
                    mode='lines',
                    line=dict(color='#bef264', width=2.8),
                    fill='tozeroy',
                    fillcolor='rgba(190, 242, 100, 0.04)',
                    hoverinfo='skip',
                    name='Balance Curve'
                ))

                # 2. Clean Checkpoint Anchor Markers (Interactive on hover, zero clutter)
                fig_balance.add_trace(go.Scatter(
                    x=list(range(n_pts)),
                    y=y_balances,
                    mode='markers',
                    marker=dict(size=4.5, color='#bef264', opacity=0.85, line=dict(color='#0b0f19', width=1)),
                    hovertext=hover_labels,
                    hoverinfo="text",
                    name='Trades'
                ))

                fig_balance.update_layout(
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
                    height=310,
                    showlegend=False
                )

                with st.container(border=True):
                    pnl_color_cur = "#00ffcc" if total_pnl >= 0 else "#ff5555"
                    pnl_sign_cur = "+" if total_pnl >= 0 else "-"
                    render_html(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:8px;">
                        <div>
                            <span style="font-size:15px; font-weight:700; color:#ffffff;">Account Balance Curve</span>
                            <span style="font-size:11px; color:#8a99ad; margin-left:8px;">Equity & Closed Balance trajectory</span>
                        </div>
                        <div style="display:flex; gap:20px; font-size:11px;">
                            <div><span style="color:#8a99ad;">Current P&L:</span> <b style="color:{pnl_color_cur}; font-size:14px;">{pnl_sign_cur}${abs(total_pnl):,.2f}</b></div>
                            <div><span style="color:#8a99ad;">Closed:</span> <b style="color:#ffffff; font-size:14px;">${current_balance:,.2f}</b></div>
                        </div>
                    </div>
                    """)
                    st.plotly_chart(
                        fig_balance, 
                        use_container_width=True, 
                        config={
                            'displayModeBar': False, 
                            'scrollZoom': False, 
                            'doubleClick': False, 
                            'showAxisDragHandles': False,
                            'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']
                        }
                    )

            with col_hero_side:
                # Winstreak & Period Returns card
                with st.container(border=True):
                    render_html(f"""
                    <div class="card-title">Winstreak & Returns</div>
                    <div class="streak-container" style="margin-top:8px;">
                        <div class="streak-item">
                            <span class="metric-label" style="font-size:10px;">Days Streak</span>
                            <div class="streak-badge-row">
                                <span class="streak-badge">{current_streak_days}</span>
                                <div class="streak-box active">{max_streak_days}</div>
                                <div class="streak-box">max</div>
                            </div>
                        </div>
                        <div class="streak-item">
                            <span class="metric-label" style="font-size:10px;">Trades Streak</span>
                            <div class="streak-badge-row">
                                <span class="streak-badge">{current_streak_trades}</span>
                                <div class="streak-box active">{max_streak_trades}</div>
                                <div class="streak-box">max</div>
                            </div>
                        </div>
                    </div>

                    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:6px; text-align:center; margin-top:14px; border-top:1px solid rgba(255,255,255,0.06); padding: 12px 0 6px 0;">
                        <div>
                            <div class="metric-label" style="font-size:9px; margin-bottom:2px;">Daily</div>
                            <div class="metric-value" style="font-size:11px; font-weight:700; color:{daily_color};">{avg_daily_ret:+.2f}%</div>
                        </div>
                        <div>
                            <div class="metric-label" style="font-size:9px; margin-bottom:2px;">Weekly</div>
                            <div class="metric-value" style="font-size:11px; font-weight:700; color:{weekly_color};">{weekly_ret:+.2f}%</div>
                        </div>
                        <div>
                            <div class="metric-label" style="font-size:9px; margin-bottom:2px;">Monthly</div>
                            <div class="metric-value" style="font-size:11px; font-weight:700; color:{monthly_color};">{monthly_ret:+.2f}%</div>
                        </div>
                        <div>
                            <div class="metric-label" style="font-size:9px; margin-bottom:2px;">Annual</div>
                            <div class="metric-value" style="font-size:11px; font-weight:700; color:{ann_color};">{ann_ret:+.2f}%</div>
                        </div>
                    </div>
                    """)

                # Wave Score Radar
                fig_radar = go.Figure()
                categories = ['Entry', 'Tempo', 'Stability', 'Exit', 'Risk', 'Entry']
                scores = [entry_score, tempo_score, stability_score, exit_score, risk_score, entry_score]

                fig_radar.add_trace(go.Scatterpolar(
                    r=scores,
                    theta=categories,
                    fill='toself',
                    fillcolor='rgba(255, 74, 138, 0.15)',
                    line=dict(color='#ff4a8a', width=1.5),
                    name='Wave Score'
                ))
                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=False, range=[0, 100]),
                        angularaxis=dict(gridcolor='rgba(255,255,255,0.05)', linecolor='rgba(255,255,255,0.05)', tickfont=dict(size=8, color='#8a99ad')),
                        bgcolor='rgba(0,0,0,0)'
                    ),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=20, r=20, t=8, b=8),
                    height=115,
                    showlegend=False,
                    annotations=[
                        dict(
                            text=str(wave_score),
                            x=0.5,
                            y=0.5,
                            font=dict(size=18, color='#ffffff', family='Arial', weight='bold'),
                            showarrow=False
                        )
                    ]
                )

                with st.container(border=True):
                    render_html('<div class="card-title" style="margin-bottom: 2px;">Wave Score Radar</div>')
                    st.plotly_chart(fig_radar, use_container_width=True, config={'displayModeBar': False})

            # ------------------
            # ROW 2 GRID (Gauges and Calendar)
            # ------------------
            col2_1, col2_2 = st.columns([2, 1.2])

            with col2_1:
                # Left side Gauges matrix (Design 2 Circular SVG meters)
                # 1. Profit Factor SVG Circle Dasharray calculation
                pf_dash = min(100, int((profit_factor / 3.0) * 100)) if profit_factor > 0 else 0

                # 2. Win Ratio Dasharray
                wr_dash = int(win_rate)

                # 3. Biggest Winner/Loser Gauge Ratio
                big_win_loss_ratio = biggest_win / abs(biggest_loss) if biggest_loss != 0 else 1.0
                bw_dash = min(100, int((big_win_loss_ratio / 5.0) * 100))

                # Progress bar percentages
                # Avg Winner / Loser split
                avg_win = filtered_df[filtered_df["net_profit"] > 0]["net_profit"].mean() if winning_trades > 0 else 0.0
                avg_loss = abs(filtered_df[filtered_df["net_profit"] <= 0]["net_profit"].mean()) if losing_trades > 0 else 0.0
                total_avg = avg_win + avg_loss
                win_bar_pct = (avg_win / total_avg) * 100 if total_avg > 0 else 50.0

                # Long / Short count split
                long_count = len(filtered_df[filtered_df["direction"] == "LONG"])
                short_count = len(filtered_df[filtered_df["direction"] == "SHORT"])
                total_ls = long_count + short_count
                long_bar_pct = (long_count / total_ls) * 100 if total_ls > 0 else 50.0

                render_html(f"""
                <div class="trading-card" style="height: 100%;">
                    <div class="card-title">Performance Analytics & Gauges</div>

                    <div class="gauge-matrix">
                        <!-- Gauge 1: Profit Factor -->
                        <div class="gauge-card">
                            <svg viewBox="0 0 36 36" style="width: 75px; height: 75px;">
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="3" />
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#00ffcc" stroke-dasharray="{pf_dash}, 100" stroke-width="3" stroke-linecap="round" />
                                <text x="18" y="21" font-size="8.5px" font-weight="bold" fill="#fff" text-anchor="middle">{profit_factor:.2f}</text>
                            </svg>
                            <div class="gauge-details">
                                <div class="gauge-title">Profit Factor</div>
                                <div class="gauge-sub-row">
                                    <span style="color:#00ffcc;">${gross_wins:,.2f}</span>
                                    <span style="color:#ff5555;">-${gross_losses:,.2f}</span>
                                </div>
                            </div>
                        </div>

                        <!-- Gauge 2: Win Ratio -->
                        <div class="gauge-card">
                            <svg viewBox="0 0 36 36" style="width: 75px; height: 75px;">
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="3" />
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#00ffcc" stroke-dasharray="{wr_dash}, 100" stroke-width="3" stroke-linecap="round" />
                                <text x="18" y="21" font-size="7.5px" font-weight="bold" fill="#fff" text-anchor="middle">{win_rate:.1f}%</text>
                            </svg>
                            <div class="gauge-details">
                                <div class="gauge-title">Win Ratio</div>
                                <div class="gauge-sub-row">
                                    <span style="color:#00ffcc;">Wins: {winning_trades}</span>
                                    <span style="color:#ff5555;">Losses: {losing_trades}</span>
                                </div>
                            </div>
                        </div>

                        <!-- Gauge 3: Biggest Win/Loss Ratio -->
                        <div class="gauge-card">
                            <svg viewBox="0 0 36 36" style="width: 75px; height: 75px;">
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="3" />
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#00ffcc" stroke-dasharray="{bw_dash}, 100" stroke-width="3" stroke-linecap="round" />
                                <text x="18" y="21" font-size="8.5px" font-weight="bold" fill="#fff" text-anchor="middle">{big_win_loss_ratio:.1f}</text>
                            </svg>
                            <div class="gauge-details">
                                <div class="gauge-title">Max Win/Loss Ratio</div>
                                <div class="gauge-sub-row">
                                    <span style="color:#00ffcc;">${biggest_win:,.2f}</span>
                                    <span style="color:#ff5555;">-${abs(biggest_loss):,.2f}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Progress Bars: Ratios Row -->
                    <div class="ratios-row">
                        <!-- Avg Winner/Loser -->
                        <div class="ratio-card">
                            <div class="ratio-label-row">
                                <span>Avg Winner/Loser</span>
                                <span>{win_bar_pct:.1f}% / {(100-win_bar_pct):.1f}%</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:700; margin-top:4px;">
                                <span style="color:#00ffcc;">+${avg_win:,.2f}</span>
                                <span style="color:#ff5555;">-${avg_loss:,.2f}</span>
                            </div>
                            <div class="ratio-bar-bg">
                                <div class="ratio-bar-green" style="width: {win_bar_pct}%;"></div>
                                <div class="ratio-bar-red" style="width: {100-win_bar_pct}%;"></div>
                            </div>
                        </div>

                        <!-- Long/Short count -->
                        <div class="ratio-card">
                            <div class="ratio-label-row">
                                <span>Long / Short Counts</span>
                                <span>{long_bar_pct:.1f}% / {(100-long_bar_pct):.1f}%</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:700; margin-top:4px;">
                                <span style="color:#00ffcc;">L: {long_count}</span>
                                <span style="color:#ff5555;">S: {short_count}</span>
                            </div>
                            <div class="ratio-bar-bg">
                                <div class="ratio-bar-green" style="width: {long_bar_pct}%;"></div>
                                <div class="ratio-bar-red" style="width: {100-long_bar_pct}%;"></div>
                            </div>
                        </div>
                    </div>
                </div>
                """)

            with col2_2:
                # Custom Monday-first Trading Calendar Grid in unified container
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

                    # 100% Pure HTML Flexbox Navigation Header (Guaranteed single horizontal line on all screens)
                    render_html(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 8px;">
                        <div style="font-size: 16px; font-weight: 700; color: #ffffff; letter-spacing: -0.2px;">{month_name} {st.session_state.cal_year}</div>
                        <div style="display: flex; gap: 6px;">
                            <a href="?cal_m={prev_m}&cal_y={prev_y}" target="_self" class="cal-nav-link-btn" title="Previous Month">‹</a>
                            <a href="?cal_m={next_m}&cal_y={next_y}" target="_self" class="cal-nav-link-btn" title="Next Month">›</a>
                        </div>
                    </div>
                    """)

                    # Process monthly stats
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

                    # Format month signs consistently
                    month_pnl_sign = "+" if month_profits >= 0 else "-"
                    month_gain_sign = "+" if month_gain_pct >= 0 else "-"

                    # Show summary stats above calendar
                    render_html(f"""
                    <div style="background: rgba(255,255,255,0.02); padding: 6px 12px; border-radius: 6px; font-size:11px; margin-bottom:8px; display:flex; gap:16px; font-weight:600;">
                        <span style="color:#8a99ad;">T: <b style="color:#fff;">{month_total_trades}</b></span>
                        <span style="color:#8a99ad;">W: <b style="color:#00ffcc;">{month_wins}</b></span>
                        <span style="color:#8a99ad;">PnL: <b style="color:{'#00ffcc' if month_profits >= 0 else '#ff5555'};">{month_pnl_sign}${abs(month_profits):,.2f}</b></span>
                        <span style="color:#8a99ad;">Gain: <b style="color:{'#00ffcc' if month_gain_pct >= 0 else '#ff5555'};">{month_gain_sign}{abs(month_gain_pct):.1f}%</b></span>
                    </div>
                    """)

                    # Render HTML calendar grid (without the outer trading-card div wrapper since st.container provides the border card layout)
                    cal_html = '<div class="calendar-grid">'

                    # Day Headers (Monday first!)
                    days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    for day_h in days_header:
                        cal_html += f'<div class="calendar-day-header">{day_h}</div>'

                    # Get first weekday of the month (0 = Monday, 6 = Sunday)
                    first_weekday, num_days = calendar.monthrange(st.session_state.cal_year, st.session_state.cal_month)

                    # Padding empty cells before the 1st of the month
                    for _ in range(first_weekday):
                        cal_html += '<div></div>'

                    monthly_daily_pnl = month_trades.groupby(month_trades["exit_time"].dt.day)["net_profit"].sum().to_dict()

                    # Render calendar days
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

                    # Padding empty trailing cells after the last day to complete the week row
                    trailing_empty = (7 - (first_weekday + num_days) % 7) % 7
                    for _ in range(trailing_empty):
                        cal_html += '<div style="background: rgba(255, 255, 255, 0.01); border: 1px dashed rgba(255, 255, 255, 0.025); border-radius: 6px; min-height: 52px;"></div>'

                    cal_html += '</div><div style="height: 6px;"></div>'
                    render_html(cal_html)

            # ------------------
            # ROW 3 TABS (Journal & Analytics Charts)
            # ------------------
            st.markdown("---")
            tab_journal, tab_charts = st.tabs(["Trades Journal & Open Positions", "Trade Performance Charts"])

            with tab_journal:
                # ------------------------------------
                # 1. LIVE ACTIVE OPEN POSITIONS TRAY
                # ------------------------------------
                if not df_open.empty:
                    open_rows_html = ""
                    for idx, pos in df_open.iterrows():
                        pos_id_raw = str(pos["position_id"])
                        t_disp = "#" + pos_id_raw.replace("MT5_", "").replace("CAP_", "")
                        sym = str(pos["symbol"]).upper()
                        dir_str = str(pos["direction"]).upper()
                        dir_badge = f'<span class="badge-dir-long">↑ {dir_str}</span>' if "BUY" in dir_str or "LONG" in dir_str else f'<span class="badge-dir-short">↓ {dir_str}</span>'
                        vol = float(pos.get("volume", 0.0))
                        vol_disp = f"{vol:,.2f}" if vol < 1000 else f"{vol:,.0f}"
                        entry_px = float(pos.get("entry_price", 0.0))
                        curr_px = float(pos.get("current_price", 0.0))
                        fl_pnl = float(pos.get("floating_pnl", 0.0))
                        sl_val = float(pos.get("sl", 0.0))
                        tp_val = float(pos.get("tp", 0.0))
                        sl_disp = f"{sl_val:.5f}" if sl_val > 0 else "—"
                        tp_disp = f"{tp_val:.5f}" if tp_val > 0 else "—"

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
                            <td style="font-family:monospace; color:#8a99ad;">{entry_px:.5f}</td>
                            <td style="font-family:monospace; color:#00ffcc;">{curr_px:.5f}</td>
                            <td style="font-family:monospace; color:#ff5555; font-size:11px;">{sl_disp}</td>
                            <td style="font-family:monospace; color:#00ffcc; font-size:11px;">{tp_disp}</td>
                            <td>{pnl_badge}</td>
                            <td style="font-size:11px; color:#8a99ad;">{open_t_str}</td>
                        </tr>
                        """

                    render_html(f"""
                    <div style="margin-bottom: 24px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:8px;">
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#00ffcc; box-shadow: 0 0 10px #00ffcc;"></span>
                                <span style="font-size:14px; font-weight:700; color:#ffffff;">Active Open Positions ({len(df_open)})</span>
                            </div>
                            <div style="font-size:12px;">
                                <span style="color:#8a99ad;">Total Floating P&L:</span> 
                                <b style="color:{unrealized_color}; font-size:14px; margin-left:4px;">{unrealized_sign}${abs(unrealized_pnl):,.2f}</b>
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
                else:
                    render_html("""
                    <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:10px 16px; margin-bottom:20px;">
                        <div style="display:flex; align-items:center; gap:8px; font-size:12px; color:#8a99ad;">
                            <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#8a99ad;"></span>
                            <span>No active open positions. Watching markets for trade setups.</span>
                        </div>
                        <span style="font-size:11px; color:#8a99ad; font-family:monospace;">Floating P&L: $0.00</span>
                    </div>
                    """)

                # ------------------------------------
                # 2. CLOSED TRADES JOURNAL
                # ------------------------------------
                st.markdown('<div style="font-size:14px; font-weight:700; color:#ffffff; margin-bottom:10px;">Closed Trades Journal</div>', unsafe_allow_html=True)
                df_display = filtered_df.sort_values(by="exit_time", ascending=False).copy()

                # Build Rich Styled HTML Table with Profit Green and Loss Red
                table_rows_html = ""
                for idx, row in df_display.iterrows():
                    trade_id_raw = str(row["trade_id"])
                    # Clean ticket presentation
                    if trade_id_raw.startswith("MT5_"):
                        ticket_disp = "#" + trade_id_raw.split("_")[-1]
                        acc_disp = "MT5 (Funded)"
                    else:
                        ticket_disp = "#" + trade_id_raw.split("-")[1] if "-" in trade_id_raw else "#" + trade_id_raw[:8]
                        acc_disp = "Capital (Real)"

                    sym = str(row["symbol"]).upper()
                    direction = str(row["direction"]).upper()
                    dir_badge = f'<span class="badge-dir-long">↑ {direction}</span>' if "LONG" in direction or "BUY" in direction else f'<span class="badge-dir-short">↓ {direction}</span>'

                    vol = float(row.get("volume", 0.0))
                    vol_disp = f"{vol:,.2f}" if vol < 1000 else f"{vol:,.0f}"

                    entry_px = float(row.get("entry_price", 0.0))
                    exit_px = float(row.get("exit_price", 0.0))
                    net_pnl = float(row.get("net_profit", 0.0))

                    if net_pnl > 0:
                        pnl_badge = f'<span class="badge-pnl-win">+${net_pnl:,.2f}</span>'
                    elif net_pnl < 0:
                        pnl_badge = f'<span class="badge-pnl-loss">-${abs(net_pnl):,.2f}</span>'
                    else:
                        pnl_badge = '<span style="color:#8a99ad; font-weight:600;">$0.00</span>'

                    # Quality Score computation
                    pnl_pct = abs(net_pnl) / initial_balance * 100
                    if net_pnl > 0:
                        q_score = min(98, int(75 + (net_pnl / initial_balance * 500)))
                        q_badge = f'<span class="badge-quality badge-quality-high">{q_score} GOOD</span>'
                    else:
                        q_score = max(12, int(65 - (pnl_pct * 30)))
                        if q_score >= 40:
                            q_badge = f'<span class="badge-quality badge-quality-med">{q_score} AVG</span>'
                        else:
                            q_badge = f'<span class="badge-quality badge-quality-low">{q_score} POOR</span>'

                    entry_time_str = pd.to_datetime(row["entry_time"]).strftime("%Y-%m-%d %H:%M")
                    exit_time_str = pd.to_datetime(row["exit_time"]).strftime("%Y-%m-%d %H:%M")
                    dur = float(row.get("duration_minutes", 0.0))
                    dur_str = f"{dur:.1f} min" if dur < 60 else f"{dur/60:.1f} hrs"

                    tag_raw = row.get("setup_tag")
                    tag_disp = f'<span class="badge-tag-pill">{tag_raw}</span>' if pd.notna(tag_raw) and str(tag_raw).strip() != "" and str(tag_raw) != "None" else '<span style="color:#4a5568; font-size:10px;">—</span>'

                    table_rows_html += f"""
                    <tr>
                        <td style="font-family:monospace; font-size:11px; color:#8a99ad;">{ticket_disp}</td>
                        <td style="font-size:11px; color:#c084fc;">{acc_disp}</td>
                        <td style="font-weight:700; color:#ffffff;">{sym}</td>
                        <td>{dir_badge}</td>
                        <td style="font-family:monospace;">{vol_disp}</td>
                        <td style="font-family:monospace; color:#8a99ad;">{entry_px:.5f}</td>
                        <td style="font-family:monospace; color:#8a99ad;">{exit_px:.5f}</td>
                        <td>{pnl_badge}</td>
                        <td>{q_badge}</td>
                        <td style="font-size:11px; color:#8a99ad;">{entry_time_str}</td>
                        <td style="font-size:11px; color:#8a99ad;">{exit_time_str}</td>
                        <td style="font-size:11px; color:#8a99ad;">{dur_str}</td>
                        <td>{tag_disp}</td>
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
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_html}
                        </tbody>
                    </table>
                </div>
                """)

                with st.expander("Tag Editor (Categorize Setups)", expanded=False):
                    st.write("Double-click on the **setup_tag** column below to categorize your trades. Click **Save Tags** to write changes.")
                    edited_df = st.data_editor(
                        df_display[[
                            "trade_id", "symbol", "direction", "net_profit", "exit_time", "setup_tag"
                        ]],
                        column_config={
                            "trade_id": st.column_config.TextColumn("Trade ID", disabled=True),
                            "symbol": st.column_config.TextColumn("Symbol", disabled=True),
                            "direction": st.column_config.TextColumn("Dir", disabled=True),
                            "net_profit": st.column_config.NumberColumn("Net PnL ($)", disabled=True, format="$%.2f"),
                            "exit_time": st.column_config.DatetimeColumn("Exit Time", disabled=True),
                            "setup_tag": st.column_config.TextColumn("Setup Tag")
                        },
                        hide_index=True,
                        use_container_width=True
                    )

                    if st.button("Save Tags", type="primary"):
                        changes_saved = 0
                        for idx, row in edited_df.iterrows():
                            trade_id = row["trade_id"]
                            new_tag = row["setup_tag"]

                            original_tag = df_display[df_display["trade_id"] == trade_id]["setup_tag"].values[0]
                            original_tag = None if pd.isna(original_tag) else str(original_tag)
                            new_tag = None if pd.isna(new_tag) or new_tag == "" or new_tag is None else str(new_tag)

                            if original_tag != new_tag:
                                database.update_setup_tag(trade_id, new_tag)
                                changes_saved += 1

                        if changes_saved > 0:
                            st.success(f"Saved {changes_saved} setup tags to the database!")
                            st.rerun()
                        else:
                            st.info("No tag modifications detected.")

            with tab_charts:
                st.subheader("Performance Breakdown")
                col_ch1, col_ch2 = st.columns(2)

                with col_ch1:
                    # Performance by Symbol
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
                    # Performance by Strategy Setup Tag
                    tag_pnl = filtered_df.fillna("Untagged").groupby("setup_tag")["net_profit"].sum().reset_index()
                    fig_tag = px.bar(
                        tag_pnl,
                        x="setup_tag",
                        y="net_profit",
                        title="Net Profit by Setup Tag",
                        labels={"setup_tag": "Setup / Strategy", "net_profit": "Net PnL ($)"},
                        color="net_profit",
                        color_continuous_scale=["#ff5555", "#00ffcc"],
                        template="plotly_dark"
                    )
                    fig_tag.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_tag, use_container_width=True)

render_live_dashboard()
