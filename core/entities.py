from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence


@dataclass(slots=True)
class Candle:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def change_ratio(self) -> float:
        if self.open == 0:
            return 0.0
        return (self.close - self.open) / self.open

    def body_size(self) -> float:
        return abs(self.close - self.open)

    def range_size(self) -> float:
        return self.high - self.low


@dataclass(slots=True)
class Signal:
    symbol: str
    score: float
    reasons: list[str] = field(default_factory=list)

    def summary(self) -> str:
        reasons = ", ".join(self.reasons) if self.reasons else "N/A"
        return f"{self.symbol} (score={self.score:.2f}) — {reasons}"


@dataclass(slots=True)
class Position:
    symbol: str
    qty: int
    avg_price: float
    side: str = "long"

    def market_value(self, last_price: float) -> float:
        return self.qty * last_price

    def unrealized_pnl(self, last_price: float) -> float:
        return (last_price - self.avg_price) * self.qty


def top_n_signals(signals: Iterable[Signal], n: int) -> list[Signal]:
    ordered = sorted(signals, key=lambda s: s.score, reverse=True)
    return ordered[:n]
