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

# Page Config
st.set_page_config(page_title="Trade Logger & Analytics", layout="wide", page_icon="📈")

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
    
    /* Hide Streamlit top header white bar and footer */
    [data-testid="stHeader"], header {
        background: transparent !important;
        background-color: rgba(0, 0, 0, 0) !important;
        height: 0px !important;
    }
    
    /* Adjust Streamlit main container top padding to remove excessive spacing */
    .stMainBlockContainer {
        padding-top: 1.5rem !important;
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
    /* RESPONSIVE & MOBILE ACCESSIBILITY  */
    /* ---------------------------------- */
    @media (max-width: 991px) {
        .top-stats-container {
            grid-template-columns: repeat(3, 1fr) !important;
            gap: 12px !important;
        }
        
        .gauge-matrix {
            grid-template-columns: repeat(2, 1fr) !important;
        }
    }
    
    @media (max-width: 768px) {
        /* Stack the main container margins for mobile */
        .stMainBlockContainer {
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            padding-top: 1rem !important;
        }
        
        /* Stack top stats bar */
        .top-stats-container {
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 10px !important;
        }
        
        /* Stack gauges matrix */
        .gauge-matrix {
            grid-template-columns: 1fr !important;
            gap: 12px !important;
        }
        
        /* Make gauge cards column-flex for small widths */
        .gauge-card {
            flex-direction: column !important;
            text-align: center !important;
            padding: 12px !important;
        }
        
        .gauge-details {
            margin-top: 8px !important;
        }
        
        /* Stack progress bars row on mobile */
        div[style*="display: grid; grid-template-columns: 1fr 1fr"] {
            grid-template-columns: 1fr !important;
            gap: 12px !important;
        }
        
        /* Adjust calendar cell height and padding on mobile */
        .calendar-cell {
            min-height: 52px !important;
            padding: 6px !important;
        }
        
        .calendar-day-num {
            font-size: 11px !important;
        }
        
        .calendar-day-val {
            font-size: 10px !important;
        }
        
        .calendar-day-pct {
            font-size: 8px !important;
        }
        
        /* Stack top-level main grid columns only on mobile */
        .main div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:not(:has(button[key="prev_btn"])):not(:has(button[key="next_btn"])) {
            flex: 1 1 100% !important;
            width: 100% !important;
        }
    }

    /* Clean Calendar Navigation & Chevron Buttons */
    .cal-title-text {
        font-size: 15px;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.2px;
        line-height: 28px;
    }

    div[data-testid="stHorizontalBlock"]:has(button[key="prev_btn"]),
    div[data-testid="stHorizontalBlock"]:has(button[key="next_btn"]) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 6px !important;
        margin-bottom: 4px !important;
    }

    div[data-testid="stHorizontalBlock"]:has(button[key="prev_btn"]) > div[data-testid="column"],
    div[data-testid="stHorizontalBlock"]:has(button[key="next_btn"]) > div[data-testid="column"] {
        min-width: 0 !important;
        width: auto !important;
        flex: 0 0 auto !important;
    }

    div[data-testid="stHorizontalBlock"]:has(button[key="prev_btn"]) > div[data-testid="column"]:first-child,
    div[data-testid="stHorizontalBlock"]:has(button[key="next_btn"]) > div[data-testid="column"]:first-child {
        flex: 1 1 auto !important;
        min-width: 140px !important;
    }
