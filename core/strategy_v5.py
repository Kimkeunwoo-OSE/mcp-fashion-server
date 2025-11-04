from __future__ import annotations

from typing import Iterable

from core.entities import Candle, Signal, top_n_signals
from core.symbols import get_name


class StrategyV5:
    """Rule-based scoring strategy for the v5 Trader rewrite."""

    def __init__(self, settings) -> None:
        self.settings = settings

    def score_symbol(self, candles: Iterable[Candle]) -> tuple[float, list[str]]:
        candles_list = list(candles)
        if len(candles_list) < 2:
            return 0.0, ["데이터 부족"]

        latest = candles_list[-1]
        prev = candles_list[-2]
        change_pct = latest.change_ratio() * 100
        momentum_pct = ((latest.close - prev.close) / prev.close) * 100 if prev.close else 0.0
        volume_values = [c.volume for c in candles_list[-20:]]
        volume_rank = 0.0
        if volume_values:
            rank = sorted(volume_values).index(latest.volume)
            volume_rank = (rank + 1) / len(volume_values)

        intensity = 0.0
        if latest.range_size():
            intensity = latest.body_size() / latest.range_size()

        score = (
            change_pct * self.settings.return_threshold
            + momentum_pct * self.settings.intensity
            + volume_rank * self.settings.volume_rank * 100
            + intensity * 10
        )

        reasons: list[str] = []
        reasons.append(f"일간 변동 {change_pct:.2f}%")
        reasons.append(f"모멘텀 {momentum_pct:.2f}%")
        reasons.append(f"거래량 랭크 {volume_rank:.2f}")
        reasons.append(f"바디/레인지 {intensity:.2f}")
        return score, reasons

    def pick_top_signals(self, candles_by_symbol: dict[str, Iterable[Candle]], top_n: int = 3) -> list[Signal]:
        signals: list[Signal] = []
        for symbol, candles in candles_by_symbol.items():
            score, reasons = self.score_symbol(candles)
            signals.append(
                Signal(symbol=symbol, score=score, reasons=reasons, name=get_name(symbol))
            )
        return top_n_signals(signals, top_n)
