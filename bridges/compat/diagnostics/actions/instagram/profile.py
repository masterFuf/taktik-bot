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


@action("profile.get_follow_state")
def get_follow_state(a, p):
    """Read the relationship shown by the profile-header action button.

    follow = no relationship | follow_back = THEY follow us | following = WE follow them
    | requested = pending request | message | unknown.
    Same production function the workflows use to decide whether to skip an existing relationship.
    """
    state = a.click.get_follow_button_state()
    logger.info(f"Follow button state: {state}")
    return {
        "success": state != "unknown",
        "message": state,
        "details": {"follow_button_state": state},
    }


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
      - posts_to_inspect: number of sequential posts the run needs to inspect.
    """
    try:
        posts_count = int(p.get("posts_count") or 0)
    except (TypeError, ValueError):
        posts_count = 0
    try:
        posts_to_inspect = int(p.get("posts_to_inspect") or 0)
    except (TypeError, ValueError):
        posts_to_inspect = 0
    ok = a.like._open_entry_post_of_profile(
        posts_count,
        posts_to_inspect=posts_to_inspect,
    )
    return {
        "success": bool(ok),
        "message": (
            f"entry post opened={ok} (posts_count={posts_count}, "
            f"posts_to_inspect={posts_to_inspect})"
        ),
    }


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
    """Exercise the production grid-scroll action with the shared session state."""
    ok = a.scroll.scroll_post_grid_down()
    decision = dict(getattr(a.scroll, "_last_behavior_gesture", {}))
    snapshot = getattr(a.scroll, "_behavior_snapshot", lambda: {})()
    return {
        "success": bool(ok),
        "message": (
            f"grid scroll={ok} style={decision.get('style')} "
            f"energy={decision.get('energy')}"
        ),
        "details": {
            "gesture_decision": decision,
            "behavior_state": snapshot,
        },
    }


@action("profile.ensure_header_actions")
def ensure_header_actions(a, p):
    """Run the production bounded header recovery used before deferred story/follow actions."""
    def enabled(value, default):
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() not in {"", "0", "false", "no", "off"}
        return bool(value)

    needs_story = enabled(p.get("needs_story"), False)
    needs_follow = enabled(p.get("needs_follow"), True)
    try:
        max_attempts = int(p.get("max_attempts", 3))
    except (TypeError, ValueError):
        max_attempts = 3
    reached = a.popup._ensure_profile_header_actions_visible(
        needs_story=needs_story,
        needs_follow=needs_follow,
        max_attempts=max_attempts,
    )
    return {
        "success": bool(reached),
        "message": (
            f"profile header actions visible={reached} "
            f"(story={needs_story}, follow={needs_follow})"
        ),
        "details": {
            "needs_story": needs_story,
            "needs_follow": needs_follow,
            "max_attempts": max_attempts,
        },
    }


# =============================================================================
# Bio / enrichment reads (ProfileExtractionMixin via a.detection). Device must be
# on a PROFILE screen. No hardcoded selectors (PROFILE_SELECTORS catalog).
# =============================================================================

@action("profile.get_biography")
def get_biography(a, p):
    """Read the bio text of the current profile (single value)."""
    bio = a.detection.get_biography_from_profile()
    return {"success": bool(bio), "message": (bio or "")[:200], "details": {"biography": bio}}


@action("profile.get_text_batch")
def get_text_batch(a, p):
    """Read username + full_name + biography in a single XML dump."""
    data = a.detection.get_profile_text_batch() or {}
    return {"success": bool(data.get("username") or data.get("biography")),
            "message": f"@{data.get('username')} — bio={(data.get('biography') or '')[:60]}",
            "details": data}


@action("profile.get_enriched")
def get_enriched(a, p):
    """Read the ENRICHED profile: username/full_name/bio/category/website/linked +
    the bio_truncated flag (whether a '… more'/'… plus' expander is present)."""
    data = a.detection.get_enriched_profile_data() or {}
    public_data = {key: value for key, value in data.items() if not key.startswith("_")}
    return {"success": bool(data.get("username") or data.get("biography")),
            "message": (f"@{data.get('username')} | bio_truncated={data.get('bio_truncated')} | "
                        f"bio={(data.get('biography') or '')[:50]}"),
            "details": public_data}


@action("profile.expand_bio_more")
def expand_bio_more(a, p):
    """Expand a TRUNCATED bio through the production OCR path. Screenshot and
    Tesseract have individual budgets inside a coherent total wall-clock boundary;
    the tap stays on the caller thread."""
    ok = a.detection.click_bio_more_button()
    return {"success": bool(ok),
            "message": "bio expanded via OCR" if ok else "bio not truncated / expander not located"}
