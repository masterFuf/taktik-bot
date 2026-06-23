"""Shared computer-vision primitives (platform-agnostic).

Currently: local OCR to locate on-screen UI text that exposes no accessibility node
(IG/TikTok "more"/"suite"/"plus" inline expanders, full-bio expanders, etc.).
"""

from .ocr import OcrService, TextMatch
from .screen_text import locate_text_on_screen, screenshot_pil

__all__ = ["OcrService", "TextMatch", "locate_text_on_screen", "screenshot_pil"]
