from __future__ import annotations

from typing import Protocol

from core.entities import Position


class IBroker(Protocol):
    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        price: float | None = None,
        *,
        require_user_confirm: bool = False,
    ) -> bool: ...

    def amend(self, order_id: str, **kwargs) -> bool: ...

    def cancel(self, order_id: str) -> bool: ...

    def get_positions(self) -> list[Position]: ...
