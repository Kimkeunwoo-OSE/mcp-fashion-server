from __future__ import annotations

import math
import statistics
from typing import Iterable

from core.entities import Candle, Signal, top_n_signals
from core.symbols import get_name


class StrategyV5:
    """Rule-based scoring strategy for the v5 Trader rewrite."""

    def __init__(self, settings) -> None:
        self.settings = settings

    def score_symbol(self, candles: Iterable[Candle]) -> tuple[float, list[str]]:
        candles_list = list(candles)
        if len(candles_list) < 10:
            return 0.0, ["데이터 부족"]

        latest = candles_list[-1]
        prev = candles_list[-2]
        change_pct = ((latest.close - prev.close) / prev.close) * 100 if prev.close else 0.0

        lookback = min(20, len(candles_list) - 1)
        momentum_basis = candles_list[-(lookback + 1)]
        momentum_pct = (
            ((latest.close - momentum_basis.close) / momentum_basis.close) * 100
            if momentum_basis.close
            else 0.0
        )

        returns = []
        for older, newer in zip(candles_list[-(lookback + 1) : -1], candles_list[-lookback:]):
            if older.close:
                returns.append((newer.close - older.close) / older.close)
        volatility = statistics.pstdev(returns) * 100 if len(returns) > 1 else 0.0

        volumes = [c.volume for c in candles_list[-20:]]
        volume_rank = 0.0
        if volumes:
            sorted_vol = sorted(volumes)
            try:
                rank = sorted_vol.index(latest.volume)
            except ValueError:
                rank = len(sorted_vol) - 1
            volume_rank = (rank + 1) / len(sorted_vol)

        range_ratio = 0.0
        if latest.range_size():
            range_ratio = latest.body_size() / latest.range_size()

        score = (
            change_pct * self.settings.return_threshold
            + momentum_pct * self.settings.intensity
            + (1 - min(volatility, 10) / 10) * 20
            + volume_rank * self.settings.volume_rank * 100
            + range_ratio * 15
        )

        reasons = [
            f"일간 변동 {change_pct:.2f}%",
            f"{lookback}일 모멘텀 {momentum_pct:.2f}%",
            f"변동성 {volatility:.2f}%",
            f"거래량 랭크 {volume_rank:.2f}",
            f"바디/레인지 {range_ratio:.2f}",
        ]
        return score, reasons

    def screen_candidates(
        self, candles_by_symbol: dict[str, Iterable[Candle]], top_n: int
    ) -> list[Signal]:
        signals: list[Signal] = []
        for symbol, candles in candles_by_symbol.items():
            score, reasons = self.score_symbol(candles)
            if not math.isfinite(score):
                continue
            signals.append(
                Signal(symbol=symbol, score=score, reasons=reasons, name=get_name(symbol))
            )
        return top_n_signals(signals, top_n)

    def pick_top_signals(
        self, candles_by_symbol: dict[str, Iterable[Candle]], top_n: int = 3
    ) -> list[Signal]:
        return self.screen_candidates(candles_by_symbol, top_n)
