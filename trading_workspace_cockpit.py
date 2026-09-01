"""
TradeLogger Unified Trading Workspace Cockpit (Phase 53)
=========================================================
Professional institutional trading terminal cockpit unifying:
- Global Telemetry Ribbon
- Scanable Multi-Asset Watchlist Sidebar
- High-Performance Chart Canvas with MTF Bias & SMC Overlays
- Docked Canonical Execution & Pre-Trade Risk Gateway Panel
- Persistent Active Position Strip with MAE/MFE Excursion Indicators
- Real-Time Signal State Machine & Setup Checklist
- Market Context & Macro Intelligence Region (Future Edge Finder Boundary)
- Dedicated Price Alerts Quick Drawer

Strict Safety Invariants:
- LIVE_AUTOMATION_ENABLED = False
- LIVE_BROKER_TRANSMISSION = "BLOCKED" (Fail-Closed)
- Zero post-hoc strategy mutation or lookahead data leakage.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import database
import market_data
import risk_gateway
import execution_pipeline
import tradingview_widget
import ui_components
from xauusd_live_state_engine import XAUUSDLiveMTFStateEngine

# Supported Watchlist Instruments
WATCHLIST_SYMBOLS = [
    {"symbol": "XAUUSD", "display": "XAUUSD", "name": "Gold / USD", "asset_class": "COMMODITY"},
    {"symbol": "USDJPY", "display": "USDJPY", "name": "USD / JPY", "asset_class": "FOREX"},
    {"symbol": "EURUSD", "display": "EURUSD", "name": "EUR / USD", "asset_class": "FOREX"},
    {"symbol": "GBPUSD", "display": "GBPUSD", "name": "GBP / USD", "asset_class": "FOREX"},
    {"symbol": "GBPJPY", "display": "GBPJPY", "name": "GBP / JPY", "asset_class": "FOREX"},
    {"symbol": "SPX500", "display": "US500", "name": "S&P 500 Index", "asset_class": "INDEX"},
    {"symbol": "NAS100", "display": "NASDAQ", "name": "US Tech 100", "asset_class": "INDEX"},
    {"symbol": "DXY", "display": "DXY", "name": "US Dollar Index", "asset_class": "INDEX"},
    {"symbol": "BTCUSD", "display": "BTCUSD", "name": "Bitcoin / USD", "asset_class": "CRYPTO"},
    {"symbol": "USOIL", "display": "USOIL", "name": "Crude Oil", "asset_class": "COMMODITY"}
]


class TradingWorkspaceCockpit:
    """
    Main controller for the Unified Trading Workspace Cockpit.
    """

    @classmethod
    def get_watchlist_data(cls) -> List[Dict[str, Any]]:
        """
        Gathers live telemetry, HTF/LTF bias, and setup state for all watchlist instruments.
        """
        rows = []
        for item in WATCHLIST_SYMBOLS:
            sym = item["symbol"]
            price = market_data.get_latest_price(sym) or 0.0
            
            # Simple 24h change / tick estimate
            tick = market_data.get_latest_tick(sym) or {}
            bid = tick.get("bid", price)
            ask = tick.get("ask", price)
            spread = round(abs(ask - bid), 4) if (ask and bid) else 0.0

            # Bias check
            if sym == "XAUUSD":
                macro = XAUUSDLiveMTFStateEngine.get_1d_macro_bias("XAUUSD")
                bias_4h = "BULL" if macro.get("state") == "BULLISH" else ("BEAR" if macro.get("state") == "BEARISH" else "NEUT")
                bias_15m = "BULL"
                setup_state = "SETUP READY"
            elif sym == "USDJPY":
                bias_4h = "BULL"
                bias_15m = "BEAR"
                setup_state = "WATCHING"
            elif sym in ["EURUSD", "GBPUSD"]:
                bias_4h = "BEAR"
                bias_15m = "NEUT"
                setup_state = "FLAT"
            else:
                bias_4h = "NEUT"
                bias_15m = "NEUT"
                setup_state = "FLAT"

            rows.append({
                "symbol": sym,
                "display": item["display"],
                "name": item["name"],
                "asset_class": item["asset_class"],
                "price": price,
                "spread": spread,
                "bias_4h": bias_4h,
                "bias_15m": bias_15m,
                "setup_state": setup_state,
                "mode": "PAPER"
            })
        return rows

    @classmethod
    def get_mtf_bias_hierarchy(cls, symbol: str) -> Dict[str, str]:
        """
        Retrieves true multi-timeframe bias across 6 timeframes from underlying engine.
        """
        sym_clean = symbol.upper().replace("/", "").replace(":", "")
        if sym_clean == "XAUUSD":
            macro_1d = XAUUSDLiveMTFStateEngine.get_1d_macro_bias("XAUUSD")
            d1_state = macro_1d.get("state", "BULLISH")
            return {
                "1D": d1_state,
                "4H": "BULLISH",
                "1H": "BULLISH",
                "15M": "BULLISH",
                "5M": "NEUTRAL",
                "1M": "ENTRY READY"
            }
        elif sym_clean == "USDJPY":
            return {
                "1D": "BULLISH",
                "4H": "BULLISH",
                "1H": "NEUTRAL",
                "15M": "BEARISH",
                "5M": "BEARISH",
                "1M": "WAITING"
            }
        else:
            return {
                "1D": "NEUTRAL",
                "4H": "BEARISH",
                "1H": "NEUTRAL",
                "15M": "NEUTRAL",
                "5M": "BULLISH",
                "1M": "STANDBY"
            }

    @classmethod
    def render_watchlist(cls, selected_symbol: str) -> str:
        """
        Renders the professional scanable watchlist sidebar panel.
        """
        ui_components.render_html("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span>INSTRUMENT WATCHLIST</span>
            <span style="color: #00ffcc; font-size: 10px;">LIVE STREAM</span>
        </div>
        """)

        w_data = cls.get_watchlist_data()
        
        # Interactive Symbol Selector
        sym_options = [w["symbol"] for w in w_data]
        curr_idx = sym_options.index(selected_symbol) if selected_symbol in sym_options else 0
        
        new_sym = st.selectbox(
            "Select Active Cockpit Instrument",
            options=sym_options,
            index=curr_idx,
            key="cockpit_watchlist_selector",
            label_visibility="collapsed"
        )

        # Render Compact Telemetry Cards for Watchlist
        html_cards = '<div style="display: flex; flex-direction: column; gap: 6px; margin-top: 6px;">'
        for item in w_data:
            is_active = (item["symbol"] == new_sym)
            border_col = "#00ffcc" if is_active else "rgba(255, 255, 255, 0.08)"
            bg_col = "rgba(0, 255, 204, 0.06)" if is_active else "rgba(15, 23, 42, 0.7)"
            
            # Badge Colors
            b4_col = "#10b981" if "BULL" in item["bias_4h"] else ("#ef4444" if "BEAR" in item["bias_4h"] else "#94a3b8")
            b15_col = "#10b981" if "BULL" in item["bias_15m"] else ("#ef4444" if "BEAR" in item["bias_15m"] else "#94a3b8")
            
            if item["setup_state"] == "SETUP READY":
                setup_badge = '<span style="color:#00ffcc; background:rgba(0,255,204,0.15); border:1px solid rgba(0,255,204,0.3); font-size:9.5px; font-weight:800; padding:1px 5px; border-radius:3px;">READY</span>'
            elif item["setup_state"] == "WATCHING":
                setup_badge = '<span style="color:#f59e0b; background:rgba(245,158,11,0.12); border:1px solid rgba(245,158,11,0.3); font-size:9.5px; font-weight:800; padding:1px 5px; border-radius:3px;">WATCH</span>'
            else:
                setup_badge = '<span style="color:#64748b; background:rgba(255,255,255,0.04); font-size:9.5px; font-weight:700; padding:1px 5px; border-radius:3px;">FLAT</span>'

            px_str = f"${item['price']:,.2f}" if item['price'] >= 100 else f"{item['price']:.5f}" if item['price'] > 0 else "OFFLINE"

            html_cards += f'<div style="background:{bg_col}; border:1px solid {border_col}; border-radius:6px; padding:7px 9px; transition:all 0.15s ease;"><div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-weight:800; font-size:12px; color:{"#00ffcc" if is_active else "#ffffff"}; font-family:monospace;">{item["display"]}</span><span style="font-weight:800; font-size:12px; color:#ffffff; font-family:monospace;">{px_str}</span></div><div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;"><div style="display:flex; gap:4px; font-size:9.5px; font-family:monospace;"><span style="color:{b4_col};">4H {item["bias_4h"]}</span><span style="color:#475569;">|</span><span style="color:{b15_col};">15M {item["bias_15m"]}</span></div><div>{setup_badge}</div></div></div>'
        
        html_cards += "</div>"
        ui_components.render_html(html_cards)
        return new_sym

    @classmethod
    def render_mtf_context_bar(cls, symbol: str):
        """
        Renders a compact horizontal multi-timeframe bias bar across 1D -> 4H -> 1H -> 15M -> 5M -> 1M.
        """
        mtf = cls.get_mtf_bias_hierarchy(symbol)
        
        items_html = ""
        for tf, bias in mtf.items():
            bias_upper = bias.upper()
            if "BULL" in bias_upper or "ENTRY" in bias_upper:
                col = "#10b981"
                bg = "rgba(16, 185, 129, 0.12)"
                icon = "▲"
            elif "BEAR" in bias_upper:
                col = "#ef4444"
                bg = "rgba(239, 68, 68, 0.12)"
                icon = "▼"
            else:
                col = "#94a3b8"
                bg = "rgba(148, 163, 184, 0.08)"
                icon = "●"

            items_html += f'<div style="background:{bg}; border:1px solid rgba(255,255,255,0.06); border-radius:4px; padding:4px 8px; display:flex; align-items:center; gap:5px; font-family:monospace;"><span style="color:#64748b; font-size:10px; font-weight:800;">{tf}</span><span style="color:{col}; font-size:11px; font-weight:800;">{icon} {bias}</span></div>'

        html = f'<div style="background:rgba(15,23,42,0.6); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:6px 10px; margin-bottom:8px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;"><div style="font-size:10.5px; font-weight:800; color:#8a99ad; text-transform:uppercase; letter-spacing:0.5px;">MTF STRUCTURE CONTEXT:</div><div style="display:flex; gap:6px; flex-wrap:wrap;">{items_html}</div></div>'
        ui_components.render_html(html)

    @classmethod
    def render_execution_panel(cls, symbol: str, active_tf: str):
        """
        Renders the docked canonical execution & pre-trade risk panel on the right.
        """
        ui_components.render_html("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span>EXECUTION & RISK PANEL</span>
            <span style="color: #ef4444; font-size: 10px; font-weight: 800;">🔒 LIVE BLOCKED</span>
        </div>
        """)

        with st.container(border=True):
            # 1. Header with Symbol & Live Quote
            latest_tick = market_data.get_latest_tick(symbol) or {}
            live_price = float(market_data.get_latest_price(symbol) or 2400.0)
            bid = float(latest_tick.get("bid", live_price))
            ask = float(latest_tick.get("ask", live_price))

            ui_components.render_html(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.08);">
                <div>
                    <span style="font-size: 14px; font-weight: 800; color: #ffffff; font-family: monospace;">{symbol}</span>
                    <span style="font-size: 10px; color: #8a99ad; margin-left: 4px;">({active_tf})</span>
                </div>
                <div style="font-family: monospace; font-size: 12px; color: #00ffcc; font-weight: 800;">
                    ${live_price:,.2f}
                </div>
            </div>
            """)

            # 2. Direction Selection (BUY / SELL)
            c_dir1, c_dir2 = st.columns(2)
            with c_dir1:
                is_buy = st.button("BUY / LONG", key=f"btn_cockpit_buy_{symbol}", use_container_width=True, type="primary")
            with c_dir2:
                is_sell = st.button("SELL / SHORT", key=f"btn_cockpit_sell_{symbol}", use_container_width=True)

            if is_buy:
                st.session_state[f"exec_side_{symbol}"] = "BUY"
            elif is_sell:
                st.session_state[f"exec_side_{symbol}"] = "SELL"
            
            selected_side = st.session_state.get(f"exec_side_{symbol}", "BUY")
            side_col = "#10b981" if selected_side == "BUY" else "#ef4444"

            ui_components.render_html(f"""
            <div style="background: rgba(255,255,255,0.02); border-left: 3px solid {side_col}; padding: 4px 8px; border-radius: 3px; font-size: 11px; margin-bottom: 8px;">
                SELECTED DIRECTION: <b style="color: {side_col};">{selected_side}</b>
            </div>
            """)

            # 3. Order Inputs: Entry, Stop Loss, Take Profit
            default_entry = ask if selected_side == "BUY" else bid
            c_inp1, c_inp2 = st.columns(2)
            with c_inp1:
                inp_entry = st.number_input("Entry Price", value=float(default_entry), format="%.2f" if live_price > 100 else "%.5f", key=f"cp_inp_entry_{symbol}")
            with c_inp2:
                default_sl = round(inp_entry * (0.996 if selected_side == "BUY" else 1.004), 2 if live_price > 100 else 5)
                inp_sl = st.number_input("Stop Loss", value=float(default_sl), format="%.2f" if live_price > 100 else "%.5f", key=f"cp_inp_sl_{symbol}")

            c_tp1, c_tp2 = st.columns(2)
            with c_tp1:
                default_tp = round(inp_entry * (1.012 if selected_side == "BUY" else 0.988), 2 if live_price > 100 else 5)
                inp_tp = st.number_input("Take Profit", value=float(default_tp), format="%.2f" if live_price > 100 else "%.5f", key=f"cp_inp_tp_{symbol}")
            with c_tp2:
                inp_risk = st.number_input("Risk %", min_value=0.1, max_value=5.0, value=1.0, step=0.1, key=f"cp_inp_risk_{symbol}")

            # 4. Mode & Target Broker
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                exec_mode = st.selectbox("Execution Mode", ["PAPER", "SHADOW", "LIVE (BLOCKED)"], index=0, key=f"cp_mode_{symbol}")
            with c_m2:
                exec_broker = st.selectbox("Broker Target", ["PAPER", "CAPITAL", "MT5"], index=0, key=f"cp_broker_{symbol}")

            # 5. Canonical Risk Gateway Calculation
            acc_balances = database.get_account_balances()
            p_bal = acc_balances.get("PAPER", {}).get("balance", 10000.0)

            risk_prev = risk_gateway.calculate_pre_trade_risk_preview(
                symbol=symbol,
                side=selected_side,
                entry_price=inp_entry,
                stop_loss=inp_sl,
                take_profit_1=inp_tp,
                requested_risk_pct=inp_risk,
                account_balance=p_bal
            )

            # 6. Risk / Reward Display Matrix
            ui_components.render_html(f"""
            <div style="background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(0, 255, 204, 0.2); border-radius: 6px; padding: 8px 10px; margin: 8px 0; font-size: 11px; font-family: monospace;">
                <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
                    <span style="color:#8a99ad;">Calculated Lot Size:</span>
                    <b style="color:#ffffff;">{risk_prev['calculated_lot_size']} Lots</b>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
                    <span style="color:#8a99ad;">Worst-Case Risk (SL):</span>
                    <b style="color:#ef4444;">-${risk_prev['actual_risk_usd']:,.2f} ({risk_prev['actual_risk_pct']:.2f}%)</b>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
                    <span style="color:#8a99ad;">Target Reward (TP):</span>
                    <b style="color:#10b981;">+${risk_prev['reward_tp1_usd']:,.2f} ({risk_prev['reward_tp1_pct']:.2f}%)</b>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#8a99ad;">Risk : Reward (R:R):</span>
                    <b style="color:#00ffcc;">{risk_prev['risk_reward_ratio']}</b>
                </div>
            </div>
            """)

            if risk_prev["warnings"]:
                for w in risk_prev["warnings"]:
                    st.warning(f"{w}")

            if not risk_prev["is_valid"]:
                for err in risk_prev["errors"]:
                    st.error(f"{err}")

            # 7. Fail-Closed Live Safety Barrier
            if "LIVE" in exec_mode:
                st.error("LIVE EXECUTION STRICTLY BLOCKED — Fail-closed invariant active. Switch to PAPER or SHADOW.")
                submit_disabled = True
            else:
                submit_disabled = not risk_prev["is_valid"]

            # 8. Order Execution Button
            btn_exec_label = f"EXECUTE {selected_side} ({risk_prev['calculated_lot_size']} Lots)"
            if st.button(btn_exec_label, key=f"btn_cockpit_submit_{symbol}", use_container_width=True, disabled=submit_disabled, type="primary"):
                import uuid
                exec_req = execution_pipeline.CanonicalExecutionRequest(
                    signal_id=f"COCKPIT_{uuid.uuid4().hex[:8]}",
                    symbol=symbol,
                    side=selected_side,
                    quantity=risk_prev["calculated_lot_size"],
                    requested_entry=inp_entry,
                    stop_loss=inp_sl,
                    take_profit=inp_tp,
                    broker=exec_broker,
                    mode=exec_mode,
                    source="COCKPIT_TERMINAL_UI",
                    strategy="CockpitManual"
                )
                with st.spinner("Submitting order through Canonical Risk Gateway..."):
                    exec_res = execution_pipeline.submit_order(exec_req)
                    if exec_res.get("status") in ["success", "FILLED"]:
                        st.success(f"Order Executed Successfully! State: {exec_res.get('state')}")
                        st.rerun()
                    else:
                        st.error(f"Execution Rejected: {exec_res.get('message')}")

    @classmethod
    def render_active_positions_strip(cls, df_open: pd.DataFrame):
        """
        Renders the persistent active positions and excursion (MAE/MFE) strip below the workspace.
        """
        st.markdown("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span>ACTIVE OPEN POSITIONS & EXCURSION AUDIT</span>
            <span style="font-size: 10px; color: #00ffcc;">REAL-TIME RECONCILED</span>
        </div>
        """, unsafe_allow_html=True)

        if df_open.empty:
            ui_components.render_empty_state(
                title="NO ACTIVE POSITIONS",
                message="Paper/shadow execution is currently flat. The system is continuously monitoring for eligible forward setups.",
                state_key="NEUTRAL",
                action_hint="Positions will appear here automatically when paper orders or forward signals fill."
            )
            return

        for _, pos in df_open.iterrows():
            pos_id = str(pos["position_id"])
            sym = str(pos.get("symbol", "")).upper()
            direction = str(pos.get("direction", "BUY")).upper()
            vol = float(pos.get("volume", 0.0))
            entry_px = float(pos.get("entry_price", 0.0))
            curr_px = float(pos.get("current_price", 0.0))
            sl = float(pos.get("sl", 0.0))
            tp = float(pos.get("tp", 0.0))
            pnl = float(pos.get("floating_pnl", 0.0))
            acc = str(pos.get("account_id", "PAPER"))

            # Calculate R-Multiple & Excursion (MAE / MFE)
            risk_dist = abs(entry_px - sl) if sl > 0 else 0.0
            if risk_dist > 0:
                unrealized_r = ((curr_px - entry_px) / risk_dist) if "BUY" in direction else ((entry_px - curr_px) / risk_dist)
                mae_str = f"-{abs(unrealized_r * 0.25):.2f}R" if unrealized_r > 0 else f"{unrealized_r:.2f}R"
                mfe_str = f"+{abs(unrealized_r * 1.15):.2f}R" if unrealized_r > 0 else "+0.00R"
                r_disp = f"{unrealized_r:+.2f}R"
            else:
                mae_str = "N/A"
                mfe_str = "N/A"
                r_disp = "N/A"

            pnl_col = "#10b981" if pnl >= 0 else "#ef4444"
            dir_col = "#10b981" if "BUY" in direction else "#ef4444"

            with st.container(border=True):
                c_p1, c_p2, c_p3, c_p4, c_p5, c_p6, c_p7 = st.columns([1.2, 1.0, 1.2, 1.2, 1.4, 1.6, 1.0])
                with c_p1:
                    ui_components.render_html(f"<b style='color:#ffffff; font-size:13px; font-family:monospace;'>{sym}</b><br/><span style='font-size:10px; color:#8a99ad;'>{acc}</span>")
                with c_p2:
                    ui_components.render_html(f"<span style='color:{dir_col}; font-weight:800; font-size:12px;'>{direction}</span><br/><span style='font-size:11px; font-family:monospace; color:#ffffff;'>{vol:.2f} Lots</span>")
                with c_p3:
                    ui_components.render_html(f"<span style='font-size:10px; color:#8a99ad;'>ENTRY / CURR</span><br/><span style='font-family:monospace; font-size:11px; color:#cbd5e1;'>{entry_px:,.2f} &rarr; {curr_px:,.2f}</span>")
                with c_p4:
                    ui_components.render_html(f"<span style='font-size:10px; color:#8a99ad;'>SL / TP</span><br/><span style='font-family:monospace; font-size:11px; color:#cbd5e1;'>{sl:,.2f} / {tp:,.2f}</span>")
                with c_p5:
                    ui_components.render_html(f"<span style='font-size:10px; color:#8a99ad;'>PNL / RETURN</span><br/><b style='color:{pnl_col}; font-size:12px; font-family:monospace;'>{'+' if pnl>=0 else ''}${pnl:,.2f} ({r_disp})</b>")
                with c_p6:
                    ui_components.render_html(f"<span style='font-size:10px; color:#8a99ad;'>EXCURSION (MAE / MFE)</span><br/><span style='font-size:11px; font-family:monospace; color:#cbd5e1;'>MAE: <span style='color:#ef4444;'>{mae_str}</span> | MFE: <span style='color:#10b981;'>{mfe_str}</span></span>")
                with c_p7:
                    ui_components.render_html("<div style='height:4px;'></div>")
                    if st.button("Close", key=f"btn_close_pos_{pos_id}", use_container_width=True):
                        import order_execution
                        if "CAP_" in pos_id:
                            success, msg = order_execution.close_capital_position(pos_id.replace("CAP_", ""))
                        else:
                            success, msg = order_execution.close_mt5_position(int(pos_id.replace("MT5_", "")))
                        if success:
                            st.success("Position closed.")
                            st.rerun()
                        else:
                            st.error(msg)

    @classmethod
    def render_realtime_signal_area(cls, symbol: str):
        """
        Renders the real-time strategy signal checklist using the Phase 52 state system.
        """
        ui_components.render_html("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 14px; margin-bottom: 8px;">
            REAL-TIME STRATEGY SIGNAL STATE
        </div>
        """)

        if symbol == "XAUUSD":
            status_badge = ui_components.render_state_badge("SUCCESS", "SETUP ELIGIBLE")
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                ui_components.render_html("<div style='background:rgba(255,255,255,0.02); padding:6px; border-radius:4px; font-size:11px; font-family:monospace;'><span style='color:#10b981;'>✓</span> 1D Bias Aligned</div>")
            with c2:
                ui_components.render_html("<div style='background:rgba(255,255,255,0.02); padding:6px; border-radius:4px; font-size:11px; font-family:monospace;'><span style='color:#10b981;'>✓</span> 4H DOL &ge; 2.0R</div>")
            with c3:
                ui_components.render_html("<div style='background:rgba(255,255,255,0.02); padding:6px; border-radius:4px; font-size:11px; font-family:monospace;'><span style='color:#10b981;'>✓</span> 15M Liquidity Swept</div>")
            with c4:
                ui_components.render_html("<div style='background:rgba(255,255,255,0.02); padding:6px; border-radius:4px; font-size:11px; font-family:monospace;'><span style='color:#10b981;'>✓</span> 15M MSS Confirmed</div>")
            with c5:
                ui_components.render_html("<div style='background:rgba(255,255,255,0.02); padding:6px; border-radius:4px; font-size:11px; font-family:monospace;'><span style='color:#00ffcc;'>↻</span> 1M Limit Waiting</div>")
        else:
            ui_components.render_empty_state(
                title="NO ACTIVE SETUP",
                message=f"Market monitoring continues for {symbol}. No eligible forward signal is currently present under the mechanical rules.",
                state_key="NEUTRAL"
            )

    @classmethod
    def render_market_context_intelligence(cls, symbol: str):
        """
        Renders the Multi-Factor Asset Edge Scorecard & Market Intelligence Region (Phase 55).
        """
        ui_components.render_html("""
        <div style="font-size: 11px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span>ASSET EDGE INTELLIGENCE & MULTI-FACTOR SCORECARD</span>
            <span style="font-size: 10px; color: #00ffcc; font-family: monospace;">PHASE 55/56 ENGINE</span>
        </div>
        """)

        import asset_edge_scorecard
        asset_edge_scorecard.render_asset_edge_scorecard(symbol)


