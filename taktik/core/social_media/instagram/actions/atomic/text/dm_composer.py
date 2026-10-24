"""Direct-message composer atomics: find the field, type in it, press send.

Four implementations of this used to exist — the messaging workflow, the DM reply actions, the
DM outreach actions and the engagement bridge's sender mixin. Each had its own way of locating
the composer, its own focus, and its own fallback chain, so a change to the Instagram composer
repaired exactly one of the four and left the other three broken. It was the bridge that had the
most thorough field lookup and the workflow that had the humanised tap; none had both.

This module is their union, and the only place that knows how to talk to a DM composer:

- **finding the field** tries every signature the four used, richest first;
- **focusing it** uses the sampled human tap, with a centre click as fallback, once the Taktik
  keyboard is the phone's keyboard (a switch after the tap can cost the field its focus);
- **typing** goes through the Taktik keyboard only, and counts only when the composer then reads
  exactly the message; a keyboard that fails is a failure, nothing is pasted;
- **sending** tries the xpath catalogue, then the resource-ids, then the content-descriptions.

`device_id` is REQUIRED. The three call sites that resolved it as
`getattr(self.device_manager, 'device_id', None) or 'emulator-5554'` would, on a missing id,
type the message into a device that is not the one running the session — silently.
"""

import time
from typing import Any, Optional

from loguru import logger as _default_logger

