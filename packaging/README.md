# Windows Desktop Packaging

Build a single-file Windows installer your friend can run without Python, Node, or any dev tools.

## What gets installed

- **Application:** `TradingResearch.exe` (PyInstaller one-file bundle)
- **User data:** `%LOCALAPPDATA%\TradingResearch\data\` (SQLite DB, parquet files, logs)
- **First launch:** copies bundled seed data, runs Alembic migrations, opens a native window (pywebview)

## Prerequisites (build machine only)

| Tool | Purpose |
|------|---------|
| Python 3.12+ | Backend runtime |
| [uv](https://docs.astral.sh/uv/) | Python dependency management |
| Node.js 20+ | Frontend build |
| [Inno Setup 6](https://jrsoftware.org/isinfo.php) | Windows installer compiler |

On Linux you can cross-check the Python/PyInstaller steps; the Inno Setup step requires Windows (or CI).

## Local build (Windows)

From the repository root:

```powershell
# 1. Install dependencies
cd backend
uv sync --group packaging
cd ..\frontend
npm install

# 2. Build frontend
cd ..
make build

# 3. Stage seed data (migrated DB, WAL checkpointed)
cd backend
uv run python ..\packaging\prepare_seed_data.py

# 4. PyInstaller bundle
cd ..
uv run --directory backend pyinstaller ..\packaging\backtesting.spec --distpath packaging\dist --workpath packaging\build --noconfirm

# 5. Inno Setup installer
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

The installer is written to:

```
packaging/installer/TradingResearch-Setup-0.1.0.exe
```

Send that file to your friend. They double-click it, install, and launch from the Start Menu or desktop shortcut.

## Local build (Linux — test bundle only, no installer)

```bash
make install
make build
cd backend && uv run python ../packaging/prepare_seed_data.py
cd backend && uv sync --group packaging
cd backend && uv run pyinstaller ../packaging/backtesting.spec \
  --distpath ../packaging/dist \
  --workpath ../packaging/build \
  --noconfirm
```

Output: `packaging/dist/TradingResearch/TradingResearch.exe` (onedir bundle — not a single file).

## CI build (GitHub Actions)

Push to `main` or open a PR — workflow `.github/workflows/windows-installer.yml` builds the installer on `windows-latest` and uploads `TradingResearch-Setup-*.exe` as a workflow artifact.

Download from: **Actions → Windows Installer → Artifacts**.

## Updating seed data

`packaging/prepare_seed_data.py` creates a fresh migrated database with empty `market/`, `artifacts/`, `imports/`, and `logs/` directories. Re-run before each release build so new migrations are baked into the seed.

To ship sample datasets, import them into a dev `data/` directory, checkpoint WAL, then copy the relevant files into `packaging/seed_data/` before building.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Blank window on launch | Check `%LOCALAPPDATA%\TradingResearch\data\logs\app.log` |
| "Frontend build missing" during PyInstaller | Run `make build` first |
| Port already in use | Launcher picks a free port automatically; restart the app |
| Antivirus blocks exe | Expected for unsigned PyInstaller builds; build in CI or sign the binary |

## Data location

| Path | Contents |
|------|----------|
| `%LOCALAPPDATA%\TradingResearch\data\app.db` | SQLite catalog |
| `%LOCALAPPDATA%\TradingResearch\data\market\` | Bar parquet files |
| `%LOCALAPPDATA%\TradingResearch\data\artifacts\` | Backtest outputs |
| `%LOCALAPPDATA%\TradingResearch\data\imports\` | Staged uploads |
| `%LOCALAPPDATA%\TradingResearch\data\logs\` | Application logs |

Uninstalling via the installer removes `%LOCALAPPDATA%\TradingResearch` (see `installer.iss`).
