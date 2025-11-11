from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from typing import Optional

import webview

LOGGER = logging.getLogger(__name__)
DEFAULT_PORT = 8501
PORT_SCAN_LIMIT = 30
POLL_INTERVAL = 0.2
WAIT_TIMEOUT = 25.0


def _find_free_port(preferred: int = DEFAULT_PORT, limit: int = PORT_SCAN_LIMIT) -> int:
    port = preferred
    for _ in range(limit):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    return preferred


def _wait_http_ready(port: int, timeout: float = WAIT_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(POLL_INTERVAL)
    return False


def _launch_streamlit(port: int) -> subprocess.Popen[str]:
    ui_py = os.path.join(os.path.dirname(__file__), "ui_streamlit.py")
    args = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        ui_py,
        "--server.port",
        str(port),
        "--client.showErrorDetails=true",
        "--server.headless=true",
    ]
    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    env.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    LOGGER.info("Streamlit launch: %s", " ".join(args))
    return subprocess.Popen(
        args,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    LOGGER.info("Streamlit 프로세스 종료 중...")
    try:
        process.terminate()
        process.wait(3)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def _build_menu(window: webview.Window, url: str) -> Optional[object]:  # pragma: no cover - optional
    try:
        from webview.menu import Menu, MenuItem
    except Exception:
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
        except Exception as exc:
            LOGGER.debug("다크 모드 토글 실패: %s", exc)

    return Menu(
        MenuItem("새로고침", refresh),
        MenuItem("다크 모드 토글", toggle_theme),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    port = _find_free_port()
    process = _launch_streamlit(port)
    try:
        if not _wait_http_ready(port):
            print(f"[desktop] Streamlit가 {port} 포트에서 뜨지 않았습니다.", file=sys.stderr)
            _terminate_process(process)
            raise SystemExit(1)

        url = f"http://127.0.0.1:{port}"
        window = webview.create_window(
            title="v5 Trader",
            url=url,
            width=1200,
            height=800,
            resizable=True,
            confirm_close=True,
            min_size=(960, 640),
        )

        try:
            menu_obj = _build_menu(window, url)
            if menu_obj is not None:
                window.menu = menu_obj  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.debug("메뉴 구성 실패: %s", exc)

        try:
            webview.start(gui="msedgewebview2")
        except Exception:
            webview.start()
    finally:
        _terminate_process(process)


if __name__ == "__main__":  # pragma: no cover
    main()
