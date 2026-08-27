"""Shared computer-vision primitives (platform-agnostic).

Three things the accessibility tree cannot give us:
- local OCR, to locate on-screen text that exposes no node (IG/TikTok "more"/"suite"/"plus"
  inline expanders, full-bio expanders, etc.);
- pixel reading of a segmented progress bar, drawn by Compose as a single childless node;
- whether a screenshot shows a screen at all, or the black frame a device returns when the
  surface was not composed at the moment of the grab (see capture.py).
"""

from .capture import capture_non_blank, is_blank_capture
from .ocr import OcrService, TextMatch
from .progress_bar import count_progress_segments, segment_spans
from .screen_text import locate_text_on_screen, screenshot_pil

__all__ = [
    "OcrService",
    "TextMatch",
    "capture_non_blank",
    "count_progress_segments",
    "is_blank_capture",
    "segment_spans",
    "locate_text_on_screen",
    "screenshot_pil",
]
