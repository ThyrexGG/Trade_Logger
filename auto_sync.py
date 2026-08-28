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

# Load environment
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

import mt5_sync
import capital_sync

SYNC_INTERVAL_SECONDS = 120  # Sync every 2 minutes

def run_auto_sync():
    log("TRADELOGGER AUTOMATIC CLOUD SYNC DAEMON STARTED")
    log(f"Interval: Every {SYNC_INTERVAL_SECONDS} seconds")
    
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
            
        log(f"Sleeping for {SYNC_INTERVAL_SECONDS}s...")
        time.sleep(SYNC_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        run_auto_sync()
    except Exception as exc:
        log(f"CRITICAL DAEMON CRASH: {exc}")
