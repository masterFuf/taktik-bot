"""Profile actions for Instagram compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("profile.click_follow")
def click_follow(a, p):
    return a.click.click_follow_button()


@action("profile.click_unfollow")
def click_unfollow(a, p):
    return a.click.click_unfollow_button()


@action("profile.is_follow_available")
def is_follow_available(a, p):
    result = a.click.is_follow_button_available()
    logger.info(f"Follow button available: {result}")
    return result


@action("profile.is_unfollow_available")
def is_unfollow_available(a, p):
    result = a.click.is_unfollow_button_available()
    logger.info(f"Unfollow button available: {result}")
    return result


@action("profile.click_followers_count")
def click_followers(a, p):
    return a.click.click_followers_count()


@action("profile.click_following_count")
def click_following(a, p):
    return a.click.click_following_count()


@action("profile.click_message_button")
def click_message(a, p):
    return a.click.click_message_button()


@action("profile.open_entry_post")
def open_entry_post(a, p):
    """Humanised profile entry: open a post WITHOUT always taking the top-left one.

    On a large-enough profile it may scroll the grid down a little first (human
    flick), then opens a varied visible thumbnail (top-weighted but spread) with a
    human tap. Re-run a few times: the opened post should differ. Pass the profile's
    publication count to exercise the adaptive pre-scroll.

    params (optional):
      - posts_count: the profile's number of publications (drives pre-scroll).
    """
    try:
        posts_count = int(p.get("posts_count") or 0)
    except (TypeError, ValueError):
        posts_count = 0
    ok = a.like._open_entry_post_of_profile(posts_count)
    return {"success": bool(ok), "message": f"entry post opened={ok} (posts_count={posts_count})"}


@action("profile.open_post_index")
def open_post_index(a, p):
    """Open a SPECIFIC post by its grid position (1-based) — deterministic, for
    targeting tests (NOT the humanised entry). e.g. index=9 → ligne 3, colonne 3.
    Scrolls the grid to reveal the cell if needed.

    params:
      - index: 1-based post position to open (default 1).
    """
    try:
        index = int(p.get("index") or 1)
    except (TypeError, ValueError):
        index = 1
    ok = a.like._open_post_at_position(index)
    return {"success": bool(ok), "message": f"post #{index} opened={ok}"}


@action("profile.open_first_post")
def open_first_post(a, p):
    """Legacy entry (always opens the first/top-left post) — kept for A/B comparison
    against `profile.open_entry_post`."""
    ok = a.like._open_first_post_of_profile()
    return {"success": bool(ok), "message": f"first post opened={ok}"}


@action("profile.scroll_grid")
def scroll_grid(a, p):
    """Scroll the profile post grid down with a humanised flick (sampled geometry,
    real fling) — the primitive used by the adaptive pre-scroll."""
    ok = a.scroll._strong_flick("up")
    return {"success": bool(ok), "message": f"grid flick done={ok}"}

