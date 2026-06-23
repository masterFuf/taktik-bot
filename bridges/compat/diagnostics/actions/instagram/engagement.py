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
