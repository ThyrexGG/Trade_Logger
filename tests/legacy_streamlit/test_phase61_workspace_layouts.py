# -*- coding: utf-8 -*-
"""
Phase 61 - Test Workspace Layout Modes (Default, Research, Compact, Analysis)
"""
import pytest
import streamlit as st
from workspace_layout_manager import WorkspaceLayoutManager, WORKSPACE_LAYOUTS


def test_workspace_layouts_catalog():
    """Verify that all 4 supported workspace layout modes exist with definitions."""
    assert "DEFAULT" in WORKSPACE_LAYOUTS
    assert "RESEARCH" in WORKSPACE_LAYOUTS
    assert "COMPACT" in WORKSPACE_LAYOUTS
    assert "ANALYSIS" in WORKSPACE_LAYOUTS

    for k, lay in WORKSPACE_LAYOUTS.items():
        assert "name" in lay
        assert "description" in lay
        assert "columns" in lay


def test_workspace_layout_state_switching():
    """Verify layout state management."""
    WorkspaceLayoutManager.set_active_layout("COMPACT")
    assert WorkspaceLayoutManager.get_active_layout() == "COMPACT"

    WorkspaceLayoutManager.set_active_layout("ANALYSIS")
    assert WorkspaceLayoutManager.get_active_layout() == "ANALYSIS"

    WorkspaceLayoutManager.set_active_layout("DEFAULT")
    assert WorkspaceLayoutManager.get_active_layout() == "DEFAULT"
