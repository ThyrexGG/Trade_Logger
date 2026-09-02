# -*- coding: utf-8 -*-
"""
TradeLogger User Preferences Engine (Phase 61 / Fast Terminal Architecture)
===========================================================================
Provides lightweight, reliable, high-speed user preference management.
Features thread-safe process-level caching for sub-millisecond API reads,
Streamlit session_state synchronization, and database persistence (SQLite / PostgreSQL).

Strict Safety Invariants:
- NEVER stores credentials, API keys, or broker secrets.
- NEVER modifies historical research datasets or baseline constants.
- Strictly isolated from order execution and risk gateway logic.
"""

import sqlite3
import json
import threading
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

# Process-level thread-safe in-memory cache for sub-millisecond reads
_PREFERENCES_CACHE: Optional[Dict[str, Any]] = None
_PREFERENCES_LOCK = threading.Lock()


def _ensure_preferences_table(conn=None):
    """Ensures preferences table exists in SQLite or PostgreSQL."""
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
    Manages user preferences with process-level caching and database persistence.
    """

    @classmethod
    def initialize_preferences(cls, force_reload: bool = False) -> Dict[str, Any]:
        """
        Initializes preferences with process-level caching and Streamlit session_state sync.
        """
        global _PREFERENCES_CACHE
        with _PREFERENCES_LOCK:
            if _PREFERENCES_CACHE is not None and not force_reload:
                try:
                    if "user_preferences" not in st.session_state:
                        st.session_state["user_preferences"] = dict(_PREFERENCES_CACHE)
                except Exception:
                    pass
                return dict(_PREFERENCES_CACHE)

            # Cold load from DB
            _ensure_preferences_table()
            prefs = dict(DEFAULT_PREFERENCES)
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

            _PREFERENCES_CACHE = dict(prefs)
            try:
                st.session_state["user_preferences"] = prefs
            except Exception:
                pass
            return dict(_PREFERENCES_CACHE)

    @classmethod
    def get_preference(cls, key: str, default: Any = None) -> Any:
        """
        Retrieves a user preference from cache.
        """
        prefs = cls.initialize_preferences()
        return prefs.get(key, DEFAULT_PREFERENCES.get(key, default))

    @classmethod
    def set_preference(cls, key: str, value: Any, persist_to_db: bool = True) -> None:
        """
        Sets a user preference in memory cache and optionally persists to SQLite/PostgreSQL.
        """
        global _PREFERENCES_CACHE
        with _PREFERENCES_LOCK:
            if _PREFERENCES_CACHE is None:
                cls.initialize_preferences()
            _PREFERENCES_CACHE[key] = value

        try:
            if "user_preferences" in st.session_state:
                st.session_state["user_preferences"][key] = value
        except Exception:
            pass

        if persist_to_db:
            try:
                from datetime import datetime, timezone
                conn = database.get_connection()
                cur = conn.cursor()
                val_json = json.dumps(value)
                now_iso = datetime.now(timezone.utc).isoformat()
                placeholder = database.get_sql_placeholder(conn)
                if database.is_postgres():
                    cur.execute(
                        f"""
                        INSERT INTO user_terminal_preferences (pref_key, pref_value, updated_at)
                        VALUES ({placeholder}, {placeholder}, {placeholder})
                        ON CONFLICT (pref_key) DO UPDATE SET pref_value = EXCLUDED.pref_value, updated_at = EXCLUDED.updated_at
                        """,
                        (key, val_json, now_iso)
                    )
                else:
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
        Returns all active preferences from process cache.
        """
        return dict(cls.initialize_preferences())

    @classmethod
    def reset_to_defaults(cls) -> Dict[str, Any]:
        """
        Resets all preferences to factory defaults in cache and DB.
        """
        global _PREFERENCES_CACHE
        with _PREFERENCES_LOCK:
            _PREFERENCES_CACHE = dict(DEFAULT_PREFERENCES)

        try:
            st.session_state["user_preferences"] = dict(DEFAULT_PREFERENCES)
        except Exception:
            pass

        try:
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM user_terminal_preferences")
            conn.commit()
            conn.close()
        except Exception:
            pass
        return dict(DEFAULT_PREFERENCES)

    @classmethod
    def invalidate_cache(cls) -> None:
        """
        Explicitly invalidates process cache forcing database reload on next read.
        """
        global _PREFERENCES_CACHE
        with _PREFERENCES_LOCK:
            _PREFERENCES_CACHE = None
