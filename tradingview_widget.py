import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit.components.v1 import html
import os

DEFAULT_SYMBOLS = {
    "Gold (XAU/USD)": "OANDA:XAUUSD",
    "US Tech 100 (Nasdaq)": "FOREXCOM:NAS100USD",
    "US 500 (S&P 500)": "FOREXCOM:SPX500USD",
    "EUR/USD": "FX:EURUSD",
    "GBP/USD": "FX:GBPUSD",
    "USD/JPY": "FX:USDJPY",
    "Bitcoin (BTC/USDT)": "BINANCE:BTCUSDT",
    "US Crude Oil": "TVC:USOIL"
}

def render_tradingview_chart(symbol="OANDA:XAUUSD", interval="15", height=700, custom_layout_url=None):
    """
    Renders an interactive TradingView Advanced Real-Time Pro Suite Chart.
    Supports standard Pro Chart with localStorage drawing persistence or personal TradingView cloud layout.
    """
    if custom_layout_url and custom_layout_url.strip():
        # User provided their own personal TradingView cloud layout link
        clean_url = custom_layout_url.strip()
        if not clean_url.startswith("http"):
            clean_url = "https://" + clean_url
            
        tv_html = f"""
        <div class="tradingview-widget-container" style="height:100%;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.5);border:1px solid rgba(0,255,204,0.2);">
            <iframe src="{clean_url}" style="width:100%; height:{height}px; border:none;" allow="clipboard-write; storage-access; cookies; camera"></iframe>
        </div>
        """
        html(tv_html, height=height + 20)
        return

    # Standard Pro TradingView Widget (without forced default studies so user changes persist)
    container_id = "tradingview_pro_suite_canvas"

    tv_html = f"""
    <!-- TradingView Advanced Pro Widget -->
    <div class="tradingview-widget-container" style="height:100%;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.5);border:1px solid rgba(0,255,204,0.2);">
      <div id="{container_id}" style="height:{height}px;width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "{symbol}",
        "interval": "{interval}",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#0e131f",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "hide_top_toolbar": false,
        "allow_symbol_change": true,
        "save_image": true,
        "withdateranges": true,
        "details": true,
        "hotlist": false,
        "calendar": false,
        "show_popup_button": true,
        "popup_width": "1200",
        "popup_height": "800",
        "container_id": "{container_id}",
        "enabled_features": [
          "use_localstorage_for_settings",
          "save_chart_properties_to_local_storage",
          "study_templates",
          "side_toolbar_in_fullscreen_mode",
          "header_in_fullscreen_mode"
        ],
        "overrides": {{
          "paneProperties.background": "#0a0e17",
          "paneProperties.vertGridProperties.color": "rgba(255, 255, 255, 0.04)",
          "paneProperties.horzGridProperties.color": "rgba(255, 255, 255, 0.04)",
          "mainSeriesProperties.candleStyle.upColor": "#00ffcc",
          "mainSeriesProperties.candleStyle.downColor": "#ff5555",
          "mainSeriesProperties.candleStyle.drawWick": true,
          "mainSeriesProperties.candleStyle.drawBorder": true,
          "mainSeriesProperties.candleStyle.borderColor": "#00ffcc",
          "mainSeriesProperties.candleStyle.borderUpColor": "#00ffcc",
          "mainSeriesProperties.candleStyle.borderDownColor": "#ff5555",
          "mainSeriesProperties.candleStyle.wickUpColor": "#00ffcc",
          "mainSeriesProperties.candleStyle.wickDownColor": "#ff5555"
        }}
      }}
      );
      </script>
    </div>
    """
    html(tv_html, height=height + 20)

def fetch_mt5_candles(symbol="XAUUSD", timeframe="1h", count=150):
    """
    Fetches real OHLC candlestick rates directly from MetaTrader 5 terminal.
    """
    try:
        import mt5_sync
        if not mt5_sync.MT5_AVAILABLE:
            return None
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return None

        tf_map = {
            "1m": mt5.TIMEFRAME_M1,
            "5m": mt5.TIMEFRAME_M5,
            "15m": mt5.TIMEFRAME_M15,
            "1h": mt5.TIMEFRAME_H1,
            "4h": mt5.TIMEFRAME_H4,
            "D": mt5.TIMEFRAME_D1
        }
        mt5_tf = tf_map.get(timeframe, mt5.TIMEFRAME_H1)
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        mt5.shutdown()

        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
    except Exception as e:
        print(f"Error fetching MT5 candles: {e}")
    return None

