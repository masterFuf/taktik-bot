"""Local, free OCR — locate words/phrases in an image and return their bounding boxes.

Reusable primitive: many IG/TikTok controls render text as a ClickableSpan with NO
accessibility node (the "more" / "suite" / "plus" comment expanders, the full-bio
"more", …). They cannot be located in a UI dump, so we OCR a screenshot region and
tap the word's real on-screen position.

Backed directly by the tesseract CLI. Degrades gracefully: if the binary is unavailable,
``locate`` logs once and returns ``[]`` — callers simply skip the OCR-driven action (no
crash). Pure: takes an image in, returns matches; no device access (see ``screen_text``
for the device-aware wrapper).
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

from loguru import logger

try:  # Pillow is a hard dep; keep the import defensive anyway.
    from PIL import Image
    _PIL_IMAGE = Image.Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    _PIL_IMAGE = object  # type: ignore

ImageInput = Union["_PIL_IMAGE", str, bytes]
Region = Tuple[int, int, int, int]  # (x1, y1, x2, y2) in image pixels

# Strip surrounding punctuation/quotes so an OCR'd "more," or "«more»" still matches "more".
_TRIM = " \t\n\r·•.,;:!?…\"'«»“”()[]{}"


@dataclass
class TextMatch:
    """One OCR hit: the recognised word + its box (in the FULL image's pixel space)."""
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int

    @property
    def center(self) -> Tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    @property
    def bbox(self) -> Region:
        return (self.left, self.top, self.left + self.width, self.top + self.height)


class OcrService:
    """Locate text in an image via tesseract. Stateless; methods are classmethods."""

    _unavailable_warned = False
    _resolved = False
    _tesseract_cmd: Optional[str] = None

    @classmethod
    def _resolve_tesseract_cmd(cls) -> Optional[str]:
        """Resolve the bundled/system tesseract executable once.

        Resolution order: ``TAKTIK_TESSERACT_CMD`` env → a ``tesseract/`` folder bundled
        next to the frozen executable / in PyInstaller ``_MEIPASS`` → standard Windows
        install locations → ``PATH``. ``TESSDATA_PREFIX`` follows a bundled executable
        when its sibling ``tessdata`` folder exists.
        """
        if cls._resolved:
            return cls._tesseract_cmd

        exe_name = "tesseract.exe" if os.name == "nt" else "tesseract"
        candidates = []
        env_cmd = os.environ.get("TAKTIK_TESSERACT_CMD")
        if env_cmd:
            candidates.append((env_cmd, os.path.join(os.path.dirname(env_cmd), "tessdata")))
        for base in (getattr(sys, "_MEIPASS", None),
                     os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else None):
            if base:
                folder = os.path.join(base, "tesseract")
                candidates.append((os.path.join(folder, exe_name), os.path.join(folder, "tessdata")))
        # Standard host install locations (dev machines / a system-installed tesseract) —
        # so it's found even when the install's PATH update hasn't reached this process.
        if os.name == "nt":
            for root in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                         os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                         os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
                if root:
                    folder = os.path.join(root, "Tesseract-OCR")
                    candidates.append((os.path.join(folder, exe_name), os.path.join(folder, "tessdata")))
        for cmd, tessdata in candidates:
            resolved = cmd if cmd and os.path.isfile(cmd) else shutil.which(cmd or "")
            if resolved:
                cls._tesseract_cmd = resolved
                cls._resolved = True
                if os.path.isdir(tessdata):
                    os.environ["TESSDATA_PREFIX"] = tessdata
                logger.debug(f"OCR: using tesseract at {resolved}")
                return resolved

        cls._tesseract_cmd = shutil.which(exe_name)
        cls._resolved = True
        if cls._tesseract_cmd:
            logger.debug(f"OCR: using tesseract at {cls._tesseract_cmd}")
        return cls._tesseract_cmd

    @classmethod
    def prepare(cls) -> bool:
        """Resolve the lightweight CLI dependency without importing native Python modules."""
        return cls._resolve_tesseract_cmd() is not None

    @staticmethod
    def _startupinfo():
        if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
            return None
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        return startupinfo

    @classmethod
    def _image_to_tsv(
        cls,
        command: str,
        image,
        *,
        lang: Optional[str],
        timeout_seconds: float,
    ) -> str:
        """Run tesseract out-of-process and return its TSV word data."""
        encoded = io.BytesIO()
        image.save(encoded, format="PNG")

        args = [command, "stdin", "stdout"]
        if lang:
            args.extend(("-l", lang))
        args.extend(("--psm", "11", "tsv"))

        completed = subprocess.run(
            args,
            input=encoded.getvalue(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=max(0.1, float(timeout_seconds)),
            startupinfo=cls._startupinfo(),
        )
        if completed.returncode != 0:
            error = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(error or f"tesseract exited with code {completed.returncode}")
        return completed.stdout.decode("utf-8", errors="replace")

    @classmethod
    def available(cls) -> bool:
        """True if the tesseract binary resolves and starts successfully."""
        command = cls._resolve_tesseract_cmd()
        if command is None:
            return False
        try:
            completed = subprocess.run(
                [command, "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=3.0,
                startupinfo=cls._startupinfo(),
            )
            return completed.returncode == 0
        except Exception:
            if not cls._unavailable_warned:
                cls._unavailable_warned = True
                logger.warning("OCR unavailable: tesseract binary not found on the host.")
            return False

    @staticmethod
    def _load(image: ImageInput):
        if Image is None:
            return None
        if isinstance(image, _PIL_IMAGE):
            return image
        try:
            if isinstance(image, (bytes, bytearray)):
                import io
                return Image.open(io.BytesIO(image))
            return Image.open(image)  # path-like
        except Exception as exc:
            logger.debug(f"OCR: could not load image: {exc}")
            return None

    @classmethod
    def locate(
        cls,
        image: ImageInput,
        queries: Union[str, Sequence[str]],
        *,
        region: Optional[Region] = None,
        min_confidence: float = 40.0,
        whole_word: bool = True,
        lang: Optional[str] = None,
        timeout_seconds: float = 5.0,
    ) -> List[TextMatch]:
        """Return every box whose recognised word matches one of ``queries``.

        ``region`` (x1,y1,x2,y2) limits OCR to a crop (faster + avoids matching the word
        elsewhere on screen); returned boxes are mapped back to the FULL image space.
        Matching is case-insensitive on the punctuation-stripped word; ``whole_word``
        requires an exact token match (else substring). Returns ``[]`` if OCR is
        unavailable or nothing matches.
        """
        command = cls._resolve_tesseract_cmd()
        if command is None:
            if not cls._unavailable_warned:
                cls._unavailable_warned = True
                logger.warning(
                    "OCR unavailable: tesseract binary not found. OCR-driven taps are skipped."
                )
            return []
        img = cls._load(image)
        if img is None:
            return []

        ox, oy = 0, 0
        if region:
            x1, y1, x2, y2 = region
            x1, y1 = max(0, x1), max(0, y1)
            try:
                img = img.crop((x1, y1, x2, y2))
            except Exception as exc:
                logger.debug(f"OCR: crop failed ({region}): {exc}")
                return []
            ox, oy = x1, y1

        wanted = [queries] if isinstance(queries, str) else list(queries)
        wanted = [w.strip().lower() for w in wanted if w and w.strip()]
        if not wanted:
            return []

        try:
            tsv = cls._image_to_tsv(
                command,
                img,
                lang=lang,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            if not cls._unavailable_warned:
                cls._unavailable_warned = True
                logger.warning(f"OCR unavailable (tesseract call failed): {exc}")
            return []

        matches: List[TextMatch] = []
        for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
            raw = row.get("text") or ""
            token = (raw or "").strip().strip(_TRIM).lower()
            if not token:
                continue
            try:
                conf = float(row.get("conf") or -1)
            except (TypeError, ValueError):
                conf = -1.0
            if conf < min_confidence:
                continue
            hit = token in wanted if whole_word else any(w in token for w in wanted)
            if not hit:
                continue
            matches.append(TextMatch(
                text=raw.strip(),
                confidence=conf,
                left=int(row["left"]) + ox,
                top=int(row["top"]) + oy,
                width=int(row["width"]),
                height=int(row["height"]),
            ))
        return matches


__all__ = ["OcrService", "TextMatch"]
