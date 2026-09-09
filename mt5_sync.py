import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import database
from mt5_ingest import clean_symbol, ingest_mt5_payload, reconstruct_positions  # noqa: F401

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


def sync_mt5():
    # Reload .env freshly
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

    # Guard: MetaTrader5 is only available on Windows.
    if not MT5_AVAILABLE:
        print("MetaTrader5 is not available on this platform (Linux/Cloud). MT5 sync only works locally on Windows.")
        return False

    # Guard: the live-MT5 master switch. When off, do not touch the terminal
    # (mt5.initialize() would launch it). Capital.com sync is unaffected.
    try:
        import mt5_gate
        if not mt5_gate.is_mt5_enabled():
            print("Live MT5 data is switched off (app_settings) -- skipping MT5 sync.")
            return False
    except Exception:
        pass

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
    try:
        mt5.shutdown()
    except Exception:
        pass

    connected = False
    if login_str and password and server:
        try:
            login = int(login_str)
            # Try connecting with credentials
            if mt5.initialize(login=login, password=password, server=server, timeout=10000):
                connected = True
            else:
                # Fallback to default initialize
                if mt5.initialize(timeout=10000):
                    connected = True
                else:
                    print(f"MT5 initialize failed. Error code: {mt5.last_error()}")
        except Exception as e:
            print(f"MT5 initialization error: {e}")
            if mt5.initialize():
                connected = True
    else:
        # Connect to already open terminal on system
        if mt5.initialize():
            connected = True
        else:
            print("Could not connect to active MT5 terminal. Please make sure the MT5 terminal is open.")

    if not connected:
        return False

    # Get active account info to use as the unique account ID
    acc_info = mt5.account_info()
    if not acc_info:
        print("Failed to get account info from MT5.")
        try:
            mt5.shutdown()
        except Exception:
            pass
        return False

    account_id = f"MT5_{acc_info.login}"
    print(f"Successfully connected to MT5 Account: {acc_info.login} ({acc_info.company})")

    # --- Read the terminal (the Windows-only half) -------------------------
    balance_payload = {
        "balance": float(acc_info.balance),
        "equity": float(acc_info.equity),
        "currency": getattr(acc_info, "currency", "USD") or "USD",
    }

    positions_payload = []
    try:
        for pos in (mt5.positions_get() or []):
            positions_payload.append({
                "position_id": f"MT5_{pos.ticket}",
                "symbol": pos.symbol,
                "direction": "BUY" if pos.type == 0 else "SELL",
                "volume": float(pos.volume),
                "entry_price": float(pos.price_open),
                "current_price": float(pos.price_current),
                "sl": float(pos.sl) if pos.sl else 0.0,
                "tp": float(pos.tp) if pos.tp else 0.0,
                "floating_pnl": float(pos.profit),
                "swap": float(pos.swap) if pos.swap else 0.0,
                "open_time": datetime.fromtimestamp(pos.time, tz=timezone.utc).isoformat(),
            })
    except Exception as pos_err:
        print(f"Error reading open positions: {pos_err}")

    # Determine start timestamp for incremental sync
    last_ts = database.get_last_deal_timestamp(account_id)
    if last_ts > 0:
        start_date = datetime.fromtimestamp(last_ts - 10, tz=timezone.utc)
    else:
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end_date = datetime.now(timezone.utc) + timedelta(days=2)

    print(f"Fetching deals from {start_date} to {end_date}...")
    deals = mt5.history_deals_get(start_date, end_date)
    if deals is None:
        print(f"No deals found or failed to fetch. Error: {mt5.last_error()}")
        mt5.shutdown()
        return False

    deals_payload = []
    for deal in deals:
        # MT5 deal types: 0 = Buy, 1 = Sell; skip balance/deposit transactions.
        if deal.type not in (0, 1):
            continue
        deals_payload.append({
            "deal_id": str(deal.ticket),
            "symbol": deal.symbol,
            "type": "BUY" if deal.type == 0 else "SELL",
            "volume": float(deal.volume),
            "price": float(deal.price),
            "commission": float(deal.commission),
            "swap": float(deal.swap),
            "profit": float(deal.profit),
            "timestamp": int(deal.time),
            "position_id": str(deal.position_id),
        })

    mt5.shutdown()

    # --- Transform + write (shared with the push-agent ingest path) -------
    summary = ingest_mt5_payload(
        account_id,
        balance=balance_payload,
        positions=positions_payload,
        deals=deals_payload,
        logfn=print,
    )
    print(
        f"MT5 sync done: {summary['raw_deals']} raw deals, "
        f"{summary['closed_trades']} closed trades, "
        f"{summary['open_positions']} open positions."
    )
    return True


if __name__ == "__main__":
    sync_mt5()
