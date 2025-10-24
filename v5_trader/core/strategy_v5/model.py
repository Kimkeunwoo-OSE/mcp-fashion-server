"""Implementation of the v5 Next-Day Surge Probability Strategy."""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.linear_model import LogisticRegression

from v5_trader.core.data_engine.database import PriceCandle

FEATURE_COLUMNS = ["return", "volatility", "momentum", "range_ratio"]


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
        X_full = df.loc[:, FEATURE_COLUMNS].iloc[5:]
        y_full = (df["return"].shift(-1) > 0.03).iloc[5:]
        X, y = X_full.align(y_full, join="inner", axis=0)
        if X.empty or y.empty:
            self.is_trained = False
            return
        X = X.astype(float)
        y_numeric = y.astype(int)
        mask = np.isfinite(X.to_numpy()).all(axis=1) & np.isfinite(y_numeric.to_numpy(dtype=float))
        X = X.loc[mask]
        y_numeric = y_numeric.loc[mask]
        if X.empty or y_numeric.empty:
            self.is_trained = False
            return
        self.model.fit(X, y_numeric)
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
            proba = self.model.predict_proba(df[FEATURE_COLUMNS])
            surge_prob = float(proba[0][1])
            confidence = 0.7
        target_price = latest.close * (1 + surge_prob * 0.05)
        return StrategyResult(
            symbol=latest.symbol,
            surge_probability=surge_prob,
            target_price=target_price,
            confidence=confidence,
        )
