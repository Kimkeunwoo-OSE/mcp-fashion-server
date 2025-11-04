from __future__ import annotations

from datetime import datetime, timedelta

from config.schema import StrategySettings
from core.entities import Candle
from core.strategy_v5 import StrategyV5


def _make_candle(symbol: str, base: datetime, offset: int, close: float, volume: float) -> Candle:
    ts = base + timedelta(days=offset)
    return Candle(
        symbol=symbol,
        timestamp=ts,
        open=close * 0.98,
        high=close * 1.01,
        low=close * 0.97,
        close=close,
        volume=volume,
    )


def test_screen_candidates_orders_by_score():
    base = datetime(2024, 1, 1)
    data = {
        "AAA": [_make_candle("AAA", base, i, 100 + i, 1000 + i * 5) for i in range(30)],
        "BBB": [_make_candle("BBB", base, i, 100 + i * 2.5, 1200 + i * 10) for i in range(30)],
        "CCC": [_make_candle("CCC", base, i, 120 - i * 1.5, 900 + i * 4) for i in range(30)],
    }
    settings = StrategySettings(return_threshold=1.0, intensity=1.0, volume_rank=1.0)
    strategy = StrategyV5(settings)

    signals = strategy.screen_candidates(data, top_n=2)
    assert [signal.symbol for signal in signals] == ["BBB", "AAA"]
    assert all(signal.score != 0 for signal in signals)
    assert all(signal.reasons for signal in signals)
