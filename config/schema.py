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
    refresh_interval: int = Field(default=5, ge=1)


class TradeSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    quick_pct: list[int] = Field(default_factory=lambda: [10, 25, 50, 100])
    tick: int = Field(default=50, ge=1)
    default_price_type: str = Field(default="market", pattern=r"^(market|limit)$")
    confirm_phrase: str = Field(default="자동매매 금지 정책에 동의합니다")


class ChartSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    periods: list[int] = Field(default_factory=lambda: [60, 120, 250])
    indicators: list[str] = Field(default_factory=lambda: ["SMA20", "SMA60", "RSI14"])


class WatchSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    universe: str = Field(
        default="KOSPI_TOP200",
        pattern=r"^(KOSPI_TOP200|KOSDAQ_TOP150|CUSTOM)$",
    )
    symbols: list[str] = Field(default_factory=list)
    top_n: int = Field(default=5, ge=1, le=20)
    refresh_sec: int = Field(default=60, ge=10)


class RiskSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stop_loss_pct: float = Field(default=0.07, ge=0)
    take_profit_pct: float = Field(default=0.18, ge=0)
    trailing_pct: float = Field(default=0.03, ge=0)
    daily_loss_limit_r: float = Field(default=-3.0)
    max_positions: int = Field(default=3, ge=1)


class MarketSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = Field(default="mock", pattern="^(mock|kis)$")


class BrokerSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = Field(default="mock", pattern="^(mock|kis)$")


class KISSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keys_path: str = Field(default="config/kis.keys.toml")
    paper: bool = Field(default=True)


class DisplaySettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    show_names: bool = Field(default=True)


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="mock", pattern="^(mock|paper|live)$")
    notifier: NotifierSettings = Field(default_factory=NotifierSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    strategy: StrategySettings = Field(default_factory=StrategySettings)
    ui: UISettings = Field(default_factory=UISettings)
    trade: TradeSettings = Field(default_factory=TradeSettings)
    chart: ChartSettings = Field(default_factory=ChartSettings)
    watch: WatchSettings = Field(default_factory=WatchSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    market: MarketSettings = Field(default_factory=MarketSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    kis: KISSettings = Field(default_factory=KISSettings)
    display: DisplaySettings = Field(default_factory=DisplaySettings)


def load_settings(path: Path | None = None) -> AppSettings:
    config_path = path or Path("config/settings.toml")
    data: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)
    else:
        logger.warning("%s not found. Using defaults.", config_path)

    data = _inject_optional_sections(dict(data))

    try:
        settings = AppSettings.model_validate(data)
    except ValidationError as exc:
        logger.error("설정 검증 실패: %s", exc)
        raise

    _warn_missing_sections(data)
    return settings


def _inject_optional_sections(data: dict[str, Any]) -> dict[str, Any]:
    injected: list[str] = []
    defaults: dict[str, dict[str, Any]] = {
        "trade": {
            "quick_pct": [10, 25, 50, 100],
            "tick": 50,
            "default_price_type": "market",
            "confirm_phrase": "자동매매 금지 정책에 동의합니다",
        },
        "chart": {
            "periods": [60, 120, 250],
            "indicators": ["SMA20", "SMA60", "RSI14"],
        },
    }
    for section, default in defaults.items():
        if section not in data:
            data[section] = dict(default)
            injected.append(section)
    if injected:
        logger.info(
            "settings 보정 적용: 기본 섹션 주입 (%s)",
            ", ".join(sorted(injected)),
        )
    return data


def _warn_missing_sections(data: dict[str, Any]) -> None:
    expected_sections = {
        "notifier",
        "db",
        "strategy",
        "ui",
        "trade",
        "chart",
        "watch",
        "risk",
        "market",
        "broker",
        "kis",
        "display",
    }
    for section in expected_sections:
        if section not in data:
            logger.warning("설정 섹션 %s 이(가) 누락되었습니다. 기본값을 사용합니다.", section)