def render_broker_candlestick_overlay(symbol="XAUUSD", df_trades=None, df_open=None, timeframe="1h", count=150):
    """
    Renders an interactive Broker Candlestick Chart with YOUR REAL trades,
    execution entry/exit points, profit badges, and SL/TP levels overlaid directly on the candles!
    """
    df_candles = fetch_mt5_candles(symbol=symbol, timeframe=timeframe, count=count)
    
    if df_candles is None or df_candles.empty:
        st.warning(f"Could not connect to live broker price feed for {symbol}. Ensure MT5 is running on your PC.")
        return

    # Base Candlestick Chart
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df_candles['time'],
        open=df_candles['open'],
        high=df_candles['high'],
        low=df_candles['low'],
        close=df_candles['close'],
        name=f"{symbol} Candlesticks",
        increasing_line_color='#00ffcc',
        decreasing_line_color='#ff5555',
        increasing_fillcolor='#00ffcc',
        decreasing_fillcolor='#ff5555'
    ))

    # 1. Overlay Closed Trades on this Symbol
    if df_trades is not None and not df_trades.empty:
        # Match symbol (e.g. XAUUSD, GOLD, etc.)
        sym_clean = symbol.upper().replace("/", "").replace("-", "")
        trades_sym = df_trades[df_trades["symbol"].str.upper().apply(lambda s: sym_clean in s or s in sym_clean)]

        if not trades_sym.empty:
            for idx, tr in trades_sym.iterrows():
                entry_t = pd.to_datetime(tr["entry_time"])
                exit_t = pd.to_datetime(tr["exit_time"])
                entry_px = float(tr.get("entry_price", 0.0))
                exit_px = float(tr.get("exit_price", 0.0))
                pnl = float(tr.get("net_profit", 0.0))
                direction = str(tr.get("direction", "BUY")).upper()
                is_buy = "BUY" in direction or "LONG" in direction
                pnl_col = "#00ffcc" if pnl >= 0 else "#ff5555"
                pnl_sign = "+" if pnl >= 0 else "-"
                ticket_id = str(tr.get("trade_id", "")).replace("MT5_", "").replace("CAP_", "")

                # A. Entry Marker
                fig.add_trace(go.Scatter(
                    x=[entry_t],
                    y=[entry_px],
                    mode="markers+text",
                    marker=dict(
                        symbol="triangle-up" if is_buy else "triangle-down",
                        size=14,
                        color="#00ffcc" if is_buy else "#ff5555",
                        line=dict(color="#ffffff", width=1.5)
                    ),
                    text=[f"{'BUY' if is_buy else 'SELL'} #{ticket_id}"],
                    textposition="bottom center" if is_buy else "top center",
                    textfont=dict(color="#ffffff", size=10, family="Inter"),
                    name=f"Entry #{ticket_id}",
                    hoverinfo="text",
                    hovertext=f"<b>ENTRY: {direction}</b><br>Price: ${entry_px:,.2f}<br>Time: {entry_t.strftime('%Y-%m-%d %H:%M')}"
                ))

                # B. Exit Marker
                fig.add_trace(go.Scatter(
                    x=[exit_t],
                    y=[exit_px],
                    mode="markers+text",
                    marker=dict(
                        symbol="circle",
                        size=11,
                        color=pnl_col,
                        line=dict(color="#ffffff", width=1.5)
                    ),
                    text=[f"{pnl_sign}${abs(pnl):,.2f}"],
                    textposition="top right",
                    textfont=dict(color=pnl_col, size=11, family="Inter", weight="bold"),
                    name=f"Exit #{ticket_id}",
                    hoverinfo="text",
                    hovertext=f"<b>EXIT #{ticket_id}</b><br>Net PnL: <b>{pnl_sign}${abs(pnl):,.2f}</b><br>Exit Price: ${exit_px:,.2f}<br>Time: {exit_t.strftime('%Y-%m-%d %H:%M')}"
                ))

                # C. Dashed Trajectory Line connecting Entry to Exit
                fig.add_trace(go.Scatter(
                    x=[entry_t, exit_t],
                    y=[entry_px, exit_px],
                    mode="lines",
                    line=dict(color=pnl_col, width=1.8, dash="dot"),
                    hoverinfo="skip",
                    showlegend=False
                ))

    # 2. Overlay Live Open Positions
    if df_open is not None and not df_open.empty:
        sym_clean = symbol.upper().replace("/", "").replace("-", "")
        open_sym = df_open[df_open["symbol"].str.upper().apply(lambda s: sym_clean in s or s in sym_clean)]

        if not open_sym.empty:
            for idx, op in open_sym.iterrows():
                o_entry = float(op.get("entry_price", 0.0))
                o_sl = float(op.get("sl", 0.0))
                o_tp = float(op.get("tp", 0.0))
                o_fl = float(op.get("floating_pnl", 0.0))
                o_pnl_col = "#00ffcc" if o_fl >= 0 else "#ff5555"
                o_dir = str(op.get("direction", "BUY")).upper()
                o_t_str = pd.to_datetime(op.get("open_time"))

                # Live Entry Level
                fig.add_hline(
                    y=o_entry,
                    line_dash="dash",
                    line_color="#00ffcc",
                    line_width=1.5,
                    annotation_text=f"LIVE OPEN: {o_dir} (${o_entry:,.2f} • {('+' if o_fl >= 0 else '-')}${abs(o_fl):,.2f})",
                    annotation_position="top left",
                    annotation_font=dict(color="#00ffcc", size=10)
                )

                # Stop Loss line
                if o_sl > 0:
                    fig.add_hline(
                        y=o_sl,
                        line_dash="dot",
                        line_color="#ff5555",
                        line_width=1.2,
                        annotation_text=f"SL: ${o_sl:,.2f}",
                        annotation_position="bottom right",
                        annotation_font=dict(color="#ff5555", size=10)
                    )

                # Take Profit line
                if o_tp > 0:
                    fig.add_hline(
                        y=o_tp,
                        line_dash="dot",
                        line_color="#00ffcc",
                        line_width=1.2,
                        annotation_text=f"TP: ${o_tp:,.2f}",
                        annotation_position="top right",
                        annotation_font=dict(color="#00ffcc", size=10)
                    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(10,14,23,0.8)",
        margin=dict(l=10, r=20, t=20, b=10),
        height=680,
        showlegend=False,
        xaxis=dict(
            rangeslider=dict(visible=False),
            showgrid=True,
            gridcolor="rgba(255,255,255,0.04)",
            linecolor="rgba(255,255,255,0.08)"
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.04)",
            linecolor="rgba(255,255,255,0.08)",
            tickprefix="$",
            tickformat=",.2f"
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": True,
            "scrollZoom": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"]
        }
    )
