from __future__ import annotations

from app.main import DEFAULT_SYMBOLS, build_dependencies, resolve_universe, run_cli
from config.schema import AppSettings


def test_wiring_produces_named_signals(tmp_path):
    settings = AppSettings.model_validate(
        {
            "db": {"path": str(tmp_path / "test.db")},
            "notifier": {"type": "none"},
            "display": {"show_names": True},
            "watch": {"top_n": 3},
        }
    )
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)
    try:
        signals = run_cli(strategy, market, DEFAULT_SYMBOLS[:5], top_n=3)
        assert len(signals) == 3
        assert all(signal.name for signal in signals)
    finally:
        storage.close()


def test_custom_universe_resolution(tmp_path):
    settings = AppSettings.model_validate(
        {
            "db": {"path": str(tmp_path / "custom.db")},
            "watch": {"universe": "CUSTOM", "symbols": ["AAA", "BBB"], "top_n": 2},
            "notifier": {"type": "none"},
        }
    )
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)
    try:
        symbols = resolve_universe(settings, market)
        assert symbols == ["AAA", "BBB"]
    finally:
        storage.close()
