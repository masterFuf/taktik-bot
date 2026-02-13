"""Multi-target followers workflow: extract from multiple targets then interact."""

import time
from typing import Dict, Any, List, Optional


class FollowerMultiTargetWorkflowMixin:
    """Mixin: interact_with_target_followers — multi-target extraction + interaction."""

    def interact_with_target_followers(self, target_username: str = None, target_usernames: List[str] = None,
                                     max_interactions: int = 10,
                                     like_posts: bool = True,
                                     max_likes_per_profile: int = 2,
                                     skip_processed: bool = True,
                                     automation=None,
                                     account_id: int = None,
                                     config: Dict[str, Any] = None) -> Dict[str, Any]:
        # Support both single and multi-target
        if target_usernames is None:
            target_usernames = [target_username] if target_username else []
        
        if not target_usernames:
            self.logger.error("No target username(s) provided")
            return {}
        
        if len(target_usernames) > 1:
            self.logger.info(f"🎯 Multi-target mode: {len(target_usernames)} targets configured")
        
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
        
        if config is None:
            config = {}
        
        interaction_config = {
            'max_interactions_per_session': max_interactions,
            'like_posts': like_posts,
            'max_likes_per_profile': max_likes_per_profile,
            'like_probability': config.get('like_probability', 0.8),
            'follow_probability': config.get('follow_probability', 0.2),
            'comment_probability': config.get('comment_probability', 0.1),
            'story_probability': config.get('story_probability', 0.2),
            'filter_criteria': config.get('filter_criteria', config.get('filters', {}))
        }
        
        # Démarrer la phase de scraping
        if self.session_manager:
            self.session_manager.start_scraping_phase()
        
        # Extract followers from multiple targets
        all_followers = []
        for target_idx, target_username in enumerate(target_usernames):
            try:
                self.logger.info(f"📥 [{target_idx + 1}/{len(target_usernames)}] Extracting followers from @{target_username}...")
                
                if not self.nav_actions.navigate_to_profile(target_username):
                    self.logger.error(f"Failed to navigate to @{target_username}, skipping")
                    continue
                
                if self.detection_actions.is_private_account():
                    self.logger.warning(f"@{target_username} is a private account, skipping")
                    continue
                
                # Get profile info to check follower count BEFORE opening list
                profile_info = self.profile_business.get_complete_profile_info(target_username, navigate_if_needed=False)
                total_followers_count = profile_info.get('followers_count', 0) if profile_info else 0
                
                if total_followers_count > 0:
                    self.logger.info(f"📊 @{target_username} has {total_followers_count} followers")
                
                if not self.nav_actions.open_followers_list():
                    self.logger.error(f"Failed to open followers list for @{target_username}, skipping")
                    continue
                
                self._random_sleep()
                
                # Calculate how many more followers we need
                remaining_needed = (max_interactions * 2) - len(all_followers)
                if remaining_needed <= 0:
                    self.logger.info(f"✅ Target reached: {len(all_followers)} followers collected")
                    break
                
                # Adjust extraction limit based on profile's actual follower count
                extraction_limit = remaining_needed
                if total_followers_count > 0:
                    max_available = int(total_followers_count * 0.9)
                    extraction_limit = min(remaining_needed, max_available)
                    self.logger.info(f"🎯 Extraction limit adjusted to {extraction_limit} (profile has ~{total_followers_count} followers)")
                
                followers = self._extract_followers_with_scroll(
                    extraction_limit, 
                    account_id, 
                    target_username,
                    max_followers_count=total_followers_count
                )
                
                if followers:
                    all_followers.extend(followers)
                    self.logger.info(f"✅ {len(followers)} followers extracted from @{target_username} (total: {len(all_followers)})")
                else:
                    self.logger.warning(f"⚠️ No followers extracted from @{target_username}")
                
                # Check if we have enough followers
                if len(all_followers) >= max_interactions * 2:
                    self.logger.info(f"🎯 Target reached: {len(all_followers)} followers collected")
                    break
                    
            except Exception as e:
                self.logger.error(f"Error extracting from @{target_username}: {e}")
                continue
        
        # Terminer le scraping et démarrer les interactions
        if self.session_manager:
            self.session_manager.end_scraping_phase()
            self.session_manager.start_interaction_phase()
        
        if not all_followers:
            self.logger.warning(f"❌ No followers extracted from any target")
            return stats
        
        self.logger.info(f"✅ Total: {len(all_followers)} followers extracted from {len(target_usernames)} target(s)")
        self.logger.info(f"🎯 Processing {min(len(all_followers), max_interactions)} followers...")
        
        try:
            session_id_str = str(getattr(automation, 'current_session_id', 'unknown')) if automation else 'unknown'
            return self.interact_with_followers(
                all_followers[:max_interactions], 
                interaction_config,
                session_id=session_id_str,
                target_username=target_usernames[0]  # Use first target for checkpoint naming
            )
            
        except Exception as e:
            self.logger.error(f"Error during interactions: {e}")
            return {
                'interactions_performed': 0,
                'likes_performed': 0,
                'follows_performed': 0,
                'profiles_processed': 0,
                'error': str(e)
            }
