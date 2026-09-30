"""Popup actions for TikTok compat diagnostics.

A closer that finds nothing to close says so (`absent_on_screen`): not applicable when the screen,
read and TikTok's, holds none of what it closes; a failure when it could not be read or when the
production detector still sees the thing.
"""

from loguru import logger

from bridges.tools.lab.actions.tiktok import action, detection_action
from bridges.tools.lab.action_test.not_applicable import absent_on_screen


def _closed_or_absent(action_id, a, closed, still_there, what):
    """The production closer's answer, or why there was nothing to close."""
    if closed:
        return True
    return absent_on_screen(action_id, device=a.device, platform="tiktok", still_there=still_there, what=what)


@detection_action("tt.popups.has_popup")
def has_popup(a, p):
    return a.popup_detector.has_popup()


@action("tt.popups.close_popup")
def close_popup(a, p):
    return _closed_or_absent("tt.popups.close_popup", a, a.popup.close_popup(),
                             a.popup_detector.has_popup, "popup or banner")


@action("tt.popups.close_collections")
def close_collections(a, p):
    return _closed_or_absent("tt.popups.close_collections", a, a.popup.close_collections_popup(),
                             a.popup_detector.has_collections_popup, "shared collections popup")


@action("tt.popups.close_follow_friends")
def close_follow_friends(a, p):
    return _closed_or_absent("tt.popups.close_follow_friends", a, a.popup.close_follow_friends_popup(),
                             a.popup_detector.has_follow_friends_popup, "follow your friends popup")


@action("tt.popups.dismiss_notification")
def dismiss_notification(a, p):
    from taktik.core.social_media.tiktok.actions.base.utils import first_matching

    return _closed_or_absent("tt.popups.dismiss_notification", a, a.popup.dismiss_notification_banner(),
                             lambda: bool(first_matching(a.device, a.popup.popup_selectors.notification_banner)),
                             "in-app message banner")


@action("tt.popups.close_comments")
def close_comments(a, p):
    return a.popup.close_comments_section()


@action("tt.popups.close_system")
def close_system_popup(a, p):
    # The system dialogs are Android's, not TikTok's: absent means TikTok's own screen is in front.
    return _closed_or_absent("tt.popups.close_system", a, a.popup.close_system_popup(), None, "system dialog")


@action("tt.popups.dismiss_update_prompt")
def dismiss_update_prompt(a, p):
    """The "update the app" prompt draws no readable node: found by its shape, read by OCR."""
    from taktik.core.shared.device.ui_dump import parse_ui_dump
    from taktik.core.social_media.tiktok.workflows.common.popup_handler import (
        unlabelled_overlay_region,
    )

    tree = parse_ui_dump(a.device.dump_hierarchy())
    region = unlabelled_overlay_region(tree) if tree is not None else None
    if region is None:
        return absent_on_screen("tt.popups.dismiss_update_prompt", device=a.device, platform="tiktok",
                                still_there=None, what="unlabelled dialog")
    return a.popup.dismiss_update_prompt(region)


@detection_action("tt.popups.has_collections")
def has_collections(a, p):
    return a.popup_detector.has_collections_popup()


@detection_action("tt.popups.has_comments")
def has_comments(a, p):
    return a.popup_detector.has_comments_section_open()


@action("tt.popups.click_follow_back")
def click_follow_back(a, p):
    """Tap the real Follow back button on the suggestion/interstitial popup."""
    ok = a.popup.click_follow_back()
    logger.info(f"Follow back clicked: {ok}")
    return {"success": bool(ok), "message": f"follow back clicked={ok}"}

