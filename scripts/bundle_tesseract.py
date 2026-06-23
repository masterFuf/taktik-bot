"""Stage a portable tesseract under ``bot/assets/tesseract/`` for the frozen build.

Decision (build-pipeline): we do NOT commit the tesseract binary to git, and clients must
NOT install anything by hand. Instead this script copies the tesseract already installed on
the BUILD machine (exe + runtime DLLs + the tessdata we need) into ``bot/assets/tesseract/``
so ``build_exe.py`` can ``--add-data`` it into the launcher. At runtime ``OcrService._configure``
resolves ``_MEIPASS/tesseract/tesseract.exe`` + ``_MEIPASS/tesseract/tessdata``.

Languages: ``eng`` is enough for our use (we OCR short Latin words — "more"/"plus"/"suite",
bio expanders — to locate+tap them, not full-text NLP); ``fra`` and ``osd`` are bundled too
when present for robustness.

Run standalone (``python scripts/bundle_tesseract.py``) or let ``build_exe.py`` call it.
Non-fatal: if no source tesseract is found it warns and leaves the folder empty — the build
still works, OCR just degrades to a no-op until a binary is bundled.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEST_DIR = BASE_DIR / "assets" / "tesseract"
DEST_TESSDATA = DEST_DIR / "tessdata"

# tessdata we ship. eng covers the Latin expander words; osd helps orientation; fra is a
# nice-to-have for accuracy. Others are skipped to keep the bundle small.
WANTED_LANGS = ("eng", "fra", "osd")


def _find_source_exe() -> Path | None:
    exe_name = "tesseract.exe" if os.name == "nt" else "tesseract"
    env_cmd = os.environ.get("TAKTIK_TESSERACT_CMD")
    candidates: list[Path] = []
    if env_cmd:
        candidates.append(Path(env_cmd))
    which = shutil.which("tesseract")
    if which:
        candidates.append(Path(which))
    if os.name == "nt":
        for root in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
        ):
            if root:
                candidates.append(Path(root) / "Tesseract-OCR" / exe_name)
    else:
        candidates += [Path("/usr/bin/tesseract"), Path("/usr/local/bin/tesseract"),
                       Path("/opt/homebrew/bin/tesseract")]
    for cand in candidates:
        if cand and cand.is_file():
            return cand.resolve()
    return None


def _find_tessdata(src_dir: Path) -> Path | None:
    # tessdata may live next to the exe, one level up (UB-Mannheim install layout), or via env.
    env_prefix = os.environ.get("TESSDATA_PREFIX")
    for cand in (src_dir / "tessdata", src_dir.parent / "tessdata",
                 Path(env_prefix) if env_prefix else None):
        if cand and cand.is_dir():
            return cand
    return None


def main() -> int:
    src_exe = _find_source_exe()
    if not src_exe:
        print("[bundle_tesseract] WARNING: no tesseract found on this build machine "
              "(set TAKTIK_TESSERACT_CMD or install it). Skipping — OCR will be a no-op "
              "in the build until a binary is bundled.")
        return 0

    src_dir = src_exe.parent
    if DEST_DIR.exists():
        shutil.rmtree(DEST_DIR)
    DEST_TESSDATA.mkdir(parents=True, exist_ok=True)

    # 1) the exe + every runtime DLL sitting next to it (leptonica, etc.).
    shutil.copy2(src_exe, DEST_DIR / src_exe.name)
    dll_count = 0
    for dll in src_dir.glob("*.dll"):
        shutil.copy2(dll, DEST_DIR / dll.name)
        dll_count += 1

    # 2) the tessdata we want.
    src_tessdata = _find_tessdata(src_dir)
    langs_copied: list[str] = []
    if src_tessdata:
        for lang in WANTED_LANGS:
            tf = src_tessdata / f"{lang}.traineddata"
            if tf.is_file():
                shutil.copy2(tf, DEST_TESSDATA / tf.name)
                langs_copied.append(lang)
    if "eng" not in langs_copied:
        print(f"[bundle_tesseract] WARNING: eng.traineddata not found under {src_tessdata}; "
              "OCR accuracy will suffer. Install the English language data.")

    print(f"[bundle_tesseract] staged tesseract from {src_exe}")
    print(f"  -> {DEST_DIR} ({dll_count} DLL(s), langs: {', '.join(langs_copied) or 'NONE'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
