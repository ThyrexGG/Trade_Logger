# -*- coding: utf-8 -*-
"""
TradeLogger Global Command Palette (Phase 61)
=============================================
Provides a fast, keyboard-navigable command palette (Ctrl + K) routing directly to
all terminal zones, subviews, instruments, workspace layouts, and utilities.

Strict Safety Invariants:
- Routes only to existing safe terminal views.
- Zero live execution triggers or automated order submission from command palette.
- No duplicate navigation logic.
"""

from typing import Dict, List, Any, Optional
import streamlit as st
import ui_components
from user_preferences import UserPreferencesManager
from workspace_layout_manager import WorkspaceLayoutManager

COMMAND_REGISTRY: List[Dict[str, Any]] = [
    # Navigation Commands
    {
        "id": "nav_trading_workspace",
        "title": "Go to Trading Workspace Cockpit",
        "category": "NAVIGATION",
        "icon": "&#128202;",
        "keywords": "charts workspace terminal trading live cockpit",
        "action": {"zone": "TRADING WORKSPACE", "subview": "CHARTS & WORKSPACE"}
    },
    {
        "id": "nav_market_scanner",
        "title": "Open Market Intelligence Scanner & Regime",
        "category": "NAVIGATION",
        "icon": "&#127757;",
        "keywords": "scanner regime heatmap market intelligence command center cross-asset",
        "action": {"zone": "TRADING WORKSPACE", "subview": "MARKET SCANNER & REGIME"}
    },
    {
        "id": "nav_quick_terminal",
        "title": "Open Quick Trading Terminal",
        "category": "NAVIGATION",
        "icon": "&#9889;",
        "keywords": "quick terminal execution order entry manual",
        "action": {"zone": "TRADING WORKSPACE", "subview": "QUICK TERMINAL"}
    },
    {
        "id": "nav_ai_context",
        "title": "Open AI Market Context & Technicals",
        "category": "NAVIGATION",
        "icon": "&#129302;",
        "keywords": "ai technical analysis market context scenarios",
        "action": {"zone": "TRADING WORKSPACE", "subview": "AI MARKET CONTEXT"}
    },
    {
        "id": "nav_price_alerts",
        "title": "Open Price Alerts Drawer",
        "category": "NAVIGATION",
        "icon": "&#128276;",
        "keywords": "alerts notifications price triggers sound",
        "action": {"zone": "TRADING WORKSPACE", "subview": "PRICE ALERTS"}
    },
    {
        "id": "nav_research_lab",
        "title": "Go to Research & Strategy Lab",
        "category": "NAVIGATION",
        "icon": "&#128300;",
        "keywords": "research lab strategy empirical mtf backtest walkforward",
        "action": {"zone": "RESEARCH & STRATEGY LAB", "subview": "RESEARCH LAB OVERVIEW"}
    },
    {
        "id": "nav_xauusd_audit",
        "title": "Open XAUUSD Adversarial Stress Audit",
        "category": "NAVIGATION",
        "icon": "&#128737;",
        "keywords": "xauusd gold adversarial audit stress monte carlo cost slippage",
        "action": {"zone": "RESEARCH & STRATEGY LAB", "subview": "XAUUSD ADVERSARIAL AUDIT"}
    },
    {
        "id": "nav_strategy_sandbox",
        "title": "Open Multi-Timeframe Strategy Sandbox",
        "category": "NAVIGATION",
        "icon": "&#9874;",
        "keywords": "sandbox backtest simulation wfo optimization",
        "action": {"zone": "RESEARCH & STRATEGY LAB", "subview": "STRATEGY SANDBOX"}
    },
    {
        "id": "nav_forward_evidence",
        "title": "Go to Forward Evidence & Governance Cockpit",
        "category": "NAVIGATION",
        "icon": "&#128220;",
        "keywords": "forward evidence governance milestones statistics bootstrap wilson forensics",
        "action": {"zone": "FORWARD EVIDENCE & GOVERNANCE", "subview": "FORWARD EVIDENCE CENTER"}
    },
    {
        "id": "nav_daily_command",
        "title": "Open Daily Trading Command Center",
        "category": "NAVIGATION",
        "icon": "&#128197;",
        "keywords": "daily command center preflight news macro session matrix checklist",
        "action": {"zone": "OPERATIONS, JOURNAL & AUDIT", "subview": "DAILY COMMAND CENTER"}
    },
    {
        "id": "nav_analytics_overview",
        "title": "Open Analytics & Performance Overview",
        "category": "NAVIGATION",
        "icon": "&#128200;",
        "keywords": "analytics performance balance equity curve metrics radar calendar pnl",
        "action": {"zone": "OPERATIONS, JOURNAL & AUDIT", "subview": "ANALYTICS & OVERVIEW"}
    },
    {
        "id": "nav_trade_journal",
        "title": "Open Trade Journal & Setup Studio",
        "category": "NAVIGATION",
        "icon": "&#128214;",
        "keywords": "journal trades closed positions history screenshots logs accounts",
        "action": {"zone": "OPERATIONS, JOURNAL & AUDIT", "subview": "TRADE JOURNAL"}
    },
    {
        "id": "nav_system_health",
        "title": "Open System Health & Execution Operations",
        "category": "NAVIGATION",
        "icon": "&#128154;",
        "keywords": "system health operations broker reconciliation mt5 paper daemon",
        "action": {"zone": "OPERATIONS, JOURNAL & AUDIT", "subview": "SYSTEM HEALTH & PAPER OPS"}
    },

    # Workspace Layout Commands
    {
        "id": "layout_default",
        "title": "Switch to Default Cockpit Layout",
        "category": "WORKSPACE LAYOUT",
        "icon": "&#9638;",
        "keywords": "layout default cockpit 3-column watchlist chart execution",
        "action": {"layout": "DEFAULT"}
    },
    {
        "id": "layout_research",
        "title": "Switch to Research Focus Layout",
        "category": "WORKSPACE LAYOUT",
        "icon": "&#128300;",
        "keywords": "layout research context macro fundamentals edge",
        "action": {"layout": "RESEARCH"}
    },
    {
        "id": "layout_compact",
        "title": "Switch to Compact Density Layout",
        "category": "WORKSPACE LAYOUT",
        "icon": "&#9636;",
        "keywords": "layout compact high density minimal vertical space",
        "action": {"layout": "COMPACT"}
    },
    {
        "id": "layout_analysis",
        "title": "Switch to Full-Width Technical Analysis Layout",
        "category": "WORKSPACE LAYOUT",
        "icon": "&#128200;",
        "keywords": "layout analysis technical dominant chart full width",
        "action": {"layout": "ANALYSIS"}
    },

    # Quick Instrument Commands
    {
        "id": "sym_xauusd",
        "title": "Select Instrument: XAUUSD (Gold / US Dollar)",
        "category": "INSTRUMENT",
        "icon": "&#129351;",
        "keywords": "gold xauusd metals commodity",
        "action": {"symbol": "XAUUSD"}
    },
    {
        "id": "sym_eurusd",
        "title": "Select Instrument: EURUSD (Euro / US Dollar)",
        "category": "INSTRUMENT",
        "icon": "&#128182;",
        "keywords": "euro eurusd forex fx",
        "action": {"symbol": "EURUSD"}
    },
    {
        "id": "sym_usdjpy",
        "title": "Select Instrument: USDJPY (US Dollar / Yen)",
        "category": "INSTRUMENT",
        "icon": "&#128180;",
        "keywords": "yen usdjpy forex fx japan",
        "action": {"symbol": "USDJPY"}
    },
    {
        "id": "sym_gbpusd",
        "title": "Select Instrument: GBPUSD (Pound / US Dollar)",
        "category": "INSTRUMENT",
        "icon": "&#128183;",
        "keywords": "pound gbpusd cable forex fx",
        "action": {"symbol": "GBPUSD"}
    },
    {
        "id": "sym_spx500",
        "title": "Select Instrument: SPX500 (S&P 500 Index)",
        "category": "INSTRUMENT",
        "icon": "&#127970;",
        "keywords": "spx500 sp500 equities indices us500",
        "action": {"symbol": "SPX500"}
    },
    {
        "id": "sym_nas100",
        "title": "Select Instrument: NAS100 (US Tech 100)",
        "category": "INSTRUMENT",
        "icon": "&#128187;",
        "keywords": "nas100 nasdaq tech equities indices",
        "action": {"symbol": "NAS100"}
    },
    {
        "id": "sym_btcusd",
        "title": "Select Instrument: BTCUSD (Bitcoin / US Dollar)",
        "category": "INSTRUMENT",
        "icon": "&#8383;",
        "keywords": "bitcoin btcusd crypto btc",
        "action": {"symbol": "BTCUSD"}
    },
    {
        "id": "sym_usoil",
        "title": "Select Instrument: USOIL (WTI Crude Oil)",
        "category": "INSTRUMENT",
        "icon": "&#128738;",
        "keywords": "oil usoil crude wti commodity energy",
        "action": {"symbol": "USOIL"}
    },

    # Utility Commands
    {
        "id": "util_shortcuts_help",
        "title": "Open Keyboard Shortcuts Help Reference",
        "category": "UTILITY",
        "icon": "&#9000;",
        "keywords": "keyboard shortcuts hotkeys help cheatsheet controls",
        "action": {"modal": "shortcuts_help"}
    },
    {
        "id": "util_toggle_compact",
        "title": "Toggle Compact Mode",
        "category": "UTILITY",
        "icon": "&#9881;",
        "keywords": "toggle compact density mode theme",
        "action": {"toggle": "compact_mode"}
    },
    {
        "id": "util_reset_prefs",
        "title": "Reset Terminal Preferences to Defaults",
        "category": "UTILITY",
        "icon": "&#128472;",
        "keywords": "reset defaults preferences settings factory",
        "action": {"reset_prefs": True}
    }
]


