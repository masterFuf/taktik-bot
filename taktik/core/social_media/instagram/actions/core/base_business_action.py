import time
import random
from typing import Optional, List, Dict, Any
from loguru import logger

from .base_action import BaseAction
from ..atomic.navigation_actions import NavigationActions
from ..atomic.detection_actions import DetectionActions
from ..atomic.click_actions import ClickActions
from ..atomic.scroll_actions import ScrollActions
from ..base_stats import BaseStatsManager
from ...ui.selectors import (
    POPUP_SELECTORS, POST_SELECTORS, DETECTION_SELECTORS, 
    NAVIGATION_SELECTORS, PROFILE_SELECTORS, BUTTON_SELECTORS
)
from ...ui.extractors import InstagramUIExtractors


class BaseBusinessAction(BaseAction):
    def __init__(self, device, session_manager=None, automation=None, module_name="business", 
                 init_business_modules=False):
        super().__init__(device)
        self.session_manager = session_manager
        self.automation = automation
        self.logger = logger.bind(module=f"instagram-{module_name}-business")
        
        self.popup_selectors = POPUP_SELECTORS
        self.post_selectors = POST_SELECTORS
        self.detection_selectors = DETECTION_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.profile_selectors = PROFILE_SELECTORS
        self.button_selectors = BUTTON_SELECTORS
        
        self.selectors = DETECTION_SELECTORS
        
        self.ui_extractors = InstagramUIExtractors(device)
        
        self._init_atomic_actions()
        
        self.stats_manager = BaseStatsManager(module_name)
        
        if automation and hasattr(automation, 'active_account_id'):
            self.active_account_id = automation.active_account_id
        else:
            self.active_account_id = 1
        
        if init_business_modules:
            self._init_business_modules()
        
        self.default_config = {}
    
    def _init_atomic_actions(self):
        self.nav_actions = NavigationActions(self.device)
        self.detection_actions = DetectionActions(self.device)
        self.click_actions = ClickActions(self.device)
        self.scroll_actions = ScrollActions(self.device)
    
    def _init_business_modules(self):
        from ..business.management.profile import ProfileBusiness
        from ..business.management.content import ContentBusiness
        from ..business.management.filtering import FilteringBusiness
        from ..business.actions.like import LikeBusiness
        from ..business.actions.comment import CommentBusiness
        
        self.profile_business = ProfileBusiness(self.device, self.session_manager)
        self.content_business = ContentBusiness(self.device, self.session_manager)
        self.filtering_business = FilteringBusiness(self.device, self.session_manager)
        self.like_business = LikeBusiness(self.device, self.session_manager, self.automation)
        self.comment_business = CommentBusiness(self.device, self.session_manager, self.automation)
        
    def _get_account_id(self) -> Optional[int]:
        if hasattr(self, 'automation') and self.automation:
            return getattr(self.automation, 'active_account_id', None)
        return None
    
    def _get_session_id(self) -> Optional[int]:
        if hasattr(self, 'automation') and self.automation:
            return getattr(self.automation, 'current_session_id', None)
        return None
    
    def _record_action(self, username: str, action_type: str, count: int = 1) -> bool:
        """
        Record an action in the database and emit IPC event for WorkflowAnalyzer.
        Centralized method to avoid code duplication across business actions.
        
        Args:
            username: Target username
            action_type: Type of action (LIKE, FOLLOW, UNFOLLOW, STORY_WATCH, STORY_LIKE, COMMENT, etc.)
            count: Number of actions to record
            
        Returns:
            True if recording succeeded, False otherwise
        """
        try:
            from ..business.common.database_helpers import DatabaseHelpers
            
            account_id = self._get_account_id()
            session_id = self._get_session_id()
            
            if not account_id:
                self.logger.warning(f"Cannot record {action_type} - no account_id")
                return False
            
            DatabaseHelpers.record_individual_actions(
                username=username,
                action_type=action_type,
                count=count,
                account_id=account_id,
                session_id=session_id
            )
            self.logger.debug(f"✅ {count} {action_type} action(s) recorded for @{username}")
            
            # Emit IPC event for WorkflowAnalyzer (if bridge is available)
            try:
                from bridges.instagram.desktop_bridge import send_instagram_action
                send_instagram_action(action_type.lower(), username, {"count": count})
            except ImportError:
                pass  # Bridge not available (CLI mode)
            except Exception:
                pass  # Ignore IPC errors
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to record {action_type} for @{username}: {e}")
            return False
    
    def _is_likers_popup_open(self) -> bool:
        # First check if we're in comments view (to avoid false positives)
        if self._is_comments_view_open():
            self.logger.debug("⚠️ Comments view detected, not likers popup")
            return False
        
        for indicator in self.popup_selectors.likers_popup_indicators:
            if self._is_element_present([indicator]):
                return True
        return False
    
    def _is_comments_view_open(self) -> bool:
        """Check if we're in the comments view instead of likers popup."""
        for indicator in self.popup_selectors.comments_view_indicators:
            if self._is_element_present([indicator]):
                return True
        return False
    
    def _close_likers_popup(self):
        try:
            for _ in range(5):
                if not self._is_likers_popup_open():
                    break
                self._close_popup_by_swipe_down()
                time.sleep(1.2)
            self._human_like_delay('popup_close')
        except:
            pass
    
    def _close_popup_by_swipe_down(self) -> bool:
        try:
            handle_element = self.device.xpath(self.popup_selectors.drag_handle_selector)
            
            if handle_element.exists:
                bounds = handle_element.info.get('bounds', {})
                if bounds:
                    handle_y = (bounds.get('top', 710) + bounds.get('bottom', 710)) // 2
                    center_x = (bounds.get('left', 492) + bounds.get('right', 588)) // 2
                    
                    self.logger.debug(f"📍 Handle detected at Y={handle_y}, X={center_x}")
                    
                    screen_height = self.device.info.get('displayHeight', 1920)
                    end_y = int(screen_height * 0.95)
                    
                    self.device.swipe_coordinates(center_x, handle_y, center_x, end_y, duration=0.3)
                    self.logger.debug(f"✅ Swipe to close: ({center_x}, {handle_y}) → ({center_x}, {end_y})")
                    return True
            
            screen_info = self.device.info
            center_x = screen_info.get('displayWidth', 1080) // 2
            handle_y = int(screen_info.get('displayHeight', 1920) * 0.37)
            end_y = int(screen_info.get('displayHeight', 1920) * 0.95)
            self.device.swipe_coordinates(center_x, handle_y, center_x, end_y, duration=0.3)
            return True
        except Exception as e:
            self.logger.debug(f"❌ Error closing popup: {e}")
            return False
    
    
    def _get_filter_criteria_from_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        filter_criteria = config.get('filter_criteria', config.get('filters', {}))
        
        return {
            'min_followers': filter_criteria.get('min_followers', config.get('min_followers', 0)),
            'max_followers': filter_criteria.get('max_followers', config.get('max_followers', 100000)),
            'min_posts': filter_criteria.get('min_posts', config.get('min_posts', 3)),
            'max_following': filter_criteria.get('max_following', config.get('max_following', 10000)),
            'allow_private': not filter_criteria.get('skip_private', config.get('skip_private', True)),
            'max_followers_following_ratio': filter_criteria.get('max_followers_following_ratio', 
                                                                 config.get('max_followers_following_ratio', 10))
        }
    
    def _determine_interactions_from_config(self, config: Dict[str, Any]) -> List[str]:
        interactions = []
        
        # Support both percentage (0-100) and probability (0.0-1.0) formats
        def get_percentage(key_percentage: str, key_probability: str) -> float:
            """Get percentage value, supporting both formats"""
            if key_percentage in config:
                return config[key_percentage]
            if key_probability in config:
                # Convert probability (0.0-1.0) to percentage (0-100)
                return config[key_probability] * 100
            return 0
        
        like_pct = get_percentage('like_percentage', 'like_probability')
        follow_pct = get_percentage('follow_percentage', 'follow_probability')
        comment_pct = get_percentage('comment_percentage', 'comment_probability')
        story_pct = get_percentage('story_watch_percentage', 'story_probability')
        story_like_pct = get_percentage('story_like_percentage', 'story_like_probability')
        
        if random.randint(1, 100) <= like_pct:
            interactions.append('like')
        
        if random.randint(1, 100) <= follow_pct:
            interactions.append('follow')
        
        if random.randint(1, 100) <= comment_pct:
            interactions.append('comment')
        
        if random.randint(1, 100) <= story_pct:
            interactions.append('story')
        
        if random.randint(1, 100) <= story_like_pct:
            interactions.append('story_like')
        
        return interactions
    
    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.error(f"❌ Cannot navigate to @{username}")
                return None
            
            profile_info = self.profile_business.get_complete_profile_info(username, navigate_if_needed=False)
            if not profile_info:
                self.logger.error(f"❌ Cannot get profile info for @{username}")
                return None
            
            if profile_info.get('is_private', False):
                self.logger.info(f"⏭️ Private profile @{username} - SKIP immediately")
                
                if hasattr(self, 'stats_manager'):
                    self.stats_manager.increment('private_profiles')
                
                return None
            
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_info, 
                self._get_filter_criteria_from_config(config)
            )
            
            if not filter_result['suitable']:
                reason = filter_result.get('reason', 'Criteria not met')
                reasons = filter_result.get('reasons', [reason])
                self.logger.info(f"🚫 @{username} filtered: {reason}")
                
                if hasattr(self, 'stats_manager'):
                    if 'privé' in reason.lower() or 'private' in reason.lower():
                        self.stats_manager.increment('private_profiles')
                    else:
                        self.stats_manager.increment('profiles_filtered')
                
                try:
                    from ..business.common.database_helpers import DatabaseHelpers
                    reasons_text = ', '.join(reasons) if reasons else reason
                    
                    source_type = 'HASHTAG' if 'hashtag' in self.logger._context.get('module', '') else 'POST_URL'
                    source_name = config.get('source', 'unknown')
                    
                    DatabaseHelpers.record_filtered_profile(
                        username=username,
                        reason=reasons_text,
                        source_type=source_type,
                        source_name=source_name,
                        account_id=self._get_account_id(),
                        session_id=self._get_session_id()
                    )
                    self.logger.debug(f"✅ Filtered profile @{username} recorded in API")
                except Exception as e:
                    self.logger.error(f"❌ Error recording filtered profile @{username}: {e}")
                
                return None
            
            # Note: record_profile_processed est appelé dans interact_with_followers_direct
            # SEULEMENT après qu'une interaction réelle ait eu lieu (actually_interacted=True)
            
            interactions_to_do = self._determine_interactions_from_config(config)
            self.logger.debug(f"🎯 Planned interactions for @{username}: {interactions_to_do}")
            
            result = {'likes': 0, 'follows': 0, 'comments': 0, 'stories': 0, 'stories_liked': 0}
            
            should_comment = 'comment' in interactions_to_do
            should_like = 'like' in interactions_to_do
            
            if should_like or should_comment:
                likes_result = self.like_business.like_profile_posts(
                    username, 
                    max_likes=config.get('max_likes_per_profile', 3),
                    config={'randomize_order': True},
                    should_comment=should_comment,
                    custom_comments=config.get('custom_comments', []),
                    comment_template_category=config.get('comment_template_category', 'generic'),
                    max_comments=config.get('max_comments_per_profile', 1),
                    navigate_to_profile=False,  # Already on profile from _interact_with_user
                    profile_data=profile_info  # Pass existing profile data to avoid re-fetching
                )
                likes_count = likes_result.get('posts_liked', 0)
                comments_count = likes_result.get('posts_commented', 0)
                result['likes'] = likes_count
                result['comments'] = comments_count
                
                if comments_count > 0:
                    from ..business.common.database_helpers import DatabaseHelpers
                    account_id = self._get_account_id()
                    session_id = self._get_session_id()
                    DatabaseHelpers.record_individual_actions(username, 'COMMENT', comments_count, account_id, session_id)
            
            if 'follow' in interactions_to_do:
                follow_result = self.click_actions.follow_user(username)
                if follow_result:
                    result['follows'] = 1
                    
                    from ..business.common.database_helpers import DatabaseHelpers
                    account_id = self._get_account_id()
                    session_id = self._get_session_id()
                    DatabaseHelpers.record_individual_actions(username, 'FOLLOW', 1, account_id, session_id)
            
            if 'story' in interactions_to_do or 'story_like' in interactions_to_do:
                should_like_stories = 'story_like' in interactions_to_do
                
                if hasattr(self, 'follower_business'):
                    story_result = self.follower_business._view_stories(username, like_stories=should_like_stories)
                    if story_result:
                        result['stories'] = story_result.get('stories_viewed', 1)
                        
                        from ..business.common.database_helpers import DatabaseHelpers
                        account_id = self._get_account_id()
                        session_id = self._get_session_id()
                        
                        if should_like_stories and story_result.get('stories_liked', 0) > 0:
                            result['stories_liked'] = story_result.get('stories_liked', 0)
                            DatabaseHelpers.record_individual_actions(username, 'STORY_LIKE', 
                                                                      story_result['stories_liked'], 
                                                                      account_id, session_id)
                        else:
                            DatabaseHelpers.record_individual_actions(username, 'STORY_WATCH', 1, 
                                                                      account_id, session_id)
            
            return result if any(result.values()) else None
            
        except Exception as e:
            self.logger.error(f"❌ Error interacting with @{username}: {e}")
            return None
    
    def _extract_likers_from_regular_post(self, max_interactions: int = None, 
                                         multiply_by: int = 2) -> List[str]:
        try:
            like_count_element = self.ui_extractors.find_like_count_element(logger_instance=self.logger)
            if not like_count_element:
                self.logger.warning("⚠️ Like count not found")
                return []
            
            self.logger.debug("👆 Clicking on like count")
            like_count_element.click()
            self._human_like_delay('popup_open')
            
            if max_interactions is None:
                max_interactions = getattr(self, 'current_max_interactions', 
                                          self.default_config.get('max_interactions', 20))
            
            target_users = max_interactions * multiply_by
            
            if hasattr(self, 'current_max_interactions'):
                original_max = self.current_max_interactions
                self.current_max_interactions = target_users
                likers = self.ui_extractors.extract_usernames_from_likers_popup(
                    current_max_interactions_attr=target_users,
                    automation=self.automation,
                    logger_instance=self.logger,
                    add_initial_sleep=False
                )
                self.current_max_interactions = original_max
            else:
                likers = self.ui_extractors.extract_usernames_from_likers_popup(
                    max_interactions=target_users,
                    automation=self.automation,
                    logger_instance=self.logger,
                    add_initial_sleep=True
                )
            
            self._close_likers_popup()
            
            return likers
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting likers from regular post: {e}")
            return []
    
    def _extract_likers_from_reel(self, max_interactions: int = None, 
                                 multiply_by: int = 2) -> List[str]:
        try:
            like_element = None
            found_selector = None
            
            for selector in self.post_selectors.reel_like_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    if not elements:
                        continue
                    
                    for element in elements:
                        text = element.get_text() if hasattr(element, 'get_text') else (
                            element.text if hasattr(element, 'text') else ""
                        )
                        
                        if text and self.ui_extractors.is_like_count_text(text):
                            like_element = element
                            found_selector = selector
                            self.logger.info(f"✅ Reel like count found: '{text}' via {selector}")
                            break
                    
                    if like_element:
                        break
                        
                except Exception as e:
                    self.logger.debug(f"Error testing selector {selector}: {e}")
                    continue
            
            if not like_element:
                self.logger.warning("⚠️ Reel like count not found with any selector")
                return []
            
            like_element.click()
            self._human_like_delay('popup_open')
            
            if max_interactions is None:
                max_interactions = getattr(self, 'current_max_interactions', 
                                          self.default_config.get('max_interactions', 20))
            
            target_users = max_interactions * multiply_by
            
            if hasattr(self, 'current_max_interactions'):
                original_max = self.current_max_interactions
                self.current_max_interactions = target_users
                likers = self.ui_extractors.extract_usernames_from_likers_popup(
                    current_max_interactions_attr=target_users,
                    automation=self.automation,
                    logger_instance=self.logger,
                    add_initial_sleep=False
                )
                self.current_max_interactions = original_max
            else:
                likers = self.ui_extractors.extract_usernames_from_likers_popup(
                    max_interactions=target_users,
                    automation=self.automation,
                    logger_instance=self.logger,
                    add_initial_sleep=True
                )
            
            self._close_likers_popup()
            
            return likers
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting likers from Reel: {e}")
            return []
    
    def _handle_follow_suggestions_popup(self):
        try:
            self.logger.debug("🔍 Checking for suggestions popup after follow...")
            
            popup_detected = False
            for selector in self.popup_selectors.follow_suggestions_indicators:
                if self.device.xpath(selector).exists:
                    popup_detected = True
                    self.logger.debug(f"✅ Suggestions popup detected: {selector}")
                    break
            
            if popup_detected:
                # Swipe UP to scroll back to top of profile where posts are visible
                # This hides the "Suggested for you" section by scrolling past it
                from ..core.device_facade import Direction
                self.logger.debug("📜 Scrolling up to hide suggestions section...")
                self.device.swipe(Direction.DOWN, scale=0.5)  # DOWN = finger moves down = content goes UP
                time.sleep(0.3)
                self.device.swipe(Direction.DOWN, scale=0.5)  # Second swipe to ensure we're at top
                time.sleep(0.3)
                self.logger.debug("✅ Suggestions section hidden by scrolling up")
            else:
                self.logger.debug("ℹ️ No suggestions popup detected")
                
        except Exception as e:
            self.logger.debug(f"Error handling suggestions popup: {e}")
    
    
    def _is_reel_post(self) -> bool:
        return self.ui_extractors.is_reel_post(logger_instance=self.logger)
    
    def _get_account_id(self) -> Optional[int]:
        """Get the active account ID from automation or fallback to default."""
        if self.automation and hasattr(self.automation, 'active_account_id'):
            return self.automation.active_account_id
        return self.active_account_id
    
    def _get_session_id(self) -> Optional[int]:
        """Get the current session ID from automation or session_manager."""
        if self.automation and hasattr(self.automation, 'current_session_id'):
            return self.automation.current_session_id
        if self.session_manager and hasattr(self.session_manager, 'session_id'):
            return self.session_manager.session_id
        return None


# Export for easier import
__all__ = ['BaseBusinessAction']
