"""Reopen a TikTok post from its link.

Measured on device on 2026-08-30 on 46.6.3: firing an `android.intent.action.VIEW` at a collected
short link lands on the post itself, not on the app's home. `https://vm.tiktok.com/ZN8FaXgeY/`
reopened charli d'amelio's video with its caption `dc @Kittrell` intact.

That is what makes a stored `post_url` worth storing at all. The link is useless as an IDENTITY --
TikTok mints a new shortcode on every copy, which is why `tiktok_post_key` exists -- but it
navigates perfectly, and navigating is the whole job here.

The app is force-stopped first. Sending the intent to a running TikTok landed on whatever screen
happened to be up about as often as it landed on the post, because the running task gets resumed
instead of the deep link being honoured.
"""

from __future__ import annotations

import subprocess
import time
from typing import Any, Optional

from loguru import logger

from taktik.core.social_media.tiktok.actions.core.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.creator import (
    VIDEO_CREATOR_SELECTORS,
)

#: The app under test. TikTok also ships as `trill` and `aweme` in some regions; the intent names
#: the package so Android does not offer a chooser, and `musically` is the build these accounts run.
_PACKAGE = "com.zhiliaoapp.musically"

#: How long the app needs between the intent and a readable video screen. Measured at 9-12s on a
#: cold start; the arrival check below is what actually decides, this is only the floor.
_COLD_START_SECONDS = 9.0


def open_post_by_url(
    device: Any,
    post_url: str,
    *,
    device_id: str = "",
    timeout: float = 20.0,
) -> bool:
    """Open the post at `post_url` and return True once a video screen is actually up.

    Returns False when the link is empty, when `am start` fails, or when no video screen appeared
    inside `timeout`. Reporting the intent instead of the arrival would hand the caller whatever
    screen TikTok happened to open -- and a commenter scrape on the wrong post files a stranger's
    audience under this post's name.
    """
    url = (post_url or "").strip()
    if not url:
        return False

    serial = device_id or _serial_of(device)
    base = ["adb"] + (["-s", serial] if serial else [])

    try:
        subprocess.run(base + ["shell", "am", "force-stop", _PACKAGE],
                       capture_output=True, timeout=20)
        time.sleep(1.5)
        started = subprocess.run(
            base + ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url, _PACKAGE],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:
        logger.warning(f"open_post_by_url: could not fire the intent for {url} ({exc})")
        return False

    output = (started.stdout or "") + (started.stderr or "")
    if "Error" in output or "Exception" in output:
        logger.warning(f"open_post_by_url: am start refused {url}: {output.strip()[:120]}")
        return False

    time.sleep(_COLD_START_SECONDS)

    # Arrival, not the intent: the author node is the cheapest proof that a video screen is up.
    deadline = time.time() + max(0.0, timeout - _COLD_START_SECONDS)
    while True:
        if first_matching(device, VIDEO_CREATOR_SELECTORS.author_username):
            logger.info(f"🔗 opened {url}")
            return True
        if time.time() >= deadline:
            logger.warning(f"open_post_by_url: {url} did not open a video screen")
            return False
        time.sleep(1.0)


def _serial_of(device: Any) -> Optional[str]:
    """The adb serial behind a facade, when it exposes one."""
    for attribute in ("serial", "_serial", "device_id"):
        value = getattr(device, attribute, None)
        if isinstance(value, str) and value:
            return value
    inner = getattr(device, "_device", None)
    if inner is not None and inner is not device:
        return _serial_of(inner)
    return None


__all__ = ["open_post_by_url"]
