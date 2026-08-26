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
    # Mirror production exactly, like post.open_likers below: the bot opens the thread via
    # the shared _open_comments_view flow (tap + empty-state guard + verifies the thread
    # actually opened), not the bare click_comment_button atomic which prod never calls.
    return a.popup._open_comments_view()


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


@action("post.read_commenters")
def read_commenters(a, p):
    """List the people visible in the open comments thread.

    Same reader the scraping loop and the post-URL interaction loop use, so what the Lab
    reports here is literally what a run would walk.
    """
    from taktik.core.social_media.instagram.workflows.common.detection import (
        read_visible_commenters,
    )

    rows = read_visible_commenters(a.device, logger)
    usernames = [row["username"] for row in rows]
    return {
        "success": bool(usernames),
        "message": f"{len(usernames)} commenter(s): {', '.join(usernames[:10]) or 'none'}",
        "details": {"count": len(usernames), "usernames": usernames},
    }


@action("post.is_liked")
def is_liked(a, p):
    result = a.click.is_post_already_liked()
    logger.info(f"Post liked: {result}")
    return result


@action("post.read_stats")
def read_stats(a, p):
    """Read the current post counters through the production UI extractors."""
    is_reel = bool(p.get("is_reel")) if isinstance(p, dict) else False
    likes = a.like.ui_extractors.extract_likes_count_from_ui(is_reel=is_reel)
    comments = a.like.ui_extractors.extract_comments_count_from_ui(is_reel=is_reel)
    return {
        "success": True,
        "message": f"likes={likes}, comments={comments}",
        "details": {"likes": likes, "comments": comments, "is_reel": is_reel},
    }


@action("post.read_card")
def read_card(a, p):
    """Read the OPEN post's catalogue card: author, counters, caption, date and share URL.

    The exact composition the profile-posts scan writes to `social_posts`
    (`read_open_post_card`), on the production extractors, framed-post reader and
    share-sheet URL read. `with_url=no` skips the share sheet — the cheap read the scan
    uses to recognise a post it already holds. `username` is the grid's owner, used when
    the author cannot be read on screen.
    """
    from taktik.core.social_media.instagram.workflows.common.post_card import read_open_post_card

    with_url = str(p.get("with_url", "yes")).strip().lower() not in ("no", "false", "0", "")
    card = read_open_post_card(
        a.device,
        logger,
        ui_extractors=a.like.ui_extractors,
        scroll_actions=a.scroll,
        with_url=with_url,
        author_hint=(p.get("username") or "").strip() or None,
    )
    complete = bool(card.author) and (card.post_url is not None or not with_url)
    return {
        "success": complete,
        "message": (
            f"@{card.author or '?'} | likes={card.likes_count} comments={card.comments_count}"
            f"{' (atomic)' if card.counters_atomic else ''} | {'reel' if card.is_reel else 'post'}"
            f" | {card.post_url or ('url skipped' if not with_url else 'no url')}"
        ),
        "details": card.as_dict(),
    }


@action("post.navigate_next")
def navigate_next(a, p):
    """Advance to the next post in the in-viewer sequence with the humanised swipe
    (sampled geometry, randomised distance) instead of the old fixed 78%->21%
    gesture. Must be run while a post is open."""
    ok = a.like._navigate_to_next_post_in_sequence()
    scroll = a.like.scroll_actions
    decision = dict(getattr(scroll, "_last_advance_behavior", {}))
    snapshot = getattr(scroll, "_behavior_snapshot", lambda: {})()
    return {
        "success": bool(ok),
        "message": (
            f"navigated to next post={ok} mode={decision.get('mode')} "
            f"style={decision.get('style')} energy={decision.get('energy')}"
        ),
        "details": {"advance_decision": decision, "behavior_state": snapshot},
    }


@action("post.return_to_profile")
def return_to_profile(a, p):
    """Return from an open post back to the profile grid (back button, else a
    humanised downward swipe)."""
    ok = a.like._return_to_profile_from_post()
    decision = dict(getattr(a.like.scroll_actions, "_last_behavior_gesture", {}))
    return {
        "success": bool(ok),
        "message": f"returned to profile={ok} style={decision.get('style')}",
        "details": {
            "gesture_decision": decision,
            "behavior_state": a.like._behavior_state_snapshot(),
        },
    }


@action("post.return_to_grid_and_reopen")
def return_to_grid_and_reopen(a, p):
    """Exercise the production alternate sequence: leave the viewer and open another grid post."""
    posts_count = max(0, int(p.get("posts_count", 0)))
    username = str(p.get("username") or "") or None
    ok = a.like._return_to_grid_and_open_another_post(posts_count, username=username)
    decision = dict(getattr(a.like.scroll_actions, "_last_behavior_gesture", {}))
    return {
        "success": bool(ok),
        "message": f"retour grille + reouverture={ok} style={decision.get('style')}",
        "details": {
            "gesture_decision": decision,
            "behavior_state": a.like._behavior_state_snapshot(),
        },
    }


@action("post.read_context")
def read_post_context(a, p):
    """Author, publish date, window and caption of the FRAMED post.

    The exact context the AI smart comment grounds on — same production path
    (PostReadingMixin.framed_post_context + clean_post_caption), so what the Lab
    reports here is literally what the comment model would be given.
    """
    from taktik.core.social_media.instagram.workflows.core.caption_hygiene import (
        clean_post_caption,
    )

    ctx = a.scroll.framed_post_context()
    if not ctx:
        return {"success": False,
                "message": "aucun post cadre (pas de header visible dans le dump)"}
    cleaned = clean_post_caption(ctx.get("caption_text"), author_hint=ctx.get("author"))
    flags = []
    if cleaned.truncated:
        flags.append("tronquee")
    if cleaned.mangled:
        flags.append("emoji manges par le dump")
    if not cleaned.has_substance:
        flags.append("sans matiere")
    caption_note = f"caption {len(cleaned.text)} car." + (f" ({', '.join(flags)})" if flags else "")
    return {
        "success": True,
        "message": f"@{ctx.get('author') or '?'} | {ctx.get('header_desc') or 'header sans date'} | {caption_note}",
        "details": {
            "author": ctx.get("author"),
            "header_desc": ctx.get("header_desc"),
            "caption_clean": cleaned.text,
            "caption_raw": ctx.get("caption_text"),
            "caption_truncated": cleaned.truncated,
            "caption_mangled": cleaned.mangled,
            "caption_has_substance": cleaned.has_substance,
            "header_bounds": ctx.get("header_bounds"),
            "buttons_bounds": ctx.get("buttons_bounds"),
            "window_bottom": ctx.get("window_bottom"),
        },
    }
