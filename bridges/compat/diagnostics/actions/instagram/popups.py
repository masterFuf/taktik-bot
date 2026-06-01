"""Popup actions for Instagram compat diagnostics."""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("popups.is_comment_open")
def check_comment_popup(a, p):
    result = a.popup._is_comments_view_open()
    logger.info(f"Comment popup open: {result}")
    return result


@action("popups.close_comment")
def close_comment_popup(a, p):
    return a.comment._close_comment_popup()


@action("popups.is_likers_open")
def check_likers_popup(a, p):
    result = a.popup._is_likers_popup_open()
    logger.info(f"Likers popup open: {result}")
    return result


@action("popups.close_likers")
def close_likers_popup(a, p):
    a.popup._close_likers_popup()
    return not a.popup._is_likers_popup_open()


@action("popups.close_by_swipe")
def close_popup_swipe(a, p):
    return a.popup._close_popup_by_swipe_down()


@action("popups.close_follow_suggestions")
def close_follow_suggestions(a, p):
    a.popup._handle_follow_suggestions_popup()
    return True


@action("popups.press_back")
def press_back(a, p):
    a.device.press("back")
    time.sleep(0.8)
    return True

