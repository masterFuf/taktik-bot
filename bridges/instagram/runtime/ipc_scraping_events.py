"""Instagram scraping and discovery IPC events."""

from __future__ import annotations

from bridges.common.runtime.bridge_base import _ipc


def send_profile_captured(username: str, profile_data: dict = None, profile_pic_base64: str = None):
    """Send captured profile data (with optional base64 image) to desktop app."""
    data = {"username": username}
    if profile_data:
        data.update({
            "full_name": profile_data.get("full_name"),
            "follower_count": profile_data.get("followers_count", 0),
            "following_count": profile_data.get("following_count", 0),
            "media_count": profile_data.get("posts_count", 0),
            "is_private": profile_data.get("is_private", False),
            "is_verified": profile_data.get("is_verified", False),
            "biography": profile_data.get("biography"),
        })
    if profile_pic_base64:
        data["profile_pic_url"] = profile_pic_base64
    _ipc.send("profile_captured", **data)


def send_profile_skipped(username: str, reason: str = "already in DB"):
    """Send profile skipped (dedup) event to Taktik Agent panel."""
    _ipc.send("profile_skipped", username=username, reason=reason)


def send_scraping_profile_visit(username: str, profile_data: dict = None):
    """Emit a scraping_profile_visit event (pre-AI, pre-deep-qualify) to the Agent panel."""
    pd = profile_data or {}
    _ipc.scraping_profile_visit(
        username=username,
        biography=pd.get("biography", ""),
        followers_count=pd.get("followers_count"),
        following_count=pd.get("following_count"),
        posts_count=pd.get("posts_count"),
        full_name=pd.get("full_name", ""),
        is_business=bool(pd.get("is_business", False)),
        business_category=pd.get("business_category", ""),
        is_private=bool(pd.get("is_private", False)),
        is_verified=bool(pd.get("is_verified", False)),
    )


def send_scraping_dq_progress(username: str, count: int, max_count: int):
    """Emit live following-collection progress during deep qualify."""
    _ipc.scraping_dq_progress(username=username, count=count, max_count=max_count)


def send_post_skipped(author: str, reason: str = "already_processed", hashtag: str = None):
    """Send post skipped event to desktop app for real-time activity."""
    _ipc.send("post_skipped", author=author, reason=reason, hashtag=hashtag)


def send_current_post(
    author: str,
    likes_count: int = None,
    comments_count: int = None,
    caption: str = None,
    hashtag: str = None,
):
    """Send current post metadata to desktop app for live panel display."""
    _ipc.send(
        "current_post",
        author=author,
        likes_count=likes_count,
        comments_count=comments_count,
        caption=caption[:100] if caption else None,
        hashtag=hashtag,
    )


__all__ = [
    "send_profile_captured",
    "send_profile_skipped",
    "send_scraping_profile_visit",
    "send_scraping_dq_progress",
    "send_post_skipped",
    "send_current_post",
]
