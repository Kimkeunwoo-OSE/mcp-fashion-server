"""Dependency wiring helpers for the FastAPI backend and tests."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple

from adapters.broker_kis import BrokerKIS
from adapters.broker_mock import MockBroker
from adapters.market_kis import MarketKIS
from adapters.market_mock import MarketMock
from adapters.notifier_windows import NotifierWindows
from adapters.storage_sqlite import SQLiteStorage, set_default_storage
from config.schema import AppSettings
from core.entities import Candle, ExitSignal, Position, Signal
from core.risk import RiskManager, format_exit_message
from core.strategy_v5 import StrategyV5
from core.symbols import get_name, iter_default_symbols

DEFAULT_SYMBOLS: Tuple[str, ...] = tuple(iter_default_symbols())

logger = logging.getLogger(__name__)


class NullNotifier:
    """Fallback notifier used outside of Windows environments."""

    def send(self, text: str) -> bool:  # pragma: no cover - simple stub
        logger.debug("Notifier disabled: %s", text)
        return False


def build_notifier(settings: AppSettings):
    if settings.notifier.type == "windows":
        return NotifierWindows()
    return NullNotifier()


def build_market(settings: AppSettings, storage: SQLiteStorage | None = None):
    if settings.market.provider == "kis":
        return MarketKIS(settings, storage=storage)
    return MarketMock(seed=42)


def build_broker(settings: AppSettings, storage: SQLiteStorage):
    if settings.broker.provider == "kis":
        return BrokerKIS(
            storage=storage,
            keys_path=Path(settings.kis.keys_path),
            paper=settings.kis.paper,
            risk_config=settings.risk,
            mode=settings.mode,
        )
    return MockBroker(storage=storage)


def build_dependencies(settings: AppSettings):
    storage = SQLiteStorage(Path(settings.db.path))
    set_default_storage(storage)
    market = build_market(settings, storage)
    broker = build_broker(settings, storage)
    notifier = build_notifier(settings)
    strategy = StrategyV5(settings.strategy)
    risk = RiskManager(settings.risk)
    return storage, market, broker, notifier, strategy, risk


def resolve_symbol_name(symbol: str, market) -> str:
    try:
        if hasattr(market, "get_name"):
            name = market.get_name(symbol)
            if name:
                return name
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.debug("심볼 이름 조회 실패(%s): %s", symbol, exc)
    fallback = get_name(symbol)
    return fallback if fallback else symbol


def resolve_universe(settings: AppSettings, market) -> list[str]:
    universe = settings.watch.universe
    custom = settings.watch.symbols
    if hasattr(market, "get_universe"):
        symbols = market.get_universe(universe, custom)
    else:
        symbols = list(DEFAULT_SYMBOLS)
    if universe == "CUSTOM" and not symbols:
        logger.warning("CUSTOM 유니버스가 비어 있습니다. 기본 심볼 사용")
        return list(DEFAULT_SYMBOLS)
    if not symbols:
        logger.warning("유니버스가 비어 있습니다. 기본 심볼 사용")
        return list(DEFAULT_SYMBOLS)
    return symbols


def collect_candles(market, symbols: Iterable[str], limit: int = 120) -> Dict[str, list[Candle]]:
    candles: Dict[str, list[Candle]] = {}
    for symbol in symbols:
        try:
            candles[symbol] = list(market.get_candles(symbol, timeframe="D", limit=limit))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("캔들 조회 실패(%s): %s", symbol, exc)
            candles[symbol] = []
    return candles


def scan_signals(
    strategy: StrategyV5,
    market,
    symbols: Iterable[str],
    top_n: int,
) -> Tuple[list[Signal], Dict[str, list[Candle]]]:
    candles = collect_candles(market, symbols)
    signals = strategy.screen_candidates(candles, top_n)
    return signals, candles


def run_cli(strategy: StrategyV5, market, symbols: Iterable[str], top_n: int) -> list[Signal]:
    signals, _ = scan_signals(strategy, market, symbols, top_n)
    for signal in signals:
        if not signal.name:
            signal.name = resolve_symbol_name(signal.symbol, market)
    return signals


def enrich_positions(
    positions: Iterable[Position],
    market,
    candles: Dict[str, list[Candle]],
    storage: SQLiteStorage,
) -> list[Position]:
    enriched: list[Position] = []
    timestamp = datetime.now(timezone.utc).isoformat()
    for position in positions:
        if position.qty <= 0:
            continue
        series = candles.get(position.symbol)
        if not series:
            series = list(market.get_candles(position.symbol, timeframe="D", limit=2))
            candles[position.symbol] = series
        if series:
            position.last_price = series[-1].close
        if position.avg_price:
            position.pnl_pct = (position.last_price - position.avg_price) / position.avg_price
        if position.trail_stop == 0 and position.last_price:
            position.trail_stop = position.last_price
        storage.upsert_position(position, timestamp)
        enriched.append(position)
    return enriched


def handle_exit_signals(
    positions: Iterable[Position],
    risk: RiskManager,
    storage: SQLiteStorage,
    notifier,
    market,
    show_names: bool,
) -> list[Tuple[Position, ExitSignal]]:
    results: list[Tuple[Position, ExitSignal]] = []
    for position in positions:
        signal = risk.evaluate_exit(position)
        if not signal:
            continue
        already_sent = not storage.remember_alert(
            position.symbol,
            signal.signal_type,
            signal.triggered_at.date(),
        )
        display_name = resolve_symbol_name(position.symbol, market) if show_names else None
        message = format_exit_message(signal, display_name)
        if not already_sent:
            try:
                notifier.send(message)
            except Exception as exc:  # pragma: no cover
                logger.warning("토스트 전송 실패(%s): %s", position.symbol, exc)
        results.append((position, signal))
    return results
