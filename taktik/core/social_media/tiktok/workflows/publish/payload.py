"""One reading of a TikTok publish payload, for the desktop bridge and the Agent handler alike.

The wire form is what the desktop writes (`TikTokUploadWorkflowService.writeConfig`): a video
(`localPath`, `caption`, `hashtags`) or a text post (`postType: text`, `text`, `toStory`), with an
optional `packageName` for a cloned TikTok and the operated account (`botUsername`, the key the
followers and unfollow payloads use). The snake_case names an Agent plan or a CLI call
writes stay accepted. Every key is read by name, so the app's config contract test can see which
ones the bot reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


class PublishRequestError(ValueError):
    """A request that cannot be published: refused before the phone is touched."""


@dataclass
class PublishRequest:
    #: `video` (the gallery upload) or `text`; any other value takes the video road, as it did.
    post_type: str = "video"
    local_path: str = ""
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    text: str = ""
    to_story: bool = False
    package_name: Optional[str] = None
    #: The operated account: a refused publication is filed in its health history.
    bot_username: Optional[str] = None


def _first_given(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _hashtags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None]
    raise PublishRequestError("TikTok upload_post hashtags must be a list of strings")


def publish_request_from_payload(payload: Mapping[str, Any]) -> PublishRequest:
    """The request of one publish run. Refuses a video without a file and a text post without
    text: nothing would be published."""
    post_type = str(_first_given(payload.get("postType"), payload.get("post_type")) or "video").strip().lower()
    local_path = _first_given(payload.get("localPath"), payload.get("local_path")) or ""
    text = payload.get("text") or ""

    if post_type == "video" and not local_path:
        raise PublishRequestError("localPath is required")
    if post_type == "text" and not str(text).strip():
        raise PublishRequestError("text is required for a text post")

    return PublishRequest(
        post_type=post_type,
        local_path=str(local_path),
        caption=str(payload.get("caption") or ""),
        hashtags=_hashtags(payload.get("hashtags")),
        text=str(text),
        to_story=bool(_first_given(payload.get("toStory"), payload.get("to_story")) or False),
        package_name=_first_given(payload.get("packageName"), payload.get("package_name")),
        bot_username=(str(_first_given(payload.get("botUsername"), payload.get("bot_username")) or "")
                      .strip().lstrip("@") or None),
    )


__all__ = ["PublishRequest", "PublishRequestError", "publish_request_from_payload"]
