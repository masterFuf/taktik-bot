"""Liker extraction and UI delegation methods for hashtag workflow."""

import time
from typing import Dict, List, Any, Optional


class HashtagExtractorsMixin:
    """Mixin: extract likers from posts, delegate to ui_extractors."""
    
    def _extract_likers_from_selected_posts(self, posts: List[Dict[str, Any]], config: Dict[str, Any]) -> List[str]:
        all_likers = []
        max_interactions = config.get('max_interactions', 30)
        
        selected_posts = [p for p in posts if p.get('selected', False)]
        
        if not selected_posts:
            return []
        
        self.logger.info(f"Extracting likers from {len(selected_posts)} selected posts")
        
        try:
            if not self._open_first_post_in_grid():
                return []
            
            current_index = 0
            
            # Get screen dimensions once for adaptive swipes
            width, height = self.device.get_screen_size()
            center_x = width // 2
            start_y = int(height * 0.83)
            end_y = int(height * 0.21)
            
            for post in posts:
                while current_index < post['index']:
                    self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.6)
                    time.sleep(2)
                    current_index += 1
                
                if post.get('selected', False):
                    self.logger.info(f"Extracting likers from post #{post['index'] + 1} ({post['likes_count']} likes)")
                    
                    post_likers = self._extract_likers_from_current_post()
                    
                    for username in post_likers:
                        if username not in all_likers:
                            all_likers.append(username)
                            
                            if len(all_likers) >= max_interactions * 2:
                                self.logger.info(f"Target reached: {len(all_likers)} likers collected")
                                for _ in range(3):
                                    self.device.back()
                                    time.sleep(1)
                                return all_likers
                    
                    self.logger.info(f"Total likers collected: {len(all_likers)}")
                
                if current_index < len(posts) - 1:
                    current_index += 1
            
            for _ in range(3):
                self.device.back()
                time.sleep(1)
            
            self.logger.info(f"{len(all_likers)} unique likers extracted")
            return all_likers
            
        except Exception as e:
            self.logger.error(f"Error extracting likers: {e}")
            return []
    
    def _extract_likers_from_current_post(self, is_reel: bool = None, max_interactions: int = None) -> List[str]:
        try:
            if is_reel is None:
                is_reel = self._is_reel_post()
            
            if is_reel:
                self.logger.debug("Reel post detected")
                return self._extract_likers_from_reel(max_interactions=max_interactions)
            else:
                self.logger.debug("Regular post detected")
                return self._extract_likers_from_regular_post(max_interactions=max_interactions)
                
        except Exception as e:
            self.logger.error(f"Error extracting likers: {e}")
            return []
    
    def _extract_likers_from_regular_post(self, max_interactions: int = None) -> List[str]:
        return super()._extract_likers_from_regular_post(max_interactions=max_interactions, multiply_by=2)
    
    def _extract_likers_from_reel(self, max_interactions: int = None) -> List[str]:
        return super()._extract_likers_from_reel(max_interactions=max_interactions, multiply_by=2)
    
    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return super()._interact_with_user(username, config)
    
    def _get_filter_criteria_from_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return super()._get_filter_criteria_from_config(config)
    
    def _is_like_count_text(self, text: str) -> bool:
        return self.ui_extractors.is_like_count_text(text)
    
    def _extract_usernames_from_likers_popup(self, max_interactions: int = None) -> List[str]:
        return self.ui_extractors.extract_usernames_from_likers_popup(
            max_interactions=max_interactions,
            automation=self.automation,
            logger_instance=self.logger,
            add_initial_sleep=True
        )
    
    def _extract_visible_usernames(self) -> List[str]:
        return self.ui_extractors.extract_visible_usernames(logger_instance=self.logger)
    
    def _extract_username_from_element(self, element) -> Optional[str]:
        return self.ui_extractors.extract_username_from_element(element, logger_instance=self.logger)
    
    def _is_valid_username(self, username: str) -> bool:
        return self.ui_extractors.is_valid_username(username)
