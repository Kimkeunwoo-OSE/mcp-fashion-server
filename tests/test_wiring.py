from __future__ import annotations


from app.main import DEFAULT_SYMBOLS, build_dependencies, run_cli, run_cli_mode
from config.schema import AppSettings


def test_wiring_produces_named_signals(tmp_path):
    settings = AppSettings.model_validate(
        {
            "db": {"path": str(tmp_path / "test.db")},
            "notifier": {"type": "none"},
            "display": {"show_names": True},
        }
    )
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)

    signals = run_cli(strategy, market, DEFAULT_SYMBOLS[:5])
    assert len(signals) == 3
    assert all(signal.name for signal in signals)

    exit_code = run_cli_mode(settings)
    assert exit_code == 0


def test_kis_mode_without_keys(tmp_path):
    settings = AppSettings.model_validate(
        {
            "db": {"path": str(tmp_path / "kis.db")},
            "market": {"provider": "kis"},
            "broker": {"provider": "kis"},
            "kis": {"keys_path": str(tmp_path / "missing.toml")},
            "notifier": {"type": "none"},
        }
    )
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)

    signals = run_cli(strategy, market, DEFAULT_SYMBOLS[:3])
    assert len(signals) == 3
    assert broker.place_order("005930.KS", "buy", 1, price=100.0) is False
