"""Portfolio statistics dashboard helper."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from v5_trader.core.data_engine.database import DatabaseManager


@dataclass
class PortfolioMetric:
    label: str
    value: float


class StatisticsDashboard:
    """Compute summary metrics for the holdings and orders."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def metrics(self) -> List[PortfolioMetric]:
        holdings = self.db.list_holdings()
        orders = self.db.list_orders()
        total_value = sum(h.quantity * h.average_price for h in holdings)
        realized = sum(o.quantity * o.price if o.side == "SELL" else 0 for o in orders)
        return [
            PortfolioMetric(label="Total Holdings Value", value=total_value),
            PortfolioMetric(label="Realized Sales", value=realized),
            PortfolioMetric(label="Positions", value=len(holdings)),
        ]
