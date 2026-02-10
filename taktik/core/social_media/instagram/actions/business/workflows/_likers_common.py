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

from ...core.base_business_action import BaseBusinessAction
from ..common.database_helpers import DatabaseHelpers


class LikersWorkflowBase(BaseBusinessAction):
    """Base class for workflows that interact with profiles from a likers popup."""

    # Sélecteurs pour le bouton back d'Instagram
    _back_button_selectors = [
        '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
        '//android.widget.ImageView[@content-desc="Retour"]',
        '//android.widget.ImageView[@content-desc="Back"]',
        '//*[@content-desc="Retour"]',
        '//*[@content-desc="Back"]'
    ]

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

                # Get profile info
                profile_data = self.profile_business.get_complete_profile_info(
                    username=username, navigate_if_needed=False
                )

                if not profile_data:
                    self.logger.warning(f"Could not get profile data for @{username}")
                    if not self._ensure_on_likers_popup(force_back=True):
                        self.logger.error("Could not recover to likers popup, stopping")
                        break
                    stats['errors'] += 1
                    continue

                # Check private
                if profile_data.get('is_private', False):
                    self.logger.info(f"🔒 Private profile @{username} - skipped")
                    stats['skipped'] += 1
                    self.stats_manager.increment('private_profiles')
                    DatabaseHelpers.record_filtered_profile(
                        username=username,
                        reason='Private profile',
                        source_type=source_type,
                        source_name=source_name,
                        account_id=account_id,
                        session_id=session_id
                    )
                    if not self._ensure_on_likers_popup(force_back=True):
                        self.logger.error("Could not recover to likers popup, stopping")
                        break
                    continue

                # Apply filters
                filter_criteria = effective_config.get('filter_criteria', {})
                filter_result = self.filtering_business.apply_comprehensive_filter(
                    profile_data, filter_criteria
                )

                if not filter_result.get('suitable', False):
                    reasons = filter_result.get('reasons', [])
                    self.logger.info(f"🚫 @{username} filtered: {', '.join(reasons)}")
                    stats['profiles_filtered'] += 1
                    self.stats_manager.increment('profiles_filtered')
                    DatabaseHelpers.record_filtered_profile(
                        username=username,
                        reason=', '.join(reasons),
                        source_type=source_type,
                        source_name=source_name,
                        account_id=account_id,
                        session_id=session_id
                    )
                    if not self._ensure_on_likers_popup(force_back=True):
                        self.logger.error("Could not recover to likers popup, stopping")
                        break
                    continue

                # === PERFORM INTERACTIONS ===
                interaction_result = self._perform_likers_interactions(
                    username, effective_config, profile_data=profile_data
                )

                if interaction_result and interaction_result.get('actually_interacted', False):
                    stats['users_interacted'] += 1
                    stats['likes_made'] += interaction_result.get('likes', 0)
                    stats['follows_made'] += interaction_result.get('follows', 0)
                    stats['comments_made'] += interaction_result.get('comments', 0)
                    stats['stories_watched'] += interaction_result.get('stories', 0)
                    stats['stories_liked'] += interaction_result.get('stories_liked', 0)

                    DatabaseHelpers.mark_profile_as_processed(
                        username, source_name, account_id, session_id
                    )

                    self.logger.success(f"✅ Successful interaction with @{username}")
                    self.stats_manager.increment('profiles_visited')
                    self.stats_manager.increment('profiles_interacted')

                    if interaction_result.get('likes', 0) > 0:
                        self.stats_manager.increment('likes', interaction_result['likes'])
                    if interaction_result.get('follows', 0) > 0:
                        self.stats_manager.increment('follows', interaction_result['follows'])
                        DatabaseHelpers.record_individual_actions(
                            username, 'FOLLOW', interaction_result['follows'],
                            account_id, session_id
                        )
                    if interaction_result.get('stories', 0) > 0:
                        self.stats_manager.increment('stories_watched', interaction_result['stories'])
                    if interaction_result.get('stories_liked', 0) > 0:
                        self.stats_manager.increment('stories_liked', interaction_result['stories_liked'])

                    self.stats_manager.display_stats(current_profile=username)
                else:
                    self.logger.debug(f"@{username} visited but no interaction (probability)")
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

    # ─── Perform interactions on a single profile ────────────────────────

    def _perform_likers_interactions(
        self,
        username: str,
        config: Dict[str, Any],
        profile_data: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Perform interactions (like, follow, story, comment) on a profile.
        Shared by hashtag and post_url workflows.
        """
        result = {
            'likes': 0,
            'follows': 0,
            'comments': 0,
            'stories': 0,
            'stories_liked': 0,
            'actually_interacted': False
        }

        try:
            interactions_to_do = self._determine_interactions_from_config(config)
            self.logger.debug(f"🎯 Planned interactions for @{username}: {interactions_to_do}")

            # Like posts
            should_like = 'like' in interactions_to_do
            should_comment = 'comment' in interactions_to_do

            if should_like or should_comment:
                likes_result = self.like_business.like_profile_posts(
                    username,
                    max_likes=config.get('max_likes_per_profile', 3),
                    config={'randomize_order': True},
                    should_comment=should_comment,
                    custom_comments=config.get('custom_comments', []),
                    comment_template_category=config.get('comment_template_category', 'generic'),
                    max_comments=config.get('max_comments_per_profile', 1),
                    navigate_to_profile=False,
                    profile_data=profile_data,
                    should_like=should_like
                )
                if likes_result:
                    result['likes'] = likes_result.get('posts_liked', 0)
                    result['comments'] = likes_result.get('posts_commented', 0)
                    if result['likes'] > 0 or result['comments'] > 0:
                        result['actually_interacted'] = True

            # Follow
            if 'follow' in interactions_to_do:
                if self.click_actions.click_follow_button():
                    result['follows'] = 1
                    result['actually_interacted'] = True
                    self.logger.info(f"✅ Followed @{username}")

            # Watch stories
            if 'story' in interactions_to_do or 'story_like' in interactions_to_do:
                should_like_story = 'story_like' in interactions_to_do
                story_result = self.story_business.watch_user_stories(
                    username,
                    max_stories=config.get('max_stories_per_profile', 3),
                    should_like=should_like_story,
                    navigate_to_profile=False
                )
                if story_result:
                    result['stories'] = story_result.get('stories_watched', 0)
                    result['stories_liked'] = story_result.get('stories_liked', 0)
                    if result['stories'] > 0:
                        result['actually_interacted'] = True

            return result

        except Exception as e:
            self.logger.error(f"Error performing interactions on @{username}: {e}")
            return result

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
            for selector in self._back_button_selectors[:3]:
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
        """Go back to the likers list using Instagram's back button."""
        try:
            clicked = False
            for selector in self._back_button_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element.click()
                        self.logger.debug("⬅️ Clicked Instagram back button")
                        self._human_like_delay('click')
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                self.logger.debug("⬅️ Using system back button (fallback)")
                self.device.press('back')
                self._human_like_delay('click')

            time.sleep(0.5)
            if self._is_likers_popup_open():
                self.logger.debug("✅ Back to likers list confirmed")
                return True
            else:
                self.logger.warning("⚠️ Back clicked but not on likers list")
                return False

        except Exception as e:
            self.logger.error(f"Error going back: {e}")
            self.device.press('back')
            self._human_like_delay('click')
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
