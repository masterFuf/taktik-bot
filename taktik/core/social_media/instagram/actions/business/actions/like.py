import time
import random
import re
from typing import Dict, List, Any, Optional
from loguru import logger

from ...core.base_business_action import BaseBusinessAction
from ..management.profile import ProfileBusiness

class LikeBusiness(BaseBusinessAction):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "like")
        
        from ....ui.selectors import (
            PROFILE_SELECTORS, NAVIGATION_SELECTORS, DEBUG_SELECTORS, POST_SELECTORS
        )
        self.profile_selectors = PROFILE_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.debug_selectors = DEBUG_SELECTORS
        self.post_selectors = POST_SELECTORS
        
        from ....ui.detectors.problematic_page import ProblematicPageDetector
        self.problematic_page_detector = ProblematicPageDetector(device, debug_mode=False)
        
        self.profile_business = ProfileBusiness(device, session_manager)
        
        self.default_config = {
            'like_delay_range': (2, 5),
            'navigation_delay_range': (1, 3),
            'skip_already_liked': True
        }
    
    def like_profile_posts(self, username: str, max_likes: int = 3, 
                          navigate_to_profile: bool = True,
                          config: dict = None,
                          profile_data: dict = None,
                          should_comment: bool = False,
                          custom_comments: list = None,
                          comment_template_category: str = 'generic',
                          max_comments: int = 1,
                          should_like: bool = True) -> dict:
        config = {**self.default_config, **(config or {})}
        
        stats = {
            'username': username,
            'posts_liked': 0,
            'posts_commented': 0,
            'posts_skipped': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            self.logger.info(f"Starting to like posts from @{username} (max: {max_likes})")
            
            if navigate_to_profile:
                if not self.nav_actions.navigate_to_profile(username):
                    self.logger.error(f"Failed to navigate to @{username}")
                    stats['errors'] += 1
                    return stats
            
            if profile_data:
                profile_info = profile_data
            else:
                profile_info = self.profile_business.get_complete_profile_info(username=username, navigate_if_needed=False)
            
            if not profile_info:
                self.logger.error(f"Failed to get profile info for @{username}")
                stats['errors'] += 1
                return stats
            
            if profile_info.get('is_private', False):
                self.logger.warning(f"@{username} is a private account")
                stats['errors'] += 1
                return stats
            
            sequential_stats = self.like_posts_with_sequential_scroll(
                username, max_likes, config, profile_data=profile_info,
                should_comment=should_comment, custom_comments=custom_comments,
                comment_template_category=comment_template_category, max_comments=max_comments,
                should_like=should_like
            )
            posts_liked = sequential_stats['posts_liked']
            posts_commented = sequential_stats.get('posts_commented', 0)
            stats['posts_liked'] = posts_liked
            stats['posts_commented'] = posts_commented
            stats['posts_seen'] = sequential_stats.get('posts_seen', 0)
            stats['method'] = sequential_stats.get('method', 'sequential_scroll')
            
            # Legacy grid method removed - sequential scroll is now the only method
            
            self.logger.debug(f"Checking session_manager: hasattr={hasattr(self, 'session_manager')}, session_manager={self.session_manager}, posts_liked={posts_liked}")
            if hasattr(self, 'session_manager') and self.session_manager and posts_liked > 0:
                try:
                    for i in range(posts_liked):
                        self.session_manager.record_action('like_posts', success=True, source=username)
                    self.logger.debug(f"Session stats recorded: {posts_liked} individual likes for @{username}")
                except Exception as e:
                    self.logger.error(f"CRITICAL FAILURE: Unable to record likes in API")
                    self.logger.error(f"SECURITY: {posts_liked} likes for @{username} cancelled to avoid quota leak")
                    
                    stats['posts_liked'] = 0
                    stats['success'] = False
                    
                    raise Exception(f"Likes cancelled for @{username} - API quota recording failed: {e}")
            else:
                self.logger.warning(f"Stats NOT recorded - Reason: session_manager={self.session_manager}, posts_liked={posts_liked}")
            
            if posts_liked > 0:
                self._record_action(username, 'LIKE', posts_liked)
            
            stats['success'] = stats['posts_liked'] > 0
            self.logger.info(f"Likes completed for @{username}: {stats['posts_liked']} posts liked")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"General error liking @{username}: {e}")
            stats['errors'] += 1
            return stats
    
    def like_posts_with_grid_method(self, username: str, max_likes: int = 3, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """DEPRECATED - This method is no longer used."""
        self.logger.warning("Grid method is deprecated and no longer available")
        return {
            'username': username,
            'posts_liked': 0,
            'success': False,
            'errors': 1,
            'method': 'deprecated'
        }

    def like_posts_with_sequential_scroll(self, username: str, max_likes: int = 3, config: dict = None, profile_data: dict = None,
                                         should_comment: bool = False, custom_comments: list = None,
                                         comment_template_category: str = 'generic', max_comments: int = 1,
                                         should_like: bool = True) -> dict:
        """Like posts with sequential scroll method.
        
        Args:
            should_like: If False, skip liking posts (only comment if should_comment is True)
        """
        config = {**self.default_config, **(config or {})}
        
        stats = {
            'username': username,
            'posts_liked': 0,
            'posts_commented': 0,
            'posts_seen': 0,
            'success': False,
            'errors': 0,
            'method': 'sequential_scroll'
        }
        
        try:
            self.logger.info(f"Sequential scroll method for @{username}")
            
            if profile_data:
                profile_info = profile_data
            else:
                profile_info = self.profile_business.get_complete_profile_info(username=username, navigate_if_needed=False)
            total_posts_on_profile = profile_info.get('posts_count', 0) if profile_info else 0
            
            if total_posts_on_profile > 0:
                max_posts_to_see = min(total_posts_on_profile, max_likes * 5)
                self.logger.info(f"Profile has {total_posts_on_profile} posts - viewing max {max_posts_to_see}")
            else:
                max_posts_to_see = max_likes * 5
                self.logger.debug(f"Post count unknown - max {max_posts_to_see} by default")
            
            posts_liked = 0
            posts_commented = 0
            posts_seen = 0
            
            if not self._open_first_post_of_profile():
                self.logger.error("Failed to open first post of profile")
                stats['errors'] += 1
                return stats
            
            self.logger.success("First post opened, starting sequential scroll")
            
            consecutive_identical_posts = 0
            seen_posts_signatures = set()
            unique_posts_seen = 0
            
            while posts_liked < max_likes and posts_seen < max_posts_to_see:
                posts_seen += 1
                stats['posts_seen'] = posts_seen
                
                time.sleep(0.3)
                
                try:
                    current_likes = self._extract_likes_count_from_ui()
                    current_comments = self._extract_comments_count_from_ui()
                    is_reel = self._is_current_post_reel()
                    
                    post_signature = f"{current_likes}_{current_comments}_{is_reel}"
                    
                    self.logger.debug(f"Extracted signature: {post_signature} | Already seen: {len(seen_posts_signatures)} posts")
                    
                    is_new_post = post_signature not in seen_posts_signatures
                    
                    if is_new_post:
                        seen_posts_signatures.add(post_signature)
                        unique_posts_seen += 1
                        consecutive_identical_posts = 0
                        
                        post_type = "Reel" if is_reel else "Post"
                        self.logger.info(f"{post_type} #{unique_posts_seen} UNIQUE (scroll #{posts_seen}) - {current_likes} likes, {current_comments} comments - Likes: {posts_liked}/{max_likes}")
                    else:
                        consecutive_identical_posts += 1
                        self.logger.debug(f"Already seen post (signature: {post_signature}) - scroll #{consecutive_identical_posts}/6")
                        
                        if consecutive_identical_posts >= 6:
                            self.logger.warning(f"End of feed detected after {unique_posts_seen} unique posts - stopping scroll")
                            break
                        
                        if posts_seen < max_posts_to_see:
                            if not self._navigate_to_next_post_in_sequence():
                                break
                        continue
                    
                except Exception as e:
                    self.logger.debug(f"Error extracting post metadata #{posts_seen}: {e}")
                    self.logger.info(f"Post #{posts_seen}/{max_posts_to_see} - Metadata unavailable - Likes: {posts_liked}/{max_likes}")
                    consecutive_identical_posts = 0
                
                if posts_liked >= max_likes:
                    self.logger.success(f"Goal reached: {posts_liked}/{max_likes} posts liked - stopping scroll")
                    break
                
                # Use should_like parameter to determine if we should attempt to like
                # This respects the user's like_probability setting from the workflow
                if should_like:
                    # Add some randomness to which posts we like (not all of them)
                    base_probability = 0.70
                    position_factor = 1.0
                    if unique_posts_seen <= 2:
                        position_factor = 0.8
                    elif unique_posts_seen <= 5:
                        position_factor = 1.0
                    else:
                        position_factor = 1.2
                    
                    final_probability = base_probability * position_factor
                    should_like_this_post = random.random() < final_probability
                    self.logger.debug(f"Post #{posts_seen}: like_probability={final_probability:.2f} (base={base_probability:.2f}, position_factor={position_factor:.1f})")
                else:
                    should_like_this_post = False
                    final_probability = 0.0
                    self.logger.debug(f"Post #{posts_seen}: liking disabled by config")
                
                if should_like_this_post and posts_liked < max_likes:
                    # Vérifier d'abord si le post est déjà liké
                    if self._is_post_already_liked():
                        self.logger.debug(f"Post #{posts_seen} already liked - skipping to avoid unlike")
                        stats['already_liked'] = stats.get('already_liked', 0) + 1
                    elif self.like_current_post():
                        posts_liked += 1
                        stats['posts_liked'] = posts_liked
                        self.logger.success(f"Post #{posts_seen} liked successfully ({posts_liked}/{max_likes})")
                        
                        if should_comment and posts_commented < max_comments:
                            try:
                                from .comment import CommentBusiness
                                comment_business = CommentBusiness(self.device, self.session_manager, self.automation)
                                comment_result = comment_business.comment_on_post(
                                    custom_comments=custom_comments,
                                    template_category=comment_template_category,
                                    config=config,
                                    username=username
                                )
                                if comment_result.get('commented'):
                                    posts_commented += 1
                                    stats['posts_commented'] = posts_commented
                                    self.logger.success(f"✅ Comment posted: '{comment_result.get('comment_text')}' ({posts_commented}/{max_comments})")
                                else:
                                    self.logger.debug(f"Comment failed on post #{posts_seen}")
                            except Exception as e:
                                self.logger.error(f"Error commenting on post #{posts_seen}: {e}")
                        elif should_comment and posts_commented >= max_comments:
                            self.logger.debug(f"Max comments reached ({posts_commented}/{max_comments}) - skipping comment")
                    else:
                        self.logger.warning(f"Failed to like post #{posts_seen}")
                else:
                    self.logger.debug(f"Post #{posts_seen} skipped (probability: {final_probability:.2f})")
                
                if posts_seen < max_posts_to_see:
                    scroll_count = 1
                    if posts_seen % 4 == 0:
                        scroll_count = 2
                        self.logger.debug(f"Double scroll at post #{posts_seen} for more variety")
                    
                    success = True
                    for i in range(scroll_count):
                        if not self._navigate_to_next_post_in_sequence():
                            self.logger.warning("Unable to navigate to next post - end of scroll")
                            success = False
                            break
                        if i < scroll_count - 1:
                            time.sleep(0.3)
                    
                    if not success:
                        break
                
                self._human_like_delay('scroll')
            
            self._return_to_profile_from_post()
            
            stats['success'] = posts_liked > 0
            stats['unique_posts_seen'] = unique_posts_seen
            self.logger.success(f"[FINAL] Sequential scroll completed: {posts_liked}/{max_likes} posts liked from {unique_posts_seen} unique posts ({posts_seen} scrolls)")
            return stats
            
        except Exception as e:
            self.logger.error(f"Error in like_posts_with_sequential_scroll: {e}")
            stats['errors'] += 1
            try:
                self._return_to_profile_from_post()
            except:
                pass
            return stats

    def like_current_post(self) -> bool:
        try:
            if not self.detection_actions.is_on_post_screen():
                self.logger.warning("Not on a post screen")
                return False
            
            if self.detection_actions.is_post_liked():
                self.logger.debug("Post already liked")
                return True
            
            if self.click_actions.like_post():
                self.logger.debug("Post liked successfully")
                return True
            else:
                self.logger.warning("Failed to like")
                return False
                
        except Exception as e:
            self.logger.error(f"Error liking current post: {e}")
            return False
    
    def _is_post_already_liked(self) -> bool:
        try:
            return self.detection_actions.is_post_liked()
        except Exception as e:
            self.logger.debug(f"Error checking if liked: {e}")
            return False
    
    def _open_first_post_of_profile(self) -> bool:
        try:
            self.logger.info("Opening first post of profile...")
            
            posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()
            
            if not posts:
                self.logger.error("No posts found in grid")
                return False
            
            first_post = posts[0]
            first_post.click()
            self.logger.debug("Clicking on first post...")
            
            time.sleep(3)  # Increased from 2s to 3s for slower devices
            
            if self._is_in_post_view():
                self.logger.success("First post opened successfully")
                return True
            else:
                self.logger.error("Failed to open first post")
                return False
                
        except Exception as e:
            self.logger.error(f"Error opening first post: {e}")
            return False
    
    def _is_in_post_view(self) -> bool:
        try:
            # Use both post_view_indicators and post_detail_indicators for better detection
            post_indicators = self.post_selectors.post_view_indicators + self.post_selectors.post_detail_indicators
            
            for indicator in post_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Post view detected via: {indicator[:50]}...")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking post view: {e}")
            return False
    
    def _navigate_to_next_post_in_sequence(self) -> bool:
        try:
            self.logger.debug("Navigating to next post...")
            
            # Get screen dimensions for adaptive swipe coordinates
            width, height = self.device.get_screen_size()
            
            try:
                # Vertical scroll: center X, from 78% to 21% of height
                center_x = width // 2
                start_y = int(height * 0.78)
                end_y = int(height * 0.21)
                
                self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.25)
                time.sleep(2.0)
                
                if self._is_in_post_view():
                    self.logger.debug("Navigation successful via vertical scroll")
                    return True
            except Exception as e:
                self.logger.debug(f"Vertical scroll failed: {e}")
            
            try:
                # Horizontal swipe: from 74% to 19% of width, center Y
                start_x = int(width * 0.74)
                end_x = int(width * 0.19)
                center_y = height // 2
                
                self.device.swipe_coordinates(start_x, center_y, end_x, center_y, duration=0.3)
                time.sleep(1)
                
                if self._is_in_post_view():
                    self.logger.debug("Navigation successful via horizontal swipe")
                    return True
            except Exception as e:
                self.logger.debug(f"Horizontal swipe failed: {e}")
            
            try:
                next_button_selectors = self.post_selectors.next_post_button_selectors
                
                for selector in next_button_selectors:
                    if self.device.xpath(selector).exists():
                        self.device.xpath(selector).click()
                        time.sleep(1)
                        
                        if self._is_in_post_view():
                            self.logger.debug("Navigation successful via Next button")
                            return True
            except Exception as e:
                self.logger.debug(f"Next button failed: {e}")
            
            self.logger.warning("All navigation methods failed")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to next post: {e}")
            return False
    
    def _return_to_profile_from_post(self):
        try:
            self.logger.info("Returning to profile from post...")
            
            back_selectors = self.post_selectors.back_button_selectors
            
            for selector in back_selectors:
                if self.device.xpath(selector).exists:
                    self.device.xpath(selector).click()
                    time.sleep(1.5)
                    self.logger.debug("Returned via back button")
                    return
            
            # Adaptive swipe coordinates
            width, height = self.device.get_screen_size()
            center_x = width // 2
            start_y = int(height * 0.625)  # ~62.5% of height
            end_y = int(height * 0.21)     # ~21% of height
            
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.5)
            time.sleep(1.5)
            self.logger.debug("Returned via downward swipe")
            
        except Exception as e:
            self.logger.error(f"Error returning to profile: {e}")
    
    
    def _extract_likes_count_from_ui(self) -> int:
        """Delegate to ui_extractors for likes extraction."""
        return self.ui_extractors.extract_likes_count_from_ui()
    
    def _extract_comments_count_from_ui(self) -> int:
        """Delegate to ui_extractors for comments extraction."""
        return self.ui_extractors.extract_comments_count_from_ui()
    
    def _is_current_post_reel(self) -> bool:
        """Delegate to detection_actions for reel detection."""
        return self.detection_actions.is_reel_post()
