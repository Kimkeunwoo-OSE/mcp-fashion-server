from __future__ import annotations

import datetime as dt
import logging
import math
import time
from typing import Dict, Iterable, List, Sequence

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from app.main import (
    build_dependencies,
    collect_candles,
    handle_exit_signals,
    resolve_symbol_name,
    resolve_universe,
)
from config.schema import AppSettings, load_settings
from core.entities import Candle, Position

logger = logging.getLogger(__name__)

TAB_TRADE = "거래"
TAB_CHART = "차트"
TAB_RECO = "추천"
TAB_HOLD = "보유/알림"


def _candles_to_df(candles: Iterable[Candle]) -> pd.DataFrame:
    rows = [
        {
            "timestamp": candle.timestamp,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        for candle in candles
    ]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def _resolve_name(symbol: str, market) -> str:
    try:
        return resolve_symbol_name(symbol, market)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("심볼 이름 조회 실패(%s): %s", symbol, exc)
        return symbol


def _ensure_candles(
    symbol: str,
    candles_by_symbol: Dict[str, List[Candle]],
    market,
    limit: int,
) -> List[Candle]:
    if not symbol:
        return []
    candles = candles_by_symbol.get(symbol, [])
    if candles:
        return candles
    try:
        candles = list(market.get_candles(symbol, timeframe="D", limit=limit))
        candles_by_symbol[symbol] = candles
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("캔들 조회 실패(%s): %s", symbol, exc)
        candles = []
    return candles


def _compute_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0)


def _prepare_positions(
    positions: Sequence[Position],
    candles_by_symbol: Dict[str, List[Candle]],
    market,
    storage,
    risk,
    notifier,
    show_names: bool,
) -> tuple[list[Position], dict[str, str], dict[str, str]]:
    enriched: list[Position] = []
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    for position in positions:
        if position.qty <= 0:
            continue
        series = candles_by_symbol.get(position.symbol)
        if not series:
            series = list(market.get_candles(position.symbol, timeframe="D", limit=2))
            candles_by_symbol[position.symbol] = series
        if series:
            position.last_price = series[-1].close
        if position.avg_price:
            try:
                position.pnl_pct = (position.last_price - position.avg_price) / position.avg_price
            except ZeroDivisionError:  # pragma: no cover - defensive
                position.pnl_pct = 0.0
        if position.trail_stop == 0 and position.last_price:
            position.trail_stop = position.last_price
        storage.upsert_position(position, timestamp)
        enriched.append(position)

    exit_signals = handle_exit_signals(
        enriched,
        risk,
        storage,
        notifier,
        market,
        show_names,
    )
    exit_map = {signal.symbol: signal.signal_type for _, signal in exit_signals}

    name_map: dict[str, str] = {}
    if show_names:
        for pos in enriched:
            name_map[pos.symbol] = _resolve_name(pos.symbol, market)

    return enriched, exit_map, name_map


def _set_symbol(symbol: str, target_tab: str | None = None) -> None:
    normalized = (symbol or "").strip().upper()
    if not normalized:
        return
    manual = set(st.session_state.get("manual_symbols", []))
    manual.add(normalized)
    st.session_state["manual_symbols"] = list(manual)
    st.session_state["selected_symbol"] = normalized
    if target_tab:
        st.session_state["ui_tab"] = target_tab
        st.session_state["tab_selector"] = target_tab
    st.experimental_rerun()


def _render_environment(settings: AppSettings, market, broker) -> None:
    st.title("v5 Trader — Windows Toast Edition")
    st.caption("Mock → Paper → Live 로 확장 가능한 동기 I/O 전략 도우미")

    env_col, risk_col, watch_col = st.columns(3)
    with env_col:
        st.subheader("환경")
        st.metric("Mode", settings.mode)
        st.metric("Market", getattr(market, "provider", "unknown"))
        st.metric("Broker", getattr(broker, "provider", "unknown"))
        kis_path = settings.kis.keys_path
        st.caption(f"KIS 키 파일: {kis_path}")
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
            symbols = settings.watch.symbols or []
            st.caption(", ".join(symbols) if symbols else "(심볼 없음)")


