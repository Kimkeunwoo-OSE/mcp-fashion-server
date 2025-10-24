"""Implementation of the v5 Next-Day Surge Probability Strategy."""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.linear_model import LogisticRegression

from v5_trader.core.data_engine.database import PriceCandle


class StrategyResult(BaseModel):
    symbol: str
    surge_probability: float
    target_price: float
    confidence: float


class SurgeProbabilityModel:
    """A lightweight logistic regression model using engineered features."""

    def __init__(self) -> None:
        self.model = LogisticRegression()
        self.is_trained = False

    @staticmethod
    def _features_from_candles(candles: List[PriceCandle]) -> pd.DataFrame:
        data = [
            {
                "close": candle.close,
                "high": candle.high,
                "low": candle.low,
                "volume": candle.volume,
            }
            for candle in candles
        ]
        df = pd.DataFrame(data)
        df["return"] = df["close"].pct_change().fillna(0.0)
        df["volatility"] = df["return"].rolling(5).std().fillna(0.0)
        df["momentum"] = df["close"].pct_change(3).fillna(0.0)
        df["range_ratio"] = (df["high"] - df["low"]) / df["close"].clip(lower=1e-6)
        return df

    def train(self, candles: List[PriceCandle]) -> None:
        df = self._features_from_candles(candles)
        if len(df) < 10:
            self.is_trained = False
            return
        X = df[["return", "volatility", "momentum", "range_ratio"]][5:]
        y = (df["return"].shift(-1) > 0.03)[5:-1]
        if y.empty:
            self.is_trained = False
            return
        self.model.fit(X, y)
        self.is_trained = True

    def predict(self, candles: List[PriceCandle]) -> StrategyResult:
        if not candles:
            raise ValueError("No candles provided")
        self.train(candles)
        latest = candles[-1]
        df = self._features_from_candles(candles)[-1:]
        if not self.is_trained:
            surge_prob = float(np.clip(df["momentum"].iloc[0] * 5 + 0.5, 0, 1))
            confidence = 0.4
        else:
            proba = self.model.predict_proba(df[["return", "volatility", "momentum", "range_ratio"]])
            surge_prob = float(proba[0][1])
            confidence = 0.7
        target_price = latest.close * (1 + surge_prob * 0.05)
        return StrategyResult(
            symbol=latest.symbol,
            surge_probability=surge_prob,
            target_price=target_price,
            confidence=confidence,
        )
