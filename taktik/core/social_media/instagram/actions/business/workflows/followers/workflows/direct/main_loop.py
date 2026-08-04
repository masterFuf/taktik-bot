"""Main interaction loop for the direct followers workflow."""

import time
from typing import Dict, Any

from ......core.stats import create_workflow_stats, sync_aliases
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.shared.telemetry import emit_step
from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter
from ....common.revisit_policy import RevisitPolicy
from ....common.private_streak_policy import PrivateStreakPolicy
from ....common.followers_tracker import FollowersTracker
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
        🆕 NOUVEAU WORKFLOW: Interaction directe depuis la liste des followers.
        
        Au lieu de scraper puis naviguer via deep link, on:
        1. Ouvre la liste des followers
        2. Pour chaque follower visible: clic direct → interaction → retour
        3. Scroll seulement quand tous les visibles sont traités
        
        Avantages:
        - ❌ Plus de deep links (pattern suspect)
        - ✅ Navigation 100% naturelle par clics
        - ✅ Comportement humain réaliste
        """
        config = config or {}
        
        stats = create_workflow_stats('followers_direct')
        
        interaction_config = {
            'like_probability': config.get('like_probability', 0.8),
            'follow_probability': config.get('follow_probability', 0.2),
            'comment_probability': config.get('comment_probability', 0.1),
            'story_probability': config.get('story_probability', 0.2),
            'story_like_probability': config.get('story_like_probability', 0.0),
            'min_likes_per_profile': config.get('min_likes_per_profile', 1),
            'max_likes_per_profile': config.get('max_likes_per_profile', 3),
            'max_comments_per_profile': config.get('max_comments_per_profile', 1),
            'max_stories_per_profile': config.get('max_stories_per_profile', 3),
            'max_story_likes_per_profile': config.get('max_story_likes_per_profile', 1),
            'ai_decision_mode': config.get('ai_decision_mode'),
            'ai_decision_dry_run': config.get('ai_decision_dry_run', True),
            'ai_decision_capabilities': config.get('ai_decision_capabilities'),
            'filter_criteria': config.get('filter_criteria', config.get('filters', {}))
        }
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
        max_consecutive_known_usernames = config.get('max_consecutive_known_usernames')
        if max_consecutive_known_usernames is not None:
            max_consecutive_known_usernames = max(1, int(max_consecutive_known_usernames or 1))

        legacy_max_no_new_usernames_scrolls = config.get('max_no_new_usernames_scrolls')
        if legacy_max_no_new_usernames_scrolls is not None:
            legacy_max_no_new_usernames_scrolls = max(1, int(legacy_max_no_new_usernames_scrolls or 1))
        elif max_consecutive_known_usernames is None:
            legacy_max_no_new_usernames_scrolls = 20
        
        try:
            # 1. Naviguer vers le profil cible et ouvrir la liste
            target_followers_count, profile_info = self._setup_direct_workflow(
                target_username, stats, config, deep_link_percentage, force_search_for_target
            )
            if target_followers_count is None:
                return stats  # Setup failed
            
            # Démarrer la phase d'interaction
            if self.session_manager:
                self.session_manager.start_interaction_phase()
            
            # 3. Boucle principale d'interaction
            processed_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 100
            no_new_profiles_count = 0
            known_usernames_streak = 0
            total_usernames_seen = 0
            
            # Contexte de navigation pour savoir où on en est
            last_visited_username = None
            next_expected_username = None
            
            # Initialiser le ScrollEndDetector et le tracker
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

            while stats['interacted'] < max_interactions and scroll_attempts < max_scroll_attempts:
                # Vérifier si on doit prendre une pause
                took_break = self._maybe_take_break()
                
                # Après une pause, vérifier qu'on est toujours sur la liste des followers
                if took_break:
                    self._recover_after_break(
                        target_username, deep_link_percentage, force_search_for_target, total_usernames_seen
                    )
                
                # Vérifier si la session doit continuer
                if self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        session_stop_reason = stop_reason
                        break
                
                # Récupérer les followers visibles (uniquement les vrais, pas les suggestions)
                visible_followers = self.detection_actions.get_visible_followers_with_elements()
                
                # Tracker: enregistrer les followers visibles + détecter les boucles
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
                        session_stop_reason = session_stop_reason or 'followers_list_unavailable'
                        break
                    # Gérer la fin de liste / suggestions / scroll
                    should_break = self._handle_empty_followers_screen(scroll_detector)
                    if should_break:
                        break
                    scroll_attempts += 1
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
                    continue

                new_usernames_found = 0
                new_profiles_to_interact = 0
                did_interact_this_iteration = False
                
                visible_usernames_list = [f['username'] for f in visible_followers]
                
                # Vérifier si on est au bon endroit après un retour de profil
                if last_visited_username and next_expected_username:
                    position_ok = last_visited_username in visible_usernames_list or next_expected_username in visible_usernames_list
                    tracker.log_position_check(last_visited_username, next_expected_username, visible_usernames_list, position_ok)
                    
                    if position_ok:
                        self.logger.debug(f"✅ Position OK: found @{last_visited_username} or @{next_expected_username} in visible list")
                    else:
                        self.logger.debug(f"⚠️ Position lost: neither @{last_visited_username} nor @{next_expected_username} visible")
                
                for idx, follower_data in enumerate(visible_followers):
                    username = follower_data['username']
                    
                    # Skip si déjà vu dans cette session
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
                    
                    # Vérifier si déjà traité OU filtré via DB
                    if account_id:
                        try:
                            should_skip, skip_reason = InstagramWorkflowStateService.is_profile_skippable(
                                username, account_id,
                                hours_limit=revisit_policy.reinteraction_hours,
                                filtered_max_age_days=revisit_policy.filtered_max_age_days,
                            )
                            if should_skip:
                                known_usernames_streak += 1
                                # "Already known" is its OWN outcome — a follower we deliberately leave
                                # alone (60-day cooldown = already interacted) or one already filtered
                                # in a PRIOR session. It is NOT a this-session rejection, so it must NOT
                                # land in stats['skipped'] / stats['filtered'] (which count private /
                                # probability skips and this-session quality filters) — that would
                                # inflate the run's reject stats and mix "we already did this profile"
                                # with "we rejected this profile". Dedicated buckets + a distinct
                                # telemetry action (`already_known`) keep it separate everywhere it is
                                # tallied; the reason token still feeds the per-reason breakdown.
                                if skip_reason == "already_processed":
                                    self.logger.debug(f"@{username} already processed in DB, skipping")
                                    stats['already_processed'] += 1
                                    tracker.log_skipped_from_db(username, "already_processed")
                                elif skip_reason == "already_filtered":
                                    self.logger.debug(f"@{username} already filtered in DB, skipping")
                                    stats['already_filtered'] += 1
                                    tracker.log_skipped_from_db(username, "already_filtered")
                                emit_step("follower_decision", action="already_known", target=username,
                                          reason=skip_reason or "db_skip", encounter_order=total_usernames_seen,
                                          source_type="FOLLOWERS", streak=known_usernames_streak)
                                # Live visibility (Taktik Agent): surface the pre-click DB skip as a
                                # SkippedProfileCard. Until now this reason (60-day cooldown /
                                # already-filtered) only went to local trace + aggregate telemetry, so
                                # the user saw in-profile filters but never WHY a profile was skipped
                                # before the click. reason is the machine token (front localizes it);
                                # detail adds the original filter reason / days-since-interaction.
                                skip_detail = InstagramWorkflowStateService.get_skip_detail(
                                    username, account_id, skip_reason
                                )
                                IPCEmitter.emit_profile_skipped(
                                    username, reason=skip_reason or "already in DB", detail=skip_detail
                                )
                                continue
                            known_usernames_streak = 0
                        except Exception as e:
                            self.logger.warning(f"Error checking @{username}: {e}")
                            known_usernames_streak = 0
                    else:
                        known_usernames_streak = 0
                    
                    new_profiles_to_interact += 1
                    
                    # Mémoriser le contexte AVANT de cliquer
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
                        session_stop_reason = session_stop_reason or 'navigation_lost'
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
                    
                    # Retour à la liste des followers avec vérification robuste
                    # force_back=False: _process_single_follower_direct already calls
                    # _ensure_on_followers_list for filtered/private/error cases, so we only
                    # need to force a back when coming from an actual interaction (like/follow)
                    if not self._ensure_on_followers_list(target_username, force_back=False):
                        # "stopping" must mean STOPPING: this break only exits the for-loop, so
                        # without the flag the while-loop kept scrolling a dead screen for minutes.
                        self.logger.error("Could not return to followers list, stopping")
                        navigation_lost = True
                        session_stop_reason = session_stop_reason or 'navigation_lost'
                        break
                    
                    # Vérification de position après retour
                    visible_after_back = self.detection_actions.get_visible_followers_with_elements()
                    if visible_after_back:
                        visible_usernames_after = [f['username'] for f in visible_after_back]
                        position_ok = tracker.check_position_after_back(username, visible_usernames_after)
                        if not position_ok:
                            self.logger.debug(f"⚠️ Position lost after visiting @{username} - may cause loop")
                    
                    self.stats_manager.display_stats(current_profile=username)
                    
                    if stats['interacted'] >= max_interactions:
                        break
                    
                    # Après interaction, re-scanner la liste
                    break

                if navigation_lost:
                    self.logger.error("🛑 Navigation lost — ending run (no blind scrolling on an unknown screen)")
                    break

                # === PRIVATE ZONE ESCAPE ===
                # Enough consecutive private profiles to conclude we are in a head of list that
                # was handed to this account rather than in a private-heavy source. Transport
                # past it instead of spending the whole session budget there.
                if private_streak_policy.should_escape(private_streak, private_zone_jumps):
                    emit_step("private_zone_escape", action="transport_start",
                              streak=private_streak, jump=private_zone_jumps + 1,
                              source_type="FOLLOWERS", target=target_username)
                    IPCEmitter.emit_action('private_zone_escape', target_username, {
                        'streak': private_streak,
                        'jump': private_zone_jumps + 1,
                        'max_jumps': private_streak_policy.max_jumps,
                        'source_followers': target_followers_count,
                    })

                    moved = self._escape_private_zone(
                        private_streak_policy, private_zone_jumps, target_followers_count
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

                    tracker.log_scroll("private_zone_transport")
                    emit_step("private_zone_escape", action="transport_done",
                              gestures=moved, jump=private_zone_jumps,
                              source_type="FOLLOWERS", target=target_username)
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
                
                # Gestion du scroll et fin de liste
                should_stop, stop_reason = self._handle_scroll_and_end_detection(
                    new_usernames_found, no_new_profiles_count, total_usernames_seen,
                    target_followers_count, scroll_detector, tracker, scroll_attempts,
                    new_profiles_to_interact, did_interact_this_iteration,
                    stats, max_interactions, known_usernames_streak,
                    max_consecutive_known_usernames, legacy_max_no_new_usernames_scrolls
                )
                
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
                            break
                        
                        tracker.log_scroll("down")
                        self.scroll_actions.scroll_followers_list_down()
                        self._human_like_delay('scroll')
                        scroll_attempts += 1
            
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
                        status='INTERRUPTED', reason=session_stop_reason or 'navigation_lost')
                elif session_stop_reason:
                    self.automation.helpers.finalize_session(status='COMPLETED', reason=session_stop_reason)
                else:
                    reason = f"Workflow completed ({stats['interacted']} interactions)"
                    self.automation.helpers.finalize_session(status='COMPLETED', reason=reason)

            return stats

        except Exception as e:
            self.logger.error(f"Error in direct followers workflow: {e}")
            sync_aliases(stats, 'followers_direct')
            stats.setdefault('stop_reason', '')
            return stats
