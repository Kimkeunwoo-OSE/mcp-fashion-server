"""FastAPI backend powering data access for v5 Trader."""
from __future__ import annotations

from typing import List

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from v5_trader.core.alert_manager.manager import AlertManager
from v5_trader.core.data_engine.database import DatabaseManager
from v5_trader.core.data_engine.schemas import (
    HoldingResponse,
    OrderCreate,
    OrderRecord,
    OrderResponse,
    RecommendationResponse,
)
from v5_trader.core.data_engine.market_data import MarketDataService
from v5_trader.core.strategy_v5.engine import StrategyEngine
from v5_trader.core.strategy_v5.model import StrategyResult
from v5_trader.core.utils.config import Settings, load_settings


def get_settings() -> Settings:
    """Resolve application settings with caching support."""

    return load_settings()


def get_db(settings: Settings = Depends(get_settings)) -> DatabaseManager:
    """Instantiate a database manager for the request scope."""

    return DatabaseManager(settings)


def get_market_service(settings: Settings = Depends(get_settings)) -> MarketDataService:
    """Return a market data service configured for the current mode."""

    return MarketDataService(settings)


def get_strategy_engine(
    settings: Settings = Depends(get_settings),
    market: MarketDataService = Depends(get_market_service),
    db: DatabaseManager = Depends(get_db),
) -> StrategyEngine:
    """Build a strategy engine for executing surge predictions."""

    return StrategyEngine(settings, market, db)


def get_alert_manager(settings: Settings = Depends(get_settings)) -> AlertManager:
    """Provide an alert manager to emit surge notifications."""

    return AlertManager(settings)


app = FastAPI(title="v5 Trader API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple liveness probe for monitoring."""

    return {"status": "ok"}


@app.get("/strategy/recommendations", response_model=List[StrategyResult])
def run_strategy(
    engine: StrategyEngine = Depends(get_strategy_engine),
    alerts: AlertManager = Depends(get_alert_manager),
) -> List[StrategyResult]:
    """Execute the v5 strategy across the active watchlist."""

    results = engine.run_batch()
    threshold = engine.settings.alerts.surge_threshold
    for result in results:
        if result.surge_probability >= threshold:
            alerts.dispatch(result)
    return results


@app.get("/orders", response_model=List[OrderRecord])
def list_orders(db: DatabaseManager = Depends(get_db)) -> List[OrderRecord]:
    """Return recorded manual orders for audit and UI display."""

    return [
        OrderRecord(
            id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            timestamp=order.timestamp,
            note=order.note,
        )
        for order in db.list_orders()
    ]


@app.post("/orders", response_model=OrderResponse)
def record_order(order: OrderCreate, db: DatabaseManager = Depends(get_db)) -> OrderResponse:
    saved = db.record_order(symbol=order.symbol, side=order.side, quantity=order.quantity, price=order.price, note=order.note)
    return OrderResponse(id=saved.id, status="recorded", timestamp=saved.timestamp)


@app.get("/holdings", response_model=List[HoldingResponse])
def list_holdings(db: DatabaseManager = Depends(get_db)) -> List[HoldingResponse]:
    """Expose holdings snapshots for the UI and integrations."""

    return [
        HoldingResponse(
            symbol=holding.symbol,
            quantity=holding.quantity,
            average_price=holding.average_price,
            last_updated=holding.last_updated,
        )
        for holding in db.list_holdings()
    ]


@app.get("/recommendations", response_model=List[RecommendationResponse])
def list_recommendations(db: DatabaseManager = Depends(get_db)) -> List[RecommendationResponse]:
    """Return the most recently stored surge recommendations."""

    return [
        RecommendationResponse(
            symbol=rec.symbol,
            run_date=rec.run_date,
            surge_probability=rec.surge_probability,
            target_price=rec.target_price,
            confidence=rec.confidence,
        )
        for rec in db.list_recommendations()
    ]
