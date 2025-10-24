"""Korea Investment & Securities OpenAPI adapter."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, List

import httpx

from v5_trader.core.data_engine.database import PriceCandle
from v5_trader.core.utils.config import Settings


class KISClient:
    """Minimal client for interacting with the KIS REST API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.kis.url_base.rstrip("/")
        self.session = httpx.Client()

    def _auth_headers(self) -> dict[str, str]:
        return {
            "appkey": self.settings.kis.app_key,
            "appsecret": self.settings.kis.app_secret,
            "tr_id": "FHKST03010100",
        }

    def fetch_daily_candles(self, *, symbol: str, lookback_days: int) -> List[PriceCandle]:
        """Fetch historical candles via the KIS REST endpoint."""

        if not self.settings.kis.app_key:
            raise RuntimeError("KIS credentials missing; enable mock mode or provide keys")

        end_date = datetime.today().date()
        start_date = end_date - timedelta(days=lookback_days)
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
        }
        response = self.session.get(
            f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price",
            headers=self._auth_headers(),
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        items = response.json().get("output", [])
        candles: List[PriceCandle] = []
        for item in items:
            candles.append(
                PriceCandle(
                    symbol=symbol,
                    date=datetime.strptime(item["stck_bsop_date"], "%Y%m%d"),
                    open=float(item["stck_oprc"]),
                    high=float(item["stck_hgpr"]),
                    low=float(item["stck_lwpr"]),
                    close=float(item["stck_clpr"]),
                    volume=int(item["acml_vol"]),
                )
            )
        candles.sort(key=lambda c: c.date)
        return candles

    def fetch_realtime_price(self, symbol: str) -> PriceCandle:
        """Fetch the most recent price using the daily candle endpoint as a fallback."""

        candles = self.fetch_daily_candles(symbol=symbol, lookback_days=2)
        return candles[-1]

    def list_symbols(self) -> Iterable[str]:
        """Return the account's default watchlist.

        This implementation uses a static placeholder because the KIS API
        requires additional endpoints to query user-defined watchlists. Users
        can modify this method to integrate their own logic.
        """

        return {"005930.KS", "000660.KS", "035420.KS"}

    def submit_order(self, *, symbol: str, side: str, quantity: float, price: float) -> dict:
        """Submit an order via KIS (placeholder, user executes manually)."""

        return {
            "status": "manual",
            "message": "Orders are executed manually in v5 Trader.",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
        }
