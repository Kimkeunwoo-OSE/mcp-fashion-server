from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

try:  # pragma: no cover - Python 3.10 fallback
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

logger = logging.getLogger(__name__)


class NotifierSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = Field(default="windows", pattern="^(windows|none)$")


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = Field(default="v5_rewrite.db")


class StrategySettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    return_threshold: float = Field(default=1.0, ge=0)
    intensity: float = Field(default=1.0, ge=0)
    volume_rank: float = Field(default=0.5, ge=0)


class UISettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    theme: str = Field(default="dark")
    refresh_interval: int = Field(default=30, ge=5)


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="mock", pattern="^(mock|paper|live)$")
    notifier: NotifierSettings = Field(default_factory=NotifierSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    strategy: StrategySettings = Field(default_factory=StrategySettings)
    ui: UISettings = Field(default_factory=UISettings)


def load_settings(path: Path | None = None) -> AppSettings:
    config_path = path or Path("config/settings.toml")
    data: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)
    else:
        logger.warning("%s not found. Using defaults.", config_path)

    try:
        settings = AppSettings.model_validate(data)
    except ValidationError as exc:
        logger.error("설정 검증 실패: %s", exc)
        raise

    _warn_missing_sections(data)
    return settings


def _warn_missing_sections(data: dict[str, Any]) -> None:
    expected_sections = {"notifier", "db", "strategy", "ui"}
    for section in expected_sections:
        if section not in data:
            logger.warning("설정 섹션 %s 이(가) 누락되었습니다. 기본값을 사용합니다.", section)
