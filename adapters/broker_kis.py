from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import requests

from core.entities import Position
from ports.broker import IBroker

try:  # pragma: no cover - Python 3.10 fallback
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

_ORDER_TR_IDS = {
    ("buy", True): "VTTC0802U",
    ("sell", True): "VTTC0801U",
    ("buy", False): "TTTC0802U",
    ("sell", False): "TTTC0801U",
}

_BALANCE_TR_ID = {True: "VTTC8434R", False: "TTTC8434R"}
_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
_BASE_URLS = {
    True: "https://openapivts.koreainvestment.com:29443",
    False: "https://openapi.koreainvestment.com:9443",
}


class BrokerKIS(IBroker):
    """KIS OpenAPI broker adapter with explicit user confirmation guard."""

    def __init__(
        self,
        storage,
        keys_path: Path | str,
        paper: bool = True,
        session: Optional[requests.Session] = None,
        timeout: float = 5.0,
    ) -> None:
        self.storage = storage
        self.provider = "kis"
        self.keys_path = Path(keys_path)
        self.paper = paper
        self.timeout = timeout
        self._session = session or requests.Session()
        self._keys = self._load_keys()
        self.enabled = bool(self._keys)
        if not self.enabled:
            logger.warning(
                "KIS 브로커 키 파일이 없어 주문 기능이 비활성화됩니다: %s", self.keys_path
            )
        account = (self._keys or {}).get("account", {})
        self._cano, self._acnt_prdt_cd = self._split_account(account.get("accno", ""))

    @property
    def _base_url(self) -> str:
        return _BASE_URLS[self.paper]

    def _load_keys(self) -> Optional[dict]:
        if not self.keys_path.exists():
            return None
        try:
            with self.keys_path.open("rb") as fh:
                return tomllib.load(fh)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("KIS 키 파일 파싱 실패: %s", exc)
            return None

    def _split_account(self, acc: str) -> tuple[str, str]:
        clean = acc.replace("-", "").strip()
        if len(clean) >= 10:
            return clean[:8], clean[8:10]
        if clean:
            return clean, "01"
        return "", "01"

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

    def _request(self, method: str, path: str, tr_id: str, payload: dict) -> Optional[dict]:
        if method.upper() != "POST":  # 현재 주문만 지원
            raise ValueError("Unsupported method")
        url = f"{self._base_url}{path}"
        try:
            response = self._session.post(
                url,
                headers=self._build_headers(tr_id),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.warning("KIS 요청 실패(%s): %s", tr_id, exc)
        except ValueError as exc:  # pragma: no cover - JSON parsing
            logger.warning("KIS 응답 파싱 실패(%s): %s", tr_id, exc)
        return None

    # --- IBroker interface -------------------------------------------------
    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        price: float | None = None,
        *,
        require_user_confirm: bool = False,
    ) -> bool:
        if side not in {"buy", "sell"}:
            logger.warning("지원하지 않는 주문 방향: %s", side)
            return False
        if qty <= 0:
            logger.warning("수량은 양수여야 합니다: %s", qty)
            return False
        if not self.enabled:
            logger.warning("KIS 키가 없어 주문을 수행할 수 없습니다. Mock 모드를 사용하세요.")
            return False
        if not require_user_confirm:
            logger.warning("사용자 확인(require_user_confirm)이 필요합니다.")
            return False
        if not self._cano:
            logger.warning("계좌번호(accno)가 설정되지 않았습니다. config/kis.keys.toml 확인")
            return False

        symbol_code = symbol.split(".")[0]
        price_str = "0" if price is None else f"{price:.2f}"
        payload = {
            "CANO": self._cano,
            "ACNT_PRDT_CD": self._acnt_prdt_cd,
            "PDNO": symbol_code,
            "ORD_DVSN": "01",  # 지정가 기본
            "ORD_QTY": str(qty),
            "ORD_UNPR": price_str,
        }
        tr_id = _ORDER_TR_IDS.get((side, self.paper))
        if not tr_id:
            logger.warning("주문 TR_ID를 찾을 수 없습니다. side=%s paper=%s", side, self.paper)
            return False

        result = self._request(
            "POST",
            "/uapi/domestic-stock/v1/trading/order-cash",
            tr_id,
            payload,
        )
        if not result:
            self.storage.log_event(
                "WARNING",
                f"KIS 주문 실패: {symbol} {side} {qty} {price_str}",
            )
            return False

        rt_cd = result.get("rt_cd")
        if rt_cd != "0":
            msg = result.get("msg1") or "주문 거절"
            logger.warning("KIS 주문 거절: %s", msg)
            self.storage.log_event("WARNING", f"KIS 주문 거절: {msg}")
            return False

        output = result.get("output", {})
        ord_no = output.get("ODNO") or result.get("order_no") or "unknown"
        ts = datetime.now(timezone.utc).isoformat()
        self.storage.log_event("INFO", f"KIS 주문 접수: {symbol} {side} {qty} #{ord_no}")
        # API 응답만으로 체결 정보를 알 수 없으므로 trade 테이블에는 기록하지 않는다.
        return True

    def amend(self, order_id: str, **kwargs) -> bool:
        logger.info("KIS 주문 정정은 현재 UI에서 직접 지원하지 않습니다. (order_id=%s)", order_id)
        self.storage.log_event("INFO", f"KIS amend requested: {order_id}")
        return False

    def cancel(self, order_id: str) -> bool:
        logger.info("KIS 주문 취소는 현재 UI에서 직접 지원하지 않습니다. (order_id=%s)", order_id)
        self.storage.log_event("INFO", f"KIS cancel requested: {order_id}")
        return False

    def get_positions(self) -> List[Position]:
        remote = self._fetch_remote_positions()
        if remote:
            return remote
        try:
            return self.storage.get_positions()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("KIS 포지션 조회 실패: %s", exc)
            return []

    def _fetch_remote_positions(self) -> List[Position]:
        if not self.enabled or not self._cano:
            return []
        tr_id = _BALANCE_TR_ID[self.paper]
        params = {
            "CANO": self._cano,
            "ACNT_PRDT_CD": self._acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "N",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        url = f"{self._base_url}{_BALANCE_PATH}"
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
            logger.debug("KIS 잔고 조회 실패(%s): %s", tr_id, exc)
            return []

        items = payload.get("output1") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []

        positions: List[Position] = []
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            try:
                qty = int(float(item.get("hldg_qty", 0)))
                if qty <= 0:
                    continue
                avg_price = float(item.get("pchs_avg_pric", 0) or 0)
                last_price = float(item.get("prpr", 0) or 0)
                symbol = item.get("pdno", "").strip()
                if not symbol:
                    continue
                symbol = f"{symbol}.KS"
                pnl_pct = float(item.get("evlu_pfls_rt", 0) or 0) / 100
                take_profit_price = avg_price * 1.0 + avg_price * 0.2 if avg_price else 0.0
                highest_raw = item.get("hghst_prc", last_price)
                try:
                    highest = float(highest_raw) if highest_raw else last_price
                except (TypeError, ValueError):
                    highest = last_price
                position = Position(
                    symbol=symbol,
                    qty=qty,
                    avg_price=avg_price,
                    last_price=last_price,
                    pnl_pct=pnl_pct,
                    trail_stop=max(last_price, highest),
                    hard_stop=0.0,
                    take_profit_price=take_profit_price,
                )
                positions.append(position)
                self.storage.upsert_position(position, now)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("KIS 포지션 파싱 실패: %s", exc)
        return positions
