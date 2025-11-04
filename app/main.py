from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

from adapters.broker_kis import BrokerKIS
from adapters.broker_mock import MockBroker
from adapters.market_kis import MarketKIS
from adapters.market_mock import MarketMock
from adapters.notifier_windows import NotifierWindows
from adapters.storage_sqlite import SQLiteStorage
from config.schema import AppSettings, load_settings
from core.entities import Signal
from core.risk import RiskManager
from core.strategy_v5 import StrategyV5
from core.symbols import get_name, iter_default_symbols

DEFAULT_SYMBOLS: Sequence[str] = tuple(iter_default_symbols())


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
        return NotifierWindows()
    return NullNotifier()


def build_market(settings: AppSettings):
    if settings.market.provider == "kis":
        return MarketKIS(settings)
    return MarketMock(seed=42)


def build_broker(settings: AppSettings, storage: SQLiteStorage):
    if settings.broker.provider == "kis":
        return BrokerKIS(
            storage=storage,
            keys_path=Path(settings.kis.keys_path),
            paper=settings.kis.paper,
        )
    return MockBroker(storage=storage)


def build_dependencies(settings: AppSettings):
    storage = SQLiteStorage(Path(settings.db.path))
    market = build_market(settings)
    broker = build_broker(settings, storage)
    notifier = build_notifier(settings)
    strategy = StrategyV5(settings.strategy)
    risk = RiskManager()
    return storage, market, broker, notifier, strategy, risk


def run_cli(strategy: StrategyV5, market, symbols: Iterable[str]) -> list[Signal]:
    candles_by_symbol = {}
    for symbol in symbols:
        candles_by_symbol[symbol] = list(market.get_candles(symbol, timeframe="D", limit=120))
    return strategy.pick_top_signals(candles_by_symbol, top_n=3)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="v5 Trader CLI")
    parser.add_argument("--ui", action="store_true", help="Run Streamlit UI instead of CLI output")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def run_cli_mode(settings: AppSettings) -> int:
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)
    logging.getLogger(__name__).info(
        "Running CLI in %s mode with market=%s broker=%s notifier=%s",
        settings.mode,
        getattr(market, "provider", "unknown"),
        getattr(broker, "provider", "unknown"),
        settings.notifier.type,
    )

    try:
        signals = run_cli(strategy, market, DEFAULT_SYMBOLS)
    except Exception as exc:
        logging.exception("Execution failed: %s", exc)
        print("애플리케이션 실행 중 오류가 발생했습니다. 로그를 확인하세요.", file=sys.stderr)
        return 1

    print("=== v5 Trader 추천 종목 ===")
    if not signals:
        print("추천 신호가 없습니다. 설정을 확인하세요.")
    for idx, signal in enumerate(signals, start=1):
        reasons = "; ".join(signal.reasons) if signal.reasons else "N/A"
        display_name = signal.name if settings.display.show_names else None
        name_part = f" {display_name}" if display_name else ""
        print(f"{idx}. {signal.symbol}{name_part} (score={signal.score:.2f}) - {reasons}")

    if signals:
        top = signals[0]
        top_name = top.name or get_name(top.symbol)
        message = f"[v5] 추천: {top.symbol} {top_name} | score={top.score:.2f}"[:200]
    else:
        message = "v5 Trader 후보가 없습니다."

    try:
        notifier.send(message)
    except Exception as exc:  # pragma: no cover - defensive guard
        logging.getLogger(__name__).warning("Notifier send failed: %s", exc)

    storage.log_event("INFO", f"CLI run completed with {len(signals)} signals")
    return 0


def run_ui_mode() -> int:
    """Launch the Streamlit UI via subprocess."""

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

    return run_cli_mode(settings)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
