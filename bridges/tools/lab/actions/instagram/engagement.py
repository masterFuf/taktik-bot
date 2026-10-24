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

from bridges.tools.lab.actions.instagram import action, detection_action
from bridges.tools.lab.action_test.params import lab_flag, lab_int


@action("engagement.like_current_post")
def like_current_post(a, p):
    """Like the CURRENTLY OPEN post via the production orchestration (double-tap vs
    button + already-liked guard) — distinct from the atomic ``post.like``. A post must
    be open. An already-liked post is no gesture and no like: it is said so, never « post liked »."""
    from taktik.core.social_media.instagram.services.like.orchestration import FramedLike

    outcome = a.like.like_current_post()
    if outcome is FramedLike.LIKED:
        return {"success": True, "message": "post liked", "details": {"outcome": outcome.value}}
    if outcome is FramedLike.ALREADY_LIKED:
        return {"success": True, "message": "already liked: no gesture, no like given",
                "details": {"outcome": outcome.value}}
    return {"success": False, "message": "like failed", "details": {"outcome": outcome.value}}


@action("engagement.read_feed_post_author")
def read_feed_post_author(a, p):
    """Read, without a gesture, the author the Feed files the framed post under
    (``FeedBusiness._get_current_post_author``): the first handle of the framed post's own
    header description (``framed_post_identity``), the post the Feed likes. None when no post is
    framed or the description names no handle: the Feed then leaves the post alone."""
    author = a.feed._get_current_post_author()
    identity = a.feed.scroll_actions.framed_post_identity()
    return {"success": bool(author),
            "message": f"@{author}" if author else "no author: no framed post, or no handle in its header",
            "details": {"author": author, "framed_identity": identity}}


@action("engagement.like_feed_post")
def like_feed_post(a, p):
    """Like the home-feed post on screen the way the Feed workflow does: read its author
    (``FeedBusiness._get_current_post_author``), then like it through the Feed's like
    (``FeedBusiness._like_current_post(record_as=author)``: the framed post's own media or heart,
    verified on that heart, ``LikeOrchestration.like_framed_post``), which files the like under
    that author. An unreadable author means no like, as in the workflow. Param: account (the like
    is recorded under it, as a run records it; without it the write is refused and logged, the
    gesture is the production one)."""
    author = a.feed._get_current_post_author()
    if not author:
        return {"success": False, "message": "post author unreadable: the feed does not engage this post"}
    ok = a.feed._like_current_post(record_as=author)
    return {"success": bool(ok), "message": f"@{author}: liked" if ok else f"@{author}: not liked / already liked",
            "details": {"author": author}}


@action("engagement.comment_feed_post")
def comment_feed_post(a, p):
    """Comment the home-feed post on screen the way the Feed workflow does: read its author
    (``FeedBusiness._get_current_post_author``), then comment through the Feed's own comment
    (``FeedBusiness._comment_feed_post``), filed under that author. Param: text (optional, the
    operator's custom comment). Without a text there is no comment, never a template: the Lab
    has no AI hook, so an empty text shows the Feed's rule. An unreadable author means no
    comment, as in the workflow."""
    author = a.feed._get_current_post_author()
    if not author:
        return {"success": False, "message": "post author unreadable: the feed does not engage this post"}
    text = (p.get("text") or "").strip()
    result = a.feed._comment_feed_post(author, {"custom_comments": [text] if text else []})
    if result.get("skipped"):
        return {"success": False, "message": f"@{author}: no comment ({result.get('skip_reason')})",
                "details": result}
    ok = bool(result.get("commented"))
    return {"success": ok, "message": f"@{author}: commented" if ok else f"@{author}: comment failed",
            "details": {**result, "author": author}}


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
    """Watch the stories of the profile ON SCREEN the way every profile visit of a workflow does
    (``InteractionEngineMixin._view_stories_on_current_profile``, which ``_do_watch_story`` calls):
    the ring, each slide watched with the check that it did not leave on its own, likes in
    proportion to the story when asked, the viewer closed. Be on the profile. Params: username
    (the visit's name, for the logs), max_stories (default 3), story_like (default no),
    max_story_likes (default 3)."""
    username = (p.get("username") or "").strip().lstrip("@")
    result = a.popup._view_stories_on_current_profile(
        username,
        do_story_like=lab_flag(p, "story_like", False),
        max_story_likes=lab_int(p, "max_story_likes", 3),
        max_stories=lab_int(p, "max_stories", 3),
    )
    if not result:
        return {"success": False,
                "message": "no story watched: no story ring on this profile, or the viewer did not open"}
    return {"success": True,
            "message": f"{result.get('stories_viewed', 0)} slide(s) watched, {result.get('stories_liked', 0)} liked",
            "details": result}


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
    """Unfollow ONE account from our following list, with every check of the engine (production
    `UnfollowBusiness.unfollow_listed_accounts`): its row is found in the list, its profile
    checked when the mode asks, the row button tapped, a private account confirmed, the row read
    again (counted only if it now offers to follow), a block detected, then written in the base.
    DESTRUCTIVE. Params: username (required), account (required: an unfollow the base does not
    hold leaves the account "followed" for the next decision), and the page fields
    (unfollow_mode, skip_verified...)."""
    from bridges.tools.lab.actions.instagram.unfollow import unfollow_and_report

    username = (p.get("username") or "").strip().lstrip("@")
    if not username:
        return {"success": False, "message": "username param is required"}
    return unfollow_and_report(a, username, p)


