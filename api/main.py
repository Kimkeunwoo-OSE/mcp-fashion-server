"""FastAPI entrypoint for the v5 Trader backend."""

from __future__ import annotations

import logging
from typing import List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api import schemas
from api.deps import (
    build_dependencies,
    collect_candles,
    resolve_symbol_name,
    resolve_universe,
    run_cli,
)
from config.schema import AppSettings, load_settings

logger = logging.getLogger(__name__)

settings: AppSettings = load_settings()
storage, market, broker, notifier, strategy, risk = build_dependencies(settings)

app = FastAPI(title="v5 Trader API", version="0.1.0")

origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5173",
    "tauri://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def _shutdown() -> None:  # pragma: no cover - cleanup hook
    try:
        storage.close()
    except Exception:
        logger.debug("Storage already closed")


@app.get("/api/health", response_model=dict)
def health() -> dict:
    return {"ok": True}


@app.get("/api/settings", response_model=dict)
def get_settings() -> dict:
    return {
        "watch": settings.watch.model_dump(),
        "trade": settings.trade.model_dump(),
        "chart": settings.chart.model_dump(),
        "risk": settings.risk.model_dump(),
    }


@app.get("/api/holdings", response_model=schemas.HoldingsResponse)
def get_holdings() -> schemas.HoldingsResponse:
    positions = list(broker.get_positions())
    if not positions:
        return schemas.HoldingsResponse(positions=[], cash=0.0)

    symbols = {pos.symbol for pos in positions}
    candles = collect_candles(market, symbols, limit=2)

    items: List[schemas.PositionOut] = []
    for pos in positions:
        last_candles = candles.get(pos.symbol) or []
        if last_candles:
            pos.last_price = last_candles[-1].close
            if pos.avg_price:
                pos.pnl_pct = (pos.last_price - pos.avg_price) / pos.avg_price
        exit_signal = risk.evaluate_exit(pos)
        items.append(
            schemas.PositionOut(
                symbol=pos.symbol,
                name=resolve_symbol_name(pos.symbol, market),
                qty=pos.qty,
                avg_price=pos.avg_price,
                last_price=pos.last_price,
                pnl_pct=pos.pnl_pct,
                exit_signal=exit_signal.message if exit_signal else None,
            )
        )
    return schemas.HoldingsResponse(positions=items, cash=0.0)


@app.get("/api/reco", response_model=schemas.RecommendationsResponse)
def get_recommendations(top: int = Query(default=5, ge=1, le=20)) -> schemas.RecommendationsResponse:
    symbols = resolve_universe(settings, market)
    signals = run_cli(strategy, market, symbols, top)
    cards = [
        schemas.RecommendationCard(
            symbol=signal.symbol,
            name=signal.name or resolve_symbol_name(signal.symbol, market),
            score=signal.score,
            reasons=signal.reasons,
        )
        for signal in signals[:top]
    ]
    return schemas.RecommendationsResponse(items=cards)


@app.get("/api/candles", response_model=schemas.CandleSeriesResponse)
def get_candles(symbol: str, tf: str = "D", limit: int = 120) -> schemas.CandleSeriesResponse:
    series = list(market.get_candles(symbol, timeframe=tf, limit=limit))
    candles = [
        schemas.CandleOut(
            symbol=candle.symbol,
            timestamp=candle.timestamp,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
        )
        for candle in series
    ]
    return schemas.CandleSeriesResponse(candles=candles)


@app.get("/api/name", response_model=dict)
def get_name(symbol: str) -> dict:
    return {"symbol": symbol, "name": resolve_symbol_name(symbol, market)}


@app.post("/api/order", response_model=schemas.OrderResponse)
def place_order(payload: schemas.OrderRequest) -> schemas.OrderResponse:
    if not payload.approve:
        raise HTTPException(status_code=400, detail="승인 필요(자동매매 금지)")
    result = broker.place_order(
        payload.symbol,
        payload.side.upper(),
        int(payload.qty),
        payload.price_type,
        payload.limit_price,
    )
    return schemas.OrderResponse(**result)
