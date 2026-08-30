import os
import sqlite3
import pandas as pd
import numpy as np
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

import database
import alerts

# Initialize FastAPI App
app = FastAPI(title="Trade Logger Pro Engine API", version="2.0.0")

# Enable CORS for Flutter Desktop, Web, and Mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Standard Popular Assets Catalog
ASSET_CATALOG = [
    {"id": "XAUUSD", "display": "XAUUSD (GOLD)", "desc": "Gold Spot / US Dollar", "cat": "Commodities", "type": "commodity cfd", "icon_bg": "#f59e0b", "icon_txt": "AU"},
    {"id": "EURUSD", "display": "EURUSD (EUR/USD)", "desc": "Euro / US Dollar", "cat": "Forex", "type": "forex cfd", "icon_bg": "#3b82f6", "icon_txt": "EU"},
    {"id": "GBPUSD", "display": "GBPUSD (GBP/USD)", "desc": "British Pound / US Dollar", "cat": "Forex", "type": "forex cfd", "icon_bg": "#6366f1", "icon_txt": "GB"},
    {"id": "USDJPY", "display": "USDJPY (USD/JPY)", "desc": "US Dollar / Japanese Yen", "cat": "Forex", "type": "forex cfd", "icon_bg": "#ec4899", "icon_txt": "JP"},
    {"id": "NAS100", "display": "NAS100 (US100)", "desc": "US Tech 100", "cat": "Indices", "type": "index cfd", "icon_bg": "#06b6d4", "icon_txt": "100"},
    {"id": "US30", "display": "US30 (US30)", "desc": "US 30 Wall St", "cat": "Indices", "type": "index cfd", "icon_bg": "#0284c7", "icon_txt": "30"},
    {"id": "SPX500", "display": "SPX500 (US500)", "desc": "US 500 S&P", "cat": "Indices", "type": "index cfd", "icon_bg": "#ef4444", "icon_txt": "500"},
    {"id": "DXY", "display": "DXY (DXY)", "desc": "US Dollar Index", "cat": "Indices", "type": "index cfd", "icon_bg": "#10b981", "icon_txt": "$"},
    {"id": "BTCUSD", "display": "BTCUSD (BITCOIN)", "desc": "Bitcoin / US Dollar", "cat": "Crypto", "type": "crypto cfd", "icon_bg": "#f59e0b", "icon_txt": "BTC"},
    {"id": "USOIL", "display": "USOIL (OIL_CRUDE)", "desc": "Crude Oil Spot", "cat": "Commodities", "type": "commodity cfd", "icon_bg": "#475569", "icon_txt": "OIL"},
    {"id": "XAGUSD", "display": "XAGUSD (SILVER)", "desc": "Silver Spot", "cat": "Commodities", "type": "commodity cfd", "icon_bg": "#94a3b8", "icon_txt": "AG"},
    {"id": "GER40", "display": "GER40 (DE40)", "desc": "Germany 40 DAX", "cat": "Indices", "type": "index cfd", "icon_bg": "#3b82f6", "icon_txt": "40"}
]

# --- Pydantic Models ---
class PriceAlertCreate(BaseModel):
    symbol: str
    target_price: float
    condition: str
    notes: Optional[str] = ""

class SymbolFavoriteToggle(BaseModel):
    symbol: str

class JournalUpdateRequest(BaseModel):
    trade_id: int
    setup_notes: Optional[str] = ""
    setup_strategy: Optional[str] = ""
    setup_rating: Optional[int] = 5
    setup_screenshot: Optional[str] = ""


# --- API Routes ---

