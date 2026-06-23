# -*- mode: python ; coding: utf-8 -*-

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
]

# Bundle a portable tesseract (tesseract.exe + DLLs + tessdata for the languages we
# support) so OCR ships WITH the app — clients never install it. Drop the portable build
# under bot/assets/tesseract/ ; the OCR service resolves it from _MEIPASS at runtime
# (OcrService._configure). Guarded: the build still works if the folder is absent (OCR
# then degrades gracefully = truncated text kept).
_TESSERACT_DIR = BOT_DIR / "assets" / "tesseract"
if _TESSERACT_DIR.exists():
    datas.append((str(_TESSERACT_DIR), "tesseract"))

binaries = []
hiddenimports = [
    "taktik",
    "taktik.core",
    "taktik.core.database",
    "taktik.core.license",
    "taktik.core.database.api_client",
    "taktik.core.license.unified_license_manager",
    "taktik.core.social_media.tiktok",
    "bridges.common",
    "adbutils",
    "uiautomator2",
    "loguru",
    "requests",
    "httpx",
    "yaml",
    "rich",
    "typer",
    "pydantic",
    "pytesseract",  # lazy import in taktik.core.shared.vision.ocr
    *load_bridge_modules(),
]
hiddenimports += collect_submodules("bridges.tiktok")

tmp_ret = collect_all("taktik")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

tmp_ret = collect_all("bridges")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

tmp_ret = collect_all("rich")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]


a = Analysis(
    [str(BRIDGES_DIR / "launcher.py")],
    pathex=[str(BOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["cv2", "matplotlib", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="taktik_launcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
