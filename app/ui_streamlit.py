from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

from app.main import (
    build_dependencies,
    collect_candles,
    handle_exit_signals,
    resolve_universe,
)
from config.schema import AppSettings, load_settings
from core.entities import Candle, Position
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


def _enrich_positions(positions: list[Position], candles: dict[str, list[Candle]], market, storage, risk, notifier, show_names: bool) -> tuple[list[Position], dict[str, str]]:
    enriched: list[Position] = []
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    for pos in positions:
        if pos.qty <= 0:
            continue
        series = candles.get(pos.symbol)
        if not series:
            series = list(market.get_candles(pos.symbol, timeframe="D", limit=2))
            candles[pos.symbol] = series
        if series:
            pos.last_price = series[-1].close
        if pos.avg_price:
            pos.pnl_pct = (pos.last_price - pos.avg_price) / pos.avg_price
        if pos.trail_stop == 0 and pos.last_price:
            pos.trail_stop = pos.last_price
        storage.upsert_position(pos, timestamp)
        enriched.append(pos)
    exit_signals = handle_exit_signals(enriched, risk, storage, notifier, show_names)
    exit_map = {signal.symbol: signal.signal_type for _, signal in exit_signals}
    return enriched, exit_map


def _render_dashboard(settings: AppSettings, market, broker, strategy, notifier, storage, risk) -> None:
    st.set_page_config(page_title="v5 Trader", layout="wide", initial_sidebar_state="collapsed")
    st.title("v5 Trader — Windows Toast Edition")
    st.caption("Mock → Paper → Live 로 확장 가능한 동기 I/O 전략 도우미")

    env_col, risk_col, watch_col = st.columns(3)
    with env_col:
        st.subheader("환경")
        st.metric("Mode", settings.mode)
        st.metric("Market", getattr(market, "provider", "unknown"))
        st.metric("Broker", getattr(broker, "provider", "unknown"))
        kis_path = Path(settings.kis.keys_path)
        st.metric("KIS 키 파일", "존재" if kis_path.exists() else "없음")
        st.caption(f"경로: {kis_path}")
    with risk_col:
        st.subheader("리스크")
        st.metric("Stop Loss", f"{settings.risk.stop_loss_pct * 100:.1f}%")
        st.metric("Take Profit", f"{settings.risk.take_profit_pct * 100:.1f}%")
        st.metric("Trailing", f"{settings.risk.trailing_pct * 100:.1f}%")
        st.caption(f"Max Positions: {settings.risk.max_positions}")
    with watch_col:
        st.subheader("감시 유니버스")
        st.metric("Universe", settings.watch.universe)
        st.metric("Top N", settings.watch.top_n)
        st.metric("Refresh", f"{settings.watch.refresh_sec}s")
        if settings.watch.universe == "CUSTOM":
            st.caption(
                ", ".join(settings.watch.symbols) if settings.watch.symbols else "(심볼 없음)"
            )

    universe_symbols = resolve_universe(settings, market)
    candles_by_symbol = collect_candles(market, universe_symbols, limit=120)
    signals = strategy.screen_candidates(candles_by_symbol, settings.watch.top_n)

    st.subheader("추천 종목")
    st.caption(f"스캔 시각: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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
        try:
            ok = notifier.send(message[:200])
        except Exception:  # pragma: no cover - defensive guard
            ok = False
        if ok:
            st.success("Windows Toast 알림을 전송했습니다.")
        else:
            st.warning("알림 전송에 실패했습니다. Windows 환경인지 확인하세요.")

    st.subheader("보유 종목")
    raw_positions = list(broker.get_positions())
    enriched_positions, exit_map = _enrich_positions(
        raw_positions,
        candles_by_symbol,
        market,
        storage,
        risk,
        notifier,
        show_names,
    )

    if enriched_positions:
        rows = []
        for pos in enriched_positions:
            rows.append(
                {
                    "symbol": pos.symbol,
                    "name": get_name(pos.symbol) if show_names else "",
                    "qty": pos.qty,
                    "avg": pos.avg_price,
                    "last": pos.last_price,
                    "pnl_pct": pos.pnl_pct * 100,
                    "exit_signal": exit_map.get(pos.symbol, "-"),
                }
            )
        df_positions = pd.DataFrame(rows)
        st.dataframe(df_positions, width="stretch", hide_index=True)
        for pos in enriched_positions:
            if st.button("매도 보조", key=f"sell_{pos.symbol}"):
                ok = broker.place_order(
                    pos.symbol,
                    "sell",
                    max(pos.qty, 1),
                    price=pos.last_price or None,
                    require_user_confirm=True,
                )
                if ok:
                    st.success(f"{pos.symbol} 매도 요청을 전송했습니다.")
                else:
                    st.warning("매도 요청이 거절되었습니다. 로그를 확인하세요.")
    else:
        st.info("보유 포지션이 없습니다.")

    st.caption(
        f"자동 새로 고침 권장 주기: {settings.watch.refresh_sec}s — Streamlit 설정에서 수동으로 구성하세요."
    )

    storage.log_event(
        "INFO",
        f"UI rendered at {dt.datetime.utcnow().isoformat()}Z with {len(signals)} signals",
    )


def render() -> None:
    settings = load_settings()
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)
    _render_dashboard(settings, market, broker, strategy, notifier, storage, risk)


if __name__ == "__main__":  # pragma: no cover - manual execution
    render()
