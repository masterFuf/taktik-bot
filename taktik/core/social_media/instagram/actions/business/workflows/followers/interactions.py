"""Profile interaction and filtering logic for the followers workflow."""

from typing import Dict, Any, Optional


class FollowerInteractionsMixin:
    """Mixin: profile interactions, stories, validation — specific to followers."""
    
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
            
            # === FILTERING (specific to followers workflow) ===
            filter_criteria = config.get('filter_criteria', config.get('filters', {}))
            
            self.logger.debug(f"Filter criteria for @{username}: {filter_criteria}")
            
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
            
            # === INTERACTIONS (delegated to unified method) ===
            # Note: record_profile_processed est appelé dans interact_with_followers_direct
            # SEULEMENT après qu'une interaction réelle ait eu lieu (actually_interacted=True)
            interaction = self._perform_interactions_on_profile(username, config, profile_data=profile_info)
            
            # Convert unified result dict to boolean format expected by callers
            if interaction.get('likes', 0) > 0:
                result['liked'] = True
                result['likes_count'] = interaction['likes']
            if interaction.get('follows', 0) > 0:
                result['followed'] = True
            if interaction.get('stories', 0) > 0:
                result['story_viewed'] = True
            if interaction.get('stories_liked', 0) > 0:
                result['story_liked'] = True
            if interaction.get('comments', 0) > 0:
                result['commented'] = True
            if interaction.get('error'):
                result['error'] = interaction['error']
            
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
                    self._human_like_delay(2, 5)
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
        return self._validate_resource_limits(
            available=profile_info.get('followers_count', 0),
            requested=requested_interactions,
            resource_name="followers"
        )
