import time
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

LOG_FILE = os.path.join(os.path.dirname(__file__), "sync_log.txt")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

import mt5_sync
import capital_sync
import database
import alerts

SYNC_INTERVAL_SECONDS = 30  # Sync every 30 seconds for live floating PnL and trade updates

def run_auto_sync():
    log("TRADELOGGER AUTOMATIC CLOUD SYNC & PUSH ALERTS DAEMON STARTED")
    log(f"Interval: Every {SYNC_INTERVAL_SECONDS} seconds")
    
    # Initialize known trades cache
    try:
        df_init = database.get_closed_trades()
        known_trade_ids = set(df_init["trade_id"].tolist()) if not df_init.empty else set()
        log(f"Loaded {len(known_trade_ids)} initial trades into alert cache.")
    except Exception as e:
        known_trade_ids = set()
        log(f"Cache init warning: {e}")
    
    while True:
        log("Starting sync cycle...")
        
        # 1. Sync MetaTrader 5
        try:
            mt5_success = mt5_sync.sync_mt5()
            if mt5_success:
                log("MT5 Sync: SUCCESS")
            else:
                log("MT5 Sync: Completed (no new trades or terminal busy)")
        except Exception as e:
            log(f"MT5 Sync Exception: {e}")
            
        # 2. Sync Capital.com
        try:
            cap_success = capital_sync.sync_capital()
            if cap_success:
                log("Capital.com Sync: SUCCESS")
            else:
                log("Capital.com Sync: Completed (no new trades)")
        except Exception as e:
            log(f"Capital.com Sync Exception: {e}")
            
        # 3. Check for newly closed trades to trigger push notifications
        try:
            current_df = database.get_closed_trades()
            if not current_df.empty:
                new_trades = current_df[~current_df["trade_id"].isin(known_trade_ids)]
                if not new_trades.empty:
                    log(f"Detected {len(new_trades)} newly closed trades! Dispatching push alerts...")
                    for _, row in new_trades.iterrows():
                        trade_dict = row.to_dict()
                        alerts.notify_trade_closed(trade_dict)
                        known_trade_ids.add(row["trade_id"])
                        log(f"Alert sent for trade {row['trade_id']} ({row['symbol']} PnL: ${row['net_profit']:.2f})")
        except Exception as alert_err:
            log(f"Alert dispatch error: {alert_err}")
            
        log(f"Sleeping for {SYNC_INTERVAL_SECONDS}s...")
        time.sleep(SYNC_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        run_auto_sync()
    except Exception as exc:
        log(f"CRITICAL DAEMON CRASH: {exc}")
