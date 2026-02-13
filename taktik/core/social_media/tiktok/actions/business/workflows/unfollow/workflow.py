"""Unfollow Workflow for TikTok automation.

Navigates to the bot's profile, opens the Following list,
and unfollows users one by one with human-like delays.
"""

from typing import Optional, Callable, Dict, Any
from loguru import logger
import time
import random

from ....atomic.navigation_actions import NavigationActions
from ....atomic.scroll_actions import ScrollActions
from ....core.base_action import BaseAction
from ....ui.selectors import FOLLOWERS_SELECTORS
from .models import UnfollowConfig, UnfollowStats


class UnfollowWorkflow:
    """Core unfollow logic — no IPC, no bridge dependencies."""

    def __init__(self, device, config: UnfollowConfig):
        self.device = device
        self.config = config
        self.stats = UnfollowStats()
        self.stopped = False

        # Action helpers
        self._nav = NavigationActions(device)
        self._scroll = ScrollActions(device)
        self._base = BaseAction(device)
        self._selectors = FOLLOWERS_SELECTORS

        # Callbacks (set by bridge)
        self._on_unfollow: Optional[Callable] = None
        self._on_skip: Optional[Callable] = None
        self._on_stats: Optional[Callable] = None

    # ── public setters ──────────────────────────────────────────────

    def set_on_unfollow_callback(self, cb: Callable):
        self._on_unfollow = cb

    def set_on_skip_callback(self, cb: Callable):
        self._on_skip = cb

    def set_on_stats_callback(self, cb: Callable):
        self._on_stats = cb

    def stop(self):
        self.stopped = True

    # ── run ──────────────────────────────────────────────────────────

    def run(self) -> UnfollowStats:
        """Navigate to profile → Following list → unfollow loop.

        Returns the final stats.
        """
        # 1. Navigate to profile tab
        logger.info("👤 Navigating to profile...")
        if not self._nav.navigate_to_profile():
            raise RuntimeError("Failed to navigate to profile")
        time.sleep(2)

        # 2. Open Following list
        logger.info("📋 Opening following list...")
        if not self._base._find_and_click(self._selectors.following_list_opener, timeout=5):
            raise RuntimeError("Failed to open following list")
        time.sleep(2)

        # 3. Unfollow loop
        scroll_attempts = 0

        while self.stats.unfollowed < self.config.max_unfollows and not self.stopped:
            buttons = self.device.xpath(
                self._selectors.following_or_friends_button[0]
            ).all()

            if not buttons:
                scroll_attempts += 1
                if scroll_attempts >= self.config.max_scroll_attempts:
                    logger.info("No more users to unfollow (no buttons found)")
                    break
                logger.info("No buttons found, scrolling...")
                self._scroll.scroll_profile_videos(direction='down')
                time.sleep(1)
                continue

            unfollowed_this_round = 0

            for elem in buttons:
                if self.stats.unfollowed >= self.config.max_unfollows or self.stopped:
                    break

                try:
                    btn_text = elem.text or ''
                    username = self._resolve_username(elem)

                    # Skip mutual-follow ("Friends") if configured
                    if 'Friends' in btn_text and not self.config.include_friends:
                        self.stats.skipped_friends += 1
                        if self._on_skip:
                            self._on_skip(username)
                        logger.info(f"⏭️ Skipped friend: @{username or 'unknown'}")
                        continue

                    # Click the button → unfollow
                    elem.click()
                    time.sleep(1)

                    # Handle confirmation dialog
                    self._base._find_and_click(self._selectors.unfollow_confirm_button, timeout=2, human_delay=False)

                    self.stats.unfollowed += 1
                    unfollowed_this_round += 1
                    logger.info(f"✅ Unfollowed @{username or 'unknown'} ({self.stats.unfollowed}/{self.config.max_unfollows})")

                    if self._on_unfollow:
                        self._on_unfollow(username, self.stats.unfollowed)
                    self._emit_stats()

                    # Human-like delay
                    delay = random.uniform(self.config.min_delay, self.config.max_delay)
                    time.sleep(delay)

                except Exception as e:
                    self.stats.errors += 1
                    logger.warning(f"Failed to unfollow: {e}")
                    continue

            if unfollowed_this_round == 0:
                scroll_attempts += 1
                if scroll_attempts >= self.config.max_scroll_attempts:
                    logger.info("No more users to unfollow (only Friends remaining)")
                    break
                self._scroll.scroll_profile_videos(direction='down')
                time.sleep(1)
            else:
                scroll_attempts = 0

        return self.stats

    # ── helpers ──────────────────────────────────────────────────────

    def _resolve_username(self, button_elem) -> Optional[str]:
        """Try to find the username associated with a Following/Friends button."""
        try:
            btn_bounds = button_elem.bounds
            if not btn_bounds:
                return None
            username_elems = self.device.xpath(
                self._selectors.follower_username[0]
            ).all()
            for ue in username_elems:
                ue_bounds = ue.bounds
                if ue_bounds and abs(ue_bounds[1] - btn_bounds[1]) < 50:
                    return ue.text
        except Exception:
            pass
        return None

    def _emit_stats(self):
        if self._on_stats:
            self._on_stats(self.stats.to_dict())
