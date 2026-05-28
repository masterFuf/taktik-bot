"""Screen detection helpers for the TikTok publish workflow."""

from __future__ import annotations

import time
from typing import Callable

from lxml import etree

from taktik.core.social_media.tiktok.ui.selectors.publish import (
    PUBLISH_SELECTORS,
    PublishSelectors,
)
from taktik.core.social_media.tiktok.ui.xpath import to_lxml


LogFn = Callable[[str, str], None]


def is_gallery_picker_open(
    device,
    selectors: PublishSelectors = PUBLISH_SELECTORS,
    selector_timeout: float = 0.4,
) -> bool:
    """Return True when the TikTok media picker/grid is visible."""
    for selector in selectors.gallery_first_item:
        try:
            if device.xpath(selector).wait(timeout=selector_timeout):
                return True
        except Exception:
            pass

    try:
        xml = device.dump_hierarchy(compressed=False)
        return selectors.has_gallery_picker_marker(xml)
    except Exception:
        return False


def is_camera_creation_screen(
    device,
    selectors: PublishSelectors = PUBLISH_SELECTORS,
) -> bool:
    """Return True when TikTok is on the camera/create screen."""
    try:
        xml = device.dump_hierarchy(compressed=False)
        return selectors.has_camera_creation_marker(xml)
    except Exception:
        return False


def is_post_screen(
    device,
    selectors: PublishSelectors = PUBLISH_SELECTORS,
) -> bool:
    """Return True when TikTok is on the post description screen."""
    try:
        xml = device.dump_hierarchy(compressed=False)
        if selectors.has_post_screen_marker(xml):
            return True

        tree = etree.fromstring(xml.encode("utf-8"))
        for xpath in selectors.post_screen_indicators:
            try:
                if tree.xpath(to_lxml(xpath)):
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False


def is_video_edit_screen(
    device,
    selectors: PublishSelectors = PUBLISH_SELECTORS,
) -> bool:
    """Return True when TikTok opened the post-upload video editor."""
    try:
        xml = device.dump_hierarchy(compressed=False)
        return selectors.has_video_edit_screen_marker(xml)
    except Exception:
        return False


def wait_for_tiktok_home(
    device,
    selectors: PublishSelectors = PUBLISH_SELECTORS,
    timeout: float = 60.0,
    per_selector_timeout: float = 2.0,
    log: LogFn | None = None,
    clock: Callable[[], float] = time.time,
) -> bool:
    """Poll until TikTok's home screen is ready."""
    start = clock()
    last_log = start

    while True:
        elapsed = clock() - start
        if elapsed >= timeout:
            if log:
                log("warning", f"TikTok home not detected after {timeout:.0f}s, proceeding anyway")
            return False

        for xpath in selectors.home_ready_indicators:
            try:
                if device.xpath(xpath).wait(timeout=per_selector_timeout):
                    if log:
                        log("info", f"TikTok home ready in {clock() - start:.1f}s")
                    return True
            except Exception:
                pass
            if clock() - start >= timeout:
                break

        now = clock()
        if now - last_log >= 10.0:
            if log:
                log("info", f"Waiting for TikTok home... ({int(now - start)}s)")
            last_log = now
