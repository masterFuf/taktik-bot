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
    detected = a.popup._handle_follow_suggestions_popup()
    return {
        "success": True,
        "message": (
            "inline follow suggestions detected and left in place"
            if detected else
            "no inline follow suggestions detected"
        ),
        "details": {"detected": bool(detected), "scrolled": False},
    }


@action("popups.press_back")
def press_back(a, p):
    a.device.press("back")
    time.sleep(0.8)
    return True


# === Bottom sheets (generic close cascade) ===================================

@action("popups.is_share_sheet_open")
def is_share_sheet_open(a, p):
    """Detection: is the Direct / share sheet (post share button) currently up?"""
    from taktik.core.social_media.instagram.actions.atomic.interaction.bottom_sheet import (
        is_share_sheet_open as _is_open,
    )
    found = _is_open(a.device)
    return {"success": True, "found": bool(found), "message": f"share_sheet_open={bool(found)}"}


@action("popups.find_sheet_handle")
def find_sheet_handle(a, p):
    """Diagnostic: locate the grey grab bar of the open bottom sheet, and say HOW it was found.

    `source=id` means Instagram named it on this sheet; `source=geometry` means it is anonymous
    here (the Direct share sheet is) and we matched it by shape. Reading which one fired is the
    point of this action — an id-only lookup silently finds nothing on the share sheet."""
    from taktik.core.social_media.instagram.actions.atomic.interaction.bottom_sheet import find_drag_handle
    handle = find_drag_handle(a.device, logger)
    if not handle:
        return {"success": False, "found": False, "message": "no grab bar found on screen"}
    return {
        "success": True,
        "found": True,
        "message": f"grab bar at ({handle['x']},{handle['y']}) via {handle['source']}",
        "details": handle,
    }


@action("popups.close_share_sheet")
def close_share_sheet(a, p):
    """Close the Direct / share sheet through the shared verified cascade.

    Same function production will call: defocus, back x3, handle drag (skipped when the sheet is
    expanded to the top), then a drag from inside the sheet. Each step re-checks that the sheet
    is really gone, so a false success cannot be reported."""
    from taktik.core.social_media.instagram.actions.atomic.interaction.bottom_sheet import (
        dismiss_share_sheet,
        is_share_sheet_open as _is_open,
    )
    was_open = _is_open(a.device)
    if not was_open:
        return {"success": False, "message": "no share sheet open — open one first", "details": {"was_open": False}}
    closed = dismiss_share_sheet(a.device, logger)
    return {
        "success": bool(closed),
        "message": "share sheet closed" if closed else "share sheet STILL OPEN after every strategy",
        "details": {"was_open": True, "closed": bool(closed)},
    }
