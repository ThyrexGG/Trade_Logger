from .base import BaseStrategy
import pandas as pd

class MeanReversionStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "Mean Reversion"
        
    @property
    def description(self) -> str:
        return "Buys when RSI is oversold (<30) and sells when RSI is overbought (>70)."
        
    def analyze(self, df: pd.DataFrame, current_index: int, context: dict = None) -> dict:
        row = df.iloc[current_index]
        rsi = float(row.get('RSI', 50))
        close = float(row['Close'])
        atr = float(row.get('ATR', 0))
        
        sl_atr = context.get('sl_atr', 1.5) if context else 1.5
        tp_atr = context.get('tp_atr', 2.0) if context else 2.0
        
        signal = None
        if rsi < 30:
            signal = "LONG"
        elif rsi > 70:
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
                "trigger": "RSI Extreme Reversal",
                "invalidation": "RSI crosses 50.",
                "confidence": "Medium",
                "setup_quality": "C",
                "liquidity_type": "N/A",
                "session": "N/A",
                "reason": "N/A"
            }
            
        return self.build_no_trade("No mean reversion signal.")
