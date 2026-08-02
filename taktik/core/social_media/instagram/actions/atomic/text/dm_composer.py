"""Direct-message composer atomics: find the field, type in it, press send.

Four implementations of this used to exist — the messaging workflow, the DM reply actions, the
DM outreach actions and the engagement bridge's sender mixin. Each had its own way of locating
the composer, its own focus, and its own fallback chain, so a change to the Instagram composer
repaired exactly one of the four and left the other three broken. It was the bridge that had the
most thorough field lookup and the workflow that had the humanised tap; none had both.

This module is their union, and the only place that knows how to talk to a DM composer:

- **finding the field** tries every signature the four used, richest first;
- **focusing it** uses the sampled human tap, with a centre click as fallback;
- **typing** goes through the Taktik keyboard, then `set_text`, then `send_keys`;
- **sending** tries the xpath catalogue, then the resource-ids, then the content-descriptions.

`device_id` is REQUIRED. The three call sites that resolved it as
`getattr(self.device_manager, 'device_id', None) or 'emulator-5554'` would, on a missing id,
type the message into a device that is not the one running the session — silently.
"""

import time
from typing import Any, Optional

from loguru import logger as _default_logger

from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.shared.input.taktik_keyboard import type_text_human
from ....ui.selectors.surfaces.direct_messages import DM_SELECTORS


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


def find_message_input(device, *, timeout: float = 5.0, logger=None) -> Optional[Any]:
    """Locate the conversation composer, trying every known signature.

    Order matters: the xpath catalogue carries the composer resource-id first and only then
    falls back to looser shapes (an EditText hinted "Message", any clickable EditText), so a
    precise match always wins over a generic one.
    """
    log = logger or _default_logger

    for selector in DM_SELECTORS.message_input:
        try:
            found = device.xpath(selector)
            if found.exists:
                return found.get(timeout=timeout)
        except Exception:
            continue

    for resource_id in DM_SELECTORS.message_input_resource_ids:
        try:
            candidate = device(resourceId=resource_id)
            if candidate.exists:
                return candidate
        except Exception:
            continue

    try:
        candidate = device(className=DM_SELECTORS.edit_text_class_name)
        if candidate.exists:
            return candidate
    except Exception:
        pass

    for hint in DM_SELECTORS.message_input_text_contains:
        try:
            candidate = device(textContains=hint)
            if candidate.exists:
                return candidate
        except Exception:
            continue

    log.warning("DM composer not found with any known signature")
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
    typos: bool = False,
    logger=None,
) -> bool:
    """Focus the composer and type `message`, falling back until something lands.

    `typos=True` routes through the humanised typing plan (adjacent-key mistakes that get
    corrected, think-pauses). The plan's rendering equals the target exactly, so a mistake is
    never committed — but it stays opt-in per caller.
    """
    log = logger or _default_logger
    if not message:
        return True
    device_id = resolve_device_id(device, device_id)

    element = element if element is not None else find_message_input(device, logger=log)
    if element is None:
        return False

    focus_message_input(device, element, logger=log)
    time.sleep(0.3)

    if type_text_human(device_id, message, typos=typos):
        return True

    log.warning("Taktik Keyboard failed, falling back to set_text")
    try:
        element.set_text(message)
        return True
    except Exception as exc:
        log.warning(f"set_text failed: {exc}, trying send_keys")

    try:
        element.send_keys(message)
        return True
    except Exception as exc:
        log.error(f"Could not type the DM: {exc}")
        return False


def find_send_button(device, *, timeout: float = 3.0, logger=None) -> Optional[Any]:
    """Locate the send button: xpath catalogue, then resource-ids, then content-descriptions."""
    log = logger or _default_logger

    for selector in DM_SELECTORS.send_button:
        try:
            found = device.xpath(selector)
            if found.exists:
                return found.get(timeout=timeout)
        except Exception:
            continue

    for resource_id in DM_SELECTORS.send_button_resource_ids:
        try:
            candidate = device(resourceId=resource_id)
            if candidate.exists:
                return candidate
        except Exception:
            continue

    for description in DM_SELECTORS.send_button_content_descriptions:
        try:
            candidate = device(description=description)
            if candidate.exists:
                return candidate
        except Exception:
            continue

    log.warning("DM send button not found with any known signature")
    return None


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
