from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from core.entities import Position


@dataclass(slots=True)
class RiskLimits:
    stop_loss_pct: float = 0.07
    take_profit_pct: float = 0.18
    trailing_pct: float = 0.03
    daily_loss_limit_r: float = -3.0
    hard_loss_limit_pct: float = 0.05
    max_positions: int = 3


class RiskManager:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def should_stop_loss(self, position: Position, current_price: float) -> bool:
        if position.avg_price == 0:
            return False
        change = (current_price - position.avg_price) / position.avg_price
        return change <= -self.limits.stop_loss_pct

    def should_take_profit(self, position: Position, current_price: float) -> bool:
        if position.avg_price == 0:
            return False
        change = (current_price - position.avg_price) / position.avg_price
        return change >= self.limits.take_profit_pct

    def should_trail(self, peak_price: float, current_price: float) -> bool:
        if peak_price == 0:
            return False
        drawdown = (peak_price - current_price) / peak_price
        return drawdown >= self.limits.trailing_pct

    def should_halt_trading(self, cumulative_r: float) -> bool:
        return cumulative_r <= self.limits.daily_loss_limit_r

    def can_open_position(self, current_positions: int) -> bool:
        return current_positions < self.limits.max_positions

    def describe(self) -> Dict[str, float]:
        return {
            "stop_loss_pct": self.limits.stop_loss_pct,
            "take_profit_pct": self.limits.take_profit_pct,
            "trailing_pct": self.limits.trailing_pct,
            "daily_loss_limit_r": self.limits.daily_loss_limit_r,
            "max_positions": self.limits.max_positions,
        }

    def evaluate_position(self, position: Position, current_price: float, peak_price: float | None = None) -> dict[str, bool]:
        return {
            "stop_loss": self.should_stop_loss(position, current_price),
            "take_profit": self.should_take_profit(position, current_price),
            "trail": self.should_trail(peak_price or current_price, current_price),
        }
