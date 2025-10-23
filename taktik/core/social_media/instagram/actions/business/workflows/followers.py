"""Business logic for Instagram follower interactions."""

from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
import time
import random
import json
import os
from pathlib import Path

from ...core.base_business_action import BaseBusinessAction
from taktik.core.database import get_db_service

from ..common import DatabaseHelpers


class FollowerBusiness(BaseBusinessAction):
    """Business logic for Instagram follower interactions."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "follower", init_business_modules=True)
        
        self.default_config = {
            'max_followers_to_extract': 50,
            'max_interactions_per_session': 20,
            'interaction_delay_range': (5, 12),
            'scroll_attempts': 5,
            'like_probability': 0.8,
            'follow_probability': 0.2,
            'story_probability': 0.15,
            'like_posts': True,
            'max_likes_per_profile': 4,
            'comment_probability': 0.05
        }
        self.checkpoint_dir = Path("temp/checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.current_checkpoint_file = None
        self.current_followers_list = []
        self.current_index = 0
    

    def extract_followers_from_profile(self, target_username: str, 
                                     max_followers: int = 50,
                                     filter_criteria: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        try:
            self.logger.info(f"Extracting followers from @{target_username} (max: {max_followers})")
            
            if not self.nav_actions.navigate_to_profile(target_username):
                self.logger.error(f"Failed to navigate to @{target_username}")
                return []
            
            # Vérifier que le profil est accessible
            if self.detection_actions.is_private_account():
                self.logger.warning(f"@{target_username} is a private account")
                return []
            
            if not self.nav_actions.open_followers_list():
                self.logger.error("Failed to open followers list")
                return []
            
            self._random_sleep()
            
            followers = self._extract_followers_with_scroll(max_followers)
            
            if not followers:
                self.logger.warning("No followers extracted")
                return []
            
            self.logger.info(f"{len(followers)} followers extracted from @{target_username}")
            
            if filter_criteria:
                filtered_followers = self._filter_followers(followers, filter_criteria)
                self.logger.info(f"{len(filtered_followers)}/{len(followers)} followers after filtering")
                return filtered_followers
            
            return followers
            
        except Exception as e:
            self.logger.error(f"Error extracting followers from @{target_username}: {e}")
            return []
    
    def _create_checkpoint(self, session_id: str, target_username: str, followers: List[Dict[str, Any]], current_index: int = 0) -> str:
        try:
            checkpoint_data = {
                'session_id': session_id,
                'target_username': target_username,
                'followers': followers,
                'current_index': current_index,
                'total_followers': len(followers),
                'created_at': time.time(),
                'status': 'active'
            }
            
            checkpoint_filename = f"checkpoint_{session_id}_{target_username}.json"
            checkpoint_path = self.checkpoint_dir / checkpoint_filename
            
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            
            self.current_checkpoint_file = str(checkpoint_path)
            self.current_followers_list = followers
            self.current_index = current_index
            
            self.logger.info(f"Checkpoint created: {checkpoint_filename} (index: {current_index}/{len(followers)})")
            return str(checkpoint_path)
            
        except Exception as e:
            self.logger.error(f"Error creating checkpoint: {e}")
            return None
    
    def _load_checkpoint(self, session_id: str, target_username: str) -> Dict[str, Any]:
        try:
            checkpoint_filename = f"checkpoint_{session_id}_{target_username}.json"
            checkpoint_path = self.checkpoint_dir / checkpoint_filename
            
            if not checkpoint_path.exists():
                return None
            
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            self.current_checkpoint_file = str(checkpoint_path)
            self.current_followers_list = checkpoint_data.get('followers', [])
            self.current_index = checkpoint_data.get('current_index', 0)
            
            self.logger.info(f"Checkpoint loaded: {checkpoint_filename} (index: {self.current_index}/{len(self.current_followers_list)})")
            return checkpoint_data
            
        except Exception as e:
            self.logger.error(f"Error loading checkpoint: {e}")
            return None
    
    def _update_checkpoint_index(self, new_index: int):
        try:
            if not self.current_checkpoint_file or not os.path.exists(self.current_checkpoint_file):
                return
            
            with open(self.current_checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            checkpoint_data['current_index'] = new_index
            checkpoint_data['updated_at'] = time.time()
            
            with open(self.current_checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            
            self.current_index = new_index
            self.logger.debug(f"Checkpoint updated: index {new_index}/{len(self.current_followers_list)}")
            
        except Exception as e:
            self.logger.error(f"Error updating checkpoint: {e}")
    
    def _cleanup_checkpoint(self):
        try:
            if self.current_checkpoint_file and os.path.exists(self.current_checkpoint_file):
                os.remove(self.current_checkpoint_file)
                self.logger.info(f"Checkpoint cleaned: {os.path.basename(self.current_checkpoint_file)}")
            
            self.current_checkpoint_file = None
            self.current_followers_list = []
            self.current_index = 0
            
        except Exception as e:
            self.logger.error(f"Error cleaning checkpoint: {e}")
    
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
        
        max_interactions = min(len(followers), config['max_interactions_per_session'])
        start_index = 0
        
        self.logger.info(f"Probabilities: like={config.get('like_probability', 'N/A')}, follow={config.get('follow_probability', 'N/A')}")
        self.logger.info(f"Config: {config}")
        self.logger.info(f"Max interactions: {max_interactions} (followers: {len(followers)}, config: {config['max_interactions_per_session']})")
        if session_id and target_username:
            checkpoint_data = self._load_checkpoint(session_id, target_username)
            if checkpoint_data:
                followers = checkpoint_data.get('followers', followers)
                start_index = checkpoint_data.get('current_index', 0)
                stats['resumed_from_checkpoint'] = True
                self.logger.info(f"Resuming from checkpoint at index {start_index}/{len(followers)}")
            else:
                self._create_checkpoint(session_id, target_username, followers, 0)
        
        self.logger.info(f"Starting interactions with {max_interactions} followers (start index: {start_index})")
        
        try:
            for i in range(start_index, min(len(followers), max_interactions)):
                # Vérifier si la session doit continuer (durée, limites, etc.)
                if hasattr(self, 'session_manager') and self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        break
                
                follower = followers[i]
                username = follower.get('username', '')
                
                try:
                    if not username:
                        stats['skipped'] += 1
                        self._update_checkpoint_index(i + 1)
                        continue
                    
                    self.logger.info(f"[{i+1}/{max_interactions}] Interacting with @{username}")
                    if session_id and target_username:
                        self._update_checkpoint_index(i)
                    
                    account_id = follower.get('source_account_id')
                    if account_id:
                        try:
                            if DatabaseHelpers.is_profile_already_processed(username, account_id, hours_limit=24*60):
                                self.logger.info(f"Profile @{username} already processed, skipped")
                                stats['skipped'] += 1
                                self.stats_manager.increment('skipped')
                                
                                # Enregistrer le profil skipped dans filtered_profile
                                try:
                                    session_id = self._get_session_id()
                                    source_name = getattr(self.automation, 'target_username', 'unknown')
                                    DatabaseHelpers.record_filtered_profile(
                                        username=username,
                                        reason='Already processed',
                                        source_type='FOLLOWER',
                                        source_name=source_name,
                                        account_id=account_id,
                                        session_id=session_id
                                    )
                                    self.logger.debug(f"Already processed profile @{username} recorded in API")
                                except Exception as e:
                                    self.logger.error(f"Error recording already processed profile @{username}: {e}")
                                
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
                    
                    if account_id:
                        try:
                            visit_notes = f"Profile visit during follower exploration"
                            DatabaseHelpers.mark_profile_as_processed(
                                username, visit_notes,
                                account_id=account_id,
                                session_id=self._get_session_id()
                            )
                            stats['processed'] += 1
                        except Exception as e:
                            self.logger.warning(f"Error marking @{username}: {e}")
                    try:
                        # ✅ Passer profile_data pour éviter une 2ème extraction
                        interaction_result = self._perform_profile_interactions(username, config, profile_data=profile_data)
                        
                        if interaction_result.get('liked'):
                            stats['liked'] += 1
                        if interaction_result.get('followed'):
                            stats['followed'] += 1
                        if interaction_result.get('story_viewed'):
                            stats['stories_viewed'] += 1
                        if interaction_result.get('commented'):
                            if 'comments' not in stats:
                                stats['comments'] = 0
                            stats['comments'] += 1
                        
                        self.stats_manager.increment('profiles_visited')
                        
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
                            if interaction_result.get('followed'):
                                self.stats_manager.increment('follows')
                            if interaction_result.get('story_viewed'):
                                self.stats_manager.increment('stories_watched')
                            if interaction_result.get('commented'):
                                self.stats_manager.increment('comments')
                        
                    except Exception as e:
                        self.logger.error(f"Error interacting with @{username}: {e}")
                        stats['errors'] += 1
                        self.stats_manager.add_error(f"Interaction error @{username}: {str(e)}")
                        continue
                    
                    self.stats_manager.display_stats(current_profile=username)
                    
                    if i < max_interactions - 1:
                        delay = random.randint(*config['interaction_delay_range'])
                        self.logger.debug(f"Delay {delay}s before next interaction")
                        time.sleep(delay)
                    
                except Exception as e:
                    self.logger.error(f"Critical error @{username}: {e}")
                    stats['errors'] += 1
                    self.stats_manager.add_error(f"Critical error @{username}: {str(e)}")
                    
                    if session_id and target_username:
                        self._update_checkpoint_index(i + 1)
                    
                    continue
        
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
    
    def interact_with_target_followers(self, target_username: str, 
                                     max_interactions: int = 10,
                                     like_posts: bool = True,
                                     max_likes_per_profile: int = 2,
                                     skip_processed: bool = True,
                                     automation=None,
                                     account_id: int = None,
                                     config: Dict[str, Any] = None) -> Dict[str, Any]:
        stats = {
            'interactions_performed': 0,
            'likes_performed': 0,
            'follows_performed': 0,
            'profiles_processed': 0,
            'profiles_visited': 0,
            'profiles_filtered': 0,
            'skipped': 0,
            'errors': 0
        }
        
        try:
            self.logger.info(f"Starting interactions with followers of @{target_username}")
            
            if not self.nav_actions.navigate_to_profile(target_username):
                self.logger.error(f"Failed to navigate to @{target_username}")
                return stats
            
            if self.detection_actions.is_private_account():
                self.logger.warning(f"@{target_username} is a private account")
                return stats
            
            profile_info = self.profile_business.get_complete_profile_info(target_username, navigate_if_needed=False)
            if profile_info:
                validation_result = self._validate_follower_limits(profile_info, max_interactions)
                if not validation_result['valid']:
                    self.logger.warning(f" {validation_result['warning']}")
                    if validation_result.get('suggestion'):
                        self.logger.info(f" Suggestion: {validation_result['suggestion']}")
                    if validation_result.get('adjusted_max'):
                        max_interactions = validation_result['adjusted_max']
                        self.logger.info(f" Adjusted max interactions to {validation_result['adjusted_max']}")
            
            if not self.nav_actions.open_followers_list():
                self.logger.error("Failed to open followers list")
                return stats
            
            self._random_sleep()
            
            followers_data = []
            processed_usernames = set()
            
            if config is None:
                config = {}
            
            interaction_config = {
                'max_interactions_per_session': max_interactions,
                'like_posts': like_posts,
                'max_likes_per_profile': max_likes_per_profile,
                'like_probability': config.get('like_probability', 0.8),
                'follow_probability': config.get('follow_probability', 0.2),
                'comment_probability': config.get('comment_probability', 0.1),
                'story_probability': config.get('story_probability', 0.2)
            }
            
            self.logger.debug(f"Interaction config received: {config}")
            self.logger.debug(f"Interaction config used: {interaction_config}")
            self.logger.info(f"Max interactions from CLI: {max_interactions}")
            
            self.logger.info(f"📥 Extraction des followers de @{target_username} en cours...")
            followers = self._extract_followers_with_scroll(max_interactions * 2, account_id, target_username)
            
            if not followers:
                self.logger.warning(f"❌ No followers extracted from @{target_username}")
                return stats
            
            self.logger.info(f"✅ {len(followers)} followers extracted from @{target_username}")
            self.logger.info(f"🎯 Processing {min(len(followers), max_interactions)} followers...")
            
            session_id_str = str(getattr(automation, 'current_session_id', 'unknown')) if automation else 'unknown'
            return self.interact_with_followers(
                followers[:max_interactions], 
                interaction_config,
                session_id=session_id_str,
                target_username=target_username
            )
            
        except Exception as e:
            self.logger.error(f"Error interacting with followers of @{target_username}: {e}")
            return {
                'interactions_performed': 0,
                'likes_performed': 0,
                'follows_performed': 0,
                'profiles_processed': 0,
                'error': str(e)
            }
    
    def _extract_followers_with_scroll(self, max_followers: int, account_id: int = None, target_username: str = None) -> List[Dict[str, Any]]:
        followers_data = []
        processed_usernames = set()
        scroll_attempts = 0
        max_scroll_attempts = 10
        
        def follower_callback(follower_username):
            if follower_username in processed_usernames:
                return True
            
            processed_usernames.add(follower_username)
            
            if account_id:
                try:
                    if DatabaseHelpers.is_profile_already_processed(follower_username, account_id, hours_limit=24*60):
                        self.logger.info(f"Profile @{follower_username} already processed, skipped")
                        return True
                except Exception as e:
                    self.logger.warning(f"Error checking @{follower_username}: {e}")
            
            follower_data = {
                'username': follower_username,
                'source_account_id': account_id,
                'source_username': target_username,
                'full_name': None,
                'is_verified': False,
                'is_private': False,
                'followers_count': None,
                'following_count': None,
                'timestamp': time.time()
            }
            followers_data.append(follower_data)
            
            if len(followers_data) >= max_followers:
                return False
            
            return True
        
        self.logger.info(f"Extracting with individual filtering (max: {max_followers})")
        
        while len(followers_data) < max_followers and scroll_attempts < max_scroll_attempts:
            current_usernames = self.content_business.extract_usernames_from_follow_list()
            
            if not current_usernames:
                self.logger.debug("No new followers found")
                scroll_attempts += 1
            else:
                new_found = 0
                for username in current_usernames:
                    if username:
                        continue_extraction = follower_callback(username)
                        if continue_extraction:
                            new_found += 1
                        else:
                            self.logger.info(f"{len(followers_data)} eligible followers collected")
                            return followers_data
                
                if new_found == 0:
                    scroll_attempts += 1
                    if scroll_attempts >= max_scroll_attempts:
                        self.logger.info(f"No new eligible followers found after {scroll_attempts} scrolls - end of list reached")
                        break
                else:
                    scroll_attempts = 0
                
                self.logger.debug(f"{new_found} new eligible, total: {len(followers_data)}")
            
            if len(followers_data) < max_followers:
                load_more_result = self.scroll_actions.check_and_click_load_more()
                if load_more_result:
                    self.logger.info("'Load more' button clicked, 25 new followers loaded")
                    self._human_like_delay('load_more')
                    scroll_attempts = 0
                elif load_more_result is False:
                    self.logger.info("End of followers list detected")
                    break
                elif load_more_result is None:
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
        
        self.logger.info(f"Extraction completed: {len(followers_data)} eligible followers")
        return followers_data
    
    def _filter_followers(self, followers: List[Dict[str, Any]], 
                         criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        filtered = []
        
        for follower in followers:
            username = follower.get('username', '')
            if not username:
                continue
            
            if criteria.get('exclude_bots', True):
                if self.utils.is_likely_bot_username(username):
                    continue
            
            filtered.append(follower)
        
        return filtered
    
    def _perform_profile_interactions(self, username: str, 
                                    config: Dict[str, Any],
                                    profile_data: dict = None) -> Dict[str, bool]:
        result = {
            'liked': False,
            'followed': False,
            'story_viewed': False,
            'commented': False
        }
        
        try:
            # ✅ Utiliser profile_data si déjà fourni (évite extraction inutile)
            if profile_data:
                profile_info = profile_data
            else:
                profile_info = self.profile_business.get_complete_profile_info(username=username, navigate_if_needed=False)
            
            if not profile_info:
                return result
            
            if profile_info.get('is_private', False):
                self.logger.debug(f"@{username} is a private profile")
            filter_criteria = config.get('filter_criteria', {})
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_info, filter_criteria
            )
            
            if not filter_result.get('suitable', False):
                reasons = filter_result.get('reasons', [])
                self.logger.info(f"@{username} filtered: {', '.join(reasons)}")
                
                posts_count = profile_info.get('posts_count', 0)
                min_posts = filter_criteria.get('min_posts', 0)
                if posts_count < min_posts:
                    self.logger.warning(f"@{username} has {posts_count} posts (minimum required: {min_posts})")
                
                result['filtered'] = True
                result['filter_reasons'] = reasons
                self.stats_manager.increment('profiles_filtered')
                return result
            
            like_probability = config.get('like_probability', 0.8)
            follow_probability = config.get('follow_probability', 0.2)
            comment_probability = config.get('comment_probability', 0.1)
            
            self.logger.debug(f"Probabilities: like={like_probability}, follow={follow_probability}, comment={comment_probability}")
            self.logger.debug(f"Config: {config}")
            
            like_roll = random.random()
            follow_roll = random.random()
            comment_roll = random.random()
            
            if follow_roll < follow_probability:
                self.logger.debug(f"Follow probability won ({follow_roll:.3f} < {follow_probability})")
                follow_result = self.click_actions.follow_user(username)
                if follow_result:
                    result['followed'] = True
                    try:
                        self.stats_manager.increment('follows')
                    except Exception as e:
                        self.logger.error(f"Critical error: Follow of @{username} cancelled - {e}")
                        self.logger.error(f"Security: Follow of @{username} cancelled to avoid quota leak")
                        
                        result['followed'] = False
                        result['error'] = f"Follow cancelled - API quotas not updated: {e}"
                        return result
                    
                    # REMOVED: L'enregistrement des follows est déjà géré dans base_business_action.py (centralisé)
                    
                    self._handle_follow_suggestions_popup()
                else:
                    self.logger.debug(f"Follow failed for @{username}")
            else:
                self.logger.debug(f"Follow probability lost ({follow_roll:.3f} >= {follow_probability})")
            
            should_comment = comment_roll < comment_probability and not profile_info.get('is_private', False)
            
            if like_roll < like_probability or should_comment:
                action_type = []
                if like_roll < like_probability:
                    action_type.append("like")
                if should_comment:
                    action_type.append("comment")
                
                self.logger.debug(f"Opening posts for: {', '.join(action_type)}")
                
                try:
                    custom_comments = config.get('custom_comments', [])
                    like_result = self.like_business.like_profile_posts(
                        username=username,
                        max_likes=3,
                        navigate_to_profile=False,
                        config=config,
                        profile_data=profile_info,
                        should_comment=should_comment,
                        custom_comments=custom_comments,
                        comment_template_category=config.get('comment_template_category', 'generic')
                    )
                    
                    likes_count = like_result.get('posts_liked', 0)
                    comments_count = like_result.get('posts_commented', 0)
                    
                    if likes_count > 0:
                        result['liked'] = True
                        result['likes_count'] = likes_count
                        self.logger.debug(f"Likes completed - {likes_count} posts liked")
                    
                    if comments_count > 0:
                        result['commented'] = True
                        self.logger.info(f"✅ {comments_count} comment(s) posted on @{username}'s posts")
                    
                    if likes_count == 0 and comments_count == 0:
                        self.logger.debug(f"No actions performed for @{username}")
                        
                except Exception as e:
                    self.logger.error(f"Error during post interactions for @{username}: {e}")
            else:
                if like_roll >= like_probability:
                    self.logger.debug(f"Like probability lost ({like_roll:.3f} >= {like_probability})")
                if comment_roll >= comment_probability:
                    self.logger.debug(f"Comment probability lost ({comment_roll:.3f} >= {comment_probability})")
            
            if random.random() < config.get('story_probability', 0.3):
                if self._view_stories(username):
                    result['story_viewed'] = True
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error interacting with @{username}: {e}")
            return result
    
    def _view_stories(self, username: str, like_stories: bool = False) -> Optional[Dict[str, int]]:
        try:
            if not self.detection_actions.has_stories():
                return None
            
            if self.click_actions.click_story_ring():
                self._human_like_delay('story_load')
                
                stories_viewed = 0
                stories_liked = 0
                
                for _ in range(3):
                    time.sleep(random.uniform(2, 5))
                    stories_viewed += 1
                    
                    if like_stories:
                        try:
                            if self.click_actions.like_story():
                                stories_liked += 1
                                self.logger.debug(f"Story liked")
                        except Exception as e:
                            self.logger.debug(f"Error liking story: {e}")
                    
                    if not self.nav_actions.navigate_to_next_story():
                        break
                
                self.device.back()
                self._human_like_delay('navigation')
                
                if stories_viewed > 0:
                    self.logger.debug(f"{stories_viewed} stories viewed, {stories_liked} liked")
                    return {
                        'stories_viewed': stories_viewed,
                        'stories_liked': stories_liked
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error viewing stories @{username}: {e}")
            return None
    
    def get_session_stats(self) -> Dict[str, Any]:
        return self.stats_manager.get_summary()
    
    def _validate_follower_limits(self, profile_info: Dict[str, Any], requested_interactions: int) -> Dict[str, Any]:
        available_followers = profile_info.get('followers_count', 0)
        
        result = {
            'valid': True,
            'warning': None,
            'suggestion': None,
            'adjusted_max': None
        }
        
        if available_followers == 0:
            result['valid'] = False
            result['warning'] = "Profile has no followers, cannot extract followers"
            result['suggestion'] = "Choose a profile with followers"
            return result
        
        if requested_interactions > available_followers:
            result['valid'] = False
            result['warning'] = f"Requested {requested_interactions} interactions but only {available_followers} followers available"
            result['suggestion'] = f"Automatically adjusting to maximum {available_followers} interactions"
            result['adjusted_max'] = available_followers
        
        return result