def _render_symbol_toolbar(
    *,
    all_symbols: Sequence[str],
    favorites: Sequence[str],
    market,
    show_names: bool,
    key_prefix: str,
    header: str,
) -> None:
    base_symbols = list(all_symbols)
    formatted = {
        symbol: f"{symbol} {_resolve_name(symbol, market)}" if show_names else symbol
        for symbol in base_symbols
    }
    current = st.session_state.get("selected_symbol")
    options = base_symbols.copy()
    if current and current not in options:
        options.insert(0, current)
        if show_names and current not in formatted:
            formatted[current] = _resolve_name(current, market)
    if not options:
        st.info("선택 가능한 심볼이 없습니다. 설정을 확인하세요.")
        return
    st.selectbox(
        header,
        options=options,
        index=options.index(current) if current in options else 0,
        format_func=lambda sym: formatted.get(sym, sym),
        key=f"symbol_select_{key_prefix}",
    )
    st.session_state["selected_symbol"] = st.session_state.get(
        f"symbol_select_{key_prefix}", current or options[0]
    )

    search_value = st.text_input("심볼 검색", key=f"symbol_search_{key_prefix}")
    if st.button("검색 적용", key=f"symbol_search_apply_{key_prefix}"):
        _set_symbol(search_value)

    if favorites:
        st.caption("관심 심볼")
        cols = st.columns(min(len(favorites), 4) or 1)
        for idx, symbol in enumerate(favorites):
            col = cols[idx % len(cols)]
            label = formatted.get(symbol) or (
                f"{symbol} {_resolve_name(symbol, market)}" if show_names else symbol
            )
            if col.button(label, key=f"fav_{key_prefix}_{symbol}"):
                _set_symbol(symbol)


def _submit_order(
    *,
    broker,
    storage,
    notifier,
    symbol: str,
    side: str,
    qty: int,
    price_type: str,
    limit_price: float | None,
    name: str,
    reference_price: float | None,
) -> dict:
    timestamp = dt.datetime.utcnow().isoformat()
    try:
        result = broker.place_order(symbol, side, qty, price_type, limit_price)
    except Exception as exc:  # pragma: no cover - defensive
        result = {"ok": False, "order_id": None, "message": str(exc)}

    label = name or symbol
    if result.get("ok"):
        order_id = result.get("order_id") or f"{symbol}-{int(time.time())}"
        storage.log_event(
            "order_ok",
            f"{side} {symbol} {label} x{qty} ({price_type}) → #{order_id}",
        )
        storage.record_trade(
            order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=float(limit_price or reference_price or 0.0),
            ts=timestamp,
        )
        try:
            notifier.send(
                f"ORDER OK {symbol} {label} x{qty} ({price_type}) → #{order_id}"
            )
        except Exception:
            pass
    else:
        reason = result.get("message") or "주문이 거절되었습니다."
        storage.log_event(
            "order_fail",
            f"ORDER FAIL {symbol} {label} x{qty}: {reason}",
        )
        try:
            notifier.send(f"ORDER FAIL {symbol} {label} x{qty}: {reason}")
        except Exception:
            pass
    return result


