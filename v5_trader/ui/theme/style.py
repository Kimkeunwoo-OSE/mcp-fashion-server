"""Theme utilities for Streamlit UI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import streamlit as st


def load_theme() -> Dict[str, str]:
    config_path = Path(__file__).resolve().parents[2] / "config" / "theme.json"
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def apply_theme() -> None:
    theme = load_theme()
    css = f"""
    <style>
    body {{
        background-color: {theme['background']} !important;
        font-family: {theme['font_family']};
    }}
    .block-container {{
        padding-top: 2rem;
    }}
    div[data-testid="stSidebar"] {{
        background: linear-gradient(135deg, {theme['surface']}, rgba(0,0,0,0.5));
    }}
    .glass-card {{
        background: {theme['surface']};
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 18px 40px rgba(0, 0, 0, 0.35);
        color: {theme['text_primary']};
    }}
    .metric-label {{
        color: {theme['accent_mint']};
        font-weight: 600;
    }}
    .metric-value {{
        font-size: 2rem;
        color: {theme['accent_coral']};
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
