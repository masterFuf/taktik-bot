"""Unfollow Workflow for TikTok automation.

Navigates to the bot's profile, opens the Following list,
and unfollows users one by one with human-like delays.
"""

from typing import Optional, Callable, Dict, Any
from loguru import logger
import time
import random

from ....atomic.navigation.navigation_actions import NavigationActions
from ....atomic.scroll.scroll_actions import ScrollActions
from ....core.base_action import BaseAction
from .....ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from .....ui.labels import is_friends_button
from .....services.followers.stop_policy import normalize_username
from taktik.core.database.tiktok_follow_graph import TikTokFollowGraphService
from .models import UnfollowConfig, UnfollowStats


class UnfollowWorkflow:
    """Core unfollow logic — no IPC, no bridge dependencies."""

    def __init__(self, device, config: UnfollowConfig):
        self.device = device
        self.config = config
        self.stats = UnfollowStats()
        self.stopped = False
        self._account_id: Optional[int] = None
        self._account_resolved = False

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
            buttons = []
            for sel in self._selectors.following_or_friends_button:
                buttons = self.device.xpath(sel).all()
                if buttons:
                    break

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

                    # Skip mutual-follow ("Friends" / "Amis") if configured. The label was
                    # hardcoded English, so on a French phone the option silently did
                    # nothing and every mutual follow was unfollowed anyway.
                    if is_friends_button(btn_text) and not self.config.include_friends:
                        self.stats.skipped_friends += 1
                        if self._on_skip:
                            self._on_skip(username)
                        logger.info(f"⏭️ Skipped friend: @{username or 'unknown'}")
                        continue

                    # "Âge min. (jours)": an account the bot followed too recently stays.
                    if self._followed_too_recently(username):
                        self.stats.skipped_recent_follows += 1
                        if self._on_skip:
                            self._on_skip(username, "followed_too_recently")
                        logger.info(f"⏭️ Followed too recently: @{username}")
                        continue

                    # Click the button → unfollow (humanized tap; centre-click fallback)
                    if not self._base._human_tap_bounds(elem):
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

    def _followed_too_recently(self, username: Optional[str]) -> bool:
        """Whether the bot followed this account less than `min_follow_age_days` ago.

        Only a KNOWN recent follow holds an account back. No handle on the row, no acting account,
        or no FOLLOW record for it (followed by hand, or before the base) means no known age, and
        the run treats it as it did before the rule existed.
        """
        min_days = self.config.min_follow_age_days
        handle = normalize_username(username)
        if min_days <= 0 or not handle:
            return False
        account_id = self._acting_account_id()
        if not account_id:
            return False
        days = TikTokFollowGraphService.get_days_since_follow(handle, account_id)
        return days is not None and days < min_days

    def _acting_account_id(self) -> Optional[int]:
        """The acting account's id, resolved once, the way the list sync resolves it."""
        if self._account_resolved:
            return self._account_id
        self._account_resolved = True
        username = normalize_username(self.config.bot_username)
        if not username:
            logger.warning("Minimum follow age ignored: the acting account is unknown")
            return None
        try:
            from taktik.core.database.local.service import get_local_database

            self._account_id, _ = get_local_database().get_or_create_tiktok_account(username)
        except Exception as e:
            logger.warning(f"Minimum follow age ignored: could not resolve @{username} ({e})")
            self._account_id = None
        return self._account_id

    def _resolve_username(self, button_elem) -> Optional[str]:
        """Try to find the username associated with a Following/Friends button."""
        try:
            btn_bounds = button_elem.bounds
            if not btn_bounds:
                return None
            username_elems = []
            for sel in self._selectors.follower_username:
                username_elems = self.device.xpath(sel).all()
                if username_elems:
                    break
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
