"""Base Video Workflow — shared logic for ForYou and Search workflows.

Centralises: callbacks, stop/pause/resume, like/follow/favorite,
action-decision, limits, pause checks, popup handling, stuck-video detection,
stats dataclass, and _parse_count delegation.

Subclasses only need to implement:
    - run()            — the main entry point
    - _should_skip_video()  (optional override)
"""

from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from loguru import logger
import time
import random

from ...core.utils import parse_count
from ._base_workflow import BaseTikTokWorkflow


# ---------------------------------------------------------------------------
# Shared Stats dataclass
# ---------------------------------------------------------------------------

@dataclass
class VideoWorkflowStats:
    """Statistics shared by all video-based workflows (ForYou, Search, …)."""

    videos_watched: int = 0
    videos_liked: int = 0
    users_followed: int = 0
    videos_favorited: int = 0
    videos_skipped: int = 0
    ads_skipped: int = 0
    popups_closed: int = 0
    suggestions_handled: int = 0
    errors: int = 0

    start_time: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time
        return {
            'videos_watched': self.videos_watched,
            'videos_liked': self.videos_liked,
            'users_followed': self.users_followed,
            'videos_favorited': self.videos_favorited,
            'videos_skipped': self.videos_skipped,
            'ads_skipped': self.ads_skipped,
            'popups_closed': self.popups_closed,
            'suggestions_handled': self.suggestions_handled,
            'errors': self.errors,
            'elapsed_seconds': elapsed,
            'elapsed_formatted': f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
        }


# ---------------------------------------------------------------------------
# Base workflow
# ---------------------------------------------------------------------------

