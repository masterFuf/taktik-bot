"""One reading of an Instagram publication's payload, for the bridge, the CLI and the Lab alike.

The desktop bridge read its file in its constructor and refused in `run`; the CLI built the
workflow's arguments itself; the Lab's bench did the same. The request is now read here once
(`publish_request_from_payload`), by the one launcher (`agent_handler.run_instagram_publish`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from taktik.core.social_media.instagram.workflows.common.startup import package_name_from_payload

#: What `InstagramPostWorkflow` publishes.
POST_TYPES = ("post", "reel", "carousel", "story")


class PublishRequestError(ValueError):
    """A publication refused before the phone is touched."""


@dataclass(frozen=True)
class PublishRequest:
    """What one publication is asked, read once from its payload."""

    post_type: str
    media_paths: list[str]
    caption: str = ""
    hashtags: list[str] | None = None
    package_name: Optional[str] = None
    bot_username: Optional[str] = None
    #: The CLI's: a story entered through the feed's story tray instead of the create button.
    story_via_feed: bool = False
    #: The CLI's and the Lab's rehearsal: the whole flow, stopped before the share button.
    stop_before_share: bool = False


def _first(payload: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def media_paths_from_payload(payload: Mapping[str, Any]) -> list[str]:
    """The media to publish: the list (`mediaPaths`), else the single file (`localPath`)."""
    listed = _first(payload, "mediaPaths", "media_paths")
    if listed:
        return [str(path) for path in listed if path]
    single = _first(payload, "localPath", "local_path")
    return [str(single)] if single else []


def publish_request_from_payload(payload: Mapping[str, Any]) -> PublishRequest:
    """The publication a payload asks for. Refuses an unknown kind and a publication without a
    media, before the phone is touched."""
    media_paths = media_paths_from_payload(payload)
    post_type = str(_first(payload, "postType", "post_type") or "post").lower()
    if post_type not in POST_TYPES:
        raise PublishRequestError(f"Unsupported postType '{post_type}' (expected one of {POST_TYPES})")
    if not media_paths:
        raise PublishRequestError("At least one media path is required (mediaPaths/localPath)")
    hashtags = _first(payload, "hashtags")
    return PublishRequest(
        post_type=post_type,
        media_paths=media_paths,
        caption=str(_first(payload, "caption") or ""),
        hashtags=[str(tag) for tag in hashtags] if hashtags else [],
        package_name=package_name_from_payload(payload),
        bot_username=_first(payload, "botUsername", "bot_username"),
        story_via_feed=bool(_first(payload, "storyViaFeed", "story_via_feed")),
        stop_before_share=bool(_first(payload, "stopBeforeShare", "stop_before_share")),
    )


def published_kind(request: PublishRequest) -> str:
    """What the workflow publishes. Several media on a feed post IS a carousel, Instagram has no
    other meaning for it: a caller that sends every path but leaves the type at "post" would get
    the single-media branch, which publishes one image while the rest sit unused in the gallery."""
    if request.post_type == "post" and len(request.media_paths) > 1:
        return "carousel"
    return request.post_type


__all__ = [
    "POST_TYPES",
    "PublishRequest",
    "PublishRequestError",
    "media_paths_from_payload",
    "publish_request_from_payload",
    "published_kind",
]
