"""Main interaction loop for the direct followers workflow."""

import time
from typing import Dict, Any
from taktik.core.shared.diagnostics import capture_screen_snapshot

from ......core.stats import create_workflow_stats, sync_aliases
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.shared.telemetry import emit_step
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons
from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter
from ....common.revisit_policy import RevisitPolicy
from ....common.private_streak_policy import PrivateStreakPolicy
from ....common.followers_tracker import FollowersTracker
from ....common.interaction_config import build_interaction_config
from ....common.stop_limits import resolve_stop_limits
from ....common.list_reload_policy import ListReloadPolicy
from .navigation_helpers import DirectNavigationMixin
from .profile_processing import DirectProfileProcessingMixin


class FollowerDirectWorkflowMixin(DirectNavigationMixin, DirectProfileProcessingMixin):
    """Mixin: interact_with_followers_direct — main workflow using direct clicks."""

    def interact_with_followers_direct(self, target_username: str,
                                       max_interactions: int = 30,
                                       config: Dict[str, Any] = None,
                                       account_id: int = None,
                                       finalize: bool = True) -> Dict[str, Any]:
        """
        Direct interaction from the followers list.
        
        Au lieu de scraper puis naviguer via deep link, on:
        1. open the followers list
        2. for each visible follower: direct tap, interaction, back
        3. scroll only once every visible one is handled
        
        Avantages:
        - no more deep links, which are a recognisable pattern
        - navigation entirely by taps
        - ✅ Comportement humain réaliste
        """
        config = config or {}
        
        stats = create_workflow_stats('followers_direct')
        
        interaction_config = build_interaction_config(config)
        # Operator-set revisit delays (how long an interaction / a stored filter keeps a
        # profile off-limits FOR THIS ACCOUNT). Single owner of the semantic.
        revisit_policy = RevisitPolicy.from_filters(interaction_config['filter_criteria'])
        # Escape hatch for an account served its private followers first. Disarmed on its own
        # when the operator ALLOWS private profiles — nothing is being rejected, so there is no
        # zone to leave.
        private_streak_policy = PrivateStreakPolicy.from_filters(interaction_config['filter_criteria'])

        # Navigation configuration. 0 = go through the SEARCH BAR like a person (and like the
        # hashtag flow already does); the deep link stays available as a fallback inside
        # `navigate_to_profile`. This default used to be 90, and since no config, no config
        # builder and no page ever set the key, 90 was what every target run actually used —
        # an ADB intent to open the target profile.
        deep_link_percentage = config.get('deep_link_percentage', 0)
        force_search_for_target = config.get('force_search_for_target', False)

        stop_limits = resolve_stop_limits(config)
        max_consecutive_known_usernames = stop_limits.max_consecutive_known_usernames
        legacy_max_no_new_usernames_scrolls = stop_limits.legacy_max_no_new_usernames_scrolls

        try:
            # 1. Navigate to the target profile and open the list
            target_followers_count, profile_info = self._setup_direct_workflow(
                target_username, stats, config, deep_link_percentage, force_search_for_target
            )
            if target_followers_count is None:
                # Setup failed. `stats['stop_reason']` carries WHY (set by the setup); returning
                # it is what lets the terminal path file this run as INTERRUPTED instead of
                # "completed with 0 interactions".
                return stats
            
            # Start the interaction phase
            if self.session_manager:
                self.session_manager.start_interaction_phase()
            
            # 3. Boucle principale d'interaction
            processed_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 100
            no_new_profiles_count = 0
            known_usernames_streak = 0
            total_usernames_seen = 0
            
            # Navigation context, to know where we stand
            last_visited_username = None
            next_expected_username = None
            
            # Set up the end-of-scroll detector and the tracker
            scroll_detector = ScrollEndDetector(repeats_to_end=5, device=self.device)
            
            account_username = "unknown"
            if self.automation and hasattr(self.automation, 'active_username') and self.automation.active_username:
                account_username = self.automation.active_username
            tracker = FollowersTracker(account_username, target_username)
            self.logger.info(f"📝 Tracking log: {tracker.get_log_file_path()}")
            
            self.logger.info(f"🚀 Starting direct interactions (max: {max_interactions})")
            
            session_stop_reason = None
            # Consecutive "back at the top of the list" detections WITHOUT progress. Reset on any
            # non-loop scan, so scattered re-tops over a long session don't accumulate into a false
            # stop — only a list genuinely stuck at the top (scrolling never advances) ends it.
            consecutive_top_loops = 0
            # True when we could not recover to the followers list: must end the WHOLE run.
            # The old code only broke the inner for-loop, so the while-loop kept blind-scrolling
            # an unknown screen for minutes (real runs: ~7 min of empty scrolls, non-human bursts)
            # until the global 100-scroll cap finally tripped.
            navigation_lost = False
            # Consecutive scans with NO visible followers. A handful is normal (loading, end of
            # list being handled), but a long streak means the list is gone (e.g. the
            # "Suggestions" screen) — stop instead of scrolling into the void.
            consecutive_empty_screens = 0
            # Consecutive PRIVATE profiles among those actually VISITED. A flagged account is
            # served its private followers first, so a long run of them means we are inside a
            # head of list that was handed to us, not that this source is private-heavy.
            # Skips that never opened a profile (already known, relationship, own/target account)
            # leave this untouched: they say nothing about the zone, and counting them would stop
            # the streak from ever forming on a list we have already worked.
            private_streak = 0
            private_zone_jumps = 0
            # The safety net for a list that has not finished loading. Consulted ONLY where the
            # run is about to stop on a spent source, so a healthy run never waits. `None` means
            # no net has been spent yet; afterwards it holds the interaction count at the time,
            # and a fresh net is earned by interacting again — never by waiting again.
            reload_policy = ListReloadPolicy.from_config(config)
            reload_spent_at = None

            def list_was_only_loading(reason):
                """True if the list came back — the caller must then resume, not stop."""
                nonlocal reload_spent_at, scroll_detector, consecutive_empty_screens
                nonlocal consecutive_top_loops, no_new_profiles_count, known_usernames_streak
                if reload_spent_at is not None and stats['interacted'] <= reload_spent_at:
                    return False
                if not self._list_came_back_after_waiting(
                        reload_policy, reason, total_usernames_seen):
                    return False
                reload_spent_at = stats['interacted']
                # The same gates the private-zone transport clears, for the same reason: they
                # were filled by the screens the outage produced, and reading them now would
                # end the run on evidence that is no longer true.
                consecutive_empty_screens = 0
                consecutive_top_loops = 0
                no_new_profiles_count = 0
                known_usernames_streak = 0
                scroll_detector = ScrollEndDetector(repeats_to_end=5, device=self.device)
                return True

            while stats['interacted'] < max_interactions and scroll_attempts < max_scroll_attempts:
                # Vérifier si on doit prendre une pause
                took_break = self._maybe_take_break()
                
                # After a break, confirm we are still on the followers list
                if took_break:
                    self._recover_after_break(
                        target_username, deep_link_percentage, force_search_for_target, total_usernames_seen
                    )
                
                # Should the session keep running?
                if self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        session_stop_reason = stop_reason
                        break
                
                # Read the visible followers, the real ones only and not the suggestions
                visible_followers = self.detection_actions.get_visible_followers_with_elements()
                
                # Tracker: record the visible followers and detect loops
                if visible_followers:
                    consecutive_empty_screens = 0
                    visible_usernames_for_tracking = [f['username'] for f in visible_followers]
                    loop_detected = tracker.log_visible_followers(visible_usernames_for_tracking, "scan")
                    if loop_detected:
                        # Back at the TOP of the list (visible page ~= the first page seen). NOT a
                        # reason to end the session — a back/recovery just landed us at the top. We
                        # already remember every username seen this session, so the right move is to
                        # SCROLL DOWN past the already-seen region and resume discovery; the loop
                        # clears as soon as we move past the first page. Only stop if we stay stuck at
                        # the top for many CONSECUTIVE scans despite scrolling (genuine cycling).
                        consecutive_top_loops += 1
                        if consecutive_top_loops >= 8:
                            self.logger.error("🛑 Stuck at top of followers list (8 scans, scrolling does not advance) — stopping")
                            session_stop_reason = (
                                session_stop_reason or stop_reasons.stuck_at_top(consecutive_top_loops))
                            break
                        self.logger.info(
                            f"🔄 Back at top of followers list — scrolling past the already-seen region "
                            f"({consecutive_top_loops}/8)"
                        )
                        for _ in range(3):
                            self.scroll_actions.scroll_followers_list_down()
                            self._human_like_delay('scroll')
                            scroll_attempts += 1
                        continue
                    consecutive_top_loops = 0
                
                if not visible_followers:
                    consecutive_empty_screens += 1
                    if consecutive_empty_screens >= 4:
                        # 4 scans in a row with zero followers: the list is gone (suggestions
                        # screen / navigation drift). Blind-scrolling further is pure waste and
                        # a detectable non-human burst.
                        self.logger.error("🛑 Followers list unavailable (4 consecutive empty scans) — ending run")
                        if list_was_only_loading(stop_reasons.list_unavailable()):
                            continue
                        session_stop_reason = session_stop_reason or stop_reasons.list_unavailable()
                        break
                    # Handle end of list, suggestions and scrolling
                    end_reason = self._handle_empty_followers_screen(
                        scroll_detector, total_usernames_seen)
                    if end_reason:
                        if list_was_only_loading(end_reason):
                            continue
                        session_stop_reason = session_stop_reason or end_reason
                        break
                    scroll_attempts += 1
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
                    continue

                new_usernames_found = 0
                new_profiles_to_interact = 0
                did_interact_this_iteration = False
                
                visible_usernames_list = [f['username'] for f in visible_followers]
                
                # Check we are in the right place after coming back from a profile
                if last_visited_username and next_expected_username:
                    position_ok = last_visited_username in visible_usernames_list or next_expected_username in visible_usernames_list
                    tracker.log_position_check(last_visited_username, next_expected_username, visible_usernames_list, position_ok)
                    
                    if position_ok:
                        self.logger.debug(f"✅ Position OK: found @{last_visited_username} or @{next_expected_username} in visible list")
                    else:
                        self.logger.debug(f"⚠️ Position lost: neither @{last_visited_username} nor @{next_expected_username} visible")
                
                for idx, follower_data in enumerate(visible_followers):
                    username = follower_data['username']
                    
                    # Skip when already seen in this session
                    if username in processed_usernames:
                        continue
                    
                    # Skip own account
                    if account_username and account_username != "unknown":
                        if username.lower() == account_username.lower():
                            self.logger.info(f"⏭️ Skipping own account @{username}")
                            processed_usernames.add(username)
                            emit_step("follower_decision", action="skipped", target=username,
                                      reason="own_account", encounter_order=total_usernames_seen + 1,
                                      source_type="FOLLOWERS")
                            continue

                    # Skip target account
                    if target_username and username.lower() == target_username.lower():
                        self.logger.info(f"⏭️ Skipping target account @{username}")
                        processed_usernames.add(username)
                        emit_step("follower_decision", action="skipped", target=username,
                                  reason="target_account", encounter_order=total_usernames_seen + 1,
                                  source_type="FOLLOWERS")
                        continue

                    processed_usernames.add(username)
                    new_usernames_found += 1
                    total_usernames_seen += 1
                    
                    # Already interacted with, or filtered in a PRIOR session?
                    already_known, known_usernames_streak = self._skip_if_already_known(
                        username, account_id, revisit_policy, stats, tracker,
                        total_usernames_seen, known_usernames_streak,
                    )
                    if already_known:
                        continue

                    new_profiles_to_interact += 1
                    
                    # Remember the context BEFORE tapping
                    last_visited_username = username
                    if idx + 1 < len(visible_followers):
                        next_expected_username = visible_followers[idx + 1]['username']
                    else:
                        next_expected_username = None
                    
                    # === INTERACTION DIRECTE ===
                    interaction_ok = self._process_single_follower_direct(
                        username, idx, stats, interaction_config, account_id,
                        target_username, target_followers_count, total_usernames_seen,
                        max_interactions, tracker
                    )
                    
                    if interaction_ok is None:
                        # Critical error — could not recover to list. Flag it so the OUTER loop
                        # ends too (this break only exits the for-loop).
                        emit_step("follower_decision", action="error", target=username,
                                  reason="processing_error", encounter_order=total_usernames_seen,
                                  source_type="FOLLOWERS")
                        navigation_lost = True
                        session_stop_reason = session_stop_reason or stop_reasons.navigation_lost()
                        # Keep the screen we could not read. Without it the next occurrence is as
                        # opaque as this one: the app is closed seconds later and the evidence with it.
                        capture_screen_snapshot(self.device, 'navigation_lost')
                        break

                    # Consecutive-private streak. `None` = no profile was opened, so the visit
                    # says nothing about the zone and the streak is left as it is.
                    if self._last_visit_was_private is True:
                        private_streak += 1
                    elif self._last_visit_was_private is False:
                        private_streak = 0

                    # Outcome ledger: the rich reason (private/filtered/error) is recorded
                    # inside _process_single_follower_direct; here we mark interacted vs not.
                    if interaction_ok:
                        did_interact_this_iteration = True
                        emit_step("follower_decision", action="interacted", target=username,
                                  encounter_order=total_usernames_seen, source_type="FOLLOWERS")
                    else:
                        emit_step("follower_decision", action="not_interacted", target=username,
                                  reason="filtered_or_private", encounter_order=total_usernames_seen,
                                  source_type="FOLLOWERS")
                    
                    # Back to the followers list, with a solid check
                    # force_back=False: _process_single_follower_direct already calls
                    # _ensure_on_followers_list for filtered/private/error cases, so we only
                    # need to force a back when coming from an actual interaction (like/follow)
                    if not self._ensure_on_followers_list(target_username, force_back=False):
                        # "stopping" must mean STOPPING: this break only exits the for-loop, so
                        # without the flag the while-loop kept scrolling a dead screen for minutes.
                        self.logger.error("Could not return to followers list, stopping")
                        navigation_lost = True
                        session_stop_reason = session_stop_reason or stop_reasons.navigation_lost()
                        # Keep the screen we could not read. Without it the next occurrence is as
                        # opaque as this one: the app is closed seconds later and the evidence with it.
                        capture_screen_snapshot(self.device, 'navigation_lost')
                        break
                    
                    # Position check after coming back
                    visible_after_back = self.detection_actions.get_visible_followers_with_elements()
                    if visible_after_back:
                        visible_usernames_after = [f['username'] for f in visible_after_back]
                        position_ok = tracker.check_position_after_back(username, visible_usernames_after)
                        if not position_ok:
                            self.logger.debug(f"⚠️ Position lost after visiting @{username} - may cause loop")
                    
                    self.stats_manager.display_stats(current_profile=username)
                    
                    if stats['interacted'] >= max_interactions:
                        break
                    
                    # After the interaction, scan the list again
                    break

                if navigation_lost:
                    self.logger.error("🛑 Navigation lost — ending run (no blind scrolling on an unknown screen)")
                    break

                # === PRIVATE ZONE ESCAPE ===
                # Enough consecutive private profiles to conclude we are in a head of list that
                # was handed to this account rather than in a private-heavy source. Transport
                # past it instead of spending the whole session budget there.
                if private_streak_policy.should_escape(private_streak, private_zone_jumps):
                    moved = self._transport_out_of_private_zone(
                        private_streak_policy, private_streak, private_zone_jumps,
                        target_username, target_followers_count,
                        account_username, total_usernames_seen, tracker,
                    )
                    private_zone_jumps += 1
                    scroll_attempts += moved

                    # The four gates that would otherwise read a deliberate transport as a fault.
                    # Missing any one of them turns the rescue into the thing that ends the run:
                    #  - empty screens: a fling outruns the loading, and 4 empty scans stop the run
                    #  - top loops:     the landing zone is unknown to the anti-loop check
                    #  - scroll end:    a large jump looks exactly like reaching the bottom
                    #  - known streak:  landing in already-worked territory would trip the
                    #                   stop-this-source rule and cancel the benefit of the jump
                    private_streak = 0
                    consecutive_empty_screens = 0
                    consecutive_top_loops = 0
                    known_usernames_streak = 0
                    scroll_detector = ScrollEndDetector(repeats_to_end=5, device=self.device)
                    continue

                # Notify the scroll-end detector ONLY when the visible page is exhausted
                # (every follower on it already processed this session). While a fresh follower
                # remains, we deliberately re-scan the SAME page (process one -> break -> re-scan),
                # so feeding those identical re-scans to the detector inflated its "same page N
                # times in a row" counter (_duplicate_page_count) and tripped a FALSE end-of-list:
                # a run stopping at 24/472 followers even though the scroll was advancing fine.
                # The duplicate-page signal must mean "scrolled but nothing new appeared", never
                # "haven't scrolled yet because the page is still being worked through". Gating on
                # exhaustion (== right before we actually scroll) restores that meaning.
                visible_usernames = [f['username'] for f in visible_followers]
                if new_usernames_found == 0:
                    scroll_detector.notify_new_page(visible_usernames, list(processed_usernames))
                
                # Scrolling and end-of-list handling
                should_stop, stop_reason = self._handle_scroll_and_end_detection(
                    new_usernames_found, no_new_profiles_count, total_usernames_seen,
                    target_followers_count, scroll_detector, tracker, scroll_attempts,
                    new_profiles_to_interact, did_interact_this_iteration,
                    stats, max_interactions, known_usernames_streak,
                    max_consecutive_known_usernames, legacy_max_no_new_usernames_scrolls
                )
                
                if should_stop and list_was_only_loading(stop_reason):
                    continue

                if stop_reason:
                    session_stop_reason = stop_reason
                
                if should_stop:
                    break
                
                if new_usernames_found == 0:
                    no_new_profiles_count += 1
                    tracker.log_scroll("down")
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
                    scroll_attempts += 1
                    continue
                else:
                    no_new_profiles_count = 0
                    if target_followers_count > 0:
                        coverage = (total_usernames_seen / target_followers_count) * 100
                        self.logger.debug(f"📊 Progress: {total_usernames_seen:,}/{target_followers_count:,} ({coverage:.1f}%) - {new_usernames_found} new this page")
                    if new_profiles_to_interact == 0 and new_usernames_found > 0:
                        if max_consecutive_known_usernames is not None:
                            self.logger.debug(
                                f"📋 {new_usernames_found} new usernames seen, but all already in DB - "
                                f"known streak {known_usernames_streak}/{max_consecutive_known_usernames}"
                            )
                        else:
                            self.logger.debug(f"📋 {new_usernames_found} new usernames seen, but all already in DB - continuing scroll")
                
                # Scroller si nécessaire
                if stats['interacted'] < max_interactions:
                    if not did_interact_this_iteration or (new_usernames_found > 0 and new_profiles_to_interact == 0):
                        self.logger.debug(f"📜 Scrolling (interacted: {did_interact_this_iteration}, new_usernames: {new_usernames_found}, to_interact: {new_profiles_to_interact})")
                        
                        load_more_result = self.scroll_actions.check_and_click_load_more()
                        if load_more_result is True:
                            self.logger.info("✅ 'Voir plus' clicked before scroll - loading more real followers")
                            self._human_like_delay('load_more')
                            time.sleep(1.0)
                            scroll_attempts = 0
                            continue
                        elif load_more_result is False:
                            self.logger.info("🏁 End of followers list detected (suggestions section)")
                            if list_was_only_loading(stop_reasons.end_of_list_suggestions()):
                                continue
                            session_stop_reason = (
                                session_stop_reason or stop_reasons.end_of_list_suggestions())
                            break
                        
                        tracker.log_scroll("down")
                        self.scroll_actions.scroll_followers_list_down()
                        self._human_like_delay('scroll')
                        scroll_attempts += 1
            
            # The loop's own scroll ceiling is an exit too. Reached mid-list with budget still
            # to spend, it used to fall through to the `completed` fallback and reach the
            # operator as a job done — three runs of one account in a week, one of them at 18%
            # of a 517-follower list.
            if (scroll_attempts >= max_scroll_attempts
                    and stats['interacted'] < max_interactions
                    and not session_stop_reason):
                session_stop_reason = stop_reasons.scroll_budget(
                    scroll_attempts, total_usernames_seen)

            # Finalization — sync aliased keys before return
            sync_aliases(stats, 'followers_direct')
            # Surface the session-level stop to callers: a multi-target driver must stop
            # distributing budget to the NEXT targets when this run ended for a session
            # reason (duration, global limits), not just because this list ran dry.
            stats['stop_reason'] = session_stop_reason or ''
            tracker.log_session_end(stats)
            self.logger.info(f"✅ Direct interactions completed: {stats}")
            self.stats_manager.display_final_stats(workflow_name="FOLLOWERS_DIRECT")

            # finalize=False: a multi-target run finalises ONCE at the driver level —
            # finalising here would end the session after the first target.
            if finalize and self.automation and hasattr(self.automation, 'helpers'):
                if navigation_lost:
                    # A run that died on lost navigation is NOT a completed run: surface it as
                    # INTERRUPTED (already an accepted terminal status — Ctrl+C uses it) so the
                    # operator can tell a degraded run (626: 23/46) from a healthy one.
                    self.automation.helpers.finalize_session(
                        status='INTERRUPTED', reason=session_stop_reason or stop_reasons.navigation_lost())
                else:
                    # The STATUS follows the motive, as it already does at the driver level.
                    # Hard-coding COMPLETED here filed a run that lost its list exactly like one
                    # that spent its budget — visible only on a single-target run, since a
                    # multi-target one finalises at the driver and derived it correctly.
                    reason = session_stop_reason or stop_reasons.completed(stats['interacted'])
                    self.automation.helpers.finalize_session(
                        status=stop_reasons.terminal_status(reason), reason=reason)

            return stats

        except Exception as e:
            self.logger.error(f"Error in direct followers workflow: {e}")
            sync_aliases(stats, 'followers_direct')
            stats.setdefault('stop_reason', '')
            return stats
