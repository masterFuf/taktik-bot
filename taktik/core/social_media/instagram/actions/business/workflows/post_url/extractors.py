"""Liker extraction and UI delegation methods for post_url workflow."""

import re
import time
from typing import Dict, List, Any, Optional


class PostUrlExtractorsMixin:
    """Mixin: extract likers from posts, find matching posts, delegate to ui_extractors."""
    
    def _find_and_extract_likers_from_profile(self, post_metadata: Dict[str, Any]) -> List[str]:
        try:
            self.logger.info(f"Searching for post with {post_metadata['likes_count']} likes, {post_metadata['comments_count']} comments")
            
            self.logger.debug("Attempting to open first post...")
            if not self._open_first_post_in_grid():
                self.logger.error("Failed to open first post")
                return []
            
            self.logger.debug("First post opened, starting search...")
            
            max_scrolls = 500
            scroll_count = 0
            detected_posts = []
            posts_checked = 0
            duplicate_count = 0
            
            self.logger.debug(f"Starting search loop (max {max_scrolls} scrolls)")
            while scroll_count < max_scrolls and posts_checked < 50:
                # Vérifier si la session doit continuer (durée, limites, etc.)
                if hasattr(self, 'session_manager') and self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        return None
                
                try:
                    self.logger.debug("Extracting current post metadata...")
                    
                    # Try atomic extraction first (prevents timing issues during scroll)
                    stats = self.ui_extractors.extract_post_stats_atomic()
                    
                    if stats:
                        current_likes = stats['likes']
                        current_comments = stats['comments']
                    else:
                        # Fallback to separate extraction
                        current_likes = self.ui_extractors.extract_likes_count_from_ui()
                        current_comments = self.ui_extractors.extract_comments_count_from_ui()
                    
                    post_signature = (current_likes, current_comments)
                    
                    if post_signature in detected_posts:
                        duplicate_count += 1
                        self.logger.debug(f"Duplicate post (scroll #{scroll_count + 1}): {current_likes} likes, {current_comments} comments")
                        if duplicate_count >= 5:
                            self.logger.warning("Too many duplicates, ending search")
                            break
                    else:
                        duplicate_count = 0
                        posts_checked += 1
                        detected_posts.append(post_signature)
                        
                        self.logger.info(f"UNIQUE POST #{posts_checked}: {current_likes} likes, {current_comments} comments | TARGET: {post_metadata['likes_count']} likes, {post_metadata['comments_count']} comments")
                        
                        # Exact match - best case
                        if current_likes == post_metadata['likes_count'] and current_comments == post_metadata['comments_count']:
                            self.logger.success(f"✅ Exact post found (post #{posts_checked})!")
                            return self._extract_likers_from_current_post()
                        
                        # Adaptive tolerance based on post popularity
                        likes_diff = abs(current_likes - post_metadata['likes_count'])
                        adaptive_tolerance = self._calculate_adaptive_tolerance(post_metadata['likes_count'])
                        
                        # Comments must match exactly (they change less frequently)
                        if likes_diff <= adaptive_tolerance and current_comments == post_metadata['comments_count']:
                            self.logger.success(f"✅ Matching post found (likes diff: {likes_diff}/{adaptive_tolerance}, post #{posts_checked})!")
                            return self._extract_likers_from_current_post()
                    
                except Exception as e:
                    self.logger.debug(f"Error checking scroll #{scroll_count + 1}: {e}")
                
                self.logger.debug(f"Vertical scroll #{scroll_count + 1}")
                # Adaptive swipe coordinates
                width, height = self.device.get_screen_size()
                center_x = width // 2
                start_y = int(height * 0.89)  # ~89% of height
                end_y = int(height * 0.16)    # ~16% of height
                self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.7)
                time.sleep(2.5)
                scroll_count += 1
            
            self.logger.warning(f"Matching post not found after {posts_checked} unique posts ({scroll_count} scrolls)")
            return []
            
        except Exception as e:
            self.logger.error(f"Error searching for post: {e}")
            return []
    
    def _open_first_post_in_grid(self) -> bool:
        try:
            first_post = self.device.xpath(self.post_selectors.first_post_grid)
            if first_post.exists:
                self.logger.debug("Opening first post")
                first_post.click()
                time.sleep(3)
                return True
            else:
                self.logger.error("First post not found")
                return False
        except Exception as e:
            self.logger.error(f"Error opening first post: {e}")
            return False
    
    def _extract_likers_from_current_post(self) -> List[str]:
        try:
            if self._is_reel_post():
                self.logger.debug("Reel type post detected")
                return self._extract_likers_from_reel()
            else:
                self.logger.debug("Regular post detected")
                return self._extract_likers_from_regular_post()
                
        except Exception as e:
            self.logger.error(f"Error extracting likers: {e}")
            return []
    
    def _extract_likers_from_regular_post(self) -> List[str]:
        return super()._extract_likers_from_regular_post(max_interactions=None, multiply_by=2)
    
    def _extract_likers_from_reel(self) -> List[str]:
        return super()._extract_likers_from_reel(max_interactions=None, multiply_by=2)
    
    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return super()._interact_with_user(username, config)
    
    def _get_filter_criteria_from_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return super()._get_filter_criteria_from_config(config)
    
    def _determine_interactions_from_config(self, config: Dict[str, Any]) -> List[str]:
        return super()._determine_interactions_from_config(config)
    
    def _is_like_count_text(self, text: str) -> bool:
        return self.ui_extractors.is_like_count_text(text)
    
    def _extract_usernames_from_likers_popup(self) -> List[str]:
        max_users = getattr(self, 'current_max_interactions', self.default_config['max_interactions'])
        
        return self.ui_extractors.extract_usernames_from_likers_popup(
            current_max_interactions_attr=max_users,
            automation=self.automation,
            logger_instance=self.logger,
            add_initial_sleep=False
        )
    
    def _extract_visible_usernames(self) -> List[str]:
        return self.ui_extractors.extract_visible_usernames(logger_instance=self.logger)
    
    def _extract_username_from_element(self, element) -> Optional[str]:
        return self.ui_extractors.extract_username_from_element(element, logger_instance=self.logger)
    
    def _get_popup_bounds(self) -> Optional[Dict]:
        try:
            for selector in self.popup_selectors.popup_bounds_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element_info = element.info
                        bounds_data = element_info.get('bounds', '')
                        
                        if bounds_data:
                            left, top, right, bottom = None, None, None, None
                            
                            if isinstance(bounds_data, dict):
                                left = bounds_data.get('left', 0)
                                top = bounds_data.get('top', 0)
                                right = bounds_data.get('right', 0)
                                bottom = bounds_data.get('bottom', 0)
                                self.logger.debug(f"Dict format detected for popup")
                            else:
                                bounds_str = str(bounds_data)
                                
                                match1 = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                                if match1:
                                    left, top, right, bottom = map(int, match1.groups())
                                    self.logger.debug(f"[x,y][x,y] format detected for popup")
                                
                                match2 = re.match(r'\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', bounds_str)
                                if match2:
                                    left, top, right, bottom = map(int, match2.groups())
                                    self.logger.debug(f"(x, y, x, y) format detected for popup")
                            
                            if left is not None:
                                popup_bounds = {
                                    'left': left,
                                    'top': top,
                                    'right': right,
                                    'bottom': bottom
                                }
                                self.logger.debug(f"Popup bounds detected with {selector}: {popup_bounds}")
                                return popup_bounds
                                
                except Exception as e:
                    self.logger.debug(f"Error with popup selector {selector}: {e}")
                    continue
            
            self.logger.debug("No popup bounds detected - fallback to fixed coordinates")
            return None
            
        except Exception as e:
            self.logger.debug(f"Error detecting popup bounds: {str(e)}")
            return None
