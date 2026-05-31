#!/usr/bin/env python3
"""Threads bridge base — re-exports shared infrastructure + Threads-specific helpers.

Common scaffolding (bootstrap, IPC singleton, status/error/log wrappers,
signal handling, PlatformBridgeBase) lives in `bridges.common.runtime.bridge_base`.
This module adds only the Threads-specific IPC events and the
`ThreadsBridgeBase` subclass.

Usage:
    from bridges.threads.base import (
        logger, _ipc,
        send_message, send_status, send_progress,
        send_threads_stats, send_threads_action, send_threads_profile_visit,
        send_follow_event, send_unfollow_event,
        send_error, send_log,
        ThreadsBridgeBase,
    )
"""

from bridges.common.runtime.bridge_base import (
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


# ── Threads-specific IPC helpers ─────────────────────────────────────

def send_threads_stats(
    profiles_visited: int = 0,
    profiles_interacted: int = 0,
    profiles_filtered: int = 0,
    private_profiles: int = 0,
    likes: int = 0,
    follows: int = 0,
    reposts: int = 0,
    replies: int = 0,
    errors: int = 0,
):
    """Send comprehensive Threads stats update."""
    _ipc.threads_stats(
        profiles_visited=profiles_visited,
        profiles_interacted=profiles_interacted,
        profiles_filtered=profiles_filtered,
        private_profiles=private_profiles,
        likes=likes,
        follows=follows,
        reposts=reposts,
        replies=replies,
        errors=errors,
    )


def send_threads_action(action: str, username: str, details: dict = None):
    """Send a Threads action event (like, follow, repost, ...)."""
    _ipc.threads_action(action, username, details)


def send_threads_profile_visit(username: str, followers: int = None, is_private: bool = False):
    """Send a Threads profile visit event."""
    _ipc.threads_profile_visit(username, followers, is_private)


def send_follow_event(username: str, success: bool = True, profile_data: dict = None):
    """Send follow event (platform-agnostic helper)."""
    _ipc.follow_event(username, success, profile_data)


def send_unfollow_event(username: str, success: bool = True):
    """Send unfollow event (platform-agnostic helper)."""
    _ipc.unfollow_event(username, success)


# ── Threads bridge base class ────────────────────────────────────────

class ThreadsBridgeBase(PlatformBridgeBase):
    """Threads-specific bridge base. Inherits connect/restart from `PlatformBridgeBase`."""

    PLATFORM = "threads"
    DEFAULT_PACKAGE = "com.instagram.barcelona"

    def restart_threads(self):
        """Backward-compatible alias for `restart()`."""
        self.restart()


__all__ = [
    "_ipc",
    "logger",
    "send_message",
    "send_status",
    "send_progress",
    "send_error",
    "send_log",
    "send_threads_stats",
    "send_threads_action",
    "send_threads_profile_visit",
    "send_follow_event",
    "send_unfollow_event",
    "get_workflow",
    "set_workflow",
    "signal_handler",
    "ThreadsBridgeBase",
]
