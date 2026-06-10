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


@action("post.navigate_next")
def navigate_next(a, p):
    """Advance to the next post in the in-viewer sequence with the humanised swipe
    (sampled geometry, randomised distance) instead of the old fixed 78%->21%
    gesture. Must be run while a post is open."""
    ok = a.like._navigate_to_next_post_in_sequence()
    return {"success": bool(ok), "message": f"navigated to next post={ok}"}


@action("post.return_to_profile")
def return_to_profile(a, p):
    """Return from an open post back to the profile grid (back button, else a
    humanised downward swipe)."""
    a.like._return_to_profile_from_post()
    return {"success": True, "message": "returned to profile"}

