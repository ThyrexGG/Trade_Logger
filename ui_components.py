# -*- coding: utf-8 -*-
"""
TradeLogger Professional Design System & UI Component Library (Phase 60 Refinement)
==================================================================================
Provides centralized design tokens, global stylesheet injection, standardized
15-state visual language, persistent global telemetry ribbon, and reusable
trading terminal component primitives for high-performance institutional UX.
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import textwrap

# -----------------------------------------------------------------------------
# 1. DESIGN TOKENS
# -----------------------------------------------------------------------------

TOKENS = {
    "colors": {
        "bg_app": "#0a0e17",
        "bg_panel": "#0f172a",
        "bg_elevated": "#1e293b",
        "bg_hover": "#27354f",
        "bg_active": "rgba(0, 255, 204, 0.08)",
        "border_subtle": "rgba(255, 255, 255, 0.08)",
        "border_card": "rgba(255, 255, 255, 0.12)",
        "border_accent": "rgba(0, 255, 204, 0.35)",
        "border_glow": "rgba(0, 255, 204, 0.25)",
        
        # Semantic Accents (Restrained & Institutional)
        "accent_primary": "#00ffcc",      # Teal / Cyan Accent
        "accent_secondary": "#00a3ff",    # Electric Blue Accent
        "accent_tertiary": "#bef264",     # Lime Accent
        "mode_paper": "#00d2ff",          # Paper Mode (Cyan)
        "mode_shadow": "#a855f7",         # Shadow Mode (Purple)
        "mode_live_blocked": "#ef4444",   # Live Safety Lock (Crimson Red)
        
        # Text Palette
        "text_primary": "#ffffff",
        "text_secondary": "#94a3b8",
        "text_muted": "#64748b",
        "text_highlight": "#e2e8f0",
        
        # State Colors
        "state_success": "#10b981",
        "state_warning": "#f59e0b",
        "state_error": "#ef4444",
        "state_info": "#3b82f6",
        "state_neutral": "#64748b",
    },
    "typography": {
        "font_family": "-apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        "font_mono": "'JetBrains Mono', 'Fira Code', 'Roboto Mono', Consolas, monospace",
        "size_hero": "1.75rem",
        "size_h1": "1.35rem",
        "size_h2": "1.10rem",
        "size_h3": "0.95rem",
        "size_body": "0.85rem",
        "size_caption": "0.75rem",
        "size_forensic": "0.70rem"
    },
    "spacing": {
        "xs": "4px",
        "sm": "8px",
        "md": "12px",
        "lg": "16px",
        "xl": "24px",
        "xxl": "32px"
    },
    "radii": {
        "sm": "4px",
        "md": "8px",
        "lg": "12px",
        "pill": "9999px"
    }
}

# -----------------------------------------------------------------------------
# 2. 15-STATE VISUAL LANGUAGE SPECIFICATION
# -----------------------------------------------------------------------------

STATES_SPEC: Dict[str, Dict[str, Any]] = {
    "SUCCESS": {
        "label": "SUCCESS",
        "icon": "&#10003;",
        "color": "#10b981",
        "bg": "rgba(16, 185, 129, 0.12)",
        "border": "rgba(16, 185, 129, 0.35)",
        "aria": "Operation successful",
        "severity": "NORMAL"
    },
    "WARNING": {
        "label": "WARNING",
        "icon": "&#9650;",
        "color": "#f59e0b",
        "bg": "rgba(245, 158, 11, 0.12)",
        "border": "rgba(245, 158, 11, 0.35)",
        "aria": "Attention required",
        "severity": "ELEVATED"
    },
    "ERROR": {
        "label": "ERROR",
        "icon": "&#10005;",
        "color": "#ef4444",
        "bg": "rgba(239, 68, 68, 0.12)",
        "border": "rgba(239, 68, 68, 0.35)",
        "aria": "Critical error",
        "severity": "HIGH"
    },
    "INFO": {
        "label": "INFO",
        "icon": "&#8505;",
        "color": "#3b82f6",
        "bg": "rgba(59, 130, 246, 0.12)",
        "border": "rgba(59, 130, 246, 0.35)",
        "aria": "Informational state",
        "severity": "LOW"
    },
    "NEUTRAL": {
        "label": "STANDBY",
        "icon": "&#9679;",
        "color": "#94a3b8",
        "bg": "rgba(148, 163, 184, 0.10)",
        "border": "rgba(148, 163, 184, 0.25)",
        "aria": "Neutral baseline standby",
        "severity": "NORMAL"
    },
    "NO_DATA": {
        "label": "NO DATA (N=0)",
        "icon": "&#9675;",
        "color": "#94a3b8",
        "bg": "rgba(148, 163, 184, 0.08)",
        "border": "rgba(148, 163, 184, 0.20)",
        "aria": "No observation recorded",
        "severity": "NORMAL"
    },
    "LOADING": {
        "label": "SYNCING",
        "icon": "&#8635;",
        "color": "#00ffcc",
        "bg": "rgba(0, 255, 204, 0.10)",
        "border": "rgba(0, 255, 204, 0.30)",
        "aria": "Synchronizing data",
        "severity": "NORMAL"
    },
    "DISCONNECTED": {
        "label": "DISCONNECTED",
        "icon": "&#9889;",
        "color": "#ef4444",
        "bg": "rgba(239, 68, 68, 0.15)",
        "border": "rgba(239, 68, 68, 0.40)",
        "aria": "Feed disconnected",
        "severity": "CRITICAL"
    },
    "STALE_DATA": {
        "label": "STALE DATA",
        "icon": "&#9201;",
        "color": "#f59e0b",
        "bg": "rgba(245, 158, 11, 0.12)",
        "border": "rgba(245, 158, 11, 0.35)",
        "aria": "Data feed is stale",
        "severity": "ELEVATED"
    },
    "REJECTED": {
        "label": "REJECTED",
        "icon": "&#8856;",
        "color": "#f43f5e",
        "bg": "rgba(244, 63, 94, 0.12)",
        "border": "rgba(244, 63, 94, 0.35)",
        "aria": "Signal or order rejected by risk gate",
        "severity": "ELEVATED"
    },
    "QUARANTINED": {
        "label": "QUARANTINED",
        "icon": "&#128737;",
        "color": "#f59e0b",
        "bg": "rgba(245, 158, 11, 0.15)",
        "border": "rgba(245, 158, 11, 0.40)",
        "aria": "Quarantined for manual audit",
        "severity": "HIGH"
    },
    "BLOCKED": {
        "label": "SAFETY BLOCKED",
        "icon": "&#128274;",
        "color": "#ef4444",
        "bg": "rgba(239, 68, 68, 0.15)",
        "border": "rgba(239, 68, 68, 0.40)",
        "aria": "Execution blocked by safety invariant",
        "severity": "CRITICAL"
    },
    "PAPER": {
        "label": "PAPER EXECUTION",
        "icon": "&#9672;",
        "color": "#00d2ff",
        "bg": "rgba(0, 210, 255, 0.12)",
        "border": "rgba(0, 210, 255, 0.35)",
        "aria": "Local paper execution mode",
        "severity": "NORMAL"
    },
    "SHADOW": {
        "label": "SHADOW EXECUTION",
        "icon": "&#9671;",
        "color": "#a855f7",
        "bg": "rgba(168, 85, 247, 0.12)",
        "border": "rgba(168, 85, 247, 0.35)",
        "aria": "Passive shadow logging mode",
        "severity": "NORMAL"
    },
    "LIVE_BLOCKED": {
        "label": "LIVE - BLOCKED &#128274;",
        "icon": "&#128274;",
        "color": "#ef4444",
        "bg": "rgba(239, 68, 68, 0.15)",
        "border": "rgba(239, 68, 68, 0.45)",
        "aria": "Live broker transmission is permanently blocked",
        "severity": "SAFETY_LOCK"
    }
}

# -----------------------------------------------------------------------------
# 3. GLOBAL CSS INJECTOR
# -----------------------------------------------------------------------------

def inject_global_design_system():
    """Injects centralized CSS tokens and styling into Streamlit DOM."""
    css = f"""
    <style>
    /* ==========================================================================
       TRADELOGGER PROFESSIONAL DESIGN SYSTEM (PHASE 60 REFINEMENT)
       ========================================================================== */
    
    :root {{
        --bg-app: {TOKENS['colors']['bg_app']};
        --bg-panel: {TOKENS['colors']['bg_panel']};
        --bg-elevated: {TOKENS['colors']['bg_elevated']};
        --bg-hover: {TOKENS['colors']['bg_hover']};
        --bg-active: {TOKENS['colors']['bg_active']};
        --border-subtle: {TOKENS['colors']['border_subtle']};
        --border-card: {TOKENS['colors']['border_card']};
        --border-accent: {TOKENS['colors']['border_accent']};
        --border-glow: {TOKENS['colors']['border_glow']};
        --accent-primary: {TOKENS['colors']['accent_primary']};
        --accent-secondary: {TOKENS['colors']['accent_secondary']};
        --accent-tertiary: {TOKENS['colors']['accent_tertiary']};
        --text-primary: {TOKENS['colors']['text_primary']};
        --text-secondary: {TOKENS['colors']['text_secondary']};
        --text-muted: {TOKENS['colors']['text_muted']};
        --font-mono: {TOKENS['typography']['font_mono']};
    }}

    /* Base Streamlit Overrides */
    .stApp {{
        background-color: var(--bg-app) !important;
        font-family: {TOKENS['typography']['font_family']} !important;
        color: var(--text-primary) !important;
    }}
    
    /* Hide Default Header Decoration */
    header[data-testid="stHeader"] {{
        background: rgba(10, 14, 23, 0.90) !important;
        backdrop-filter: blur(10px) !important;
        border-bottom: 1px solid var(--border-subtle) !important;
    }}
    
    /* Centralized Container Styling */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: var(--bg-panel) !important;
        border: 1px solid var(--border-card) !important;
        border-radius: {TOKENS['radii']['md']} !important;
        padding: 14px 16px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35) !important;
        transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
    }}
    
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        border-color: rgba(255, 255, 255, 0.20) !important;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.45) !important;
    }}

    /* Global Telemetry Ribbon */
    .tl-telemetry-ribbon {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.98) 0%, rgba(10, 14, 23, 0.98) 100%);
        border: 1px solid var(--border-accent);
        border-radius: {TOKENS['radii']['md']};
        padding: 8px 14px;
        margin-bottom: 12px;
        box-shadow: 0 4px 18px rgba(0, 255, 204, 0.10);
        flex-wrap: wrap;
        gap: 8px;
    }}

    .tl-telemetry-cluster {{
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }}

    .tl-telemetry-item {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 11.5px;
        font-family: var(--font-mono);
        color: var(--text-secondary);
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid var(--border-subtle);
        padding: 3px 8px;
        border-radius: 4px;
    }}

    .tl-telemetry-item b {{
        color: #ffffff;
        font-weight: 700;
    }}

    .tl-telemetry-price {{
        font-family: var(--font-mono);
        font-size: 13.5px;
        font-weight: 900;
        color: #00ffcc;
        letter-spacing: 0.5px;
        background: rgba(0, 255, 204, 0.08);
        border: 1px solid rgba(0, 255, 204, 0.25);
        padding: 2px 8px;
        border-radius: 4px;
    }}

    /* Standardized State Badges */
    .tl-badge {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 11px;
        font-family: var(--font-mono);
        font-weight: 800;
        letter-spacing: 0.4px;
        padding: 3px 9px;
        border-radius: 4px;
        text-transform: uppercase;
        line-height: 1.2;
    }}

    /* Standardized Metric Card */
    .tl-metric-card {{
        background: var(--bg-panel);
        border: 1px solid var(--border-card);
        border-radius: {TOKENS['radii']['md']};
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }}

    .tl-metric-card:hover {{
        border-color: var(--border-accent);
        transform: translateY(-1px);
    }}

    .tl-metric-title {{
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--text-muted);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}

    .tl-metric-value {{
        font-size: 1.35rem;
        font-weight: 900;
        font-family: var(--font-mono);
        color: #ffffff;
        letter-spacing: -0.5px;
    }}

    .tl-metric-sub {{
        font-size: 11px;
        color: var(--text-secondary);
    }}

    /* Standardized Section Header */
    .tl-section-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-top: 4px;
        margin-bottom: 12px;
        padding-bottom: 6px;
        border-bottom: 1px solid var(--border-subtle);
        flex-wrap: wrap;
        gap: 8px;
    }}

    .tl-section-title {{
        font-size: 1.15rem;
        font-weight: 900;
        color: #ffffff;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    .tl-section-sub {{
        font-size: 12px;
        color: var(--text-secondary);
        margin: 2px 0 0 0;
    }}

    /* Standardized Empty State */
    .tl-empty-state {{
        background: rgba(15, 23, 42, 0.7);
        border: 1px dashed rgba(255, 255, 255, 0.15);
        border-radius: {TOKENS['radii']['md']};
        padding: 32px 24px;
        text-align: center;
        margin: 12px 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
    }}

    .tl-empty-title {{
        font-size: 14px;
        font-weight: 800;
        color: #ffffff;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        margin: 0;
    }}

    .tl-empty-msg {{
        font-size: 12.5px;
        color: var(--text-secondary);
        max-width: 520px;
        line-height: 1.5;
        margin: 0;
    }}

    /* Navigation Zone Pills Customization */
    div[data-testid="stPills"] button {{
        font-size: 11.5px !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
        text-transform: uppercase !important;
        border-radius: 6px !important;
        padding: 6px 14px !important;
        transition: all 0.15s ease !important;
    }}

    /* Tables & Dataframes */
    div[data-testid="stDataFrame"] {{
        border: 1px solid var(--border-card) !important;
        border-radius: {TOKENS['radii']['md']} !important;
        overflow: hidden !important;
    }}

    /* Responsive Viewport Optimizations */
    @media (max-width: 1440px) {{
        .tl-telemetry-ribbon {{
            padding: 6px 10px;
            font-size: 11px;
        }}
        .tl-telemetry-item {{
            font-size: 10.5px;
            padding: 2px 6px;
        }}
        .tl-telemetry-price {{
            font-size: 12px;
        }}
    }}

    @media (max-width: 1280px) {{
        .tl-telemetry-ribbon {{
            flex-direction: column;
            align-items: flex-start;
            gap: 6px;
        }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 4. REUSABLE COMPONENT PRIMITIVES
# -----------------------------------------------------------------------------

def render_state_badge(state_key: str, custom_label: Optional[str] = None) -> str:
    """Returns HTML for a standardized 15-state badge with semantic color, icon, and accessible label."""
    spec = STATES_SPEC.get(state_key.upper(), STATES_SPEC["NEUTRAL"])
    lbl = custom_label or spec["label"]
    return f"""<span class="tl-badge" style="color:{spec['color']}; background:{spec['bg']}; border:1px solid {spec['border']};" title="{spec['aria']}">{spec['icon']} {lbl}</span>"""


def render_section_header(title: str, subtitle: Optional[str] = None, badge_state: Optional[str] = None, badge_label: Optional[str] = None):
    """Renders a standardized section header with optional state badge."""
    badge_html = f" {render_state_badge(badge_state, badge_label)}" if badge_state else ""
    sub_html = f'<p class="tl-section-sub">{subtitle}</p>' if subtitle else ""
    
    html = f"""
    <div class="tl-section-header">
        <div>
            <h3 class="tl-section-title">{title}{badge_html}</h3>
            {sub_html}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_metric_card(title: str, value: str, delta: Optional[str] = None, status_color: Optional[str] = None, subtitle: Optional[str] = None, badge_state: Optional[str] = None):
    """Renders a dark-glass KPI metric card."""
    val_color = status_color or "#ffffff"
    delta_html = f'<span style="font-size:11px; font-weight:700; color:{status_color or "#00ffcc"}; margin-left:6px;">{delta}</span>' if delta else ""
    badge_html = render_state_badge(badge_state) if badge_state else ""
    sub_html = f'<div class="tl-metric-sub">{subtitle}</div>' if subtitle else ""

    html = f"""
    <div class="tl-metric-card">
        <div class="tl-metric-title">
            <span>{title}</span>
            {badge_html}
        </div>
        <div class="tl-metric-value" style="color:{val_color};">
            {value}{delta_html}
        </div>
        {sub_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_empty_state(title: str, message: str, state_key: str = "NO_DATA", action_hint: Optional[str] = None):
    """Renders a standardized, intentional empty operational state (e.g. N=0 forward validation)."""
    badge_html = render_state_badge(state_key)
    hint_html = f'<div style="font-size:11px; font-family:monospace; color:#00ffcc; margin-top:4px;">{action_hint}</div>' if action_hint else ""
    
    html = f"""
    <div class="tl-empty-state">
        <div style="margin-bottom:4px;">{badge_html}</div>
        <h4 class="tl-empty-title">{title}</h4>
        <p class="tl-empty-msg">{message}</p>
        {hint_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_global_telemetry_ribbon(
    symbol: str = "XAUUSD",
    price: Optional[float] = None,
    timeframe: str = "15m",
    session_name: str = "LONDON / NY OVERLAP",
    data_health: str = "HEALTHY",
    exec_mode: str = "PAPER",
    system_health: str = "NORMAL",
    live_blocked: bool = True,
    spread_pips: Optional[float] = None
):
    """
    Renders the persistent top telemetry ribbon across all zones.
    Communicates at a glance: Symbol, Price, Timeframe, Session, Spread, Data Health, Execution Mode, System Health, and Safety Lock.
    """
    if price and price > 0:
        if symbol in ["XAUUSD", "USOIL", "BTCUSD", "NAS100", "SPX500", "US30"]:
            price_disp = f"${price:,.2f}"
        else:
            price_disp = f"{price:,.4f}"
    else:
        price_disp = "DATA UNAVAILABLE"
    
    # Data Health Badge
    health_upper = str(data_health).upper()
    if health_upper in ["HEALTHY", "LIVE", "CONNECTED"]:
        dh_badge = render_state_badge("SUCCESS", "DATA HEALTHY")
    elif health_upper in ["STALE", "DEGRADED"]:
        dh_badge = render_state_badge("STALE_DATA")
    else:
        dh_badge = render_state_badge("DISCONNECTED")

    # Mode Badge
    if exec_mode.upper() == "SHADOW":
        mode_badge = render_state_badge("SHADOW")
    else:
        mode_badge = render_state_badge("PAPER")

    # Safety Lock Badge (Always enforced fail-closed)
    safety_badge = render_state_badge("LIVE_BLOCKED")

    # System Health Badge
    if system_health.upper() in ["HEALTHY", "NORMAL"]:
        sys_badge = render_state_badge("SUCCESS", "SYS HEALTHY")
    else:
        sys_badge = render_state_badge("WARNING", f"SYS {system_health}")

    # Optional spread
    spread_html = f'<span class="tl-telemetry-item"><b>SPREAD:</b> {spread_pips:.1f}p</span>' if spread_pips is not None else ""

    html = f"""
    <div class="tl-telemetry-ribbon">
        <div class="tl-telemetry-cluster">
            <span class="tl-telemetry-item"><b>ASSET:</b> <span style="color:#ffffff;">{symbol}</span></span>
            <span class="tl-telemetry-price">{price_disp}</span>
            {spread_html}
            <span class="tl-telemetry-item"><b>TF:</b> {timeframe}</span>
            <span class="tl-telemetry-item"><b>SESSION:</b> {session_name}</span>
            {dh_badge}
        </div>
        <div class="tl-telemetry-cluster">
            <span class="tl-telemetry-item"><b>MODE:</b> {mode_badge}</span>
            {sys_badge}
            {safety_badge}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_safety_banner():
    """
    Renders permanent, unambiguous safety disclaimer for all execution panels.
    Confirms LIVE_AUTOMATION_ENABLED = False and LIVE_BROKER_TRANSMISSION = 'BLOCKED'.
    """
    html = """
    <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.35); border-left: 4px solid #ef4444; border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 14px;">&#128274;</span>
            <span style="font-size: 11.5px; font-weight: 700; color: #ffffff; letter-spacing: 0.3px;">
                SAFETY GATE ENFORCED: <span style="color: #ef4444;">LIVE BROKER TRANSMISSION IS PERMANENTLY BLOCKED</span>
            </span>
        </div>
        <div style="font-size: 11px; font-family: monospace; color: #94a3b8;">
            AUTOMATION = OFF &#8226; SHADOW/PAPER ONLY
        </div>
    </div>
    """
    render_html(html)


def clean_html(html_content: str) -> str:
    """
    Normalizes multiline HTML strings so markdown-it never parses indented
    lines as <pre><code> blocks.

    textwrap.dedent() alone is insufficient here: several widgets interpolate an
    already-indented fragment (e.g. items_html) into another indented f-string,
    leaving nested lines with 4+ leading spaces after the common prefix is
    removed. markdown-it then renders those lines verbatim. Stripping the leading
    whitespace from every line removes the ambiguity; inter-tag indentation is
    insignificant in HTML and none of these templates are whitespace-sensitive
    (no <pre> / white-space: pre content).
    """
    import textwrap
    dedented = textwrap.dedent(html_content).strip()
    lines = [ln.strip() for ln in dedented.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def render_html(html_content: str):
    """
    Renders raw HTML via st.markdown with strict unindentation / dedent
    so that indented python multiline strings are never parsed as markdown code blocks.
    """
    st.markdown(clean_html(html_content), unsafe_allow_html=True)
