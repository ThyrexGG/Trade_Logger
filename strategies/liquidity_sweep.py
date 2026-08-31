from .base import BaseStrategy
from .smc_utils import add_smc_features, detect_liquidity_sweep
import pandas as pd

class LiquiditySweepStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "Liquidity Sweep Reversal"
        
    @property
    def version(self) -> str:
        return "1.1.0"

    @property
    def description(self) -> str:
        return "Detects a sweep of a major swing high (BSL) or low (SSL) that rejects and closes back inside the range, entering a reversal trade immediately."
        
    def analyze(self, df: pd.DataFrame, current_index: int, context: dict = None) -> dict:
        if current_index < 20:
            return self.build_no_trade("Insufficient data.")
            
        if 'last_swing_high' not in df.columns:
            df = add_smc_features(df)
            
        row = df.iloc[current_index]
        close = float(row['Close'])
        atr = float(row.get('ATR', 0))
        
        sl_atr = context.get('sl_atr', 1.0) if context else 1.0
        tp_atr = context.get('tp_atr', 2.0) if context else 2.0
        
        sweep_data = detect_liquidity_sweep(df, current_index)
        
        if sweep_data["sweep"] == "SSL":
            # Valid Long
            entry = close
            sl = row['Low'] - (atr * 0.5) # Stop just below the sweep wick
            tp1 = entry + (atr * tp_atr)
            
            session_name = "N/A"
            if hasattr(row, 'is_asia') and getattr(row, 'is_asia'): session_name = "ASIA"
            elif hasattr(row, 'is_london') and getattr(row, 'is_london'): session_name = "LONDON"
            elif hasattr(row, 'is_ny') and getattr(row, 'is_ny'): session_name = "NEW_YORK"
            
            sweep_type = sweep_data.get("type", "SWING_LOW")
            
            return {
                "status": "READY",
                "setup": "LONG",
                "execution_model": "MARKET",
                "expiration_bars": 1,
                "entry_zone": f"~{entry:.4f}",
                "ideal_entry": entry,
                "stop_loss": sl,
                "tp1": tp1,
                "tp2": "N/A",
                "risk_reward": f"1:{tp_atr/sl_atr:.1f}",
                "trigger": f"SSL Sweep detected at {sweep_data['level']:.4f}",
                "invalidation": "Close below the sweep low.",
                "confidence": "High",
                "setup_quality": "A",
                "liquidity_type": sweep_type,
                "session": session_name,
                "reason": "N/A"
            }
            
        elif sweep_data["sweep"] == "BSL":
            # Valid Short
            entry = close
            sl = row['High'] + (atr * 0.5)
            tp1 = entry - (atr * tp_atr)
            
            session_name = "N/A"
            if hasattr(row, 'is_asia') and getattr(row, 'is_asia'): session_name = "ASIA"
            elif hasattr(row, 'is_london') and getattr(row, 'is_london'): session_name = "LONDON"
            elif hasattr(row, 'is_ny') and getattr(row, 'is_ny'): session_name = "NEW_YORK"
            
            sweep_type = sweep_data.get("type", "SWING_HIGH")
            
            return {
                "status": "READY",
                "setup": "SHORT",
                "execution_model": "MARKET",
                "expiration_bars": 1,
                "entry_zone": f"~{entry:.4f}",
                "ideal_entry": entry,
                "stop_loss": sl,
                "tp1": tp1,
                "tp2": "N/A",
                "risk_reward": f"1:{tp_atr/sl_atr:.1f}",
                "trigger": f"BSL Sweep detected at {sweep_data['level']:.4f}",
                "invalidation": "Close above the sweep high.",
                "confidence": "High",
                "setup_quality": "A",
                "liquidity_type": sweep_type,
                "session": session_name,
                "reason": "N/A"
            }
            
        return self.build_no_trade("No liquidity sweep detected on the current bar.")
