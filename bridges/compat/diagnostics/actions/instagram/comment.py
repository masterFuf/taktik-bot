"""Comment actions for Instagram compat diagnostics."""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("comment.open_and_type")
def comment_open_and_type(a, p):
    text = p.get("text", "Test comment \U0001f916")
    if not a.click.click_comment_button():
        logger.error("Could not open comment box")
        return False
    time.sleep(1.5)
    if not a.comment._type_comment(text):
        logger.error("Could not type comment (field not found)")
        return False
    logger.info(f"Typed comment: '{text}'")
    return True


@action("comment.post_comment")
def post_comment(a, p):
    return a.comment._post_comment()


@action("comment.close_popup")
def close_comment(a, p):
    return a.comment._close_comment_popup()
