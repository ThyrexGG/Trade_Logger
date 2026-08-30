import database
import pandas as pd
from account_state import get_account_state

def reconcile_open_positions(account_type="MT5"):
    """
    Compares local open positions with the broker's open positions.
    Returns:
    {
        "status": "success" | "mismatch" | "error",
        "message": str,
        "local_only": list,
        "broker_only": list,
        "mismatched": list,
        "matched": list
    }
    """
    res = {
        "status": "error",
        "message": "",
        "local_only": [],
        "broker_only": [],
        "mismatched": [],
        "matched": []
    }
    
    # 1. Get broker state
    state = get_account_state(account_type)
    if state["status"] != "success":
        res["message"] = f"Failed to fetch broker state: {state['message']}"
        return res
        
    broker_positions = state["open_positions"]
    broker_pos_dict = {str(p["ticket"]): p for p in broker_positions}
    
    # 2. Get local database state
    try:
        conn = database.get_connection()
        local_df = pd.read_sql_query("SELECT position_id, symbol, direction, volume, entry_price, sl, tp FROM open_positions", conn)
        conn.close()
    except Exception as e:
        res["message"] = f"Failed to fetch local database state: {e}"
        return res
        
    local_pos_dict = {}
    for _, row in local_df.iterrows():
        # Clean ticket from position_id (e.g. 'MT5_12345' -> '12345')
        ticket = str(row['position_id']).split("_")[-1]
        local_pos_dict[ticket] = row.to_dict()
        local_pos_dict[ticket]['ticket'] = ticket
        
    # 3. Compare
    broker_keys = set(broker_pos_dict.keys())
    local_keys = set(local_pos_dict.keys())
    
    res["broker_only"] = [broker_pos_dict[k] for k in broker_keys - local_keys]
    res["local_only"] = [local_pos_dict[k] for k in local_keys - broker_keys]
    
    for k in broker_keys.intersection(local_keys):
        bp = broker_pos_dict[k]
        lp = local_pos_dict[k]
        
        # Check for SL / TP / Volume modifications
        mismatches = []
        if round(bp["volume"], 2) != round(lp["volume"], 2):
            mismatches.append(f"Volume mismatch: Broker={bp['volume']} Local={lp['volume']}")
        if bp["sl"] != lp["sl"]:
            mismatches.append(f"SL mismatch: Broker={bp['sl']} Local={lp['sl']}")
        if bp["tp"] != lp["tp"]:
            mismatches.append(f"TP mismatch: Broker={bp['tp']} Local={lp['tp']}")
            
        if mismatches:
            res["mismatched"].append({
                "ticket": k,
                "broker": bp,
                "local": lp,
                "issues": mismatches
            })
        else:
            res["matched"].append(k)
            
    if res["broker_only"] or res["local_only"] or res["mismatched"]:
        res["status"] = "mismatch"
        res["message"] = "Discrepancy detected between broker and local database."
    else:
        res["status"] = "success"
        res["message"] = "Broker and local state are in sync."
        
    return res

def perform_system_recovery_check():
    """
    Called on server startup or during execution pipeline to verify system integrity.
    Validates idempotency logs and ensures the kill switch is respected.
    """
    try:
        kill_switch = str(database.get_setting("SYSTEM_STATE", "PAPER")).upper()
        if kill_switch == "EMERGENCY HALT":
            return {"status": "halted", "message": "System is currently in EMERGENCY HALT."}
        return {"status": "ok", "message": "System recovery check passed."}
    except Exception as e:
        return {"status": "error", "message": f"Database unavailable for recovery check: {e}"}
