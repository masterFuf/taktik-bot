"""Popup actions for TikTok compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action


@action("tt.popups.has_popup")
def has_popup(a, p):
    result = a.popup_detector.has_popup()
    logger.info(f"Has popup: {result}")
    return result


@action("tt.popups.close_popup")
def close_popup(a, p):
    return a.popup.close_popup()


@action("tt.popups.close_collections")
def close_collections(a, p):
    return a.popup.close_collections_popup()


@action("tt.popups.close_follow_friends")
def close_follow_friends(a, p):
    return a.popup.close_follow_friends_popup()


@action("tt.popups.dismiss_notification")
def dismiss_notification(a, p):
    return a.popup.dismiss_notification_banner()


@action("tt.popups.close_comments")
def close_comments(a, p):
    return a.popup.close_comments_section()


@action("tt.popups.close_system")
def close_system_popup(a, p):
    return a.popup.close_system_popup()


@action("tt.popups.has_collections")
def has_collections(a, p):
    result = a.popup_detector.has_collections_popup()
    logger.info(f"Has collections popup: {result}")
    return result


@action("tt.popups.has_comments")
def has_comments(a, p):
    result = a.popup_detector.has_comments_section_open()
    logger.info(f"Has comments open: {result}")
    return result

