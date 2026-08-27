"""Navigation and recovery helpers for the direct followers workflow."""

import time
import json
from taktik.core.shared.diagnostics import capture_screen_snapshot
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons
from typing import Dict, Any, Optional

from taktik.core.shared.telemetry import emit_step
from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter


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

    def _record_restriction_signal(self, account_username, source_name, source_followers,
                                   streak, encounter_order, jump_index, gestures):
        """Persist one detection. Never raises — losing a measurement must not lose the run."""
        if not account_username or account_username == "unknown":
            return
        try:
            # Through the service's repository, like every other bot write — never a
            # connection opened on the side (AGENTS.md: no direct SQL in a workflow).
            from taktik.core.database.local.service import LocalDatabaseService

            LocalDatabaseService().account_restrictions.record_signal(
                account_username,
                platform="instagram",
                source_type="FOLLOWERS",
                source_name=source_name,
                source_followers=source_followers,
                streak=streak,
                encounter_order=encounter_order,
                jump_index=jump_index,
                gestures=gestures,
                session_id=self._get_session_id() if hasattr(self, "_get_session_id") else None,
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.debug(f"Could not persist restriction signal: {exc}")

    def _transport_out_of_private_zone(self, policy, private_streak, jumps_done,
                                       target_username, source_followers,
                                       account_username, encounter_order, tracker) -> int:
        """Announce, fling, and record one escape out of a private zone.

        Everything the transport DOES lives here; what the loop must forget afterwards
        stays with the loop, because those resets are the fragile half and belong where a
        reader of the loop can see them.

        The detection is persisted, not just reacted to: this reordering is the only
        observable symptom we have of Instagram flagging the account, so each occurrence is
        a dated measurement of that account's standing — since when, how often, on which
        sources, and when it STOPS, which reads as detections ceasing on runs that used to
        produce them.

        Returns the number of gestures that actually moved the list, which the caller adds
        to its scroll budget.
        """
        jump = jumps_done + 1
        emit_step("private_zone_escape", action="transport_start",
                  streak=private_streak, jump=jump,
                  source_type="FOLLOWERS", target=target_username)
        IPCEmitter.emit_action('private_zone_escape', target_username, {
            'streak': private_streak,
            'jump': jump,
            'max_jumps': policy.max_jumps,
            'source_followers': source_followers,
        })

        moved = self._escape_private_zone(policy, jumps_done, source_followers)

        self._record_restriction_signal(
            account_username=account_username,
            source_name=target_username,
            source_followers=source_followers,
            streak=policy.threshold,
            encounter_order=encounter_order,
            jump_index=jump,
            gestures=moved,
        )

        tracker.log_scroll("private_zone_transport")
        emit_step("private_zone_escape", action="transport_done",
                  gestures=moved, jump=jump,
                  source_type="FOLLOWERS", target=target_username)
        return moved

    def _escape_private_zone(self, policy, jumps_done, source_followers=None):
        """Transport the list past a run of private profiles. Returns the gestures that
        actually moved something.

        An affected account is served its private profiles first. Their overall rate is
        unchanged — only their position — so the session budget burns in a head of list it
        was handed. This walks out of it.

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

    def _fail_setup(self, stats, reason, label):
        """Record WHY the setup gave up, and keep the screen that explains it.

        A setup failure used to return a bare `(None, None)`: the caller returned at once, no motive
        was ever set, and the driver concluded `completed (0 interactions)` — a run that never
        managed to open a single list was filed exactly like one that did its whole job. Two such
        runs in one evening, both reported as successes.
        """
        stats['stop_reason'] = reason
        capture_screen_snapshot(self.device, label)
        return None, None

    def _setup_direct_workflow(self, target_username, stats, config, deep_link_percentage, force_search_for_target):
        """Navigate to target profile, open followers/following list. Returns (followers_count, profile_info) or (None, None) on failure."""
        self.logger.info(f"🎯 Opening followers list of @{target_username}")
        
        if not self.nav_actions.navigate_to_profile(
            target_username, 
            deep_link_usage_percentage=deep_link_percentage,
            force_search=force_search_for_target
        ):
            self.logger.error(f"Failed to navigate to @{target_username}")
            return self._fail_setup(stats, stop_reasons.navigation_lost(), 'setup_navigation_failed')
        
        self._human_like_delay('click')
        
        profile_info = self.profile_business.get_complete_profile_info(target_username, navigate_if_needed=False)
        
        if profile_info and profile_info.get('is_private', False):
            self.logger.warning(f"@{target_username} is a private account")
            # NOT a technical failure: a private target has no list to open. The operator has to
            # pick another source, which is a different action from "go and look at the phone".
            stats['stop_reason'] = stop_reasons.list_unavailable()
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
        
        # Open the followers OR the following list, depending on the interaction type
        interaction_type = config.get('interaction_type', 'followers')
        
        if interaction_type == 'following':
            self.logger.info(f"📋 Opening FOLLOWING list of @{target_username}")
            if not self.nav_actions.open_following_list():
                self.logger.error("Failed to open following list")
                return self._fail_setup(stats, stop_reasons.list_unavailable(), 'setup_following_list_unavailable')
        else:
            self.logger.info(f"📋 Opening FOLLOWERS list of @{target_username}")
            if not self.nav_actions.open_followers_list():
                self.logger.error("Failed to open followers list")
                return self._fail_setup(stats, stop_reasons.list_unavailable(), 'setup_followers_list_unavailable')
        
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

    def _handle_empty_followers_screen(self, scroll_detector, total_usernames_seen=0):
        """Handle case when no visible followers found.

        Returns the reason to STOP on, or None to carry on. It used to return a bare bool,
        so the three ways out of here reached the caller stripped of what they knew, the loop
        broke with no motive set, and the run was filed `completed` — the fallback of a silent
        exit. Thirteen runs of one account in a week, every one reported as a job done.
        """
        self.logger.debug("No visible followers found on screen")
        
        # Are we in the suggestions section?
        if self.detection_actions.is_in_suggestions_section():
            self.logger.info("📋 Reached suggestions section - checking for 'See more' button")
            
            if scroll_detector.click_load_more_if_present():
                self._human_like_delay('load_more')
                time.sleep(1.5)
                return None  # continue
            else:
                self.logger.debug("No 'See more' button found, trying a small scroll...")
                self.scroll_actions.scroll_followers_list_down()
                self._human_like_delay('scroll')
                
                if scroll_detector.click_load_more_if_present():
                    self._human_like_delay('load_more')
                    time.sleep(1.5)
                    return None  # continue

                # READ the screen that rescue scroll produced before concluding. This door
                # used to break on ONE empty scan without ever looking again — while the main
                # loop needs four consecutive empty scans to call a list gone. A scan that
                # outruns the loading looks exactly like the end of a list, and the run was
                # filed as a completed one: 9 profiles of the 69 allowed, at 11% of the list.
                if self.detection_actions.get_visible_followers_with_elements():
                    self.logger.info("📋 Followers came back after the scroll - not the end of the list")
                    return None  # continue

                self.logger.info("🏁 No more real followers to load - end of list")
                return stop_reasons.end_of_list_suggestions()
        
        if scroll_detector.click_load_more_if_present():
            self._human_like_delay('load_more')
            return None  # continue
        
        if scroll_detector.is_the_end():
            self.logger.info("🏁 End of followers list detected")
            return stop_reasons.no_new_profiles(total_usernames_seen)
        
        load_more_result = self.scroll_actions.check_and_click_load_more()
        if load_more_result is True:
            self.logger.info("✅ 'Voir plus' clicked (no visible followers) - loading more real followers")
            self._human_like_delay('load_more')
            time.sleep(1.0)
            return None  # continue
        elif load_more_result is False:
            self.logger.info("🏁 End of followers list detected (suggestions section)")
            return stop_reasons.end_of_list_suggestions()
        
        return None  # continue (will scroll in caller)

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
            reason = stop_reasons.known_streak(max_consecutive_known_usernames, total_usernames_seen)
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
        
        # Check the load-more button
        if scroll_detector.click_load_more_if_present():
            self._human_like_delay('load_more')
            return False, None
        
        # Stop conditions
        if target_followers_count > 0 and total_usernames_seen >= target_followers_count * 0.95:
            reason = stop_reasons.end_of_list(total_usernames_seen, target_followers_count)
            self.logger.info(f"🏁 Reached end of list: seen {total_usernames_seen:,}/{target_followers_count:,} followers (~95%)")
            return True, reason
        
        if scroll_detector.is_the_end():
            reason = stop_reasons.no_new_profiles(total_usernames_seen)
            self.logger.info("🏁 ScrollEndDetector: end of list reached")
            return True, reason
        
        if tracker.is_end_of_list():
            reason = stop_reasons.end_of_list_repeated()
            self.logger.info("🏁 Tracker: same followers seen multiple times - end of list")
            return True, reason
        
        if (
            legacy_max_no_new_usernames_scrolls is not None
            and no_new_profiles_count >= legacy_max_no_new_usernames_scrolls
        ):
            reason = stop_reasons.scroll_streak(legacy_max_no_new_usernames_scrolls, total_usernames_seen)
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
            return True, stop_reasons.end_of_list_suggestions()
        
        return False, None
