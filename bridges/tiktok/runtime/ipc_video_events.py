"""TikTok video/action IPC event helpers."""

from __future__ import annotations

from bridges.common.runtime.bridge_base import _ipc


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
    watch_time: float = None,
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
        watch_time=watch_time,
    )


def send_action(action: str, target: str = "") -> None:
    """Send action event to desktop app."""
    _ipc.action(action, target)


def send_pause(duration: int) -> None:
    """Send pause event to desktop app."""
    _ipc.pause(duration)


def send_relevance(
    username: str,
    *,
    relevant: bool,
    score=None,
    reason: str = None,
    follow: bool = False,
    comment: bool = False,
    like: bool = False,
) -> None:
    """Surface the AI engagement verdict for a profile (the WHY) to the desktop app —
    platform-neutral `ai_relevance` message consumed by the Taktik Agent panel."""
    _ipc.send(
        "ai_relevance",
        username=username,
        relevant=bool(relevant),
        score=score,
        reason=reason,
        follow=bool(follow),
        comment=bool(comment),
        like=bool(like),
    )


__all__ = ["send_stats", "send_video_info", "send_action", "send_pause", "send_relevance"]
