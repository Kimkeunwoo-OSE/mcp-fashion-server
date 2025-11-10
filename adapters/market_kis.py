from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, List, Optional
from typing import Iterable, List, Optional

import requests

from adapters.kis_auth import BASE_PROD, BASE_VTS, DEFAULT_TIMEOUT, ensure_token
from adapters.storage_sqlite import SQLiteStorage
from config.schema import AppSettings as Settings
from core.entities import Candle
from core.symbols import DEFAULT_SYMBOLS, get_name as fallback_symbol_name  # noqa: F401
from ports.market_data import IMarketData

try:  # pragma: no cover - Python 3.10 fallback
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

TR_DAILY = "FHKST01010400"
TR_PRICE = "FHKST01010100"

PATH_DAILY = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
PATH_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-price"

JSON = dict[str, object]

KOSDAQ_FALLBACK = ["096770.KQ", "051910.KS", "068270.KS", "035720.KS"]


def _strip_suffix(symbol: str) -> str:
    return symbol.split(".")[0].strip()


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


class MarketKIS(IMarketData):
    """한국투자증권 시세 어댑터."""

    provider = "kis"

    def __init__(self, settings: Settings, storage: SQLiteStorage | None = None) -> None:
        self.settings = settings
        self.keys_path = settings.kis.keys_path
        self.is_vts = bool(settings.kis.paper)
        self.bearer = ensure_token(self.keys_path, self.is_vts)
        if not self.bearer:
            logger.warning("KIS 토큰을 확보하지 못했습니다. (키 파일/권한/네트워크 확인)")

        self.appkey = ""
        self.appsecret = ""
        self._load_credentials()
        self.storage = storage
        self._name_cache: Dict[str, str] = {}

    def _load_credentials(self) -> None:
        if not os.path.exists(self.keys_path):
            logger.warning("KIS 키 파일이 없습니다: %s", self.keys_path)
            return
        try:
            with open(self.keys_path, "rb") as file:
                data = tomllib.load(file)
            auth = data.get("auth", {})
            self.appkey = auth.get("appkey", "")
            self.appsecret = auth.get("appsecret", "")
            if not self.appkey or not self.appsecret:
                logger.warning("KIS appkey/appsecret이 설정되지 않았습니다.")
        except Exception as exc:
            logger.warning("KIS 키 파일 파싱 실패: %s", exc)

    def _base(self) -> str:
        return BASE_VTS if self.is_vts else BASE_PROD

    def _headers(self, bearer: str, tr_id: str) -> dict[str, str]:
        return {
            "content-type": "application/json",
            "authorization": bearer,
            "appkey": self.appkey,
            "appsecret": self.appsecret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _call(
        self,
        session: requests.Session,
        path: str,
        tr_id: str,
        params: dict[str, str],
    ) -> requests.Response:
        if not self.bearer:
            raise RuntimeError("KIS bearer token missing")

        url = f"{self._base()}{path}"
        headers = self._headers(self.bearer, tr_id)
        logger.debug(
            "KIS 요청 path=%s base=%s tr_id=%s params=%s", path, self._base(), tr_id, params
        )
        response = session.get(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
        if response.status_code in (401, 403, 500):
            logger.warning(
                "KIS %s -> 재발급/재시도: %s params=%s",
                response.status_code,
                url,
                params,
            )
            self.bearer = ensure_token(self.keys_path, self.is_vts)
            if not self.bearer:
                response.raise_for_status()
            headers = self._headers(self.bearer, tr_id)
            response = session.get(
                url,
                headers=headers,
                params=params,
                timeout=DEFAULT_TIMEOUT,
            )
        response.raise_for_status()
        return response

    def get_candles(self, symbol: str, timeframe: str = "D", limit: int = 120) -> Iterable[Candle]:
        if not self.bearer:
            logger.error("KIS: 토큰 미확보로 시세를 가져올 수 없습니다.")
            return []
        if timeframe != "D":
            logger.warning("KIS 어댑터는 현재 일봉(D)만 지원합니다. (요청: %s)", timeframe)
            return []

        sym6 = _strip_suffix(symbol)
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
                response = self._call(session, PATH_DAILY, TR_DAILY, params_daily)
                data = response.json()
                output = data.get("output", {})
                items = output.get("prc") if isinstance(output, dict) else output
                if not isinstance(items, list):
                    items = []
                for item in items[:limit]:
                    candle = _parse_candle(symbol, item)
                    if candle:
                        candles.append(candle)
                candles.sort(key=lambda candle: candle.timestamp)
                if candles:
                    return candles
            except requests.HTTPError as exc:
                logger.error("KIS 시세 조회 실패(%s): %s", symbol, exc)
                logger.debug(
                    "KIS 실패 상세(base=%s, mode=%s, tr_id=%s, params=%s)",
                    self._base(),
                    "VTS" if self.is_vts else "PROD",
                    TR_DAILY,
                    params_daily,
                )
            except Exception as exc:
                logger.exception("KIS 일별 시세 처리 중 예외(%s): %s", symbol, exc)

            try:
                response = self._call(session, PATH_PRICE, TR_PRICE, params_price)
                payload = response.json()
                output = payload.get("output", {}) if isinstance(payload, dict) else {}
                candle = _candle_from_price(symbol, output)
                if candle:
                    candles.append(candle)
            except Exception as exc:
                logger.error("KIS 현재가 폴백 실패(%s): %s", symbol, exc)
                logger.debug(
                    "KIS 폴백 상세(base=%s, mode=%s, tr_id=%s, params=%s)",
                    self._base(),
                    "VTS" if self.is_vts else "PROD",
                    TR_PRICE,
                    params_price,
                )

        return candles

    def get_themes(self) -> list[str]:
        return []

    def get_universe(self, name: str, custom: list[str] | None = None) -> list[str]:
        upper = (name or "").upper()
        if upper == "CUSTOM":
            return list(custom or self.settings.watch.symbols or [])
        if upper == "KOSDAQ_TOP150":
            kosdaq = [sym for sym in DEFAULT_SYMBOLS if sym.endswith(".KQ")]
            if not kosdaq:
                kosdaq = KOSDAQ_FALLBACK
            return kosdaq
        return list(DEFAULT_SYMBOLS)

    def get_name(self, symbol: str) -> str:
        clean_symbol = (symbol or "").strip()
        if not clean_symbol:
            return clean_symbol

        cached = self._name_cache.get(clean_symbol)
        if cached:
            return cached

        if self.storage:
            stored = self.storage.get_symbol_name(clean_symbol)
            if stored:
                self._name_cache[clean_symbol] = stored
                return stored

        name: Optional[str] = None
        if self.bearer:
            params = {
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": _strip_suffix(clean_symbol),
            }
            with requests.Session() as session:
                try:
                    response = self._call(session, PATH_PRICE, TR_PRICE, params)
                    payload = response.json()
                    if isinstance(payload, dict):
                        output = payload.get("output", {})
                        if isinstance(output, dict):
                            raw_name = output.get("hts_kor_isnm")
                            if isinstance(raw_name, str) and raw_name.strip():
                                name = raw_name.strip()
                except Exception as exc:  # pragma: no cover - defensive fallback
                    logger.debug("KIS 종목명 조회 실패(%s): %s", clean_symbol, exc)

        if not name:
            name = fallback_symbol_name(clean_symbol)

        self._name_cache[clean_symbol] = name
        if self.storage:
            try:
                self.storage.upsert_symbol(clean_symbol, name)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("심볼 이름 저장 실패(%s): %s", clean_symbol, exc)
        return name
