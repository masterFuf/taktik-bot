"""Our own profile picture, cropped out of the screen.

TikTok gives no URL for it and no id on the node. What it gives is pixels, so this does what the
Instagram side already does: find the avatar's bounds in the XML dump, screenshot, crop, and hand
back a JPEG data URL the front can render without a network call.

Two things measured on 46.6.3 on 2026-08-30 that shape it:

- The picture is an `ImageView` with NO id and NO description, and every ancestor up to four
  levels is obfuscated. So the anchor is the container, and the biggest match wins -- the
  container holds exactly two images, the 252x252 avatar and the 63x63 "add to story" badge on
  top of it. Picking the larger drops the badge without having to name it.
- The screenshot comes from `shared.vision.screen_text.screenshot_pil`, NOT from `device
  .screenshot_pil`. The latter is a facade method, and the raw device a workflow is handed does
  not have it -- that exact call is what silently killed every TikTok AI qualification until
  yesterday.
"""

import base64
import io
from typing import Any, Optional

from ...core.base_action import BaseAction
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS

#: The badge is a quarter of the avatar's size; anything under this is not a profile picture.
_MIN_AVATAR_PX = 100

#: Enough for a thumbnail, small enough to travel in a bridge message and sit in a row.
_JPEG_QUALITY = 85


class AvatarActions(BaseAction):
    """Read the connected account's profile picture off its own profile page."""

    def __init__(self, device):
        super().__init__(device)
        self.profile_selectors = PROFILE_SELECTORS

    # ------------------------------------------------------------------

    def capture_own_avatar(self) -> Optional[str]:
        """A `data:image/jpeg;base64,...` for our avatar, or None.

        None on every failure rather than a placeholder: a front that receives a picture believes
        it, and an account showing someone else's face is worse than an account showing none.
        Must be called while our own profile page is up.
        """
        bounds = self._largest_avatar_bounds()
        if not bounds:
            self.logger.debug("capture_own_avatar: no avatar node on this screen")
            return None

        screenshot = self._screenshot()
        if screenshot is None:
            self.logger.warning("capture_own_avatar: could not take a screenshot")
            return None

        left, top, right, bottom = bounds
        # A couple of pixels of margin, clamped: the crop must stay inside the image even when the
        # node touches an edge.
        padding = 2
        box = (
            max(0, left - padding),
            max(0, top - padding),
            min(screenshot.size[0], right + padding),
            min(screenshot.size[1], bottom + padding),
        )
        try:
            cropped = screenshot.crop(box).convert("RGB")
            buffer = io.BytesIO()
            cropped.save(buffer, format="JPEG", quality=_JPEG_QUALITY)
        except Exception as exc:
            self.logger.warning(f"capture_own_avatar: crop failed ({exc})")
            return None

        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        self.logger.info(
            f"📸 Avatar capturé ({cropped.size[0]}x{cropped.size[1]}, {len(encoded) // 1024} Ko)"
        )
        return f"data:image/jpeg;base64,{encoded}"

    # ------------------------------------------------------------------

    def _largest_avatar_bounds(self) -> Optional[tuple]:
        """The bounds of the biggest image inside the avatar container, or None.

        Biggest rather than first: the container also holds the story badge, and which of the two
        the dump lists first is not something to rely on.
        """
        best = None
        best_area = 0
        for selector in self.profile_selectors.own_avatar_container:
            try:
                found = self.device.xpath(selector).all()
            except Exception:
                continue
            for element in found:
                bounds = self._bounds_of(element)
                if not bounds:
                    continue
                left, top, right, bottom = bounds
                width, height = right - left, bottom - top
                if width < _MIN_AVATAR_PX or height < _MIN_AVATAR_PX:
                    continue
                area = width * height
                if area > best_area:
                    best, best_area = bounds, area
            if best:
                return best
        return best

    @staticmethod
    def _bounds_of(element: Any) -> Optional[tuple]:
        info = getattr(element, "info", None) or {}
        bounds = info.get("bounds") or {}
        try:
            return (
                int(bounds["left"]), int(bounds["top"]),
                int(bounds["right"]), int(bounds["bottom"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _screenshot(self):
        """Through the shared reader, which knows how to get pixels off either device shape."""
        from taktik.core.shared.vision.screen_text import screenshot_pil

        try:
            return screenshot_pil(self.device)
        except Exception as exc:
            self.logger.debug(f"capture_own_avatar: screenshot unavailable ({exc})")
            return None


__all__ = ["AvatarActions"]
