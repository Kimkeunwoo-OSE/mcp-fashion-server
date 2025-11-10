from __future__ import annotations

import contextlib
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import webview

LOGGER = logging.getLogger(__name__)
DEFAULT_PORT = 8501
STARTUP_RETRIES = 60
POLL_INTERVAL = 0.2


def find_free_port(default: int = DEFAULT_PORT) -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", default))
            return default
        except OSError:
            LOGGER.info("포트 %s 사용 중, 대체 포트 탐색", default)
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def launch_streamlit(port: int) -> subprocess.Popen[str]:
    script_path = Path(__file__).with_name("ui_streamlit.py")
    args = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(script_path),
        "--server.port",
        str(port),
        "--client.showErrorDetails=true",
        "--server.headless=true",
    ]
    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    env.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    LOGGER.info("Streamlit 서브프로세스 시작: %s", " ".join(args))
    return subprocess.Popen(
        args,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_server(port: int, process: subprocess.Popen[str]) -> bool:
    for _ in range(STARTUP_RETRIES):
        if process.poll() is not None:
            LOGGER.error("Streamlit 프로세스가 예상보다 빨리 종료되었습니다.")
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(POLL_INTERVAL)
    LOGGER.error("포트 %s에서 Streamlit 서버가 기동되지 않았습니다.", port)
    return False


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    LOGGER.info("Streamlit 프로세스 종료 중...")
    with contextlib.suppress(Exception):
        process.terminate()
        process.wait(timeout=3)
    if process.poll() is not None:
        return
    with contextlib.suppress(Exception):
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.kill()


def _build_menu(window: webview.Window, url: str):
    try:
        from webview.menu import Menu, MenuItem
    except Exception:  # pragma: no cover - optional feature
        return None

    def refresh() -> None:
        window.load_url(url)

    def toggle_theme() -> None:
        script = """
        (function() {
            try {
                const key = 'streamlit-theme';
                const current = window.localStorage.getItem(key) || 'dark';
                const next = current === 'dark' ? 'light' : 'dark';
                window.localStorage.setItem(key, next);
                window.location.reload();
            } catch (err) {
                console.error(err);
            }
        })();
        """
        try:
            window.evaluate_js(script)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.debug("다크 모드 토글 실패: %s", exc)

    return Menu(
        MenuItem("새로고침", refresh),
        MenuItem("다크 모드 토글", toggle_theme),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    port = find_free_port()
    process = launch_streamlit(port)
    try:
        if not _wait_for_server(port, process):
            raise SystemExit(1)
        url = f"http://127.0.0.1:{port}"

        def on_closed() -> None:
            LOGGER.info("데스크톱 창 종료 감지")

        icon_path = Path("assets/app.ico")

        window = webview.create_window(
            "v5 Trader",
            url=url,
            width=1200,
            height=800,
            min_size=(900, 600),
            resizable=True,
            confirm_close=True,
            icon=str(icon_path) if icon_path.exists() else None,
        )
        window.events.closed += on_closed

        try:
            menu_obj = _build_menu(window, url)
            if menu_obj is not None:
                window.menu = menu_obj  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - optional feature
            LOGGER.debug("메뉴 구성 실패: %s", exc)

        webview.start()
    finally:
        _terminate_process(process)


if __name__ == "__main__":  # pragma: no cover
    main()
