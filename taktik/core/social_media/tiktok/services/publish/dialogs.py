"""Dialog helpers used by the TikTok publish workflow."""

from __future__ import annotations

import time
from typing import Callable

from taktik.core.shared.device.permissions import PermissionHandler
from taktik.core.social_media.tiktok.ui.selectors.shell.popups import POPUP_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
    PUBLISH_COMPOSER_SELECTORS,
    PUBLISH_EDITOR_SELECTORS,
    PublishComposerSelectors,
    PublishEditorSelectors,
)
from taktik.core.social_media.tiktok.ui.xpath import find_element, tap_element


LogFn = Callable[[str, str], None]


def handle_permission_dialog(
    device,
    device_id: str,
    log: LogFn | None = None,
) -> bool:
    """Grant Android media permissions while denying TikTok contacts prompts."""
    try:
        handler = PermissionHandler(device, device_id)
        if handler.deny_contacts_if_present(wait=0.8):
            if log:
                log("info", "Denied TikTok contacts permission dialog")
            return True

        dismissed = handler.grant(rounds=2, per_round_wait=1.5)
        if dismissed:
            if log:
                log("info", f"Granted {dismissed} permission dialog(s)")
            return True
    except Exception as exc:
        if log:
            log("warning", f"Permission handler failed: {exc}")
    return False


def dismiss_post_popups(
    device,
    selectors: PublishEditorSelectors = PUBLISH_EDITOR_SELECTORS,
    sleep: Callable[[float], None] = time.sleep,
    log: LogFn | None = None,
) -> bool:
    """Dismiss system or TikTok dialogs that may appear around publishing."""
    if tap_element(device, POPUP_SELECTORS.gdpr_got_it_button, timeout=1.5):
        if log:
            log("info", "[popup] dismissed TikTok GDPR data-transfer notice")
        sleep(0.5)
        return True

    element = find_element(device, selectors.popup_cancel_buttons, timeout=3.0)
    if not element:
        return False

    try:
        if log:
            log("info", "Dismissing post-publishing dialog...")
        element.click()
        sleep(0.5)
        return True
    except Exception as exc:
        if log:
            log("debug", f"[dismiss_popup] click failed: {exc}")
        return False


def handle_publish_confirmation_dialog(
    device,
    selectors: PublishComposerSelectors = PUBLISH_COMPOSER_SELECTORS,
    log: LogFn | None = None,
) -> bool:
    """Confirm TikTok's optional publish visibility dialog."""
    if not find_element(device, selectors.publish_confirm_dialog, timeout=1.5):
        return False

    if log:
        log("info", "[publishing] confirming TikTok visibility dialog...")
    return tap_element(device, selectors.publish_confirm_btn, timeout=2.0)
