from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests

from config.schema import AppSettings as Settings
from core.entities import Candle
from core.symbols import get_name  # noqa: F401  # 일관성을 위해 유지
from ports.market_data import IMarketData

try:  # pragma: no cover - Python 3.10 fallback
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

BASE_VTS = "https://openapivts.koreainvestment.com:29443"
BASE_PROD = "https://openapi.koreainvestment.com:9443"

TR_DAILY = "FHKST01010400"
TR_PRICE = "FHKST01010100"

PATH_DAILY = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
PATH_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-price"

DEFAULT_TIMEOUT = 10

JSON = dict[str, object]


@dataclass
class KisAuth:
    appkey: str
    appsecret: str
    access_token: str


def _base_url(settings: Settings) -> str:
    return BASE_VTS if settings.kis.paper else BASE_PROD


def _strip_suffix(symbol: str) -> str:
    return symbol.split(".")[0].strip()


def _load_keys(settings: Settings) -> Optional[KisAuth]:
    path = settings.kis.keys_path
    if not os.path.exists(path):
        logger.warning("KIS 키 파일이 없습니다: %s (KIS 비활성)", path)
        return None
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("KIS 키 파일 파싱 실패: %s", exc)
        return None

    try:
        auth = data["auth"]
        appkey = auth["appkey"]
        appsecret = auth["appsecret"]
        token = auth.get("access_token", "")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("KIS 키 정보가 누락되었습니다: %s", exc)
        return None

    if not token.startswith("Bearer "):
        logger.warning("KIS access_token 형식이 올바르지 않습니다. 'Bearer ' 접두사가 필요합니다.")
    return KisAuth(appkey=appkey, appsecret=appsecret, access_token=token)


def _headers(auth: KisAuth, tr_id: str) -> dict[str, str]:
    return {
        "content-type": "application/json",
        "authorization": auth.access_token,
        "appkey": auth.appkey,
        "appsecret": auth.appsecret,
        "appKey": auth.appkey,
        "appSecret": auth.appsecret,
        "tr_id": tr_id,
    }


def _req(
    session: requests.Session,
    method: str,
    url: str,
    headers: dict[str, str],
    params: dict[str, str],
) -> requests.Response:
    response = session.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response


class MarketKIS(IMarketData):
    """KIS 시세 어댑터."""

    provider = "kis"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.auth = _load_keys(settings)
        self.enabled = self.auth is not None
        if not self.enabled:
            logger.warning("MarketKIS 비활성 (키/토큰 미설정)")

    def get_candles(self, symbol: str, timeframe: str = "D", limit: int = 120) -> Iterable[Candle]:
        if not self.enabled:
            return []
        if timeframe != "D":
            logger.warning("KIS 어댑터는 현재 일봉(D)만 지원합니다. (요청: %s)", timeframe)
            return []

        sym6 = _strip_suffix(symbol)
        base = _base_url(self.settings)
        params_daily = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": sym6,
            "fid_period_div_code": "D",
            "fid_org_adj_prc": "1",
        }
        params_price = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": sym6,
        }

        candles: List[Candle] = []
        with requests.Session() as session:
            try:
                logger.debug(
                    "KIS 일별 시세 요청(base=%s, tr_id=%s, params=%s)",
                    base,
                    TR_DAILY,
                    params_daily,
                )
                response = _req(
                    session,
                    "GET",
                    f"{base}{PATH_DAILY}",
                    _headers(self.auth, TR_DAILY),
                    params_daily,
                )
                data = response.json()
                items = data.get("output", {}).get("prc") if isinstance(data.get("output"), dict) else data.get("output")
                if not isinstance(items, list):
                    items = []
                for item in items[:limit]:
                    candle = _parse_candle(symbol, item)
                    if candle:
                        candles.append(candle)
                candles.sort(key=lambda c: c.timestamp)
                if candles:
                    return candles
            except requests.HTTPError as exc:
                logger.error("KIS 시세 조회 실패(%s): %s", symbol, exc)
                logger.debug(
                    "KIS 실패 상세(base=%s, mode=%s, tr_id=%s, params=%s)",
                    base,
                    "VTS" if self.settings.kis.paper else "PROD",
                    TR_DAILY,
                    params_daily,
                )
            except Exception as exc:
                logger.exception("KIS 일별 시세 처리 중 예외(%s): %s", symbol, exc)

            try:
                logger.debug(
                    "KIS 현재가 폴백 요청(base=%s, tr_id=%s, params=%s)",
                    base,
                    TR_PRICE,
                    params_price,
                )
                response = _req(
                    session,
                    "GET",
                    f"{base}{PATH_PRICE}",
                    _headers(self.auth, TR_PRICE),
                    params_price,
                )
                data = response.json()
                output = data.get("output", {}) if isinstance(data, dict) else {}
                candle = _candle_from_price(symbol, output)
                if candle:
                    candles.append(candle)
            except Exception as exc:
                logger.exception("KIS 현재가 폴백 실패(%s): %s", symbol, exc)

        return candles

    def get_themes(self) -> list[str]:
        return []


def _parse_candle(symbol: str, item: JSON) -> Optional[Candle]:
    try:
        timestamp = _parse_dt(item.get("stck_bsop_date"))
        open_price = _safe_float(item.get("stck_oprc"))
        high_price = _safe_float(item.get("stck_hgpr"), default=open_price)
        low_price = _safe_float(item.get("stck_lwpr"), default=open_price)
        close_price = _safe_float(item.get("stck_clpr"), default=open_price)
        volume = _safe_float(item.get("acml_vol"))
        return Candle(
            symbol=symbol,
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("KIS 캔들 파싱 실패(%s): %s", symbol, exc)
        return None


def _candle_from_price(symbol: str, data: JSON) -> Optional[Candle]:
    try:
        price = _safe_float(data.get("stck_prpr"))
        volume = _safe_float(data.get("acml_vol"))
        return Candle(
            symbol=symbol,
            timestamp=_now_dt(),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("KIS 현재가 파싱 실패(%s): %s", symbol, exc)
        return None


def _parse_dt(value: object) -> "datetime":
    from datetime import datetime

    try:
        if isinstance(value, str):
            return datetime.strptime(value, "%Y%m%d")
        if isinstance(value, (int, float)):
            return datetime.strptime(str(int(value)), "%Y%m%d")
    except Exception:  # pragma: no cover - fallback
        pass
    return _now_dt()


def _now_dt():
    from datetime import datetime

    return datetime.now()


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - fallback
        return default
