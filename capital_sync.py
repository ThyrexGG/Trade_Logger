import requests
import os
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import time
import database

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Constants for Capital.com API
LIVE_API_URL = "https://api-capital.backend-capital.com/api/v1"
DEMO_API_URL = "https://demo-api-capital.backend-capital.com/api/v1"

def clean_symbol(symbol):
    """Cleans Capital.com epics to simple standard symbols (e.g., US500 -> SPX500, Gold -> XAUUSD)."""
    symbol = symbol.upper()
    mapping = {
        "GOLD": "XAUUSD",
        "SILVER": "XAGUSD",
        "BRENT": "BRENT",
        "US500": "SPX500",
        "DE30": "GER30",
        "US30": "DJ30",
    }
    return mapping.get(symbol, symbol)

def sync_capital():
    # Reload .env freshly
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

    api_key = os.getenv("CAPITAL_API_KEY")
    email = os.getenv("CAPITAL_EMAIL")
    password = os.getenv("CAPITAL_PASSWORD")
    account_id = os.getenv("CAPITAL_ACCOUNT_ID")
    is_demo = str(os.getenv("CAPITAL_IS_DEMO", "false")).strip().lower() == "true"

    # Try Streamlit Cloud secrets as fallback if running on cloud
    try:
        import streamlit as st
        if hasattr(st, "secrets") and len(st.secrets) > 0:
            api_key = st.secrets.get("CAPITAL_API_KEY", api_key) or api_key
            email = st.secrets.get("CAPITAL_EMAIL", email) or email
            password = st.secrets.get("CAPITAL_PASSWORD", password) or password
            account_id = str(st.secrets.get("CAPITAL_ACCOUNT_ID", account_id) or account_id or "")
            if "CAPITAL_IS_DEMO" in st.secrets:
                is_demo = str(st.secrets["CAPITAL_IS_DEMO"]).strip().lower() == "true"
    except Exception:
        pass

    # Strip any extra accidental surrounding quotes from .env strings
    if api_key: api_key = api_key.strip('"\'')
    if email: email = email.strip('"\'')
    if password: password = password.strip('"\'')
    if account_id: account_id = account_id.strip('"\'')

    # Initialize the database
    database.init_db()

    if not all([api_key, email, password, account_id]):
        print("Capital.com credentials missing. Skipping sync.")
        return False

    base_url = DEMO_API_URL if is_demo else LIVE_API_URL
    print(f"Connecting to Capital.com API ({'Demo' if is_demo else 'Live'})...")

    # Step 1: Establish Session (Log in)
    session = requests.Session()
    headers = {
        "X-CAP-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "identifier": email,
        "password": password
    }

    try:
        response = session.post(f"{base_url}/session", headers=headers, json=payload)
        if response.status_code != 200:
            print(f"Authentication failed: {response.status_code} - {response.text}")
            return False
            
        cst = response.headers.get("CST")
        security_token = response.headers.get("X-SECURITY-TOKEN")
        
        if not cst or not security_token:
            print("Failed to retrieve session tokens from response headers.")
            return False
            
        headers.update({
            "CST": cst,
            "X-SECURITY-TOKEN": security_token
        })
        print("Session established successfully.")
        
    except Exception as e:
        print(f"Error connecting to Capital.com: {e}")
        return False

    # Step 2: Fetch Transaction History (To get realized profit/loss & deal IDs)
    last_ts = database.get_last_deal_timestamp(account_id)
    if last_ts > 0:
        # Start 3 days before the last known deal to catch any overlaps/updates
        start_date = datetime.fromtimestamp(last_ts - 3 * 86400, tz=timezone.utc)
    else:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        
    end_date = datetime.now(timezone.utc)
    from_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
    
    params = {
        "from": from_str,
        "limit": 100
    }

    print(f"Fetching Capital.com transactions from {from_str}...")
    try:
        res = session.get(f"{base_url}/history/transactions", headers=headers, params=params)
        if res.status_code != 200:
            print(f"Failed to fetch transaction history: {res.status_code} - {res.text}")
            return False
            
        data = res.json()
        transactions = data.get("transactions", [])
        closed_trade_txs = [t for t in transactions if t.get("transactionType") == "TRADE" and t.get("note") == "Trade closed"]
        print(f"Found {len(closed_trade_txs)} closed trade transactions.")
        
    except Exception as e:
        print(f"Error fetching transactions: {e}")
        return False
        
    if not closed_trade_txs:
        print("No new Capital.com transactions to process.")
        return True

    # Step 3: Fetch Activities day-by-day (restricted to 1-day windows) to locate execution details
    print("Fetching activities in 1-day increments...")
    activities_by_deal = {}
    delta_days = (end_date - start_date).days + 2
    
    for i in range(delta_days):
        chunk_start = start_date + timedelta(days=i)
        chunk_end = chunk_start + timedelta(days=1)
        
        # Stop if we exceed current time
        if chunk_start > end_date:
            break
            
        from_str_chunk = chunk_start.strftime("%Y-%m-%dT%H:%M:%S")
        to_str_chunk = chunk_end.strftime("%Y-%m-%dT%H:%M:%S")
        
        params_chunk = {
            "from": from_str_chunk,
            "to": to_str_chunk,
            "detailed": "true"
        }
        
        time.sleep(0.2) # Rate limit protection
        try:
            activity_res = session.get(f"{base_url}/history/activity", headers=headers, params=params_chunk)
            if activity_res.status_code == 200:
                chunk = activity_res.json().get("activities", [])
                for act in chunk:
                    deal_id = act.get("dealId")
                    if deal_id:
                        if deal_id not in activities_by_deal:
                            activities_by_deal[deal_id] = []
                        activities_by_deal[deal_id].append(act)
            else:
                print(f"Warning: Failed to fetch activities for {from_str_chunk}: {activity_res.text}")
        except Exception as e:
            print(f"Warning: Error fetching activity chunk: {e}")

    # Step 4: Reconstruct and save trades
    trades_to_save = []
    raw_deals_list = []
    
    for tx in closed_trade_txs:
        deal_id = tx.get("dealId")
        net_profit = float(tx.get("size", 0.0))
        exit_time_str = tx.get("dateUtc")
        
        # Get matching activities
        deal_activities = activities_by_deal.get(deal_id, [])
        if not deal_activities:
            print(f"Skipping deal {deal_id} because no detailed activities were returned in the synced range.")
            continue
            
        # Sort activities chronologically
        deal_activities.sort(key=lambda a: a.get("dateUTC", ""))
        
        opening_act = deal_activities[0]
        closing_act = deal_activities[-1]
        
        details = closing_act.get("details", {})
        if not details:
            details = opening_act.get("details", {})
            
        symbol = clean_symbol(tx.get("instrumentName", closing_act.get("epic", "UNKNOWN")))
        
        # Determine direction
        closing_dir = details.get("direction", "SELL")
        trade_direction = "SHORT" if closing_dir == "BUY" else "LONG"
        
        opening_details = opening_act.get("details", {})
        if opening_details and "direction" in opening_details:
            trade_direction = "LONG" if opening_details["direction"] == "BUY" else "SHORT"
            
        volume = float(details.get("size", 0.0))
        entry_price = float(details.get("openPrice", opening_details.get("level", 0.0)))
        exit_price = float(details.get("level", 0.0))
        
        entry_time_str = opening_act.get("dateUTC", exit_time_str)
        
        try:
            t_entry = datetime.fromisoformat(entry_time_str.replace("Z", ""))
            t_exit = datetime.fromisoformat(exit_time_str.replace("Z", ""))
            duration_minutes = (t_exit - t_entry).total_seconds() / 60.0
        except Exception:
            duration_minutes = 0.0
            
        trade_data = {
            "trade_id": deal_id,
            "account_id": account_id,
            "symbol": symbol,
            "direction": trade_direction,
            "volume": volume,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "commission": 0.0,
            "swap": 0.0,
            "gross_profit": net_profit,
            "net_profit": net_profit,
            "entry_time": entry_time_str,
            "exit_time": exit_time_str,
            "duration_minutes": duration_minutes,
            "setup_tag": None
        }
        trades_to_save.append(trade_data)
        
        # Also construct a raw deal record to store in database so incremental syncs work
        try:
            t_exit = datetime.fromisoformat(exit_time_str.replace("Z", ""))
            ts = int(t_exit.timestamp())
        except Exception:
            ts = int(datetime.now(timezone.utc).timestamp())
            
        raw_deal = {
            "deal_id": f"{account_id}_{deal_id}",
            "account_id": account_id,
            "symbol": symbol,
            "type": "SELL" if closing_dir == "SELL" else "BUY",
            "volume": volume,
            "price": exit_price,
            "commission": 0.0,
            "swap": 0.0,
            "profit": net_profit,
            "timestamp": ts,
            "position_id": f"{account_id}_{deal_id}"
        }
        raw_deals_list.append(raw_deal)

    if trades_to_save:
        database.save_raw_deals(raw_deals_list)
        database.save_closed_trades(trades_to_save)
        print(f"Reconstructed and saved {len(trades_to_save)} closed trades from Capital.com.")
        
    # Sync active open positions from Capital.com
    try:
        pos_resp = requests.get(f"{base_url}/positions", headers=headers)
        if pos_resp.status_code == 200:
            positions_data = pos_resp.json().get("positions", [])
            parsed_cap_open = []
            for p in positions_data:
                pos_info = p.get("position", {})
                market_info = p.get("market", {})
                dir_str = "BUY" if pos_info.get("direction") == "BUY" else "SELL"
                deal_id = str(pos_info.get("dealId", ""))
                parsed_cap_open.append({
                    "position_id": f"CAP_{deal_id}",
                    "account_id": account_id,
                    "symbol": clean_symbol(market_info.get("instrumentName", pos_info.get("epic", "UNKNOWN"))),
                    "direction": dir_str,
                    "volume": float(pos_info.get("size", 0.0)),
                    "entry_price": float(pos_info.get("level", 0.0)),
                    "current_price": float(market_info.get("bid", pos_info.get("level", 0.0))),
                    "sl": float(pos_info.get("stopLevel", 0.0)) if pos_info.get("stopLevel") else 0.0,
                    "tp": float(pos_info.get("profitLevel", 0.0)) if pos_info.get("profitLevel") else 0.0,
                    "floating_pnl": float(pos_info.get("upl", 0.0)),
                    "swap": 0.0,
                    "open_time": pos_info.get("createdDateUTC", datetime.now(timezone.utc).isoformat()),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                })
            database.save_open_positions(account_id, parsed_cap_open)
            print(f"Synced {len(parsed_cap_open)} active open positions for Capital.com.")
    except Exception as cap_pos_err:
        print(f"Error syncing Capital.com open positions: {cap_pos_err}")
        
    return True

if __name__ == "__main__":
    sync_capital()
