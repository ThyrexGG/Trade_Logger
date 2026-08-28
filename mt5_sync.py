import os
from datetime import datetime, timezone
from dotenv import load_dotenv
import database

# MetaTrader5 is a Windows-only package. On Linux/cloud it will not be available.
# The sync button in the UI will show an error message instead of crashing the app.
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

def clean_symbol(symbol):
    """Normalizes symbol names by removing suffixes like .fs, .pro, .m, etc."""
    # Common suffixes for prop firms and retail brokers
    for suffix in [".fs", ".pro", ".m", ".raw", ".std", ".ecn"]:
        if symbol.endswith(suffix):
            symbol = symbol[:-len(suffix)]
    return symbol.upper()

def sync_mt5():
    # Reload .env freshly
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

    # Guard: MetaTrader5 is only available on Windows.
    if not MT5_AVAILABLE:
        print("MetaTrader5 is not available on this platform (Linux/Cloud). MT5 sync only works locally on Windows.")
        return False

    # Initialize MT5 connection
    login_str = os.getenv("MT5_LOGIN", "")
    password = os.getenv("MT5_PASSWORD", "")
    server = os.getenv("MT5_SERVER", "")

    if login_str: login_str = login_str.strip('"\'')
    if password: password = password.strip('"\'')
    if server: server = server.strip('"\'')
    
    # Initialize the database just in case
    database.init_db()

    print("Connecting to MetaTrader 5 terminal...")
    if login_str and password and server:
        # Connect using specified credentials
        login = int(login_str)
        if not mt5.initialize(login=login, password=password, server=server):
            print(f"MT5 initialize failed. Error code: {mt5.last_error()}")
            return False
    else:
        # Connect to already open terminal on system
        if not mt5.initialize():
            print("Could not connect to active MT5 terminal. Please make sure the MT5 terminal is open.")
            return False
            
    # Get active account info to use as the unique account ID
    acc_info = mt5.account_info()
    if not acc_info:
        print("Failed to get account info from MT5.")
        mt5.shutdown()
        return False
        
    account_id = f"MT5_{acc_info.login}"
    print(f"Successfully connected to MT5 Account: {acc_info.login} ({acc_info.company})")

    # Determine start timestamp for incremental sync
    last_ts = database.get_last_deal_timestamp(account_id)
    if last_ts > 0:
        # Start 10 seconds before the last known deal to catch any overlaps/updates
        start_date = datetime.fromtimestamp(last_ts - 10, tz=timezone.utc)
    else:
        # Default start date (e.g. 5 years ago)
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        
    end_date = datetime.now(timezone.utc)
    
    print(f"Fetching deals from {start_date} to {end_date}...")
    deals = mt5.history_deals_get(start_date, end_date)
    
    if deals is None:
        print(f"No deals found or failed to fetch. Error: {mt5.last_error()}")
        mt5.shutdown()
        return False
        
    if len(deals) == 0:
        print("No new deals to import.")
        mt5.shutdown()
        return True
        
    print(f"Found {len(deals)} raw deals. Processing...")
    
    raw_deals_list = []
    position_ids_to_reprocess = set()
    
    for deal in deals:
        # MT5 deal types: 0 = Buy, 1 = Sell
        # Skip balance/deposit transactions (deal type 2, 3, etc.)
        if deal.type not in [0, 1]:
            continue
            
        deal_type_str = "BUY" if deal.type == 0 else "SELL"
        
        deal_data = {
            "deal_id": f"{account_id}_{deal.ticket}",
            "account_id": account_id,
            "symbol": deal.symbol,
            "type": deal_type_str,
            "volume": float(deal.volume),
            "price": float(deal.price),
            "commission": float(deal.commission),
            "swap": float(deal.swap),
            "profit": float(deal.profit),
            "timestamp": int(deal.time),
            "position_id": f"{account_id}_{deal.position_id}"
        }
        
        raw_deals_list.append(deal_data)
        position_ids_to_reprocess.add(deal_data["position_id"])
        
    # Save raw deals to database
    database.save_raw_deals(raw_deals_list)
    print(f"Saved {len(raw_deals_list)} raw deals to database.")
    
    # Reprocess affected positions to build/update closed_trades
    reconstruct_positions(position_ids_to_reprocess, account_id)
    
    mt5.shutdown()
    return True

