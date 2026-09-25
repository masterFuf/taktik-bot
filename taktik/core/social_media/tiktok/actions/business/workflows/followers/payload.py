"""One reading of a TikTok Followers payload, for the bridge and the Agent handler alike.

The bridge read a list of targets (`targetAccounts`, `targets`), shared the profile budget between
them and read the page's percentages; the Agent handler, which the CLI runs, read one target
(`searchQuery`), gave it the whole budget, kept "1" as 100 % and dropped the comment texts.
Target Profiles and Post URL read their interaction settings here too.

The wire form is the page's camelCase, probabilities in percent (always divided by 100). The
snake_case names an Agent plan writes stay accepted, probabilities as fractions (above 1, read as
a percentage). Every key is read by name, so the app's config contract test can see which ones the
bot reads.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_payload import (
    as_bool,
    as_float,
    as_int,
    first_given,
    probability,
    text_list,
)

from .filtering import resolve_tiktok_filter_criteria
from .models import FollowersConfig

#: Profiles a run visits when the payload names no budget (the bridge's; the handler's was 50).
DEFAULT_PROFILE_BUDGET = 20


def _names(raw: Any) -> list[str]:
    """Handles without "@"; filtered after the "@" is gone, so a bare "@" is no target."""
    if isinstance(raw, str):
        raw = [raw]
    cleaned = (str(name or "").strip().replace("@", "") for name in raw)
    return [name for name in cleaned if name]


def followers_targets_from_payload(payload: Mapping[str, Any]) -> list[str]:
    """The accounts whose followers the run walks, in order, "@" removed.

    A list wins (`targetAccounts`, then `targets`), even when none of its names is usable;
    otherwise the single target under the page's name (`searchQuery`) or the older ones an Agent
    plan or a CLI call may carry.
    """
    for key in ("targetAccounts", "targets"):
        raw = payload.get(key)
        if raw:
            return _names(raw)

    single = (
        payload.get("searchQuery")
        or payload.get("search_query")
        or payload.get("target")
        or payload.get("username")
    )
    if isinstance(single, (list, tuple)):
        single = single[0] if single else ""
    return _names([single])


def names_a_target_list(payload: Mapping[str, Any]) -> bool:
    """True when a target list was sent, even one without a usable name."""
    return bool(payload.get("targetAccounts")) or bool(payload.get("targets"))


def profile_budget_from_payload(payload: Mapping[str, Any]) -> int:
    """How many profiles the whole run may visit: `maxFollowers`, else `maxVideos`."""
    return as_int(
        payload.get("maxFollowers")
        or payload.get("max_followers")
        or first_given(payload.get("maxVideos"), payload.get("max_videos")),
        DEFAULT_PROFILE_BUDGET,
    )


def profile_budgets(total: int, target_count: int) -> list[int]:
    """Each target's share of the run's budget; the first targets take the remainder.

    The shares add up to the budget, never more: below the number of targets, the last targets
    get nothing.
    """
    per_target, extra = divmod(max(total, 0), target_count)
    return [per_target + (1 if index < extra else 0) for index in range(target_count)]


def session_limits_from_payload(payload: Mapping[str, Any]) -> tuple[int, int]:
    """(likes, follows) the whole session may spend."""
    return (
        as_int(first_given(payload.get("maxLikesPerSession"), payload.get("max_likes_per_session")), 50),
        as_int(first_given(payload.get("maxFollowsPerSession"), payload.get("max_follows_per_session")), 20),
    )


def bot_username_from_payload(payload: Mapping[str, Any]) -> Optional[str]:
    """The account the app says the run acts as; the phone's own profile wins over it."""
    value = payload.get("botUsername") or payload.get("bot_username")
    return str(value) if value else None


def followers_settings_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The interaction settings of every profile-visiting workflow, read once, same defaults.

    `skipPrivateAccounts` is not read here: it is a filter criterion (`allow_private`), which
    `filters` carries.
    """
    return {
        "posts_per_profile": as_int(first_given(payload.get("postsPerProfile"), payload.get("posts_per_profile")), 2),
        "min_watch_time": as_float(first_given(payload.get("minWatchTime"), payload.get("min_watch_time")), 5.0),
        "max_watch_time": as_float(first_given(payload.get("maxWatchTime"), payload.get("max_watch_time")), 15.0),
        "like_probability": probability(payload.get("likeProbability"), payload.get("like_probability"), 70),
        "favorite_probability": probability(
            payload.get("favoriteProbability"), payload.get("favorite_probability"), 30
        ),
        "comment_probability": probability(
            payload.get("commentProbability"), payload.get("comment_probability"), 10
        ),
        "comment_texts": (
            text_list(payload.get("commentTexts"))
            or text_list(payload.get("comments"))
            or text_list(payload.get("comment_texts"))
        ),
        "max_comments_per_session": as_int(
            first_given(payload.get("maxCommentsPerSession"), payload.get("max_comments_per_session")), 10
        ),
        "share_probability": probability(payload.get("shareProbability"), payload.get("share_probability"), 5),
        "follow_probability": probability(payload.get("followProbability"), payload.get("follow_probability"), 50),
        "story_like_probability": probability(
            payload.get("storyLikeProbability"), payload.get("story_like_probability"), 50
        ),
        "min_delay": as_float(first_given(payload.get("minDelay"), payload.get("min_delay")), 1.0),
        "max_delay": as_float(first_given(payload.get("maxDelay"), payload.get("max_delay")), 3.0),
        "pause_after_actions": as_int(
            first_given(payload.get("pauseAfterActions"), payload.get("pause_after_actions")), 10
        ),
        "pause_duration_min": as_float(
            first_given(payload.get("pauseDurationMin"), payload.get("pause_duration_min")), 30.0
        ),
        "pause_duration_max": as_float(
            first_given(payload.get("pauseDurationMax"), payload.get("pause_duration_max")), 60.0
        ),
        "include_friends": as_bool(first_given(payload.get("includeFriends"), payload.get("include_friends")), False),
        "max_consecutive_known_usernames": as_int(
            first_given(payload.get("maxConsecutiveKnownUsernames"), payload.get("max_consecutive_known_usernames")),
            150,
        ),
        "filters": resolve_tiktok_filter_criteria(payload),
    }


def followers_config_for_target(
    settings: Mapping[str, Any],
    *,
    search_query: str,
    max_followers: int,
    max_likes_per_session: int,
    max_follows_per_session: int,
    config_class: type = FollowersConfig,
    **extra: Any,
):
    """The config of one pass: the run's settings, this pass's share of the budgets."""
    return config_class(**{
        **settings,
        "search_query": search_query,
        "max_followers": max_followers,
        "max_likes_per_session": max_likes_per_session,
        "max_follows_per_session": max_follows_per_session,
        **extra,
    })


__all__ = [
    "DEFAULT_PROFILE_BUDGET",
    "bot_username_from_payload",
    "followers_config_for_target",
    "followers_settings_from_payload",
    "followers_targets_from_payload",
    "names_a_target_list",
    "profile_budget_from_payload",
    "profile_budgets",
    "session_limits_from_payload",
]
