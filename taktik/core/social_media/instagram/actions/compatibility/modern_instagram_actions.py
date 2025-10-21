from typing import Dict, Any, List, Optional
from loguru import logger

from ..core.base_action import BaseAction
from ..base_stats import BaseStatsManager

from ..business.management.profile import ProfileBusiness
from ..business.management.content import ContentBusiness
from ..business.management.filtering import FilteringBusiness
from ..business.workflows.followers import FollowerBusiness
from ..business.workflows.hashtag import HashtagBusiness
from ..business.workflows.post_url import PostUrlBusiness
from ..business.actions.like import LikeBusiness
from ..business.actions.story import StoryBusiness
from ..business.system.license import LicenseBusiness
from ..business.system.config import ConfigBusiness


class ModernInstagramActions(BaseAction):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device)
        self.session_manager = session_manager
        self.automation = automation
        self.logger = logger.bind(module="modern-instagram-actions")
        
        self.stats = BaseStatsManager()
        
        self.profile_business = ProfileBusiness(device, session_manager)
        self.content_business = ContentBusiness(device, session_manager)
        self.filtering_business = FilteringBusiness(device)
        self.follower_business = FollowerBusiness(device, session_manager, automation)
        self.hashtag_business = HashtagBusiness(device, session_manager, automation)
        self.post_url_business = PostUrlBusiness(device, session_manager, automation)
        self.like_business = LikeBusiness(device, session_manager, automation)
        self.story_business = StoryBusiness(device, session_manager)
        self.license_business = LicenseBusiness(device, session_manager)
        self.config_business = ConfigBusiness(device, session_manager)
        
        self.logger.info("ModernInstagramActions initialized with BaseStatsManager and new architecture")
    
    def navigate_to_profile(self, username: str, deep_link_usage_percentage: int = 90) -> bool:
        self.logger.debug(f"[COMPAT] Navigating to @{username}")
        self.stats.increment('profiles_visited')
        
        try:
            result = self.profile_business.nav_actions.navigate_to_profile(
                username=username,
                deep_link_usage_percentage=deep_link_usage_percentage
            )
            
            if result:
                self.logger.debug(f"Navigation successful to @{username}")
                return True
            else:
                self.stats.add_error(f"Navigation failed for @{username}")
                return False
                
        except Exception as e:
            self.stats.add_error(f"Navigation error for @{username}: {str(e)}")
            self.logger.error(f"Navigation error @{username}: {e}")
            return False
    
    def get_profile_info(self, username: str = None) -> Optional[Dict[str, Any]]:
        self.logger.debug(f"[COMPAT] Extracting profile info: {username or 'current'}")
        
        try:
            profile_info = self.profile_business.get_complete_profile_info(
                username=username,
                navigate_if_needed=username is not None
            )
            
            if profile_info:
                self.stats.increment('profiles_interacted')
                self.logger.debug(f"Profile extracted: @{profile_info.get('username', 'unknown')}")
                return profile_info
            else:
                self.stats.add_error(f"Profile extraction failed for {username}")
                return None
                
        except Exception as e:
            self.stats.add_error(f"Profile extraction error: {str(e)}")
            self.logger.error(f"Profile extraction error: {e}")
            return None
    
    def follow_user(self, username: str) -> bool:
        self.logger.debug(f"[COMPAT] Follow @{username}")
        
        try:
            if not self.profile_business.nav_actions.navigate_to_profile(username):
                return False
            
            if self.profile_business.click_actions.follow_user():
                self.stats.increment('follows')
                self.logger.info(f"Follow successful: @{username}")
                return True
            else:
                self.stats.add_error(f"Follow failed for @{username}")
                return False
                
        except Exception as e:
            self.stats.add_error(f"Follow error for @{username}: {str(e)}")
            self.logger.error(f"Follow error @{username}: {e}")
            return False
    
    def like_post(self, post_index: int = 0) -> bool:
        self.logger.debug(f"[COMPAT] Like post #{post_index}")
        
        try:
            if self.like_business.like_current_post():
                self.stats.increment('likes')
                self.logger.info(f"Post liked: #{post_index}")
                return True
            else:
                self.stats.add_error(f"Like failed for post #{post_index}")
                return False
                
        except Exception as e:
            self.stats.add_error(f"Like error for post #{post_index}: {str(e)}")
            self.logger.error(f"Like error post #{post_index}: {e}")
            return False
    
    def get_followers_from_profile(self, username: str, max_followers: int = 100) -> List[str]:
        self.logger.debug(f"[COMPAT] Extracting followers @{username} (max: {max_followers})")
        
        try:
            followers = self.content_business.extract_followers_from_profile(
                username=username,
                max_followers=max_followers
            )
            
            self.stats.increment('profiles_visited')
            self.stats.set_value('followers_extracted', len(followers))
            
            self.logger.info(f"{len(followers)} followers extracted from @{username}")
            return followers
            
        except Exception as e:
            self.stats.add_error(f"Followers extraction error for @{username}: {str(e)}")
            self.logger.error(f"Followers extraction error @{username}: {e}")
            return []
    
    def filter_profile(self, profile_info: Dict[str, Any], 
                      criteria: Dict[str, Any] = None) -> Dict[str, Any]:
        self.logger.debug(f"[COMPAT] Filtering profile @{profile_info.get('username', 'unknown')}")
        
        try:
            if criteria is None:
                criteria = self.filtering_business.get_default_criteria("general")
            
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_info=profile_info,
                criteria=criteria
            )
            
            if filter_result['suitable']:
                self.stats.increment('profiles_interacted')
            else:
                self.stats.increment('profiles_filtered')
            
            return filter_result
            
        except Exception as e:
            self.stats.add_error(f"Profile filtering error: {str(e)}")
            self.logger.error(f"Profile filtering error: {e}")
            return {'suitable': False, 'reason': f'Filter error: {str(e)}'}
    
    def execute_target_workflow(self, target_username: str, max_interactions: int = 50) -> Dict[str, Any]:
        self.logger.info(f"[CLI] Starting target workflow: @{target_username}")
        self.stats.set_value('workflow_type', 'target')
        
        try:
            followers = self.get_followers_from_profile(target_username, max_interactions * 2)
            
            if not followers:
                return self._build_workflow_result("No followers extracted")
            
            suitable_profiles = []
            criteria = self.filtering_business.get_default_criteria("general")
            
            for username in followers[:max_interactions * 3]:
                profile_info = self.get_profile_info(username)
                if profile_info:
                    filter_result = self.filter_profile(profile_info, criteria)
                    if filter_result['suitable']:
                        suitable_profiles.append(username)
                        
                        if len(suitable_profiles) >= max_interactions:
                            break
            
            successful_interactions = 0
            for username in suitable_profiles:
                if self.follow_user(username):
                    if self.navigate_to_profile(username):
                        self.like_post(0)
                        successful_interactions += 1
                
                self._human_like_delay('navigation')
            
            return self._build_workflow_result(
                success=True,
                details={
                    'followers_extracted': len(followers),
                    'suitable_profiles': len(suitable_profiles),
                    'successful_interactions': successful_interactions
                }
            )
            
        except Exception as e:
            self.stats.add_error(f"Target workflow error: {str(e)}")
            return self._build_workflow_result(f"Workflow error: {str(e)}")
    
    def execute_hashtag_workflow(self, hashtag: str, max_interactions: int = 30) -> Dict[str, Any]:
        self.logger.info(f"[CLI] Starting hashtag workflow: #{hashtag}")
        self.stats.set_value('workflow_type', 'hashtag')
        
        try:
            posts = self.content_business.extract_hashtag_posts(
                hashtag=hashtag,
                max_posts=max_interactions * 2
            )
            
            if not posts:
                return self._build_workflow_result("No posts found for hashtag")
            
            unique_authors = []
            seen_authors = set()
            
            for post in posts:
                author = post.get('author_username')
                if author and author not in seen_authors:
                    unique_authors.append(author)
                    seen_authors.add(author)
                    
                    if len(unique_authors) >= max_interactions:
                        break
            
            successful_interactions = 0
            for author in unique_authors:
                profile_info = self.get_profile_info(author)
                if profile_info:
                    filter_result = self.filter_profile(profile_info)
                    if filter_result['suitable']:
                        if self.follow_user(author):
                            self.like_post(0)
                            successful_interactions += 1
                
                self._human_like_delay('navigation')
            
            return self._build_workflow_result(
                success=True,
                details={
                    'posts_found': len(posts),
                    'unique_authors': len(unique_authors),
                    'successful_interactions': successful_interactions
                }
            )
            
        except Exception as e:
            self.stats.add_error(f"Hashtag workflow error: {str(e)}")
            return self._build_workflow_result(f"Workflow error: {str(e)}")
    
    def execute_post_url_workflow(self, post_url: str, max_interactions: int = 20, **kwargs) -> Dict[str, Any]:
        self.logger.info(f"[CLI] Starting post URL workflow: {post_url}")
        self.logger.info(f"[CLI] Parameters received: max_interactions={max_interactions}, kwargs={kwargs}")
        self.stats.set_value('workflow_type', 'post_url')
        
        try:
            config = {
                'max_interactions': max_interactions,
                'like_percentage': kwargs.get('like_percentage', 70),
                'follow_percentage': kwargs.get('follow_percentage', 15),
                'comment_percentage': kwargs.get('comment_percentage', 5),
                'story_watch_percentage': kwargs.get('story_watch_percentage', 10),
                'max_likes_per_profile': kwargs.get('max_likes_per_profile', 3),
                'filter_criteria': {
                    'min_followers': kwargs.get('min_followers', 0),
                    'max_followers': kwargs.get('max_followers', 100000),
                    'min_posts': kwargs.get('min_posts', 3),
                    'max_following': kwargs.get('max_following', 10000),
                    'skip_private': not kwargs.get('allow_private', False)
                }
            }
            
            self.logger.info(f"Generated configuration: {config}")
            
            result = self.post_url_business.interact_with_post_likers(post_url, config)
            
            return self._build_workflow_result(
                success=result.get('success', False),
                details={
                    'users_found': result.get('users_found', 0),
                    'users_interacted': result.get('users_interacted', 0),
                    'likes_made': result.get('likes_made', 0),
                    'follows_made': result.get('follows_made', 0),
                    'comments_made': result.get('comments_made', 0),
                    'stories_watched': result.get('stories_watched', 0)
                }
            )
            
        except Exception as e:
            self.stats.add_error(f"Post URL workflow error: {str(e)}")
            return self._build_workflow_result(f"Workflow error: {str(e)}")
    
    def _build_workflow_result(self, success: bool = True, details: Dict[str, Any] = None, 
                               error_message: str = None) -> Dict[str, Any]:
        result = {
            'success': success,
            'stats': self.stats.to_dict(),
            'details': details or {},
            'error': error_message
        }
        
        self.stats.display_stats()
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        return self.stats.to_dict()
    
    def reset_stats(self) -> None:
        self.stats = BaseStatsManager()
        self.logger.info("Statistics reset")
    
    def display_stats(self) -> None:
        self.stats.display_stats()
