from __future__ import annotations

from typing import Literal, Protocol, TypedDict

from core.entities import Position


class OrderResult(TypedDict, total=False):
    ok: bool
    order_id: str | None
    message: str


class IBroker(Protocol):
    def place_order(
        self,
        symbol: str,
        side: Literal["BUY", "SELL"],
        qty: int,
        price_type: Literal["market", "limit"],
        limit_price: float | None = None,
    ) -> OrderResult: ...

    def get_positions(self) -> list[Position]: ...
