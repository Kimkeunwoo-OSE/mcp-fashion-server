from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from core.entities import ExitSignal, Position


class RiskConfigProtocol(Protocol):
    stop_loss_pct: float
    take_profit_pct: float
    trailing_pct: float
    daily_loss_limit_r: float
    max_positions: int


@dataclass(slots=True)
class RiskConfig:
    stop_loss_pct: float = 0.07
    take_profit_pct: float = 0.18
    trailing_pct: float = 0.03
    daily_loss_limit_r: float = -3.0
    max_positions: int = 3


class RiskManager:
    """Evaluate exit signals and track high-level limits."""

    def __init__(self, config: RiskConfigProtocol | None = None) -> None:
        self.config: RiskConfigProtocol = config or RiskConfig()

    def evaluate_exit(self, position: Position) -> ExitSignal | None:
        return evaluate_exit(position, self.config)

    def can_open_position(self, current_positions: int) -> bool:
        return current_positions < self.config.max_positions


def _resolve_pct(position: Position) -> float:
    if position.pnl_pct:
        return position.pnl_pct
    if position.avg_price:
        return (position.last_price - position.avg_price) / position.avg_price
    return 0.0


def evaluate_exit(position: Position, config: RiskConfigProtocol) -> ExitSignal | None:
    """Return the highest-priority exit signal for the position."""

    pnl_pct = _resolve_pct(position)
    now = datetime.now(timezone.utc)

    if pnl_pct <= -abs(config.stop_loss_pct):
        return ExitSignal(
            symbol=position.symbol,
            signal_type="stop_loss",
            message=f"손절 트리거: {pnl_pct * 100:.2f}%",
            triggered_at=now,
        )

    if pnl_pct >= abs(config.take_profit_pct):
        return ExitSignal(
            symbol=position.symbol,
            signal_type="take_profit",
            message=f"익절 트리거: {pnl_pct * 100:.2f}%",
            triggered_at=now,
        )

    if position.trail_stop and config.trailing_pct > 0:
        threshold = position.trail_stop * (1 - config.trailing_pct)
        if position.last_price <= threshold:
            return ExitSignal(
                symbol=position.symbol,
                signal_type="trailing",
                message=f"트레일링 스탑: 현재 {position.last_price:,.2f} ≤ 임계 {threshold:,.2f}",
                triggered_at=now,
            )

    if position.hard_stop and position.last_price <= position.hard_stop:
        return ExitSignal(
            symbol=position.symbol,
            signal_type="hard_stop",
            message=f"하드 스탑: 현재 {position.last_price:,.2f} ≤ {position.hard_stop:,.2f}",
            triggered_at=now,
        )

    return None


def format_exit_message(signal: ExitSignal, name: str | None = None) -> str:
    label = f"{signal.symbol}"
    if name:
        label = f"{label} {name}"
    return f"[v5] 매도 신호({signal.signal_type}): {label} — {signal.message}"[:200]
