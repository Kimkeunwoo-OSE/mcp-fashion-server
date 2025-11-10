from __future__ import annotations

from core.entities import ExitSignal, Position
from core.risk import RiskConfig, RiskManager, evaluate_exit


def make_position(avg: float, last: float) -> Position:
    return Position(symbol="AAA", qty=10, avg_price=avg, last_price=last)


def test_evaluate_exit_stop_loss():
    config = RiskConfig(stop_loss_pct=0.05)
    pos = make_position(100.0, 94.0)
    signal = evaluate_exit(pos, config)
    assert isinstance(signal, ExitSignal)
    assert signal.signal_type == "stop_loss"


def test_evaluate_exit_take_profit_and_trailing():
    config = RiskConfig(take_profit_pct=0.1, trailing_pct=0.02)
    pos = make_position(100.0, 115.0)
    signal = evaluate_exit(pos, config)
    assert signal and signal.signal_type == "take_profit"

    pos = Position(symbol="AAA", qty=10, avg_price=100.0, last_price=110.0, trail_stop=120.0)
    signal = evaluate_exit(pos, config)
    assert signal and signal.signal_type == "trailing"


def test_risk_manager_capacity():
    manager = RiskManager(RiskConfig(max_positions=3))
    assert manager.can_open_position(2) is True
    assert manager.can_open_position(3) is False
