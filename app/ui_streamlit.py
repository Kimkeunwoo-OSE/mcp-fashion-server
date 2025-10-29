from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

from app.main import DEFAULT_SYMBOLS, build_dependencies
from config.schema import AppSettings, load_settings
from core.entities import Candle
from core.risk import RiskManager
from core.strategy_v5 import StrategyV5
from core.symbols import get_name


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
        st.metric("Market Provider", getattr(market, "provider", "unknown"))
        st.metric("Broker Provider", getattr(broker, "provider", "unknown"))
        kis_path = Path(settings.kis.keys_path)
        kis_state = "존재" if kis_path.exists() else "없음"
        st.metric("KIS 키 파일", kis_state)
        st.caption(f"경로: {kis_path}")
    with risk_col:
        st.subheader("리스크 한도")
        st.write(risk.describe())

    themes = market.get_themes() or list(DEFAULT_SYMBOLS)
    default_selection = themes[:3] if themes else list(DEFAULT_SYMBOLS)[:3]
    symbols = st.multiselect("관심 심볼", options=themes, default=default_selection)
    if not symbols:
        st.warning("최소 1개 이상의 심볼을 선택하세요.")
        return

    candles_by_symbol: dict[str, list[Candle]] = {}
    for symbol in symbols:
        candles = list(market.get_candles(symbol, timeframe="D", limit=120))
        candles_by_symbol[symbol] = candles

    signals = strategy.pick_top_signals(candles_by_symbol, top_n=3)

    st.subheader("추천 종목")
    show_names = settings.display.show_names
    for signal in signals:
        candles = candles_by_symbol.get(signal.symbol, [])
        last_close = candles[-1].close if candles else 0.0
        name = signal.name or get_name(signal.symbol) if show_names else None
        with st.container(border=True):
            title = f"{signal.symbol} {name}" if name else signal.symbol
            st.markdown(f"### {title} — 점수 {signal.score:.2f}")
            if signal.reasons:
                st.markdown("\n".join(f"- {reason}" for reason in signal.reasons))
            df = _candles_to_df(candles)
            if not df.empty:
                st.line_chart(df["close"], height=150)

            action_col, info_col = st.columns([1, 1])
            with action_col:
                qty = st.number_input(
                    "수량",
                    min_value=1,
                    value=1,
                    step=1,
                    key=f"qty_{signal.symbol}",
                )
                is_kis = getattr(broker, "provider", "") == "kis"
                approval = True
                if is_kis:
                    approval = st.checkbox(
                        "주문 전 사용자 승인",
                        key=f"approve_{signal.symbol}",
                        help="자동매매 금지 — 체크해야 주문이 전송됩니다.",
                    )
                if st.button("모의 주문(Paper)", key=f"order_{signal.symbol}"):
                    if is_kis and not approval:
                        st.warning("KIS 주문은 사용자 승인 체크 후 진행됩니다.")
                    else:
                        ok = broker.place_order(
                            signal.symbol,
                            "buy",
                            int(qty),
                            price=last_close or None,
                            require_user_confirm=True,
                        )
                        if ok:
                            st.success("주문 요청을 전송했습니다.")
                        else:
                            st.warning("주문이 접수되지 않았습니다. 로그를 확인하세요.")
            with info_col:
                st.metric("마지막 가격", f"{last_close:,.2f}" if last_close else "-", help="최근 종가 기준")

    if st.button("알림 테스트"):
        if signals:
            sample = signals[0]
            sample_name = sample.name or get_name(sample.symbol)
            message = f"[v5] 추천: {sample.symbol} {sample_name} | score={sample.score:.2f}"
        else:
            message = "v5 Trader 알림 테스트"
        ok = notifier.send(message[:200])
        if ok:
            st.success("Windows Toast 알림을 전송했습니다.")
        else:
            st.warning("알림 전송에 실패했습니다. Windows 환경인지 확인하세요.")

    positions = list(broker.get_positions())
    st.subheader("포지션")
    if positions:
        rows = []
        for pos in positions:
            rows.append(
                {
                    "symbol": pos.symbol,
                    "name": get_name(pos.symbol) if show_names else "",
                    "qty": pos.qty,
                    "avg_price": pos.avg_price,
                }
            )
        df_positions = pd.DataFrame(rows)
        st.dataframe(df_positions, use_container_width=True, hide_index=True)
    else:
        st.info("보유 포지션이 없습니다.")

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
