#!/usr/bin/env python3
"""
Instagram Bridge Base — Instagram-specific helpers + clone-aware bridge base.

Common scaffolding (bootstrap, IPC singleton, send_message/status/error/log,
signal handling, PlatformBridgeBase) lives in `bridges.common.bridge_base`.
This module only adds:
  - Instagram-specific IPC helpers (instagram_stats, follow_event, ...)
  - `_CloneAwareDeviceProxy` for resourceId rewriting on cloned packages
  - `InstagramBridgeBase` (subclass of `PlatformBridgeBase`)
  - `setup_stats_callback()` to wire `BaseStatsManager` to IPC

Usage:
    from bridges.instagram.base import (
        logger, send_status, send_error, send_message, send_stats,
        send_instagram_stats, send_instagram_action, send_follow_event,
        send_like_event, send_unfollow_event, send_post_skipped,
        send_current_post, send_instagram_profile_visit,
        send_log, send_progress, setup_stats_callback,
        _ipc,
    )
"""

from bridges.common.bridge_base import (
    _ipc,
    logger,
    send_message,
    send_status,
    send_error,
    send_log,
    send_progress,
    get_workflow,
    set_workflow,
    signal_handler,
    PlatformBridgeBase,
)


# ── Instagram-specific IPC helpers ───────────────────────────────────

def send_stats(likes: int = 0, follows: int = 0, comments: int = 0, profiles: int = 0, unfollows: int = 0):
    """Send legacy stats update to desktop app."""
    _ipc.send("stats", likes=likes, follows=follows, comments=comments, profiles=profiles, unfollows=unfollows)


def send_instagram_stats(
    profiles_visited: int = 0,
    profiles_interacted: int = 0,
    profiles_filtered: int = 0,
    private_profiles: int = 0,
    likes: int = 0,
    follows: int = 0,
    comments: int = 0,
    stories_watched: int = 0,
    errors: int = 0,
):
    """Send comprehensive Instagram stats update to desktop app."""
    _ipc.instagram_stats(
        profiles_visited=profiles_visited,
        profiles_interacted=profiles_interacted,
        profiles_filtered=profiles_filtered,
        private_profiles=private_profiles,
        likes=likes,
        follows=follows,
        comments=comments,
        stories_watched=stories_watched,
        errors=errors,
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


def send_post_skipped(author: str, reason: str = "already_processed", hashtag: str = None):
    """Send post skipped event to desktop app for real-time activity."""
    _ipc.send("post_skipped", author=author, reason=reason, hashtag=hashtag)


def send_current_post(author: str, likes_count: int = None, comments_count: int = None, caption: str = None, hashtag: str = None):
    """Send current post metadata to desktop app for live panel display."""
    _ipc.send("current_post",
              author=author,
              likes_count=likes_count,
              comments_count=comments_count,
              caption=caption[:100] if caption else None,
              hashtag=hashtag)


def _on_stats_update(stats_dict: dict):
    """Callback for BaseStatsManager to send stats via IPC."""
    send_instagram_stats(
        profiles_visited=stats_dict.get('profiles_visited', 0),
        profiles_interacted=stats_dict.get('profiles_interacted', 0),
        profiles_filtered=stats_dict.get('profiles_filtered', 0),
        private_profiles=stats_dict.get('private_profiles', 0),
        likes=stats_dict.get('likes', 0),
        follows=stats_dict.get('follows', 0),
        comments=stats_dict.get('comments', 0),
        stories_watched=stats_dict.get('stories_watched', 0),
        errors=stats_dict.get('errors', 0)
    )


def setup_stats_callback():
    """Setup the stats callback on BaseStatsManager for IPC updates."""
    try:
        from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager
        # Store original __init__ to wrap it
        original_init = BaseStatsManager.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            # Automatically set the IPC callback on every new StatsManager
            self.set_on_stats_callback(_on_stats_update)

        BaseStatsManager.__init__ = patched_init
        logger.info("✅ Stats IPC callback configured for BaseStatsManager")
    except Exception as e:
        logger.warning(f"Could not setup stats callback: {e}")


# ── Clone-aware device proxy ─────────────────────────────────────────

class _CloneAwareDeviceProxy:
    """Transparent proxy around a uiautomator2 device that rewrites
    ``resourceId`` keyword arguments on-the-fly so that bridges written
    for ``com.instagram.android`` work unmodified on clone packages
    (e.g. ``com.taktik.ig1``).

    All attribute access and method calls are forwarded to the real device.
    Only ``__call__`` (selector creation) intercepts ``resourceId`` to patch
    the package prefix.
    """

    __slots__ = ("_device", "_official", "_clone")

    def __init__(self, device, clone_package: str):
        object.__setattr__(self, "_device", device)
        object.__setattr__(self, "_official", "com.instagram.android")
        object.__setattr__(self, "_clone", clone_package)

    # Forward attribute access (press, swipe, xpath, screenshot, …)
    def __getattr__(self, name):
        return getattr(self._device, name)

    # Intercept selector creation: device(resourceId="com.instagram.android:id/…")
    def __call__(self, *args, **kwargs):
        rid = kwargs.get("resourceId")
        if rid and self._official in rid:
            kwargs["resourceId"] = rid.replace(self._official, self._clone)
        return self._device(*args, **kwargs)


# ── Base class for Instagram bridges ─────────────────────────────────

class InstagramBridgeBase(PlatformBridgeBase):
    """Instagram-specific bridge base.

    Extends `PlatformBridgeBase` with:
    - Clone package registration (``set_active_package``)
    - Transparent device proxy that rewrites resourceId for clone packages
    - ``rid()`` helper for manual resourceId resolution
    - ``restart_instagram()`` backward-compatible alias
    """

    PLATFORM = "instagram"
    DEFAULT_PACKAGE = "com.instagram.android"

    def _after_connect(self) -> None:
        """Register clone package globally and wrap device proxy."""
        if self.package_name and self.package_name != self.DEFAULT_PACKAGE:
            from taktik.core.clone import set_active_package
            set_active_package(self.package_name)
            # Wrap raw underlying device (not the alias we set) so attribute
            # forwarding works correctly.
            self.device = _CloneAwareDeviceProxy(
                self._connection.device, self.package_name
            )

    def rid(self, resource_id: str) -> str:
        """Resolve a resource-id for the active package.

        Replaces 'com.instagram.android' with the active clone package
        when running on a cloned app (e.g. com.taktik.ig1).

        Usage:
            self.device(resourceId=self.rid("com.instagram.android:id/search_tab"))
        """
        if self.package_name and self.package_name != self.DEFAULT_PACKAGE:
            return resource_id.replace(self.DEFAULT_PACKAGE, self.package_name)
        return resource_id

    def restart_instagram(self):
        """Backward-compatible alias for `restart()`."""
        self.restart()


__all__ = [
    # IPC + helpers re-exported from bridges.common.bridge_base
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
    # Instagram-specific helpers
    "send_stats",
    "send_instagram_stats",
    "send_instagram_action",
    "send_instagram_profile_visit",
    "send_unfollow_event",
    "send_follow_event",
    "send_like_event",
    "send_profile_captured",
    "send_profile_skipped",
    "send_post_skipped",
    "send_current_post",
    "setup_stats_callback",
    # Bridge base + clone proxy
    "InstagramBridgeBase",
    "_CloneAwareDeviceProxy",
]
