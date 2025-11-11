"""Pydantic models used by the FastAPI layer."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CandleOut(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    model_config = dict(populate_by_name=True)


class SignalOut(BaseModel):
    symbol: str
    name: Optional[str] = None
    score: float
    reasons: List[str] = Field(default_factory=list)


class PositionOut(BaseModel):
    symbol: str
    name: str
    qty: int
    avg_price: float
    last_price: float
    pnl_pct: float
    exit_signal: Optional[str] = None

    model_config = dict(populate_by_name=True)


class HoldingsResponse(BaseModel):
    positions: List[PositionOut]
    cash: float = 0.0


class RecommendationCard(BaseModel):
    symbol: str
    name: str
    score: float
    reasons: List[str] = Field(default_factory=list)


class RecommendationsResponse(BaseModel):
    items: List[RecommendationCard]


class CandleSeriesResponse(BaseModel):
    candles: List[CandleOut]


class OrderRequest(BaseModel):
    symbol: str
    side: str
    qty: int
    price_type: str = Field(default="market", alias="priceType")
    limit_price: float | None = Field(default=None, alias="limitPrice")
    approve: bool = False

    model_config = dict(populate_by_name=True)


class OrderResponse(BaseModel):
    ok: bool
    order_id: Optional[str] = None
    message: str = ""
