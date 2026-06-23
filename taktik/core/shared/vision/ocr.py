"""Local, free OCR — locate words/phrases in an image and return their bounding boxes.

Reusable primitive: many IG/TikTok controls render text as a ClickableSpan with NO
accessibility node (the "more" / "suite" / "plus" comment expanders, the full-bio
"more", …). They cannot be located in a UI dump, so we OCR a screenshot region and
tap the word's real on-screen position.

Backed by tesseract (pytesseract). Degrades gracefully: if pytesseract or the tesseract
binary is unavailable, ``locate`` logs once and returns ``[]`` — callers simply skip the
OCR-driven action (no crash). Pure: takes an image in, returns matches; no device access
(see ``screen_text`` for the device-aware wrapper).
"""

from __future__ import annotations

import re
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

    @classmethod
    def _pytesseract(cls):
        """Return the pytesseract module if usable, else None (logged once)."""
        try:
            import pytesseract  # noqa: PLC0415 (lazy: optional dep)
            return pytesseract
        except Exception:
            if not cls._unavailable_warned:
                cls._unavailable_warned = True
                logger.warning(
                    "OCR unavailable: `pip install pytesseract` and install the tesseract "
                    "binary (UB-Mannheim build on Windows). OCR-driven taps are skipped."
                )
            return None

    @classmethod
    def available(cls) -> bool:
        """True if pytesseract import AND the tesseract binary both resolve."""
        pt = cls._pytesseract()
        if pt is None:
            return False
        try:
            pt.get_tesseract_version()
            return True
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
    ) -> List[TextMatch]:
        """Return every box whose recognised word matches one of ``queries``.

        ``region`` (x1,y1,x2,y2) limits OCR to a crop (faster + avoids matching the word
        elsewhere on screen); returned boxes are mapped back to the FULL image space.
        Matching is case-insensitive on the punctuation-stripped word; ``whole_word``
        requires an exact token match (else substring). Returns ``[]`` if OCR is
        unavailable or nothing matches.
        """
        pt = cls._pytesseract()
        if pt is None:
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
            config = "--psm 11"  # sparse text: find as much text as possible, any orientation
            data = pt.image_to_data(img, output_type=pt.Output.DICT,
                                    **({"lang": lang} if lang else {}), config=config)
        except Exception as exc:
            if not cls._unavailable_warned:
                cls._unavailable_warned = True
                logger.warning(f"OCR unavailable (tesseract call failed): {exc}")
            return []

        matches: List[TextMatch] = []
        words = data.get("text", [])
        for i, raw in enumerate(words):
            token = (raw or "").strip().strip(_TRIM).lower()
            if not token:
                continue
            try:
                conf = float(data["conf"][i])
            except (ValueError, KeyError, IndexError):
                conf = -1.0
            if conf < min_confidence:
                continue
            hit = token in wanted if whole_word else any(w in token for w in wanted)
            if not hit:
                continue
            matches.append(TextMatch(
                text=raw.strip(),
                confidence=conf,
                left=int(data["left"][i]) + ox,
                top=int(data["top"][i]) + oy,
                width=int(data["width"][i]),
                height=int(data["height"][i]),
            ))
        return matches


__all__ = ["OcrService", "TextMatch"]
