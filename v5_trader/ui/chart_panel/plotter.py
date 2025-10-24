"""Chart plotting utilities using Plotly."""
from __future__ import annotations

from typing import List

import pandas as pd
import plotly.graph_objs as go

from v5_trader.core.data_engine.database import PriceCandle


def plot_price_chart(candles: List[PriceCandle], title: str) -> go.Figure:
    df = pd.DataFrame(
        {
            "Date": [c.date for c in candles],
            "Open": [c.open for c in candles],
            "High": [c.high for c in candles],
            "Low": [c.low for c in candles],
            "Close": [c.close for c in candles],
            "Volume": [c.volume for c in candles],
        }
    )
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df["Date"],
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name="Price",
            )
        ]
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Price",
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.add_trace(
        go.Bar(
            x=df["Date"],
            y=df["Volume"],
            name="Volume",
            marker_color="rgba(78, 243, 196, 0.6)",
            yaxis="y2",
        )
    )
    fig.update_layout(
        yaxis2=dict(
            title="Volume",
            overlaying="y",
            side="right",
            showgrid=False,
        )
    )
    return fig
