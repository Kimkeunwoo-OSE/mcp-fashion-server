from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

from adapters.kis_auth import BASE_PROD, BASE_VTS, ensure_token
from core.entities import Position
from ports.broker import IBroker, OrderResult

try:  # pragma: no cover - Python 3.10 compatibility
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"

ORDER_TR_ID = {
    ("SELL", True): "VTTC0801U",
    ("SELL", False): "TTTC0801U",
    ("BUY", True): "VTTC0802U",
    ("BUY", False): "TTTC0802U",
}

BALANCE_TR_ID = {True: "VTTC8434R", False: "TTTC8434R"}


@dataclass(slots=True)
class _AuthBundle:
    appkey: str
    appsecret: str
    account: Dict[str, str]


class BrokerKIS(IBroker):
    """KIS OpenAPI broker adapter with safety rails for live trading."""

    def __init__(
        self,
        storage,
        keys_path: Path | str,
        *,
        paper: bool = True,
        session: Optional[requests.Session] = None,
        timeout: float = 10.0,
        risk_config=None,
        mode: str = "mock",
    ) -> None:
        self.storage = storage
        self.provider = "kis"
        self.keys_path = Path(keys_path)
        self.paper = paper
        self.timeout = timeout
        self.mode = mode
        self._session = session or requests.Session()
        self._auth = self._load_keys()
        self.enabled = self._auth is not None
        self._bearer: str | None = None
        self._last_token_ts: float = 0.0
        self._risk_config = risk_config
        if not self.enabled:
            logger.warning("KIS 브로커 키 파일이 없어 주문 기능이 비활성화됩니다: %s", self.keys_path)
        self._cano, self._acnt_prdt_cd = self._split_account(
            (self._auth.account.get("accno") if self._auth else "")
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_keys(self) -> _AuthBundle | None:
        if not self.keys_path.exists():
            return None
        try:
            with self.keys_path.open("rb") as fh:
                raw = tomllib.load(fh)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("KIS 키 파일 파싱 실패: %s", exc)
            return None
        auth = raw.get("auth", {})
        account = raw.get("account", {})
        return _AuthBundle(
            appkey=str(auth.get("appkey", "")),
            appsecret=str(auth.get("appsecret", "")),
            account={k: str(v) for k, v in account.items()},
        )

    def _split_account(self, acc: str) -> tuple[str, str]:
        clean = acc.replace("-", "").strip()
        if len(clean) >= 10:
            return clean[:8], clean[8:10]
        if clean:
            return clean, "01"
        return "", "01"

    @property
    def _base_url(self) -> str:
        return BASE_VTS if self.paper else BASE_PROD

    def _ensure_token(self) -> bool:
        if not self.enabled:
            return False
        now = time.time()
        if self._bearer and (now - self._last_token_ts) < 30:
            return True
        bearer = ensure_token(str(self.keys_path), self.paper)
        if bearer:
            self._bearer = bearer
            self._last_token_ts = now
            return True
        return False

    def _headers(self, tr_id: str) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "appkey": self._auth.appkey if self._auth else "",
            "appsecret": self._auth.appsecret if self._auth else "",
            "tr_id": tr_id,
            "custtype": "P",
        }
        if self._bearer:
            headers["authorization"] = self._bearer
        return headers

    def _request(self, method: str, path: str, tr_id: str, payload: dict) -> Optional[dict]:
        if not self._ensure_token():
            logger.warning("KIS 토큰을 확보하지 못했습니다.")
            return None
        url = f"{self._base_url}{path}"
        headers = self._headers(tr_id)
        try:
            response = self._session.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code in {401, 403, 500}:
                logger.warning("KIS %s 응답(%s) → 토큰 재발급/재시도", response.status_code, tr_id)
                if not self._ensure_token():
                    response.raise_for_status()
                headers = self._headers(tr_id)
                response = self._session.request(
                    method,
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.warning("KIS 요청 실패(%s %s): %s", tr_id, url, exc)
        except ValueError as exc:  # pragma: no cover - JSON parsing
            logger.warning("KIS 응답 파싱 실패(%s): %s", tr_id, exc)
        return None

    def _symbol_code(self, symbol: str) -> str:
        return symbol.split(".")[0].strip()

    def _daily_loss_blocked(self) -> bool:
        limit = getattr(self._risk_config, "daily_loss_limit_r", None)
        if limit is None:
            return False
        try:
            return self.storage.is_daily_loss_limit_exceeded(float(limit))
        except AttributeError:  # pragma: no cover - storage without helper
            return False

    # ------------------------------------------------------------------
    # IBroker implementation
    # ------------------------------------------------------------------
    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        price_type: str,
        limit_price: float | None = None,
    ) -> OrderResult:
        side_norm = side.upper()
        if side_norm not in {"BUY", "SELL"}:
            message = f"지원하지 않는 주문 방향: {side}"
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        if qty <= 0:
            message = "주문 수량은 양수여야 합니다."
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        if price_type not in {"market", "limit"}:
            message = f"지원하지 않는 주문 유형: {price_type}"
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        if price_type == "limit" and (limit_price is None or limit_price <= 0):
            message = "지정가 주문은 limit_price가 필요합니다."
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        if not self.enabled:
            message = "KIS 키 파일이 없어 주문을 전송할 수 없습니다."
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        if self.mode.lower() != "live" or self.paper:
            message = "실전(Live) 모드 & 실계좌에서만 주문이 허용됩니다."
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}
        if self._daily_loss_blocked():
            message = "일중 손실 제한으로 주문이 차단되었습니다."
            logger.warning(message)
            self.storage.log_event("risk", message)
            return {"ok": False, "order_id": None, "message": message}
        if not self._cano:
            message = "계좌번호(accno)가 설정되지 않았습니다."
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}

        holdings = {pos.symbol: pos for pos in self.get_positions()}
        position = holdings.get(symbol)
        if side_norm == "SELL":
            if not position:
                message = "보유 수량이 없어 매도할 수 없습니다."
                logger.warning(message)
                return {"ok": False, "order_id": None, "message": message}
            if qty > position.qty:
                message = "주문 수량이 보유 수량을 초과합니다."
                logger.warning(message)
                return {"ok": False, "order_id": None, "message": message}

        ord_dvsn = "01" if price_type == "limit" else "00"
        price_val = 0.0 if price_type == "market" else float(limit_price)
        payload = {
            "CANO": self._cano,
            "ACNT_PRDT_CD": self._acnt_prdt_cd,
            "PDNO": self._symbol_code(symbol),
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(qty),
            "ORD_UNPR": f"{price_val:.2f}",
        }
        tr_id = ORDER_TR_ID.get((side_norm, self.paper))
        if not tr_id:
            message = "주문 TR_ID를 찾을 수 없습니다."
            logger.warning(message)
            return {"ok": False, "order_id": None, "message": message}

        response = self._request("POST", ORDER_PATH, tr_id, payload)
        if not response:
            message = "KIS 주문 응답이 비어 있습니다."
            self.storage.log_event("order_fail", f"{symbol} {side_norm} {qty} {price_type}")
            return {"ok": False, "order_id": None, "message": message}

        if response.get("rt_cd") != "0":
            msg = response.get("msg1") or response.get("msg2") or "주문 거절"
            self.storage.log_event("order_fail", f"{symbol} {side_norm} {qty}: {msg}")
            return {"ok": False, "order_id": None, "message": msg}

        output = response.get("output", {})
        order_id = output.get("ODNO") or response.get("order_no")
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.storage.record_trade(
            order_id or f"kis-{timestamp}",
            symbol=symbol,
            side=side_norm,
            qty=qty,
            price=price_val,
            ts=timestamp,
        )
        self.storage.log_event(
            "order_ok",
            f"{symbol} {side_norm} {qty} {price_type} #{order_id or 'N/A'}",
        )
        return {"ok": True, "order_id": order_id, "message": "주문 전송"}

    def get_positions(self) -> List[Position]:
        remote = self._fetch_remote_positions()
        if remote:
            return remote
        try:
            return self.storage.get_positions()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("저장된 포지션 조회 실패: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Remote helpers
    # ------------------------------------------------------------------
    def _fetch_remote_positions(self) -> List[Position]:
        if not self.enabled or not self._cano:
            return []
        if not self._ensure_token():
            return []
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
        tr_id = BALANCE_TR_ID[self.paper]
        url = f"{self._base_url}{BALANCE_PATH}"
        try:
            response = self._session.get(
                url,
                headers=self._headers(tr_id),
                params=params,
                timeout=self.timeout,
            )
            if response.status_code in {401, 403, 500}:
                logger.warning("KIS 포지션 조회 오류(%s) → 토큰 재발급", response.status_code)
                if not self._ensure_token():
                    response.raise_for_status()
                response = self._session.get(
                    url,
                    headers=self._headers(tr_id),
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
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
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
                pnl_pct = float(item.get("evlu_pfls_rt", 0) or 0) / 100
                take_profit = avg_price * (1 + getattr(self._risk_config, "take_profit_pct", 0.18))
                trail_ref = max(last_price, float(item.get("hghst_prc", last_price) or last_price))
                position = Position(
                    symbol=f"{symbol}.KS",
                    qty=qty,
                    avg_price=avg_price,
                    last_price=last_price,
                    pnl_pct=pnl_pct,
                    trail_stop=trail_ref,
                    hard_stop=0.0,
                    take_profit_price=take_profit,
                )
                positions.append(position)
                self.storage.upsert_position(position, ts)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("KIS 포지션 파싱 실패: %s", exc)
        return positions
