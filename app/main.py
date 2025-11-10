from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple

from adapters.broker_kis import BrokerKIS
from adapters.broker_mock import MockBroker
from adapters.market_kis import MarketKIS
from adapters.market_mock import MarketMock
from adapters.notifier_windows import NotifierWindows
from adapters.storage_sqlite import SQLiteStorage
from config.schema import AppSettings, load_settings
from core.entities import Candle, ExitSignal, Position, Signal
from core.risk import RiskManager, format_exit_message
from core.strategy_v5 import StrategyV5
from core.symbols import get_name, iter_default_symbols

DEFAULT_SYMBOLS: Tuple[str, ...] = tuple(iter_default_symbols())


def resolve_symbol_name(symbol: str, market) -> str:
    try:
        if hasattr(market, "get_name"):
            name = market.get_name(symbol)
            if name:
                return name
    except Exception as exc:  # pragma: no cover - defensive fallback
        logging.debug("심볼 이름 조회 실패(%s): %s", symbol, exc)
    return get_name(symbol)


class NullNotifier:
    """Fallback notifier that logs instead of sending alerts."""

    def send(self, text: str) -> bool:
        logging.getLogger(__name__).warning("Notifier disabled: %s", text)
        return False


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


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
    market = build_market(settings, storage)
    broker = build_broker(settings, storage)
    notifier = build_notifier(settings)
    strategy = StrategyV5(settings.strategy)
    risk = RiskManager(settings.risk)
    return storage, market, broker, notifier, strategy, risk


def resolve_universe(settings: AppSettings, market) -> list[str]:
    universe = settings.watch.universe
    custom = settings.watch.symbols
    if hasattr(market, "get_universe"):
        symbols = market.get_universe(universe, custom)
    else:
        symbols = list(DEFAULT_SYMBOLS)
    if universe == "CUSTOM" and not symbols:
        logging.warning("CUSTOM 유니버스가 비어 있습니다. 기본 심볼을 사용합니다.")
        return list(DEFAULT_SYMBOLS)
    if not symbols:
        logging.warning("유니버스가 비어 있습니다. 기본 심볼을 사용합니다.")
        return list(DEFAULT_SYMBOLS)
    return symbols


def collect_candles(market, symbols: Iterable[str], limit: int = 120) -> Dict[str, list[Candle]]:
    candles: Dict[str, list[Candle]] = {}
    for symbol in symbols:
        try:
            candles[symbol] = list(market.get_candles(symbol, timeframe="D", limit=limit))
        except Exception as exc:  # pragma: no cover - defensive guard
            logging.warning("캔들 조회 실패(%s): %s", symbol, exc)
            candles[symbol] = []
    return candles


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
        already_sent = not storage.remember_alert(position.symbol, signal.signal_type, signal.triggered_at.date())
        display_name = resolve_symbol_name(position.symbol, market) if show_names else None
        message = format_exit_message(signal, display_name)
        if not already_sent:
            try:
                notifier.send(message)
            except Exception as exc:  # pragma: no cover - defensive
                logging.warning("토스트 전송 실패(%s): %s", position.symbol, exc)
        results.append((position, signal))
    return results


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


def run_scan_once(
    settings: AppSettings,
    storage: SQLiteStorage,
    market,
    broker,
    notifier,
    strategy: StrategyV5,
    risk: RiskManager,
) -> int:
    symbols = resolve_universe(settings, market)
    top_n = settings.watch.top_n
    signals, candles = scan_signals(strategy, market, symbols, top_n)

    print("=== v5 Trader 추천 종목 ===")
    if not signals:
        print("추천 신호가 없습니다. 설정을 확인하세요.")
    show_names = settings.display.show_names
    if show_names:
        for signal in signals:
            if not signal.name:
                signal.name = resolve_symbol_name(signal.symbol, market)
    for idx, signal in enumerate(signals, start=1):
        reasons = "; ".join(signal.reasons) if signal.reasons else "N/A"
        name_part = f" {signal.name}" if show_names and signal.name else ""
        print(f"{idx}. {signal.symbol}{name_part} (score={signal.score:.2f}) - {reasons}")

    if signals:
        top_signal = signals[0]
        top_name = top_signal.name or resolve_symbol_name(top_signal.symbol, market)
        toast_text = f"[v5] 추천: {top_signal.symbol} {top_name} | score={top_signal.score:.2f}"[:200]
    else:
        toast_text = "v5 Trader 후보가 없습니다."
    try:
        notifier.send(toast_text)
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("추천 토스트 전송 실패: %s", exc)

    positions = enrich_positions(list(broker.get_positions()), market, candles, storage)
    exit_signals = handle_exit_signals(positions, risk, storage, notifier, market, show_names)

    if positions:
        print("\n=== 보유 종목 현황 ===")
        alerts_by_symbol = {signal.symbol: signal.signal_type for _, signal in exit_signals}
        for position in positions:
            name_part = f" {resolve_symbol_name(position.symbol, market)}" if show_names else ""
            pnl_pct = position.pnl_pct * 100
            alert = alerts_by_symbol.get(position.symbol, "-")
            print(
                f"{position.symbol}{name_part} qty={position.qty} avg={position.avg_price:.2f} "
                f"last={position.last_price:.2f} pnl={pnl_pct:.2f}% exit={alert}"
            )
    else:
        print("\n보유 중인 포지션이 없습니다.")

    storage.log_event(
        "INFO",
        f"scan completed with {len(signals)} signals / {len(exit_signals)} exit alerts",
    )
    return 0


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="v5 Trader CLI")
    parser.add_argument("--ui", action="store_true", help="Run Streamlit UI instead of CLI output")
    parser.add_argument("--scan", action="store_true", help="Run one-shot screening and exit alerts")
    parser.add_argument("--loop", action="store_true", help="Keep scanning on an interval (use with --scan)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def run_cli_mode(settings: AppSettings) -> int:
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)
    try:
        return run_scan_once(settings, storage, market, broker, notifier, strategy, risk)
    finally:
        storage.close()


def run_scan_mode(settings: AppSettings, loop: bool) -> int:
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)
    try:
        while True:
            exit_code = run_scan_once(settings, storage, market, broker, notifier, strategy, risk)
            if not loop:
                return exit_code
            time.sleep(settings.watch.refresh_sec)
    finally:
        storage.close()


def run_ui_mode() -> int:
    ui_path = Path(__file__).with_name("ui_streamlit.py")
    if not ui_path.exists():
        logging.error("UI 파일을 찾을 수 없습니다: %s", ui_path)
        return 1

    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ui_path),
        "--client.showErrorDetails=true",
    ]
    logging.info("Launching Streamlit: %s", " ".join(cmd))
    try:
        return subprocess.call(cmd, env=env)
    except FileNotFoundError:
        logging.error("Streamlit 실행 실패: streamlit 모듈이 설치되어 있는지 확인하세요.")
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        settings = load_settings()
    except Exception as exc:  # pragma: no cover
        logging.exception("Failed to load settings: %s", exc)
        print("설정 로드에 실패했습니다. 로그를 확인하세요.", file=sys.stderr)
        return 1

    if args.ui:
        return run_ui_mode()

    if args.scan:
        return run_scan_mode(settings, loop=args.loop)

    return run_cli_mode(settings)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
