"""Strategy orchestration for producing recommendations."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from v5_trader.core.data_engine.database import DatabaseManager, Recommendation
from v5_trader.core.data_engine.market_data import MarketDataService
from v5_trader.core.strategy_v5.model import StrategyResult, SurgeProbabilityModel
from v5_trader.core.utils.config import Settings


class StrategyEngine:
    """Coordinates data loading, model inference, and persistence."""

    def __init__(self, settings: Settings, data_service: MarketDataService, db: DatabaseManager) -> None:
        self.settings = settings
        self.data_service = data_service
        self.db = db
        self.model = SurgeProbabilityModel()

    def run_for_symbol(self, symbol: str) -> StrategyResult:
        candles = self.data_service.fetch_daily_candles(symbol, self.settings.strategy.lookback_days)
        result = self.model.predict(candles)
        with self.db.session() as session:
            record = Recommendation(
                symbol=result.symbol,
                run_date=datetime.utcnow().date(),
                surge_probability=result.surge_probability,
                target_price=result.target_price,
                confidence=result.confidence,
            )
            session.add(record)
            session.commit()
        return result

    def run_batch(self) -> List[StrategyResult]:
        results: List[StrategyResult] = []
        for symbol in self.data_service.list_watchlist():
            try:
                results.append(self.run_for_symbol(symbol))
            except Exception as exc:  # pragma: no cover - logging placeholder
                print(f"Failed to run strategy for {symbol}: {exc}")
        return results
