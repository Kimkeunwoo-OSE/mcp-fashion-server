from __future__ import annotations


from app.main import DEFAULT_SYMBOLS, build_dependencies, run_cli
from config.schema import AppSettings


def test_wiring_produces_three_signals(tmp_path):
    settings = AppSettings.model_validate({"db": {"path": str(tmp_path / "test.db")}})
    storage, market, broker, notifier, strategy, risk = build_dependencies(settings)

    signals = run_cli(strategy, market, DEFAULT_SYMBOLS[:5])
    assert len(signals) == 3
    assert all(signal.score != 0 for signal in signals)

    notifier.send("integration test")
    storage.log_event("INFO", "integration test complete")
