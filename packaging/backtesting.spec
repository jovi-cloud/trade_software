# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Trading Research desktop application."""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

SPEC_DIR = Path(SPECPATH)
REPO_ROOT = SPEC_DIR.parent
BACKEND_ROOT = REPO_ROOT / "backend"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
SEED_DATA = REPO_ROOT / "packaging" / "seed_data"

if not FRONTEND_DIST.is_dir():
    raise SystemExit(f"Frontend build missing: {FRONTEND_DIST}. Run: make build")
if not SEED_DATA.is_dir():
    raise SystemExit(f"Seed data missing: {SEED_DATA}. Run packaging/prepare_seed_data.py")

block_cipher = None

hiddenimports = collect_submodules("alembic")
hiddenimports += collect_submodules("app.models")
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "webview",
]

datas: list[tuple[str, str]] = [
    (str(FRONTEND_DIST), "frontend_dist"),
    (str(SEED_DATA), "seed_data"),
    (str(BACKEND_ROOT / "alembic"), "alembic"),
    (str(BACKEND_ROOT / "alembic.ini"), "."),
]

binaries: list[tuple[str, str]] = []
for package in ("polars", "pyarrow", "numpy", "pandas"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    [str(BACKEND_ROOT / "app" / "desktop" / "launcher.py")],
    pathex=[str(BACKEND_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="TradingResearch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
