"""
IPC (Inter-Process Communication) service for bridge scripts.
Handles structured JSON message passing between Python bridges and the Electron app.

Messages are sent via stdout (file descriptor 1) as JSON lines.
Logs go to stderr via loguru — they never interfere with IPC messages.

Usage:
    from bridges.common.runtime.ipc import IPC

    ipc = IPC()
    ipc.status("connecting", "Connecting to device...")
    ipc.error("Something went wrong")
    ipc.progress(current=5, total=100, action="scraping")
    ipc.send("custom_event", key="value")
"""

import os
import json
from typing import Any

from bridges.common.runtime.ipc_ai import AIIpcMixin
from bridges.common.runtime.ipc_dm import DMIpcMixin
from bridges.common.runtime.ipc_tiktok import TikTokIpcMixin


class IPC(TikTokIpcMixin, DMIpcMixin, AIIpcMixin):
    """
    Structured IPC channel to the Electron desktop app.
    
    Writes JSON messages directly to the original stdout file descriptor
    to avoid interference with loguru or print() redirections.
    """

    def __init__(self):
        # Duplicate the original stdout fd BEFORE any wrapper can interfere.
        # This ensures messages always reach Electron's stdout parser.
        self._fd = None
        try:
            self._fd = os.dup(1)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Core send
    # ------------------------------------------------------------------

    def send(self, msg_type: str, **kwargs: Any) -> None:
        """Send a structured JSON message to the desktop app."""
        try:
            message = {"type": msg_type, **kwargs}
            msg_bytes = (json.dumps(message, ensure_ascii=False) + '\n').encode('utf-8')
            if self._fd is not None:
                try:
                    os.write(self._fd, msg_bytes)
                except (OSError, ValueError):
                    pass
            else:
                try:
                    os.write(1, msg_bytes)
                except (OSError, ValueError):
                    pass
        except Exception:
            pass  # Never crash on IPC failure

    # ------------------------------------------------------------------
    # Common message helpers
    # ------------------------------------------------------------------

    def status(self, status: str, message: str = "") -> None:
        """Send a status update (connecting, launching, running, etc.)."""
        self.send("status", status=status, message=message)

    def error(self, error: str, error_code: str = None) -> None:
        """Send an error message with optional error_code for i18n."""
        data = {"error": error}
        if error_code:
            data["error_code"] = error_code
        self.send("error", **data)

    def progress(self, current: int, total: int, action: str = "") -> None:
        """Send a progress update (e.g. 5/100 profiles scraped)."""
        self.send("progress", current=current, total=total, action=action)

    def log(self, level: str, message: str) -> None:
        """Send a log message to the desktop debug console."""
        self.send("log", level=level, message=message)

    def stats(self, **stats: Any) -> None:
        """Send stats update (platform-agnostic)."""
        self.send("stats", stats=stats)

    # ------------------------------------------------------------------
    # Instagram-specific helpers
    # ------------------------------------------------------------------

    def instagram_stats(
        self,
        profiles_visited: int = 0,
        profiles_interacted: int = 0,
        profiles_filtered: int = 0,
        private_profiles: int = 0,
        likes: int = 0,
        follows: int = 0,
        comments: int = 0,
        stories_watched: int = 0,
        errors: int = 0,
    ) -> None:
        """Send comprehensive Instagram stats update."""
        self.send("instagram_stats", stats={
            "profiles_visited": profiles_visited,
            "profiles_interacted": profiles_interacted,
            "profiles_filtered": profiles_filtered,
            "private_profiles": private_profiles,
            "likes": likes,
            "follows": follows,
            "comments": comments,
            "stories_watched": stories_watched,
            "errors": errors,
        })

    def instagram_action(self, action: str, username: str, details: dict = None) -> None:
        """Send Instagram action event (like, follow, filter, etc.)."""
        data = {"action": action, "username": username}
        if details:
            data["details"] = details
        self.send("instagram_action", **data)

    def follow_event(self, username: str, success: bool = True, profile_data: dict = None) -> None:
        """Send follow event for real-time activity."""
        data = {"username": username, "success": success}
        if profile_data:
            data["profile_data"] = profile_data
        self.send("follow_event", **data)

    def like_event(self, username: str, likes_count: int = 1, profile_data: dict = None) -> None:
        """Send like event for real-time activity."""
        data = {"username": username, "likes_count": likes_count}
        if profile_data:
            data["profile_data"] = profile_data
        self.send("like_event", **data)

    def unfollow_event(self, username: str, success: bool = True) -> None:
        """Send unfollow event."""
        self.send("unfollow_event", username=username, success=success)

    def profile_visit(self, username: str, followers: int = None, is_private: bool = False) -> None:
        """Send profile visit event."""
        self.send("instagram_profile_visit", username=username, followers=followers, is_private=is_private)

    def scraping_profile_visit(self, username: str, biography: str = None,
                               followers_count: int = None, following_count: int = None,
                               posts_count: int = None, full_name: str = None,
                               is_business: bool = False, business_category: str = None,
                               is_private: bool = False, is_verified: bool = False) -> None:
        """Signal that we've visited a profile during scraping (pre-AI)."""
        data: dict = dict(
            username=username,
            is_business=is_business,
            is_private=is_private,
            is_verified=is_verified,
        )
        if biography is not None:
            data['biography'] = biography
        if followers_count is not None:
            data['followers_count'] = followers_count
        if following_count is not None:
            data['following_count'] = following_count
        if posts_count is not None:
            data['posts_count'] = posts_count
        if full_name is not None:
            data['full_name'] = full_name
        if business_category is not None:
            data['business_category'] = business_category
        self.send("scraping_profile_visit", **data)

    def scraping_dq_progress(self, username: str, count: int, max_count: int) -> None:
        """Emit live following-collection progress during deep qualify."""
        self.send("scraping_dq_progress", username=username, count=count, max_count=max_count)

    def post_skipped(self, author: str, reason: str = "already_processed", hashtag: str = None) -> None:
        """Send post skipped event."""
        self.send("post_skipped", author=author, reason=reason, hashtag=hashtag)

    def current_post(self, author: str, likes_count: int = None, comments_count: int = None,
                     caption: str = None, hashtag: str = None) -> None:
        """Send current post metadata for live panel."""
        self.send("current_post", author=author, likes_count=likes_count,
                  comments_count=comments_count,
                  caption=caption[:100] if caption else None,
                  hashtag=hashtag)

    def session_start(self, session_id: int, **kwargs) -> None:
        """Send session start event with session ID."""
        self.send("session_start", session_id=session_id, **kwargs)

    # ------------------------------------------------------------------
    # Threads-specific helpers
    # ------------------------------------------------------------------

    def threads_stats(
        self,
        profiles_visited: int = 0,
        profiles_interacted: int = 0,
        profiles_filtered: int = 0,
        private_profiles: int = 0,
        likes: int = 0,
        follows: int = 0,
        reposts: int = 0,
        replies: int = 0,
        errors: int = 0,
    ) -> None:
        """Send comprehensive Threads stats update."""
        self.send("threads_stats", stats={
            "profiles_visited": profiles_visited,
            "profiles_interacted": profiles_interacted,
            "profiles_filtered": profiles_filtered,
            "private_profiles": private_profiles,
            "likes": likes,
            "follows": follows,
            "reposts": reposts,
            "replies": replies,
            "errors": errors,
        })

    def threads_action(self, action: str, username: str, details: dict = None) -> None:
        """Send Threads action event (like, follow, repost, etc.)."""
        data = {"action": action, "username": username}
        if details:
            data["details"] = details
        self.send("threads_action", **data)

    def threads_profile_visit(self, username: str, followers: int = None, is_private: bool = False) -> None:
        """Send Threads profile visit event."""
        self.send("threads_profile_visit", username=username, followers=followers, is_private=is_private)
