"""Publish a TEXT post, the format the bot had no road to.

TikTok's creation screen offers four modes -- CRÉER, PHOTO, TEXTE, LIVE -- beside the gallery
upload the existing workflow drives. This is the TEXTE one, and it is the cheapest content there
is: nothing to film, nothing to edit, nothing to upload. The same argument that made reposting
worth building.

The road, measured end to end on 46.6.3 on 2026-08-30 by publishing a real post:

    Créer -> TEXTE -> type -> Terminé -> "Publi. dans le fil" -> published

Two things this refuses to do on faith.

It never treats the tap on the destination as the publication. A workflow that counted taps would
report posts it never made, which on a publish surface means an operator believing their account
is active while it is silent. What it waits for instead is the destination sheet going away --
matched by resource-id, so it holds in either language. The share sheet TikTok raises on some runs
is taken as a fast yes, never as the only one: it came up in French and never appeared in English
on the same build, and waiting on it alone reports a failure on a post that is online.

And it refuses to publish an empty post. The composer keeps its placeholder when typing fails,
and the placeholder is not text: `set_text` is unavailable on these devices
(`NoSuchMethodException` on `InputManager.getInstance`), so the typing goes through the TAKTIK
keyboard and is read back before anything is confirmed.
"""

import time
from typing import Any, Dict, Optional

from loguru import logger

from taktik.core.shared.input.taktik_keyboard import type_text_human
from ...actions.core.utils import first_matching, first_text
from ...ui.selectors.flows.publish import (
    PUBLISH_CREATION_ENTRY_SELECTORS,
    PUBLISH_TEXT_POST_SELECTORS,
)

#: The composer needs a moment after the mode switch before it accepts a tap.
_COMPOSER_SETTLE = 4.0

#: How long TikTok takes to publish and raise its share sheet. Measured at about two seconds;
#: this is the ceiling, not the expectation.
_PUBLISH_TIMEOUT = 25.0


def publish_text_post(
    device: Any,
    device_id: str,
    text: str,
    *,
    to_story: bool = False,
    click: Optional[Any] = None,
) -> Dict[str, Any]:
    """Write and publish one text post. Returns what happened, step by step.

    `device_id` is separate from `device` because the keyboard types over ADB and needs the
    SERIAL -- passing the device object there is exactly the mistake that made this flow look
    blocked for an hour: `type_text_human` swallows the failure and returns False, the field keeps
    its placeholder, and the screen looks like it refused the text.
    """
    result: Dict[str, Any] = {
        "success": False,
        "step": "start",
        "typed": "",
        "destination": "story" if to_story else "feed",
        "error": None,
    }

    body = (text or "").strip()
    if not body:
        result["error"] = "empty text"
        return result

    tap = click or (lambda selectors, timeout=4: _tap(device, selectors, timeout))

    result["step"] = "open_create"
    if not tap(PUBLISH_CREATION_ENTRY_SELECTORS.create_btn, 6):
        result["error"] = "the Create button was not found"
        return result
    time.sleep(_COMPOSER_SETTLE + 2)

    result["step"] = "mode_text"
    if not tap(PUBLISH_TEXT_POST_SELECTORS.mode_text_tab, 6):
        result["error"] = "the TEXT mode is not offered on this creation screen"
        return result
    time.sleep(_COMPOSER_SETTLE)

    result["step"] = "type"
    if not tap(PUBLISH_TEXT_POST_SELECTORS.text_field, 5):
        result["error"] = "the composer field was not found"
        return result
    time.sleep(1.5)

    if not type_text_human(device_id, body):
        result["error"] = "the keyboard did not type"
        return result
    time.sleep(2.0)

    # Read back before confirming. A composer that still shows its placeholder holds no text, and
    # publishing then would put an empty post on the account.
    written = first_text(device, PUBLISH_TEXT_POST_SELECTORS.text_field)
    result["typed"] = written
    if not _looks_written(written, body):
        result["error"] = f"the composer holds {written[:40]!r} rather than the text"
        return result

    result["step"] = "done"
    if not tap(PUBLISH_TEXT_POST_SELECTORS.done_button, 5):
        result["error"] = "the Done button was not found"
        return result
    time.sleep(_COMPOSER_SETTLE + 2)

    result["step"] = "destination"
    destination = (PUBLISH_TEXT_POST_SELECTORS.post_to_story if to_story
                   else PUBLISH_TEXT_POST_SELECTORS.post_to_feed)
    if not tap(destination, 6):
        result["error"] = f"the {result['destination']} destination was not offered"
        return result

    result["step"] = "verify"
    if not _wait_for_published(device):
        result["error"] = "tapped, but nothing said the post went out"
        return result

    result.update(success=True, step="published")
    logger.success(f"📝 Post texte publié ({len(body)} caractères)")
    return result


# ----------------------------------------------------------------------------------------------


def _tap(device: Any, selectors, timeout: float) -> bool:
    """Tap the first selector that resolves, polling until `timeout`."""
    deadline = time.time() + timeout
    while True:
        for selector in selectors or ():
            try:
                node = device.xpath(selector)
                if node.exists:
                    node.click()
                    return True
            except Exception:
                continue
        if time.time() >= deadline:
            return False
        time.sleep(0.4)


def _looks_written(written: str, wanted: str) -> bool:
    """True when the composer holds the text rather than its own placeholder.

    Compared loosely on the opening of the string: TikTok wraps and truncates long text in the
    node, so an exact match would refuse a post that is perfectly fine.
    """
    from taktik.core.shared.text import fold_for_match

    folded_written = fold_for_match(written)
    folded_wanted = fold_for_match(wanted)
    if not folded_written or not folded_wanted:
        return False
    head = folded_wanted[:24]
    return head in folded_written


def _wait_for_published(device: Any) -> bool:
    """Wait until the post has actually left.

    Two ways of saying yes, because one of them is not always offered. TikTok sometimes raises its
    share sheet on publication -- that is the fast path -- and sometimes goes straight to the
    published post instead. Measured both on the same build: French raised the sheet, English did
    not. What holds either way is that the DESTINATION SHEET GOES AWAY, matched by resource-id so
    the check does not depend on a translation being right.

    The sheet is also what makes this able to say no: a destination tap that did nothing leaves it
    on screen, and the wait then times out instead of announcing a post that was never made.
    """
    deadline = time.time() + _PUBLISH_TIMEOUT
    while True:
        if first_matching(device, PUBLISH_TEXT_POST_SELECTORS.published_indicator):
            return True
        if not first_matching(device, PUBLISH_TEXT_POST_SELECTORS.destination_sheet):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(1.0)


__all__ = ["publish_text_post"]
