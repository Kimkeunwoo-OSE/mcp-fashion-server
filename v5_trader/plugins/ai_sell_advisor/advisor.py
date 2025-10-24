"""AI-assisted sell advisor leveraging surge predictions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SellAdvice:
    symbol: str
    suggested_price: float
    rationale: str


class AISellAdvisor:
    """Generate sell targets based on strategy probabilities."""

    def recommend(self, *, symbol: str, surge_probability: float, current_price: float) -> SellAdvice:
        multiplier = 1 + surge_probability * 0.08
        suggested = current_price * multiplier
        rationale = (
            "Target derived from v5 surge probability with adaptive multiplier. "
            "Consider trimming if price exceeds suggestion while probability declines."
        )
        return SellAdvice(symbol=symbol, suggested_price=suggested, rationale=rationale)
