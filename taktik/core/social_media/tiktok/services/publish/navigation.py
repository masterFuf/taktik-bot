"""Navigation helpers for the TikTok publish workflow."""

from __future__ import annotations

import time
from typing import Callable

from taktik.core.social_media.tiktok.services.publish.dialogs import handle_permission_dialog
from taktik.core.social_media.tiktok.services.publish.screen_detector import (
    is_camera_creation_screen,
    is_gallery_picker_open,
    is_post_screen,
)
from taktik.core.social_media.tiktok.services.publish.touch_fallbacks import (
    tap_create_button_fallback,
    tap_first_gallery_item_fallback,
    tap_upload_bottom_left_fallback,
    tap_upload_right_strip_fallback,
)
from taktik.core.social_media.tiktok.services.publish.upload_picker import tap_upload_button_from_dump
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
    PUBLISH_CREATION_ENTRY_SELECTORS,
    PUBLISH_MEDIA_PICKER_SELECTORS,
    PublishCreationEntrySelectors,
    PublishMediaPickerSelectors,
)
from taktik.core.social_media.tiktok.ui.xpath import tap_element


LogFn = Callable[[str, str], None]
SleepFn = Callable[[float], None]


def tap_create_button(
    device,
    *,
    selectors: PublishCreationEntrySelectors = PUBLISH_CREATION_ENTRY_SELECTORS,
    log: LogFn | None = None,
) -> bool:
    """Tap TikTok's Create button, then use a documented coordinate fallback."""
    if tap_element(device, selectors.create_btn, timeout=3.0):
        return True
    return tap_create_button_fallback(device, log=log)


def tap_upload_button(
    device,
    *,
    selectors: PublishMediaPickerSelectors = PUBLISH_MEDIA_PICKER_SELECTORS,
    log: LogFn | None = None,
) -> bool:
    """Tap Upload/Gallery using selectors, dump bounds, then coordinate fallbacks."""
    if tap_element(device, selectors.upload_btn, timeout=6.0):
        return True
    if tap_upload_button_from_dump(device, selectors=selectors, log=log):
        return True
    if tap_upload_right_strip_fallback(device, log=log):
        return True
    return tap_upload_bottom_left_fallback(device, log=log)


def ensure_gallery_picker_open(
    device,
    device_id: str,
    *,
    attempts: int = 3,
    selectors: PublishMediaPickerSelectors = PUBLISH_MEDIA_PICKER_SELECTORS,
    sleep: SleepFn = time.sleep,
    log: LogFn | None = None,
) -> bool:
    """Retry Upload/Gallery taps until TikTok's media picker is visible."""
    for attempt in range(1, attempts + 1):
        sleep(1.2)
        handle_permission_dialog(device, device_id, log=log)
        sleep(1.0)

        if is_gallery_picker_open(device):
            return True

        if is_camera_creation_screen(device):
            _log(
                log,
                "info",
                f"[upload] still on TikTok camera after upload tap; retrying gallery tap ({attempt}/{attempts})",
            )
            tap_upload_button(device, selectors=selectors, log=log)
            continue

        _log(log, "debug", f"[upload] gallery not detected yet ({attempt}/{attempts}); retrying")
        tap_upload_button(device, selectors=selectors, log=log)

    sleep(1.0)
    handle_permission_dialog(device, device_id, log=log)
    return is_gallery_picker_open(device)


def select_first_gallery_item(
    device,
    *,
    selectors: PublishMediaPickerSelectors = PUBLISH_MEDIA_PICKER_SELECTORS,
    sleep: SleepFn = time.sleep,
    log: LogFn | None = None,
) -> bool:
    """Select the most recent media item from TikTok's gallery picker."""
    if tap_element(device, selectors.gallery_first_item, timeout=5.0):
        return True
    return tap_first_gallery_item_fallback(
        device,
        is_camera_creation_screen=lambda: is_camera_creation_screen(device),
        sleep=sleep,
        log=log,
    )


def advance_to_post_screen(
    device,
    *,
    attempts: int = 3,
    selectors: PublishMediaPickerSelectors = PUBLISH_MEDIA_PICKER_SELECTORS,
    sleep: SleepFn = time.sleep,
) -> bool:
    """Tap Next until TikTok reaches the post description screen."""
    for _ in range(attempts):
        if is_post_screen(device):
            return True
        if not tap_element(device, selectors.next_btn, timeout=3.0):
            break
        sleep(1.5)

    return is_post_screen(device)


def _log(log: LogFn | None, level: str, message: str) -> None:
    if log:
        log(level, message)
