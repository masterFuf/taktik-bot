"""Build the single TAKTIK bridge launcher executable.

Run with:
    python scripts/build_exe.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DIST_DIR = BASE_DIR / "dist" / "taktik-bot"
BUILD_DIR = BASE_DIR / "build"
BRIDGES_DIR = BASE_DIR / "bridges"
MANIFEST_PATH = BRIDGES_DIR / "bridges.manifest.json"


def get_uiautomator2_assets_path() -> Path:
    """Return the uiautomator2 assets folder bundled with the launcher."""
    import uiautomator2

    return Path(uiautomator2.__file__).resolve().parent / "assets"


def load_bridge_modules() -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    modules: list[str] = []
    for platform_bridges in manifest.values():
        modules.extend(platform_bridges.values())
    return sorted(set(modules))


def pyinstaller_data_arg(source: Path, target: str) -> str:
    return f"--add-data={source}{os.pathsep}{target}"


def stage_tesseract() -> Path | None:
    """Stage a portable tesseract under assets/tesseract/ (best-effort) so it ships with
    the launcher. Returns the folder if populated, else None."""
    try:
        import bundle_tesseract  # noqa: PLC0415 (sibling script in scripts/)
    except ModuleNotFoundError:
        sys.path.insert(0, str(SCRIPT_DIR))
        import bundle_tesseract  # noqa: PLC0415
    bundle_tesseract.main()
    tesseract_dir = BASE_DIR / "assets" / "tesseract"
    has_exe = (tesseract_dir / "tesseract.exe").exists() or (tesseract_dir / "tesseract").exists()
    return tesseract_dir if has_exe else None


def build_launcher() -> None:
    u2_assets = get_uiautomator2_assets_path()
    tesseract_dir = stage_tesseract()
    hidden_imports = [
        "taktik",
        "taktik.core",
        "taktik.core.database",
        "bridges",
        "bridges.common",
        "adbutils",
        "uiautomator2",
        "PIL",
        "pytesseract",  # OCR (lazy import in taktik.core.shared.vision.ocr)
        "loguru",
        "requests",
        "httpx",
        "yaml",
        "rich",
        "typer",
        "pydantic",
        *load_bridge_modules(),
    ]

    args = [
        str(BRIDGES_DIR / "launcher.py"),
        "--name=taktik_launcher",
        "--onefile",
        "--console",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--specpath={BUILD_DIR}",
        f"--paths={BASE_DIR}",
        "--collect-all=taktik",
        "--collect-all=bridges",
        "--collect-all=rich",
        "--collect-submodules=bridges.tiktok",
        "--exclude-module=cv2",
        "--exclude-module=matplotlib",
        "--exclude-module=tkinter",
        "--clean",
        pyinstaller_data_arg(BASE_DIR / "taktik", "taktik"),
        pyinstaller_data_arg(BRIDGES_DIR, "bridges"),
        pyinstaller_data_arg(u2_assets, "uiautomator2/assets"),
    ]
    # Bundle the portable tesseract (exe + DLLs + tessdata) when staged, so OCR ships with
    # the launcher (clients install nothing). OcrService resolves _MEIPASS/tesseract at runtime.
    if tesseract_dir:
        args.append(pyinstaller_data_arg(tesseract_dir, "tesseract"))
    for module in hidden_imports:
        args.append(f"--hidden-import={module}")

    PyInstaller.__main__.run(args)


def main() -> None:
    print("=" * 50)
    print("TAKTIK Bot - Building Bridge Launcher")
    print("=" * 50)

    if DIST_DIR.exists():
        print(f"Cleaning {DIST_DIR}...")
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/1] Building taktik_launcher.exe...")
    build_launcher()

    print("\n" + "=" * 50)
    print("Build complete!")
    print(f"Executable is in: {DIST_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()
