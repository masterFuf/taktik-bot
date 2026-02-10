"""Direct followers workflow: interact by clicking profiles in the followers list."""

import time
import json
from typing import Dict, Any, List

from ....common import DatabaseHelpers
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from ...common.followers_tracker import FollowersTracker


class FollowerDirectWorkflowMixin:
    """Mixin: interact_with_followers_direct — main workflow using direct clicks."""

    def interact_with_followers_direct(self, target_username: str,
                                       max_interactions: int = 30,
                                       config: Dict[str, Any] = None,
                                       account_id: int = None) -> Dict[str, Any]:
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
        
        stats = {
            'interacted': 0,      # Profiles with actual interaction (like/follow/story/comment)
            'visited': 0,         # Total profiles visited (navigated to)
            'liked': 0,
            'followed': 0,
            'stories_viewed': 0,
            'story_likes': 0,     # Likes on stories
            'errors': 0,
            'skipped': 0,
            'filtered': 0,        # Profiles filtered by criteria
            'already_processed': 0,
            # Keep 'processed' as alias for 'interacted' for backward compatibility
            'processed': 0
        }
        
        interaction_config = {
            'like_probability': config.get('like_probability', 0.8),
            'follow_probability': config.get('follow_probability', 0.2),
            'comment_probability': config.get('comment_probability', 0.1),
            'story_probability': config.get('story_probability', 0.2),
            'max_likes_per_profile': config.get('max_likes_per_profile', 3),
            'filter_criteria': config.get('filter_criteria', config.get('filters', {}))
        }
        
        # Navigation configuration
        deep_link_percentage = config.get('deep_link_percentage', 90)
        force_search_for_target = config.get('force_search_for_target', False)
        
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
                    visible_usernames_for_tracking = [f['username'] for f in visible_followers]
                    loop_detected = tracker.log_visible_followers(visible_usernames_for_tracking, "scan")
                    if loop_detected:
                        self.logger.warning("⚠️ LOOP DETECTED: Back to start of followers list!")
                        if tracker.loop_detected_count >= 3:
                            self.logger.error("🛑 Too many loops detected (3+), stopping to avoid infinite loop")
                            break
                        else:
                            self.logger.info("🔄 Trying to scroll past the loop...")
                            for _ in range(3):
                                self.scroll_actions.scroll_followers_list_down()
                                self._human_like_delay('scroll')
                            continue
                
                if not visible_followers:
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
                        self.logger.warning(f"⚠️ Position lost: neither @{last_visited_username} nor @{next_expected_username} visible")
                
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
                            continue
                    
                    # Skip target account
                    if target_username and username.lower() == target_username.lower():
                        self.logger.info(f"⏭️ Skipping target account @{username}")
                        processed_usernames.add(username)
                        continue
                    
                    processed_usernames.add(username)
                    new_usernames_found += 1
                    total_usernames_seen += 1
                    
                    # Vérifier si déjà traité OU filtré via DB
                    if account_id:
                        try:
                            should_skip, skip_reason = DatabaseHelpers.is_profile_skippable(
                                username, account_id, hours_limit=24*60
                            )
                            if should_skip:
                                if skip_reason == "already_processed":
                                    self.logger.debug(f"@{username} already processed in DB, skipping")
                                    stats['already_processed'] += 1
                                    tracker.log_skipped_from_db(username, "already_processed")
                                elif skip_reason == "already_filtered":
                                    self.logger.debug(f"@{username} already filtered in DB, skipping")
                                    stats['filtered'] += 1
                                    tracker.log_skipped_from_db(username, "already_filtered")
                                stats['skipped'] += 1
                                continue
                        except Exception as e:
                            self.logger.warning(f"Error checking @{username}: {e}")
                    
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
                        # Critical error — could not recover to list
                        break
                    
                    if interaction_ok:
                        did_interact_this_iteration = True
                    
                    # Retour à la liste des followers avec vérification robuste
                    if not self._ensure_on_followers_list(target_username, force_back=True):
                        self.logger.error("Could not return to followers list, stopping")
                        break
                    
                    # Vérification de position après retour
                    visible_after_back = self.detection_actions.get_visible_followers_with_elements()
                    if visible_after_back:
                        visible_usernames_after = [f['username'] for f in visible_after_back]
                        position_ok = tracker.check_position_after_back(username, visible_usernames_after)
                        if not position_ok:
                            self.logger.warning(f"⚠️ Position lost after visiting @{username} - may cause loop")
                    
                    self.stats_manager.display_stats(current_profile=username)
                    
                    if stats['interacted'] >= max_interactions:
                        break
                    
                    # Après interaction, re-scanner la liste
                    break
                
                # Notifier le scroll detector des usernames vus
                visible_usernames = [f['username'] for f in visible_followers]
                scroll_detector.notify_new_page(visible_usernames, list(processed_usernames))
                
                # Gestion du scroll et fin de liste
                should_stop, stop_reason = self._handle_scroll_and_end_detection(
                    new_usernames_found, no_new_profiles_count, total_usernames_seen,
                    target_followers_count, scroll_detector, tracker, scroll_attempts,
                    new_profiles_to_interact, did_interact_this_iteration,
                    stats, max_interactions
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
            
            # Finalization
            tracker.log_session_end(stats)
            self.logger.info(f"✅ Direct interactions completed: {stats}")
            self.stats_manager.display_final_stats(workflow_name="FOLLOWERS_DIRECT")
            
            if session_stop_reason and self.automation and hasattr(self.automation, 'helpers'):
                self.automation.helpers.finalize_session(status='COMPLETED', reason=session_stop_reason)
            elif self.automation and hasattr(self.automation, 'helpers'):
                reason = f"Workflow completed ({stats['interacted']} interactions)"
                self.automation.helpers.finalize_session(status='COMPLETED', reason=reason)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error in direct followers workflow: {e}")
            return stats

    # ─── Helper: setup target navigation ──────────────────────────────────

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

    # ─── Helper: recover after break ──────────────────────────────────────

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

    # ─── Helper: handle empty followers screen ────────────────────────────

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

    # ─── Helper: process a single follower from the list ──────────────────

    def _process_single_follower_direct(
        self, username, idx, stats, interaction_config, account_id,
        target_username, target_followers_count, total_usernames_seen,
        max_interactions, tracker
    ):
        """
        Process a single follower: click profile → extract info → filter → interact.
        
        Returns:
            True if interaction happened, False if skipped/filtered, None if critical error (can't recover)
        """
        # Progress info
        profiles_clicked = stats.get('profiles_clicked', 0) + 1
        stats['profiles_clicked'] = profiles_clicked
        progress_info = f"[{stats['interacted']}/{max_interactions} interactions, {profiles_clicked} visited]"
        if target_followers_count > 0:
            progress_pct = (total_usernames_seen / target_followers_count) * 100
            progress_info += f" ({progress_pct:.1f}% of {target_followers_count:,} followers scanned)"
        self.logger.info(f"{progress_info} 👆 Clicking on @{username}")
        
        # Cliquer sur le profil dans la liste
        if not self.detection_actions.click_follower_in_list(username):
            self.logger.warning(f"Could not click on @{username}")
            stats['errors'] += 1
            return False
        
        self._human_like_delay('navigation')
        
        # Vérifier qu'on est bien sur un profil
        if not self.detection_actions.is_on_profile_screen():
            self.logger.warning(f"Not on profile screen after clicking @{username}")
            if not self._ensure_on_followers_list(target_username):
                return None  # Critical
            stats['errors'] += 1
            return False
        
        # Profile successfully visited
        stats['visited'] += 1
        self.stats_manager.increment('profiles_visited')
        
        # Emit IPC event
        try:
            from bridges.instagram.desktop_bridge import send_instagram_profile_visit
            send_instagram_profile_visit(username)
        except (ImportError, Exception):
            pass
        
        tracker.log_profile_visit(username, idx, already_in_db=False)
        
        # Extraire les infos du profil
        try:
            profile_data = self.profile_business.get_complete_profile_info(
                username=username, 
                navigate_if_needed=False
            )
            
            if not profile_data:
                self.logger.warning(f"Could not get profile data for @{username}")
                if not self._ensure_on_followers_list(target_username, force_back=True):
                    return None  # Critical
                stats['errors'] += 1
                return False
            
            # Vérifier si profil privé
            if profile_data.get('is_private', False):
                self.logger.info(f"🔒 Private profile @{username} - skipped")
                stats['skipped'] += 1
                self.stats_manager.increment('private_profiles')
                tracker.log_profile_filtered(username, "Private profile", profile_data)
                
                if account_id:
                    try:
                        DatabaseHelpers.record_filtered_profile(
                            username=username,
                            reason='Private profile',
                            source_type='FOLLOWER',
                            source_name=target_username,
                            account_id=account_id,
                            session_id=self._get_session_id()
                        )
                    except Exception:
                        pass
                
                if not self._ensure_on_followers_list(target_username, force_back=True):
                    return None  # Critical
                return False
            
            # Appliquer les filtres
            filter_criteria = interaction_config.get('filter_criteria', {})
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_data, filter_criteria
            )
            
            if not filter_result.get('suitable', False):
                reasons = filter_result.get('reasons', [])
                self.logger.info(f"🚫 @{username} filtered: {', '.join(reasons)}")
                stats['filtered'] += 1
                self.stats_manager.increment('profiles_filtered')
                tracker.log_profile_filtered(username, ', '.join(reasons), profile_data)
                
                if account_id:
                    try:
                        DatabaseHelpers.record_filtered_profile(
                            username=username,
                            reason=', '.join(reasons),
                            source_type='FOLLOWER',
                            source_name=target_username,
                            account_id=account_id,
                            session_id=self._get_session_id()
                        )
                    except Exception as e:
                        self.logger.debug(f"Error recording filtered profile @{username}: {e}")
                
                if not self._ensure_on_followers_list(target_username, force_back=True):
                    return None  # Critical
                return False
            
            # === EFFECTUER LES INTERACTIONS ===
            interaction_result = self._perform_profile_interactions(
                username, 
                interaction_config, 
                profile_data=profile_data
            )
            
            self.logger.debug(f"🔍 interaction_result for @{username}: {interaction_result}")
            
            actually_interacted = False
            
            if interaction_result.get('liked'):
                likes_count = interaction_result.get('likes_count', 1)
                stats['liked'] += likes_count
                self.stats_manager.increment('likes', likes_count)
                actually_interacted = True
            if interaction_result.get('followed'):
                stats['followed'] += 1
                self.stats_manager.increment('follows')
                actually_interacted = True
            if interaction_result.get('story_viewed'):
                stats['stories_viewed'] += 1
                self.stats_manager.increment('stories_watched')
                actually_interacted = True
            if interaction_result.get('story_liked'):
                stats['story_likes'] += 1
                self.stats_manager.increment('story_likes')
                actually_interacted = True
            if interaction_result.get('commented'):
                actually_interacted = True
            
            if actually_interacted:
                stats['interacted'] += 1
                stats['processed'] += 1
                self.stats_manager.increment('profiles_interacted')
                self.human.record_interaction()
                tracker.log_profile_interacted(username, {
                    'liked': interaction_result.get('liked', False),
                    'followed': interaction_result.get('followed', False),
                    'story_viewed': interaction_result.get('story_viewed', False),
                    'commented': interaction_result.get('commented', False)
                })
            else:
                self.logger.debug(f"@{username} visited but no interaction (probability)")
                stats['skipped'] += 1
            
            # Marquer comme traité dans la DB
            if account_id:
                try:
                    DatabaseHelpers.mark_profile_as_processed(
                        username, 
                        "Direct interaction from followers list" if actually_interacted else "Visited but no interaction",
                        account_id=account_id,
                        session_id=self._get_session_id()
                    )
                except Exception:
                    pass
            
            if actually_interacted and self.session_manager:
                self.session_manager.record_profile_processed()
            
            return actually_interacted
        
        except Exception as e:
            self.logger.error(f"Error interacting with @{username}: {e}")
            stats['errors'] += 1
            return False

    # ─── Helper: scroll & end detection logic ─────────────────────────────

    def _handle_scroll_and_end_detection(
        self, new_usernames_found, no_new_profiles_count, total_usernames_seen,
        target_followers_count, scroll_detector, tracker, scroll_attempts,
        new_profiles_to_interact, did_interact_this_iteration,
        stats, max_interactions
    ):
        """
        Handle end-of-list detection when no new usernames found.
        
        Returns:
            (should_stop: bool, stop_reason: str or None)
        """
        if new_usernames_found > 0:
            return False, None
        
        # No new usernames found
        remaining_followers = target_followers_count - total_usernames_seen if target_followers_count > 0 else float('inf')
        self.logger.debug(f"⚠️ No new usernames found ({no_new_profiles_count}/15) - {total_usernames_seen} seen, ~{remaining_followers:,.0f} remaining")
        
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
        
        if no_new_profiles_count >= 20:
            reason = f"No new followers after 20 scroll attempts ({total_usernames_seen} seen)"
            self.logger.info(f"🏁 No new usernames found after 20 attempts (seen {total_usernames_seen:,} usernames)")
            return True, reason
        
        if no_new_profiles_count >= 10:
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
