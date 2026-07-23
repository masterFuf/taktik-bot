"""Device-aware OCR helper: screenshot the device, locate on-screen text, return boxes.

Reusable across platforms/workflows to tap UI text that has no accessibility node
(IG/TikTok "more"/"suite"/"plus" expanders, full-bio "more", …): pass a ``region``
(an element's bounds from the UI dump) to limit OCR to that element and get the word's
real on-screen coordinates back. Platform-agnostic (lives in shared/).
"""

from __future__ import annotations

import base64
import io
from typing import List, Optional, Sequence, Tuple, Union

from loguru import logger
from PIL import Image

from taktik.core.shared.actions.optional_call import run_bounded_optional

from .ocr import OcrService, TextMatch

Region = Tuple[int, int, int, int]


def screenshot_pil(device, *, timeout_seconds: float = 5.0):
    """Best-effort full-resolution PIL screenshot of the device, or None.

    Works with the uiautomator2 device or a facade exposing it as ``_device``.
    A real uiautomator2 screenshot uses the JSON-RPC endpoint directly so its
    optional OCR path cannot inherit u2's multi-minute global HTTP timeout.
    """
    target = getattr(device, "_device", None) or device

    jsonrpc = getattr(target, "jsonrpc", None)
    if jsonrpc is not None:
        try:
            encoded = jsonrpc.takeScreenshot(
                1,
                80,
                http_timeout=max(0.1, float(timeout_seconds)),
            )
            if encoded:
                image = Image.open(io.BytesIO(base64.b64decode(encoded)))
                image.load()
                return image
        except Exception as exc:
            logger.debug(f"bounded screenshot failed: {exc}")
        # Do not retry through target.screenshot(): on u2 that would restore the
        # global (multi-minute) HTTP timeout we are explicitly avoiding here.
        return None

    for attempt in (
        lambda: target.screenshot(),                 # u2 default -> PIL.Image
        lambda: target.screenshot(format="pillow"),  # explicit
    ):
        try:
            img = attempt()
        except TypeError:
            continue
        except Exception as exc:
            logger.debug(f"screenshot failed: {exc}")
            continue
        if img is not None and hasattr(img, "crop"):  # looks like a PIL image
            return img
    logger.debug("screenshot: no PIL image returned")
    return None


def locate_text_on_screen(
    device,
    queries: Union[str, Sequence[str]],
    *,
    region: Optional[Region] = None,
    min_confidence: float = 40.0,
    whole_word: bool = True,
    lang: Optional[str] = None,
    screenshot_timeout_seconds: float = 5.0,
    operation_timeout_seconds: float = 8.0,
) -> List[TextMatch]:
    """Screenshot the device and OCR-locate ``queries`` (optionally within ``region``).

    Returns matches in FULL-screen pixel coordinates (tap-ready via ``.center``), or
    ``[]`` if the screenshot or OCR is unavailable.
    """
    def locate() -> List[TextMatch]:
        img = screenshot_pil(device, timeout_seconds=screenshot_timeout_seconds)
        if img is None:
            return []
        return OcrService.locate(
            img, queries, region=region, min_confidence=min_confidence,
            whole_word=whole_word, lang=lang,
        )

    result = run_bounded_optional(
        locate,
        timeout_seconds=operation_timeout_seconds,
        label="screen text OCR",
    )
    return result.value or []


__all__ = ["locate_text_on_screen", "screenshot_pil", "TextMatch"]
