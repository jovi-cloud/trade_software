"""Desktop launcher: local uvicorn server + native window via pywebview."""

from __future__ import annotations

import logging
import multiprocessing
import re
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from html import escape
from pathlib import Path

import uvicorn
import webview

from app.core.config import get_settings
from app.core.runtime import bundle_dir, default_data_dir, frontend_dist_dir, is_frozen
from app.main import create_app

logger = logging.getLogger(__name__)

_STARTUP_TIMEOUT_S = 60.0
_POLL_INTERVAL_S = 0.1
_ASSET_URL_RE = re.compile(r"""(?:src|href)="(/assets/[^"]+)""")


def _startup_log_path() -> Path:
    return default_data_dir() / "logs" / "startup.log"


def _configure_startup_logging() -> None:
    log_path = _startup_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    if not is_frozen():
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(formatter)
        root.addHandler(stream)
    logger.info("Startup logging to %s", log_path)


def find_free_port(host: str = "127.0.0.1") -> int:
    """Bind to an ephemeral port and return its number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _extract_asset_paths(index_html: Path) -> list[str]:
    content = index_html.read_text(encoding="utf-8")
    return _ASSET_URL_RE.findall(content)


def _verify_frontend_bundle(dist_dir: Path) -> list[str]:
    index_path = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"
    if not index_path.is_file():
        raise RuntimeError(f"Frontend index.html not found at {index_path}")
    if not assets_dir.is_dir():
        raise RuntimeError(f"Frontend assets directory not found at {assets_dir}")
    asset_paths = _extract_asset_paths(index_path)
    if not asset_paths:
        raise RuntimeError(f"No /assets/* references found in {index_path}")
    logger.info(
        "Frontend bundle OK: %s (%d assets referenced, frozen=%s, bundle=%s)",
        dist_dir,
        len(asset_paths),
        is_frozen(),
        bundle_dir(),
    )
    return asset_paths


def _http_get(url: str, timeout_s: float = 5.0) -> int:
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        return response.status


def _wait_for_server(url: str, timeout_s: float = _STARTUP_TIMEOUT_S) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            status = _http_get(url, timeout_s=1.0)
            if status == 200:
                return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(_POLL_INTERVAL_S)
    raise RuntimeError(f"Server did not become ready at {url} within {timeout_s}s")


def _verify_frontend_http(host: str, port: int, asset_paths: list[str]) -> None:
    base = f"http://{host}:{port}"
    _http_get(f"{base}/")
    for asset_path in asset_paths:
        status = _http_get(f"{base}{asset_path}")
        if status != 200:
            raise RuntimeError(f"Frontend asset {asset_path} returned HTTP {status}")


def _run_uvicorn(host: str, port: int) -> None:
    settings = get_settings()
    application = create_app()
    config = uvicorn.Config(
        application,
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    server.run()


def _show_error_window(title: str, message: str) -> None:
    body = escape(message)
    html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>{escape(title)}</title>
        <style>
          body {{
            margin: 0;
            padding: 24px;
            font-family: Segoe UI, system-ui, sans-serif;
            background: #111827;
            color: #f9fafb;
          }}
          h1 {{ font-size: 20px; margin-bottom: 12px; }}
          pre {{
            white-space: pre-wrap;
            background: #1f2937;
            padding: 16px;
            border-radius: 8px;
            font-size: 13px;
            line-height: 1.5;
          }}
          p {{ color: #9ca3af; font-size: 13px; margin-top: 16px; }}
        </style>
      </head>
      <body>
        <h1>{escape(title)}</h1>
        <pre>{body}</pre>
        <p>Details were also written to %LOCALAPPDATA%\\TradingResearch\\data\\logs\\startup.log</p>
      </body>
    </html>
    """
    webview.create_window(title, html=html, width=900, height=600)
    webview.start(gui="edgechromium")


def main() -> None:
    multiprocessing.freeze_support()
    _configure_startup_logging()

    try:
        settings = get_settings()
        dist_dir = frontend_dist_dir()
        asset_paths = _verify_frontend_bundle(dist_dir)

        host = settings.host
        port = find_free_port(host)
        health_url = f"http://{host}:{port}/api/v1/system/health"

        server_error: BaseException | None = None

        def _server_target() -> None:
            nonlocal server_error
            try:
                _run_uvicorn(host, port)
            except BaseException as exc:
                server_error = exc
                logger.exception("Uvicorn server thread failed")

        server_thread = threading.Thread(
            target=_server_target,
            name="uvicorn",
            daemon=False,
        )
        server_thread.start()
        _wait_for_server(health_url)
        if server_error is not None:
            raise server_error

        _verify_frontend_http(host, port, asset_paths)

        window_url = f"http://{host}:{port}/"
        logger.info("Opening desktop window at %s", window_url)
        webview.create_window(
            settings.app_name,
            window_url,
            width=1280,
            height=800,
            min_size=(800, 600),
        )
        webview.start(gui="edgechromium")
    except Exception as exc:
        logger.exception("Desktop launcher failed")
        detail = f"{exc}\n\n{traceback.format_exc()}"
        _show_error_window("Trading Research failed to start", detail)


if __name__ == "__main__":
    main()
