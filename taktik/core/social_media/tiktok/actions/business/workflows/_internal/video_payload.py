"""One reading of the settings every TikTok video workflow shares (For You, Search, Hashtag).

The wire form is the desktop page's camelCase, probabilities in percent (always divided by 100,
so "1" is 1 %). The snake_case names an Agent plan writes stay accepted, probabilities as
fractions (above 1, read as a percentage). Every key is read by name, so the app's config
contract test can see which ones the bot reads.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


def first_given(*values: Any) -> Optional[Any]:
    """The first value actually given: None means "not set"."""
    for value in values:
        if value is not None:
            return value
    return None


def as_int(value: Any, default: int) -> int:
    return int(value) if value is not None else default


def as_optional_int(value: Any) -> Optional[int]:
    return int(value) if value is not None else None


def as_float(value: Any, default: float) -> float:
    return float(value) if value is not None else default


def as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def probability(percent: Any, fraction: Any, default_percent: float) -> float:
    """camelCase is a percentage, always divided by 100; snake_case a fraction, or a percentage above 1."""
    if percent is not None:
        return float(percent) / 100.0
    if fraction is not None:
        fraction = float(fraction)
        return fraction / 100.0 if fraction > 1 else fraction
    return default_percent / 100.0


def hashtag_list(value: Any) -> list[str]:
    """Without "#": the filter adds it before matching the caption."""
    if isinstance(value, str):
        value = value.split(",")
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().lstrip("#") for item in value if str(item).strip()]
    return []


def text_list(value: Any) -> list[str]:
    """Free text kept as written: a comment may start with "#" or hold a comma."""
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def keyword_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def video_settings_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The fields For You and Search configs share, read once, with the same defaults."""
    return {
        "max_videos": as_int(first_given(payload.get("maxVideos"), payload.get("max_videos")), 50),
        "min_watch_time": as_float(first_given(payload.get("minWatchTime"), payload.get("min_watch_time")), 2.0),
        "max_watch_time": as_float(first_given(payload.get("maxWatchTime"), payload.get("max_watch_time")), 8.0),
        "like_probability": probability(payload.get("likeProbability"), payload.get("like_probability"), 30),
        "follow_probability": probability(payload.get("followProbability"), payload.get("follow_probability"), 10),
        "favorite_probability": probability(
            payload.get("favoriteProbability"), payload.get("favorite_probability"), 5
        ),
        "comment_probability": probability(
            payload.get("commentProbability"), payload.get("comment_probability"), 0
        ),
        "max_comments_per_session": as_int(
            first_given(payload.get("maxCommentsPerSession"), payload.get("max_comments_per_session")), 10
        ),
        "repost_probability": probability(payload.get("repostProbability"), payload.get("repost_probability"), 0),
        "max_reposts_per_session": as_int(
            first_given(payload.get("maxRepostsPerSession"), payload.get("max_reposts_per_session")), 5
        ),
        "comment_texts": (
            text_list(payload.get("commentTexts"))
            or text_list(payload.get("comments"))
            or text_list(payload.get("comment_texts"))
        ),
        "required_hashtags": hashtag_list(
            first_given(payload.get("requiredHashtags"), payload.get("required_hashtags"))
        ),
        "excluded_hashtags": hashtag_list(
            first_given(payload.get("excludedHashtags"), payload.get("excluded_hashtags"))
        ),
        "min_likes": as_optional_int(first_given(payload.get("minLikes"), payload.get("min_likes"))),
        "max_likes": as_optional_int(first_given(payload.get("maxLikes"), payload.get("max_likes"))),
        "max_likes_per_session": as_int(
            first_given(payload.get("maxLikesPerSession"), payload.get("max_likes_per_session")), 50
        ),
        "max_follows_per_session": as_int(
            first_given(payload.get("maxFollowsPerSession"), payload.get("max_follows_per_session")), 20
        ),
        "skip_already_liked": as_bool(
            first_given(payload.get("skipAlreadyLiked"), payload.get("skip_already_liked")), True
        ),
        "skip_already_followed": as_bool(
            first_given(payload.get("skipAlreadyFollowed"), payload.get("skip_already_followed")), True
        ),
        "skip_ads": as_bool(first_given(payload.get("skipAds"), payload.get("skip_ads")), True),
        "pause_after_actions": as_int(
            first_given(payload.get("pauseAfterActions"), payload.get("pause_after_actions")), 10
        ),
        "pause_duration_min": as_float(
            first_given(payload.get("pauseDurationMin"), payload.get("pause_duration_min")), 30.0
        ),
        "pause_duration_max": as_float(
            first_given(payload.get("pauseDurationMax"), payload.get("pause_duration_max")), 60.0
        ),
    }


__all__ = [
    "as_bool",
    "as_float",
    "as_int",
    "as_optional_int",
    "first_given",
    "hashtag_list",
    "keyword_list",
    "probability",
    "text_list",
    "video_settings_from_payload",
]
