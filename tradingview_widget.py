import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit.components.v1 import html
import os
import json
import database

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

def render_tradingview_chart(symbol="OANDA:XAUUSD", interval="15", height=750, custom_layout_url=None):
    """
    Renders the Super App Technical Charting Studio with Interactive Persistent Drawing Canvas.
    Drawings (trendlines, horizontal levels, order blocks) are saved directly into the database & localStorage!
    """
    clean_sym = symbol.replace(":", "_").replace("/", "_").upper()
    saved_drawings = database.get_chart_drawings(clean_sym)
    if not saved_drawings or saved_drawings == "None":
        saved_drawings = "[]"

    container_id = f"tv_chart_superapp_{clean_sym}"

    tv_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
        body {{ background: #0a0e17; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; overflow: hidden; height: 100%; }}
        .superapp-container {{ position: relative; width: 100%; height: {height}px; background: #0a0e17; border-radius: 12px; overflow: hidden; border: 1px solid rgba(0, 255, 204, 0.25); box-shadow: 0 10px 30px rgba(0,0,0,0.6); }}
        
        /* Floating Drawing Toolbar */
        .drawing-toolbar {{
          position: absolute;
          top: 14px;
          left: 14px;
          z-index: 99;
          display: flex;
          align-items: center;
          gap: 6px;
          background: rgba(14, 19, 31, 0.92);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 8px;
          padding: 6px 10px;
          box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        }}
        .tool-btn {{
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: #8a99ad;
          font-size: 11px;
          font-weight: 700;
          padding: 6px 10px;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          gap: 5px;
        }}
        .tool-btn:hover {{ background: rgba(0, 255, 204, 0.15); color: #00ffcc; border-color: rgba(0, 255, 204, 0.4); }}
        .tool-btn.active {{ background: rgba(0, 255, 204, 0.25); color: #00ffcc; border-color: #00ffcc; box-shadow: 0 0 10px rgba(0, 255, 204, 0.35); }}
        
        .color-dot {{ width: 14px; height: 14px; border-radius: 50%; cursor: pointer; border: 1.5px solid rgba(255,255,255,0.4); }}
        .color-dot.active {{ border-color: #ffffff; transform: scale(1.2); box-shadow: 0 0 8px rgba(255,255,255,0.8); }}
        
        /* Interactive Overlay Canvas for Persistent Drawings */
        #drawingCanvas {{
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          z-index: 10;
          pointer-events: none;
        }}
        #drawingCanvas.active-drawing {{ pointer-events: auto; cursor: crosshair; }}
        
        /* Save Status Pill */
        .save-pill {{
          font-size: 10px;
          font-weight: 800;
          color: #00ffcc;
          background: rgba(0, 255, 204, 0.12);
          border: 1px solid rgba(0, 255, 204, 0.3);
          padding: 4px 8px;
          border-radius: 4px;
          margin-left: 6px;
          letter-spacing: 0.5px;
        }}
      </style>
    </head>
    <body>
      <div class="superapp-container">
        <!-- Floating Persistent Drawing Studio Toolbar -->
        <div class="drawing-toolbar">
          <button class="tool-btn active" id="toolPan" onclick="setTool('pan')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 9l-3 3 3 3M9 5l3-3 3 3M15 19l-3 3-3-3M19 9l3 3-3 3M2 12h20M12 2v20"/></svg>
            NAVIGATE
          </button>
          <button class="tool-btn" id="toolHLine" onclick="setTool('hline')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="2" y1="12" x2="22" y2="12"/></svg>
            HORIZONTAL RAY
          </button>
          <button class="tool-btn" id="toolTrend" onclick="setTool('trend')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="4" y1="20" x2="20" y2="4"/></svg>
            TRENDLINE
          </button>
          <button class="tool-btn" id="toolBox" onclick="setTool('box')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
            ORDER BLOCK ZONE
          </button>
          
          <div style="display:flex; align-items:center; gap:5px; margin: 0 4px;">
            <div class="color-dot active" style="background:#00ffcc;" onclick="setColor('#00ffcc', this)"></div>
            <div class="color-dot" style="background:#bef264;" onclick="setColor('#bef264', this)"></div>
            <div class="color-dot" style="background:#ff5555;" onclick="setColor('#ff5555', this)"></div>
            <div class="color-dot" style="background:#f59e0b;" onclick="setColor('#f59e0b', this)"></div>
            <div class="color-dot" style="background:#ffffff;" onclick="setColor('#ffffff', this)"></div>
          </div>
          
          <button class="tool-btn" onclick="clearAllDrawings()" style="color:#ff5555;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            CLEAR
          </button>
          
          <span class="save-pill" id="saveStatus">AUTO-SAVED TO DB</span>
        </div>

        <!-- Drawing Canvas Layer -->
        <canvas id="drawingCanvas"></canvas>

        <!-- TradingView Embedded Pro Engine -->
        <div id="{container_id}" style="height: 100%; width: 100%;"></div>
      </div>

      <script>
        const SYMBOL_KEY = "tv_drawings_{clean_sym}";
        let currentTool = 'pan';
        let currentColor = '#00ffcc';
        let drawings = [];

        // Load saved drawings from database or localStorage
        try {{
          const initialDb = {saved_drawings};
          const localStr = localStorage.getItem(SYMBOL_KEY);
          if (localStr && JSON.parse(localStr).length > 0) {{
            drawings = JSON.parse(localStr);
          }} else if (Array.isArray(initialDb) && initialDb.length > 0) {{
            drawings = initialDb;
          }}
        }} catch(e) {{
          console.log("Error loading saved drawings:", e);
        }}

        // Initialize TradingView Widget
        new TradingView.widget({{
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
          "container_id": "{container_id}",
          "overrides": {{
            "paneProperties.background": "#0a0e17",
            "paneProperties.vertGridProperties.color": "rgba(255, 255, 255, 0.04)",
            "paneProperties.horzGridProperties.color": "rgba(255, 255, 255, 0.04)",
            "mainSeriesProperties.candleStyle.upColor": "#00ffcc",
            "mainSeriesProperties.candleStyle.downColor": "#ff5555",
            "mainSeriesProperties.candleStyle.wickUpColor": "#00ffcc",
            "mainSeriesProperties.candleStyle.wickDownColor": "#ff5555"
          }}
        }});

        // Setup Drawing Canvas
        const canvas = document.getElementById('drawingCanvas');
        const ctx = canvas.getContext('2d');
        let isDrawing = false;
        let startX = 0, startY = 0;

        function resizeCanvas() {{
          canvas.width = canvas.parentElement.clientWidth;
          canvas.height = canvas.parentElement.clientHeight;
          redrawAll();
        }}
        window.addEventListener('resize', resizeCanvas);
        setTimeout(resizeCanvas, 500);

        function setTool(tool) {{
          currentTool = tool;
          document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
          if (tool === 'pan') {{
            document.getElementById('toolPan').classList.add('active');
            canvas.classList.remove('active-drawing');
          }} else if (tool === 'hline') {{
            document.getElementById('toolHLine').classList.add('active');
            canvas.classList.add('active-drawing');
          }} else if (tool === 'trend') {{
            document.getElementById('toolTrend').classList.add('active');
            canvas.classList.add('active-drawing');
          }} else if (tool === 'box') {{
            document.getElementById('toolBox').classList.add('active');
            canvas.classList.add('active-drawing');
          }}
        }}

        function setColor(color, el) {{
          currentColor = color;
          document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
          el.classList.add('active');
        }}

        // Canvas Drawing Events
        canvas.addEventListener('mousedown', (e) => {{
          if (currentTool === 'pan') return;
          const rect = canvas.getBoundingClientRect();
          startX = e.clientX - rect.left;
          startY = e.clientY - rect.top;
          isDrawing = true;

          if (currentTool === 'hline') {{
            drawings.push({{
              type: 'hline',
              y: startY,
              color: currentColor,
              lineWidth: 2
            }});
            isDrawing = false;
            saveDrawings();
            redrawAll();
          }}
        }});

        canvas.addEventListener('mousemove', (e) => {{
          if (!isDrawing || currentTool === 'pan' || currentTool === 'hline') return;
          const rect = canvas.getBoundingClientRect();
          const currX = e.clientX - rect.left;
          const currY = e.clientY - rect.top;

          redrawAll();
          ctx.save();
          ctx.strokeStyle = currentColor;
          ctx.lineWidth = 2;
          ctx.shadowColor = currentColor;
          ctx.shadowBlur = 8;

          if (currentTool === 'trend') {{
            ctx.beginPath();
            ctx.moveTo(startX, startY);
            ctx.lineTo(currX, currY);
            ctx.stroke();
          }} else if (currentTool === 'box') {{
            ctx.fillStyle = currentColor + '22';
            ctx.fillRect(startX, startY, currX - startX, currY - startY);
            ctx.strokeRect(startX, startY, currX - startX, currY - startY);
          }}
          ctx.restore();
        }});

        canvas.addEventListener('mouseup', (e) => {{
          if (!isDrawing) return;
          isDrawing = false;
          const rect = canvas.getBoundingClientRect();
          const endX = e.clientX - rect.left;
          const endY = e.clientY - rect.top;

          if (currentTool === 'trend') {{
            drawings.push({{
              type: 'trend',
              x1: startX, y1: startY,
              x2: endX, y2: endY,
              color: currentColor,
              lineWidth: 2
            }});
          }} else if (currentTool === 'box') {{
            drawings.push({{
              type: 'box',
              x: startX, y: startY,
              w: endX - startX, h: endY - startY,
              color: currentColor
            }});
          }}
          saveDrawings();
          redrawAll();
        }});

        function redrawAll() {{
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          drawings.forEach(d => {{
            ctx.save();
            ctx.strokeStyle = d.color;
            ctx.lineWidth = d.lineWidth || 2;
            ctx.shadowColor = d.color;
            ctx.shadowBlur = 8;

            if (d.type === 'hline') {{
              ctx.beginPath();
              ctx.moveTo(0, d.y);
              ctx.lineTo(canvas.width, d.y);
              ctx.stroke();
              
              // Draw price badge tag
              ctx.fillStyle = d.color;
              ctx.fillRect(canvas.width - 70, d.y - 10, 65, 20);
              ctx.fillStyle = '#000000';
              ctx.font = 'bold 10px Inter, sans-serif';
              ctx.fillText('LEVEL', canvas.width - 55, d.y + 4);
            }} else if (d.type === 'trend') {{
              ctx.beginPath();
              ctx.moveTo(d.x1, d.y1);
              ctx.lineTo(d.x2, d.y2);
              ctx.stroke();
            }} else if (d.type === 'box') {{
              ctx.fillStyle = d.color + '22';
              ctx.fillRect(d.x, d.y, d.w, d.h);
              ctx.strokeRect(d.x, d.y, d.w, d.h);
            }}
            ctx.restore();
          }});
        }}

        function saveDrawings() {{
          const dataStr = JSON.stringify(drawings);
          localStorage.setItem(SYMBOL_KEY, dataStr);
          
          // Send to Python FastAPI backend database
          fetch('http://127.0.0.1:8000/api/chart/drawings', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ symbol: '{clean_sym}', drawings_data: dataStr }})
          }}).catch(err => console.log('DB sync notice:', err));

          const pill = document.getElementById('saveStatus');
          pill.innerText = 'SAVED (' + drawings.length + ' LINES)';
          pill.style.color = '#bef264';
        }}

        function clearAllDrawings() {{
          drawings = [];
          saveDrawings();
          redrawAll();
          document.getElementById('saveStatus').innerText = 'DRAWINGS CLEARED';
        }}
      </script>
    </body>
    </html>
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
        increasing_fillcolor='rgba(0, 255, 204, 0.4)',
        decreasing_fillcolor='rgba(255, 85, 85, 0.4)'
    ))

    # Overlap closed executed trades
    if df_trades is not None and not df_trades.empty:
        sym_clean = symbol.replace("/", "").upper()
        sym_trades = df_trades[df_trades['symbol'].str.upper() == sym_clean]
        
        for _, trade in sym_trades.iterrows():
            entry_time = pd.to_datetime(trade['entry_time'])
            exit_time = pd.to_datetime(trade['exit_time'])
            entry_price = float(trade['entry_price'])
            exit_price = float(trade['exit_price'])
            pnl = float(trade['net_profit'])
            direction = str(trade['direction']).upper()

            is_win = pnl >= 0
            pnl_color = '#00ffcc' if is_win else '#ff5555'
            sign = '+' if is_win else '-'

            # Execution Holding Line
            fig.add_trace(go.Scatter(
                x=[entry_time, exit_time],
                y=[entry_price, exit_price],
                mode='lines+markers',
                line=dict(color=pnl_color, width=2.5, dash='dot'),
                marker=dict(size=8, color=pnl_color, symbol=['circle', 'square']),
                name=f"Trade #{trade.get('trade_id', '')} ({direction})"
            ))

            # Profit Badge annotation at exit point
            fig.add_annotation(
                x=exit_time,
                y=exit_price,
                text=f"<b>{direction} {sign}${abs(pnl):,.2f}</b>",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1.5,
                arrowcolor=pnl_color,
                font=dict(size=11, color='#ffffff', family='Inter'),
                bgcolor='rgba(14, 19, 31, 0.95)',
                bordercolor=pnl_color,
                borderwidth=1.5,
                borderpad=4,
                opacity=0.95
            )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='#0a0e17',
        plot_bgcolor='#0a0e17',
        xaxis=dict(
            gridcolor='rgba(255, 255, 255, 0.04)',
            rangeslider=dict(visible=False),
            showline=False
        ),
        yaxis=dict(
            gridcolor='rgba(255, 255, 255, 0.04)',
            side='right',
            showline=False
        ),
        margin=dict(l=10, r=60, t=20, b=20),
        height=650,
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)
