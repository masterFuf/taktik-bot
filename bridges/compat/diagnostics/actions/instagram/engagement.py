"""Engagement actions for Instagram compat diagnostics (Cartography Lab).

These expose the REAL production engagement orchestrations (not the low-level atomic
taps) so each can be unit-tested in isolation:
- ``LikeOrchestration`` (``a.like``): like-the-open-post + like-a-profile loop, with the
  production double-tap-vs-button choice and the already-liked guard.
- ``CommentAction`` (``a.comment``): the orchestrated comment (open + type + post + close),
  template-driven when no text is given.

Both are already instantiated in the Lab bundle from the warm device, so the Lab runs the
exact path the workflows run. No hardcoded selectors here.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("engagement.like_current_post")
def like_current_post(a, p):
    """Like the CURRENTLY OPEN post via the production orchestration (double-tap vs
    button + already-liked guard) — distinct from the atomic ``post.like``. A post must
    be open."""
    ok = a.like.like_current_post()
    return {"success": bool(ok), "message": "post liked" if ok else "like failed / already liked"}


@action("engagement.comment_on_post")
def comment_on_post(a, p):
    """Comment on the CURRENTLY OPEN post via the orchestrated flow (open composer + type
    + post + close). Param: text (optional → a generic template comment is used). A post
    must be open."""
    text = (p.get("text") or "").strip() or None
    result = a.comment.comment_on_post(comment_text=text)
    if isinstance(result, dict):
        return {"success": bool(result.get("success")),
                "message": result.get("message") or ("comment posted" if result.get("success") else "comment failed"),
                "details": result}
    return {"success": bool(result), "message": "comment posted" if result else "comment failed"}


@action("engagement.like_profile_posts")
def like_profile_posts(a, p):
    """Engagement loop: open ``username``'s profile and like up to ``max_likes`` of their
    posts (production sequence: humanised entry + read + optional comment). Params:
    username (required), max_likes (default 2)."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    try:
        max_likes = int(p.get("max_likes") or 2)
    except (TypeError, ValueError):
        max_likes = 2
    result = a.like.like_profile_posts(username, max_likes=max_likes, navigate_to_profile=True, should_like=True)
    logger.info(f"engagement.like_profile_posts @{username}: {result}")
    if isinstance(result, dict):
        ok = bool(result.get("success", result.get("likes_count", 0)))
        return {"success": ok, "message": f"@{username}: {result.get('likes_count', '?')} like(s)", "details": result}
    return {"success": bool(result), "message": f"@{username} liked={result}"}


def _dict_result(result, ok_msg, fail_msg):
    if isinstance(result, dict):
        ok = bool(result.get("success", True))
        return {"success": ok, "message": result.get("message") or (ok_msg if ok else fail_msg), "details": result}
    return {"success": bool(result), "message": ok_msg if result else fail_msg}


@action("engagement.view_profile_stories")
def view_profile_stories(a, p):
    """Watch ``username``'s stories via the production StoryBusiness flow (open ring +
    watch + like/react/skip-ad per config). Params: username (required),
    max_stories (default 3)."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    try:
        max_stories = int(p.get("max_stories") or 3)
    except (TypeError, ValueError):
        max_stories = 3
    return _dict_result(a.story.view_profile_stories(username, max_stories=max_stories),
                        f"@{username}: stories viewed", f"@{username}: no stories / failed")


@action("engagement.view_feed_stories")
def view_feed_stories(a, p):
    """Watch the feed-tray stories via the production StoryBusiness flow (scroll tray +
    watch + like/react + skip ads). No params (uses default config)."""
    return _dict_result(a.story.view_feed_stories(), "feed stories viewed", "no feed stories / failed")


@action("engagement.interact_with_feed")
def interact_with_feed(a, p):
    """Run the production feed engagement loop (FeedBusiness.interact_with_feed): browse the
    home feed and like/comment real posts (skips ads). Uses the default config — keep the
    run short when testing."""
    return _dict_result(a.feed.interact_with_feed(), "feed interaction done", "feed interaction failed")


@action("engagement.unfollow_account")
def unfollow_account(a, p):
    """Unfollow ONE account via the production orchestration (tap Following + confirm modal
    + verify) — distinct from the atomic ``profile.click_unfollow``. Must be on the target's
    profile. Param: username (required, used for logging/verification)."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    ok = a.unfollow._unfollow_account(username)
    return {"success": bool(ok), "message": f"@{username} unfollowed={ok}"}


@action("engagement.unfollow_from_list")
def unfollow_from_list(a, p):
    """Batch unfollow from the Following list via the production strategy
    (UnfollowBusiness.run_simple_unfollow_from_list). DESTRUCTIVE — unfollows accounts. Uses
    the default config; run on a test account."""
    return _dict_result(a.unfollow.run_simple_unfollow_from_list(), "unfollow-from-list done", "unfollow-from-list failed")
