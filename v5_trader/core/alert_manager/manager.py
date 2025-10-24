"""Alert manager handling Telegram and desktop notifications."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from plyer import notification
from telegram import Bot

from v5_trader.core.strategy_v5.model import StrategyResult
from v5_trader.core.utils.config import Settings


@dataclass
class AlertPayload:
    title: str
    message: str


class AlertManager:
    """Dispatch alerts to available channels."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bot: Optional[Bot] = None
        if settings.alerts.enable_telegram and settings.telegram.token:
            self.bot = Bot(token=settings.telegram.token)

    def _format_message(self, result: StrategyResult) -> AlertPayload:
        title = f"🚀 Surge Alert: {result.symbol}"
        message = (
            f"Surge Probability: {result.surge_probability:.1%}\n"
            f"Target Price: {result.target_price:,.2f}\n"
            f"Confidence: {result.confidence:.0%}"
        )
        return AlertPayload(title=title, message=message)

    def dispatch(self, result: StrategyResult) -> None:
        payload = self._format_message(result)
        if self.settings.alerts.enable_desktop:
            try:
                notification.notify(title=payload.title, message=payload.message, timeout=5)
            except Exception as exc:  # pragma: no cover - desktop env dependent
                print(f"Desktop notification failed: {exc}")
        if self.bot is not None and self.settings.telegram.chat_id:
            self.bot.send_message(chat_id=self.settings.telegram.chat_id, text=payload.message)
