from __future__ import annotations

import logging
import os
import subprocess
import sys

try:
    from ports.notifier import INotifier
except Exception:  # pragma: no cover - during early boot the interface might be missing
    class INotifier:  # type: ignore
        def send(self, text: str) -> bool: ...

__all__ = ["NotifierWindows"]


class NotifierWindows(INotifier):
    """Windows toast adapter with Streamlit-aware fallbacks.

    Priority:
    1. ``winotify`` (WinRT)
    2. PowerShell BurntToast
    3. ``win10toast`` with ``threaded=False`` (disabled when Streamlit is running or via env)

    The adapter never raises—``send`` always returns ``True``/``False``.
    """

    def __init__(self, enable_ps_fallback: bool = True) -> None:
        self._is_win = sys.platform.startswith("win")
        self._enable_ps = enable_ps_fallback
        self._has_winotify = False
        self._use_win10toast = False
        self._toast = None

        if not self._is_win:
            logging.warning("Windows가 아니므로 토스트 비활성화")
            return

        running_streamlit = "streamlit" in sys.modules
        disable_win10toast = os.getenv("V5_DISABLE_WIN10TOAST") in {"1", "true", "True"}

        try:  # winotify availability (preferred path)
            import winotify  # type: ignore  # noqa: F401

            self._has_winotify = True
        except Exception:
            self._has_winotify = False

        if running_streamlit or disable_win10toast:
            reason = "Streamlit 감지" if running_streamlit else "환경변수 비활성"
            logging.info("win10toast 비활성 (%s)", reason)
            return

        try:  # optional win10toast bootstrap
            from win10toast import ToastNotifier  # type: ignore

            self._toast = ToastNotifier()
            self._use_win10toast = True
        except Exception as exc:  # pragma: no cover - depends on local env
            logging.warning("win10toast 사용 불가: %s", exc)
            self._toast = None
            self._use_win10toast = False

    def send(self, text: str) -> bool:  # noqa: D401 - short description unnecessary
        if not self._is_win:
            return False

        title = "v5_trader"
        msg = (text or "")[:200]

        if self._has_winotify:  # preferred path
            try:
                from winotify import Notification  # type: ignore

                Notification(app_id="v5_trader", title=title, msg=msg).show()
                return True
            except Exception as exc:
                logging.warning("winotify 실패: %s", exc)

        if self._enable_ps:  # PowerShell fallback
            try:
                ps = f"Try {{ New-BurntToastNotification -Text '{title}', '{msg}' }} Catch {{ Exit 2 }}"
                try:
                    subprocess.run(["pwsh", "-NoProfile", "-Command", ps], check=True)
                except Exception:
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
                return True
            except Exception as exc:
                logging.warning("PowerShell 토스트 실패: %s", exc)

        if self._use_win10toast and self._toast is not None:
            try:
                self._toast.show_toast(
                    title=title,
                    msg=msg,
                    duration=5,
                    icon_path=None,
                    threaded=False,
                )
                return True
            except Exception as exc:
                logging.warning("win10toast 실패: %s", exc)

        return False
