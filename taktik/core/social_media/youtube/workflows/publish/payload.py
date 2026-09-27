"""One reading of a YouTube upload payload, for the desktop bridge and the Agent handler alike.

The wire form is what the desktop writes (`YouTubeUploadWorkflowService`): `localPath`, `title`,
`description`, `uploadType`, `visibility`. The snake_case names an Agent plan or a CLI call writes
stay accepted, after the wire name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

SHORT_TITLE_MAX_LENGTH = 100


class YouTubeUploadRequestError(ValueError):
    """A request that cannot be uploaded: refused before the phone is touched."""


@dataclass(frozen=True)
class YouTubeUploadRequest:
    local_path: str
    title: str = ""
    description: str = ""
    upload_type: str = "short"
    visibility: str = "public"
    #: The Short's title was longer than YouTube takes and was cut.
    title_trimmed: bool = False

    def workflow_params(self) -> dict[str, Any]:
        """The keyword arguments of `YouTubeUploadWorkflow.execute`."""
        return {
            "local_path": self.local_path,
            "title": self.title,
            "description": self.description,
            "upload_type": self.upload_type,
            "visibility": self.visibility,
        }


def youtube_upload_request_from_payload(payload: Mapping[str, Any]) -> YouTubeUploadRequest:
    """The request of one upload. Refuses a payload without a file path."""
    local_path = _string_param(payload, "localPath", "local_path", default="")
    if not local_path:
        raise YouTubeUploadRequestError("YouTube upload_post requires a non-empty localPath")
    upload_type = _string_param(payload, "uploadType", "upload_type", default="short").lower()
    title, trimmed = _short_title(_string_param(payload, "title", default=""), upload_type)
    return YouTubeUploadRequest(
        local_path=local_path,
        title=title,
        description=_string_param(payload, "description", default=""),
        upload_type=upload_type,
        visibility=_string_param(payload, "visibility", default="public").lower(),
        title_trimmed=trimmed,
    )


def check_upload_file(request: YouTubeUploadRequest) -> None:
    """Refuses a file that is not on this computer."""
    if not os.path.isfile(request.local_path):
        raise YouTubeUploadRequestError(f"File not found: {request.local_path}")


def _string_param(payload: Mapping[str, Any], *names: str, default: str) -> str:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return value if isinstance(value, str) else str(value)
    return default


def _short_title(title: str, upload_type: str) -> tuple[str, bool]:
    """A Short's title, cut at the length YouTube takes."""
    if upload_type != "short" or not title:
        return title, False
    chars = list(title.strip())
    if len(chars) <= SHORT_TITLE_MAX_LENGTH:
        return title.strip(), False
    return "".join(chars[:SHORT_TITLE_MAX_LENGTH]).strip(), True


__all__ = [
    "SHORT_TITLE_MAX_LENGTH",
    "YouTubeUploadRequest",
    "YouTubeUploadRequestError",
    "check_upload_file",
    "youtube_upload_request_from_payload",
]