@action("engagement.unfollow_from_list")
def unfollow_from_list(a, p):
    """The whole unfollow step, as the page and the scheduler run it (production
    `UnfollowBusiness.run_unfollow_workflow`): syncs, decision on data, checks and unfollows on
    screen. DESTRUCTIVE: run on a test account. Params: account (required for the decision),
    max_unfollows (1 by default here), and the page fields."""
    from bridges.tools.lab.actions.instagram.unfollow import plain_stats, unfollow_config_from_params

    cfg = {"max_unfollows": 1, **unfollow_config_from_params(p)}
    stats = a.unfollow.run_unfollow_workflow(cfg)
    return {"success": bool(stats.get("success")),
            "message": f"{stats.get('unfollows_made', 0)} unfollowed of {stats.get('candidates', 0)} candidate(s)",
            "details": plain_stats(stats)}


@action("engagement.engage_likers")
def engage_likers(a, p):
    """Walk the likers of the OPEN post with the loop of the feed, hashtag and post URL workflows
    (``LikersWorkflowBase._interact_with_likers_list``): each row opened, the profile filtered,
    the planned interactions made and recorded, the list found again. The likers popup must be
    open. Params: account (required: the loop skips the profiles the base holds as processed for
    it, marks the ones it visits and records its likes and follows under it, as a run does;
    without it, nothing is touched), max_interactions (default 5), follow_percentage and
    like_percentage (0-100, as the workflow pages set them; absent, the feed's defaults)."""
    from taktik.core.social_media.instagram.actions.base.stats import create_workflow_stats

    if not a.feed._get_account_id():
        return {"success": False,
                "message": "account param is required: the likers loop records its likes and follows "
                           "under the account, as a run does (nothing touched)"}
    config = dict(a.feed.default_config)
    for key in ("follow_percentage", "like_percentage"):
        if p.get(key) not in (None, ""):
            config[key] = lab_int(p, key, 0)
    stats = create_workflow_stats("feed")
    a.feed._interact_with_likers_list(
        stats=stats,
        effective_config=config,
        max_interactions=lab_int(p, "max_interactions", 5),
        source_type="FEED",
        source_name="cartography-lab",
    )
    engaged = stats.get("users_interacted", 0)
    return {"success": engaged > 0,
            "message": f"{engaged} liker(s) engaged of {stats.get('users_found', 0)} seen",
            "details": stats}


@detection_action("engagement.has_likes")
def has_likes(a, p):
    """Detection: does the OPEN post show a like counter? The gate of the production opening of
    the likers popup (``PopupHandlingMixin._find_like_count_element``): no counter, no likers."""
    return a.popup._find_like_count_element() is not None