class CommandPaletteEngine:
    """
    Search and execution engine for terminal commands.
    """

    @classmethod
    def search_commands(cls, query: str = "") -> List[Dict[str, Any]]:
        """
        Filters commands by substring search across title, category, and keywords.
        """
        if not query or not query.strip():
            return list(COMMAND_REGISTRY)

        q = query.strip().lower()
        results = []
        for cmd in COMMAND_REGISTRY:
            t = cmd["title"].lower()
            c = cmd["category"].lower()
            k = cmd.get("keywords", "").lower()
            if q in t or q in c or q in k:
                results.append(cmd)
        return results

    @classmethod
    def execute_command(cls, cmd_id: str) -> bool:
        """
        Executes the specified command action by updating session state and user preferences.
        """
        cmd = next((c for c in COMMAND_REGISTRY if c["id"] == cmd_id), None)
        if not cmd:
            return False

        action = cmd.get("action", {})

        # 1. Navigation Action
        if "zone" in action:
            zone = action["zone"]
            st.session_state["active_zone"] = zone
            UserPreferencesManager.set_preference("last_active_zone", zone)
            if "subview" in action:
                subview = action["subview"]
                st.session_state[f"subview_{zone}"] = subview
                UserPreferencesManager.set_preference("last_active_subtab", subview)

        # 2. Workspace Layout Action
        if "layout" in action:
            layout = action["layout"]
            WorkspaceLayoutManager.set_active_layout(layout)

        # 3. Instrument Switch Action
        if "symbol" in action:
            sym = action["symbol"]
            st.session_state["active_ws_symbol"] = sym
            UserPreferencesManager.set_preference("selected_asset", sym)

        # 4. Modals and Utilities
        if "modal" in action:
            if action["modal"] == "shortcuts_help":
                st.session_state["show_shortcuts_modal"] = True

        if "toggle" in action:
            if action["toggle"] == "compact_mode":
                cur_compact = UserPreferencesManager.get_preference("compact_mode", False)
                UserPreferencesManager.set_preference("compact_mode", not cur_compact)

        if action.get("reset_prefs"):
            UserPreferencesManager.reset_to_defaults()

        return True


