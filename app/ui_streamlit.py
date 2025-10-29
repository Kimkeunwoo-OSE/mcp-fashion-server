from __future__ import annotations

import datetime as dt
from typing import Iterable

import pandas as pd
import streamlit as st

from app.main import build_dependencies
from config.schema import AppSettings, load_settings
from core.entities import Candle, Signal
from core.risk import RiskManager
from core.strategy_v5 import StrategyV5


def _candles_to_df(candles: Iterable[Candle]) -> pd.DataFrame:
    rows = [
        {
            "timestamp": candle.timestamp,
            "close": candle.close,
            "high": candle.high,
            "low": candle.low,
            "volume": candle.volume,
        }
        for candle in candles
    ]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
    return df


def _render_dashboard(
    settings: AppSettings,
    market,
    broker,
    strategy: StrategyV5,
    notifier,
    storage,
    risk: RiskManager,
) -> None:
    st.set_page_config(page_title="v5 Trader", layout="wide", initial_sidebar_state="collapsed")
    st.title("v5 Trader — Windows Toast Edition")
    st.caption("Mock → Paper → Live 로 확장 가능한 동기 I/O 전략 도우미")

    status_col, risk_col = st.columns(2)
    with status_col:
        st.subheader("환경")
        st.metric("Mode", settings.mode)
        st.metric("Notifier", settings.notifier.type)
        st.metric("DB Path", settings.db.path)
    with risk_col:
        st.subheader("리스크 한도")
        st.write(risk.describe())

    themes = market.get_themes()
    symbols = st.multiselect("관심 심볼", options=themes, default=themes[:3])
    if not symbols:
        st.warning("최소 1개 이상의 심볼을 선택하세요.")
        return

    candles_by_symbol: dict[str, list[Candle]] = {}
    for symbol in symbols:
        candles = list(market.get_candles(symbol, timeframe="D", limit=120))
        candles_by_symbol[symbol] = candles

    signals = strategy.pick_top_signals(candles_by_symbol, top_n=3)

    st.subheader("추천 종목")
    for signal in signals:
        with st.container(border=True):
            st.markdown(f"### {signal.symbol} — 점수 {signal.score:.2f}")
            if signal.reasons:
                st.markdown("\n".join(f"- {reason}" for reason in signal.reasons))
            df = _candles_to_df(candles_by_symbol[signal.symbol])
            if not df.empty:
                st.line_chart(df["close"], height=150)

    if st.button("알림 테스트"):
        ok = notifier.send("v5 Trader 알림 테스트")
        if ok:
            st.success("Windows Toast 알림을 전송했습니다.")
        else:
            st.warning("알림 전송에 실패했습니다. Windows 환경인지 확인하세요.")

    refresh_seconds = settings.ui.refresh_interval
    st.caption(
        f"자동 새로 고침 권장 주기: {refresh_seconds}s — Streamlit 설정에서 수동으로 구성하세요."
    )

    storage.log_event(
        "INFO",
        f"UI rendered at {dt.datetime.utcnow().isoformat()}Z with {len(signals)} signals",
    )


def render() -> None:
    """Entry point for Streamlit CLI execution."""

    settings = load_settings()
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)
    _render_dashboard(settings, market, broker, strategy, notifier, storage, risk)


if __name__ == "__main__":  # pragma: no cover - manual execution
    render()
