"""Mock data loaders for offline demonstration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from v5_trader.core.data_engine.database import PriceCandle


@dataclass
class MockDataset:
    symbol: str
    candles: List[PriceCandle]


def load_mock_candles(symbol: str = "005930.KS") -> MockDataset:
    """Load mock candles from the assets directory."""

    csv_path = Path(__file__).resolve().parents[3] / "ui" / "assets" / "mock_data" / "sample_prices.csv"
    df = pd.read_csv(csv_path, parse_dates=["date"])
    candles = [
        PriceCandle(
            symbol=row["symbol"],
            date=row["date"].to_pydatetime(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=int(row["volume"]),
        )
        for _, row in df.iterrows()
    ]
    return MockDataset(symbol=symbol, candles=candles)


def available_symbols() -> Iterable[str]:
    """Return the symbols present in the mock dataset."""

    dataset = load_mock_candles()
    return {dataset.symbol}
