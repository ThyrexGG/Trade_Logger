import sys
sys.path.insert(0, ".")
import backtester
import strategies

strat = strategies.get_strategy("USDJPY SMC Continuation")
print("Strategy object:", strat)

# Fetch data using backtester logic
res = backtester.run_backtest(
    symbol="USDJPY",
    timeframe="15m",
    strategy="USDJPY SMC Continuation",
    risk_pct=1.0,
    capital=10000.0
)

print("Result keys:", res.keys())
if "error" in res:
    print("Error:", res["error"])
else:
    print("Trades count:", len(res.get("trades", [])))
