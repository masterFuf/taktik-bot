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


# ── TikTok startup helper ────────────────────────────────────────────

def tiktok_startup(device_id: str, fetch_profile: bool = True):
    """
    Common TikTok startup sequence used by most workflow bridges.

    1. Create TikTokManager and restart app
    2. Navigate to Home (For You feed)
    3. Optionally fetch own profile info and send bot_profile IPC message

    Args:
        device_id: The Android device serial.
        fetch_profile: If True, navigate to profile tab, fetch info, and return it.

    Returns:
        (manager, bot_username) — manager is the TikTokManager instance,
        bot_username is the fetched username (or None if fetch_profile=False or failed).
    """
    import time
    from taktik.core.social_media.tiktok import TikTokManager

    # Connect + restart
    logger.info("📱 Connecting to device...")
    send_status("connecting", "Connecting to device")

    manager = TikTokManager(device_id=device_id)

    logger.info("📱 Restarting TikTok (clean state)...")
    send_status("launching", "Restarting TikTok app")

    if not manager.restart():
        raise RuntimeError("Failed to restart TikTok app")

    time.sleep(4)  # Wait for app to fully load

    # Navigate to Home
    try:
        from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
        nav_actions = NavigationActions(manager.device_manager.device)
        nav_actions._press_back()
        time.sleep(0.5)
        nav_actions.navigate_to_home()
        time.sleep(1)
        logger.info("✅ Navigated to For You feed")
    except Exception as e:
        logger.warning(f"Could not navigate to Home: {e}")

    # Fetch own profile
    bot_username = None
    if fetch_profile:
        try:
            from taktik.core.social_media.tiktok.actions.business.actions.profile_actions import ProfileActions

            logger.info("📊 Fetching own profile info...")
            send_status("fetching_profile", "Fetching your TikTok profile info")

            profile_actions = ProfileActions(manager.device_manager.device)
            profile_info = profile_actions.fetch_own_profile()

            if profile_info:
                bot_username = profile_info.username
                logger.info(f"✅ Bot account: @{profile_info.username} ({profile_info.display_name})")
                logger.info(f"   Followers: {profile_info.followers_count}, Following: {profile_info.following_count}")

                send_message("bot_profile", profile={
                    "username": profile_info.username,
                    "display_name": profile_info.display_name,
                    "followers_count": profile_info.followers_count,
                    "following_count": profile_info.following_count,
                })
                logger.info("📤 Bot profile message sent to frontend")
            else:
                logger.warning("❌ Could not fetch profile info - profile_info is None")
        except Exception as e:
            logger.error(f"❌ Error fetching profile info: {e}")
            import traceback
            logger.error(traceback.format_exc())

    return manager, bot_username


# ── Video workflow helpers ────────────────────────────────────────────

def setup_video_workflow_callbacks(workflow):
    """
    Wire up standard IPC callbacks for video-based workflows
    (For You, Search, etc.). Avoids duplicating the same 5 callbacks
    in every bridge.
    """
    def on_video(video_info):
        send_video_info(
            author=video_info.get('author', 'unknown'),
            description=video_info.get('description'),
            like_count=video_info.get('like_count'),
            is_liked=video_info.get('is_liked', False),
            is_followed=video_info.get('is_followed', False),
            is_ad=video_info.get('is_ad', False)
        )

    def on_like(video_info):
        send_action("like", video_info.get('author', 'unknown'))
        logger.info(f"❤️ Liked video by @{video_info.get('author', 'unknown')}")

    def on_follow(video_info):
        send_action("follow", video_info.get('author', 'unknown'))
        logger.info(f"👤 Followed @{video_info.get('author', 'unknown')}")

    def on_stats(stats_dict):
        send_stats(
            videos_watched=stats_dict.get('videos_watched', 0),
            videos_liked=stats_dict.get('videos_liked', 0),
            users_followed=stats_dict.get('users_followed', 0),
            videos_favorited=stats_dict.get('videos_favorited', 0),
            videos_skipped=stats_dict.get('videos_skipped', 0),
            errors=stats_dict.get('errors', 0)
        )

    def on_pause(duration: int):
        send_pause(duration)
        logger.info(f"⏸️ Taking a break for {duration}s")

    workflow.set_on_video_callback(on_video)
    workflow.set_on_like_callback(on_like)
    workflow.set_on_follow_callback(on_follow)
    workflow.set_on_stats_callback(on_stats)
    workflow.set_on_pause_callback(on_pause)


def send_final_video_stats(stats, workflow_name: str = "Workflow"):
    """Send final stats and completion status for a video-based workflow."""
    send_stats(
        videos_watched=stats.videos_watched,
        videos_liked=stats.videos_liked,
        users_followed=stats.users_followed,
        videos_favorited=stats.videos_favorited,
        videos_skipped=stats.videos_skipped,
        errors=stats.errors
    )
    logger.success(f"✅ {workflow_name} completed: {stats.to_dict()}")
    send_status("completed", f"{workflow_name} completed: {stats.videos_watched} videos, {stats.videos_liked} likes, {stats.users_followed} follows")
