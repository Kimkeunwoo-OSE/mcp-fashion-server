from __future__ import annotations

from core.entities import Position
from core.risk import RiskLimits, RiskManager


def test_stop_loss_trigger():
    manager = RiskManager(RiskLimits(stop_loss_pct=0.05))
    position = Position(symbol="AAA", qty=10, avg_price=100.0)
    assert manager.should_stop_loss(position, 94.0) is True
    assert manager.should_stop_loss(position, 97.0) is False


def test_take_profit_and_trail():
    manager = RiskManager(RiskLimits(take_profit_pct=0.1, trailing_pct=0.02))
    position = Position(symbol="AAA", qty=10, avg_price=100.0)
    assert manager.should_take_profit(position, 115.0) is True
    assert manager.should_trail(120.0, 117.0) is True
    assert manager.should_trail(120.0, 119.5) is False


def test_daily_stop_and_capacity():
    manager = RiskManager(RiskLimits(daily_loss_limit_r=-2.0, max_positions=3))
    assert manager.should_halt_trading(-2.1) is True
    assert manager.can_open_position(2) is True
    assert manager.can_open_position(3) is False
