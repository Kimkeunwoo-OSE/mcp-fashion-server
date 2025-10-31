from __future__ import annotations

import logging
import subprocess
import sys
from typing import Optional

try:
    from ports.notifier import INotifier
except Exception:  # pragma: no cover
    class INotifier:  # type: ignore
        def send(self, text: str) -> bool: ...

__all__ = ["NotifierWindows"]


class NotifierWindows(INotifier):
    """
    Windows 10/11 토스트 래퍼.
    - 비Windows/의존성 문제: False 반환, 예외 미전파.
    - 일부 환경에서 나타나는 WNDPROC/TypeError 회피:
      * win10toast 호출 시 threaded=False
      * title/msg 항상 str로 강제
      * 실패 시 PowerShell BurntToast 폴백(설치되어 있으면)
    """

    def __init__(self, enable_powershell_fallback: bool = True) -> None:
        self._is_windows = sys.platform.startswith("win")
        self._toast: Optional[object] = None
        self._enable_ps_fallback = enable_powershell_fallback

        if not self._is_windows:
            logging.warning("Windows 토스트는 비Windows에서 비활성화됩니다.")
            return

        try:
            from win10toast import ToastNotifier  # type: ignore

            self._toast = ToastNotifier()
        except Exception as exc:  # pragma: no cover - import issues
            logging.warning("win10toast 임포트/초기화 실패: %s", exc)
            self._toast = None

    def send(self, text: str) -> bool:
        if not self._is_windows:
            logging.warning("Windows가 아니므로 토스트 생략: %r", text)
            return False

        msg = (text or "")[:200]
        title = "v5_trader"

        if self._toast is not None:
            try:
                self._toast.show_toast(
                    title=title,
                    msg=str(msg),
                    duration=5,
                    icon_path=None,
                    threaded=False,
                )
                return True
            except Exception as exc:
                logging.warning("win10toast 실패: %s", exc)

        if self._enable_ps_fallback:
            title_escaped = title.replace("'", "’’")
            msg_escaped = str(msg).replace("'", "’’")
            ps_cmd = (
                "Try { New-BurntToastNotification -Text "
                f"'{title_escaped}', "
                f"'{msg_escaped}' }} Catch {{ Exit 2 }}"
            )
            for shell in ("pwsh", "powershell"):
                try:
                    subprocess.run(
                        [shell, "-NoProfile", "-Command", ps_cmd],
                        check=True,
                    )
                    return True
                except Exception as exc:
                    logging.debug("PowerShell 폴백 실패(%s): %s", shell, exc)
            logging.warning("PowerShell 폴백 토스트 실패")

        return False
