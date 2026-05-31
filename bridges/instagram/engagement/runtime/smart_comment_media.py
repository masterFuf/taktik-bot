"""Media capture helpers for the Instagram Smart Comment bridge."""

from __future__ import annotations

import os
from datetime import datetime

from bridges.instagram.runtime.ipc import logger, send_message as send_event


class SmartCommentMediaMixin:
    """Screenshot capture used by Smart Comment vision analysis."""

    def take_post_screenshot(self):
        """Take a screenshot of the current post for vision AI analysis."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder = os.path.join(os.environ.get("TEMP", "/tmp"), "taktik_smart_comment")
            os.makedirs(folder, exist_ok=True)
            filepath = os.path.join(folder, f"post_{timestamp}.png")

            screenshot = self.device.screenshot()
            screenshot.save(filepath, format="PNG")

            logger.info(f"Post screenshot saved: {filepath}")
            send_event("screenshot", path=filepath)
            return filepath
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None
