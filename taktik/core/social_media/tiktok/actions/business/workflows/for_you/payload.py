"""One reading of a TikTok For You payload, for the bridge and the Agent handler alike.

Two readers used to exist. The bridge read what the page sends; the Agent handler, which the CLI
runs, read an older subset: no comments, no reposts, no feed training, and a percentage of 1 read
as 100 %. The same config commented from the desktop and not from the CLI.

The wire form is the page's camelCase, probabilities in percent. The snake_case names an Agent
plan writes stay accepted, probabilities as fractions. Every key is read by name, so the config
contract test of the app can see which ones the bot reads.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .models import ForYouConfig


def _first(*values: Any) -> Optional[Any]:
    """The first value actually given: None means "not set"."""
    for value in values:
        if value is not None:
            return value
    return None


def _as_int(value: Any, default: int) -> int:
    return int(value) if value is not None else default


def _as_optional_int(value: Any) -> Optional[int]:
    return int(value) if value is not None else None


def _as_float(value: Any, default: float) -> float:
    return float(value) if value is not None else default


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _probability(percent: Any, fraction: Any, default_percent: float) -> float:
    """camelCase is a percentage, always divided by 100; snake_case a fraction, or a percentage above 1."""
    if percent is not None:
        return float(percent) / 100.0
    if fraction is not None:
        fraction = float(fraction)
        return fraction / 100.0 if fraction > 1 else fraction
    return default_percent / 100.0


def _hashtags(value: Any) -> list[str]:
    """Without "#": the filter adds it before matching the caption."""
    if isinstance(value, str):
        value = value.split(",")
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().lstrip("#") for item in value if str(item).strip()]
    return []


def _texts(value: Any) -> list[str]:
    """Free text kept as written: a comment may start with "#" or hold a comma."""
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _keywords(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def for_you_config_from_payload(payload: Mapping[str, Any]) -> ForYouConfig:
    """Build the workflow config from a bridge or Agent payload."""
    return ForYouConfig(
        max_videos=_as_int(_first(payload.get("maxVideos"), payload.get("max_videos")), 50),
        min_watch_time=_as_float(_first(payload.get("minWatchTime"), payload.get("min_watch_time")), 2.0),
        max_watch_time=_as_float(_first(payload.get("maxWatchTime"), payload.get("max_watch_time")), 8.0),
        like_probability=_probability(payload.get("likeProbability"), payload.get("like_probability"), 30),
        follow_probability=_probability(payload.get("followProbability"), payload.get("follow_probability"), 10),
        favorite_probability=_probability(
            payload.get("favoriteProbability"), payload.get("favorite_probability"), 5
        ),
        comment_probability=_probability(
            payload.get("commentProbability"), payload.get("comment_probability"), 0
        ),
        max_comments_per_session=_as_int(
            _first(payload.get("maxCommentsPerSession"), payload.get("max_comments_per_session")), 10
        ),
        repost_probability=_probability(payload.get("repostProbability"), payload.get("repost_probability"), 0),
        max_reposts_per_session=_as_int(
            _first(payload.get("maxRepostsPerSession"), payload.get("max_reposts_per_session")), 5
        ),
        training_keywords=_keywords(_first(payload.get("trainingKeywords"), payload.get("training_keywords"))),
        training_reject_off_niche=_as_bool(
            _first(payload.get("trainingRejectOffNiche"), payload.get("training_reject_off_niche")), True
        ),
        max_rejections_per_session=_as_int(
            _first(payload.get("maxRejectionsPerSession"), payload.get("max_rejections_per_session")), 20
        ),
        comment_texts=(
            _texts(payload.get("commentTexts"))
            or _texts(payload.get("comments"))
            or _texts(payload.get("comment_texts"))
        ),
        required_hashtags=_hashtags(_first(payload.get("requiredHashtags"), payload.get("required_hashtags"))),
        excluded_hashtags=_hashtags(_first(payload.get("excludedHashtags"), payload.get("excluded_hashtags"))),
        min_likes=_as_optional_int(_first(payload.get("minLikes"), payload.get("min_likes"))),
        max_likes=_as_optional_int(_first(payload.get("maxLikes"), payload.get("max_likes"))),
        max_likes_per_session=_as_int(
            _first(payload.get("maxLikesPerSession"), payload.get("max_likes_per_session")), 50
        ),
        max_follows_per_session=_as_int(
            _first(payload.get("maxFollowsPerSession"), payload.get("max_follows_per_session")), 20
        ),
        skip_already_liked=_as_bool(
            _first(payload.get("skipAlreadyLiked"), payload.get("skip_already_liked")), True
        ),
        skip_already_followed=_as_bool(
            _first(payload.get("skipAlreadyFollowed"), payload.get("skip_already_followed")), True
        ),
        skip_ads=_as_bool(_first(payload.get("skipAds"), payload.get("skip_ads")), True),
        follow_back_suggestions=_as_bool(
            _first(payload.get("followBackSuggestions"), payload.get("follow_back_suggestions")), False
        ),
        pause_after_actions=_as_int(
            _first(payload.get("pauseAfterActions"), payload.get("pause_after_actions")), 10
        ),
        pause_duration_min=_as_float(
            _first(payload.get("pauseDurationMin"), payload.get("pause_duration_min")), 30.0
        ),
        pause_duration_max=_as_float(
            _first(payload.get("pauseDurationMax"), payload.get("pause_duration_max")), 60.0
        ),
    )


__all__ = ["for_you_config_from_payload"]
