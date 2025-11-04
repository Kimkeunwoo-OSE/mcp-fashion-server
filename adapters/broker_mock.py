from __future__ import annotations

import logging
import time
import uuid
from typing import Dict

from core.entities import Position
from ports.broker import IBroker, OrderResult

logger = logging.getLogger(__name__)


class MockBroker(IBroker):
    """In-memory mock broker that also persists to SQLite storage."""

    def __init__(self, storage) -> None:
        self.storage = storage
        self.orders: Dict[str, dict] = {}
        self.positions: Dict[str, Position] = {}

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        price_type: str,
        limit_price: float | None = None,
    ) -> OrderResult:
        side_norm = side.upper()
        if side_norm not in {"BUY", "SELL"}:
            message = f"Unsupported side {side}"
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        if qty <= 0:
            message = f"Quantity must be positive: {qty}"
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        if price_type not in {"market", "limit"}:
            message = f"Unsupported price type: {price_type}"
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        if price_type == "limit" and (limit_price is None or limit_price <= 0):
            message = "Limit orders require a positive limit_price"
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        existing = self.positions.get(symbol)
        if price_type == "limit":
            price = float(limit_price)
        else:
            price = float(limit_price or (existing.last_price if existing else 0.0))
        order_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.orders[order_id] = {
            "symbol": symbol,
            "side": side_norm,
            "qty": qty,
            "price": price,
            "price_type": price_type,
            "status": "filled",
            "ts": timestamp,
        }
        self.storage.record_trade(
            order_id,
            symbol=symbol,
            side=side_norm,
            qty=qty,
            price=price,
            ts=timestamp,
        )
        self._update_position(symbol, side_norm.lower(), qty, price, timestamp)
        logger.info("Mock order filled: %s", order_id)
        return {"ok": True, "order_id": order_id, "message": "mock filled"}

    def get_positions(self):
        return self.storage.get_positions()

    def _update_position(self, symbol: str, side: str, qty: int, price: float, ts: str) -> None:
        existing = self.positions.get(symbol)
        sign = 1 if side.lower() == "buy" else -1
        qty_change = sign * qty
        if not existing:
            new_qty = qty_change
            avg_price = price if new_qty else 0.0
            trail_stop = price if new_qty > 0 else 0.0
        else:
            new_qty = existing.qty + qty_change
            if new_qty:
                total_cost = existing.avg_price * existing.qty + price * qty_change
                avg_price = total_cost / new_qty if new_qty else 0.0
            else:
                avg_price = 0.0
            trail_stop = max(existing.trail_stop, price)

        new_qty = int(new_qty)
        last_price = price
        pnl_pct = ((last_price - avg_price) / avg_price) if avg_price else 0.0
        position = Position(
            symbol=symbol,
            qty=new_qty,
            avg_price=avg_price,
            last_price=last_price,
            pnl_pct=pnl_pct,
            trail_stop=trail_stop,
            hard_stop=0.0,
            take_profit_price=avg_price * 1.2 if avg_price else 0.0,
        )
        self.positions[symbol] = position
        self.storage.upsert_position(position, ts)