def _render_trade_tab(
    *,
    settings: AppSettings,
    market,
    broker,
    notifier,
    storage,
    candles_by_symbol: Dict[str, List[Candle]],
    positions: Sequence[Position],
    all_symbols: Sequence[str],
    max_period: int,
    show_names: bool,
) -> None:
    trade_settings = settings.trade
    favorites = [pos.symbol for pos in positions if pos.qty > 0]
    _render_symbol_toolbar(
        all_symbols=all_symbols,
        favorites=favorites,
        market=market,
        show_names=show_names,
        key_prefix="trade",
        header="거래 심볼",
    )

    symbol = st.session_state.get("selected_symbol", "")
    candles = _ensure_candles(symbol, candles_by_symbol, market, max_period)
    last_close = candles[-1].close if candles else 0.0
    prev_close = candles[-2].close if len(candles) > 1 else last_close
    change = last_close - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0
    turnover = (candles[-1].volume or 0) * last_close if candles else 0.0

    info_col, gap_col = st.columns([3, 1])
    with info_col:
        st.subheader(f"{symbol} {_resolve_name(symbol, market) if show_names else ''}".strip())
        metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
        metrics_col1.metric("현재가", f"{last_close:,.2f}" if last_close else "-")
        metrics_col2.metric("전일대비", f"{change:,.2f}")
        metrics_col3.metric("등락률", f"{change_pct:.2f}%")
        st.caption(f"거래대금(추정): {turnover:,.0f}원")

    position_lookup = {pos.symbol: pos for pos in positions}
    position = position_lookup.get(symbol)
    hold_qty = position.qty if position else 0
    price_reference = last_close or (position.avg_price if position else 0.0) or 0.0

    side_key = f"trade_side_{symbol}"
    mode_key = f"trade_mode_{symbol}"
    qty_key = f"trade_qty_{symbol}"
    amt_key = f"trade_amt_{symbol}"
    price_type_key = f"trade_price_type_{symbol}"
    limit_key = f"trade_limit_{symbol}"
    approve_key = f"trade_approve_{symbol}"
    cooldown_key = f"trade_cooldown_{symbol}"

    default_qty = hold_qty or 1
    st.session_state.setdefault(qty_key, default_qty)
    st.session_state.setdefault(amt_key, int(max(price_reference, 0.0) * default_qty) or 0)
    st.session_state.setdefault(price_type_key, trade_settings.default_price_type)
    if price_reference:
        st.session_state.setdefault(limit_key, float(price_reference))
    else:
        st.session_state.setdefault(limit_key, float(trade_settings.tick))

    side = st.segmented_control("거래", ["매수", "매도"], key=side_key)
    mode = st.segmented_control("입력 방식", ["수량", "금액"], key=mode_key)

    if mode == "수량":
        qty = st.number_input(
            "수량",
            min_value=1,
            step=1,
            key=qty_key,
        )
        st.session_state[amt_key] = int(max(price_reference, 0.0) * qty)
    else:
        amount = st.number_input(
            "금액(원)",
            min_value=1000,
            step=1000,
            key=amt_key,
        )
        qty = max(0, int(amount // max(price_reference, 1)))
        st.caption(f"계산 수량: {qty}주 (기준 {price_reference:,.0f}원)")
        st.session_state[qty_key] = max(qty, 1) if qty else 1

    price_type = st.selectbox(
        "가격 유형",
        options=["market", "limit"],
        key=price_type_key,
    )

    limit_price = None
    if price_type == "limit":
        minus_col, input_col, plus_col = st.columns([1, 3, 1])
        if minus_col.button("–", key=f"minus_{symbol}"):
            st.session_state[limit_key] = max(1.0, st.session_state[limit_key] - trade_settings.tick)
            st.experimental_rerun()
        if plus_col.button("+", key=f"plus_{symbol}"):
            st.session_state[limit_key] = st.session_state[limit_key] + trade_settings.tick
            st.experimental_rerun()
        limit_price = input_col.number_input(
            "지정가",
            min_value=1.0,
            step=float(trade_settings.tick),
            key=limit_key,
        )
    else:
        st.session_state[limit_key] = float(price_reference or trade_settings.tick)

    pct_cols = st.columns(len(trade_settings.quick_pct) or 1)
    for idx, pct in enumerate(trade_settings.quick_pct):
        if pct_cols[idx].button(f"{pct}%", key=f"trade_pct_{symbol}_{pct}"):
            if side == "매도" and hold_qty > 0:
                computed = max(1, math.floor(hold_qty * pct / 100))
                computed = min(computed, hold_qty)
                st.session_state[qty_key] = computed
                st.session_state[amt_key] = int(max(price_reference, 0.0) * computed)
                st.experimental_rerun()
            elif side == "매수":
                st.warning("예수금 정보를 사용할 수 없습니다. 수량을 직접 입력하세요.")

    approve = st.checkbox(trade_settings.confirm_phrase, key=approve_key)

    last_click = st.session_state.get(cooldown_key)
    disabled = bool(last_click and (time.time() - last_click) < 3)
    if st.button("주문", type="primary", key=f"submit_{symbol}", disabled=disabled):
        st.session_state[cooldown_key] = time.time()
        qty_value = int(st.session_state.get(qty_key, 0))
        if not approve:
            st.error("승인 체크가 필요합니다.")
        elif qty_value < 1:
            st.error("수량이 1 미만입니다.")
        elif side == "매도" and hold_qty and qty_value > hold_qty:
            st.error("보유 수량을 초과합니다.")
        else:
            result = _submit_order(
                broker=broker,
                storage=storage,
                notifier=notifier,
                symbol=symbol,
                side="SELL" if side == "매도" else "BUY",
                qty=qty_value,
                price_type=price_type,
                limit_price=float(limit_price) if limit_price and price_type == "limit" else None,
                name=_resolve_name(symbol, market) if show_names else symbol,
                reference_price=price_reference,
            )
            if result.get("ok"):
                st.success(
                    f"주문 전송 성공: {symbol} x{qty_value} ({price_type}) / 주문번호 {result.get('order_id') or 'N/A'}"
                )
            else:
                reason = result.get("message") or "주문이 거절되었습니다."
                st.error(f"주문 실패: {reason}")
            st.session_state[approve_key] = False



def _render_chart_tab(
    *,
    settings: AppSettings,
    market,
    candles_by_symbol: Dict[str, List[Candle]],
    all_symbols: Sequence[str],
    max_period: int,
    show_names: bool,
) -> None:
    favorites = [st.session_state.get("selected_symbol", "")]
    _render_symbol_toolbar(
        all_symbols=all_symbols,
        favorites=[sym for sym in favorites if sym],
        market=market,
        show_names=show_names,
        key_prefix="chart",
        header="차트 심볼",
    )

    symbol = st.session_state.get("selected_symbol", "")
    periods = settings.chart.periods or [120]
    default_period = periods[min(1, len(periods) - 1)] if len(periods) > 1 else periods[0]
    period = st.select_slider("기간", options=periods, value=default_period, key="chart_period")

    indicator_options = settings.chart.indicators or []
    default_indicators = indicator_options
    indicators = st.multiselect(
        "지표",
        options=indicator_options,
        default=default_indicators,
        key="chart_indicators",
    )

    candles = _ensure_candles(symbol, candles_by_symbol, market, max_period)
    if candles and len(candles) > period:
        candles = candles[-period:]
    df = _candles_to_df(candles)
    if df.empty:
        st.info("차트 데이터를 불러올 수 없습니다.")
        return

    df = df.tail(period)
    close_series = df["close"].astype(float)
    timestamps = df["timestamp"]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        specs=[[{"secondary_y": True}], [{}]],
    )

    fig.add_trace(
        go.Candlestick(
            x=timestamps,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLC",
        ),
        row=1,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=timestamps,
            y=df["volume"],
            name="Volume",
            opacity=0.3,
        ),
        row=1,
        col=1,
        secondary_y=True,
    )

    for indicator in indicators:
        upper = indicator.upper()
        if upper.startswith("SMA"):
            try:
                window = int(upper.replace("SMA", ""))
            except ValueError:
                continue
            sma = _compute_sma(close_series, window)
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=sma,
                    mode="lines",
                    name=f"SMA{window}",
                ),
                row=1,
                col=1,
                secondary_y=False,
            )
        elif upper.startswith("RSI"):
            try:
                period_rsi = int(upper.replace("RSI", ""))
            except ValueError:
                continue
            rsi = _compute_rsi(close_series, period_rsi)
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=rsi,
                    mode="lines",
                    name=f"RSI{period_rsi}",
                ),
                row=2,
                col=1,
            )
            fig.add_hline(y=70, line_width=1, line_color="#888", row=2, col=1)
            fig.add_hline(y=30, line_width=1, line_color="#888", row=2, col=1)

    fig.update_yaxes(title_text="Price", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Volume", row=1, col=1, secondary_y=True, showgrid=False)
    fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
    fig.update_layout(xaxis_rangeslider_visible=False, height=500, margin=dict(l=0, r=0, t=30, b=0))

    st.plotly_chart(fig, width="stretch")


def _render_recommendations_tab(
    *,
    settings: AppSettings,
    market,
    signals,
    candles_by_symbol: Dict[str, List[Candle]],
    max_period: int,
    show_names: bool,
) -> None:
    st.caption(f"스캔 시각: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if not signals:
        st.info("추천 후보가 없습니다.")
        return

    for idx, signal in enumerate(signals, start=1):
        candles = candles_by_symbol.get(signal.symbol) or []
        if not candles:
            candles = _ensure_candles(signal.symbol, candles_by_symbol, market, max_period)
        last_close = candles[-1].close if candles else 0.0
        prev_close = candles[-2].close if len(candles) > 1 else last_close
        change_pct = ((last_close - prev_close) / prev_close * 100) if prev_close else 0.0
        volume = candles[-1].volume if candles else 0.0
        name = signal.name or (_resolve_name(signal.symbol, market) if show_names else "")

        with st.container(border=True):
            st.markdown(
                f"### {idx}. {signal.symbol} {name} — 점수 {signal.score:.2f}".strip()
            )
            st.caption(" · ".join(signal.reasons) if signal.reasons else "(사유 없음)")
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            metrics_col1.metric("종가", f"{last_close:,.2f}")
            metrics_col2.metric("일간 변동", f"{change_pct:.2f}%")
            metrics_col3.metric("거래량", f"{volume:,.0f}")
            btn_col1, btn_col2 = st.columns(2)
            if btn_col1.button("거래로", key=f"to_trade_{signal.symbol}"):
                _set_symbol(signal.symbol, TAB_TRADE)
            if btn_col2.button("차트로", key=f"to_chart_{signal.symbol}"):
                _set_symbol(signal.symbol, TAB_CHART)


def _render_holdings_tab(
    *,
    settings: AppSettings,
    market,
    broker,
    notifier,
    storage,
    candles_by_symbol: Dict[str, List[Candle]],
    positions: Sequence[Position],
    exit_map: dict[str, str],
    name_map: dict[str, str],
    max_period: int,
    show_names: bool,
) -> None:
    if not positions:
        st.info("보유 포지션이 없습니다.")
        return

    rows = []
    for pos in positions:
        name = name_map.get(pos.symbol, _resolve_name(pos.symbol, market)) if show_names else ""
        rows.append(
            {
                "symbol": pos.symbol,
                "name": name,
                "qty": pos.qty,
                "avg": pos.avg_price,
                "last": pos.last_price,
                "pnl_pct": pos.pnl_pct * 100,
                "exit_signal": exit_map.get(pos.symbol, "-"),
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    trade_settings = settings.trade
    cooldowns = st.session_state.setdefault("sell_cooldowns", {})

    for pos in positions:
        name = name_map.get(pos.symbol, _resolve_name(pos.symbol, market)) if show_names else ""
        exit_label = exit_map.get(pos.symbol, "-")
        candles = _ensure_candles(pos.symbol, candles_by_symbol, market, max_period)
        last_close = candles[-1].close if candles else pos.last_price
        price_reference = last_close or pos.avg_price or 0.0

        key_prefix = pos.symbol.replace(".", "_")
        qty_key = f"hold_qty_{key_prefix}"
        amt_key = f"hold_amt_{key_prefix}"
        limit_key = f"hold_limit_{key_prefix}"
        approve_key = f"hold_approve_{key_prefix}"
        price_type_key = f"hold_price_type_{key_prefix}"

        st.session_state.setdefault(qty_key, max(pos.qty, 1))
        st.session_state.setdefault(amt_key, int(max(price_reference, 0.0) * pos.qty))
        st.session_state.setdefault(limit_key, float(price_reference or trade_settings.tick))
        st.session_state.setdefault(price_type_key, trade_settings.default_price_type)

        with st.container(border=True):
            st.markdown(f"#### {pos.symbol} {name}")
            info_cols = st.columns(3)
            info_cols[0].metric("보유 수량", pos.qty)
            info_cols[0].metric("평단", f"{pos.avg_price:,.2f}")
            info_cols[1].metric("현재가", f"{pos.last_price:,.2f}")
            info_cols[1].metric("손익%", f"{pos.pnl_pct * 100:.2f}%")
            if exit_label and exit_label != "-":
                info_cols[2].warning(f"Exit: {exit_label}")
            else:
                info_cols[2].info("Exit: -")

            mode = st.segmented_control(
                "입력 방식",
                ["수량", "금액"],
                key=f"hold_mode_{key_prefix}",
            )
            if mode == "수량":
                qty = st.number_input(
                    "매도 수량",
                    min_value=1,
                    max_value=max(pos.qty, 1),
                    value=max(pos.qty, 1),
                    step=1,
                    key=qty_key,
                )
                st.session_state[amt_key] = int(max(price_reference, 0.0) * qty)
            else:
                amount = st.number_input(
                    "매도 금액(원)",
                    min_value=1000,
                    step=1000,
                    key=amt_key,
                )
                qty = max(0, int(amount // max(price_reference, 1)))
                if qty > pos.qty:
                    qty = pos.qty
                st.caption(f"계산 수량: {qty}주 (기준 {price_reference:,.0f}원)")
                st.session_state[qty_key] = max(qty, 1) if qty else 1

            price_type = st.selectbox(
                "가격 유형",
                ["market", "limit"],
                key=price_type_key,
            )
            limit_price = None
            if price_type == "limit":
                minus_col, input_col, plus_col = st.columns([1, 3, 1])
                if minus_col.button("–", key=f"hold_minus_{key_prefix}"):
                    st.session_state[limit_key] = max(
                        1.0, st.session_state[limit_key] - trade_settings.tick
                    )
                    st.experimental_rerun()
                if plus_col.button("+", key=f"hold_plus_{key_prefix}"):
                    st.session_state[limit_key] = st.session_state[limit_key] + trade_settings.tick
                    st.experimental_rerun()
                limit_price = input_col.number_input(
                    "지정가",
                    min_value=1.0,
                    step=float(trade_settings.tick),
                    key=limit_key,
                )
            else:
                st.session_state[limit_key] = float(price_reference or trade_settings.tick)

            pct_cols = st.columns(len(trade_settings.quick_pct) or 1)
            for idx, pct in enumerate(trade_settings.quick_pct):
                if pct_cols[idx].button(f"{pct}%", key=f"hold_pct_{key_prefix}_{pct}"):
                    computed = max(1, math.floor(pos.qty * pct / 100))
                    computed = min(computed, pos.qty)
                    st.session_state[qty_key] = computed
                    st.session_state[amt_key] = int(max(price_reference, 0.0) * computed)
                    st.experimental_rerun()

            approval = st.checkbox(trade_settings.confirm_phrase, key=approve_key)
            last_click = cooldowns.get(pos.symbol)
            disabled = bool(last_click and (time.time() - last_click) < 3)
            if st.button(
                "매도",
                type="primary",
                key=f"hold_sell_{key_prefix}",
                disabled=disabled,
            ):
                cooldowns[pos.symbol] = time.time()
                qty_value = int(st.session_state.get(qty_key, 0))
                if not approval:
                    st.error("승인 체크 필요")
                elif qty_value < 1:
                    st.error("수량이 1 미만입니다.")
                elif qty_value > pos.qty:
                    st.error("보유 수량을 초과합니다.")
                else:
                    result = _submit_order(
                        broker=broker,
                        storage=storage,
                        notifier=notifier,
                        symbol=pos.symbol,
                        side="SELL",
                        qty=qty_value,
                        price_type=price_type,
                        limit_price=float(limit_price) if limit_price and price_type == "limit" else None,
                        name=name,
                        reference_price=price_reference,
                    )
                    if result.get("ok"):
                        st.success(
                            f"매도 전송 성공: {pos.symbol} x{qty_value} ({price_type}) / 주문번호 {result.get('order_id') or 'N/A'}"
                        )
                    else:
                        reason = result.get("message") or "주문이 거절되었습니다."
                        st.error(f"주문 실패: {reason}")
                    st.session_state[approve_key] = False
            st.session_state["sell_cooldowns"] = cooldowns


def _render_tabs(
    *,
    selected_tab: str,
    settings: AppSettings,
    market,
    broker,
    notifier,
    storage,
    candles_by_symbol: Dict[str, List[Candle]],
    signals,
    positions: Sequence[Position],
    exit_map: dict[str, str],
    name_map: dict[str, str],
    all_symbols: Sequence[str],
    max_period: int,
    show_names: bool,
) -> None:
    if selected_tab == TAB_TRADE:
        _render_trade_tab(
            settings=settings,
            market=market,
            broker=broker,
            notifier=notifier,
            storage=storage,
            candles_by_symbol=candles_by_symbol,
            positions=positions,
            all_symbols=all_symbols,
            max_period=max_period,
            show_names=show_names,
        )
    elif selected_tab == TAB_CHART:
        _render_chart_tab(
            settings=settings,
            market=market,
            candles_by_symbol=candles_by_symbol,
            all_symbols=all_symbols,
            max_period=max_period,
            show_names=show_names,
        )
    elif selected_tab == TAB_RECO:
        _render_recommendations_tab(
            settings=settings,
            market=market,
            signals=signals,
            candles_by_symbol=candles_by_symbol,
            max_period=max_period,
            show_names=show_names,
        )
    elif selected_tab == TAB_HOLD:
        _render_holdings_tab(
            settings=settings,
            market=market,
            broker=broker,
            notifier=notifier,
            storage=storage,
            candles_by_symbol=candles_by_symbol,
            positions=positions,
            exit_map=exit_map,
            name_map=name_map,
            max_period=max_period,
            show_names=show_names,
        )


def render() -> None:
    settings = load_settings()
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)

    st.set_page_config(page_title="v5 Trader", layout="wide", initial_sidebar_state="collapsed")
    _render_environment(settings, market, broker)

    show_names = settings.display.show_names
    st.session_state.setdefault("manual_symbols", [])

    raw_positions = list(broker.get_positions())
    universe_symbols = resolve_universe(settings, market)
    position_symbols = {pos.symbol for pos in raw_positions if pos.qty > 0}
    symbols_for_candles = sorted(set(universe_symbols) | position_symbols)
    max_period = max([120, *settings.chart.periods]) if settings.chart.periods else 120
    candles_by_symbol = collect_candles(market, symbols_for_candles, limit=max_period)

    strategy_signals = strategy.screen_candidates(candles_by_symbol, settings.watch.top_n)
    if show_names:
        for signal in strategy_signals:
            if not signal.name:
                signal.name = _resolve_name(signal.symbol, market)

    enriched_positions, exit_map, name_map = _prepare_positions(
        raw_positions,
        candles_by_symbol,
        market,
        storage,
        risk,
        notifier,
        show_names,
    )

    all_symbols = sorted(
        set(symbols_for_candles)
        | {signal.symbol for signal in strategy_signals}
        | set(st.session_state.get("manual_symbols", []))
        | {pos.symbol for pos in enriched_positions}
    )

    if all_symbols and (
        "selected_symbol" not in st.session_state
        or st.session_state.get("selected_symbol") not in all_symbols
    ):
        st.session_state["selected_symbol"] = all_symbols[0]

    tab_options = [TAB_TRADE, TAB_CHART, TAB_RECO, TAB_HOLD]
    default_tab = st.session_state.get("ui_tab", TAB_TRADE)
    selected_tab = st.radio(
        "탭 선택",
        tab_options,
        index=tab_options.index(default_tab) if default_tab in tab_options else 0,
        horizontal=True,
        key="tab_selector",
    )
    st.session_state["ui_tab"] = selected_tab

    _render_tabs(
        selected_tab=selected_tab,
        settings=settings,
        market=market,
        broker=broker,
        notifier=notifier,
        storage=storage,
        candles_by_symbol=candles_by_symbol,
        signals=strategy_signals,
        positions=enriched_positions,
        exit_map=exit_map,
        name_map=name_map,
        all_symbols=all_symbols,
        max_period=max_period,
        show_names=show_names,
    )

    if strategy_signals:
        sample = strategy_signals[0]
        sample_name = sample.name or _resolve_name(sample.symbol, market)
        toast_message = f"[v5] 추천: {sample.symbol} {sample_name} | score={sample.score:.2f}"[:200]
    else:
        toast_message = "v5 Trader 알림 테스트"

    if st.button("알림 테스트"):
        try:
            ok = notifier.send(toast_message)
        except Exception:
            ok = False
        if ok:
            st.success("Windows Toast 알림을 전송했습니다.")
        else:
            st.warning("알림 전송에 실패했습니다. Windows 환경인지 확인하세요.")

    storage.log_event(
        "INFO",
        f"UI rendered at {dt.datetime.utcnow().isoformat()}Z with {len(strategy_signals)} signals",
    )


if __name__ == "__main__":  # pragma: no cover - manual execution
    render()