</style>
""", unsafe_allow_html=True)

# Fetch Trades
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
    
    # Initialize per-account initial balances in session state
    if "account_balances" not in st.session_state:
        st.session_state.account_balances = {
            "ALL": 11000.0,
        }

    unique_accounts = sorted(list(df_trades["account_id"].unique()))
    account_options = unique_accounts + (["ALL"] if len(unique_accounts) > 1 else [])

    def format_account_name(acc_id):
        if acc_id == "ALL":
            return "All Accounts (Combined)"
        elif str(acc_id).startswith("MT5_"):
            return f"MetaTrader 5 ({str(acc_id).replace('MT5_', '')})"
        else:
            return f"Capital.com ({acc_id})"

    # Populate default starting balances per account
    for acc in unique_accounts:
        if acc not in st.session_state.account_balances:
            if str(acc).startswith("MT5_"):
                st.session_state.account_balances[acc] = 10000.0
            else:
                st.session_state.account_balances[acc] = 1000.0

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
            col_mt5, col_cap = st.columns([1, 1])
            with col_mt5:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button("Sync MT5", key="active_sync_mt5", use_container_width=True):
                    with st.spinner("Syncing MT5..."):
                        success = mt5_sync.sync_mt5()
                        if success:
                            st.success("MT5 sync completed!")
                            st.rerun()
                        else:
                            st.error("MT5 sync failed.")
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
            current_default_bal = st.session_state.account_balances.get(selected_account, 1000.0)
            initial_balance = st.number_input(
                "Starting Balance ($)",
                min_value=10.0,
                value=float(current_default_bal),
                step=100.0,
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
        
        # ------------------
        # METRICS COMPUTATION
        # ------------------
        filtered_df["balance"] = initial_balance + filtered_df["net_profit"].cumsum()
        current_balance = filtered_df["balance"].iloc[-1]
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

        # ------------------
        # TOP STATS BAR
        # ------------------
        sign_pnl = "+" if total_pnl >= 0 else "-"
        color_pnl = "#00ffcc" if total_pnl >= 0 else "#ff5555"
        render_html(f"""
        <div class="top-stats-container">
            <div class="top-stat-box">
                <div class="top-stat-label">Gross Profit (Loss)</div>
                <div class="top-stat-value" style="color: #00ffcc;">${gross_wins:,.2f}</div>
            </div>
            <div class="top-stat-box">
                <div class="top-stat-label">Net Profit</div>
                <div class="top-stat-value" style="color: {color_pnl};">{sign_pnl}${abs(total_pnl):,.2f}</div>
            </div>
            <div class="top-stat-box">
                <div class="top-stat-label">Balance</div>
                <div class="top-stat-value">${current_balance:,.2f}</div>
            </div>
            <div class="top-stat-box">
                <div class="top-stat-label">Avg Holding Time</div>
                <div class="top-stat-value" style="font-size: 18px; line-height: 28px;">{hold_time_str}</div>
            </div>
            <div class="top-stat-box">
                <div class="top-stat-label">SQN</div>
                <div class="top-stat-value" style="color: {'#00ffcc' if sqn >= 1.5 else ('#ff5555' if sqn < 0 else '#ffffff')};">{sqn:.2f}</div>
            </div>
            <div class="top-stat-box">
                <div class="top-stat-label">Max Drawdown</div>
                <div class="top-stat-value" style="color: #ff5555;">{max_drawdown:.2f}%</div>
            </div>
        </div>
        """)

        # ------------------
        # ROW 1 GRID
        # ------------------
        col1_1, col1_2, col1_3 = st.columns([1, 1, 1.2])
        
        with col1_1:
            # Winstreak + Period Returns card
            render_html(f"""
            <div class="trading-card" style="height: 100%;">
                <div class="card-title">Winstreak & Period Returns</div>
                <div class="streak-container">
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
                
                <hr style="border:0; border-top:1px solid rgba(255,255,255,0.05); margin:16px 0;">
                
                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:4px; text-align:center; margin-top:10px;">
                    <div>
                        <div class="metric-label" style="font-size:9px;">Daily</div>
                        <div class="metric-value" style="font-size:12px; color:{daily_color};">{avg_daily_ret:+.2f}%</div>
                    </div>
                    <div>
                        <div class="metric-label" style="font-size:9px;">Weekly</div>
                        <div class="metric-value" style="font-size:12px; color:{weekly_color};">{weekly_ret:+.2f}%</div>
                    </div>
                    <div>
                        <div class="metric-label" style="font-size:9px;">Monthly</div>
                        <div class="metric-value" style="font-size:12px; color:{monthly_color};">{monthly_ret:+.2f}%</div>
                    </div>
                    <div>
                        <div class="metric-label" style="font-size:9px;">Annualized</div>
                        <div class="metric-value" style="font-size:12px; color:{ann_color};">{ann_ret:+.2f}%</div>
                    </div>
                </div>
            </div>
            """)
            
        with col1_2:
            # Wave Score Radar + Top Sessions card
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
                margin=dict(l=25, r=25, t=10, b=10),
                height=130,
                showlegend=False,
                annotations=[
                    dict(
                        text=str(wave_score),
                        x=0.5,
                        y=0.5,
                        font=dict(size=20, color='#ffffff', family='Arial', weight='bold'),
                        showarrow=False
                    )
                ]
            )
            
            with st.container(border=True):
                render_html('<div class="card-title" style="margin-bottom: 2px;">Wave Score Radar</div>')
                st.plotly_chart(fig_radar, use_container_width=True, config={'displayModeBar': False})
                render_html(f"""
                <div style="display:flex; justify-content:space-between; font-size:10px; border-top:1px solid rgba(255,255,255,0.05); padding-top:8px;">
                    <span style="color:#8a99ad;">Most Active: <b>{most_active_sess}</b></span>
                    <span style="color:#8a99ad;">Best Day: <b style="color:#00ffcc;">{most_prof_sess}</b></span>
                </div>
                """)
            
        with col1_3:
            # Balance Line Curve
            fig_balance = go.Figure()
            time_formatted = filtered_df["exit_time"].dt.strftime("%d %b")
            
            fig_balance.add_trace(go.Scatter(
                x=time_formatted,
                y=filtered_df["balance"],
                mode='lines',
                line=dict(color='#00bfff', width=2, shape='spline'),
                fill='tozeroy',
                fillcolor='rgba(0, 191, 255, 0.06)',
                name='Balance'
            ))
            fig_balance.update_layout(
                xaxis=dict(
                    showgrid=False,
                    linecolor='rgba(255,255,255,0.05)',
                    tickfont=dict(color='#8a99ad', size=9),
                    tickmode='auto',
                    nticks=5
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.02)',
                    linecolor='rgba(255,255,255,0.05)',
                    tickfont=dict(color='#8a99ad', size=9)
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=10, r=10, t=10, b=10),
                height=180,
                showlegend=False
            )
            
            with st.container(border=True):
                render_html(f"""
                <div class="card-title" style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                    <span>Balance Curve</span>
                    <span style="color:#00bfff; font-weight:700;">${current_balance:,.2f}</span>
                </div>
                """)
                st.plotly_chart(fig_balance, use_container_width=True, config={'displayModeBar': False})

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
                    
                col_h1, col_h2, col_h3 = st.columns([5, 1, 1])
                with col_h1:
                    month_name = calendar.month_name[st.session_state.cal_month]
                    render_html(f"<div class='cal-title-text'>{month_name} {st.session_state.cal_year}</div>")
                with col_h2:
                    if st.button("‹", key="prev_btn", help="Previous Month", use_container_width=True):
                        st.session_state.cal_month -= 1
                        if st.session_state.cal_month == 0:
                            st.session_state.cal_month = 12
                            st.session_state.cal_year -= 1
                        st.rerun()
                with col_h3:
                    if st.button("›", key="next_btn", help="Next Month", use_container_width=True):
                        st.session_state.cal_month += 1
                        if st.session_state.cal_month == 13:
                            st.session_state.cal_month = 1
                            st.session_state.cal_year += 1
                        st.rerun()
    
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
                    
                cal_html += '</div>'
                render_html(cal_html)

        # ------------------
        # ROW 3 TABS (Journal & Analytics Charts)
        # ------------------
        st.markdown("---")
        tab_journal, tab_charts = st.tabs(["Closed Trades Journal", "Trade Performance Charts"])
        
        with tab_journal:
            st.write("Double-click on the **setup_tag** column below to categorize your trades. Click **Save Tags** to write changes.")
            
            df_display = filtered_df.sort_values(by="exit_time", ascending=False).copy()
            
            edited_df = st.data_editor(
                df_display[[
                    "trade_id", "account_id", "symbol", "direction", "volume", 
                    "entry_price", "exit_price", "net_profit", "entry_time", 
                    "exit_time", "duration_minutes", "setup_tag"
                ]],
                column_config={
                    "trade_id": st.column_config.TextColumn("Trade ID", disabled=True),
                    "account_id": st.column_config.TextColumn("Account", disabled=True),
                    "symbol": st.column_config.TextColumn("Symbol", disabled=True),
                    "direction": st.column_config.TextColumn("Dir", disabled=True),
                    "volume": st.column_config.NumberColumn("Lots", disabled=True, format="%.2f"),
                    "entry_price": st.column_config.NumberColumn("Entry Px", disabled=True, format="%.5f"),
                    "exit_price": st.column_config.NumberColumn("Exit Px", disabled=True, format="%.5f"),
                    "net_profit": st.column_config.NumberColumn("Net PnL ($)", disabled=True, format="$%.2f"),
                    "entry_time": st.column_config.DatetimeColumn("Entry Time", disabled=True),
                    "exit_time": st.column_config.DatetimeColumn("Exit Time", disabled=True),
                    "duration_minutes": st.column_config.NumberColumn("Duration (Min)", disabled=True, format="%.1f"),
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
