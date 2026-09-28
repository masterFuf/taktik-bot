"""Profile actions for Instagram compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action, detection_action
from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
from taktik.core.shared.behavior.interaction_plan import build_interaction_plan
from taktik.core.social_media.instagram.actions.atomic.navigation.profile_grid import (
    show_profile_posts_grid,
)


@action("profile.click_follow")
def click_follow(a, p):
    """Follow the open profile the way every workflow follows a profile, and write it down.

    The engine is the Lab's `a.popup`, bound to ``account`` by the runner. Its handle and the
    relationship its header button shows are read by the production readers (the ones that fill a
    visited profile's data); the follow is the interaction engine's `_do_follow`, under a plan
    whose only intent is the follow: a profile we already follow or asked is left alone, the
    follow tapped and checked, then written under the account (the FOLLOW interaction, and our
    following row marked as the bot's, what the unfollow of "the bot's follows only" reads).
    Then the one look for "Try again later" that follows a follow in a run.

    Params: account (required: a follow the base does not hold is one that unfollow never
    undoes). Be on the profile, its header visible.
    """
    engine = a.popup
    account_id = engine._get_account_id()
    if not account_id:
        return {"success": False, "message": "account param required: the follow is written under it"}
    username = engine.detection_actions.get_username_from_profile()
    if not username:
        return {"success": False, "message": "profile handle unreadable: no follow, it could not be written"}

    state = engine.click_actions.get_follow_button_state()
    result = {}
    tapped = engine._do_follow(username, build_interaction_plan({}, ["follow"]),
                               {"follow_button_state": state}, result)
    blocked = bool(tapped) and engine._stop_if_action_blocked(username, "follow")
    followed = bool(result.get("follows"))
    recorded = {
        "follow_interaction": InstagramFollowGraphService.has_bot_follow_record(username, account_id),
        "following_row": username.lower() in InstagramFollowGraphService.get_active_following_usernames(account_id),
    }
    if blocked:
        message = f"@{username}: Instagram refuses the follow (Try again later)"
    elif followed:
        message = f"@{username}: followed" + ("" if all(recorded.values()) else ", NOT fully written in the base")
    else:
        message = f"@{username}: not followed (button: {state})"
    return {
        "success": followed and not blocked and all(recorded.values()),
        "message": message,
        "details": {"username": username, "state_before": state, "tapped": bool(tapped),
                    "followed": followed, "blocked": blocked, "recorded": recorded},
    }


@action("profile.click_unfollow")
def click_unfollow(a, p):
    return a.click.click_unfollow_button()


@detection_action("profile.is_follow_available")
def is_follow_available(a, p):
    return a.click.is_follow_button_available()


@detection_action("profile.is_unfollow_available")
def is_unfollow_available(a, p):
    return a.click.is_unfollow_button_available()


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


@action("profile.show_posts_grid")
def show_posts_grid(a, p):
    """Show the posts grid of the profile on screen: when it shows its Reels, Reposts or Tagged
    sub-tab, one tap on the grid tab, then the wait for the grid (production
    `show_profile_posts_grid`, which every reader of a profile's grid calls before it reads). No
    tap when the grid is already shown or when no profile is on screen."""
    grid = show_profile_posts_grid(a.device)
    if not grid.has_sub_tabs:
        message = "no profile sub-tab row on screen: nothing tapped"
    elif grid.tapped:
        message = f"profile was on '{grid.found_on}': grid tab tapped, grid shown={grid.shown}"
    else:
        message = f"grid already shown ('{grid.found_on}'): nothing tapped"
    return {
        "success": grid.shown,
        "message": message,
        "details": {"has_sub_tabs": grid.has_sub_tabs, "found_on": grid.found_on,
                    "tapped": grid.tapped, "shown": grid.shown},
    }


@action("profile.count_visible_posts")
def count_visible_posts(a, p):
    """Count the post thumbnails on screen (production `count_visible_posts`, read by the content
    extraction of a hashtag): the posts grid shown first on a profile, then counted on one photo.
    Where no thumbnail is shown it counts the header's images (avatar...): the profile visit takes
    its visible posts from the header's posts count instead (`profile.get_posts_count`)."""
    count = a.detection.count_visible_posts()
    return {"success": True, "message": f"{count} visible post(s) in the grid",
            "details": {"visible_posts": count}}


@action("profile.get_posts_count")
def get_posts_count(a, p):
    """Read the posts count of the profile's header, as the profile visit does (production
    `_get_posts_count_robust`, called by `get_complete_profile_info`): the number the filters take
    as the profile's visible posts. Unknown (None, not 0) when the header cannot be read. Be on a
    profile, header visible."""
    count = a.like.profile_business._get_posts_count_robust()
    if count is None:
        return {"success": False, "message": "posts count not read: unknown",
                "details": {"posts_count": None}}
    return {"success": True, "message": f"{count} post(s) in the header",
            "details": {"posts_count": count}}


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


@action("profile.get_account_flags")
def get_account_flags(a, p):
    """Read the three account flags the profile filter acts on: private, certified, professional.

    Same production read as the automation (`get_profile_flags_batch`, one XML dump, called by
    `get_complete_profile_info` before the filter). Certified = the owner's badge, never a badge
    in the similar-accounts carousel; professional = the category line under the name, the
    Contact button of the header row, or our own professional dashboard. Be on a PROFILE screen
    with the header visible."""
    flags = a.detection.get_profile_flags_batch() or {}
    shown = {key: bool(flags.get(key)) for key in ("is_private", "is_verified", "is_business")}
    return {"success": True,
            "message": (f"private={shown['is_private']} | verified={shown['is_verified']} | "
                        f"business={shown['is_business']}"),
            "details": shown}


@action("profile.expand_bio_more")
def expand_bio_more(a, p):
    """Expand a TRUNCATED bio through the production OCR path. Screenshot and
    Tesseract have individual budgets inside a coherent total wall-clock boundary;
    the tap stays on the caller thread."""
    ok = a.detection.click_bio_more_button()
    return {"success": bool(ok),
            "message": "bio expanded via OCR" if ok else "bio not truncated / expander not located"}


def _avatar_result(data_url):
    """What the Lab shows of an avatar crop: whether it was made and its size, never the image."""
    size_kb = len(data_url) * 3 // 4 // 1024 if data_url else 0
    return {"success": bool(data_url),
            "message": f"avatar cropped ({size_kb} KB)" if data_url else "avatar not found on screen",
            "details": {"extracted": bool(data_url), "size_kb": size_kb}}


@action("profile.extract_avatar")
def extract_avatar(a, p):
    """Crop the visited profile's avatar: its bounds read on one screen photo, the picture cut
    from one screenshot (production `extract_profile_image`, the picture stored with a profile).
    Be on a profile, header visible."""
    return _avatar_result(a.detection.extract_profile_image())


@action("profile.extract_own_avatar")
def extract_own_avatar(a, p):
    """Crop OUR avatar from the bottom bar's profile tab (production
    `extract_own_avatar_from_tab`: no story ring, no add-to-story badge). Any screen with the
    bottom bar."""
    return _avatar_result(a.detection.extract_own_avatar_from_tab())