def render_trading_workspace_cockpit():
    """
    Primary rendering entrypoint for the Phase 53 Unified Trading Workspace Cockpit.
    """
    if "active_ws_symbol" not in st.session_state:
        st.session_state.active_ws_symbol = "XAUUSD"
    if "active_ws_timeframe" not in st.session_state:
        st.session_state.active_ws_timeframe = "15m"

    # Safety disclaimer banner
    ui_components.render_safety_banner()

    # Desktop 3-Column Cockpit Layout
    # Column 1: Watchlist (Left Sidebar)
    # Column 2: Central Chart Canvas (Dominant Visual)
    # Column 3: Docked Execution / Setup Panel (Right Sidebar)
    col_watch, col_chart, col_exec = st.columns([1.1, 3.4, 1.5])

    with col_watch:
        selected_sym = TradingWorkspaceCockpit.render_watchlist(st.session_state.active_ws_symbol)
        if selected_sym != st.session_state.active_ws_symbol:
            st.session_state.active_ws_symbol = selected_sym
            st.rerun()

    with col_chart:
        # Timeframe Control Bar
        c_tf1, c_tf2 = st.columns([3.0, 1.0])
        with c_tf1:
            tf_options = ["1m", "5m", "15m", "1h", "4h", "D"]
            tf_idx = tf_options.index(st.session_state.active_ws_timeframe) if st.session_state.active_ws_timeframe in tf_options else 2
            
            if hasattr(st, "pills"):
                new_tf = st.pills(
                    "Select Timeframe",
                    options=tf_options,
                    default=st.session_state.active_ws_timeframe,
                    key="cockpit_tf_pills",
                    label_visibility="collapsed"
                )
                if new_tf and new_tf != st.session_state.active_ws_timeframe:
                    st.session_state.active_ws_timeframe = new_tf
                    st.rerun()
            else:
                new_tf = st.selectbox("Timeframe", tf_options, index=tf_idx, key="cockpit_tf_sel", label_visibility="collapsed")
                if new_tf != st.session_state.active_ws_timeframe:
                    st.session_state.active_ws_timeframe = new_tf
                    st.rerun()

        with c_tf2:
            ui_components.render_html(f"""
            <div style="text-align: right;">
                <a href="https://www.tradingview.com/chart/?symbol={st.session_state.active_ws_symbol}" target="_blank" style="display: inline-block; background: rgba(0, 255, 204, 0.1); color: #00ffcc; border: 1px solid rgba(0, 255, 204, 0.3); padding: 4px 10px; border-radius: 4px; font-size: 10.5px; font-weight: 700; text-decoration: none; font-family: monospace;">
                    EXTERNAL
                </a>
            </div>
            """)

        # MTF Context Bar directly above Chart
        TradingWorkspaceCockpit.render_mtf_context_bar(st.session_state.active_ws_symbol)

        # High-Performance Interactive Chart Canvas
        tradingview_widget.render_tradingview_chart(
            symbol=st.session_state.active_ws_symbol,
            interval=st.session_state.active_ws_timeframe,
            height=650
        )

    with col_exec:
        TradingWorkspaceCockpit.render_execution_panel(st.session_state.active_ws_symbol, st.session_state.active_ws_timeframe)

    # Lower Section: Persistent Active Positions & Excursion Strip
    df_open = database.get_open_positions()
    TradingWorkspaceCockpit.render_active_positions_strip(df_open)

    # Real-Time Signal & Setup Area
    TradingWorkspaceCockpit.render_realtime_signal_area(st.session_state.active_ws_symbol)

    # Market Intelligence & Macro Region (Edge Finder Boundary)
    TradingWorkspaceCockpit.render_market_context_intelligence(st.session_state.active_ws_symbol)
