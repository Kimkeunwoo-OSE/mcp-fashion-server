from __future__ import annotations
import logging, sys, subprocess
from typing import Optional

try:
    from ports.notifier import INotifier
except Exception:  # 초기 세팅 보호
    class INotifier:  # type: ignore
        def send(self, text: str) -> bool: ...

__all__ = ["NotifierWindows"]

class NotifierWindows(INotifier):
    """
    Windows 토스트 어댑터 (안정화 버전)
    1) win10toast (threaded=False) 시도
    2) 실패 시 winotify (WinRT 기반) 폴백
    3) 실패 시 PowerShell BurntToast 폴백
    - 어떤 경우에도 예외를 호출자에게 전파하지 않고 False만 반환
    """
    def __init__(self, enable_ps_fallback: bool = True) -> None:
        self._is_win = sys.platform.startswith("win")
        self._enable_ps = enable_ps_fallback
        self._toast: Optional[object] = None
        self._has_winotify = False

        if not self._is_win:
            logging.warning("Windows가 아니므로 토스트 비활성화")
            return

        # 1차: win10toast
        try:
            from win10toast import ToastNotifier  # type: ignore
            self._toast = ToastNotifier()
        except Exception as e:
            logging.warning("win10toast 사용 불가: %s", e)
            self._toast = None

        # 2차 준비: winotify 사용 가능 여부 체크
        try:
            import winotify  # type: ignore
            self._has_winotify = True
        except Exception:
            self._has_winotify = False

    def send(self, text: str) -> bool:
        if not self._is_win:
            return False

        title = "v5_trader"
        msg = (text or "")[:200]

        # 1) win10toast (threaded=False 고정)
        if self._toast is not None:
            try:
                self._toast.show_toast(
                    title=title,
                    msg=msg,
                    duration=5,
                    icon_path=None,
                    threaded=False
                )
                return True
            except Exception as e:
                logging.warning("win10toast 실패: %s", e)

        # 2) winotify 폴백
        if self._has_winotify:
            try:
                from winotify import Notification  # type: ignore
                n = Notification(app_id="v5_trader", title=title, msg=msg)
                n.show()
                return True
            except Exception as e:
                logging.warning("winotify 실패: %s", e)

        # 3) PowerShell BurntToast 폴백 (설치되어 있으면 동작)
        if self._enable_ps:
            try:
                ps = f"Try {{ New-BurntToastNotification -Text '{title}', '{msg}' }} Catch {{ Exit 2 }}"
                try:
                    subprocess.run(["pwsh", "-NoProfile", "-Command", ps], check=True)
                except Exception:
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
                return True
            except Exception as e:
                logging.warning("PowerShell 토스트 실패: %s", e)

        # 어떤 경우에도 예외 전파 금지
        return False
