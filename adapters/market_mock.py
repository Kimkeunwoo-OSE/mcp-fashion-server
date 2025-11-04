from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Iterable, List

from core.entities import Candle
from core.symbols import iter_default_symbols
from ports.market_data import IMarketData


__all__ = ["MarketMock", "MockMarketData"]


class MarketMock(IMarketData):
    """Deterministic mock market data generator."""

    SYMBOLS = list(iter_default_symbols())

    THEMES = list(SYMBOLS[:6])

    UNIVERSES = {
        "KOSPI_TOP200": SYMBOLS,
        "KOSDAQ_TOP150": [s for s in SYMBOLS if s.endswith(".KQ")] or SYMBOLS,
    }

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.provider = "mock"
        self.enabled = True

    def _time_delta(self, timeframe: str) -> timedelta:
        if timeframe == "D":
            return timedelta(days=1)
        if timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
            return timedelta(minutes=minutes)
        return timedelta(days=1)

    def get_candles(self, symbol: str, timeframe: str = "D", limit: int = 120) -> Iterable[Candle]:
        rng = random.Random(f"{self.seed}-{symbol}-{timeframe}")
        now = datetime.now(UTC)
        delta = self._time_delta(timeframe)
        price = 50000 + rng.random() * 20000
        candles: List[Candle] = []
        for i in range(limit):
            ts = now - delta * (limit - i)
            drift = rng.uniform(-0.02, 0.02)
            open_price = max(price * (1 + drift / 2), 1000)
            close_price = max(open_price * (1 + rng.uniform(-0.015, 0.02)), 1000)
            high = max(open_price, close_price) * (1 + rng.uniform(0, 0.01))
            low = min(open_price, close_price) * (1 - rng.uniform(0, 0.01))
            volume = 1_000_000 + rng.random() * 500_000
            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=ts,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close_price,
                    volume=volume,
                )
            )
            price = close_price
        return candles

    def get_themes(self) -> list[str]:
        return list(self.THEMES)

    def get_universe(self, name: str, custom: list[str] | None = None) -> list[str]:
        name_upper = (name or "").upper()
        if name_upper == "CUSTOM":
            return list(custom or [])
        return list(self.UNIVERSES.get(name_upper, self.SYMBOLS))


# Backwards compatibility for previous import path
MockMarketData = MarketMock
