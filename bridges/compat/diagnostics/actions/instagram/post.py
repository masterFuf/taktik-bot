"""Post actions for Instagram compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("post.like")
def like_post(a, p):
    return a.click.like_post()


@action("post.unlike")
def unlike_post(a, p):
    return a.click.unlike_post()


@action("post.open_comments")
def open_comments(a, p):
    return a.click.click_comment_button()


@action("post.open_share")
def open_share(a, p):
    return a.click.click_share_button()


@action("post.save_post")
def save_post(a, p):
    return a.click.click_save_button()


@action("post.open_likers")
def open_likers(a, p):
    # Mirror production exactly: the bot opens the likers list via the shared
    # _open_likers_popup flow (reel-aware finder + verifies the popup actually
    # opened), not the bare click_likes_count atomic which prod never calls.
    is_reel = bool(p.get("is_reel")) if isinstance(p, dict) else False
    return a.popup._open_likers_popup(is_reel=is_reel)


@action("post.is_liked")
def is_liked(a, p):
    result = a.click.is_post_already_liked()
    logger.info(f"Post liked: {result}")
    return result

