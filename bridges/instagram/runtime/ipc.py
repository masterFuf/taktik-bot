"""Instagram-specific stdout IPC helpers for bridge runtime code."""

import sys

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
from bridges.instagram.runtime.ipc_stats import (
    send_instagram_stats,
    send_stats,
    setup_stats_callback,
)


def send_instagram_action(action: str, username: str, details: dict = None):
    """Send Instagram action event to desktop app."""
    _ipc.instagram_action(action, username, details)


def send_instagram_profile_visit(username: str, followers: int = None, is_private: bool = False):
    """Send profile visit event to desktop app."""
    _ipc.profile_visit(username, followers, is_private)


def send_unfollow_event(username: str, success: bool = True):
    """Send unfollow event to desktop app for real-time activity."""
    _ipc.unfollow_event(username, success)


def send_follow_event(username: str, success: bool = True, profile_data: dict = None):
    """Send follow event to desktop app for real-time activity and WorkflowAnalyzer."""
    _ipc.follow_event(username, success, profile_data)


def send_like_event(username: str, likes_count: int = 1, profile_data: dict = None):
    """Send like event to desktop app for real-time activity and WorkflowAnalyzer."""
    _ipc.like_event(username, likes_count, profile_data)


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


def _register_core_ipc_emitter() -> None:
    """Expose Instagram IPC helpers to core workflows without core importing bridges."""
    try:
        from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter

        IPCEmitter.configure_bridge_adapter(sys.modules[__name__])
    except Exception as exc:
        logger.debug(f"Could not register core IPC emitter adapter: {exc}")


_register_core_ipc_emitter()


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
    "send_instagram_stats",
    "send_instagram_action",
    "send_instagram_profile_visit",
    "send_unfollow_event",
    "send_follow_event",
    "send_like_event",
    "send_profile_captured",
    "send_profile_skipped",
    "send_scraping_profile_visit",
    "send_scraping_dq_progress",
    "send_post_skipped",
    "send_current_post",
    "setup_stats_callback",
]
