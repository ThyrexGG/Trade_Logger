# -*- coding: utf-8 -*-
"""
Legacy Streamlit-terminal tests.

The Streamlit UI (`app.py` + `ui_components.py`, `tradingview_widget.py`,
`command_palette.py`, `keyboard_shortcuts.py`, `workspace_layout_manager.py`,
`market_intelligence_ui.py`, `asset_edge_scorecard.py`,
`forward_evidence_cockpit.py`) is retired (platform plan D1). The React SPA +
FastAPI backend replace it, and `streamlit` is no longer a shipped dependency
(see `requirements-streamlit-legacy.txt`).

These tests still pass for anyone who installs the legacy extra
(`pip install -r requirements-streamlit-legacy.txt`). When `streamlit` is not
importable — the default, and every deploy/CI run — the whole directory is
skipped at collection time.
"""
import importlib.util

if importlib.util.find_spec("streamlit") is None:  # pragma: no cover
    collect_ignore_glob = ["*.py"]
