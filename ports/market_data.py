from __future__ import annotations

from typing import Iterable, Protocol

from core.entities import Candle


class IMarketData(Protocol):
    def get_candles(self, symbol: str, timeframe: str = "D", limit: int = 120) -> Iterable[Candle]: ...

    def get_themes(self) -> list[str]: ...
