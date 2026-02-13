"""Legacy followers workflow: interact with a pre-scraped list of followers."""

import time
import random
from typing import Dict, Any, List

from ....common import DatabaseHelpers
from .....core.ipc import IPCEmitter


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
                    IPCEmitter.emit_profile_visit(username)
                    
                    self._random_sleep()
                    
                    # === UNIFIED PROFILE PROCESSING ===
                    source_name = getattr(self.automation, 'target_username', 'unknown') if self.automation else 'unknown'
                    result = self._process_profile_on_screen(
                        username, config,
                        source_type='FOLLOWER', source_name=source_name,
                        account_id=account_id, session_id=self._get_session_id()
                    )
                    
                    if result.was_error:
                        stats['errors'] += 1
                        self.stats_manager.increment('errors')
                        continue
                    
                    if result.was_private:
                        stats['skipped'] += 1
                        self.stats_manager.increment('skipped')
                        continue
                    
                    if result.was_filtered:
                        stats['skipped'] += 1
                        self.stats_manager.increment('skipped')
                        continue
                    
                    try:
                        if result.actually_interacted:
                            if result.likes > 0:
                                stats['liked'] += 1
                                self.stats_manager.increment('likes', result.likes)
                            if result.follows > 0:
                                stats['followed'] += 1
                                self.stats_manager.increment('follows')
                            if result.stories > 0:
                                stats['stories_viewed'] += 1
                                self.stats_manager.increment('stories_watched')
                            if result.comments > 0:
                                if 'comments' not in stats:
                                    stats['comments'] = 0
                                stats['comments'] += 1
                                self.stats_manager.increment('comments')
                            
                            stats['processed'] += 1
                            self.stats_manager.increment('profiles_interacted')
                            self.human.record_interaction()
                        else:
                            self.logger.debug(f"@{username} visited but no interaction (probability)")
                            stats['skipped'] += 1
                        
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
