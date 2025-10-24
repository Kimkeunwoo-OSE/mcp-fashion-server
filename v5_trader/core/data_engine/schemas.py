"""Pydantic schemas for API payloads."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    symbol: str = Field(..., max_length=32)
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float
    price: float
    note: str | None = None


class OrderResponse(BaseModel):
    id: int
    status: str
    timestamp: datetime


class OrderRecord(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: datetime
    note: str | None = None


class HoldingResponse(BaseModel):
    symbol: str
    quantity: float
    average_price: float
    last_updated: datetime


class RecommendationResponse(BaseModel):
    symbol: str
    run_date: date
    surge_probability: float
    target_price: float
    confidence: float
