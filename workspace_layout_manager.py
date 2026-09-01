# -*- coding: utf-8 -*-
"""
TradeLogger Workspace Layout Manager (Phase 61)
===============================================
Provides 4 user-configurable workspace layout modes for the Trading Workspace Cockpit:
1. DEFAULT: Watchlist (1.1) | Chart (3.4) | Execution (1.5) -> Active Positions -> Market Context
2. RESEARCH: Asset Context & Edge (2.0) | Chart (3.0) -> Macro / Regime Intelligence -> Research Data
3. COMPACT: High-density 4-column layout minimizing vertical footprint
4. ANALYSIS: Dominant Chart (4.0) -> MTF Bias -> Asset Edge Scorecard -> Macro -> Correlations

Strict Invariant:
Switching workspace layouts changes ONLY visual arrangement; zero underlying calculations or safety checks are modified.
"""

from typing import Dict, List, Any
import streamlit as st
import ui_components
from user_preferences import UserPreferencesManager

WORKSPACE_LAYOUTS: Dict[str, Dict[str, Any]] = {
    "DEFAULT": {
        "name": "Standard Cockpit",
        "description": "Balanced 3-column trading cockpit with watchlist, dominant chart, and execution panel.",
        "icon": "&#9638;",
        "columns": [1.1, 3.4, 1.5]
    },
    "RESEARCH": {
        "name": "Research Focus",
        "description": "Multi-factor context and fundamental driver analysis paired with chart.",
        "icon": "&#128300;",
        "columns": [2.0, 3.0]
    },
    "COMPACT": {
        "name": "Compact Density",
        "description": "Maximum information density with scaled down cards and docked trays.",
        "icon": "&#9636;",
        "columns": [1.0, 2.8, 1.2]
    },
    "ANALYSIS": {
        "name": "Technical & Macro Analysis",
        "description": "Dominant full-width chart canvas with contextual multi-factor sub-panels.",
        "icon": "&#128200;",
        "columns": [1.0]
    }
}


class WorkspaceLayoutManager:
    """
    Manages active workspace layout state and layout selector UI.
    """

    @classmethod
    def get_active_layout(cls) -> str:
        """
        Retrieves active layout key from session_state or preferences.
        """
        if "active_workspace_layout" not in st.session_state:
            st.session_state["active_workspace_layout"] = UserPreferencesManager.get_preference("active_workspace_layout", "DEFAULT")
        return st.session_state.get("active_workspace_layout", "DEFAULT")

    @classmethod
    def set_active_layout(cls, layout_key: str) -> None:
        """
        Sets active layout and persists preference.
        """
        if layout_key in WORKSPACE_LAYOUTS:
            st.session_state["active_workspace_layout"] = layout_key
            UserPreferencesManager.set_preference("active_workspace_layout", layout_key)

    @classmethod
    def render_layout_switcher(cls) -> str:
        """
        Renders clean pill switcher for workspace layouts.
        """
        current_layout = cls.get_active_layout()
        layout_keys = list(WORKSPACE_LAYOUTS.keys())
        
        ui_components.render_html("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-size: 10.5px; font-weight: 800; color: #8a99ad; text-transform: uppercase; letter-spacing: 0.5px;">
                WORKSPACE LAYOUT:
            </span>
        </div>
        """)

        if hasattr(st, "pills"):
            selected = st.pills(
                "Workspace Layout",
                options=layout_keys,
                default=current_layout,
                key="workspace_layout_pills",
                label_visibility="collapsed"
            )
            if selected and selected != current_layout:
                cls.set_active_layout(selected)
                st.rerun()
                return selected
        else:
            selected = st.selectbox(
                "Workspace Layout",
                options=layout_keys,
                index=layout_keys.index(current_layout),
                key="workspace_layout_sel",
                label_visibility="collapsed"
            )
            if selected != current_layout:
                cls.set_active_layout(selected)
                st.rerun()
                return selected

        return current_layout
