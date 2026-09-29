"""Instagram scraping and discovery IPC events."""

from __future__ import annotations

from bridges.common.bridge_base import _ipc


#: `profile_captured` key <- key of the profile data the workflows read.
_PROFILE_CAPTURED_FIELDS = (
    ("full_name", "full_name"),
    ("follower_count", "followers_count"),
    ("following_count", "following_count"),
    ("media_count", "posts_count"),
    ("is_private", "is_private"),
    ("is_verified", "is_verified"),
    ("biography", "biography"),
)


def send_profile_captured(username: str, profile_data: dict = None, profile_pic_base64: str = None):
    """Send captured profile data (with optional base64 image) to desktop app.

    Only what was read goes out: a key the profile data does not hold, or holds as None (not
    read), is left out of the line, never sent as 0 or false; a profile not read must not pass for
    a public profile with 0 followers. The app reads every key but `username` as optional.
    """
    data = {"username": username}
    for line_key, data_key in _PROFILE_CAPTURED_FIELDS:
        value = (profile_data or {}).get(data_key)
        if value is not None:
            data[line_key] = value
    if profile_pic_base64:
        data["profile_pic_url"] = profile_pic_base64
    _ipc.send("profile_captured", **data)


def send_profile_skipped(username: str, reason: str = "already in DB", detail: str = None):
    """Send profile skipped (dedup) event to Taktik Agent panel.

    ``detail`` is an optional human hint the desktop appends to the localized reason
    (original filter reason for already_filtered, day count for already_processed).
    """
    _ipc.send("profile_skipped", username=username, reason=reason, detail=detail)


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