def reconstruct_positions(position_ids, account_id):
    """
    Groups raw deals by Position ID and rebuilds closed trades.
    Uses FIFO logic based on Position ID to track entries and exits.
    """
    if not position_ids:
        return
        
    conn = database.get_connection()
    cursor = conn.cursor()
    
    trades_to_save = []
    
    for pos_id in position_ids:
        # Fetch all deals related to this position, sorted by time
        ph = "%s" if database.is_postgres() else "?"
        cursor.execute(f"""
            SELECT type, volume, price, commission, swap, profit, timestamp, symbol 
            FROM raw_deals 
            WHERE position_id = {ph} 
            ORDER BY timestamp ASC
        """, (pos_id,))
        
        deals = cursor.fetchall()
        if not deals:
            continue
            
        # Parse deals
        entries = []
        exits = []
        total_commission = 0.0
        total_swap = 0.0
        total_profit = 0.0
        symbol = clean_symbol(deals[0][7])
        
        # Sort deals into entries vs exits
        # The first deal in the position establishes the direction (Long/Short)
        first_deal_type = deals[0][0] # "BUY" or "SELL"
        trade_direction = "LONG" if first_deal_type == "BUY" else "SHORT"
        
        for deal_type, volume, price, commission, swap, profit, timestamp, _ in deals:
            total_commission += commission
            total_swap += swap
            total_profit += profit
            
            # If the deal type matches the opening deal type, it's an entry (scale-in)
            # If it's the opposite type, it's an exit (scale-out / close)
            if deal_type == first_deal_type:
                entries.append((volume, price, timestamp))
            else:
                exits.append((volume, price, timestamp))
                
        # If there are no exits yet, the position is still open (active)
        # In this dashboard, we only record fully closed trades
        # Check if total entry volume matches total exit volume
        total_entry_vol = sum(e[0] for e in entries)
        total_exit_vol = sum(ex[0] for ex in exits)
        
        if total_exit_vol < total_entry_vol * 0.999: # Allowing a tiny floating point margin
            # Position is still open, do not write to closed_trades yet
            continue
            
        # Calculate weighted average entry price
        weighted_entry_sum = sum(vol * price for vol, price, _ in entries)
        avg_entry_price = weighted_entry_sum / total_entry_vol if total_entry_vol > 0 else 0
        
        # Calculate weighted average exit price
        weighted_exit_sum = sum(vol * price for vol, price, _ in exits)
        avg_exit_price = weighted_exit_sum / total_exit_vol if total_exit_vol > 0 else 0
        
        # Time calculations
        entry_time_epoch = entries[0][2]
        exit_time_epoch = exits[-1][2]
        
        entry_time_str = datetime.fromtimestamp(entry_time_epoch, tz=timezone.utc).isoformat()
        exit_time_str = datetime.fromtimestamp(exit_time_epoch, tz=timezone.utc).isoformat()
        
        duration_minutes = (exit_time_epoch - entry_time_epoch) / 60.0
        
        net_profit = total_profit + total_commission + total_swap
        
        trade_data = {
            "trade_id": pos_id,
            "account_id": account_id,
            "symbol": symbol,
            "direction": trade_direction,
            "volume": total_entry_vol,
            "entry_price": avg_entry_price,
            "exit_price": avg_exit_price,
            "commission": total_commission,
            "swap": total_swap,
            "gross_profit": total_profit,
            "net_profit": net_profit,
            "entry_time": entry_time_str,
            "exit_time": exit_time_str,
            "duration_minutes": duration_minutes,
            "setup_tag": None # To be labeled by the user
        }
        
        trades_to_save.append(trade_data)
        
    conn.close()
    
    if trades_to_save:
        database.save_closed_trades(trades_to_save)
        print(f"Reconstructed and saved {len(trades_to_save)} closed trades.")

if __name__ == "__main__":
    sync_mt5()
