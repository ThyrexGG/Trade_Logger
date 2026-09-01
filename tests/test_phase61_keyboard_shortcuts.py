# -*- coding: utf-8 -*-
"""
Phase 61 - Test Keyboard Shortcut Catalog, JS Listener & Exclusion Logic
"""
import pytest
import streamlit as st
from keyboard_shortcuts import SHORTCUTS_CATALOG, inject_keyboard_shortcuts_listener, render_keyboard_shortcut_reference_modal


def test_shortcuts_catalog_structure():
    """Verify that keyboard shortcut catalog contains essential terminal shortcuts."""
    assert len(SHORTCUTS_CATALOG) >= 10
    keys = [s["key"] for s in SHORTCUTS_CATALOG]
    assert "Ctrl + K" in keys
    assert "Esc" in keys
    assert "1" in keys
    assert "2" in keys
    assert "3" in keys
    assert "4" in keys
    assert "W" in keys
    assert "C" in keys
    assert "E" in keys
    assert "?" in keys


def test_inject_keyboard_shortcuts_listener_markup(monkeypatch):
    """Verify that JS script markup contains input/textarea form exclusion check."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)

    monkeypatch.setattr(st, "markdown", fake_markdown)
    inject_keyboard_shortcuts_listener()

    assert len(called) >= 1
    script_str = "".join(called)
    assert "INPUT" in script_str
    assert "TEXTAREA" in script_str
    assert "SELECT" in script_str
    assert "isContentEditable" in script_str
    assert "addEventListener('keydown'" in script_str
