"""Streamlit entry point for the v5 Trader application."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import streamlit as st

from v5_trader.core.data_engine.database import DatabaseManager, init_database
from v5_trader.core.data_engine.market_data import MarketDataService
from v5_trader.core.strategy_v5.engine import StrategyEngine
from v5_trader.core.utils.config import Settings, load_settings
from v5_trader.ui.main_window.layout import render_main_app
from v5_trader.ui.theme.style import apply_theme


@st.cache_resource(show_spinner=False)
def get_settings() -> Settings:
    return load_settings()


@st.cache_resource(show_spinner=False)
def get_database(settings: Settings) -> DatabaseManager:
    init_database(settings)
    return DatabaseManager(settings)


@st.cache_resource(show_spinner=False)
def get_market_service(settings: Settings) -> MarketDataService:
    return MarketDataService(settings)


@st.cache_resource(show_spinner=False)
def get_strategy_engine(settings: Settings, market: MarketDataService, db: DatabaseManager) -> StrategyEngine:
    return StrategyEngine(settings, market, db)


def main() -> None:
    st.set_page_config(page_title="v5 Trader", layout="wide")
    apply_theme()
    settings = get_settings()
    db = get_database(settings)
    market = get_market_service(settings)
    engine = get_strategy_engine(settings, market, db)

    st.title("v5 Trader")
    st.caption("Fully local AI-assisted trading companion")
    render_main_app(settings, engine, market, db)


if __name__ == "__main__":
    main()