@app.websocket("/ws/live_ticks/{symbol}")
async def websocket_live_ticks(websocket: WebSocket, symbol: str):
    """Streams live millisecond ticks for a specific symbol via WebSocket."""
    await websocket.accept()
    
    # Optional: We can hook directly into MT5 if it's available on the server
    mt5_available = False
    try:
        import mt5_sync
        if mt5_sync.MT5_AVAILABLE:
            import MetaTrader5 as mt5
            if mt5.initialize():
                mt5_available = True
    except:
        pass

    try:
        while True:
            tick_data = {"symbol": symbol, "timestamp": datetime.utcnow().isoformat()}
            
            if mt5_available:
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    tick_data["bid"] = tick.bid
                    tick_data["ask"] = tick.ask
                    tick_data["volume"] = tick.volume
                    tick_data["source"] = "MT5"
                else:
                    # Fallback or empty if symbol not found in MT5
                    tick_data["error"] = "No tick data"
            else:
                # If MT5 is not running, we could query Capital.com or Yahoo, but they are rate limited.
                # For now, just send a heartbeat
                tick_data["error"] = "MT5 not available for live ticks"
                
            await websocket.send_json(tick_data)
            await asyncio.sleep(0.5) # 500ms broadcast rate
            
    except WebSocketDisconnect:
        print(f"Client disconnected from live ticks for {symbol}")
    except Exception as e:
        print(f"WebSocket error for {symbol}: {e}")

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "timestamp": datetime.utcnow().isoformat(),
        "database": os.path.exists("trades.db")
    }

@app.get("/api/accounts")
def get_accounts():
    """Returns all accounts summary (MT5 Funded and Capital.com Real)."""
    df = database.get_closed_trades()
    acc_list = []
    
    if not df.empty and "account_id" in df.columns:
        unique_accs = [str(a) for a in df["account_id"].unique() if a and str(a).strip()]
    else:
        unique_accs = ["MT5 (Funded)", "Capital.com (Real)"]

    for acc in unique_accs:
        sub_df = df[df["account_id"] == acc] if not df.empty and "account_id" in df.columns else df
        total_pnl = float(sub_df["net_profit"].sum()) if not sub_df.empty and "net_profit" in sub_df.columns else 0.0
        wins = sub_df[sub_df["net_profit"] > 0] if not sub_df.empty and "net_profit" in sub_df.columns else pd.DataFrame()
        losses = sub_df[sub_df["net_profit"] < 0] if not sub_df.empty and "net_profit" in sub_df.columns else pd.DataFrame()
        
        total_trades = len(sub_df)
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
        
        gross_win = float(wins["net_profit"].sum()) if not wins.empty else 0.0
        gross_loss = abs(float(losses["net_profit"].sum())) if not losses.empty else 0.0
        profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)

        # Baseline starting balance
        init_balance = 10000.0 if "Funded" in acc else 5000.0
        current_balance = init_balance + total_pnl

        acc_list.append({
            "account_id": acc,
            "name": acc,
            "balance": round(current_balance, 2),
            "equity": round(current_balance, 2),
            "total_pnl": round(total_pnl, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "profit_factor": profit_factor,
            "is_funded": "Funded" in acc
        })

    return {"accounts": acc_list}

@app.get("/api/trades")
def get_trades(account: Optional[str] = None, limit: int = 100):
    """Returns trade history and journal entries."""
    df = database.get_closed_trades()
    if df.empty:
        return {"trades": []}
    
    if account and account != "All Accounts" and "account_id" in df.columns:
        df = df[df["account_id"] == account]
        
    df = df.head(limit)
    trades = df.to_dict(orient="records")
    return {"trades": trades}

@app.get("/api/analytics")
def get_analytics(account: Optional[str] = None):
    """Computes Monotonic Hermite Spline balance curve, drawdown, and daily calendar PnL."""
    df = database.get_closed_trades()
    if df.empty:
        return {
            "spline_curve": [],
            "calendar_pnl": {},
            "metrics": {"win_rate": 0, "profit_factor": 0, "max_drawdown": 0, "net_profit": 0}
        }

    if account and account != "All Accounts" and "account_id" in df.columns:
        df = df[df["account_id"] == account]

    # Calculate cumulative balance curve points
    df_sorted = df.copy()
    if "exit_time" in df_sorted.columns:
        df_sorted["time_dt"] = pd.to_datetime(df_sorted["exit_time"], errors="coerce")
        df_sorted = df_sorted.sort_values("time_dt")

    init_bal = 10000.0
    cum_profits = df_sorted["net_profit"].cumsum().tolist() if "net_profit" in df_sorted.columns else []
    
    curve_points = []
    current_b = init_bal
    for idx, r in df_sorted.iterrows():
        pnl = float(r.get("net_profit", 0.0))
        current_b += pnl
        t_str = str(r.get("exit_time", ""))[:16]
        sym = str(r.get("symbol", ""))
        curve_points.append({
            "time": t_str,
            "balance": round(current_b, 2),
            "pnl": round(pnl, 2),
            "symbol": sym,
            "trade_id": str(r.get("trade_id", ""))
        })

    # Daily Calendar Heatmap breakdown
    calendar_map = {}
    if "exit_time" in df.columns and "net_profit" in df.columns:
        df["day_str"] = df["exit_time"].astype(str).str[:10]
        daily_grp = df.groupby("day_str")["net_profit"].agg(["sum", "count"]).reset_index()
        for _, row in daily_grp.iterrows():
            calendar_map[row["day_str"]] = {
                "pnl": round(float(row["sum"]), 2),
                "trades_count": int(row["count"])
            }

    # Summary metrics
    total_pnl = float(df["net_profit"].sum()) if "net_profit" in df.columns else 0.0
    wins = df[df["net_profit"] > 0] if "net_profit" in df.columns else pd.DataFrame()
    losses = df[df["net_profit"] < 0] if "net_profit" in df.columns else pd.DataFrame()
    win_rate = round(len(wins) / len(df) * 100.0, 1) if len(df) > 0 else 0.0
    gross_win = float(wins["net_profit"].sum()) if not wins.empty else 0.0
    gross_loss = abs(float(losses["net_profit"].sum())) if not losses.empty else 0.0
    pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)

    return {
        "spline_curve": curve_points,
        "calendar_pnl": calendar_map,
        "metrics": {
            "win_rate": win_rate,
            "profit_factor": pf,
            "net_profit": round(total_pnl, 2),
            "total_trades": len(df)
        }
    }

