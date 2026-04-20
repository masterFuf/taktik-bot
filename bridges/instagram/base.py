#!/usr/bin/env python3
"""
Instagram Bridge Base - Common utilities for all Instagram bridges.

Delegates to bridges.common for bootstrap, IPC, and signal handling.
Module-level functions are kept for backward compatibility with existing Instagram bridges.

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

import sys
import os

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.ipc import IPC
from bridges.common import signal_handler as _sig_mod
from loguru import logger

# Shared IPC singleton
_ipc = IPC()

# ── Module-level IPC wrappers (backward-compatible) ──────────────────

def send_message(msg_type: str, **kwargs):
    """Send a structured JSON message to the desktop app."""
    _ipc.send(msg_type, **kwargs)

def send_status(status: str, message: str = ""):
    """Send status update to desktop app."""
    _ipc.status(status, message)

def send_progress(current: int, total: int, action: str = ""):
    """Send progress update to desktop app."""
    _ipc.progress(current, total, action)

def send_stats(likes: int = 0, follows: int = 0, comments: int = 0, profiles: int = 0, unfollows: int = 0):
    """Send stats update to desktop app."""
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
    errors: int = 0
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

def send_error(error: str, error_code: str = None):
    """Send error to desktop app with optional error code for translation."""
    _ipc.error(error, error_code)

def send_log(level: str, message: str):
    """Send log message to desktop app."""
    _ipc.log(level, message)

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


# ── Workflow reference + signal handling (backward-compatible) ────────

def get_workflow():
    """Get the current workflow reference."""
    return _sig_mod._workflow

def set_workflow(workflow):
    """Set the current workflow reference for signal handling."""
    _sig_mod.update_workflow(workflow)

def signal_handler(signum, frame):
    """Handle interrupt signals gracefully (delegates to shared handler)."""
    _sig_mod._handle_signal(signum, frame)


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

class InstagramBridgeBase:
    """
    Base class for Instagram bridge scripts that need device connection.

    Handles:
    - ConnectionService + AppService initialization
    - Backward-compatible aliases (self.device_manager, self.device, self.screen_width/height)
    - restart_instagram() via AppService

    Usage:
        class MyBridge(InstagramBridgeBase):
            def __init__(self, device_id):
                super().__init__(device_id)
                # add your own init here
    """

    def __init__(self, device_id: str, package_name: str = None):
        from bridges.common.connection import ConnectionService
        self.device_id = device_id
        self.package_name = package_name  # e.g. "com.taktik.ig1"
        # Shared services
        self._connection = ConnectionService(device_id)
        self._app = None  # initialized after connect
        # Backward-compatible aliases
        self.device_manager = None
        self.device = None
        self.screen_width = 1080
        self.screen_height = 2340

    def connect(self) -> bool:
        """Connect to the device using ConnectionService."""
        from bridges.common.app_manager import AppService
        if not self._connection.connect():
            return False
        self.device_manager = self._connection.device_manager
        self.device = self._connection.device
        self.screen_width, self.screen_height = self._connection.screen_size
        self._app = AppService(self._connection, platform="instagram",
                               package_override=self.package_name)
        # Register clone package globally and wrap device proxy
        if self.package_name and self.package_name != "com.instagram.android":
            from taktik.core.clone import set_active_package
            set_active_package(self.package_name)
            self.device = _CloneAwareDeviceProxy(self._connection.device, self.package_name)
        return True

    def rid(self, resource_id: str) -> str:
        """Resolve a resource-id for the active package.
        
        Replaces 'com.instagram.android' with the active clone package
        when running on a cloned app (e.g. com.taktik.ig1).
        
        Usage:
            self.device(resourceId=self.rid("com.instagram.android:id/search_tab"))
        """
        if self.package_name and self.package_name != "com.instagram.android":
            return resource_id.replace("com.instagram.android", self.package_name)
        return resource_id

    def restart_instagram(self):
        """Restart Instagram for clean state via AppService."""
        self._app.restart()
