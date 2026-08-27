"""Is a screenshot worth keeping, or did the device hand us a black frame?

`device.screenshot()` succeeds and returns an image even when the surface was not composed at the
moment of the grab. What comes back is uniformly black, and nothing downstream can tell it apart
from a real capture: it is a valid JPEG of the right size.

Measured on the production base on 2026-08-27: 116 of 28 983 stored AI screenshots are the SAME
black frame, byte for byte, and one qualification run reached 20 % of them. They were sent to the
vision model, which answered with a niche and a confidence of 0.95 — inventing from the username
what it could not see. A black screenshot is worse than no screenshot at all, because the empty
answer it produces is indistinguishable from a real one.

Platform-agnostic on purpose: Instagram, TikTok and the Cartography Lab all take screenshots the
same way, and a black frame means the same thing everywhere.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

# A real screen — even one with a dark theme — carries text, avatars and icons, so its brightest
# pixel is near 255. A frame whose BRIGHTEST pixel is still almost black was never drawn. The
# threshold is deliberately low: the cost of calling a real capture blank is a lost qualification,
# while the cost of accepting a black one is a confident answer about nothing.
_MAX_BRIGHTNESS_FOR_BLANK = 12


def is_blank_capture(image, *, max_brightness: int = _MAX_BRIGHTNESS_FOR_BLANK) -> bool:
    """True when the image shows nothing at all — a black frame rather than a screen.

    Reads the brightest pixel of the greyscale conversion, which is one C-level pass over the
    buffer. Returns False when the image cannot be read: refusing to judge is safer than declaring
    a capture blank on the strength of an exception.
    """
    if image is None:
        return True
    try:
        extrema = image.convert("L").getextrema()
    except Exception as exc:  # a non-PIL object, a truncated buffer…
        logger.debug(f"blank-capture check skipped: {exc}")
        return False
    # getextrema() returns (min, max) for a single band.
    if not extrema or len(extrema) != 2:
        return False
    _darkest, brightest = extrema
    return brightest <= max_brightness


def capture_non_blank(device, *, attempts: int = 2, retry_delay: float = 0.6) -> Optional[object]:
    """Screenshot the device, retrying while the frame comes back blank.

    Returns the first usable PIL image, or None when every attempt was blank — the caller then
    knows it has nothing to show, instead of holding a black image it believes is a screen.

    The retry is a plain wait rather than a UI condition: what we are waiting for is the surface to
    be composed, which no accessibility node reports. One extra attempt is enough in practice; the
    point is not to fight a device that is off, it is to survive a capture taken mid-transition.
    """
    import time

    for attempt in range(max(1, attempts)):
        try:
            image = device.screenshot()
        except Exception as exc:
            logger.debug(f"screenshot attempt {attempt + 1} raised: {exc}")
            image = None

        if image is not None and not is_blank_capture(image):
            return image

        if attempt + 1 < max(1, attempts):
            time.sleep(retry_delay)

    return None