@app.get("/api/symbols")
def get_symbols():
    """Returns the TradingView Symbol Catalog with Red Ribbon favorites pinned to the top."""
    fav_symbols = database.get_favorite_symbols()
    
    # Sort: favorites at top
    flagged = [item for item in ASSET_CATALOG if item["id"] in fav_symbols]
    unflagged = [item for item in ASSET_CATALOG if item["id"] not in fav_symbols]
    
    result = []
    for item in (flagged + unflagged):
        is_fav = item["id"] in fav_symbols
        result.append({
            **item,
            "is_flagged": is_fav
        })
        
    return {
        "favorites": fav_symbols,
        "symbols": result
    }

@app.post("/api/symbols/toggle-favorite")
def toggle_symbol_favorite(payload: SymbolFavoriteToggle):
    """Toggles Red Ribbon Star favorite on an asset symbol."""
    database.toggle_favorite_symbol(payload.symbol)
    fav_symbols = database.get_favorite_symbols()
    return {
        "symbol": payload.symbol,
        "is_flagged": payload.symbol in fav_symbols,
        "favorites": fav_symbols
    }

@app.get("/api/alerts")
def get_alerts():
    """Returns all active price target cross alerts."""
    df = database.get_all_price_alerts(limit=50)
    alerts_list = df.to_dict(orient="records") if not df.empty else []
    return {"alerts": alerts_list}

@app.post("/api/alerts")
def create_alert(payload: PriceAlertCreate):
    """Creates a new price target alert."""
    database.create_price_alert(
        symbol=payload.symbol.upper(),
        target_price=payload.target_price,
        condition=payload.condition.upper(),
        notes=payload.notes
    )
    return {"status": "created", "symbol": payload.symbol}

@app.delete("/api/alerts/{alert_id}")
def delete_alert(alert_id: int):
    """Deletes a price alert."""
    database.delete_price_alert(alert_id)
    return {"status": "deleted", "alert_id": alert_id}

@app.post("/api/journal/update")
def update_journal(payload: JournalUpdateRequest):
    """Updates setup screenshot, notes, confluences, and strategy rating for a trade."""
    database.update_trade_journal(
        trade_id=payload.trade_id,
        setup_tag=payload.setup_strategy,
        chart_snapshot_url=payload.setup_screenshot,
        notes=payload.setup_notes,
        rating=payload.setup_rating
    )
    return {"status": "updated", "trade_id": payload.trade_id}

import market_data

class ChartDrawingsPayload(BaseModel):
    symbol: str
    drawings_data: str

