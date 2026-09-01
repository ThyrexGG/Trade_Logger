# -*- coding: utf-8 -*-
"""
Phase 61 - Test Global Command Palette (Ctrl+K), Search & Command Execution Dispatch
"""
import pytest
import streamlit as st
from command_palette import CommandPaletteEngine, COMMAND_REGISTRY


def test_command_registry_completeness():
    """Verify that command registry contains categorized navigation, layout, instrument, and utility commands."""
    assert len(COMMAND_REGISTRY) >= 20
    categories = set(c["category"] for c in COMMAND_REGISTRY)
    assert "NAVIGATION" in categories
    assert "WORKSPACE LAYOUT" in categories
    assert "INSTRUMENT" in categories
    assert "UTILITY" in categories

    for cmd in COMMAND_REGISTRY:
        assert "id" in cmd
        assert "title" in cmd
        assert "category" in cmd
        assert "action" in cmd


def test_command_palette_search():
    """Verify fuzzy/substring search for commands."""
    all_cmds = CommandPaletteEngine.search_commands("")
    assert len(all_cmds) == len(COMMAND_REGISTRY)

    gold_cmds = CommandPaletteEngine.search_commands("gold")
    assert len(gold_cmds) >= 1
    assert any("XAUUSD" in c["title"] or "Gold" in c["title"] for c in gold_cmds)

    layout_cmds = CommandPaletteEngine.search_commands("layout")
    assert len(layout_cmds) >= 4


def test_command_execution_dispatch():
    """Verify that command execution properly mutates session state and user preferences."""
    # Test navigation command
    res = CommandPaletteEngine.execute_command("nav_research_lab")
    assert res is True
    assert st.session_state.get("active_zone") == "RESEARCH & STRATEGY LAB"

    # Test layout command
    res = CommandPaletteEngine.execute_command("layout_research")
    assert res is True
    assert st.session_state.get("active_workspace_layout") == "RESEARCH"

    # Test symbol switch
    res = CommandPaletteEngine.execute_command("sym_usdjpy")
    assert res is True
    assert st.session_state.get("active_ws_symbol") == "USDJPY"
