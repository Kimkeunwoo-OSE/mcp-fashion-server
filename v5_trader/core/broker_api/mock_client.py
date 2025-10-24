"""Mock broker client replicating a subset of KIS functionality."""
from __future__ import annotations

from typing import Iterable, List

from v5_trader.core.data_engine.database import PriceCandle
from v5_trader.core.data_engine.mock_data import load_mock_candles


class MockBrokerClient:
    """Return deterministic responses for offline demos."""

    def fetch_daily_candles(self, *, symbol: str, lookback_days: int) -> List[PriceCandle]:
        dataset = load_mock_candles(symbol)
        return dataset.candles[-lookback_days:]

    def fetch_realtime_price(self, symbol: str) -> PriceCandle:
        dataset = load_mock_candles(symbol)
        return dataset.candles[-1]

    def list_symbols(self) -> Iterable[str]:
        return {load_mock_candles().symbol}

    def submit_order(self, *, symbol: str, side: str, quantity: float, price: float) -> dict:
        return {
            "status": "mock",
            "message": "Mock mode - no real order executed.",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
        }
