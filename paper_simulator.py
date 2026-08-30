import time
import uuid
import database
import account_state
from datetime import datetime, timezone
import order_execution
import market_data

PAPER_SPREAD_ESTIMATE = 0.00015 # 1.5 pips default spread for EURUSD type
PAPER_SLIPPAGE_ESTIMATE = 0.00005 # 0.5 pips slippage
PAPER_COMMISSION = 0.0 # Standard

def run_paper_evaluation_cycle():
    """
    Evaluates all currently open PAPER positions to see if their SL/TP was hit.
    This should be run on a loop or background task.
    """
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        
        # Get all open PAPER positions
        if database.is_postgres():
            cursor.execute("SELECT position_id, symbol, direction, volume, entry_price, sl, tp FROM open_positions WHERE account_id = 'PAPER'")
        else:
            cursor.execute("SELECT position_id, symbol, direction, volume, entry_price, sl, tp FROM open_positions WHERE account_id = 'PAPER'")
            
        open_positions = cursor.fetchall()
        
        for pos in open_positions:
            pos_id, sym, direction, vol, entry, sl, tp = pos
            
            # Fetch latest price
            current_price = market_data.get_latest_price(sym)
            if not current_price:
                continue
                
            is_buy = str(direction).upper() == "BUY"
            
            # Check Stop Loss
            if sl is not None and sl > 0:
                if (is_buy and current_price <= sl) or (not is_buy and current_price >= sl):
                    close_paper_position(pos_id, sym, direction, vol, entry, sl, "SL_HIT", conn)
                    continue
                    
            # Check Take Profit
            if tp is not None and tp > 0:
                if (is_buy and current_price >= tp) or (not is_buy and current_price <= tp):
                    close_paper_position(pos_id, sym, direction, vol, entry, tp, "TP_HIT", conn)
                    continue
                    
        conn.close()
    except Exception as e:
        print(f"Error in paper evaluation cycle: {e}")

def close_paper_position(pos_id, sym, direction, vol, entry, exit_price, exit_reason, conn):
    """Closes a paper position and logs it to closed_trades."""
    now_str = datetime.now(timezone.utc).isoformat()
    cursor = conn.cursor()
    
    is_buy = str(direction).upper() == "BUY"
    
    # Calculate PnL
    multiplier = 100000.0 if ("USD" in sym or "EUR" in sym or "GBP" in sym) else 100.0
    if is_buy:
        gross_profit = (exit_price - entry) * vol * multiplier
    else:
        gross_profit = (entry - exit_price) * vol * multiplier
        
    net_profit = gross_profit - PAPER_COMMISSION
    
    trade_id = f"TRADE_{pos_id}"
    
    try:
        # Insert to closed_trades
        if database.is_postgres():
            cursor.execute("""
                INSERT INTO closed_trades (trade_id, account_id, symbol, direction, volume, entry_price, exit_price, commission, swap, gross_profit, net_profit, entry_time, exit_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (trade_id, "PAPER", sym, direction, vol, entry, exit_price, PAPER_COMMISSION, 0.0, gross_profit, net_profit, now_str, now_str))
            
            # Delete from open_positions
            cursor.execute("DELETE FROM open_positions WHERE position_id = %s", (pos_id,))
        else:
            cursor.execute("""
                INSERT INTO closed_trades (trade_id, account_id, symbol, direction, volume, entry_price, exit_price, commission, swap, gross_profit, net_profit, entry_time, exit_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (trade_id, "PAPER", sym, direction, vol, entry, exit_price, PAPER_COMMISSION, 0.0, gross_profit, net_profit, now_str, now_str))
            
            cursor.execute("DELETE FROM open_positions WHERE position_id = ?", (pos_id,))
            
        conn.commit()
        print(f"Closed PAPER position {pos_id} at {exit_price} ({exit_reason}). PnL: {net_profit:.2f}")
    except Exception as e:
        print(f"Failed to close paper position {pos_id}: {e}")

def execute_paper_order(symbol, direction, volume, entry_price, sl=None, tp=None):
    """
    Simulates a highly realistic paper execution.
    Takes the SIGNAL PRICE (entry_price) and applies spread and slippage to determine the PAPER FILL PRICE.
    """
    # Simulate spread and slippage
    is_buy = str(direction).upper() == "BUY"
    
    # Fetch live price to ensure we execute at current market context
    live_price = market_data.get_latest_price(symbol)
    reference_price = live_price if live_price and live_price > 0 else entry_price
    
    if not reference_price:
        return {"status": "error", "message": "Cannot determine live market price for paper execution."}
        
    fill_price = reference_price
    
    # Apply spread
    if is_buy:
        fill_price += PAPER_SPREAD_ESTIMATE
    else:
        fill_price -= PAPER_SPREAD_ESTIMATE
        
    # Apply slippage (always penalizes the trader)
    if is_buy:
        fill_price += PAPER_SLIPPAGE_ESTIMATE
    else:
        fill_price -= PAPER_SLIPPAGE_ESTIMATE
        
    order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
    
    # Log the simulated paper position in our local database's open_positions table
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        
        pos_id = f"POS_{order_id}"
        if database.is_postgres():
            cursor.execute("""
                INSERT INTO open_positions (position_id, account_id, symbol, direction, volume, entry_price, current_price, sl, tp, floating_pnl, swap, open_time, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (pos_id, "PAPER", symbol, direction, float(volume), fill_price, fill_price, sl, tp, 0.0, 0.0, now_str, now_str))
        else:
            cursor.execute("""
                INSERT INTO open_positions (position_id, account_id, symbol, direction, volume, entry_price, current_price, sl, tp, floating_pnl, swap, open_time, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (pos_id, "PAPER", symbol, direction, float(volume), fill_price, fill_price, sl, tp, 0.0, 0.0, now_str, now_str))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to record paper position: {e}")
        return {"status": "error", "message": f"Failed to record paper position: {e}"}

    return {
        "status": "success", 
        "message": "Paper order executed successfully", 
        "order_id": order_id,
        "execution_price": fill_price,
        "slippage": PAPER_SLIPPAGE_ESTIMATE,
        "spread": PAPER_SPREAD_ESTIMATE
    }
