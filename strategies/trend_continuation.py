from .base import BaseStrategy
import pandas as pd

class TrendContinuationStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "Trend Continuation"
        
    @property
    def description(self) -> str:
        return "Buys pullbacks in an uptrend, sells pullbacks in a downtrend based on EMA20/50 and RSI."
        
    def analyze(self, df: pd.DataFrame, current_index: int, context: dict = None) -> dict:
        if current_index < 50:
            return self.build_no_trade("Not enough data to calculate EMA50.")
            
        row = df.iloc[current_index]
        ema20 = float(row.get('EMA_20', 0))
        ema50 = float(row.get('EMA_50', 0))
        rsi = float(row.get('RSI', 50))
        close = float(row['Close'])
        atr = float(row.get('ATR', 0))
        
        sl_atr = context.get('sl_atr', 1.5) if context else 1.5
        tp_atr = context.get('tp_atr', 2.0) if context else 2.0
        
        signal = None
        if ema20 > ema50 and close <= ema20 and rsi > 50:
            signal = "LONG"
        elif ema20 < ema50 and close >= ema20 and rsi < 50:
            signal = "SHORT"
            
        if signal:
            entry = close
            if signal == "LONG":
                sl = entry - (atr * sl_atr)
                tp1 = entry + (atr * tp_atr)
            else:
                sl = entry + (atr * sl_atr)
                tp1 = entry - (atr * tp_atr)
                
            return {
                "status": "READY",
                "setup": signal,
                "execution_model": "MARKET",
                "expiration_bars": 1,
                "entry_zone": f"~{entry:.4f}",
                "ideal_entry": entry,
                "stop_loss": sl,
                "tp1": tp1,
                "tp2": "N/A",
                "risk_reward": f"1:{tp_atr/sl_atr:.1f}",
                "trigger": "Fast EMA cross & Pullback",
                "invalidation": "Opposite EMA crossover.",
                "confidence": "Medium",
                "setup_quality": "B",
                "liquidity_type": "N/A",
                "session": "N/A",
                "reason": "N/A"
            }
            
        return self.build_no_trade("No trend continuation signal.")
