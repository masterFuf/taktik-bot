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


def send_profile_classification(username: str, classification: dict, result: str = "") -> None:
    """Send the AI classification of a TikTok profile so the desktop PERSISTS it.

    The verdict was already surfaced to the panel by `send_relevance`; what was thrown away is
    the CLASSIFICATION behind it — the niche, the profession, the age group. TikTok paid a vision
    call for every profile on every pass and kept none of it, while Instagram has been persisting
    the same shape for months.

    `platform` travels explicitly. The desktop's Instagram path resolves a profile through the
    `instagram_profiles` view, so a TikTok handle sent down that road either saves nothing or,
    worse, writes a TikTok niche onto an Instagram account of the same name. The field is what
    lets the desktop route it to the TikTok profile instead.

    `persist_only` marks this as a persistence re-emit: the AI service already emitted the
    countable event for this analysis, so the desktop's counter must skip this one.
    """
    _ipc.send(
        "ai_profile_done",
        username=username,
        target_username=username,
        platform="tiktok",
        result=result,
        classification=classification,
        workflow_type="automation",
        persist_only=True,
    )


__all__ = [
    "send_stats",
    "send_video_info",
    "send_action",
    "send_pause",
    "send_relevance",
    "send_profile_classification",
]
