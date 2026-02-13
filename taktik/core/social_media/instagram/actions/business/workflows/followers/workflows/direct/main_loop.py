"""Main interaction loop for the direct followers workflow."""

import time
from typing import Dict, Any

from .....common import DatabaseHelpers
from ......core.stats import create_workflow_stats, sync_aliases
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from ....common.followers_tracker import FollowersTracker
from .navigation_helpers import DirectNavigationMixin
from .profile_processing import DirectProfileProcessingMixin


class FollowerDirectWorkflowMixin(DirectNavigationMixin, DirectProfileProcessingMixin):
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
        
        stats = create_workflow_stats('followers_direct')
        
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
                    # force_back=False: _process_single_follower_direct already calls
                    # _ensure_on_followers_list for filtered/private/error cases, so we only
                    # need to force a back when coming from an actual interaction (like/follow)
                    if not self._ensure_on_followers_list(target_username, force_back=False):
                        self.logger.error("Could not return to followers list, stopping")
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
            
            # Finalization — sync aliased keys before return
            sync_aliases(stats, 'followers_direct')
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
            sync_aliases(stats, 'followers_direct')
            return stats
