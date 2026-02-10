#!/usr/bin/env python3
"""
TikTok Bridge Base - Common utilities for all TikTok bridges.

Now delegates to bridges.common for bootstrap, IPC, and signal handling.
Module-level functions are kept for backward compatibility with existing TikTok bridges.
"""

import sys
import os
from typing import Dict, Any

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

def send_stats(videos_watched: int = 0, videos_liked: int = 0, users_followed: int = 0,
               videos_favorited: int = 0, videos_skipped: int = 0, errors: int = 0):
    """Send stats update to desktop app."""
    _ipc.tiktok_stats(
        videos_watched=videos_watched, videos_liked=videos_liked,
        users_followed=users_followed, videos_favorited=videos_favorited,
        videos_skipped=videos_skipped, errors=errors,
    )

def send_video_info(author: str, description: str = None, like_count: str = None,
                    is_liked: bool = False, is_followed: bool = False, is_ad: bool = False):
    """Send current video info to desktop app."""
    _ipc.video_info(author, description, like_count, is_liked, is_followed, is_ad)

def send_action(action: str, target: str = ""):
    """Send action event to desktop app."""
    _ipc.action(action, target)

def send_pause(duration: int):
    """Send pause event to desktop app."""
    _ipc.pause(duration)

def send_dm_conversation(conversation: Dict[str, Any]):
    """Send a conversation data to desktop app."""
    _ipc.dm_conversation(conversation)

def send_dm_progress(current: int, total: int, name: str):
    """Send DM reading progress to desktop app."""
    _ipc.dm_progress(current, total, name)

def send_dm_stats(stats: Dict[str, Any]):
    """Send DM workflow stats to desktop app."""
    _ipc.dm_stats(stats)

def send_dm_sent(conversation: str, success: bool, error: str = None):
    """Send DM sent result to desktop app."""
    _ipc.dm_sent(conversation, success, error)

def send_error(error: str):
    """Send error to desktop app."""
    _ipc.error(error)

def send_log(level: str, message: str):
    """Send log message to desktop app."""
    _ipc.log(level, message)


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
