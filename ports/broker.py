from __future__ import annotations

from typing import Iterable, Protocol

from core.entities import Position


class IBroker(Protocol):
    def place_order(self, symbol: str, side: str, qty: int, price: float | None = None) -> bool: ...

    def amend(self, order_id: str, **kwargs) -> bool: ...

    def cancel(self, order_id: str) -> bool: ...

    def get_positions(self) -> Iterable[Position]: ...
