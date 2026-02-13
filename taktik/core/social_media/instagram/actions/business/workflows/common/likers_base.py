"""Shared base class for workflows that interact with likers from a popup list.

Used by HashtagBusiness and PostUrlBusiness — both follow the same pattern:
1. Open a likers popup (from a post)
2. Iterate visible likers: click → visit profile → filter → interact → back
3. Scroll for more likers

This avoids ~300 lines of duplicated code between hashtag.py and post_url.py.
"""

import time
from typing import Dict, Any, Optional, List, Set
from loguru import logger

from ....core.base_business import BaseBusinessAction
from ....core.base_business.profile_processing import ProfileProcessingResult
from ...common.database_helpers import DatabaseHelpers


class LikersWorkflowBase(BaseBusinessAction):
    """Base class for workflows that interact with profiles from a likers popup."""

    # ─── Main interaction loop ───────────────────────────────────────────

    def _interact_with_likers_list(
        self,
        stats: Dict[str, Any],
        effective_config: Dict[str, Any],
        max_interactions: int,
        source_type: str,
        source_name: str,
        max_scroll_attempts: int = 50,
    ) -> None:
        """
        Shared interaction loop for likers popup workflows.

        Iterates visible likers, clicks each one, visits profile, applies filters,
        performs interactions, and returns to the likers list.

        Args:
            stats: Mutable stats dict (updated in place)
            effective_config: Merged workflow config
            max_interactions: Target number of successful interactions
            source_type: 'HASHTAG' or 'POST_URL' (for DB recording)
            source_name: e.g. '#travel' or 'https://instagram.com/p/...'
            max_scroll_attempts: Max scroll attempts before giving up
        """
        processed_usernames: Set[str] = set()
        scroll_attempts = 0
        account_id = getattr(self.automation, 'active_account_id', None) if self.automation else None
        session_id = getattr(self.automation, 'current_session_id', None) if self.automation else None

        while stats['users_interacted'] < max_interactions and scroll_attempts < max_scroll_attempts:
            # Check session limits
            if self.session_manager:
                should_continue, stop_reason = self.session_manager.should_continue()
                if not should_continue:
                    self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                    break

            # Get visible likers
            visible_likers = self.detection_actions.get_visible_followers_with_elements()

            if not visible_likers:
                self.logger.debug("No visible likers found on screen")
                scroll_attempts += 1
                self._scroll_likers_popup_up()
                self._human_like_delay('scroll')
                continue

            new_likers_found = False

            for liker_data in visible_likers:
                username = liker_data['username']

                if username in processed_usernames:
                    continue

                processed_usernames.add(username)
                new_likers_found = True
                stats['users_found'] += 1

                # DB skip check
                should_skip, skip_reason = DatabaseHelpers.is_profile_skippable(
                    username, account_id, hours_limit=24 * 60
                )
                if should_skip:
                    if skip_reason == "already_processed":
                        self.logger.info(f"🔄 @{username} already processed")
                    elif skip_reason == "already_filtered":
                        self.logger.info(f"🚫 @{username} already filtered")
                        stats['profiles_filtered'] += 1
                    stats['skipped'] += 1
                    self.stats_manager.increment('skipped')
                    continue

                # Click on profile
                self.logger.info(
                    f"[{stats['users_interacted']}/{max_interactions}] 👆 Clicking on @{username}"
                )

                if not self.detection_actions.click_follower_in_list(username):
                    self.logger.warning(f"Could not click on @{username}")
                    stats['errors'] += 1
                    continue

                self._human_like_delay('click')

                # Verify profile screen
                if not self.detection_actions.is_on_profile_screen():
                    self.logger.warning(f"Not on profile screen after clicking @{username}")
                    if not self._ensure_on_likers_popup():
                        self.logger.error("Could not recover to likers popup, stopping")
                        break
                    stats['errors'] += 1
                    continue

                # === UNIFIED PROFILE PROCESSING ===
                result = self._process_profile_on_screen(
                    username, effective_config,
                    source_type=source_type, source_name=source_name,
                    account_id=account_id, session_id=session_id
                )

                if result.was_error:
                    stats['errors'] += 1
                    if not self._ensure_on_likers_popup(force_back=True):
                        self.logger.error("Could not recover to likers popup, stopping")
                        break
                    continue

                if result.was_private:
                    stats['skipped'] += 1
                    if not self._ensure_on_likers_popup(force_back=True):
                        self.logger.error("Could not recover to likers popup, stopping")
                        break
                    continue

                if result.was_filtered:
                    stats['profiles_filtered'] += 1
                    if not self._ensure_on_likers_popup(force_back=True):
                        self.logger.error("Could not recover to likers popup, stopping")
                        break
                    continue

                if result.actually_interacted:
                    stats['users_interacted'] += 1
                    stats['likes_made'] += result.likes
                    stats['follows_made'] += result.follows
                    stats['comments_made'] += result.comments
                    stats['stories_watched'] += result.stories
                    stats['stories_liked'] += result.stories_liked

                    self._update_stats_from_interaction_result(
                        username, result.interaction_result, account_id, session_id
                    )
                    self.stats_manager.display_stats(current_profile=username)
                else:
                    stats['skipped'] += 1

                # Return to likers list
                if not self._ensure_on_likers_popup(force_back=True):
                    self.logger.error("Could not return to likers popup, stopping")
                    break

                # Check if target reached
                if stats['users_interacted'] >= max_interactions:
                    self.logger.info(
                        f"✅ Reached target of {max_interactions} successful interactions"
                    )
                    break

                self._human_like_delay('interaction_gap')

            # Scroll if no new likers found
            if not new_likers_found:
                scroll_attempts += 1
                self._scroll_likers_popup_up()
                self._human_like_delay('scroll')
            else:
                scroll_attempts = 0

    # ─── Liker extraction from current post ─────────────────────────────

    def _extract_likers_from_current_post(self, is_reel: bool = None, max_interactions: int = None) -> list:
        """Extract likers from the currently displayed post (regular or reel).
        Shared by HashtagBusiness and PostUrlBusiness."""
        try:
            if is_reel is None:
                is_reel = self._is_reel_post()

            if is_reel:
                self.logger.debug("Reel post detected")
                return self._extract_likers_from_reel(max_interactions=max_interactions)
            else:
                self.logger.debug("Regular post detected")
                return self._extract_likers_from_regular_post(max_interactions=max_interactions)

        except Exception as e:
            self.logger.error(f"Error extracting likers: {e}")
            return []

    # ─── Perform interactions on a single profile ────────────────────────

    def _perform_likers_interactions(
        self,
        username: str,
        config: Dict[str, Any],
        profile_data: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Perform interactions (like, follow, story, comment) on a profile.
        Delegates to unified _perform_interactions_on_profile (BaseBusinessAction).
        """
        return self._perform_interactions_on_profile(username, config, profile_data=profile_data)

    # ─── Likers popup navigation helpers ─────────────────────────────────

    def _open_likers_popup(self, is_reel: bool = False) -> bool:
        """Open the likers popup of the current post."""
        try:
            like_count_element = self._find_like_count_element()

            if not like_count_element:
                self.logger.warning("⚠️ No like counter found - post may not have visible like count")
                return False

            like_count_element.click()
            self._human_like_delay('click')
            time.sleep(1.5)

            # Check if we accidentally opened comments instead of likers
            if self._is_comments_view_open():
                self.logger.warning("⚠️ Opened comments view instead of likers popup - closing and aborting")
                self._close_comments_view()
                return False

            if self._is_likers_popup_open():
                post_type = "reel" if is_reel else "post"
                self.logger.info(f"✅ Likers popup opened ({post_type})")
                return True

            self.logger.error("❌ Could not open likers popup")
            return False

        except Exception as e:
            self.logger.error(f"Error opening likers popup: {e}")
            return False

    def _close_comments_view(self) -> bool:
        """Close comments view if accidentally opened."""
        try:
            for selector in self.navigation_selectors.back_buttons[:3]:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element.click()
                        time.sleep(0.5)
                        if not self._is_comments_view_open():
                            self.logger.debug("✅ Comments view closed")
                            return True
                except:
                    continue

            self.device.press('back')
            time.sleep(0.5)
            return not self._is_comments_view_open()
        except Exception as e:
            self.logger.debug(f"Error closing comments view: {e}")
            return False

    def _go_back_to_likers_list(self) -> bool:
        """Go back to the likers list using Instagram's UI back button."""
        try:
            # Fast path: combined XPath to find any back button in 1 round-trip
            back_selectors = self.navigation_selectors.back_buttons
            combined = ' | '.join(back_selectors[:5])  # Top 5 most reliable
            try:
                element = self.device.xpath(combined)
                if element.exists:
                    element.click()
                    self.logger.debug("⬅️ Clicked Instagram back button")
                    self._human_like_delay('click')
                else:
                    # Fallback: system back (some devices may not support it)
                    self.logger.debug("⬅️ No UI back button found, using system back (fallback)")
                    self.device.press('back')
                    self._human_like_delay('click')
            except Exception:
                self.device.press('back')
                self._human_like_delay('click')

            if self._is_likers_popup_open():
                self.logger.debug("✅ Back to likers list confirmed")
                return True
            else:
                self.logger.warning("⚠️ Back clicked but not on likers list")
                return False

        except Exception as e:
            self.logger.error(f"Error going back: {e}")
            return False

    def _ensure_on_likers_popup(self, force_back: bool = False) -> bool:
        """
        Ensure we're on the likers popup. Tries up to 3 back presses.

        Args:
            force_back: If True, always press back first (use after visiting a profile)
        """
        if not force_back and self._is_likers_popup_open():
            return True

        for attempt in range(3):
            self.logger.debug(f"🔙 Back attempt {attempt + 1}/3 to return to likers popup")
            if self._go_back_to_likers_list():
                return True
            time.sleep(0.5)

        self.logger.error("❌ Could not return to likers popup after 3 attempts")
        return False

    def _scroll_likers_popup_up(self) -> bool:
        """Scroll the likers popup up to reveal more likers."""
        return self.ui_extractors.scroll_likers_popup_up(
            logger_instance=self.logger,
            is_likers_popup_open_checker=self._is_likers_popup_open,
            verbose_logs=False
        )

    def _find_like_count_element(self):
        """Find the like count element on the current post."""
        return self.ui_extractors.find_like_count_element(logger_instance=self.logger)
