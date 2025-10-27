from __future__ import annotations

import logging
import time
import uuid
from typing import Dict

from core.entities import Position
from ports.broker import IBroker

logger = logging.getLogger(__name__)


class MockBroker(IBroker):
    """In-memory mock broker that also persists to SQLite storage."""

    def __init__(self, storage) -> None:
        self.storage = storage
        self.orders: Dict[str, dict] = {}
        self.positions: Dict[str, Position] = {}

    def place_order(self, symbol: str, side: str, qty: int, price: float | None = None) -> bool:
        if side not in {"buy", "sell"}:
            logger.warning("Unsupported side %s", side)
            return False
        if qty <= 0:
            logger.warning("Quantity must be positive: %s", qty)
            return False
        price = price or 0.0
        order_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.orders[order_id] = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "status": "filled",
            "ts": timestamp,
        }
        self.storage.record_trade(
            order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            ts=timestamp,
        )
        self._update_position(symbol, side, qty, price, timestamp)
        logger.info("Mock order filled: %s", order_id)
        return True

    def amend(self, order_id: str, **kwargs) -> bool:
        order = self.orders.get(order_id)
        if not order:
            logger.warning("Order %s not found", order_id)
            return False
        order.update(kwargs)
        self.storage.log_event("INFO", f"Order amended: {order_id}")
        return True

    def cancel(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if not order:
            logger.warning("Order %s not found", order_id)
            return False
        order["status"] = "cancelled"
        self.storage.log_event("INFO", f"Order cancelled: {order_id}")
        return True

    def get_positions(self):
        return self.storage.get_positions()

    def _update_position(self, symbol: str, side: str, qty: int, price: float, ts: str) -> None:
        existing = self.positions.get(symbol)
        sign = 1 if side == "buy" else -1
        qty_change = sign * qty
        if not existing:
            new_qty = qty_change
            avg_price = price if new_qty else 0.0
        else:
            new_qty = existing.qty + qty_change
            if new_qty:
                total_cost = existing.avg_price * existing.qty + price * qty_change
                avg_price = total_cost / new_qty if new_qty else 0.0
            else:
                avg_price = 0.0
        new_qty = int(new_qty)
        position = Position(symbol=symbol, qty=new_qty, avg_price=avg_price)
        self.positions[symbol] = position
        self.storage.upsert_position(position, ts)
