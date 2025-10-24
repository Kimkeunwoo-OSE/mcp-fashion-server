"""Configuration helpers for v5 Trader."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import json
import os

from dotenv import load_dotenv


@dataclass
class DatabaseConfig:
    path: str


@dataclass
class KISConfig:
    app_key: str
    app_secret: str
    account_no: str
    url_base: str


@dataclass
class TelegramConfig:
    token: str
    chat_id: str


@dataclass
class AlertsConfig:
    enable_desktop: bool
    enable_telegram: bool
    surge_threshold: float


@dataclass
class StrategyConfig:
    lookback_days: int
    min_volume: int
    volatility_window: int


@dataclass
class Settings:
    mock_mode: bool
    database: DatabaseConfig
    kis: KISConfig
    telegram: TelegramConfig
    alerts: AlertsConfig
    strategy: StrategyConfig


def load_settings(config_dir: Path | None = None) -> Settings:
    """Load settings from JSON files and environment variables."""

    config_dir = config_dir or Path(__file__).resolve().parents[2] / "config"
    settings_path = config_dir / "settings.json"
    with settings_path.open("r", encoding="utf-8") as fh:
        data: Dict[str, Any] = json.load(fh)

    env_path = config_dir / "user.env"
    if env_path.exists():
        load_dotenv(env_path)
    load_dotenv(Path.cwd() / ".env.local", override=True)

    mock_env = os.getenv("V5_TRADER_MOCK_MODE")
    if mock_env is not None:
        data["mock_mode"] = mock_env.lower() == "true"

    kis = data["kis"]
    kis["app_key"] = os.getenv("KIS_APP_KEY", kis.get("app_key", ""))
    kis["app_secret"] = os.getenv("KIS_APP_SECRET", kis.get("app_secret", ""))
    kis["account_no"] = os.getenv("KIS_ACCOUNT_NO", kis.get("account_no", ""))

    telegram = data["telegram"]
    telegram["token"] = os.getenv("TELEGRAM_BOT_TOKEN", telegram.get("token", ""))
    telegram["chat_id"] = os.getenv("TELEGRAM_CHAT_ID", telegram.get("chat_id", ""))

    return Settings(
        mock_mode=bool(data["mock_mode"]),
        database=DatabaseConfig(**data["database"]),
        kis=KISConfig(**kis),
        telegram=TelegramConfig(**telegram),
        alerts=AlertsConfig(**data["alerts"]),
        strategy=StrategyConfig(**data["strategy"]),
    )
