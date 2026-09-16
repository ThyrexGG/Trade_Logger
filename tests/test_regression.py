import legacy.ai_analysis as ai_analysis
import market_data
import json

def test_regression():
    assets = ["XAUUSD", "EURUSD", "BTCUSD", "SPX500"]
    timeframes = ["15m", "1h"]

    print("--- TRADELOGGER ENGINE REGRESSION TEST ---")
    
    passed = 0
    failed = 0
    
    for asset in assets:
        for tf in timeframes:
            try:
                print(f"\nTesting {asset} on {tf} timeframe...")
                data = ai_analysis.analyze_market_context(asset, tf)
                
                # Check required top-level keys
                required_keys = ["symbol", "timeframe", "timestamp", "market_structure", "fvg_data", "ob_data", "liquidity_zones", "deterministic_scenario", "confluence_bias", "validation"]
                missing = [k for k in required_keys if k not in data]
                if missing:
                    print(f"[FAIL] Missing keys: {missing}")
                    failed += 1
                    continue
                    
                # Check Liquidity
                liq = data.get("liquidity_zones", {})
                if not isinstance(liq, dict):
                    print(f"[FAIL] Liquidity zones is not a dictionary. Type: {type(liq)}")
                    failed += 1
                    continue
                
                # Check FVG
                fvgs = data.get("fvg_data", [])
                if fvgs and not isinstance(fvgs[0], dict):
                    print(f"[FAIL] FVG data is not a list of dictionaries.")
                    failed += 1
                    continue
                    
                # Check Scenario validation
                scenario = data.get("deterministic_scenario", {})
                if "status" not in scenario or "geometry" not in scenario:
                    print(f"[FAIL] Scenario missing strict geometry enforcement.")
                    failed += 1
                    continue
                    
                # Check Confluence normalization
                ml_buy = data.get("ml_prob_buy", 0)
                ml_sell = data.get("ml_prob_sell", 0)
                ml_neutral = data.get("ml_prob_neutral", 0)
                total_ml = round(ml_buy + ml_sell + ml_neutral, 1)
                
                if total_ml != 100.0:
                    print(f"[FAIL] ML Probabilities do not normalize to 100%. Sum: {total_ml}")
                    failed += 1
                    continue
                
                print(f"[PASS] {asset} {tf} | Target: {scenario.get('target', 'N/A')} | ML: Buy {ml_buy}% Sell {ml_sell}% | Validation: {data.get('validation', {}).get('status', 'N/A')}")
                passed += 1
                
            except Exception as e:
                import traceback
                print(f"[ERROR] Exception on {asset} {tf}: {e}")
                traceback.print_exc()
                failed += 1
                
    print(f"\n--- TEST COMPLETE ---")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
if __name__ == "__main__":
    test_regression()
