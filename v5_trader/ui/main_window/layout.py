"""Streamlit layout helpers for the v5 Trader UI."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from v5_trader.core.alert_manager.manager import AlertManager
from v5_trader.core.data_engine.database import DatabaseManager
from v5_trader.core.data_engine.market_data import MarketDataService
from v5_trader.core.strategy_v5.engine import StrategyEngine
from v5_trader.core.utils.config import Settings
from v5_trader.plugins.ai_sell_advisor.advisor import AISellAdvisor
from v5_trader.plugins.news_analyzer.analyzer import NewsAnalyzer, NewsHeadline
from v5_trader.plugins.statistics_dashboard.dashboard import StatisticsDashboard
from v5_trader.ui.chart_panel.plotter import plot_price_chart
from v5_trader.ui.order_panel.form import render_order_form


def render_recommend_tab(
    *,
    engine: StrategyEngine,
    market: MarketDataService,
    advisor: AISellAdvisor,
    alert_manager: AlertManager,
) -> None:
    """Display strategy outputs with contextual guidance and charts."""
    st.subheader("Next-Day Surge Recommendations")
    results = engine.run_batch()
    if not results:
        st.info("No recommendations available.")
        return
    for result in results:
        with st.container():
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown(f"### {result.symbol}")
            st.metric("Surge Probability", f"{result.surge_probability:.1%}")
            st.metric("Target Price", f"{result.target_price:,.2f}")
            candles = market.fetch_daily_candles(result.symbol, engine.settings.strategy.lookback_days)
            latest_price = candles[-1].close if candles else result.target_price
            advice = advisor.recommend(symbol=result.symbol, surge_probability=result.surge_probability, current_price=latest_price)
            st.write(advice.rationale)
            st.write(f"Suggested sell target: **{advice.suggested_price:,.2f}**")
            if result.surge_probability >= engine.settings.alerts.surge_threshold:
                alert_manager.dispatch(result)
            st.plotly_chart(plot_price_chart(candles, title=result.symbol), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)


def render_holdings_tab(db: DatabaseManager) -> None:
    """Render the holdings table using snapshots from the database."""

    st.subheader("Holdings Snapshot")
    holdings = db.list_holdings()
    if not holdings:
        st.info("No holdings recorded yet.")
        return
    df = pd.DataFrame(
        [
            {
                "Symbol": h.symbol,
                "Quantity": h.quantity,
                "Avg Price": h.average_price,
                "Last Updated": h.last_updated,
            }
            for h in holdings
        ]
    )
    st.dataframe(df, use_container_width=True)


def render_orders_tab(db: DatabaseManager) -> None:
    """Allow manual order capture and display the audit log."""

    render_order_form(db)
    orders = db.list_orders()
    if orders:
        df = pd.DataFrame(
            [
                {
                    "Symbol": o.symbol,
                    "Side": o.side,
                    "Quantity": o.quantity,
                    "Price": o.price,
                    "Timestamp": o.timestamp,
                    "Note": o.note,
                }
                for o in orders
            ]
        )
        st.dataframe(df, use_container_width=True)


def render_report_tab(db: DatabaseManager) -> None:
    """Showcase derived metrics from the statistics dashboard plugin."""

    dashboard = StatisticsDashboard(db)
    metrics = dashboard.metrics()
    st.subheader("Portfolio Metrics")
    for metric in metrics:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-label'>{metric.label}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-value'>{metric.value:,.2f}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_settings_tab(settings: Settings) -> None:
    """Expose runtime configuration and provide sentiment demo output."""

    st.subheader("Configuration")
    st.write("Mock Mode: ", "Enabled" if settings.mock_mode else "Disabled")
    st.json(
        {
            "database": settings.database.__dict__,
            "alerts": settings.alerts.__dict__,
            "strategy": settings.strategy.__dict__,
        }
    )

    st.subheader("News Sentiment Demo")
    analyzer = NewsAnalyzer()
    sample_headlines = [
        NewsHeadline(title="Tech stocks rally on semiconductor optimism", url="https://example.com/news1"),
        NewsHeadline(title="Global slowdown fears weigh on exporters", url="https://example.com/news2"),
    ]
    sentiments = analyzer.analyze(sample_headlines)
    st.table([{ "title": item.title, "sentiment": f"{item.sentiment:.2f}", "url": item.url } for item in sentiments])


def render_main_app(settings: Settings, engine: StrategyEngine, market: MarketDataService, db: DatabaseManager) -> None:
    """Compose the tabbed Streamlit experience."""
    advisor = AISellAdvisor()
    alert_manager = AlertManager(settings)
    tabs = st.tabs(["Recommend", "Holdings", "Orders", "Report", "Settings"])
    with tabs[0]:
        render_recommend_tab(engine=engine, market=market, advisor=advisor, alert_manager=alert_manager)
    with tabs[1]:
        render_holdings_tab(db)
    with tabs[2]:
        render_orders_tab(db)
    with tabs[3]:
        render_report_tab(db)
    with tabs[4]:
        render_settings_tab(settings)
