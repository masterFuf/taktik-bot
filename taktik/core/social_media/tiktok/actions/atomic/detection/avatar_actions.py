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

#: The smallest thing that can be the avatar, as a FRACTION OF SCREEN WIDTH -- not a pixel count.
#:
#: A literal 100 px encodes one screen. Measured on a 1080-wide phone the avatar is 256 px, so
#: 0.24 of the width, and the story badge beside it is about a quarter of that, so 0.06. A
#: threshold at 0.10 sits cleanly between the two on any density: 108 px on a 1080 screen, 72 on
#: a 720 one, 144 on a 1440 one. The literal would have rejected the real avatar on a low-density
#: device -- the filter meant to exclude the badge would have excluded the picture.
_MIN_AVATAR_WIDTH_RATIO = 0.10

#: Last resort when the screen cannot be measured at all: the old literal, which is right for the
#: 1080-wide phones this was written on and wrong nowhere it can now be reached.
_MIN_AVATAR_PX_FALLBACK = 100

#: Enough for a thumbnail, small enough to travel in a bridge message and sit in a row.
_JPEG_QUALITY = 85


class AvatarActions(BaseAction):
    """Read a profile picture off the profile page currently on screen.

    Written for our own account first; a VISITED profile carries the same picture in a different
    container depending on the build, which is why the search covers both. Measured on the ten
    captured surfaces of each version: on a visited profile `own_avatar_container` answers on
    46.6.3 and `profile_photo` on 43.1.4 — neither alone covers both, their union does.
    """

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
        return self.capture_avatar()

    def capture_avatar(self) -> Optional[str]:
        """The avatar of WHATEVER profile is on screen, ours or somebody else's.

        Same body, no second spelling: the only thing that differed between the two cases was
        which container the picture sits in, and the search now covers both. 789 stored TikTok
        profiles carry no picture at all because the visited-profile extractor never asked for one.
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
        minimum = self._min_avatar_side()
        # Les DEUX conteneurs : sur un profil visite, `own_avatar_container` repond en 46.6.3 et
        # `profile_photo` en 43.1.4. Prendre l'un des deux seulement rend une version aveugle.
        containers = list(self.profile_selectors.own_avatar_container)
        for extra in getattr(self.profile_selectors, "profile_photo", ()):
            if extra not in containers:
                containers.append(extra)
        for selector in containers:
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
                if width < minimum or height < minimum:
                    continue
                area = width * height
                if area > best_area:
                    best, best_area = bounds, area
            if best:
                return best
        return best

    def _min_avatar_side(self) -> float:
        """The threshold in pixels FOR THIS SCREEN, derived from its width."""
        try:
            width, _height = self.device.get_screen_size()
            if width and width > 0:
                return width * _MIN_AVATAR_WIDTH_RATIO
        except Exception as exc:
            self.logger.debug(f"avatar: screen size unreadable ({exc}); pixel fallback")
        return float(_MIN_AVATAR_PX_FALLBACK)

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
