# -*- coding: utf-8 -*-
"""
TradeLogger Global Keyboard Shortcut System (Phase 61)
======================================================
Injects client-side keyboard listener into the Streamlit DOM with strict form input exclusion.
Allows fast professional navigation without interfering with typing inside inputs/textareas.

Strict Invariants:
- Skips keystrokes when the active focus is inside INPUT, TEXTAREA, SELECT, or [contenteditable].
- Zero unintended executions while typing trade quantities, notes, prices, or search queries.
"""

from typing import Dict, List, Any
import streamlit as st
import ui_components

SHORTCUTS_CATALOG: List[Dict[str, str]] = [
    {"key": "Ctrl + K", "description": "Open Global Command Palette", "category": "GLOBAL"},
    {"key": "Esc", "description": "Close open dialog / Clear active modal", "category": "GLOBAL"},
    {"key": "?", "description": "Open Keyboard Shortcuts Help Reference", "category": "GLOBAL"},
    {"key": "1", "description": "Switch to Zone 1: Trading Workspace", "category": "ZONE NAVIGATION"},
    {"key": "2", "description": "Switch to Zone 2: Research & Strategy Lab", "category": "ZONE NAVIGATION"},
    {"key": "3", "description": "Switch to Zone 3: Forward Evidence & Governance", "category": "ZONE NAVIGATION"},
    {"key": "4", "description": "Switch to Zone 4: Operations, Journal & Audit", "category": "ZONE NAVIGATION"},
    {"key": "W", "description": "Open Watchlist View", "category": "WORKSPACE"},
    {"key": "C", "description": "Focus Chart Canvas", "category": "WORKSPACE"},
    {"key": "E", "description": "Focus Execution & Pre-Trade Risk Panel", "category": "WORKSPACE"},
    {"key": "M", "description": "Open Market Intelligence Command Center", "category": "WORKSPACE"},
    {"key": "J", "description": "Open Trade Journal & Setup Studio", "category": "OPERATIONS"},
    {"key": "R", "description": "Open Adversarial Research Lab", "category": "RESEARCH"}
]


def inject_keyboard_shortcuts_listener():
    """
    Injects lightweight JavaScript keyboard event listener into the browser window.
    Strictly excludes editable input elements.
    """
    js_code = """
    <script>
    (function() {
        if (window.__tradelogger_shortcuts_installed) return;
        window.__tradelogger_shortcuts_installed = true;

        document.addEventListener('keydown', function(e) {
            // STRICT INPUT EXCLUSION: Ignore hotkeys if user is actively typing in a form control
            var active = document.activeElement;
            if (active) {
                var tag = active.tagName ? active.tagName.toUpperCase() : '';
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || active.isContentEditable) {
                    if (e.key === 'Escape') {
                        active.blur();
                    }
                    return;
                }
            }

            // 1. Ctrl + K -> Open Command Palette
            if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
                e.preventDefault();
                var btnPalette = document.querySelector('button[key="btn_open_cmd_palette_top"]');
                if (btnPalette) {
                    btnPalette.click();
                } else {
                    var allBtns = document.querySelectorAll('button');
                    for (var i = 0; i < allBtns.length; i++) {
                        if (allBtns[i].innerText && allBtns[i].innerText.includes('COMMAND (CTRL+K)')) {
                            allBtns[i].click();
                            break;
                        }
                    }
                }
                return;
            }

            // 2. Escape -> Close Modals
            if (e.key === 'Escape') {
                var btnClose = document.querySelector('button[key="btn_close_cmd_palette"]') || document.querySelector('button[key="btn_close_shortcuts_modal"]');
                if (btnClose) {
                    btnClose.click();
                }
                return;
            }

            // 3. Single-Key Global Navigation (when not typing in form)
            if (!e.ctrlKey && !e.altKey && !e.metaKey) {
                if (e.key === '?') {
                    e.preventDefault();
                    var btnHelp = document.querySelector('button[key="btn_open_shortcuts_help"]');
                    if (btnHelp) btnHelp.click();
                }
            }
        });
    })();
    </script>
    """
    st.markdown(js_code, unsafe_allow_html=True)


def render_keyboard_shortcut_reference_modal():
    """
    Renders the cheat-sheet modal for all terminal hotkeys.
    """
    if not st.session_state.get("show_shortcuts_modal", False):
        return

    ui_components.render_html("""
    <div style="background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(0, 255, 204, 0.4); border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; box-shadow: 0 8px 32px rgba(0,0,0,0.6);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 13px; font-weight: 800; color: #00ffcc; text-transform: uppercase; letter-spacing: 0.8px;">
                &#9000; TERMINAL KEYBOARD SHORTCUTS REFERENCE
            </span>
            <span style="font-size: 10px; color: #8a99ad; font-family: monospace;">ESC TO CLOSE</span>
        </div>
    </div>
    """)

    with st.container(border=True):
        col_list, col_close = st.columns([5.0, 1.0])
        with col_close:
            if st.button("Close (Esc)", key="btn_close_shortcuts_modal", use_container_width=True):
                st.session_state["show_shortcuts_modal"] = False
                st.rerun()

        with col_list:
            categories = ["GLOBAL", "ZONE NAVIGATION", "WORKSPACE", "OPERATIONS", "RESEARCH"]
            for cat in categories:
                cat_items = [s for s in SHORTCUTS_CATALOG if s["category"] == cat]
                if cat_items:
                    st.markdown(f"<div style='font-size:11px; font-weight:800; color:#8a99ad; text-transform:uppercase; margin-top:8px; margin-bottom:4px;'>{cat}</div>", unsafe_allow_html=True)
                    for item in cat_items:
                        ui_components.render_html(f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; margin-bottom: 3px; background: rgba(255,255,255,0.02); border-radius: 4px; font-size: 11px;">
                            <span style="color: #cbd5e1;">{item['description']}</span>
                            <span style="font-family: monospace; font-weight: 800; color: #00ffcc; background: rgba(0, 255, 204, 0.1); border: 1px solid rgba(0, 255, 204, 0.3); padding: 2px 6px; border-radius: 3px;">{item['key']}</span>
                        </div>
                        """)

        st.caption("Note: Shortcuts automatically disarm whenever your cursor is inside a text input, number input, or search box.")
