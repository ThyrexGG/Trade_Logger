from .base import BaseStrategy
from .smc_utils import add_smc_features, detect_liquidity_sweep, detect_mss
import pandas as pd
import numpy as np

class ICT2022Model(BaseStrategy):
    @property
    def name(self) -> str:
        return "ICT 2022 Model"
        
    @property
    def description(self) -> str:
        return "Waits for a Liquidity Sweep, followed by a Market Structure Shift (MSS) with displacement (FVG), then enters on retracement into the FVG."
        
    def analyze(self, df: pd.DataFrame, current_index: int, context: dict = None) -> dict:
        # Require at least 20 bars to look back
        if current_index < 20:
            return self.build_no_trade("Insufficient data for ICT 2022 Model.", context)
            
        # Ensure SMC features are calculated. In a live system this is done once, but we check here just in case.
        if 'last_swing_high' not in df.columns:
            df = add_smc_features(df)
            
        row = df.iloc[current_index]
        close = float(row['Close'])
        atr = float(row.get('ATR', 0))
        
        sl_atr = context.get('sl_atr', 1.0) if context else 1.0
        tp_atr = context.get('tp_atr', 2.5) if context else 2.5
        
        bias_tf = context.get('bias_tf', '1D') if context else '1D'
        struct_tf = context.get('struct_tf', '4H') if context else '4H'
        
        # MTF Context
        htf_bias = row.get('HTF_Bias_BIAS', 'NEUTRAL')
        
        # Look back window for the setup sequence (e.g., 20 bars)
        lookback = 20
        start_idx = max(0, current_index - lookback)
        window = df.iloc[start_idx:current_index+1]
        
        # Check for Bullish Setup (SSL Sweep -> Bullish MSS -> Bullish FVG)
        # 1. Are we currently in a Bullish FVG that was formed recently?
        # A valid FVG must not have been fully mitigated (closed below). For simplicity, we check if current price is inside a recent FVG.
        
        recent_fvg = window[pd.notna(window['bullish_fvg_bottom'])]
        if not recent_fvg.empty:
            last_fvg_idx = recent_fvg.index[-1]
            fvg_top = recent_fvg.loc[last_fvg_idx, 'bullish_fvg_top']
            fvg_bot = recent_fvg.loc[last_fvg_idx, 'bullish_fvg_bottom']
            
            # If price retraced into this FVG
            if fvg_bot <= row['Low'] <= fvg_top or fvg_bot <= row['Close'] <= fvg_top:
                # 2. Was there a Bullish MSS before this FVG?
                fvg_pos = df.index.get_loc(last_fvg_idx)
                pre_fvg_window = df.iloc[max(0, fvg_pos - 10) : fvg_pos]
                mss_detected = False
                for i in range(len(pre_fvg_window)):
                    if detect_mss(df, fvg_pos - 10 + i) == "BULLISH":
                        mss_detected = True
                        break
                        
                if mss_detected:
                    # 3. Was there an SSL Sweep before the MSS?
                    sweep_detected = False
                    # Check window from start up to MSS
                    for i in range(start_idx, fvg_pos):
                        sweep = detect_liquidity_sweep(df, i)
                        if sweep["sweep"] == "SSL":
                            sweep_detected = True
                            break
                            
                    if sweep_detected:
                        # Enforce HTF Alignment for MTF Phase 7
                        if htf_bias == "BEARISH":
                            return self.build_no_trade("Setup is BULLISH but HTF Bias is BEARISH (Counter-trend).", context)
                            
                        # VALID BULLISH SETUP
                        entry = close
                        # Proper ICT Stop Loss is beyond the sweep low
                        sl = sweep["level"] - (atr * 0.2) if sweep["level"] else entry - (atr * sl_atr)
                        tp1 = entry + (atr * tp_atr)
                        
                        session_name = "N/A"
                        if hasattr(row, 'is_asia') and getattr(row, 'is_asia'): session_name = "ASIA"
                        elif hasattr(row, 'is_london') and getattr(row, 'is_london'): session_name = "LONDON"
                        elif hasattr(row, 'is_ny') and getattr(row, 'is_ny'): session_name = "NEW_YORK"
                        
                        # Confluence Scoring
                        c_score = 0
                        c_reasons = []
                        if htf_bias == "BULLISH": c_score += 1; c_reasons.append("HTF Bias Aligned")
                        if session_name in ["LONDON", "NEW_YORK"]: c_score += 1; c_reasons.append("Active Killzone")
                        if sweep.get("type") in ["PDL", "PWL"]: c_score += 1; c_reasons.append("HTF Liquidity Swept")
                        
                        return {
                            "status": "READY",
                            "setup": "LONG",
                            "execution_model": "MARKET",
                            "expiration_bars": 1,
                            "entry_zone": f"{fvg_bot:.4f} - {fvg_top:.4f}",
                            "ideal_entry": entry,
                            "stop_loss": sl,
                            "tp1": tp1,
                            "tp2": "N/A",
                            "risk_reward": f"1:{abs(tp1-entry)/abs(entry-sl):.1f}" if abs(entry-sl) > 0 else "N/A",
                            "trigger": "SSL Sweep -> Bullish MSS -> Price entered Bullish FVG",
                            "invalidation": "Close below FVG bottom.",
                            "confidence": "High",
                            "setup_quality": "A",
                            "liquidity_type": sweep.get("type", "SWING_LOW"),
                            "liquidity_timeframe": "EXECUTION" if sweep.get("type") not in ["PDH", "PDL", "PWH", "PWL"] else bias_tf,
                            "session": session_name,
                            "reason": "N/A",
                            "bias_timeframe": bias_tf,
                            "structure_timeframe": struct_tf,
                            "htf_bias": htf_bias,
                            "confluence_score": f"{c_score}/3",
                            "confluence_reasons": c_reasons
                        }

        # Check for Bearish Setup (BSL Sweep -> Bearish MSS -> Bearish FVG)
        recent_bear_fvg = window[pd.notna(window['bearish_fvg_top'])]
        if not recent_bear_fvg.empty:
            last_fvg_idx = recent_bear_fvg.index[-1]
            fvg_top = recent_bear_fvg.loc[last_fvg_idx, 'bearish_fvg_top']
            fvg_bot = recent_bear_fvg.loc[last_fvg_idx, 'bearish_fvg_bottom']
            
            # If price retraced into this FVG
            if fvg_bot <= row['High'] <= fvg_top or fvg_bot <= row['Close'] <= fvg_top:
                # 2. Was there a Bearish MSS before this FVG?
                fvg_pos = df.index.get_loc(last_fvg_idx)
                pre_fvg_window = df.iloc[max(0, fvg_pos - 10) : fvg_pos]
                mss_detected = False
                for i in range(len(pre_fvg_window)):
                    if detect_mss(df, fvg_pos - 10 + i) == "BEARISH":
                        mss_detected = True
                        break
                        
                if mss_detected:
                    # 3. Was there a BSL Sweep before the MSS?
                    sweep_detected = False
                    for i in range(start_idx, fvg_pos):
                        sweep = detect_liquidity_sweep(df, i)
                        if sweep["sweep"] == "BSL":
                            sweep_detected = True
                            break
                            
                    if sweep_detected:
                        # Enforce HTF Alignment for MTF Phase 7
                        if htf_bias == "BULLISH":
                            return self.build_no_trade("Setup is BEARISH but HTF Bias is BULLISH (Counter-trend).", context)

                        # VALID BEARISH SETUP
                        entry = close
                        sl = sweep["level"] + (atr * 0.2) if sweep["level"] else entry + (atr * sl_atr)
                        tp1 = entry - (atr * tp_atr)
                        
                        session_name = "N/A"
                        if hasattr(row, 'is_asia') and getattr(row, 'is_asia'): session_name = "ASIA"
                        elif hasattr(row, 'is_london') and getattr(row, 'is_london'): session_name = "LONDON"
                        elif hasattr(row, 'is_ny') and getattr(row, 'is_ny'): session_name = "NEW_YORK"
                        
                        # Confluence Scoring
                        c_score = 0
                        c_reasons = []
                        if htf_bias == "BEARISH": c_score += 1; c_reasons.append("HTF Bias Aligned")
                        if session_name in ["LONDON", "NEW_YORK"]: c_score += 1; c_reasons.append("Active Killzone")
                        if sweep.get("type") in ["PDH", "PWH"]: c_score += 1; c_reasons.append("HTF Liquidity Swept")
                        
                        return {
                            "status": "READY",
                            "setup": "SHORT",
                            "execution_model": "MARKET",
                            "expiration_bars": 1,
                            "entry_zone": f"{fvg_bot:.4f} - {fvg_top:.4f}",
                            "ideal_entry": entry,
                            "stop_loss": sl,
                            "tp1": tp1,
                            "tp2": "N/A",
                            "risk_reward": f"1:{abs(entry-tp1)/abs(sl-entry):.1f}" if abs(sl-entry) > 0 else "N/A",
                            "trigger": "BSL Sweep -> Bearish MSS -> Price entered Bearish FVG",
                            "invalidation": "Close above FVG top.",
                            "confidence": "High",
                            "setup_quality": "A",
                            "liquidity_type": sweep.get("type", "SWING_HIGH"),
                            "liquidity_timeframe": "EXECUTION" if sweep.get("type") not in ["PDH", "PDL", "PWH", "PWL"] else bias_tf,
                            "session": session_name,
                            "reason": "N/A",
                            "bias_timeframe": bias_tf,
                            "structure_timeframe": struct_tf,
                            "htf_bias": htf_bias,
                            "confluence_score": f"{c_score}/3",
                            "confluence_reasons": c_reasons
                        }
                        
        return self.build_no_trade("No ICT 2022 setup detected in recent window.", context)
