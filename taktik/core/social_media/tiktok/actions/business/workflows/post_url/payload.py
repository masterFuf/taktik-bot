"""What a TikTok Post URL payload says beyond the Followers settings: the link and its budgets.

The interaction settings are the Followers ones (`followers/payload.py`), read the same way. The
wire form is the page's camelCase (`TikTokPostUrl.tsx`); the snake_case names an Agent plan or a
CLI call writes stay accepted.
"""

from __future__ import annotations

from typing import Any, Mapping

from taktik.core.social_media.tiktok.actions.business.workflows.followers.payload import (
    followers_config_for_target,
    followers_settings_from_payload,
    session_limits_from_payload,
)


def post_url_from_payload(payload: Mapping[str, Any]) -> str:
    """The link to open, in whichever key carries it; "" when none does.

    Never `searchQuery` nor a target field: this run acts on exactly one video, and guessing it
    from an unrelated key is the wrong-target failure it exists to avoid.
    """
    for key in ("postUrl", "post_url", "videoUrl", "video_url", "url", "postLink"):
        raw = str(payload.get(key) or "").strip()
        if raw:
            return raw
    return ""


def max_commenters_from_payload(payload: Mapping[str, Any]) -> int:
    """How many commenters to resolve: each one costs a profile open."""
    return int(payload.get("maxCommenters") or payload.get("max_commenters") or 20)


def profile_budget_from_payload(payload: Mapping[str, Any], max_commenters: int) -> int:
    """How many commenters to visit: `maxProfiles`, else `maxFollowers`, else `maxVideos` (the
    name the live panel reads), else the commenter budget."""
    for key in ("maxProfiles", "max_profiles", "maxFollowers", "max_followers", "maxVideos", "max_videos"):
        value = payload.get(key)
        if value:
            return int(value)
    return max_commenters


def device_id_from_payload(payload: Mapping[str, Any]) -> str:
    """The serial the link is opened on."""
    return str(payload.get("deviceId") or payload.get("device_id") or "")


def post_url_config_from_payload(payload: Mapping[str, Any]):
    """The config of one Post URL run: the Followers settings, this link, these budgets."""
    from taktik.core.social_media.tiktok.actions.business.workflows.post_url.workflow import PostUrlConfig

    max_commenters = max_commenters_from_payload(payload)
    max_likes, max_follows = session_limits_from_payload(payload)
    return followers_config_for_target(
        followers_settings_from_payload(payload),
        search_query="",  # no source account: the video is the source
        max_followers=profile_budget_from_payload(payload, max_commenters),
        max_likes_per_session=max_likes,
        max_follows_per_session=max_follows,
        config_class=PostUrlConfig,
        post_url=post_url_from_payload(payload),
        max_commenters=max_commenters,
        max_comment_scrolls=int(payload.get("maxCommentScrolls") or payload.get("max_comment_scrolls") or 8),
    )


__all__ = [
    "device_id_from_payload",
    "max_commenters_from_payload",
    "post_url_config_from_payload",
    "post_url_from_payload",
    "profile_budget_from_payload",
]
