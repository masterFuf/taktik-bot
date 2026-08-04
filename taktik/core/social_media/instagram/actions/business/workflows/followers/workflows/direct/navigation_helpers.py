"""Navigation and recovery helpers for the direct followers workflow."""

import time
import json
from typing import Dict, Any, Optional


class DirectNavigationMixin:
    """Mixin: setup, recovery, empty screen handling, scroll/end detection."""

    # A fling only produces travel once the rows it is flinging exist. On a slow phone the
    # list is still loading, so the gesture lands on nothing and the workflow would believe
    # it moved when it did not. Both numbers below bound the WAIT, never the run: at worst
    # the transport stops early and the normal scan resumes where it stands.
    _TRANSPORT_SETTLE_POLL_S = 0.3
    _TRANSPORT_SETTLE_BUDGET_S = 4.0

    def _visible_usernames_now(self):
        """Snapshot of what the list shows, used to tell real travel from a fling into a
        not-yet-loaded list. Empty is a legitimate answer here (still loading)."""
        try:
            return [f['username'] for f in self.detection_actions.get_visible_followers_with_elements()]
        except Exception:
            return []

    def _wait_for_list_to_settle(self, before):
        """Wait — briefly, and never blocking — until the list shows something DIFFERENT.

        Returns True as soon as the content changed. Returns False when the budget runs out,
        which the caller must treat as "stop transporting", not as an error: an unchanged
        screen after a fling means either the list has not loaded or we reached its end, and
        both are answered the same way — stop here and resume the normal scan.
        """
        waited = 0.0
        while waited < self._TRANSPORT_SETTLE_BUDGET_S:
            time.sleep(self._TRANSPORT_SETTLE_POLL_S)
            waited += self._TRANSPORT_SETTLE_POLL_S
            now = self._visible_usernames_now()
            if now and now != before:
                return True
        return False

    def _escape_private_zone(self, policy, jumps_done, source_followers=None):
        """Transport the list past a run of private profiles. Returns the gestures that
        actually moved something.

        A flagged account is served its private followers FIRST (rho = +0.12 between two
        accounts on the same source, private profiles shifted -0.63 against +0.08 for public
        ones, p = 0.0015). The rate of private profiles is unchanged — only their position —
        so the session budget burns in a head of list it was handed. This walks out of it.

        Each gesture is confirmed before the next: without that, a burst of flings on a slow
        connection scrolls a list that has not loaded, moves nothing, and leaves the workflow
        interacting where it believes it is rather than where it is.
        """
        planned = policy.flings_for_jump(jumps_done, source_followers)
        self.logger.warning(
            f"🚧 Private zone: transporting past it ({planned} flings, jump {jumps_done + 1}/{policy.max_jumps})"
        )

        effective = 0
        for _ in range(planned):
            before = self._visible_usernames_now()
            self.scroll_actions.scroll_followers_list_fling()
            if not self._wait_for_list_to_settle(before):
                self.logger.info("🚧 List stopped moving (loading or end of list) — ending transport here")
                break
            effective += 1

        self.logger.info(f"🚧 Transport done: {effective}/{planned} gestures moved the list")
        return effective

    def _setup_direct_workflow(self, target_username, stats, config, deep_link_percentage, force_search_for_target):
        """Navigate to target profile, open followers/following list. Returns (followers_count, profile_info) or (None, None) on failure."""
        self.logger.info(f"🎯 Opening followers list of @{target_username}")
        
        if not self.nav_actions.navigate_to_profile(
            target_username, 
            deep_link_usage_percentage=deep_link_percentage,
            force_search=force_search_for_target
        ):
            self.logger.error(f"Failed to navigate to @{target_username}")
            return None, None
        
        self._human_like_delay('click')
        
        profile_info = self.profile_business.get_complete_profile_info(target_username, navigate_if_needed=False)
        
        if profile_info and profile_info.get('is_private', False):
            self.logger.warning(f"@{target_username} is a private account")
            return None, None
        
        target_followers_count = profile_info.get('followers_count', 0) if profile_info else 0
        
        if target_followers_count > 0:
            self.logger.info(f"📊 Target @{target_username} has {target_followers_count:,} followers")
        else:
            self.logger.warning(f"⚠️ Could not get followers count for @{target_username}")
        
        # Emit IPC message for frontend
        try:
            target_msg = {
                "type": "target_account",
                "username": target_username,
                "followers": target_followers_count,
                "following": profile_info.get('following_count', 0) if profile_info else 0,
                "posts": profile_info.get('media_count', 0) if profile_info else 0,
            }
            print(json.dumps(target_msg), flush=True)
        except Exception:
            pass
        
        # Ouvrir la liste des followers OU following selon interaction_type
        interaction_type = config.get('interaction_type', 'followers')
        
        if interaction_type == 'following':
            self.logger.info(f"📋 Opening FOLLOWING list of @{target_username}")
            if not self.nav_actions.open_following_list():
                self.logger.error("Failed to open following list")
                return None, None
        else:
            self.logger.info(f"📋 Opening FOLLOWERS list of @{target_username}")
            if not self.nav_actions.open_followers_list():
                self.logger.error("Failed to open followers list")
                return None, None
        
        self._human_like_delay('click')
        return target_followers_count, profile_info

    def _recover_after_break(self, target_username, deep_link_percentage, force_search_for_target, total_usernames_seen):
        """Try to recover to followers list after a break."""
        if not self.detection_actions.is_followers_list_open():
            self.logger.warning("⚠️ Not on followers list after break, trying to recover...")
            
            recovered = False
            for back_attempt in range(3):
                self.logger.debug(f"🔙 Back attempt {back_attempt + 1}/3")
                if self._go_back_to_list():
                    self._human_like_delay('navigation')
                    if self.detection_actions.is_followers_list_open():
                        self.logger.info("✅ Recovered to followers list via back button")
                        recovered = True
                        break
            
            if not recovered:
                self.logger.warning("⚠️ Could not recover via back, navigating to target (will restart from beginning)")
                if not self.nav_actions.navigate_to_profile(
                    target_username,
                    deep_link_usage_percentage=deep_link_percentage,
                    force_search=force_search_for_target
                ):
                    self.logger.error("Could not navigate back to target profile")
                    return False
                if not self.nav_actions.open_followers_list():
                    self.logger.error("Could not reopen followers list")
                    return False
                self._human_like_delay('navigation')
                self.logger.warning(f"⚠️ Position lost - restarting from beginning (was at {total_usernames_seen} usernames)")
        return True

    def _handle_empty_followers_screen(self, scroll_detector):
        """Handle case when no visible followers found. Returns True if should break."""
        self.logger.debug("No visible followers found on screen")
        
        # Vérifier si on est dans la section suggestions
        if self.detection_actions.is_in_suggestions_section():
            self.logger.info("📋 Reached suggestions section - checking for 'See more' button")
            
            if scroll_detector.click_load_more_if_present():
                self._human_like_delay('load_more')
                time.sleep(1.5)
                return False  # continue
            else:
                self.logger.debug("No 'See more' button found, trying a small scroll...")
                self.scroll_actions.scroll_followers_list_down()
                self._human_like_delay('scroll')
                
                if scroll_detector.click_load_more_if_present():
                    self._human_like_delay('load_more')
                    time.sleep(1.5)
                    return False  # continue
                
                self.logger.info("🏁 No more real followers to load - end of list")
                return True  # break
        
        if scroll_detector.click_load_more_if_present():
            self._human_like_delay('load_more')
            return False  # continue
        
        if scroll_detector.is_the_end():
            self.logger.info("🏁 End of followers list detected")
            return True  # break
        
        load_more_result = self.scroll_actions.check_and_click_load_more()
        if load_more_result is True:
            self.logger.info("✅ 'Voir plus' clicked (no visible followers) - loading more real followers")
            self._human_like_delay('load_more')
            time.sleep(1.0)
            return False  # continue
        elif load_more_result is False:
            self.logger.info("🏁 End of followers list detected (suggestions section)")
            return True  # break
        
        return False  # continue (will scroll in caller)

    def _handle_scroll_and_end_detection(
        self, new_usernames_found, no_new_profiles_count, total_usernames_seen,
        target_followers_count, scroll_detector, tracker, scroll_attempts,
        new_profiles_to_interact, did_interact_this_iteration,
        stats, max_interactions, known_usernames_streak,
        max_consecutive_known_usernames, legacy_max_no_new_usernames_scrolls
    ):
        """
        Handle end-of-list detection when no new usernames found.
        
        Returns:
            (should_stop: bool, stop_reason: str or None)
        """
        if (
            max_consecutive_known_usernames is not None
            and known_usernames_streak >= max_consecutive_known_usernames
        ):
            reason = (
                f"No new followers after {max_consecutive_known_usernames} known usernames in a row "
                f"({total_usernames_seen} seen)"
            )
            self.logger.info(
                f"🏁 No new followers discovered after {max_consecutive_known_usernames} known usernames in a row "
                f"(seen {total_usernames_seen:,} usernames)"
            )
            return True, reason

        if new_usernames_found > 0:
            return False, None
        
        # No new usernames found
        remaining_followers = target_followers_count - total_usernames_seen if target_followers_count > 0 else float('inf')
        if legacy_max_no_new_usernames_scrolls is not None:
            self.logger.debug(
                f"⚠️ No new usernames found ({no_new_profiles_count}/{legacy_max_no_new_usernames_scrolls}) - "
                f"{total_usernames_seen} seen, ~{remaining_followers:,.0f} remaining"
            )
        else:
            self.logger.debug(
                f"⚠️ No new usernames found on this page - {total_usernames_seen} seen, "
                f"~{remaining_followers:,.0f} remaining"
            )
        
        # Vérifier bouton "Voir plus"
        if scroll_detector.click_load_more_if_present():
            self._human_like_delay('load_more')
            return False, None
        
        # Conditions pour arrêter
        if target_followers_count > 0 and total_usernames_seen >= target_followers_count * 0.95:
            reason = f"End of followers list ({total_usernames_seen:,}/{target_followers_count:,} seen)"
            self.logger.info(f"🏁 Reached end of list: seen {total_usernames_seen:,}/{target_followers_count:,} followers (~95%)")
            return True, reason
        
        if scroll_detector.is_the_end():
            reason = f"No new followers found ({total_usernames_seen} profiles seen)"
            self.logger.info("🏁 ScrollEndDetector: end of list reached")
            return True, reason
        
        if tracker.is_end_of_list():
            reason = f"End of followers list (same profiles repeated)"
            self.logger.info("🏁 Tracker: same followers seen multiple times - end of list")
            return True, reason
        
        if (
            legacy_max_no_new_usernames_scrolls is not None
            and no_new_profiles_count >= legacy_max_no_new_usernames_scrolls
        ):
            reason = (
                f"No new followers after {legacy_max_no_new_usernames_scrolls} scroll attempts "
                f"({total_usernames_seen} seen)"
            )
            self.logger.info(
                f"🏁 No new usernames found after {legacy_max_no_new_usernames_scrolls} attempts "
                f"(seen {total_usernames_seen:,} usernames)"
            )
            return True, reason
        
        coverage_log_threshold = (
            max(1, legacy_max_no_new_usernames_scrolls // 2)
            if legacy_max_no_new_usernames_scrolls is not None
            else None
        )
        if coverage_log_threshold is not None and no_new_profiles_count >= coverage_log_threshold:
            if target_followers_count > 0:
                coverage = (total_usernames_seen / target_followers_count) * 100
                self.logger.debug(f"📊 {coverage:.1f}% coverage ({total_usernames_seen:,}/{target_followers_count:,}), continuing...")
        
        # Check "Voir plus" button
        load_more_result = self.scroll_actions.check_and_click_load_more()
        if load_more_result is True:
            self.logger.info("✅ 'Voir plus' clicked (no new usernames) - loading more real followers")
            self._human_like_delay('load_more')
            time.sleep(1.0)
            return False, None
        elif load_more_result is False:
            self.logger.info("🏁 End of followers list detected (suggestions section)")
            return True, "End of followers list (suggestions section)"
        
        return False, None
