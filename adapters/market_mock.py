from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Iterable, List

from core.entities import Candle
from ports.market_data import IMarketData


class MockMarketData(IMarketData):
    """Deterministic mock market data generator."""

    SYMBOLS = [
        "005930.KS",
        "000660.KS",
        "035420.KS",
        "051910.KS",
        "068270.KS",
        "207940.KS",
        "035720.KS",
        "105560.KS",
    ]

    THEMES = [
        "005930.KS",
        "000660.KS",
        "035420.KS",
        "051910.KS",
        "068270.KS",
        "207940.KS",
    ]

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

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
