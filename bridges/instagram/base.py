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


def send_scraping_profile_visit(username: str, profile_data: dict = None):
    """Emit a scraping_profile_visit event (pre-AI, pre-deep-qualify) to the Agent panel."""
    pd = profile_data or {}
    _ipc.scraping_profile_visit(
        username=username,
        biography=pd.get('biography', ''),
        followers_count=pd.get('followers_count'),
        following_count=pd.get('following_count'),
        posts_count=pd.get('posts_count'),
        full_name=pd.get('full_name', ''),
        is_business=bool(pd.get('is_business', False)),
        business_category=pd.get('business_category', ''),
        is_private=bool(pd.get('is_private', False)),
        is_verified=bool(pd.get('is_verified', False)),
    )


def send_scraping_dq_progress(username: str, count: int, max_count: int):
    """Emit live following-collection progress during deep qualify."""
    _ipc.scraping_dq_progress(username=username, count=count, max_count=max_count)


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
# The proxy implementation lives in `taktik.core.clone.device.proxy` so that
# non-bridge code (workflows, CLI, recorder) can reuse the exact same
# rewriting logic. We re-export the class here as `_CloneAwareDeviceProxy`
# for backward compatibility with any external import.

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy as _CloneAwareDeviceProxy  # noqa: E402


# ── Base class for Instagram bridges ─────────────────────────────────

class InstagramBridgeBase(PlatformBridgeBase):
    """Instagram-specific bridge base.

    Extends `PlatformBridgeBase` with:
    - Clone package registration (``set_active_package``)
    - Transparent device proxy that rewrites resourceId for clone packages
    - The proxy is propagated to ``device_manager.device`` so workflows
      constructed from the manager also benefit from it transparently.
    - ``rid()`` helper for manual resourceId resolution
    - ``restart_instagram()`` backward-compatible alias
    """

    PLATFORM = "instagram"
    DEFAULT_PACKAGE = "com.instagram.android"

    def _after_connect(self) -> None:
        """Register clone package globally and wrap device proxy everywhere
        (bridge, ConnectionService, DeviceManager) so that workflows and
        helpers constructed downstream see the same proxy."""
        if not (self.package_name and self.package_name != self.DEFAULT_PACKAGE):
            return

        from taktik.core.clone import set_active_package
        set_active_package(self.package_name)

        # The raw uiautomator2 device — wrap it once.
        raw_device = self._connection.device
        # Avoid double-wrapping if connect() is somehow called twice.
        if isinstance(raw_device, _CloneAwareDeviceProxy):
            proxy = raw_device
        else:
            proxy = _CloneAwareDeviceProxy(raw_device, self.package_name)

        # Bridge attribute (used by bridge methods)
        self.device = proxy
        # DeviceManager attribute — workflows do `self.device = device_manager.device`
        # so this is what makes the proxy visible to every downstream workflow.
        if self.device_manager is not None:
            self.device_manager.device = proxy
        # ConnectionService cache — keep in sync so `conn.device` also returns proxy.
        try:
            self._connection._device = proxy
        except AttributeError:
            pass

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


def _register_core_ipc_emitter() -> None:
    """Expose bridge IPC helpers to core workflows without core importing bridges."""
    try:
        import sys

        from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter

        IPCEmitter.configure_bridge_adapter(sys.modules[__name__])
    except Exception as exc:
        logger.debug(f"Could not register core IPC emitter adapter: {exc}")


_register_core_ipc_emitter()


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
