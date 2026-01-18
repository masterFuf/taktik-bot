#!/usr/bin/env python3
"""
TikTok Bridge Base - Common utilities for all TikTok bridges
"""

import sys
import os
import json
from typing import Dict, Any
from loguru import logger

# Force UTF-8 encoding for stdout/stderr to support emojis on Windows
# Also disable buffering for real-time output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# Configure loguru
logger.remove()
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    colorize=False
)

# Keep a reference to the original stdout buffer
_original_stdout_fd = None
try:
    _original_stdout_fd = os.dup(1)
except Exception:
    pass


def send_message(msg_type: str, **kwargs):
    """Send a structured JSON message to the desktop app."""
    global _original_stdout_fd
    try:
        message = {"type": msg_type, **kwargs}
        msg_bytes = (json.dumps(message) + '\n').encode('utf-8')
        if _original_stdout_fd is not None:
            try:
                os.write(_original_stdout_fd, msg_bytes)
                # Force flush to ensure immediate delivery
                os.fsync(_original_stdout_fd)
            except (OSError, ValueError):
                pass
        else:
            try:
                os.write(1, msg_bytes)
                # Force flush stdout
                try:
                    os.fsync(1)
                except OSError:
                    pass
            except (OSError, ValueError):
                pass
    except Exception:
        pass


def send_status(status: str, message: str = ""):
    """Send status update to desktop app."""
    send_message("status", status=status, message=message)


def send_stats(videos_watched: int = 0, videos_liked: int = 0, users_followed: int = 0, 
               videos_favorited: int = 0, videos_skipped: int = 0, errors: int = 0):
    """Send stats update to desktop app."""
    send_message("stats", stats={
        "videos_watched": videos_watched,
        "videos_liked": videos_liked,
        "users_followed": users_followed,
        "videos_favorited": videos_favorited,
        "videos_skipped": videos_skipped,
        "errors": errors
    })


def send_video_info(author: str, description: str = None, like_count: str = None, 
                    is_liked: bool = False, is_followed: bool = False, is_ad: bool = False):
    """Send current video info to desktop app."""
    send_message("video_info", video={
        "author": author,
        "description": description,
        "like_count": like_count,
        "is_liked": is_liked,
        "is_followed": is_followed,
        "is_ad": is_ad
    })


def send_action(action: str, target: str = ""):
    """Send action event to desktop app."""
    send_message("action", action=action, target=target)


def send_pause(duration: int):
    """Send pause event to desktop app."""
    send_message("pause", duration=duration)


def send_dm_conversation(conversation: Dict[str, Any]):
    """Send a conversation data to desktop app."""
    send_message("dm_conversation", conversation=conversation)


def send_dm_progress(current: int, total: int, name: str):
    """Send DM reading progress to desktop app."""
    send_message("dm_progress", current=current, total=total, name=name)


def send_dm_stats(stats: Dict[str, Any]):
    """Send DM workflow stats to desktop app."""
    send_message("dm_stats", stats=stats)


def send_dm_sent(conversation: str, success: bool, error: str = None):
    """Send DM sent result to desktop app."""
    send_message("dm_sent", conversation=conversation, success=success, error=error)


def send_error(error: str):
    """Send error to desktop app."""
    send_message("error", error=error)


def send_log(level: str, message: str):
    """Send log message to desktop app."""
    send_message("log", level=level, message=message)


# Global workflow reference for signal handling
_workflow = None


def get_workflow():
    """Get the current workflow reference."""
    global _workflow
    return _workflow


def set_workflow(workflow):
    """Set the current workflow reference."""
    global _workflow
    _workflow = workflow


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    global _workflow
    logger.info("🛑 Received interrupt signal, stopping workflow...")
    send_status("stopping", "Received stop signal")
    if _workflow:
        _workflow.stop()
    sys.exit(0)
