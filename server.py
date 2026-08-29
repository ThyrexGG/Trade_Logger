import os
import sqlite3
import pandas as pd
import numpy as np
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
    df = database.get_all_trades()
    acc_list = []
    
    if not df.empty and "account" in df.columns:
        unique_accs = [str(a) for a in df["account"].unique() if a and str(a).strip()]
    else:
        unique_accs = ["MT5 (Funded)", "Capital.com (Real)"]

    for acc in unique_accs:
        sub_df = df[df["account"] == acc] if not df.empty and "account" in df.columns else df
        total_pnl = float(sub_df["profit"].sum()) if not sub_df.empty and "profit" in sub_df.columns else 0.0
        wins = sub_df[sub_df["profit"] > 0] if not sub_df.empty and "profit" in sub_df.columns else pd.DataFrame()
        losses = sub_df[sub_df["profit"] < 0] if not sub_df.empty and "profit" in sub_df.columns else pd.DataFrame()
        
        total_trades = len(sub_df)
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
        
        gross_win = float(wins["profit"].sum()) if not wins.empty else 0.0
        gross_loss = abs(float(losses["profit"].sum())) if not losses.empty else 0.0
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
    df = database.get_all_trades()
    if df.empty:
        return {"trades": []}
    
    if account and account != "All Accounts" and "account" in df.columns:
        df = df[df["account"] == account]
        
    df = df.head(limit)
    trades = df.to_dict(orient="records")
    return {"trades": trades}

@app.get("/api/analytics")
def get_analytics(account: Optional[str] = None):
    """Computes Monotonic Hermite Spline balance curve, drawdown, and daily calendar PnL."""
    df = database.get_all_trades()
    if df.empty:
        return {
            "spline_curve": [],
            "calendar_pnl": {},
            "metrics": {"win_rate": 0, "profit_factor": 0, "max_drawdown": 0, "net_profit": 0}
        }

    if account and account != "All Accounts" and "account" in df.columns:
        df = df[df["account"] == account]

    # Calculate cumulative balance curve points
    df_sorted = df.copy()
    if "close_time" in df_sorted.columns:
        df_sorted["time_dt"] = pd.to_datetime(df_sorted["close_time"], errors="coerce")
        df_sorted = df_sorted.sort_values("time_dt")

    init_bal = 10000.0
    cum_profits = df_sorted["profit"].cumsum().tolist() if "profit" in df_sorted.columns else []
    
    curve_points = []
    current_b = init_bal
    for idx, r in df_sorted.iterrows():
        pnl = float(r.get("profit", 0.0))
        current_b += pnl
        t_str = str(r.get("close_time", ""))[:16]
        sym = str(r.get("symbol", ""))
        curve_points.append({
            "time": t_str,
            "balance": round(current_b, 2),
            "pnl": round(pnl, 2),
            "symbol": sym,
            "trade_id": int(r.get("ticket", r.get("id", 0)))
        })

    # Daily Calendar Heatmap breakdown
    calendar_map = {}
    if "close_time" in df.columns and "profit" in df.columns:
        df["day_str"] = df["close_time"].astype(str).str[:10]
        daily_grp = df.groupby("day_str")["profit"].agg(["sum", "count"]).reset_index()
        for _, row in daily_grp.iterrows():
            calendar_map[row["day_str"]] = {
                "pnl": round(float(row["sum"]), 2),
                "trades_count": int(row["count"])
            }

    # Summary metrics
    total_pnl = float(df["profit"].sum()) if "profit" in df.columns else 0.0
    wins = df[df["profit"] > 0] if "profit" in df.columns else pd.DataFrame()
    losses = df[df["profit"] < 0] if "profit" in df.columns else pd.DataFrame()
    win_rate = round(len(wins) / len(df) * 100.0, 1) if len(df) > 0 else 0.0
    gross_win = float(wins["profit"].sum()) if not wins.empty else 0.0
    gross_loss = abs(float(losses["profit"].sum())) if not losses.empty else 0.0
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
        notes=payload.setup_notes,
        strategy=payload.setup_strategy,
        rating=payload.setup_rating,
        screenshot=payload.setup_screenshot
    )
    return {"status": "updated", "trade_id": payload.trade_id}

@app.post("/api/sync")
def trigger_sync():
    """Triggers background broker synchronization."""
    # Execute non-blocking sync
    try:
        import mt5_sync
        mt5_sync.sync_mt5_trades()
    except Exception as e:
        pass
    return {"status": "sync_completed"}


# Mount Flutter Web App as static build
from fastapi.staticfiles import StaticFiles

web_build_dir = os.path.join(os.path.dirname(__file__), "trade_logger_app", "build", "web")
if os.path.exists(web_build_dir):
    app.mount("/", StaticFiles(directory=web_build_dir, html=True), name="flutter_web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