def render_command_palette_modal():
    """
    Renders the global command palette modal dialog.
    """
    if not st.session_state.get("show_command_palette", False):
        return

    ui_components.render_html("""
    <div style="background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(0, 255, 204, 0.4); border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; box-shadow: 0 8px 32px rgba(0,0,0,0.6);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 13px; font-weight: 800; color: #00ffcc; text-transform: uppercase; letter-spacing: 0.8px;">
                &#9000; GLOBAL COMMAND PALETTE (CTRL + K)
            </span>
            <span style="font-size: 10px; color: #8a99ad; font-family: monospace;">ESC TO CLOSE</span>
        </div>
    </div>
    """)

    with st.container(border=True):
        col_inp, col_cls = st.columns([5.0, 1.0])
        with col_inp:
            search_q = st.text_input(
                "Search Terminal Commands",
                placeholder="Type a command or keyword (e.g. 'scanner', 'gold', 'layout', 'journal')...",
                key="cmd_palette_search_input",
                label_visibility="collapsed"
            )
        with col_cls:
            if st.button("Close (Esc)", key="btn_close_cmd_palette", use_container_width=True):
                st.session_state["show_command_palette"] = False
                st.rerun()

        matched_cmds = CommandPaletteEngine.search_commands(search_q)

        if matched_cmds:
            cmd_options = [f"{c['icon']} [{c['category']}] {c['title']}" for c in matched_cmds]
            selected_cmd_idx = st.selectbox(
                "Matching Commands",
                range(len(matched_cmds)),
                format_func=lambda i: cmd_options[i],
                key="cmd_palette_select_box",
                label_visibility="collapsed"
            )

            col_btn1, col_btn2 = st.columns([2.5, 1.0])
            with col_btn1:
                target_cmd = matched_cmds[selected_cmd_idx]
                st.caption(f"Category: **{target_cmd['category']}** • ID: `{target_cmd['id']}`")
            with col_btn2:
                if st.button("EXECUTE COMMAND", key="btn_execute_selected_cmd", use_container_width=True, type="primary"):
                    CommandPaletteEngine.execute_command(target_cmd["id"])
                    st.session_state["show_command_palette"] = False
                    st.rerun()
        else:
            ui_components.render_empty_state("NO MATCHING COMMANDS", f"No terminal commands match '{search_q}'.", "INFO")
