"""Request validation for the YouTube upload bridge."""

from dataclasses import dataclass
import os
from typing import Callable


@dataclass
class YouTubeUploadRequest:
    """Normalized upload request consumed by the YouTube upload bridge."""

    device_id: str
    local_path: str
    title: str
    description: str
    upload_type: str
    visibility: str


def build_upload_request(
    config: dict,
    short_title_max_length: int,
    send_error: Callable[[str], None],
    send_log: Callable[[str, str], None],
) -> YouTubeUploadRequest | None:
    """Validate and normalize the incoming upload bridge payload."""
    device_id = config.get("deviceId")
    local_path = config.get("localPath", "")
    title = config.get("title", "")
    description = config.get("description", "")
    upload_type = config.get("uploadType", "short").lower()
    visibility = config.get("visibility", "public").lower()

    if not device_id:
        send_error("deviceId is required")
        return None
    if not local_path:
        send_error("localPath is required")
        return None
    if not os.path.isfile(local_path):
        send_error(f"File not found: {local_path}")
        return None

    if upload_type == "short" and title:
        chars = list(title.strip())
        if len(chars) > short_title_max_length:
            title = "".join(chars[:short_title_max_length]).strip()
            send_log(
                "warning",
                f"YouTube Shorts title trimmed to {short_title_max_length} characters",
            )

    return YouTubeUploadRequest(
        device_id=device_id,
        local_path=local_path,
        title=title,
        description=description,
        upload_type=upload_type,
        visibility=visibility,
    )
