"""Shared computer-vision primitives (platform-agnostic).

Two things the accessibility tree cannot give us:
- local OCR, to locate on-screen text that exposes no node (IG/TikTok "more"/"suite"/"plus"
  inline expanders, full-bio expanders, etc.);
- pixel reading of a segmented progress bar, drawn by Compose as a single childless node.
"""

from .ocr import OcrService, TextMatch
from .progress_bar import count_progress_segments, segment_spans
from .screen_text import locate_text_on_screen, screenshot_pil

__all__ = [
    "OcrService",
    "TextMatch",
    "count_progress_segments",
    "segment_spans",
    "locate_text_on_screen",
    "screenshot_pil",
]
