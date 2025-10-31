from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests

try:  # pragma: no cover - Python 3.10 fallback
    import tomllib  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    import tomli as tomllib  # type: ignore[attr-defined]

BASE_VTS = "https://openapivts.koreainvestment.com:29443"
BASE_PROD = "https://openapi.koreainvestment.com:9443"

TOKEN_PATH = "/oauth2/tokenP"

DEFAULT_TIMEOUT = 10


@dataclass
class KisKeys:
    appkey: str
    appsecret: str
    access_token: str | None
    expires_at: float | None
    path: str
    is_vts: bool


def _load_keys(path: str, is_vts: bool) -> Optional[KisKeys]:
    if not os.path.exists(path):
        logging.warning("KIS 키 파일이 없습니다: %s", path)
        return None
    with open(path, "rb") as file:
        data = tomllib.load(file)
    auth = data.get("auth", {})
    appkey = auth.get("appkey", "")
    appsecret = auth.get("appsecret", "")
    token = auth.get("access_token")
    expires_at = auth.get("expires_at")
    return KisKeys(
        appkey=appkey,
        appsecret=appsecret,
        access_token=token,
        expires_at=expires_at,
        path=path,
        is_vts=is_vts,
    )


def _save_token(keys: KisKeys, raw_token: str, expires_in: int | None) -> None:
    bearer = raw_token if raw_token.startswith("Bearer ") else f"Bearer {raw_token}"
    escaped = bearer.replace('"', '\\"')
    now = time.time()
    exp = now + (expires_in or 3600) - 30
    try:
        import tomli_w  # type: ignore

        with open(keys.path, "rb") as file:
            data = tomllib.load(file)
        data.setdefault("auth", {})
        data["auth"]["access_token"] = bearer
        data["auth"]["expires_at"] = int(exp)
        with open(keys.path, "wb") as file:
            tomli_w.dump(data, file)
    except Exception:
        lines: list[str] = []
        if os.path.exists(keys.path):
            with open(keys.path, "r", encoding="utf-8") as file:
                lines = file.read().splitlines()
        output: list[str] = []
        in_auth = False
        seen_token = False
        seen_exp = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[auth]"):
                in_auth = True
                output.append(line)
                continue
            if in_auth and stripped.startswith("["):
                if not seen_token:
                    output.append(f'access_token = "{escaped}"')
                    seen_token = True
                if not seen_exp:
                    output.append(f"expires_at = {int(exp)}")
                    seen_exp = True
                in_auth = False
            if in_auth and stripped.startswith("access_token"):
                output.append(f'access_token = "{escaped}"')
                seen_token = True
                continue
            if in_auth and stripped.startswith("expires_at"):
                output.append(f"expires_at = {int(exp)}")
                seen_exp = True
                continue
            output.append(line)
        if in_auth:
            if not seen_token:
                output.append(f'access_token = "{escaped}"')
                seen_token = True
            if not seen_exp:
                output.append(f"expires_at = {int(exp)}")
                seen_exp = True
        with open(keys.path, "w", encoding="utf-8") as file:
            file.write("\n".join(output))
    keys.access_token = bearer
    keys.expires_at = exp


def _need_new_token(keys: KisKeys) -> bool:
    if not keys.access_token or not keys.access_token.startswith("Bearer "):
        return True
    if keys.expires_at and time.time() < keys.expires_at:
        return False
    return True


def issue_token(keys: KisKeys) -> bool:
    base = BASE_VTS if keys.is_vts else BASE_PROD
    url = f"{base}{TOKEN_PATH}"
    payload = {
        "grant_type": "client_credentials",
        "appkey": keys.appkey,
        "appsecret": keys.appsecret,
    }
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=DEFAULT_TIMEOUT,
            headers={"content-type": "application/json"},
        )
        if response.status_code >= 400:
            response = requests.post(url, data=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        raw = data.get("access_token") or data.get("accessToken") or ""
        expires = int(data.get("expires_in") or data.get("expiresIn") or 3600)
        if not raw:
            logging.error("KIS 토큰 응답에 access_token이 없습니다: %s", data)
            return False
        _save_token(keys, raw, expires)
        logging.info("KIS access_token 발급/저장 완료 (만료 ~%ds)", expires)
        return True
    except Exception as exc:  # pragma: no cover - network failure
        logging.exception("KIS 토큰 발급 실패(POST %s): %s", url, exc)
        return False


def ensure_token(keys_path: str, is_vts: bool) -> Optional[str]:
    keys = _load_keys(keys_path, is_vts)
    if not keys:
        return None
    if _need_new_token(keys):
        if not issue_token(keys):
            return None
    return keys.access_token


__all__ = [
    "BASE_PROD",
    "BASE_VTS",
    "DEFAULT_TIMEOUT",
    "KisKeys",
    "ensure_token",
    "issue_token",
]
