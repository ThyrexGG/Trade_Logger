"""Debug script - run this while MT5 is open to see what deals MT5 is returning."""
import MetaTrader5 as mt5
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

login = int(os.getenv("MT5_LOGIN"))
password = os.getenv("MT5_PASSWORD")
server = os.getenv("MT5_SERVER")

if not mt5.initialize(login=login, password=password, server=server):
    print(f"Failed to connect: {mt5.last_error()}")
    exit()

print(f"Connected: {mt5.account_info().login} @ {mt5.account_info().company}")

# Fetch ALL deals from the beginning of time
start = datetime(2020, 1, 1, tzinfo=timezone.utc)
end = datetime.now(timezone.utc)

deals = mt5.history_deals_get(start, end)

if deals is None:
    print(f"No deals returned. Error: {mt5.last_error()}")
else:
    print(f"\nTotal deals returned by MT5: {len(deals)}")
    print("-" * 80)
    for d in deals:
        type_map = {0: "BUY", 1: "SELL", 2: "BALANCE", 3: "CREDIT", 4: "CHARGE",
                    5: "CORRECTION", 6: "BONUS", 7: "COMMISSION", 8: "DIVIDEND"}
        entry_map = {0: "IN", 1: "OUT", 2: "INOUT", 3: "OUT_BY"}
        t = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  Deal#{d.ticket} | pos#{d.position_id} | {t} | "
              f"Type:{type_map.get(d.type, d.type)} | Entry:{entry_map.get(d.entry, d.entry)} | "
              f"Symbol:{d.symbol} | Vol:{d.volume} | Price:{d.price} | Profit:{d.profit}")

mt5.shutdown()
