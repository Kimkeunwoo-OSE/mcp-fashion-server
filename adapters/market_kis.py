from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import requests

from core.entities import Candle
from ports.market_data import IMarketData

try:  # pragma: no cover - Python 3.10 fallback
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

_DAILY_TR_ID_REAL = "FHKST03010100"
_DAILY_TR_ID_PAPER = "VTTC8908R"  # 공식 문서 기준 모의투자 TR ID (일봉)


class MarketKIS(IMarketData):
    """Korea Investment & Securities (KIS) OpenAPI market data adapter."""

    def __init__(
        self,
        keys_path: Path | str,
        paper: bool = True,
        session: Optional[requests.Session] = None,
        timeout: float = 5.0,
    ) -> None:
        self.provider = "kis"
        self.keys_path = Path(keys_path)
        self.paper = paper
        self.timeout = timeout
        self._session = session or requests.Session()
        self._keys = self._load_keys()
        self.enabled = bool(self._keys)
        if not self.enabled:
            logger.warning(
                "KIS 키 파일을 찾을 수 없습니다. (%s) — KIS 시세는 비활성화됩니다.", self.keys_path
            )

    @property
    def _base_url(self) -> str:
        return "https://openapi.koreainvestment.com:9443"

    def _load_keys(self) -> Optional[dict]:
        if not self.keys_path.exists():
            return None
        try:
            with self.keys_path.open("rb") as fh:
                return tomllib.load(fh)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("KIS 키 파일 파싱 실패: %s", exc)
            return None

    def _build_headers(self, tr_id: str) -> dict[str, str]:
        auth = self._keys.get("auth", {}) if self._keys else {}
        headers = {
            "content-type": "application/json; charset=UTF-8",
            "appkey": auth.get("appkey", ""),
            "appsecret": auth.get("appsecret", ""),
            "tr_id": tr_id,
        }
        vt = auth.get("vt")
        if vt:
            headers["authorization"] = f"Bearer {vt}"
        return headers

    def _parse_candle(self, item: dict) -> Optional[Candle]:
        try:
            symbol = item.get("stck_shrn_iscd") or item.get("symbol")
            if not symbol:
                return None
            close_price = float(item.get("stck_clpr") or item.get("close") or 0.0)
            high = float(item.get("stck_hgpr") or item.get("high") or close_price)
            low = float(item.get("stck_lwpr") or item.get("low") or close_price)
            open_price = float(item.get("stck_oprc") or item.get("open") or close_price)
            volume = float(item.get("acml_vol") or item.get("volume") or 0.0)
            date_str = item.get("stck_bsop_date") or item.get("date")
            if date_str:
                # YYYYMMDD 형태를 datetime 으로 변환
                ts = datetime.strptime(str(date_str), "%Y%m%d").replace(tzinfo=timezone.utc)
            else:
                ts = datetime.now(timezone.utc)
        except Exception as exc:  # pragma: no cover - defensive parsing
            logger.warning("KIS 일봉 파싱 실패: %s", exc)
            return None
        return Candle(
            symbol=f"{symbol}.KS" if "." not in symbol else symbol,
            timestamp=ts,
            open=open_price,
            high=high,
            low=low,
            close=close_price,
            volume=volume,
        )

    def get_candles(self, symbol: str, timeframe: str = "D", limit: int = 120) -> Iterable[Candle]:
        if not self.enabled:
            return []
        if timeframe != "D":
            logger.warning("KIS 어댑터는 현재 일봉(D)만 지원합니다. (요청: %s)", timeframe)
            return []

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": symbol.split(".")[0],
            "fid_period_div_code": "D",
            "fid_org_adj_prc": "0",
        }
        tr_id = _DAILY_TR_ID_PAPER if self.paper else _DAILY_TR_ID_REAL
        url = f"{self._base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
        try:
            response = self._session.get(
                url,
                headers=self._build_headers(tr_id),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.warning("KIS 시세 조회 실패(%s): %s", symbol, exc)
            return []
        except ValueError as exc:  # pragma: no cover - JSON parsing
            logger.warning("KIS 응답 파싱 실패(%s): %s", symbol, exc)
            return []

        output = payload.get("output", []) if isinstance(payload, dict) else []
        candles: list[Candle] = []
        if isinstance(output, list):
            for item in output[:limit]:
                candle = self._parse_candle(item)
                if candle:
                    candles.append(candle)
        candles.sort(key=lambda c: c.timestamp)
        return candles

    def get_themes(self) -> list[str]:
        if not self.enabled:
            return []
        # TR ID: VTHR8508R (예시, 테마 조회) — 구현 단순화를 위해 미지원.
        logger.info("KIS 테마 조회는 아직 구현되지 않았습니다. 기본 관심 목록을 사용하세요.")
        return []