from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.shared.input.taktik_keyboard import (
    ensure_taktik_keyboard,
    field_holds_text,
    type_text_checked,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


def resolve_device_id(device, explicit: Optional[str] = None) -> str:
    """Name the device this composer types on, or refuse to type.

    Three call sites used to resolve it as
    ``getattr(self.device_manager, 'device_id', None) or 'emulator-5554'``. That default is
    worse than an error: on a multi-device rig it aims the keyboard at a phone that is not the
    one running the session, and nothing raises. The serial is right there on the device
    object — a facade forwards it — so falling back to a literal was never necessary.
    """
    for candidate in (explicit, getattr(device, "device_id", None), getattr(device, "serial", None)):
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    raise ValueError(
        "Cannot resolve the device id for the DM composer: the Taktik keyboard types on a "
        "named device, and guessing one would type into the wrong phone."
    )


def find_message_input(device, *, logger=None) -> Optional[Any]:
    """Locate the conversation composer, trying every known signature.

    Order matters: the xpath catalogue carries the composer resource-id first and only then
    falls back to looser shapes (an EditText hinted "Message", any clickable EditText), so a
    precise match always wins over a generic one.

    One kind of answer whatever signature matched: a uiautomator2 SELECTOR (`d.xpath(...)` or
    `d(...)`), which has `.exists`, `.info` and `.click()`, or None. The xpath branch used to
    hand back the resolved `XMLElement` instead, which has no `.exists`: the DM reply, which
    checks it, crashed on every conversation found that way (Pixel 6 Pro, Instagram 410,
    2026-10-24: "'XMLElement' object has no attribute 'exists'").
    """
    log = logger or _default_logger
    return _first_selector(
        device,
        xpaths=DM_SELECTORS.message_input,
        ui_selectors=(
            [{"resourceId": rid} for rid in DM_SELECTORS.message_input_resource_ids]
            + [{"className": DM_SELECTORS.edit_text_class_name}]
            + [{"textContains": hint} for hint in DM_SELECTORS.message_input_text_contains]
        ),
        what="DM composer",
        log=log,
    )


def _first_selector(device, *, xpaths, ui_selectors, what: str, log) -> Optional[Any]:
    """The first of `xpaths`, then of `ui_selectors` (keyword sets for `d(...)`), that shows on
    screen, as the selector itself; None when none does. A query that raises is logged and the
    next one asked."""
    for xpath in xpaths:
        try:
            found = device.xpath(xpath)
            if found.exists:
                return found
        except Exception as exc:
            log.warning(f"{what}: {xpath} could not be asked ({exc})")
    for selector in ui_selectors:
        try:
            candidate = device(**selector)
            if candidate.exists:
                return candidate
        except Exception as exc:
            log.warning(f"{what}: {selector} could not be asked ({exc})")
    log.warning(f"{what} not found with any known signature")
    return None


def focus_message_input(device, element, *, logger=None) -> bool:
    """Put the caret in the composer with a sampled human tap, centre click as fallback."""
    log = logger or _default_logger
    if element is None:
        return False
    if tap_element_human(device, element, logger=log):
        return True
    try:
        element.click()
        return True
    except Exception as exc:
        log.warning(f"Could not focus the DM composer: {exc}")
        return False


def type_message(
    device,
    device_id: Optional[str] = None,
    message: str = "",
    *,
    element: Optional[Any] = None,
    typos: bool = True,
    logger=None,
) -> bool:
    """Focus the composer and type `message` through the Taktik Keyboard; False when the
    composer does not then hold exactly it (nothing is pasted instead).

    Typing is humanised by default: occasional adjacent-key mistakes that get noticed and
    corrected, plus think-pauses at word and sentence boundaries. The plan's rendering equals
    the target string exactly — `render_plan` exists to prove it — so a mistake is visible on
    screen for a moment and never committed.

    A DM is the longest text this bot produces and the one a human would most obviously
    re-read while typing. Pass `typos=False` for a field where even a momentary wrong
    character is unacceptable.
    """
    log = logger or _default_logger
    if not message:
        return True
    device_id = resolve_device_id(device, device_id)

    element = element if element is not None else find_message_input(device, logger=log)
    if element is None:
        return False

    # Before the tap: a keyboard switched after it can cost the field its focus.
    ensure_taktik_keyboard(device_id)
    focus_message_input(device, element, logger=log)
    time.sleep(0.3)

    # The typing counts only if the composer then reads exactly the message. Nothing is pasted
    # when it does not: `set_text` or `send_keys` would write the whole message at once.
    if type_text_checked(device, device_id, message, typos=typos):
        return True
    log.error("The Taktik Keyboard did not leave the message in the composer: not sent, nothing pasted")
    return False


def find_send_button(device, *, logger=None) -> Optional[Any]:
    """Locate the send button: xpath catalogue, then resource-ids, then content-descriptions.
    The same kind of answer as `find_message_input`: a selector, or None."""
    return _first_selector(
        device,
        xpaths=DM_SELECTORS.send_button,
        ui_selectors=(
            [{"resourceId": rid} for rid in DM_SELECTORS.send_button_resource_ids]
            + [{"description": desc} for desc in DM_SELECTORS.send_button_content_descriptions]
        ),
        what="DM send button",
        log=logger or _default_logger,
    )


def click_send_button(device, *, logger=None) -> bool:
    """Press send. Human tap on the real bounds, centre click as fallback."""
    log = logger or _default_logger
    button = find_send_button(device, logger=log)
    if button is None:
        return False
    if not tap_element_human(device, button, logger=log):
        try:
            button.click()
        except Exception as exc:
            log.error(f"Could not press the DM send button: {exc}")
            return False
    return True


def send_message(
    device,
    device_id: Optional[str] = None,
    message: str = "",
    *,
    typos: bool = False,
    settle: float = 0.5,
    logger=None,
) -> bool:
    """The whole sequence: find the composer, type, send. False as soon as a step fails."""
    log = logger or _default_logger

    element = find_message_input(device, logger=log)
    if element is None:
        return False
    if not type_message(device, device_id, message, element=element, typos=typos, logger=log):
        return False

    time.sleep(settle)
    if not field_holds_text(device, message):
        log.error("The composer does not hold the requested message: not sent")
        return False
    if not click_send_button(device, logger=log):
        return False

    log.debug(f"DM sent ({len(message)} chars)")
    return True


__all__ = [
    "find_message_input",
    "focus_message_input",
    "type_message",
    "find_send_button",
    "click_send_button",
    "send_message",
]
