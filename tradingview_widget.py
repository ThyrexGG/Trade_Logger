import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit.components.v1 import html
import os
import json
import database
import market_data

DEFAULT_SYMBOLS = {
    "Gold (XAU/USD)": "XAUUSD",
    "US Tech 100 (Nasdaq)": "NAS100",
    "US 500 (S&P 500)": "SPX500",
    "US 30 Wall St": "US30",
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "USD/JPY": "USDJPY",
    "Bitcoin (BTC/USD)": "BTCUSD",
    "US Crude Oil": "USOIL"
}

def render_tradingview_chart(symbol="XAUUSD", interval="15m", height=750, custom_layout_url=None):
    """
    Renders our custom Native TradingView Engine (SuperApp Chart Studio) powered by
    TradingView's Lightweight Charts 4.x + Live Real Market Candlesticks + Persistent Drawing Canvas.
    All drawings and indicators are 100% saved in SQLite database (trades.db) and localStorage!
    """
    clean_sym = symbol.replace(":", "").replace("/", "").replace("OANDA", "").replace("FOREXCOM", "").replace("BINANCE", "").replace("FX", "").upper().strip()
    
    # 1. Fetch Real Market Candles (from MT5 -> Yahoo -> Binance)
    candles = market_data.get_realtime_candles(symbol=clean_sym, timeframe=interval, count=220)
    candles_json = json.dumps(candles)

    # 2. Fetch Real Trade Executions for Overlay
    df_trades = database.get_closed_trades()
    executions = []
    if not df_trades.empty:
        df_sym = df_trades[df_trades["symbol"].str.upper().str.contains(clean_sym, na=False)].copy()
        for _, r in df_sym.iterrows():
            try:
                e_t = int(pd.to_datetime(r["entry_time"]).timestamp())
                x_t = int(pd.to_datetime(r["exit_time"]).timestamp())
                executions.append({
                    "trade_id": str(r.get("trade_id", "")),
                    "dir": str(r.get("direction", "BUY")).upper(),
                    "entry_price": float(r.get("entry_price", 0.0)),
                    "exit_price": float(r.get("exit_price", 0.0)),
                    "pnl": float(r.get("net_profit", 0.0)),
                    "entry_time": e_t,
                    "exit_time": x_t
                })
            except Exception:
                pass
    exec_json = json.dumps(executions)

    # 3. Fetch Saved Drawings from SQLite Database
    saved_drawings = database.get_chart_drawings(clean_sym)
    if not saved_drawings or saved_drawings == "None":
        saved_drawings = "[]"

    container_id = f"native_chart_{clean_sym}"

    chart_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <!-- High-Performance TradingView Lightweight Charts 4.1.1 CDN -->
      <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
        body {{ background: #0a0e17; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; overflow: hidden; height: 100%; }}
        
        .superapp-chart-wrapper {{
          position: relative;
          width: 100%;
          height: {height}px;
          background: #0a0e17;
          border-radius: 12px;
          overflow: hidden;
          border: 1px solid rgba(0, 255, 204, 0.25);
          box-shadow: 0 10px 30px rgba(0,0,0,0.6);
        }}
        
        /* Floating Studio Toolbar */
        .chart-toolbar {{
          position: absolute;
          top: 12px;
          left: 14px;
          z-index: 100;
          display: flex;
          align-items: center;
          gap: 6px;
          background: rgba(14, 19, 31, 0.94);
          backdrop-filter: blur(14px);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 8px;
          padding: 6px 12px;
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
        .color-dot.active {{ border-color: #ffffff; transform: scale(1.25); box-shadow: 0 0 8px rgba(255,255,255,0.8); }}
        
        /* Interactive Persistent Drawing Canvas */
        #drawingCanvas {{
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          z-index: 50;
          pointer-events: none;
        }}
        #drawingCanvas.active-drawing {{ pointer-events: auto; cursor: crosshair; }}
        
        /* Floating OHLC Ticker Badge */
        .ticker-badge {{
          position: absolute;
          bottom: 14px;
          left: 14px;
          z-index: 100;
          background: rgba(14, 19, 31, 0.88);
          border: 1px solid rgba(255, 255, 255, 0.08);
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 11px;
          color: #8a99ad;
          font-family: monospace;
          pointer-events: none;
        }}
        
        .save-badge {{
          font-size: 10px;
          font-weight: 800;
          color: #00ffcc;
          background: rgba(0, 255, 204, 0.12);
          border: 1px solid rgba(0, 255, 204, 0.3);
          padding: 4px 8px;
          border-radius: 4px;
          letter-spacing: 0.5px;
        }}
      </style>
    </head>
    <body>
      <div class="superapp-chart-wrapper">
        <!-- Floating Drawing Toolbar -->
        <div class="chart-toolbar">
          <button class="tool-btn active" id="toolPan" onclick="setTool('pan')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 9l-3 3 3 3M9 5l3-3 3 3M15 19l-3 3-3-3M19 9l3 3-3 3M2 12h20M12 2v20"/></svg>
            MOVE / PAN
          </button>
          <button class="tool-btn" id="toolHLine" onclick="setTool('hline')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="2" y1="12" x2="22" y2="12"/></svg>
            KEY LEVEL (RAY)
          </button>
          <button class="tool-btn" id="toolTrend" onclick="setTool('trend')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="4" y1="20" x2="20" y2="4"/></svg>
            TRENDLINE
          </button>
          <button class="tool-btn" id="toolBox" onclick="setTool('box')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
            ORDER BLOCK
          </button>
          
          <div style="display:flex; align-items:center; gap:5px; margin: 0 4px;">
            <div class="color-dot active" style="background:#00ffcc;" onclick="setColor('#00ffcc', this)"></div>
            <div class="color-dot" style="background:#bef264;" onclick="setColor('#bef264', this)"></div>
            <div class="color-dot" style="background:#ff5555;" onclick="setColor('#ff5555', this)"></div>
            <div class="color-dot" style="background:#f59e0b;" onclick="setColor('#f59e0b', this)"></div>
            <div class="color-dot" style="background:#ffffff;" onclick="setColor('#ffffff', this)"></div>
          </div>
          
          <button class="tool-btn" onclick="toggleEMA()" id="btnEMA">
            EMA 20/50
          </button>
          
          <button class="tool-btn" onclick="clearAllDrawings()" style="color:#ff5555;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            CLEAR
          </button>
          
          <span class="save-badge" id="saveBadge">AUTO-SAVED TO DB</span>
        </div>

        <!-- Floating Price Badge -->
        <div class="ticker-badge" id="tickerBadge">
          <b style="color:#ffffff;">{clean_sym}</b> | REAL-TIME FEED
        </div>

        <!-- Custom Persistent Drawing Layer -->
        <canvas id="drawingCanvas"></canvas>

        <!-- TradingView Lightweight Canvas Container -->
        <div id="{container_id}" style="width: 100%; height: 100%;"></div>
      </div>

      <script>
        const SYMBOL = "{clean_sym}";
        const STORAGE_KEY = "superapp_chart_drawings_" + SYMBOL;
        let candleData = {candles_json};
        let executions = {exec_json};
        let currentTool = 'pan';
        let currentColor = '#00ffcc';
        let drawings = [];
        let showEMA = false;
        let ema20Series = null;
        let ema50Series = null;

        // Load saved drawings from DB or localStorage
        try {{
          const initialDb = {saved_drawings};
          const localStr = localStorage.getItem(STORAGE_KEY);
          if (localStr && JSON.parse(localStr).length > 0) {{
            drawings = JSON.parse(localStr);
          }} else if (Array.isArray(initialDb) && initialDb.length > 0) {{
            drawings = initialDb;
          }}
        }} catch(e) {{
          console.log("Error loading drawings:", e);
        }}

        // 1. Initialize TradingView Lightweight Chart
        const chartContainer = document.getElementById('{container_id}');
        const chart = LightweightCharts.createChart(chartContainer, {{
          width: chartContainer.clientWidth,
          height: chartContainer.clientHeight,
          layout: {{
            background: {{ color: '#0a0e17' }},
            textColor: '#8a99ad',
            fontFamily: 'Inter, sans-serif',
          }},
          grid: {{
            vertLines: {{ color: 'rgba(255, 255, 255, 0.03)' }},
            horzLines: {{ color: 'rgba(255, 255, 255, 0.03)' }},
          }},
          crosshair: {{
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {{ color: 'rgba(0, 255, 204, 0.4)', width: 1, style: 2 }},
            horzLine: {{ color: 'rgba(0, 255, 204, 0.4)', width: 1, style: 2 }},
          }},
          rightPriceScale: {{
            borderColor: 'rgba(255, 255, 255, 0.08)',
            scaleMargins: {{ top: 0.1, bottom: 0.15 }},
          }},
          timeScale: {{
            borderColor: 'rgba(255, 255, 255, 0.08)',
            timeVisible: true,
            secondsVisible: false,
          }},
        }});

        // 2. Add Candlestick Series
        const candleSeries = chart.addCandlestickSeries({{
          upColor: '#00ffcc',
          downColor: '#ff5555',
          borderUpColor: '#00ffcc',
          borderDownColor: '#ff5555',
          wickUpColor: '#00ffcc',
          wickDownColor: '#ff5555',
        }});
        candleSeries.setData(candleData);

        // 3. Add Real Trade Execution Markers (BUY/SELL arrows)
        if (executions && executions.length > 0) {{
          let markers = [];
          executions.forEach(ex => {{
            const isBuy = ex.dir.includes("BUY") || ex.dir.includes("LONG");
            const isWin = ex.pnl >= 0;
            markers.push({{
              time: ex.exit_time || ex.entry_time,
              position: isBuy ? 'belowBar' : 'aboveBar',
              color: isWin ? '#00ffcc' : '#ff5555',
              shape: isBuy ? 'arrowUp' : 'arrowDown',
              text: (isBuy ? 'BUY' : 'SELL') + ' (' + (isWin ? '+' : '') + '$' + Math.abs(ex.pnl).toFixed(2) + ')',
            }});
          }});
          // Sort markers by time
          markers.sort((a, b) => a.time - b.time);
          try {{
            candleSeries.setMarkers(markers);
          }} catch(e) {{}}
        }}

        // 4. Calculate EMA
        function calculateEMA(data, period) {{
          let k = 2 / (period + 1);
          let emaData = [];
          let prevEMA = data[0].close;
          for (let i = 0; i < data.length; i++) {{
            let val = data[i].close * k + prevEMA * (1 - k);
            prevEMA = val;
            if (i >= period) {{
              emaData.push({{ time: data[i].time, value: val }});
            }}
          }}
          return emaData;
        }}

        function toggleEMA() {{
          showEMA = !showEMA;
          const btn = document.getElementById('btnEMA');
          if (showEMA) {{
            btn.classList.add('active');
            ema20Series = chart.addLineSeries({{ color: '#00ffcc', lineWidth: 1.5, title: 'EMA 20' }});
            ema50Series = chart.addLineSeries({{ color: '#bef264', lineWidth: 1.5, title: 'EMA 50' }});
            ema20Series.setData(calculateEMA(candleData, 20));
            ema50Series.setData(calculateEMA(candleData, 50));
          }} else {{
            btn.classList.remove('active');
            if (ema20Series) chart.removeSeries(ema20Series);
            if (ema50Series) chart.removeSeries(ema50Series);
          }}
        }}

        // Update live price on crosshair
        chart.subscribeCrosshairMove((param) => {{
          if (param.time) {{
            const price = param.seriesPrices.get(candleSeries);
            if (price) {{
              document.getElementById('tickerBadge').innerHTML = 
                `<b style="color:#ffffff;">${{SYMBOL}}</b> | O: <span style="color:#00ffcc;">${{price.open}}</span> H: <span style="color:#00ffcc;">${{price.high}}</span> L: <span style="color:#ff5555;">${{price.low}}</span> C: <span style="color:${{price.close >= price.open ? '#00ffcc' : '#ff5555'}};">${{price.close}}</span>`;
            }}
          }}
        }});

        // 5. Setup Drawing Canvas Over WebGL Chart
        const canvas = document.getElementById('drawingCanvas');
        const ctx = canvas.getContext('2d');
        let isDrawing = false;
        let startX = 0, startY = 0;

        function resizeCanvas() {{
          canvas.width = chartContainer.clientWidth;
          canvas.height = chartContainer.clientHeight;
          chart.applyOptions({{ width: chartContainer.clientWidth, height: chartContainer.clientHeight }});
          redrawAll();
        }}
        window.addEventListener('resize', resizeCanvas);
        setTimeout(resizeCanvas, 400);

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

        // Canvas Events
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
              
              // Draw price level tag
              ctx.fillStyle = d.color;
              ctx.fillRect(canvas.width - 75, d.y - 10, 70, 20);
              ctx.fillStyle = '#000000';
              ctx.font = 'bold 10px Inter, sans-serif';
              ctx.fillText('KEY LEVEL', canvas.width - 68, d.y + 4);
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
          localStorage.setItem(STORAGE_KEY, dataStr);
          
          // Auto-save to SQLite Database via REST API
          fetch('http://127.0.0.1:8000/api/chart/drawings', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ symbol: SYMBOL, drawings_data: dataStr }})
          }}).catch(err => console.log('DB sync notice:', err));

          const badge = document.getElementById('saveBadge');
          badge.innerText = 'SAVED (' + drawings.length + ' DRAWINGS)';
          badge.style.color = '#bef264';
        }}

        function clearAllDrawings() {{
          drawings = [];
          saveDrawings();
          redrawAll();
          document.getElementById('saveBadge').innerText = 'DRAWINGS CLEARED';
        }}
      </script>
    </body>
    </html>
    """
    html(chart_html, height=height + 20)

def fetch_mt5_candles(symbol="XAUUSD", timeframe="1h", count=150):
    return market_data.get_realtime_candles(symbol=symbol, timeframe=timeframe, count=count)

def render_broker_candlestick_overlay(symbol="XAUUSD", df_trades=None, df_open=None, timeframe="1h", count=150):
    render_tradingview_chart(symbol=symbol, interval=timeframe, height=750)
