from __future__ import annotations

import logging
import sys

from ports.notifier import INotifier

logger = logging.getLogger(__name__)


class WindowsToastNotifier(INotifier):
    """Windows Toast implementation with graceful degradation on non-Windows systems."""

    def __init__(self) -> None:
        self._is_windows = sys.platform.startswith("win")
        self._toaster = None
        if self._is_windows:
            try:
                from win10toast import ToastNotifier

                self._toaster = ToastNotifier()
            except Exception as exc:  # pragma: no cover - import-time issues rare
                logger.warning("win10toast 초기화 실패: %s", exc)
                self._toaster = None
        else:
            logger.warning("Windows Toast notifier는 Windows 환경에서만 동작합니다.")

    def send(self, text: str) -> bool:
        if not self._is_windows or self._toaster is None:
            logger.warning("Windows Toast 사용 불가 환경입니다. message=%s", text[:50])
            return False
        try:
            self._toaster.show_toast(
                title="v5_trader",
                msg=text[:200],
                duration=5,
                icon_path=None,
            )
            return True
        except Exception as exc:  # pragma: no cover - runtime errors rare
            logger.warning("토스트 전송 실패: %s", exc)
            return False
