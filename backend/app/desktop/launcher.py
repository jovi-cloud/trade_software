"""Desktop launcher: local uvicorn server + native window via pywebview."""

from __future__ import annotations

import logging
import socket
import threading
import time
import urllib.error
import urllib.request

import uvicorn
import webview

from app.core.config import get_settings
from app.main import create_app

logger = logging.getLogger(__name__)

_STARTUP_TIMEOUT_S = 30.0
_POLL_INTERVAL_S = 0.1


def find_free_port(host: str = "127.0.0.1") -> int:
    """Bind to an ephemeral port and return its number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, timeout_s: float = _STARTUP_TIMEOUT_S) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(_POLL_INTERVAL_S)
    raise RuntimeError(f"Server did not become ready at {url} within {timeout_s}s")


def _run_uvicorn(host: str, port: int) -> None:
    settings = get_settings()
    application = create_app()
    config = uvicorn.Config(
        application,
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def main() -> None:
    settings = get_settings()
    host = settings.host
    port = find_free_port(host)
    health_url = f"http://{host}:{port}/api/v1/system/health"

    server_thread = threading.Thread(
        target=_run_uvicorn,
        args=(host, port),
        name="uvicorn",
        daemon=True,
    )
    server_thread.start()
    _wait_for_server(health_url)

    window_url = f"http://{host}:{port}/"
    logger.info("Opening desktop window at %s", window_url)
    webview.create_window(settings.app_name, window_url, width=1280, height=800)
    webview.start()


if __name__ == "__main__":
    main()