class BaseVideoWorkflow(BaseTikTokWorkflow):
    """Base class for video-feed workflows (ForYou, Search, …).

    Inherits from BaseTikTokWorkflow:
        - atomic-action helpers (click, navigation, scroll, detection)
        - popup handler
        - stop / pause / resume / _wait_if_paused
        - _send_stats_update, set_on_stats_callback

    Adds:
        - 4 video-specific callback setters
        - _like_video, _follow_user, _favorite_video
        - _decide_and_execute_actions
        - _check_limits_reached, _check_pause_needed
        - _handle_stuck_video (stuck-video detection)
        - _parse_count (delegate to utils.parse_count)
        - get_stats
    """

    def __init__(self, device, *, module_name: str = "tiktok-video-workflow"):
        super().__init__(device, module_name=module_name)

        # Video-specific callbacks
        self._on_video_callback: Optional[Callable] = None
        self._on_like_callback: Optional[Callable] = None
        self._on_follow_callback: Optional[Callable] = None
        self._on_pause_callback: Optional[Callable] = None

        # Video-specific state
        self._actions_since_pause = 0

        # Stuck-video tracking
        self._last_video_signature: Optional[str] = None
        self._same_video_count = 0

    # ------------------------------------------------------------------
    # Callback setters
    # ------------------------------------------------------------------

    def set_on_video_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called for each video processed."""
        self._on_video_callback = callback

    def set_on_like_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called when a video is liked."""
        self._on_like_callback = callback

    def set_on_follow_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called when a user is followed."""
        self._on_follow_callback = callback

    def set_on_pause_callback(self, callback: Callable[[int], None]):
        """Set callback called when workflow takes a pause."""
        self._on_pause_callback = callback

    # ------------------------------------------------------------------
    # Video actions
    # ------------------------------------------------------------------

    def _like_video(self, video_info: Dict[str, Any]) -> bool:
        """Like the current video."""
        self.logger.info(f"❤️ Liking video by @{video_info.get('author')}")

        if self.click.click_like_button():
            self.stats.videos_liked += 1
            self._send_stats_update()

            if self._on_like_callback:
                try:
                    self._on_like_callback(video_info)
                except Exception as e:
                    self.logger.warning(f"Like callback error: {e}")
            return True
        return False

    def _follow_user(self, video_info: Dict[str, Any]) -> bool:
        """Follow the current video's author."""
        self.logger.info(f"👤 Following @{video_info.get('author')}")

        if self.click.click_video_follow_button():
            self.stats.users_followed += 1
            self._send_stats_update()

            if self._on_follow_callback:
                try:
                    self._on_follow_callback(video_info)
                except Exception as e:
                    self.logger.warning(f"Follow callback error: {e}")
            return True
        return False

    def _favorite_video(self, video_info: Dict[str, Any]) -> bool:
        """Add current video to favorites."""
        self.logger.info(f"⭐ Adding to favorites: @{video_info.get('author')}")

        if self.click.click_favorite_button():
            self.stats.videos_favorited += 1
            self._send_stats_update()
            return True
        return False

    # ------------------------------------------------------------------
    # Action decision  (uses config.like_probability etc.)
    # ------------------------------------------------------------------

    def _decide_and_execute_actions(self, video_info: Dict[str, Any]):
        """Decide and execute actions based on probabilities.

        Expects ``self.config`` to expose:
            like_probability, follow_probability, favorite_probability,
            max_likes_per_session, max_follows_per_session
        """
        cfg = self.config

        # Like
        if (self.stats.videos_liked < cfg.max_likes_per_session
                and random.random() < cfg.like_probability
                and not video_info.get('is_liked')):
            if self._like_video(video_info):
                self._actions_since_pause += 1

        # Follow
        if (self.stats.users_followed < cfg.max_follows_per_session
                and random.random() < cfg.follow_probability):
            if self._follow_user(video_info):
                self._actions_since_pause += 1

        # Favorite
        if (random.random() < cfg.favorite_probability
                and not video_info.get('is_favorited')):
            if self._favorite_video(video_info):
                self._actions_since_pause += 1

    # ------------------------------------------------------------------
    # Limits & pauses
    # ------------------------------------------------------------------

    def _check_limits_reached(self) -> bool:
        """Check if session limits are reached."""
        if self.stats.videos_liked >= self.config.max_likes_per_session:
            self.logger.info("📊 Max likes per session reached")
            return True
        if self.stats.users_followed >= self.config.max_follows_per_session:
            self.logger.info("📊 Max follows per session reached")
            return True
        return False

    def _check_pause_needed(self):
        """Check if a pause is needed and execute it."""
        if self._actions_since_pause >= self.config.pause_after_actions:
            pause_duration = random.uniform(
                self.config.pause_duration_min,
                self.config.pause_duration_max,
            )
            pause_seconds = int(pause_duration)
            self.logger.info(f"⏸️ Taking a break for {pause_seconds}s")

            if self._on_pause_callback:
                try:
                    self._on_pause_callback(pause_seconds)
                except Exception as e:
                    self.logger.warning(f"Error sending pause callback: {e}")

            time.sleep(pause_duration)
            self._actions_since_pause = 0

    def _handle_popups(self):
        """Override to also track popup stats."""
        if self._popup_handler.close_all():
            self.stats.popups_closed += 1

    # ------------------------------------------------------------------
    # Stuck-video detection
    # ------------------------------------------------------------------

    def _handle_stuck_video(self, video_info: Dict[str, Any]) -> bool:
        """Detect if we're stuck on the same video.

        Returns True if stuck was detected and recovery attempted
        (caller should ``continue`` the loop).
        """
        current_author = video_info.get('author', '')
        current_likes = video_info.get('like_count', '')
        signature = f"{current_author}_{current_likes}"

        if signature == self._last_video_signature and current_author:
            self._same_video_count += 1
            self.logger.warning(
                f"⚠️ Same video detected {self._same_video_count} times: @{current_author}"
            )

            if self._same_video_count >= 3:
                self.logger.error("🚨 Stuck on same video! Checking for blocking popups...")
                self.click.close_system_popup()
                time.sleep(0.3)
                self._handle_popups()
                time.sleep(0.3)
                self.device.press("back")
                time.sleep(0.5)
                self._same_video_count = 0
                return True  # caller should continue
        else:
            self._same_video_count = 0
            self._last_video_signature = signature

        return False

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _parse_count(self, count_str: str) -> int:
        """Parse count string (e.g., '1.2K', '500', '1M') to integer."""
        return parse_count(count_str)

    def get_stats(self) -> Dict[str, Any]:
        """Get current workflow statistics."""
        return self.stats.to_dict()
