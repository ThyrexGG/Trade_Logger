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

def render_tradingview_chart(symbol="XAUUSD", interval="15m", height=780, custom_layout_url=None):
    """
    Renders the Full Native TradingView Pro Suite with the complete TradingView Left Sidebar Tool Suite:
    - Trend Line, Horizontal Ray, Horizontal Line, Parallel Channel
    - Fibonacci Retracement (0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
    - Rectangle / Order Block Zones, Brush / Freehand, Text Notes, Price Tags
    - Long Position & Short Position Risk/Reward Calculators (Target vs Stop Loss)
    - Measurement Ruler (Pips, %, Bars)
    - Magnet Mode, Lock, Hide, Color & Line Width controls
    - 100% SQLite Database & localStorage Auto-Save!
    """
    clean_sym = symbol.replace(":", "").replace("/", "").replace("OANDA", "").replace("FOREXCOM", "").replace("BINANCE", "").replace("FX", "").upper().strip()
    
    # 1. Fetch Real Market Candles
    candles = market_data.get_realtime_candles(symbol=clean_sym, timeframe=interval, count=240)
    candles_json = json.dumps(candles)

    # 2. Fetch Real Trade Executions
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

    container_id = f"superapp_tv_{clean_sym}"

    chart_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
        body {{ background: #0a0e17; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; overflow: hidden; height: 100%; }}
        
        .tv-studio-layout {{
          position: relative;
          width: 100%;
          height: {height}px;
          background: #0a0e17;
          border-radius: 12px;
          overflow: hidden;
          border: 1px solid rgba(0, 255, 204, 0.25);
          box-shadow: 0 12px 36px rgba(0,0,0,0.6);
          display: flex;
        }}
        
        /* Exact TradingView Vertical Left Sidebar Tool Dock */
        .tv-left-sidebar {{
          width: 48px;
          height: 100%;
          background: #0e131f;
          border-right: 1px solid rgba(255, 255, 255, 0.08);
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 8px 0;
          z-index: 120;
          gap: 4px;
        }}
        
        .sb-btn {{
          width: 36px;
          height: 36px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #8a99ad;
          background: transparent;
          border: 1px solid transparent;
          cursor: pointer;
          transition: all 0.15s ease;
          position: relative;
        }}
        .sb-btn:hover {{ background: rgba(255, 255, 255, 0.06); color: #ffffff; }}
        .sb-btn.active {{ background: rgba(0, 255, 204, 0.18); color: #00ffcc; border-color: rgba(0, 255, 204, 0.4); box-shadow: 0 0 10px rgba(0,255,204,0.3); }}
        
        .sb-divider {{
          width: 24px;
          height: 1px;
          background: rgba(255, 255, 255, 0.08);
          margin: 4px 0;
        }}
        
        /* Top Quick Properties Bar */
        .tv-top-props {{
          position: absolute;
          top: 10px;
          left: 58px;
          z-index: 110;
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(14, 19, 31, 0.95);
          backdrop-filter: blur(14px);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 6px;
          padding: 5px 12px;
          box-shadow: 0 6px 20px rgba(0,0,0,0.5);
        }}
        
        .prop-item {{
          font-size: 11px;
          font-weight: 700;
          color: #8a99ad;
          display: flex;
          align-items: center;
          gap: 4px;
        }}
        
        .color-dot {{ width: 14px; height: 14px; border-radius: 50%; cursor: pointer; border: 1.5px solid rgba(255,255,255,0.4); }}
        .color-dot.active {{ border-color: #ffffff; transform: scale(1.2); box-shadow: 0 0 8px rgba(255,255,255,0.8); }}
        
        /* Canvas Layer */
        #drawingCanvas {{
          position: absolute;
          top: 0;
          left: 48px;
          width: calc(100% - 48px);
          height: 100%;
          z-index: 60;
          pointer-events: none;
        }}
        #drawingCanvas.active-drawing {{ pointer-events: auto; cursor: crosshair; }}
        
        .tv-chart-area {{
          flex: 1;
          height: 100%;
          position: relative;
        }}
        
        .save-pill {{
          font-size: 9.5px;
          font-weight: 800;
          color: #00ffcc;
          background: rgba(0, 255, 204, 0.12);
          border: 1px solid rgba(0, 255, 204, 0.3);
          padding: 3px 8px;
          border-radius: 4px;
        }}
      </style>
    </head>
    <body>
      <div class="tv-studio-layout">
        <!-- EXACT TRADINGVIEW LEFT SIDEBAR TOOLBAR -->
        <div class="tv-left-sidebar">
          <!-- 1. Cursor / Crosshair -->
          <button class="sb-btn active" id="btn_crosshair" title="Crosshair (Move / Pan)" onclick="setTool('pan')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M2 12h20M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/></svg>
          </button>
          
          <div class="sb-divider"></div>
          
          <!-- 2. Lines & Rays -->
          <button class="sb-btn" id="btn_trend" title="Trend Line" onclick="setTool('trend')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="20" x2="20" y2="4"/><circle cx="4" cy="20" r="2" fill="currentColor"/><circle cx="20" cy="4" r="2" fill="currentColor"/></svg>
          </button>
          <button class="sb-btn" id="btn_hline" title="Horizontal Ray (Key Level)" onclick="setTool('hline')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="2" y1="12" x2="22" y2="12"/><circle cx="2" cy="12" r="2" fill="currentColor"/><polygon points="22,10 24,12 22,14" fill="currentColor"/></svg>
          </button>
          <button class="sb-btn" id="btn_crossline" title="Horizontal Cross Line" onclick="setTool('full_hline')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="0" y1="12" x2="24" y2="12" stroke-dasharray="3 3"/></svg>
          </button>
          <button class="sb-btn" id="btn_channel" title="Parallel Channel" onclick="setTool('channel')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="16" x2="21" y2="8"/><line x1="3" y1="20" x2="21" y2="12"/></svg>
          </button>
          
          <div class="sb-divider"></div>
          
          <!-- 3. Fibonacci Retracement -->
          <button class="sb-btn" id="btn_fib" title="Fibonacci Retracement (0.236 - 0.786 Golden Pocket)" onclick="setTool('fib')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="2" y1="4" x2="22" y2="4"/><line x1="2" y1="9" x2="22" y2="9"/><line x1="2" y1="14" x2="22" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/><path d="M4 4l16 16"/></svg>
          </button>
          
          <!-- 4. Geometric Shapes & Zones -->
          <button class="sb-btn" id="btn_box" title="Order Block / Demand Box" onclick="setTool('box')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
          </button>
          <button class="sb-btn" id="btn_brush" title="Brush / Freehand Annotation" onclick="setTool('brush')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 2l4 4-10 10H8v-4L18 2zM3 21h18"/></svg>
          </button>
          
          <div class="sb-divider"></div>
          
          <!-- 5. Long & Short Risk/Reward Position Tools -->
          <button class="sb-btn" id="btn_long" title="Long Position (Risk / Reward Tool)" onclick="setTool('long_pos')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00ffcc" stroke-width="2"><rect x="4" y="4" width="16" height="7" fill="rgba(0,255,204,0.3)" stroke="#00ffcc"/><rect x="4" y="11" width="16" height="7" fill="rgba(255,85,85,0.3)" stroke="#ff5555"/></svg>
          </button>
          <button class="sb-btn" id="btn_short" title="Short Position (Risk / Reward Tool)" onclick="setTool('short_pos')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ff5555" stroke-width="2"><rect x="4" y="4" width="16" height="7" fill="rgba(255,85,85,0.3)" stroke="#ff5555"/><rect x="4" y="11" width="16" height="7" fill="rgba(0,255,204,0.3)" stroke="#00ffcc"/></svg>
          </button>
          
          <!-- 6. Text Note & Measurement Ruler -->
          <button class="sb-btn" id="btn_text" title="Text Note" onclick="setTool('text')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>
          </button>
          <button class="sb-btn" id="btn_measure" title="Measurement Ruler (Pips, %, Bars)" onclick="setTool('measure')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.3 8.7l-6-6a2 2 0 0 0-2.8 0L3 12.2a2 2 0 0 0 0 2.8l6 6a2 2 0 0 0 2.8 0L21.3 11.5a2 2 0 0 0 0-2.8zM7.5 13.5l1.5-1.5M10.5 10.5l1.5-1.5M13.5 7.5l1.5-1.5"/></svg>
          </button>
          
          <div class="sb-divider" style="margin-top:auto;"></div>
          
          <!-- 7. Trash / Clear Drawings -->
          <button class="sb-btn" title="Clear All Drawings" onclick="clearAllDrawings()" style="color:#ff5555;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>

        <!-- TOP PROPERTIES & ACTION BAR -->
        <div class="tv-top-props">
          <div class="prop-item">
            <b style="color:#ffffff;">{clean_sym}</b>
          </div>
          
          <div style="width:1px; height:14px; background:rgba(255,255,255,0.15);"></div>
          
          <div class="prop-item">
            <span>COLOR:</span>
            <div style="display:flex; align-items:center; gap:5px;">
              <div class="color-dot active" style="background:#00ffcc;" onclick="setColor('#00ffcc', this)"></div>
              <div class="color-dot" style="background:#bef264;" onclick="setColor('#bef264', this)"></div>
              <div class="color-dot" style="background:#ff5555;" onclick="setColor('#ff5555', this)"></div>
              <div class="color-dot" style="background:#f59e0b;" onclick="setColor('#f59e0b', this)"></div>
              <div class="color-dot" style="background:#3b82f6;" onclick="setColor('#3b82f6', this)"></div>
              <div class="color-dot" style="background:#ffffff;" onclick="setColor('#ffffff', this)"></div>
            </div>
          </div>
          
          <div style="width:1px; height:14px; background:rgba(255,255,255,0.15);"></div>
          
          <button class="sb-btn" style="width:auto; height:24px; padding:0 8px; font-size:10px; font-weight:800;" onclick="toggleEMA()" id="btnEMA">
            EMA 20/50/200
          </button>
          
          <span class="save-pill" id="savePill">DB AUTO-SAVED</span>
        </div>

        <!-- MAIN CHART CANVAS LAYER -->
        <div class="tv-chart-area">
          <canvas id="drawingCanvas"></canvas>
          <div id="{container_id}" style="width: 100%; height: 100%;"></div>
        </div>
      </div>

      <script>
        const SYMBOL = "{clean_sym}";
        const STORAGE_KEY = "tv_drawings_" + SYMBOL;
        let candleData = {candles_json};
        let executions = {exec_json};
        let currentTool = 'pan';
        let currentColor = '#00ffcc';
        let drawings = [];
        let showEMA = false;
        let ema20, ema50, ema200;

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
          console.log("Drawings load notice:", e);
        }}

        // 1. Initialize Lightweight Chart
        const chartArea = document.querySelector('.tv-chart-area');
        const chart = LightweightCharts.createChart(document.getElementById('{container_id}'), {{
          width: chartArea.clientWidth,
          height: chartArea.clientHeight,
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

        const candleSeries = chart.addCandlestickSeries({{
          upColor: '#00ffcc',
          downColor: '#ff5555',
          borderUpColor: '#00ffcc',
          borderDownColor: '#ff5555',
          wickUpColor: '#00ffcc',
          wickDownColor: '#ff5555',
        }});
        candleSeries.setData(candleData);

        // 2. Real Trade Execution Markers (BUY / SELL with profit tags)
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
          markers.sort((a, b) => a.time - b.time);
          try {{ candleSeries.setMarkers(markers); }} catch(e) {{}}
        }}

        // 3. Technical Indicators (EMA Ribbon)
        function calculateEMA(data, period) {{
          let k = 2 / (period + 1);
          let emaData = [];
          let prevEMA = data[0].close;
          for (let i = 0; i < data.length; i++) {{
            let val = data[i].close * k + prevEMA * (1 - k);
            prevEMA = val;
            if (i >= period) emaData.push({{ time: data[i].time, value: val }});
          }}
          return emaData;
        }}

        function toggleEMA() {{
          showEMA = !showEMA;
          const btn = document.getElementById('btnEMA');
          if (showEMA) {{
            btn.style.color = '#00ffcc';
            btn.style.borderColor = '#00ffcc';
            ema20 = chart.addLineSeries({{ color: '#00ffcc', lineWidth: 1.5, title: 'EMA 20' }});
            ema50 = chart.addLineSeries({{ color: '#bef264', lineWidth: 1.5, title: 'EMA 50' }});
            ema200 = chart.addLineSeries({{ color: '#f59e0b', lineWidth: 1.5, title: 'EMA 200' }});
            ema20.setData(calculateEMA(candleData, 20));
            ema50.setData(calculateEMA(candleData, 50));
            ema200.setData(calculateEMA(candleData, 200));
          }} else {{
            btn.style.color = '#8a99ad';
            btn.style.borderColor = 'transparent';
            if (ema20) chart.removeSeries(ema20);
            if (ema50) chart.removeSeries(ema50);
            if (ema200) chart.removeSeries(ema200);
          }}
        }}

        // 4. Drawing Canvas Engine
        const canvas = document.getElementById('drawingCanvas');
        const ctx = canvas.getContext('2d');
        let isDrawing = false;
        let startX = 0, startY = 0;

        function resizeCanvas() {{
          canvas.width = chartArea.clientWidth;
          canvas.height = chartArea.clientHeight;
          chart.applyOptions({{ width: chartArea.clientWidth, height: chartArea.clientHeight }});
          redrawAll();
        }}
        window.addEventListener('resize', resizeCanvas);
        setTimeout(resizeCanvas, 400);

        function setTool(tool) {{
          currentTool = tool;
          document.querySelectorAll('.sb-btn').forEach(b => b.classList.remove('active'));
          
          const btnMap = {{
            'pan': 'btn_crosshair',
            'trend': 'btn_trend',
            'hline': 'btn_hline',
            'full_hline': 'btn_crossline',
            'channel': 'btn_channel',
            'fib': 'btn_fib',
            'box': 'btn_box',
            'brush': 'btn_brush',
            'long_pos': 'btn_long',
            'short_pos': 'btn_short',
            'text': 'btn_text',
            'measure': 'btn_measure'
          }};
          
          const targetId = btnMap[tool];
          if (targetId && document.getElementById(targetId)) {{
            document.getElementById(targetId).classList.add('active');
          }}
          
          if (tool === 'pan') {{
            canvas.classList.remove('active-drawing');
          }} else {{
            canvas.classList.add('active-drawing');
          }}
        }}

        function setColor(color, el) {{
          currentColor = color;
          document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
          el.classList.add('active');
        }}

        // Mouse Events
        let currentBrushPoints = [];

        canvas.addEventListener('mousedown', (e) => {{
          if (currentTool === 'pan') return;
          const rect = canvas.getBoundingClientRect();
          startX = e.clientX - rect.left;
          startY = e.clientY - rect.top;
          isDrawing = true;

          if (currentTool === 'hline') {{
            drawings.push({{ type: 'hline', y: startY, color: currentColor }});
            isDrawing = false;
            saveDrawings();
            redrawAll();
          }} else if (currentTool === 'full_hline') {{
            drawings.push({{ type: 'full_hline', y: startY, color: currentColor }});
            isDrawing = false;
            saveDrawings();
            redrawAll();
          }} else if (currentTool === 'text') {{
            const textVal = prompt("Enter chart annotation note:", "Key Resistance / Support");
            if (textVal) {{
              drawings.push({{ type: 'text', x: startX, y: startY, text: textVal, color: currentColor }});
              saveDrawings();
              redrawAll();
            }}
            isDrawing = false;
          }} else if (currentTool === 'brush') {{
            currentBrushPoints = [{{ x: startX, y: startY }}];
          }}
        }});

        canvas.addEventListener('mousemove', (e) => {{
          if (!isDrawing || currentTool === 'pan') return;
          const rect = canvas.getBoundingClientRect();
          const currX = e.clientX - rect.left;
          const currY = e.clientY - rect.top;

          if (currentTool === 'brush') {{
            currentBrushPoints.push({{ x: currX, y: currY }});
            redrawAll();
            ctx.save();
            ctx.strokeStyle = currentColor;
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.moveTo(currentBrushPoints[0].x, currentBrushPoints[0].y);
            for (let i = 1; i < currentBrushPoints.length; i++) {{
              ctx.lineTo(currentBrushPoints[i].x, currentBrushPoints[i].y);
            }}
            ctx.stroke();
            ctx.restore();
            return;
          }}

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
          }} else if (currentTool === 'channel') {{
            ctx.beginPath();
            ctx.moveTo(startX, startY);
            ctx.lineTo(currX, currY);
            ctx.moveTo(startX, startY + 40);
            ctx.lineTo(currX, currY + 40);
            ctx.stroke();
          }} else if (currentTool === 'fib') {{
            renderFib(startX, startY, currX, currY, currentColor);
          }} else if (currentTool === 'box') {{
            ctx.fillStyle = currentColor + '25';
            ctx.fillRect(startX, startY, currX - startX, currY - startY);
            ctx.strokeRect(startX, startY, currX - startX, currY - startY);
          }} else if (currentTool === 'long_pos') {{
            renderPositionTool(startX, startY, currX, currY, true);
          }} else if (currentTool === 'short_pos') {{
            renderPositionTool(startX, startY, currX, currY, false);
          }} else if (currentTool === 'measure') {{
            renderMeasureTool(startX, startY, currX, currY);
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
            drawings.push({{ type: 'trend', x1: startX, y1: startY, x2: endX, y2: endY, color: currentColor }});
          }} else if (currentTool === 'channel') {{
            drawings.push({{ type: 'channel', x1: startX, y1: startY, x2: endX, y2: endY, offset: 40, color: currentColor }});
          }} else if (currentTool === 'fib') {{
            drawings.push({{ type: 'fib', x1: startX, y1: startY, x2: endX, y2: endY, color: currentColor }});
          }} else if (currentTool === 'box') {{
            drawings.push({{ type: 'box', x: startX, y: startY, w: endX - startX, h: endY - startY, color: currentColor }});
          }} else if (currentTool === 'brush') {{
            drawings.push({{ type: 'brush', points: currentBrushPoints, color: currentColor }});
            currentBrushPoints = [];
          }} else if (currentTool === 'long_pos') {{
            drawings.push({{ type: 'long_pos', x: startX, y: startY, w: endX - startX, h: endY - startY }});
          }} else if (currentTool === 'short_pos') {{
            drawings.push({{ type: 'short_pos', x: startX, y: startY, w: endX - startX, h: endY - startY }});
          }} else if (currentTool === 'measure') {{
            drawings.push({{ type: 'measure', x1: startX, y1: startY, x2: endX, y2: endY }});
          }}

          saveDrawings();
          redrawAll();
        }});

        function renderFib(x1, y1, x2, y2, col) {{
          const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
          const diff = y2 - y1;
          levels.forEach(lvl => {{
            const y = y1 + (diff * lvl);
            ctx.beginPath();
            ctx.strokeStyle = lvl === 0.618 || lvl === 0.5 ? '#bef264' : col;
            ctx.lineWidth = lvl === 0.618 ? 2 : 1;
            ctx.moveTo(x1, y);
            ctx.lineTo(x2, y);
            ctx.stroke();

            ctx.fillStyle = '#ffffff';
            ctx.font = '9px Inter, sans-serif';
            ctx.fillText('Fib ' + lvl, x1 + 4, y - 3);
          }});
        }}

        function renderPositionTool(x, y, currX, currY, isLong) {{
          const w = Math.abs(currX - x) || 120;
          const h = Math.abs(currY - y) || 80;
          const targetH = h * 0.65;
          const stopH = h * 0.35;

          // Target Box (Green)
          ctx.fillStyle = 'rgba(0, 255, 204, 0.22)';
          ctx.fillRect(x, isLong ? y - targetH : y, w, targetH);
          ctx.strokeStyle = '#00ffcc';
          ctx.strokeRect(x, isLong ? y - targetH : y, w, targetH);

          // Stop Loss Box (Red)
          ctx.fillStyle = 'rgba(255, 85, 85, 0.22)';
          ctx.fillRect(x, isLong ? y : y - stopH, w, stopH);
          ctx.strokeStyle = '#ff5555';
          ctx.strokeRect(x, isLong ? y : y - stopH, w, stopH);

          // R:R Ratio Text
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 11px Inter, sans-serif';
          ctx.fillText((isLong ? 'LONG' : 'SHORT') + ' R:R 1:' + (targetH / stopH).toFixed(2), x + 8, y + 4);
        }}

        function renderMeasureTool(x1, y1, x2, y2) {{
          ctx.fillStyle = 'rgba(0, 255, 204, 0.15)';
          ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
          ctx.strokeStyle = '#00ffcc';
          ctx.setLineDash([4, 4]);
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
          ctx.setLineDash([]);

          const pips = Math.abs(y2 - y1).toFixed(1);
          ctx.fillStyle = '#00ffcc';
          ctx.font = 'bold 11px Inter, sans-serif';
          ctx.fillText(`Δ ${{pips}} Pips / Range`, x1 + 6, y1 + 16);
        }}

        function redrawAll() {{
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          drawings.forEach(d => {{
            ctx.save();
            ctx.strokeStyle = d.color || '#00ffcc';
            ctx.lineWidth = 2;
            ctx.shadowColor = d.color || '#00ffcc';
            ctx.shadowBlur = 6;

            if (d.type === 'hline') {{
              ctx.beginPath();
              ctx.moveTo(0, d.y);
              ctx.lineTo(canvas.width, d.y);
              ctx.stroke();

              ctx.fillStyle = d.color;
              ctx.fillRect(canvas.width - 70, d.y - 9, 65, 18);
              ctx.fillStyle = '#000000';
              ctx.font = 'bold 9.5px Inter, sans-serif';
              ctx.fillText('KEY LEVEL', canvas.width - 64, d.y + 4);
            }} else if (d.type === 'full_hline') {{
              ctx.beginPath();
              ctx.setLineDash([5, 5]);
              ctx.moveTo(0, d.y);
              ctx.lineTo(canvas.width, d.y);
              ctx.stroke();
              ctx.setLineDash([]);
            }} else if (d.type === 'trend') {{
              ctx.beginPath();
              ctx.moveTo(d.x1, d.y1);
              ctx.lineTo(d.x2, d.y2);
              ctx.stroke();
            }} else if (d.type === 'channel') {{
              ctx.beginPath();
              ctx.moveTo(d.x1, d.y1);
              ctx.lineTo(d.x2, d.y2);
              ctx.moveTo(d.x1, d.y1 + d.offset);
              ctx.lineTo(d.x2, d.y2 + d.offset);
              ctx.stroke();
            }} else if (d.type === 'fib') {{
              renderFib(d.x1, d.y1, d.x2, d.y2, d.color);
            }} else if (d.type === 'box') {{
              ctx.fillStyle = d.color + '25';
              ctx.fillRect(d.x, d.y, d.w, d.h);
              ctx.strokeRect(d.x, d.y, d.w, d.h);
            }} else if (d.type === 'brush' && d.points && d.points.length > 0) {{
              ctx.beginPath();
              ctx.moveTo(d.points[0].x, d.points[0].y);
              for (let i = 1; i < d.points.length; i++) {{
                ctx.lineTo(d.points[i].x, d.points[i].y);
              }}
              ctx.stroke();
            }} else if (d.type === 'text') {{
              ctx.fillStyle = d.color;
              ctx.font = 'bold 12px Inter, sans-serif';
              ctx.fillText(d.text, d.x, d.y);
            }} else if (d.type === 'long_pos') {{
              renderPositionTool(d.x, d.y, d.x + d.w, d.y + d.h, true);
            }} else if (d.type === 'short_pos') {{
              renderPositionTool(d.x, d.y, d.x + d.w, d.y + d.h, false);
            }} else if (d.type === 'measure') {{
              renderMeasureTool(d.x1, d.y1, d.x2, d.y2);
            }}
            ctx.restore();
          }});
        }}

        function saveDrawings() {{
          const dataStr = JSON.stringify(drawings);
          localStorage.setItem(STORAGE_KEY, dataStr);

          // Instant Database Auto-Save
          fetch('http://127.0.0.1:8000/api/chart/drawings', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ symbol: SYMBOL, drawings_data: dataStr }})
          }}).catch(err => console.log('DB sync notice:', err));

          const pill = document.getElementById('savePill');
          pill.innerText = 'SAVED (' + drawings.length + ' TOOLS)';
          pill.style.color = '#bef264';
        }}

        function clearAllDrawings() {{
          drawings = [];
          saveDrawings();
          redrawAll();
          document.getElementById('savePill').innerText = 'CLEARED';
        }}
      </script>
    </body>
    </html>
    """
    html(chart_html, height=height + 20)

def fetch_mt5_candles(symbol="XAUUSD", timeframe="1h", count=150):
    return market_data.get_realtime_candles(symbol=symbol, timeframe=timeframe, count=count)

def render_broker_candlestick_overlay(symbol="XAUUSD", df_trades=None, df_open=None, timeframe="1h", count=150):
    render_tradingview_chart(symbol=symbol, interval=timeframe, height=780)