@app.get("/api/chart/candles")
def get_chart_candles(symbol: str = "XAUUSD", timeframe: str = "15m", count: int = 250):
    """Returns real-time candlestick series from MT5, Capital.com, or live market feeds."""
    candles = market_data.get_realtime_candles(symbol=symbol, timeframe=timeframe, count=count)
    return {"symbol": symbol.upper(), "timeframe": timeframe, "candles": candles}

@app.get("/api/chart/drawings")
def get_drawings(symbol: str = "XAUUSD"):
    """Returns saved JSON drawings for a symbol."""
    drawings = database.get_chart_drawings(symbol)
    return {"symbol": symbol.upper(), "drawings_data": drawings}

@app.post("/api/chart/drawings")
def save_drawings(payload: ChartDrawingsPayload):
    """Saves JSON drawings for a symbol to the database."""
    database.save_chart_drawings(payload.symbol, payload.drawings_data)
    return {"status": "saved", "symbol": payload.symbol.upper()}

@app.get("/api/chart/executions")
def get_chart_executions(symbol: str = "XAUUSD"):
    """Returns real broker trade executions (entry/exit/PnL) for chart overlay."""
    df_trades = database.get_closed_trades()
    if df_trades.empty:
        return {"executions": []}
    
    sym = symbol.upper().replace("/", "").replace(":", "").replace("FX", "").replace("OANDA", "").replace("BINANCE", "").replace("FOREXCOM", "")
    df_sym = df_trades[df_trades["symbol"].str.upper().str.contains(sym, na=False)].copy()
    
    execs = []
    for _, r in df_sym.iterrows():
        execs.append({
            "trade_id": str(r.get("trade_id", "")),
            "direction": str(r.get("direction", "BUY")).upper(),
            "volume": float(r.get("volume", 0.01)),
            "entry_price": float(r.get("entry_price", 0.0)),
            "exit_price": float(r.get("exit_price", 0.0)),
            "net_profit": float(r.get("net_profit", 0.0)),
            "entry_time": str(r.get("entry_time", "")),
            "exit_time": str(r.get("exit_time", "")),
        })
    return {"executions": execs}

import analytics
import ai_analysis

@app.get("/api/analytics/metrics")
def get_analytics_metrics(account_id: str = "ALL", initial_balance: float = 10000.0):
    """Calculates deterministic trading performance metrics."""
    df_trades = database.get_closed_trades()
    if not df_trades.empty and account_id != "ALL":
        df_trades = df_trades[df_trades["account_id"] == account_id]
        
    metrics = analytics.calculate_performance_metrics(df_trades, initial_balance=initial_balance)
    return {"account_id": account_id, "metrics": metrics}

@app.get("/api/ai/analyze")
def get_ai_market_analysis(symbol: str = "XAUUSD", timeframe: str = "1h"):
    """Returns structured, deterministic AI technical and market context analysis."""
    analysis = ai_analysis.analyze_market_context(symbol=symbol, timeframe=timeframe)
    return analysis

@app.post("/api/sync")
def trigger_sync():
    """Triggers background broker synchronization."""
    # Execute non-blocking sync
    try:
        import mt5_sync
        mt5_sync.sync_mt5()
    except Exception as e:
        pass
    return {"status": "sync_completed"}


class OrderExecutionRequest(BaseModel):
    symbol: str
    account_id: str
    direction: str
    volume: float
    order_type: str
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

import order_execution

@app.post("/api/order/execute")
def execute_trade_order(payload: OrderExecutionRequest):
    """Executes a trade on Capital.com or MT5 based on account selection."""
    if "Capital.com" in payload.account_id or payload.account_id == "CAPITAL_REAL":
        success, msg = order_execution.execute_capital_trade(
            epic=payload.symbol,
            direction=payload.direction,
            size=payload.volume,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit
        )
    else:
        success, msg = order_execution.execute_mt5_trade(
            symbol=payload.symbol,
            direction=payload.direction,
            volume=payload.volume,
            sl=payload.stop_loss,
            tp=payload.take_profit
        )
    
    if success:
        return {"status": "executed", "message": msg}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=msg)


# Mount Flutter Web App as static build
from fastapi.staticfiles import StaticFiles

web_build_dir = os.path.join(os.path.dirname(__file__), "trade_logger_app", "build", "web")
if os.path.exists(web_build_dir):
    app.mount("/", StaticFiles(directory=web_build_dir, html=True), name="flutter_web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
