"""Comment actions for Instagram compat diagnostics."""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("comment.open_and_type")
def comment_open_and_type(a, p):
    text = p.get("text", "Test comment \U0001f916")
    # Mirror the production path: if the comment composer is already open (re-running the
    # test, or we navigated straight into the thread) don't click the comment button — it
    # isn't on that screen — just type. Otherwise open the box first (rich post-detail
    # selectors via the business, not the 2-selector shell variant).
    if a.comment._is_comment_composer_open():
        logger.info("Comment composer already open — typing directly")
    elif not a.comment._click_comment_button():
        logger.error("Could not open comment box")
        return False
    else:
        time.sleep(1.5)
    if not a.comment._type_comment(text):
        logger.error("Could not type comment (field not found)")
        return False
    logger.info(f"Typed comment ({len(text)} chars)")
    return True


@action("comment.post_comment")
def post_comment(a, p):
    return a.comment._post_comment()


@action("comment.close_popup")
def close_comment(a, p):
    return a.comment._close_comment_popup()


@action("comment.like_in_thread")
def like_comment_in_thread(a, p):
    """Like a given commenter's comment in the open thread — the production function.

    Pass ``username``; without it the action reports which commenters are visible so the
    operator can pick one, rather than liking an arbitrary row.
    """
    username = (p.get("username") or "").strip() if isinstance(p, dict) else ""
    if not username:
        from taktik.core.social_media.instagram.workflows.common.detection import (
            read_visible_commenters,
        )

        visible = [row["username"] for row in read_visible_commenters(a.device, logger)]
        return {
            "success": False,
            "message": f"username required — visible: {', '.join(visible[:10]) or 'none'}",
            "details": {"visible": visible},
        }

    result = a.comment.like_comment_in_thread(username)
    return {
        "success": bool(result.get("success")),
        "message": result.get("message", ""),
        "details": result,
    }
