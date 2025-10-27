"""Market data acquisition layer."""
from __future__ import annotations

from typing import Iterable, List

from v5_trader.core.broker_api.kis_client import KISClient
from v5_trader.core.broker_api.mock_client import MockBrokerClient
from v5_trader.core.data_engine.database import PriceCandle
from v5_trader.core.data_engine.mock_data import load_mock_candles
from v5_trader.core.utils.config import Settings


class MarketDataService:
    """Service responsible for fetching historical and intraday data."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = MockBrokerClient() if settings.mock_mode else KISClient(settings)

    def fetch_daily_candles(self, symbol: str, lookback_days: int) -> List[PriceCandle]:
        """Retrieve daily candles either from mock dataset or KIS API."""

        if self.settings.mock_mode:
            dataset = load_mock_candles(symbol)
            return dataset.candles[-lookback_days:]

        return self.client.fetch_daily_candles(symbol=symbol, lookback_days=lookback_days)

    def fetch_latest_price(self, symbol: str) -> PriceCandle:
        """Fetch the most recent candle for the symbol."""

        if self.settings.mock_mode:
            dataset = load_mock_candles(symbol)
            return dataset.candles[-1]
        return self.client.fetch_realtime_price(symbol)

    def list_watchlist(self) -> Iterable[str]:
        """Return symbols to evaluate."""

        if self.settings.mock_mode:
            return {load_mock_candles().symbol}
        return self.client.list_symbols()
