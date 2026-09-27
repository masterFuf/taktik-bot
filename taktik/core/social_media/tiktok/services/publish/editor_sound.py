"""The sound TikTok attaches on its own to an imported video, taken off before the post screen.

Decision of 2026-09-27: a video the bot publishes carries no third-party music. TikTok 47.0.3
attaches a recommended sound to a video imported from the gallery: the editor shows its title on
the sound chip, with a cross beside it (captures of that day). This service taps the cross, then
reads a fresh dump to check that the chip carries no sound any more, before anyone taps Next.

What the screen says, in four answers:

- `NO_SOUND`: no cross on the screen, so nothing to take off (the gallery, a preview, an editor
  without a sound);
- `SOUND_REMOVED`: a sound was on the video, the cross was tapped, and a fresh dump shows the chip
  without its cross;
- `SOUND_KEPT`: the cross is still there after the taps (or the chip is gone with it): the video
  would leave with that sound, so the publication must stop;
- `SOUND_UNCHECKED`: no dump could be read, so nothing is known: the publication must stop too.

The chip and its cross are version data (`PUBLISH_EDITOR_SELECTORS`, override of 47.0.3). On a
version where the cross was never measured, the service can only answer `NO_SOUND`, and
`sound_removal_is_known` lets the caller say so once in the log.
"""

from __future__ import annotations

import time
from typing import Callable

from lxml import etree

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
    PUBLISH_EDITOR_SELECTORS,
    PUBLISH_MEDIA_PICKER_SELECTORS,
    PublishEditorSelectors,
    PublishMediaPickerSelectors,
)
from taktik.core.social_media.tiktok.ui.xpath import tap_element


LogFn = Callable[[str, str], None]
SleepFn = Callable[[float], None]

NO_SOUND = "no_sound"
SOUND_REMOVED = "sound_removed"
SOUND_KEPT = "sound_kept"
SOUND_UNCHECKED = "sound_unchecked"

# TikTok may attach the sound a moment after the editor opens: the screen is read a few times
# before concluding that no sound came.
SETTLE_SECONDS = 3.0
POLL_SECONDS = 0.5
# How long the chip takes to redraw after the cross is tapped, and how many taps it gets.
VERIFY_DELAY_SECONDS = 1.0
REMOVE_ATTEMPTS = 2


def sound_removal_is_known(editor: PublishEditorSelectors = PUBLISH_EDITOR_SELECTORS) -> bool:
    """Is the cross of the sound chip known for the TikTok version these selectors describe?"""
    return bool(editor.sound_remove_btn)


def remove_attached_sound(
    device,
    *,
    editor: PublishEditorSelectors = PUBLISH_EDITOR_SELECTORS,
    picker: PublishMediaPickerSelectors = PUBLISH_MEDIA_PICKER_SELECTORS,
    settle_seconds: float = SETTLE_SECONDS,
    poll_seconds: float = POLL_SECONDS,
    sleep: SleepFn = time.sleep,
    log: LogFn | None = None,
) -> str:
    """Take off the sound TikTok attached to the video on screen; say what the screen shows after.

    Returns `NO_SOUND`, `SOUND_REMOVED`, `SOUND_KEPT` or `SOUND_UNCHECKED` (see the module).
    """
    if not sound_removal_is_known(editor):
        return NO_SOUND

    tree = _wait_for_cross(device, editor, picker, settle_seconds, poll_seconds, sleep, log)
    if tree is None:
        _log(log, "error", "[sound] the screen could not be read: whether a sound is on the video is unknown")
        return SOUND_UNCHECKED
    if _matches(tree, picker.gallery_first_item, log):
        # The gallery is drawn over the camera, whose own sound chip stays in the dump: it is not
        # the video's, and tapping its cross would land on the gallery.
        return NO_SOUND
    if not _matches(tree, editor.sound_remove_btn, log):
        return NO_SOUND

    _log(log, "info", f"[sound] TikTok attached a sound to the video ({_chip_label(tree, editor, log)!r}): taking it off")
    for attempt in range(1, REMOVE_ATTEMPTS + 1):
        if not tap_element(device, editor.sound_remove_btn, timeout=1.0):
            _log(log, "warning", f"[sound] the cross of the sound chip could not be tapped ({attempt}/{REMOVE_ATTEMPTS})")
        sleep(VERIFY_DELAY_SECONDS)
        tree = _read(device, log)
        if tree is None:
            _log(log, "error", "[sound] the screen could not be read after the tap: the sound is not known to be gone")
            return SOUND_UNCHECKED
        chip_shown = _matches(tree, editor.sound_chip, log)
        cross_shown = _matches(tree, editor.sound_remove_btn, log)
        if chip_shown and not cross_shown:
            _log(log, "info", f"[sound] sound taken off; the chip reads {_chip_label(tree, editor, log)!r}")
            return SOUND_REMOVED
        if not chip_shown:
            _log(log, "error", "[sound] the sound chip left the screen after the tap: the sound is not known to be gone")
            return SOUND_KEPT

    _log(log, "error", f"[sound] the sound is still on the video after {REMOVE_ATTEMPTS} taps on its cross")
    return SOUND_KEPT


def _wait_for_cross(device, editor, picker, settle_seconds, poll_seconds, sleep, log):
    """The last dump read while waiting for the cross; None when no dump could be read.

    Stops early on the cross, and on the gallery, where no sound of the video is shown.
    """
    polls = max(1, int(round(settle_seconds / poll_seconds)) + 1)
    last_read = None
    for index in range(polls):
        tree = _read(device, log)
        if tree is not None:
            last_read = tree
            if _matches(tree, picker.gallery_first_item, log) or _matches(tree, editor.sound_remove_btn, log):
                return tree
        if index < polls - 1:
            sleep(poll_seconds)
    return last_read


def _read(device, log):
    try:
        xml = device.dump_hierarchy(compressed=False)
    except Exception as exc:  # noqa: BLE001 - a lost dump is reported, the caller decides
        _log(log, "warning", f"[sound] screen dump failed: {exc}")
        return None
    tree = parse_ui_dump(xml)
    if tree is None:
        _log(log, "warning", "[sound] screen dump did not parse")
    return tree


def _matches(tree, xpaths, log) -> bool:
    for xpath in xpaths:
        try:
            if tree.xpath(xpath):
                return True
        except etree.XPathError as exc:
            # One broken selector: said, and the next one still reads.
            _log(log, "warning", f"[sound] selector {xpath!r} is invalid: {exc}")
    return False


def _chip_label(tree, editor, log) -> str:
    for xpath in editor.sound_chip:
        try:
            nodes = tree.xpath(xpath)
        except etree.XPathError as exc:
            _log(log, "warning", f"[sound] selector {xpath!r} is invalid: {exc}")
            continue
        if nodes:
            return nodes[0].get("text") or ""
    return ""


def _log(log: LogFn | None, level: str, message: str) -> None:
    if log:
        log(level, message)
    else:
        from loguru import logger

        getattr(logger, level)(message)


__all__ = [
    "NO_SOUND",
    "SOUND_KEPT",
    "SOUND_REMOVED",
    "SOUND_UNCHECKED",
    "remove_attached_sound",
    "sound_removal_is_known",
]
