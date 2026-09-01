# -*- coding: utf-8 -*-
"""
TradeLogger User Preferences Engine (Phase 61)
==============================================
Provides lightweight, reliable user preference management across terminal sessions.
Preferences persist in Streamlit session_state and optionally in SQLite user_terminal_preferences.

Strict Safety Invariants:
- NEVER stores credentials, API keys, or broker secrets.
- NEVER modifies historical research datasets or baseline constants.
- Strictly isolated from order execution and risk gateway logic.
"""

import sqlite3
import json
from typing import Dict, Any, Optional
import streamlit as st
import database

DEFAULT_PREFERENCES: Dict[str, Any] = {
    "selected_asset": "XAUUSD",
    "selected_timeframe": "15m",
    "active_workspace_layout": "DEFAULT",
    "watchlist_filter": "ALL",
    "compact_mode": False,
    "shortcuts_enabled": True,
    "last_active_zone": "TRADING WORKSPACE",
    "last_active_subtab": "CHARTS & WORKSPACE"
}


def _ensure_preferences_table(conn=None):
    """Ensures SQLite preferences table exists."""
    should_close = False
    if conn is None:
        conn = database.get_connection()
        should_close = True
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_terminal_preferences (
            pref_key TEXT PRIMARY KEY,
            pref_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        if should_close:
            conn.close()


class UserPreferencesManager:
    """
    Manages user preferences with session_state caching and SQLite persistence.
    """

    @classmethod
    def initialize_preferences(cls) -> Dict[str, Any]:
        """
        Initializes preferences in session state from SQLite defaults.
        """
        _ensure_preferences_table()
        if "user_preferences" not in st.session_state:
            prefs = dict(DEFAULT_PREFERENCES)
            # Load from DB if available
            try:
                conn = database.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT pref_key, pref_value FROM user_terminal_preferences")
                rows = cur.fetchall()
                conn.close()
                for k, v in rows:
                    try:
                        prefs[k] = json.loads(v)
                    except Exception:
                        prefs[k] = v
            except Exception:
                pass
            st.session_state["user_preferences"] = prefs
        return st.session_state["user_preferences"]

    @classmethod
    def get_preference(cls, key: str, default: Any = None) -> Any:
        """
        Retrieves a user preference.
        """
        prefs = cls.initialize_preferences()
        return prefs.get(key, DEFAULT_PREFERENCES.get(key, default))

    @classmethod
    def set_preference(cls, key: str, value: Any, persist_to_db: bool = True) -> None:
        """
        Sets a user preference and optionally persists to SQLite.
        """
        prefs = cls.initialize_preferences()
        prefs[key] = value
        st.session_state["user_preferences"] = prefs

        if persist_to_db:
            try:
                from datetime import datetime, timezone
                conn = database.get_connection()
                cur = conn.cursor()
                val_json = json.dumps(value)
                now_iso = datetime.now(timezone.utc).isoformat()
                placeholder = database.get_sql_placeholder(conn)
                cur.execute(
                    f"INSERT OR REPLACE INTO user_terminal_preferences (pref_key, pref_value, updated_at) VALUES ({placeholder}, {placeholder}, {placeholder})",
                    (key, val_json, now_iso)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

    @classmethod
    def get_all_preferences(cls) -> Dict[str, Any]:
        """
        Returns all active preferences.
        """
        return dict(cls.initialize_preferences())

    @classmethod
    def reset_to_defaults(cls) -> Dict[str, Any]:
        """
        Resets all preferences to factory defaults.
        """
        st.session_state["user_preferences"] = dict(DEFAULT_PREFERENCES)
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM user_terminal_preferences")
            conn.commit()
            conn.close()
        except Exception:
            pass
        return dict(DEFAULT_PREFERENCES)
