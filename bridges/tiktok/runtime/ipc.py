"""TikTok-specific stdout IPC helpers for bridge runtime code."""

from typing import Any, Dict

from bridges.common.runtime.bridge_base import (
    _ipc,
    get_workflow,
    logger,
    send_error,
    send_log,
    send_message,
    send_progress,
    send_status,
    set_workflow,
    signal_handler,
)


def send_stats(
    videos_watched: int = 0,
    videos_liked: int = 0,
    users_followed: int = 0,
    videos_favorited: int = 0,
    videos_skipped: int = 0,
    errors: int = 0,
) -> None:
    """Send TikTok stats update to desktop app."""
    _ipc.tiktok_stats(
        videos_watched=videos_watched,
        videos_liked=videos_liked,
        users_followed=users_followed,
        videos_favorited=videos_favorited,
        videos_skipped=videos_skipped,
        errors=errors,
    )


def send_video_info(
    author: str,
    description: str = None,
    like_count: str = None,
    is_liked: bool = False,
    is_followed: bool = False,
    is_ad: bool = False,
    hashtags: list = None,
    sound: str = None,
    author_pic: str = None,
) -> None:
    """Send current video info to desktop app."""
    _ipc.video_info(
        author,
        description,
        like_count,
        is_liked,
        is_followed,
        is_ad,
        hashtags=hashtags,
        sound=sound,
        author_pic=author_pic,
    )


def send_action(action: str, target: str = "") -> None:
    """Send action event to desktop app."""
    _ipc.action(action, target)


def send_pause(duration: int) -> None:
    """Send pause event to desktop app."""
    _ipc.pause(duration)


def send_dm_conversation(conversation: Dict[str, Any]) -> None:
    """Send a conversation data to desktop app."""
    _ipc.dm_conversation(conversation)


def send_dm_progress(current: int, total: int, name: str) -> None:
    """Send DM reading progress to desktop app."""
    _ipc.dm_progress(current, total, name)


def send_dm_stats(stats: Dict[str, Any]) -> None:
    """Send DM workflow stats to desktop app."""
    _ipc.dm_stats(stats)


def send_dm_sent(conversation: str, success: bool, error: str = None) -> None:
    """Send DM sent result to desktop app."""
    _ipc.dm_sent(conversation, success, error)


__all__ = [
    "_ipc",
    "logger",
    "send_message",
    "send_status",
    "send_error",
    "send_log",
    "send_progress",
    "get_workflow",
    "set_workflow",
    "signal_handler",
    "send_stats",
    "send_video_info",
    "send_action",
    "send_pause",
    "send_dm_conversation",
    "send_dm_progress",
    "send_dm_stats",
    "send_dm_sent",
]
