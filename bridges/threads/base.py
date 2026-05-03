#!/usr/bin/env python3
"""Threads bridge base — shared helpers for all Threads bridge scripts.

Mirrors `bot/bridges/instagram/base.py` but emits Threads-prefixed IPC
events. Delegates bootstrap, IPC and signal handling to `bridges.common`.

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

import os
import sys

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment

setup_environment()

from bridges.common import signal_handler as _sig_mod
from bridges.common.ipc import IPC
from loguru import logger

# Shared IPC singleton
_ipc = IPC()


# ── Module-level IPC wrappers ────────────────────────────────────────

def send_message(msg_type: str, **kwargs):
    """Send a structured JSON message to the desktop app."""
    _ipc.send(msg_type, **kwargs)


def send_status(status: str, message: str = ""):
    """Send status update to desktop app."""
    _ipc.status(status, message)


def send_progress(current: int, total: int, action: str = ""):
    """Send progress update to desktop app."""
    _ipc.progress(current, total, action)


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


def send_error(error: str, error_code: str = None):
    """Send error to desktop app with optional error code for translation."""
    _ipc.error(error, error_code)


def send_log(level: str, message: str):
    """Send log message to desktop app."""
    _ipc.log(level, message)


# ── Workflow reference + signal handling (parity with Instagram) ──────

def get_workflow():
    """Get the current workflow reference."""
    return _sig_mod._workflow


def set_workflow(workflow):
    """Set the current workflow reference for signal handling."""
    _sig_mod.update_workflow(workflow)


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully (delegates to shared handler)."""
    _sig_mod._handle_signal(signum, frame)


# ── Base class for Threads bridges ───────────────────────────────────

class ThreadsBridgeBase:
    """Base class for Threads bridge scripts that need a device connection.

    Responsibilities:
    - Initialize `ConnectionService` and `AppService`
    - Expose backward-compatible aliases (`self.device_manager`, `self.device`)
    - Provide `restart_threads()` for clean-state workflows
    """

    PLATFORM = "threads"
    DEFAULT_PACKAGE = "com.instagram.barcelona"

    def __init__(self, device_id: str, package_name: str = None):
        from bridges.common.connection import ConnectionService

        self.device_id = device_id
        self.package_name = package_name or self.DEFAULT_PACKAGE
        self._connection = ConnectionService(device_id)
        self._app = None
        # Backward-compatible aliases populated by `connect()`
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
        self._app = AppService(
            self._connection,
            platform=self.PLATFORM,
            package_override=self.package_name,
        )
        return True

    def restart_threads(self):
        """Restart Threads for a clean state via AppService."""
        self._app.restart()
