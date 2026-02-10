"""Legacy followers workflow: interact with a pre-scraped list of followers."""

import time
import random
from typing import Dict, Any, List

from ...common import DatabaseHelpers


class FollowerLegacyWorkflowMixin:
    """Mixin: interact_with_followers — legacy workflow using pre-scraped follower list."""

    def interact_with_followers(self, followers: List[Dict[str, Any]], 
                              interaction_config: Dict[str, Any] = None,
                              session_id: str = None,
                              target_username: str = None) -> Dict[str, Any]:
        config = {**self.default_config, **(interaction_config or {})}
        
        stats = {
            'processed': 0,
            'liked': 0,
            'followed': 0,
            'stories_viewed': 0,
            'errors': 0,
            'skipped': 0,
            'resumed_from_checkpoint': False
        }
        
        max_profiles_to_interact = config['max_interactions_per_session']
        start_index = 0
        
        self.logger.info(f"Probabilities: like={config.get('like_probability', 'N/A')}, follow={config.get('follow_probability', 'N/A')}")
        self.logger.info(f"Config: {config}")
        self.logger.info(f"Target: {max_profiles_to_interact} profiles to interact with (available: {len(followers)})")
        if session_id and target_username:
            checkpoint_data = self._load_checkpoint(session_id, target_username)
            if checkpoint_data:
                followers = checkpoint_data.get('followers', followers)
                start_index = checkpoint_data.get('current_index', 0)
                stats['resumed_from_checkpoint'] = True
                self.logger.info(f"Resuming from checkpoint at index {start_index}/{len(followers)}")
            else:
                self._create_checkpoint(session_id, target_username, followers, 0)
        
        self.logger.info(f"Starting interactions - goal: {max_profiles_to_interact} profiles interacted (start index: {start_index})")
        
        try:
            i = start_index
            while i < len(followers) and stats['processed'] < max_profiles_to_interact:
                # Get current follower and increment index for next iteration
                follower = followers[i]
                i += 1  # Increment here so continue statements don't skip it
                
                # Vérifier si la session doit continuer (durée, limites, etc.)
                if hasattr(self, 'session_manager') and self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        break
                
                username = follower.get('username', '')
                
                try:
                    if not username:
                        stats['skipped'] += 1
                        self._update_checkpoint_index(i)
                        continue
                    
                    self.logger.info(f"[{stats['processed']+1}/{max_profiles_to_interact}] Interacting with @{username}")
                    if session_id and target_username:
                        self._update_checkpoint_index(i - 1)
                    
                    account_id = follower.get('source_account_id')
                    if account_id:
                        try:
                            should_skip, skip_reason = DatabaseHelpers.is_profile_skippable(
                                username, account_id, hours_limit=24*60
                            )
                            if should_skip:
                                self.logger.info(f"Profile @{username} skipped ({skip_reason})")
                                stats['skipped'] += 1
                                self.stats_manager.increment('skipped')
                                continue
                        except Exception as e:
                            self.logger.warning(f"Error checking @{username}: {e}")
                    
                    try:
                        if not self.nav_actions.navigate_to_profile(username):
                            self.logger.warning(f"Failed to navigate to @{username}")
                            stats['errors'] += 1
                            self.stats_manager.add_error(f"Navigation failed to @{username}")
                            continue
                    except Exception as e:
                        self.logger.error(f"Error navigating to @{username}: {e}")
                        stats['errors'] += 1
                        self.stats_manager.add_error(f"Navigation error @{username}: {str(e)}")
                        continue
                    
                    # Emit IPC event for frontend (WorkflowAnalyzer + SessionLivePanel)
                    try:
                        from bridges.instagram.desktop_bridge import send_instagram_profile_visit
                        send_instagram_profile_visit(username)
                    except ImportError:
                        pass  # Bridge not available (CLI mode)
                    except Exception:
                        pass  # Ignore IPC errors
                    
                    self._random_sleep()
                    
                    # ✅ EXTRACTION UNIQUE DU PROFIL (évite les duplications)
                    profile_data = None
                    if hasattr(self, 'automation') and self.automation:
                        try:
                            profile_data = self.profile_business.get_complete_profile_info(username=username, navigate_if_needed=False)
                            if not profile_data:
                                self.logger.warning(f"Failed to get profile data for @{username}")
                                stats['errors'] += 1
                                self.stats_manager.increment('errors')
                                continue
                            
                            if profile_data.get('is_private', False):
                                self.logger.info(f"Private profile @{username} - skipped")
                                stats['skipped'] += 1
                                self.stats_manager.increment('private_profiles')
                                self.stats_manager.increment('skipped')
                                
                                # Enregistrer le profil privé dans filtered_profile
                                try:
                                    session_id = self._get_session_id()
                                    source_name = getattr(self.automation, 'target_username', 'unknown')
                                    DatabaseHelpers.record_filtered_profile(
                                        username=username,
                                        reason='Private profile',
                                        source_type='FOLLOWER',
                                        source_name=source_name,
                                        account_id=account_id,
                                        session_id=session_id
                                    )
                                    self.logger.debug(f"Private profile @{username} recorded in API")
                                except Exception as e:
                                    self.logger.error(f"Error recording private profile @{username}: {e}")
                                
                                continue
                                
                        except Exception as e:
                            self.logger.error(f"Error getting profile @{username}: {e}")
                            stats['errors'] += 1
                            self.stats_manager.increment('errors')
                            continue
                    
                    try:
                        # ✅ Passer profile_data pour éviter une 2ème extraction
                        interaction_result = self._perform_profile_interactions(username, config, profile_data=profile_data)
                        
                        # Track if we actually interacted
                        actually_interacted = False
                        
                        if interaction_result.get('liked'):
                            stats['liked'] += 1
                            actually_interacted = True
                        if interaction_result.get('followed'):
                            stats['followed'] += 1
                            actually_interacted = True
                        if interaction_result.get('story_viewed'):
                            stats['stories_viewed'] += 1
                            actually_interacted = True
                        if interaction_result.get('commented'):
                            if 'comments' not in stats:
                                stats['comments'] = 0
                            stats['comments'] += 1
                            actually_interacted = True
                        
                        # Only count as interacted if we actually did something
                        if actually_interacted:
                            stats['processed'] += 1
                            self.stats_manager.increment('profiles_interacted')
                            # Enregistrer l'interaction pour le système de pauses
                            self.human.record_interaction()
                        else:
                            self.logger.debug(f"@{username} visited but no interaction (probability)")
                            stats['skipped'] += 1
                        
                        # Mark as processed in DB (to avoid revisiting)
                        if account_id:
                            try:
                                visit_notes = "Profile interaction" if actually_interacted else "Visited but no interaction"
                                DatabaseHelpers.mark_profile_as_processed(
                                    username, visit_notes,
                                    account_id=account_id,
                                    session_id=self._get_session_id()
                                )
                            except Exception as e:
                                self.logger.warning(f"Error marking @{username}: {e}")
                        
                        if interaction_result.get('filtered', False):
                            self.stats_manager.increment('profiles_filtered')
                            

                            try:
                                filter_reasons = interaction_result.get('filter_reasons', [])
                                reasons_text = ', '.join(filter_reasons) if filter_reasons else 'filtered'
                                
                                account_id = self._get_account_id()
                                session_id = self._get_session_id()
                                source_name = getattr(self.automation, 'target_username', 'unknown')
                                
                                self.logger.debug(f"[FILTERED] Attempting to record @{username}: account_id={account_id}, session_id={session_id}, source={source_name}")
                                
                                if not account_id:
                                    self.logger.warning(f"[FILTERED] Cannot record @{username} - account_id is None")
                                else:
                                    DatabaseHelpers.record_filtered_profile(
                                        username=username,
                                        reason=reasons_text,
                                        source_type='FOLLOWER',
                                        source_name=source_name,
                                        account_id=account_id,
                                        session_id=session_id
                                    )
                                    self.logger.info(f"Filtered profile @{username} recorded (reasons: {reasons_text})")
                            except Exception as e:
                                self.logger.error(f"Error recording filtered profile @{username}: {e}")
                        else:
                            if interaction_result.get('liked'):
                                self.stats_manager.increment('likes', interaction_result.get('likes_count', 1))
                                # Record LIKE in database
                                likes_count = interaction_result.get('likes_count', 1)
                                DatabaseHelpers.record_individual_actions(
                                    username, 'LIKE', likes_count,
                                    account_id=account_id, session_id=self._get_session_id()
                                )
                            if interaction_result.get('followed'):
                                self.stats_manager.increment('follows')
                                # Record FOLLOW in database
                                DatabaseHelpers.record_individual_actions(
                                    username, 'FOLLOW', 1,
                                    account_id=account_id, session_id=self._get_session_id()
                                )
                            if interaction_result.get('story_viewed'):
                                self.stats_manager.increment('stories_watched')
                                # Record STORY_WATCH in database
                                DatabaseHelpers.record_individual_actions(
                                    username, 'STORY_WATCH', 1,
                                    account_id=account_id, session_id=self._get_session_id()
                                )
                            if interaction_result.get('commented'):
                                self.stats_manager.increment('comments')
                                # Record COMMENT in database
                                DatabaseHelpers.record_individual_actions(
                                    username, 'COMMENT', 1,
                                    account_id=account_id, session_id=self._get_session_id()
                                )
                        
                    except Exception as e:
                        self.logger.error(f"Error interacting with @{username}: {e}")
                        stats['errors'] += 1
                        self.stats_manager.add_error(f"Interaction error @{username}: {str(e)}")
                        continue
                    
                    self.stats_manager.display_stats(current_profile=username)
                    
                    # Delay before next profile (if not reached goal yet)
                    if stats['processed'] < max_profiles_to_interact:
                        delay = random.randint(*config['interaction_delay_range'])
                        self.logger.debug(f"Delay {delay}s before next interaction")
                        time.sleep(delay)
                    
                except Exception as e:
                    self.logger.error(f"Critical error @{username}: {e}")
                    stats['errors'] += 1
                    self.stats_manager.add_error(f"Critical error @{username}: {str(e)}")
                    
                    if session_id and target_username:
                        self._update_checkpoint_index(i)
        
        finally:
            if session_id and target_username:
                self._cleanup_checkpoint()
        
        self.logger.info(f"Interactions completed: {stats}")
        
        self.stats_manager.display_final_stats(workflow_name="FOLLOWERS")
        
        real_stats = self.stats_manager.to_dict()
        return {
            'processed': real_stats.get('profiles_visited', 0),
            'liked': real_stats.get('likes', 0),
            'followed': real_stats.get('follows', 0),
            'stories_viewed': real_stats.get('stories_watched', 0),
            'comments': real_stats.get('comments', 0),
            'errors': real_stats.get('errors', 0),
            'skipped': stats.get('skipped', 0),
            'resumed_from_checkpoint': stats.get('resumed_from_checkpoint', False)
        }
