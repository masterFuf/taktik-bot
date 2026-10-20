# -*- mode: python ; coding: utf-8 -*-
"""The one definition of the bridge launcher: taktik_launcher.exe + _internal/, every bridge of the manifest.

Built from a virtual environment installed from requirements.lock (requirements-build.txt adds
PyInstaller), never from the Python of the machine: what the environment holds is what the launcher
carries. The installer's build-all.ps1 (app) does it in core/.venv-build, on Python 3.14:

    python scripts/build/bundle_tesseract.py        (optional: OCR ships only when staged)
    python -m PyInstaller --distpath dist/taktik-bot --workpath build --noconfirm --clean taktik_launcher.spec

A folder build, read in place: a one-file build unpacked its whole content into %TEMP% at every
bridge launch (14 to 28 s before the first event).
"""

import json
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

import uiautomator2


BOT_DIR = Path(globals().get("SPECPATH", Path.cwd())).resolve()
BRIDGES_DIR = BOT_DIR / "bridges"
MANIFEST_PATH = BRIDGES_DIR / "bridges.manifest.json"
U2_ASSETS = Path(uiautomator2.__file__).resolve().parent / "assets"


def load_bridge_modules():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    modules = []
    for platform_bridges in manifest.values():
        modules.extend(platform_bridges.values())
    return sorted(set(modules))


datas = [
    (str(BOT_DIR / "taktik"), "taktik"),
    (str(BRIDGES_DIR), "bridges"),
    (str(U2_ASSETS), "uiautomator2/assets"),
    # The list of the workflows, at the root of _internal/: load_workflow_manifest climbs from its own
    # files to find it (the app's check-installer-chain.cjs and verify-package.cjs hold it).
    (str(BOT_DIR / "workflows.manifest.json"), "."),
]

# A portable tesseract (tesseract.exe + DLLs + the tessdata we support), staged by
# scripts/build/bundle_tesseract.py under assets/tesseract/, so OCR ships with the app and clients
# install nothing; the OCR service resolves it from _MEIPASS at run time. Without it the build still
# works and OCR degrades to a no-op.
_TESSERACT_DIR = BOT_DIR / "assets" / "tesseract"
if (_TESSERACT_DIR / "tesseract.exe").is_file() or (_TESSERACT_DIR / "tesseract").is_file():
    datas.append((str(_TESSERACT_DIR), "tesseract"))

binaries = []
hiddenimports = [
    "taktik",
    "taktik.core",
    "taktik.core.database",
    "taktik.core.social_media.tiktok",
    "taktik.core.shared.device.app_manager",
    "taktik.core.shared.device.connection",
    "taktik.core.shared.input.keyboard",
    "bridges.common",
    "bridges.common.bootstrap",
    "bridges.common.bridge_base",
    "bridges.common.ipc",
    "bridges.common.network",
    "bridges.common.signal_handler",
    "adbutils",
    "uiautomator2",
    "loguru",
    "requests",
    "yaml",
    "rich",
    *load_bridge_modules(),
]
hiddenimports += collect_submodules("bridges.tiktok")

for package in ("taktik", "bridges", "rich"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports


a = Analysis(
    [str(BRIDGES_DIR / "launcher.py")],
    pathex=[str(BOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # None of the bridges imports them; mitmproxy: its addon ships as a file next to the media proxy
    # and runs in the user's mitmdump, collect_all("taktik") would bundle mitmproxy for it.
    excludes=["cv2", "matplotlib", "tkinter", "mitmproxy"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="taktik_launcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="taktik_launcher",
)
