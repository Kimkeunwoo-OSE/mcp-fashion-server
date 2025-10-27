from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, Sequence

from adapters.broker_mock import MockBroker
from adapters.market_mock import MockMarketData
from adapters.notifier_windows import WindowsToastNotifier
from adapters.storage_sqlite import SQLiteStorage
from config.schema import AppSettings, load_settings
from core.entities import Signal
from core.risk import RiskManager
from core.strategy_v5 import StrategyV5

DEFAULT_SYMBOLS: Sequence[str] = (
    "005930.KS",  # Samsung Electronics
    "000660.KS",  # SK hynix
    "035420.KS",  # NAVER
    "051910.KS",  # LG Chem
    "068270.KS",  # Celltrion
    "207940.KS",  # Samsung Biologics
)


class NullNotifier:
    """Fallback notifier that logs instead of sending alerts."""

    def send(self, text: str) -> bool:
        logging.getLogger(__name__).warning("Notifier disabled: %s", text)
        return False


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def build_notifier(settings: AppSettings) -> object:
    if settings.notifier.type == "windows":
        return WindowsToastNotifier()
    return NullNotifier()


def build_dependencies(settings: AppSettings):
    storage = SQLiteStorage(Path(settings.db.path))
    market = MockMarketData(seed=42)
    broker = MockBroker(storage=storage)
    notifier = build_notifier(settings)
    strategy = StrategyV5(settings.strategy)
    risk = RiskManager()
    return storage, market, broker, notifier, strategy, risk


def run_cli(strategy: StrategyV5, market: MockMarketData, symbols: Iterable[str]) -> list[Signal]:
    candles_by_symbol = {}
    for symbol in symbols:
        candles_by_symbol[symbol] = list(market.get_candles(symbol, timeframe="D", limit=120))
    return strategy.pick_top_signals(candles_by_symbol, top_n=3)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="v5 Trader CLI")
    parser.add_argument("--ui", action="store_true", help="Run Streamlit UI instead of CLI output")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        settings = load_settings()
    except Exception as exc:  # pragma: no cover - configuration errors should surface immediately
        logging.exception("Failed to load settings: %s", exc)
        print("설정 로드에 실패했습니다. 로그를 확인하세요.", file=sys.stderr)
        return 1

    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)
    logging.getLogger(__name__).info(
        "Running in %s mode with notifier=%s", settings.mode, settings.notifier.type
    )

    if args.ui:
        from .ui_streamlit import run_ui

        run_ui(settings, market, broker, strategy, notifier, storage, risk)
        return 0

    try:
        signals = run_cli(strategy, market, DEFAULT_SYMBOLS)
    except Exception as exc:
        logging.exception("Execution failed: %s", exc)
        print("애플리케이션 실행 중 오류가 발생했습니다. 로그를 확인하세요.", file=sys.stderr)
        return 1

    print("=== v5 Trader 추천 종목 ===")
    for idx, signal in enumerate(signals, start=1):
        reasons = "; ".join(signal.reasons) if signal.reasons else "N/A"
        print(f"{idx}. {signal.symbol} (score={signal.score:.2f}) - {reasons}")

    notifier.send("v5 Trader 후보가 준비되었습니다.")
    storage.log_event("INFO", "CLI run completed")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
