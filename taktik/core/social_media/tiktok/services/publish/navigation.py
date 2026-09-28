"""Navigation helpers for the TikTok publish workflow."""

from __future__ import annotations

import time
from typing import Callable

from taktik.core.social_media.tiktok.services.publish.dialogs import handle_permission_dialog
from taktik.core.social_media.tiktok.services.publish.editor_sound import (
    SOUND_KEPT,
    SOUND_UNCHECKED,
    remove_attached_sound,
    sound_removal_is_known,
)
from taktik.core.social_media.tiktok.services.publish.screen_detector import (
    is_camera_creation_screen,
    is_gallery_picker_open,
    is_post_screen,
)
from taktik.core.social_media.tiktok.services.publish.upload_picker import tap_upload_button_from_dump
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
    PUBLISH_CREATION_ENTRY_SELECTORS,
    PUBLISH_EDITOR_SELECTORS,
    PUBLISH_MEDIA_PICKER_SELECTORS,
    PublishCreationEntrySelectors,
    PublishEditorSelectors,
    PublishMediaPickerSelectors,
)
from taktik.core.social_media.tiktok.ui.xpath import tap_element


LogFn = Callable[[str, str], None]
SleepFn = Callable[[float], None]

# What `advance_to_post_screen` answers. The two failures are also the workflow's error types.
POST_SCREEN_REACHED = "post_screen_reached"
POST_SCREEN_NOT_REACHED = "post_screen_not_reached"
SOUND_NOT_REMOVED = "sound_not_removed"


def tap_create_button(
    device,
    *,
    selectors: PublishCreationEntrySelectors = PUBLISH_CREATION_ENTRY_SELECTORS,
    log: LogFn | None = None,
) -> bool:
    """Tap TikTok's Create button by its selectors. Nothing else: when none answers, nothing is
    tapped and the workflow stops (create_btn_not_found), rather than tapping a fixed point of the
    bottom bar."""
    if tap_element(device, selectors.create_btn, timeout=3.0):
        return True
    _log(log, "error", "[create] no selector found TikTok's Create button: nothing tapped")
    return False


def tap_upload_button(
    device,
    *,
    selectors: PublishMediaPickerSelectors = PUBLISH_MEDIA_PICKER_SELECTORS,
    log: LogFn | None = None,
) -> bool:
    """Tap the camera's way into the gallery: by its selectors, then by the bounds the dump gives
    for the same ids. Nothing else. When no selector answers, nothing is tapped and the caller
    stops: the two coordinate fallbacks that stood here tapped whatever lay under a fixed point,
    and on TikTok 47.0.3 that was the effects carousel of the camera (2026-09-27)."""
    if tap_element(device, selectors.upload_btn, timeout=6.0):
        return True
    if tap_upload_button_from_dump(device, selectors=selectors, log=log):
        return True
    _log(log, "error", "[upload] no selector found the way into the gallery on this screen: nothing tapped")
    return False


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
    log: LogFn | None = None,
) -> bool:
    """Select the newest medium of TikTok's gallery by its selectors. Nothing else: when none
    answers, nothing is tapped and the workflow stops (gallery_item_not_found), rather than
    tapping a fixed point of the grid (a thumbnail, whatever it held)."""
    if tap_element(device, selectors.gallery_first_item, timeout=5.0):
        return True
    _log(log, "error", "[gallery] no selector found the newest medium of the gallery: nothing tapped")
    return False


def advance_to_post_screen(
    device,
    *,
    attempts: int = 3,
    selectors: PublishMediaPickerSelectors = PUBLISH_MEDIA_PICKER_SELECTORS,
    editor: PublishEditorSelectors = PUBLISH_EDITOR_SELECTORS,
    sleep: SleepFn = time.sleep,
    log: LogFn | None = None,
) -> str:
    """Tap Next until TikTok shows the post screen; before each Next, take off the sound TikTok
    attached to the video on its own (a video the bot publishes carries no third-party music).

    Returns `POST_SCREEN_REACHED`, or why it stopped: `SOUND_NOT_REMOVED` (a sound stays on the
    video, or the screen could not be read to tell; Next is not tapped), `POST_SCREEN_NOT_REACHED`.
    """
    if not sound_removal_is_known(editor):
        _log(
            log,
            "warning",
            "[sound] the cross of the editor's sound chip is not known for this TikTok version: "
            "a sound TikTok attaches to the video would stay on it",
        )
    for _ in range(attempts):
        if is_post_screen(device):
            return POST_SCREEN_REACHED
        sound = remove_attached_sound(device, editor=editor, picker=selectors, sleep=sleep, log=log)
        if sound in (SOUND_KEPT, SOUND_UNCHECKED):
            return SOUND_NOT_REMOVED
        if not tap_element(device, selectors.next_btn, timeout=3.0):
            break
        sleep(1.5)

    return POST_SCREEN_REACHED if is_post_screen(device) else POST_SCREEN_NOT_REACHED


def _log(log: LogFn | None, level: str, message: str) -> None:
    if log:
        log(level, message)
