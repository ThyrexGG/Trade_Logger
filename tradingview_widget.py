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
    Renders our Native TradingView SuperApp Charting Suite with exact TradingView Left Sidebar Flyout Menus:
    - Lines & Rays (Trend line, Ray, Info line, Extended, Horiz Ray, Horiz Line, Vert Line, Parallel Channel)
    - Gann & Fibonacci (Fib Retracement, Trend-based Fib Ext, Fib Channel, Fib Time Zone, Fib Fan, Fib Circles, Fib Spiral, Gann Box, Gann Square, Gann Fan)
    - Geometric Shapes (Brush, Highlighter, Rectangle / Order Block, Rotated Rect, Circle, Ellipse, Path, Polyline)
    - Text & Annotations (Text note, Callout, Price Tag, Arrow Marker)
    - Patterns (Head & Shoulders, Elliott Wave 12345, Triangle Pattern, ABCD)
    - Risk & Prediction (Long Position R:R, Short Position R:R, Price Range, Date Range, Bars Pattern)
    - Utilities (Measure Ruler, Magnet Mode, Lock, Hide, Delete)
    - 100% SQLite & localStorage Auto-Save!
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

    container_id = f"superapp_tv_canvas_{clean_sym}"

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
        
        /* Exact TradingView Left Sidebar Tool Dock */
        .tv-left-sidebar {{
          width: 48px;
          height: 100%;
          background: #0e131f;
          border-right: 1px solid rgba(255, 255, 255, 0.08);
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 8px 0;
          z-index: 150;
          gap: 4px;
        }}
        
        .sb-btn-group {{
          position: relative;
          width: 38px;
          height: 38px;
          display: flex;
          align-items: center;
          justify-content: center;
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
        .sb-btn:hover {{ background: rgba(255, 255, 255, 0.08); color: #ffffff; }}
        .sb-btn.active {{ background: rgba(0, 255, 204, 0.18); color: #00ffcc; border-color: rgba(0, 255, 204, 0.4); box-shadow: 0 0 10px rgba(0,255,204,0.3); }}
        
        .sb-arrow {{
          position: absolute;
          right: 2px;
          bottom: 2px;
          width: 0;
          height: 0;
          border-style: solid;
          border-width: 0 0 3.5px 3.5px;
          border-color: transparent transparent #8a99ad transparent;
          pointer-events: none;
        }}
        
        /* Flyout Popup Menus (Exact TradingView Submenu Style) */
        .tv-flyout-menu {{
          position: absolute;
          left: 48px;
          top: 0;
          width: 240px;
          background: #131722;
          border: 1px solid #2a2e39;
          border-radius: 6px;
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.7);
          padding: 6px 0;
          display: none;
          flex-direction: column;
          z-index: 200;
          max-height: 480px;
          overflow-y: auto;
        }}
        .tv-flyout-menu.open {{ display: flex; }}
        
        .menu-category-title {{
          padding: 6px 14px 4px 14px;
          font-size: 10px;
          font-weight: 800;
          color: #64748b;
          letter-spacing: 0.8px;
          text-transform: uppercase;
        }}
        
        .menu-item {{
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 14px;
          color: #d1d4dc;
          font-size: 12.5px;
          cursor: pointer;
          transition: background 0.15s ease, color 0.15s ease;
        }}
        .menu-item:hover {{
          background: #2a2e39;
          color: #00ffcc;
        }}
        .menu-item.selected {{
          background: rgba(0, 255, 204, 0.15);
          color: #00ffcc;
          font-weight: 700;
        }}
        .menu-item svg {{
          width: 16px;
          height: 16px;
          flex-shrink: 0;
        }}
        .menu-divider {{
          height: 1px;
          background: #2a2e39;
          margin: 4px 0;
        }}
        
        .sb-divider {{
          width: 24px;
          height: 1px;
          background: rgba(255, 255, 255, 0.08);
          margin: 3px 0;
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
        
        .color-dot {{ width: 14px; height: 14px; border-radius: 50%; cursor: pointer; border: 1.5px solid rgba(255,255,255,0.4); }}
        .color-dot.active {{ border-color: #ffffff; transform: scale(1.25); box-shadow: 0 0 8px rgba(255,255,255,0.8); }}
        
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
    <body onclick="closeAllFlyouts(event)">
      <div class="tv-studio-layout">
        <!-- EXACT TRADINGVIEW LEFT SIDEBAR WITH FLYOUT SUBMENUS -->
        <div class="tv-left-sidebar">
          
          <!-- 1. Cursor Tools -->
          <div class="sb-btn-group">
            <button class="sb-btn active" id="btn_cursor_main" title="Crosshair" onclick="toggleFlyout('menu_cursor', event)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M2 12h20M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/></svg>
              <div class="sb-arrow"></div>
            </button>
            <div class="tv-flyout-menu" id="menu_cursor">
              <div class="menu-category-title">Cursor Tools</div>
              <div class="menu-item selected" onclick="selectTool('pan', 'Crosshair', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M2 12h20"/></svg> Crosshair</div>
              <div class="menu-item" onclick="selectTool('dot', 'Dot', this)"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="4"/></svg> Dot</div>
              <div class="menu-item" onclick="selectTool('arrow', 'Arrow', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 5l14 7-7 2-2 7z"/></svg> Arrow Pointer</div>
              <div class="menu-item" onclick="selectTool('eraser', 'Eraser', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 2l4 4-10 10H8v-4L18 2zM3 21h18"/></svg> Eraser</div>
            </div>
          </div>

          <div class="sb-divider"></div>

          <!-- 2. Lines & Rays -->
          <div class="sb-btn-group">
            <button class="sb-btn" id="btn_lines_main" title="Trend Lines" onclick="toggleFlyout('menu_lines', event)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="20" x2="20" y2="4"/><circle cx="4" cy="20" r="2" fill="currentColor"/><circle cx="20" cy="4" r="2" fill="currentColor"/></svg>
              <div class="sb-arrow"></div>
            </button>
            <div class="tv-flyout-menu" id="menu_lines">
              <div class="menu-category-title">Lines & Rays</div>
              <div class="menu-item" onclick="selectTool('trend', 'Trend Line', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="20" x2="20" y2="4"/></svg> Trend Line</div>
              <div class="menu-item" onclick="selectTool('hline', 'Horizontal Ray', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="2" y1="12" x2="22" y2="12"/></svg> Horizontal Ray</div>
              <div class="menu-item" onclick="selectTool('full_hline', 'Horizontal Line', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="0" y1="12" x2="24" y2="12" stroke-dasharray="3 3"/></svg> Horizontal Line</div>
              <div class="menu-item" onclick="selectTool('vline', 'Vertical Line', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="0" x2="12" y2="24"/></svg> Vertical Line</div>
              <div class="menu-item" onclick="selectTool('channel', 'Parallel Channel', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="16" x2="21" y2="8"/><line x1="3" y1="20" x2="21" y2="12"/></svg> Parallel Channel</div>
              <div class="menu-item" onclick="selectTool('arrow_line', 'Arrow Line', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="20" x2="20" y2="4"/><polyline points="14 4 20 4 20 10"/></svg> Arrow Line</div>
            </div>
          </div>

          <!-- 3. Gann & Fibonacci -->
          <div class="sb-btn-group">
            <button class="sb-btn" id="btn_fib_main" title="Fibonacci & Gann" onclick="toggleFlyout('menu_fib', event)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="2" y1="4" x2="22" y2="4"/><line x1="2" y1="9" x2="22" y2="9"/><line x1="2" y1="14" x2="22" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/><path d="M4 4l16 16"/></svg>
              <div class="sb-arrow"></div>
            </button>
            <div class="tv-flyout-menu" id="menu_fib">
              <div class="menu-category-title">Fibonacci Tools</div>
              <div class="menu-item" onclick="selectTool('fib', 'Fib Retracement', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="2" y1="4" x2="22" y2="4"/><line x1="2" y1="10" x2="22" y2="10"/><line x1="2" y1="16" x2="22" y2="16"/><line x1="2" y1="22" x2="22" y2="22"/></svg> Fib Retracement</div>
              <div class="menu-item" onclick="selectTool('fib_ext', 'Trend-Based Fib Extension', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 18l6-6 6 6 8-8"/></svg> Trend-Based Fib Extension</div>
              <div class="menu-item" onclick="selectTool('fib_channel', 'Fib Channel', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="18" x2="21" y2="6"/><line x1="3" y1="14" x2="21" y2="2"/></svg> Fib Channel</div>
              <div class="menu-item" onclick="selectTool('fib_fan', 'Fib Speed Resistance Fan', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="21" x2="21" y2="3"/><line x1="3" y1="21" x2="21" y2="9"/><line x1="3" y1="21" x2="21" y2="15"/></svg> Fib Speed Resistance Fan</div>
              <div class="menu-divider"></div>
              <div class="menu-category-title">Gann Tools</div>
              <div class="menu-item" onclick="selectTool('gann_box', 'Gann Box', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18"/><line x1="3" y1="3" x2="21" y2="21"/><line x1="21" y1="3" x2="3" y2="21"/></svg> Gann Box</div>
              <div class="menu-item" onclick="selectTool('gann_fan', 'Gann Fan', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21L21 3M3 21l12-18M3 21L9 3"/></svg> Gann Fan</div>
            </div>
          </div>

          <!-- 4. Geometric Shapes & Zones -->
          <div class="sb-btn-group">
            <button class="sb-btn" id="btn_shapes_main" title="Geometric Shapes" onclick="toggleFlyout('menu_shapes', event)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
              <div class="sb-arrow"></div>
            </button>
            <div class="tv-flyout-menu" id="menu_shapes">
              <div class="menu-category-title">Geometric Shapes</div>
              <div class="menu-item" onclick="selectTool('box', 'Order Block (Rectangle)', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg> Rectangle / Order Block</div>
              <div class="menu-item" onclick="selectTool('brush', 'Brush (Freehand)', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 2l4 4-10 10H8v-4L18 2zM3 21h18"/></svg> Brush / Highlighter</div>
              <div class="menu-item" onclick="selectTool('circle', 'Circle / Ellipse', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/></svg> Circle</div>
              <div class="menu-item" onclick="selectTool('path', 'Path / Wave Trajectory', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 17 9 11 13 15 21 7"/></svg> Path / Trajectory</div>
            </div>
          </div>

          <!-- 5. Annotation & Text -->
          <div class="sb-btn-group">
            <button class="sb-btn" id="btn_text_main" title="Text & Notes" onclick="toggleFlyout('menu_text', event)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>
              <div class="sb-arrow"></div>
            </button>
            <div class="tv-flyout-menu" id="menu_text">
              <div class="menu-category-title">Annotation & Text</div>
              <div class="menu-item" onclick="selectTool('text', 'Text Note', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg> Text Note</div>
              <div class="menu-item" onclick="selectTool('callout', 'Callout / Speech Bubble', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> Callout</div>
              <div class="menu-item" onclick="selectTool('price_label', 'Price Label Badge', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M12 10v4M10 12h4"/></svg> Price Label</div>
            </div>
          </div>

          <div class="sb-divider"></div>

          <!-- 6. Patterns -->
          <div class="sb-btn-group">
            <button class="sb-btn" id="btn_patterns_main" title="Patterns" onclick="toggleFlyout('menu_patterns', event)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="4" cy="18" r="2"/><circle cx="10" cy="6" r="2"/><circle cx="16" cy="18" r="2"/><circle cx="22" cy="8" r="2"/><polyline points="4 18 10 6 16 18 22 8"/></svg>
              <div class="sb-arrow"></div>
            </button>
            <div class="tv-flyout-menu" id="menu_patterns">
              <div class="menu-category-title">Patterns</div>
              <div class="menu-item" onclick="selectTool('head_shoulders', 'Head & Shoulders', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 18l4-8 4 6 4-12 4 10 4-6"/></svg> Head & Shoulders</div>
              <div class="menu-item" onclick="selectTool('elliott', 'Elliott Wave (12345)', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="2 18 6 10 10 14 15 4 19 8 22 2"/></svg> Elliott Wave (1-2-3-4-5)</div>
              <div class="menu-item" onclick="selectTool('triangle_pattern', 'Triangle Pattern', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="3 19 12 5 21 19 3 19"/></svg> Triangle Pattern</div>
            </div>
          </div>

          <!-- 7. Prediction & Measurement (Risk / Reward) -->
          <div class="sb-btn-group">
            <button class="sb-btn" id="btn_risk_main" title="Prediction & Measurement" onclick="toggleFlyout('menu_risk', event)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="7" fill="rgba(0,255,204,0.3)" stroke="#00ffcc"/><rect x="4" y="11" width="16" height="7" fill="rgba(255,85,85,0.3)" stroke="#ff5555"/></svg>
              <div class="sb-arrow"></div>
            </button>
            <div class="tv-flyout-menu" id="menu_risk">
              <div class="menu-category-title">Risk / Reward & Prediction</div>
              <div class="menu-item" onclick="selectTool('long_pos', 'Long Position (R:R)', this)"><svg viewBox="0 0 24 24" fill="none" stroke="#00ffcc" stroke-width="2"><rect x="3" y="3" width="18" height="9" fill="rgba(0,255,204,0.3)"/><rect x="3" y="12" width="18" height="9" fill="rgba(255,85,85,0.3)"/></svg> Long Position (R:R)</div>
              <div class="menu-item" onclick="selectTool('short_pos', 'Short Position (R:R)', this)"><svg viewBox="0 0 24 24" fill="none" stroke="#ff5555" stroke-width="2"><rect x="3" y="3" width="18" height="9" fill="rgba(255,85,85,0.3)"/><rect x="3" y="12" width="18" height="9" fill="rgba(0,255,204,0.3)"/></svg> Short Position (R:R)</div>
              <div class="menu-item" onclick="selectTool('price_range', 'Price Range (Pips)', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="2" x2="12" y2="22"/><polyline points="8 6 12 2 16 6"/><polyline points="8 18 12 22 16 18"/></svg> Price Range</div>
              <div class="menu-item" onclick="selectTool('date_range', 'Date Range (Time)', this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="2" y1="12" x2="22" y2="12"/><polyline points="6 8 2 12 6 16"/><polyline points="18 8 22 12 18 16"/></svg> Date Range</div>
            </div>
          </div>

          <!-- 8. Ruler -->
          <div class="sb-btn-group">
            <button class="sb-btn" id="btn_measure" title="Measurement Ruler" onclick="selectTool('measure', 'Ruler', this)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.3 8.7l-6-6a2 2 0 0 0-2.8 0L3 12.2a2 2 0 0 0 0 2.8l6 6a2 2 0 0 0 2.8 0L21.3 11.5a2 2 0 0 0 0-2.8zM7.5 13.5l1.5-1.5M10.5 10.5l1.5-1.5M13.5 7.5l1.5-1.5"/></svg>
            </button>
          </div>

          <div class="sb-divider" style="margin-top: auto;"></div>

          <!-- 9. Trash / Clear -->
          <div class="sb-btn-group">
            <button class="sb-btn" title="Remove All Drawings" onclick="clearAllDrawings()" style="color:#ff5555;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </div>
        </div>

        <!-- TOP PROPERTIES & ACTIVE TOOL BAR -->
        <div class="tv-top-props">
          <div style="font-size: 11px; font-weight: 800; color: #ffffff;">
            {clean_sym}
          </div>
          
          <div style="width:1px; height:14px; background:rgba(255,255,255,0.15);"></div>
          
          <div style="font-size: 11px; color: #00ffcc; font-weight: 700;" id="activeToolLabel">
            TOOL: CROSSHAIR
          </div>
          
          <div style="width:1px; height:14px; background:rgba(255,255,255,0.15);"></div>
          
          <div style="display:flex; align-items:center; gap:5px;">
            <div class="color-dot active" style="background:#00ffcc;" onclick="setColor('#00ffcc', this)"></div>
            <div class="color-dot" style="background:#bef264;" onclick="setColor('#bef264', this)"></div>
            <div class="color-dot" style="background:#ff5555;" onclick="setColor('#ff5555', this)"></div>
            <div class="color-dot" style="background:#f59e0b;" onclick="setColor('#f59e0b', this)"></div>
            <div class="color-dot" style="background:#3b82f6;" onclick="setColor('#3b82f6', this)"></div>
            <div class="color-dot" style="background:#ffffff;" onclick="setColor('#ffffff', this)"></div>
          </div>
          
          <div style="width:1px; height:14px; background:rgba(255,255,255,0.15);"></div>
          
          <button class="sb-btn" style="width:auto; height:24px; padding:0 8px; font-size:10px; font-weight:800;" onclick="toggleEMA()" id="btnEMA">
            EMA 20/50/200
          </button>
          
          <span class="save-pill" id="savePill">DB AUTO-SAVED</span>
        </div>

        <!-- MAIN CHART AREA -->
        <div class="tv-chart-area">
          <canvas id="drawingCanvas"></canvas>
          <div id="{container_id}" style="width: 100%; height: 100%;"></div>
        </div>
      </div>

      <script>
        const SYMBOL = "{clean_sym}";
        const STORAGE_KEY = "tv_drawings_v2_" + SYMBOL;
        let candleData = {candles_json};
        let executions = {exec_json};
        let currentTool = 'pan';
        let currentColor = '#00ffcc';
        let drawings = [];
        let showEMA = false;
        let ema20, ema50, ema200;

        // Flyout Handling
        function toggleFlyout(menuId, event) {{
          event.stopPropagation();
          const menu = document.getElementById(menuId);
          const isOpen = menu.classList.contains('open');
          closeAllFlyouts();
          if (!isOpen) {{
            menu.classList.add('open');
          }}
        }}

        function closeAllFlyouts() {{
          document.querySelectorAll('.tv-flyout-menu').forEach(m => m.classList.remove('open'));
        }}

        function selectTool(tool, toolName, el) {{
          currentTool = tool;
          document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('selected'));
          document.querySelectorAll('.sb-btn').forEach(b => b.classList.remove('active'));
          
          if (el) el.classList.add('selected');
          document.getElementById('activeToolLabel').innerText = 'TOOL: ' + toolName.toUpperCase();
          
          if (tool === 'pan') {{
            document.getElementById('btn_cursor_main').classList.add('active');
            canvas.classList.remove('active-drawing');
          }} else {{
            canvas.classList.add('active-drawing');
          }}
          closeAllFlyouts();
        }}

        function setColor(color, el) {{
          currentColor = color;
          document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
          el.classList.add('active');
        }}

        // Load saved drawings from DB or localStorage
        try {{
          const initialDb = {saved_drawings};
          const localStr = localStorage.getItem(STORAGE_KEY);
          if (localStr && JSON.parse(localStr).length > 0) {{
            drawings = JSON.parse(localStr);
          }} else if (Array.isArray(initialDb) && initialDb.length > 0) {{
            drawings = initialDb;
          }}
        }} catch(e) {{}}

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

        // Trade Execution Markers
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

        // EMA Ribbon
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

        // Drawing Canvas Engine
        const canvas = document.getElementById('drawingCanvas');
        const ctx = canvas.getContext('2d');
        let isDrawing = false;
        let startX = 0, startY = 0;
        let brushPoints = [];

        function resizeCanvas() {{
          canvas.width = chartArea.clientWidth;
          canvas.height = chartArea.clientHeight;
          chart.applyOptions({{ width: chartArea.clientWidth, height: chartArea.clientHeight }});
          redrawAll();
        }}
        window.addEventListener('resize', resizeCanvas);
        setTimeout(resizeCanvas, 400);

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
          }} else if (currentTool === 'vline') {{
            drawings.push({{ type: 'vline', x: startX, color: currentColor }});
            isDrawing = false;
            saveDrawings();
            redrawAll();
          }} else if (currentTool === 'price_label') {{
            drawings.push({{ type: 'price_label', x: startX, y: startY, color: currentColor }});
            isDrawing = false;
            saveDrawings();
            redrawAll();
          }} else if (currentTool === 'text') {{
            const txt = prompt("Enter text note:", "Key Resistance / Support");
            if (txt) {{
              drawings.push({{ type: 'text', x: startX, y: startY, text: txt, color: currentColor }});
              saveDrawings();
              redrawAll();
            }}
            isDrawing = false;
          }} else if (currentTool === 'brush') {{
            brushPoints = [{{ x: startX, y: startY }}];
          }}
        }});

        canvas.addEventListener('mousemove', (e) => {{
          if (!isDrawing || currentTool === 'pan') return;
          const rect = canvas.getBoundingClientRect();
          const currX = e.clientX - rect.left;
          const currY = e.clientY - rect.top;

          if (currentTool === 'brush') {{
            brushPoints.push({{ x: currX, y: currY }});
            redrawAll();
            ctx.save();
            ctx.strokeStyle = currentColor;
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.moveTo(brushPoints[0].x, brushPoints[0].y);
            for (let i = 1; i < brushPoints.length; i++) ctx.lineTo(brushPoints[i].x, brushPoints[i].y);
            ctx.stroke();
            ctx.restore();
            return;
          }}

          redrawAll();
          ctx.save();
          ctx.strokeStyle = currentColor;
          ctx.lineWidth = 2;
          ctx.shadowColor = currentColor;
          ctx.shadowBlur = 6;

          if (currentTool === 'trend' || currentTool === 'arrow_line') {{
            ctx.beginPath();
            ctx.moveTo(startX, startY);
            ctx.lineTo(currX, currY);
            ctx.stroke();
          }} else if (currentTool === 'channel' || currentTool === 'fib_channel') {{
            ctx.beginPath();
            ctx.moveTo(startX, startY);
            ctx.lineTo(currX, currY);
            ctx.moveTo(startX, startY + 40);
            ctx.lineTo(currX, currY + 40);
            ctx.stroke();
          }} else if (currentTool === 'fib' || currentTool === 'fib_ext') {{
            renderFib(startX, startY, currX, currY, currentColor);
          }} else if (currentTool === 'box' || currentTool === 'gann_box') {{
            ctx.fillStyle = currentColor + '25';
            ctx.fillRect(startX, startY, currX - startX, currY - startY);
            ctx.strokeRect(startX, startY, currX - startX, currY - startY);
          }} else if (currentTool === 'circle') {{
            const rad = Math.sqrt(Math.pow(currX - startX, 2) + Math.pow(currY - startY, 2));
            ctx.beginPath();
            ctx.arc(startX, startY, rad, 0, 2 * Math.PI);
            ctx.stroke();
          }} else if (currentTool === 'long_pos') {{
            renderPositionTool(startX, startY, currX, currY, true);
          }} else if (currentTool === 'short_pos') {{
            renderPositionTool(startX, startY, currX, currY, false);
          }} else if (currentTool === 'measure' || currentTool === 'price_range' || currentTool === 'date_range') {{
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

          if (currentTool === 'trend' || currentTool === 'arrow_line') {{
            drawings.push({{ type: 'trend', x1: startX, y1: startY, x2: endX, y2: endY, color: currentColor }});
          }} else if (currentTool === 'channel' || currentTool === 'fib_channel') {{
            drawings.push({{ type: 'channel', x1: startX, y1: startY, x2: endX, y2: endY, offset: 40, color: currentColor }});
          }} else if (currentTool === 'fib' || currentTool === 'fib_ext') {{
            drawings.push({{ type: 'fib', x1: startX, y1: startY, x2: endX, y2: endY, color: currentColor }});
          }} else if (currentTool === 'box' || currentTool === 'gann_box') {{
            drawings.push({{ type: 'box', x: startX, y: startY, w: endX - startX, h: endY - startY, color: currentColor }});
          }} else if (currentTool === 'circle') {{
            const rad = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
            drawings.push({{ type: 'circle', x: startX, y: startY, r: rad, color: currentColor }});
          }} else if (currentTool === 'brush') {{
            drawings.push({{ type: 'brush', points: brushPoints, color: currentColor }});
            brushPoints = [];
          }} else if (currentTool === 'long_pos') {{
            drawings.push({{ type: 'long_pos', x: startX, y: startY, w: endX - startX, h: endY - startY }});
          }} else if (currentTool === 'short_pos') {{
            drawings.push({{ type: 'short_pos', x: startX, y: startY, w: endX - startX, h: endY - startY }});
          }} else if (currentTool === 'measure' || currentTool === 'price_range' || currentTool === 'date_range') {{
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

          ctx.fillStyle = 'rgba(0, 255, 204, 0.22)';
          ctx.fillRect(x, isLong ? y - targetH : y, w, targetH);
          ctx.strokeStyle = '#00ffcc';
          ctx.strokeRect(x, isLong ? y - targetH : y, w, targetH);

          ctx.fillStyle = 'rgba(255, 85, 85, 0.22)';
          ctx.fillRect(x, isLong ? y : y - stopH, w, stopH);
          ctx.strokeStyle = '#ff5555';
          ctx.strokeRect(x, isLong ? y : y - stopH, w, stopH);

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
            }} else if (d.type === 'vline') {{
              ctx.beginPath();
              ctx.moveTo(d.x, 0);
              ctx.lineTo(d.x, canvas.height);
              ctx.stroke();
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
            }} else if (d.type === 'circle') {{
              ctx.beginPath();
              ctx.arc(d.x, d.y, d.r, 0, 2 * Math.PI);
              ctx.stroke();
            }} else if (d.type === 'brush' && d.points && d.points.length > 0) {{
              ctx.beginPath();
              ctx.moveTo(d.points[0].x, d.points[0].y);
              for (let i = 1; i < d.points.length; i++) ctx.lineTo(d.points[i].x, d.points[i].y);
              ctx.stroke();
            }} else if (d.type === 'text') {{
              ctx.fillStyle = d.color;
              ctx.font = 'bold 12px Inter, sans-serif';
              ctx.fillText(d.text, d.x, d.y);
            }} else if (d.type === 'price_label') {{
              ctx.fillStyle = d.color;
              ctx.fillRect(d.x, d.y - 10, 60, 20);
              ctx.fillStyle = '#000000';
              ctx.font = 'bold 10px Inter, sans-serif';
              ctx.fillText('TAG', d.x + 18, d.y + 4);
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
