"""
Phase 16 — USDJPY SMC Trend-Continuation Strategy Module
Deterministic implementation of the SMC Continuation Model:
4H Macro Directional Bias -> 1H Structure Alignment -> Counter-trend Liquidity Sweep -> 15m Displacement -> 15m BOS -> FVG/OB Retracement Entry.
"""

import pandas as pd
import numpy as np
from .base import BaseStrategy
from .smc_utils import (
    add_smc_features,
    detect_liquidity_sweep,
    detect_mss,
    extract_active_fair_value_gaps,
    extract_order_blocks
)


class USDJPYContinuationStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "USDJPY SMC Continuation"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Trend-continuation model trading 15m BOS + FVG retracements in the direction of the 4H/1H macro trend after a counter-trend liquidity interaction."

    def analyze(self, df: pd.DataFrame, current_index: int, context: dict = None) -> dict:
        if current_index < 25:
            return self.build_no_trade("Insufficient historical bars for continuation model.", context)

        if 'last_swing_high' not in df.columns:
            df = add_smc_features(df)

        row = df.iloc[current_index]
        close = float(row['Close'])
        atr = float(row.get('ATR', 0.10))
        if atr <= 0:
            atr = 0.10

        sl_atr = context.get('sl_atr', 1.0) if context else 1.0
        tp_atr = context.get('tp_atr', 2.5) if context else 2.5
        min_displacement_atr = context.get('min_displacement_atr', 1.0) if context else 1.0

        # Multi-Timeframe Bias (Safely parse aligned HTF column or compute fallback)
        raw_bias = row.get('HTF_Bias_BIAS')
        if pd.isna(raw_bias) or str(raw_bias).upper() in ['NAN', 'NONE', '']:
            htf_bias = 'NEUTRAL'
        else:
            htf_bias = str(raw_bias).upper()

        if htf_bias == 'NEUTRAL' and len(df) >= 50:
            ema20 = df['Close'].ewm(span=20, adjust=False).mean().iloc[current_index]
            ema50 = df['Close'].ewm(span=50, adjust=False).mean().iloc[current_index]
            if close > ema20 and ema20 > ema50:
                htf_bias = 'BULLISH'
            elif close < ema20 and ema20 < ema50:
                htf_bias = 'BEARISH'

        lookback = 20
        start_idx = max(0, current_index - lookback)
        window = df.iloc[start_idx:current_index + 1]

        # ----------------------------------------------------
        # 1. BULLISH CONTINUATION BRANCH (HTF Bias == BULLISH)
        # ----------------------------------------------------
        if htf_bias in ["BULLISH", "NEUTRAL"]:
            recent_bull_fvg = window[pd.notna(window['bullish_fvg_bottom'])]
            if not recent_bull_fvg.empty:
                last_fvg_idx = recent_bull_fvg.index[-1]
                fvg_top = float(recent_bull_fvg.loc[last_fvg_idx, 'bullish_fvg_top'])
                fvg_bot = float(recent_bull_fvg.loc[last_fvg_idx, 'bullish_fvg_bottom'])

                # Check if current bar is retracing into this Bullish FVG
                if fvg_bot <= row['Low'] <= fvg_top or fvg_bot <= row['Close'] <= fvg_top:
                    fvg_pos = df.index.get_loc(last_fvg_idx)
                    
                    # The FVG impulse candle is at fvg_pos - 1
                    impulse_idx = max(0, fvg_pos - 1)
                    impulse_row = df.iloc[impulse_idx]
                    impulse_body = abs(float(impulse_row['Close']) - float(impulse_row['Open']))
                    
                    # Verify displacement threshold (or if min_displacement_atr == 0)
                    if impulse_body >= (min_displacement_atr * atr * 0.8):
                        # Verify 15m BOS (Break of Structure upward)
                        pre_fvg_window = df.iloc[max(0, fvg_pos - 10):fvg_pos]
                        bos_detected = False
                        for i in range(len(pre_fvg_window)):
                            if detect_mss(df, fvg_pos - 10 + i) == "BULLISH":
                                bos_detected = True
                                break

                        if bos_detected:
                            # Preceding Sell-Side Liquidity (SSL) sweep during pullback
                            sweep_detected = False
                            sweep_level = fvg_bot
                            sweep_type = "INTERNAL_SWING"
                            for i in range(start_idx, fvg_pos):
                                sweep_info = detect_liquidity_sweep(df, i)
                                if sweep_info.get("sweep") == "SSL":
                                    sweep_detected = True
                                    sweep_level = float(sweep_info.get("level", fvg_bot))
                                    sweep_type = sweep_info.get("type", "INTERNAL_SWING")
                                    break

                            entry = close
                            sl = sweep_level - (atr * 0.2) if sweep_level < entry else entry - (atr * sl_atr)
                            risk_dist = entry - sl
                            if risk_dist > 0:
                                tp1 = entry + (risk_dist * tp_atr)

                                session_name = "N/A"
                                if hasattr(row, 'is_asia') and getattr(row, 'is_asia'): session_name = "ASIA"
                                elif hasattr(row, 'is_london') and getattr(row, 'is_london'): session_name = "LONDON"
                                elif hasattr(row, 'is_ny') and getattr(row, 'is_ny'): session_name = "NEW_YORK"

                                c_score = 30
                                c_reasons = ["Bullish Continuation Setup"]
                                if htf_bias == "BULLISH": c_score += 30; c_reasons.append("4H Macro Trend Aligned")
                                if session_name in ["LONDON", "NEW_YORK"]: c_score += 20; c_reasons.append("Active Killzone")
                                if sweep_type in ["PDL", "PWL", "ASIAN_LOW"]: c_score += 20; c_reasons.append("Key Liquidity Swept")

                                return {
                                    "status": "READY",
                                    "setup": "LONG",
                                    "signal": "BUY",
                                    "direction": "BUY",
                                    "execution_model": "MARKET",
                                    "expiration_bars": 1,
                                    "symbol": context.get("symbol", "USDJPY") if context else "USDJPY",
                                    "timeframe": context.get("timeframe", "15m") if context else "15m",
                                    "entry_zone": f"{fvg_bot:.4f} - {fvg_top:.4f}",
                                    "ideal_entry": round(entry, 5),
                                    "entry_price": round(entry, 5),
                                    "stop_loss": round(sl, 5),
                                    "take_profit": round(tp1, 5),
                                    "tp1": round(tp1, 5),
                                    "tp2": round(entry + (risk_dist * 3.5), 5),
                                    "take_profit_1": round(tp1, 5),
                                    "take_profit_2": round(entry + (risk_dist * 3.5), 5),
                                    "risk_reward": f"1:{abs(tp1-entry)/abs(entry-sl):.1f}" if abs(entry-sl) > 0 else "1:2.5",
                                    "risk_reward_ratio": round(abs(tp1-entry)/abs(entry-sl), 2) if abs(entry-sl) > 0 else 2.5,
                                    "liquidity_type": sweep_type,
                                    "session": session_name,
                                    "confluence_score": f"{c_score}/100",
                                    "confluence_reasons": c_reasons,
                                    "setup_type": "SMC_CONTINUATION_LONG",
                                    "trigger": f"4H Bias Aligned -> Pullback SSL ({sweep_type}) -> 15m BOS -> FVG Entry",
                                    "reason": f"Bullish continuation entry on FVG retracement after SSL interaction ({sweep_type}) aligned with 4H bias."
                                }

        # ----------------------------------------------------
        # 2. BEARISH CONTINUATION BRANCH (HTF Bias == BEARISH)
        # ----------------------------------------------------
        if htf_bias in ["BEARISH", "NEUTRAL"]:
            recent_bear_fvg = window[pd.notna(window['bearish_fvg_top'])]
            if not recent_bear_fvg.empty:
                last_fvg_idx = recent_bear_fvg.index[-1]
                fvg_top = float(recent_bear_fvg.loc[last_fvg_idx, 'bearish_fvg_top'])
                fvg_bot = float(recent_bear_fvg.loc[last_fvg_idx, 'bearish_fvg_bottom'])

                if fvg_bot <= row['High'] <= fvg_top or fvg_bot <= row['Close'] <= fvg_top:
                    fvg_pos = df.index.get_loc(last_fvg_idx)
                    
                    impulse_idx = max(0, fvg_pos - 1)
                    impulse_row = df.iloc[impulse_idx]
                    impulse_body = abs(float(impulse_row['Close']) - float(impulse_row['Open']))
                    
                    if impulse_body >= (min_displacement_atr * atr * 0.8):
                        pre_fvg_window = df.iloc[max(0, fvg_pos - 10):fvg_pos]
                        bos_detected = False
                        for i in range(len(pre_fvg_window)):
                            if detect_mss(df, fvg_pos - 10 + i) == "BEARISH":
                                bos_detected = True
                                break

                        if bos_detected:
                            sweep_detected = False
                            sweep_level = fvg_top
                            sweep_type = "INTERNAL_SWING"
                            for i in range(start_idx, fvg_pos):
                                sweep_info = detect_liquidity_sweep(df, i)
                                if sweep_info.get("sweep") == "BSL":
                                    sweep_detected = True
                                    sweep_level = float(sweep_info.get("level", fvg_top))
                                    sweep_type = sweep_info.get("type", "INTERNAL_SWING")
                                    break

                            entry = close
                            sl = sweep_level + (atr * 0.2) if sweep_level > entry else entry + (atr * sl_atr)
                            risk_dist = sl - entry
                            if risk_dist > 0:
                                tp1 = entry - (risk_dist * tp_atr)

                                session_name = "N/A"
                                if hasattr(row, 'is_asia') and getattr(row, 'is_asia'): session_name = "ASIA"
                                elif hasattr(row, 'is_london') and getattr(row, 'is_london'): session_name = "LONDON"
                                elif hasattr(row, 'is_ny') and getattr(row, 'is_ny'): session_name = "NEW_YORK"

                                c_score = 30
                                c_reasons = ["Bearish Continuation Setup"]
                                if htf_bias == "BEARISH": c_score += 30; c_reasons.append("4H Macro Trend Aligned")
                                if session_name in ["LONDON", "NEW_YORK"]: c_score += 20; c_reasons.append("Active Killzone")
                                if sweep_type in ["PDH", "PWH", "ASIAN_HIGH"]: c_score += 20; c_reasons.append("Key Liquidity Swept")

                                return {
                                    "status": "READY",
                                    "setup": "SHORT",
                                    "signal": "SELL",
                                    "direction": "SELL",
                                    "execution_model": "MARKET",
                                    "expiration_bars": 1,
                                    "symbol": context.get("symbol", "USDJPY") if context else "USDJPY",
                                    "timeframe": context.get("timeframe", "15m") if context else "15m",
                                    "entry_zone": f"{fvg_bot:.4f} - {fvg_top:.4f}",
                                    "ideal_entry": round(entry, 5),
                                    "entry_price": round(entry, 5),
                                    "stop_loss": round(sl, 5),
                                    "take_profit": round(tp1, 5),
                                    "tp1": round(tp1, 5),
                                    "tp2": round(entry - (risk_dist * 3.5), 5),
                                    "take_profit_1": round(tp1, 5),
                                    "take_profit_2": round(entry - (risk_dist * 3.5), 5),
                                    "risk_reward": f"1:{abs(tp1-entry)/abs(entry-sl):.1f}" if abs(entry-sl) > 0 else "1:2.5",
                                    "risk_reward_ratio": round(abs(tp1-entry)/abs(entry-sl), 2) if abs(entry-sl) > 0 else 2.5,
                                    "liquidity_type": sweep_type,
                                    "session": session_name,
                                    "confluence_score": f"{c_score}/100",
                                    "confluence_reasons": c_reasons,
                                    "setup_type": "SMC_CONTINUATION_SHORT",
                                    "trigger": f"4H Bias Aligned -> Pullback BSL ({sweep_type}) -> 15m BOS -> FVG Entry",
                                    "reason": f"Bearish continuation entry on FVG retracement after BSL interaction ({sweep_type}) aligned with 4H bias."
                                }

        return self.build_no_trade("No USDJPY continuation pattern active.", context)
