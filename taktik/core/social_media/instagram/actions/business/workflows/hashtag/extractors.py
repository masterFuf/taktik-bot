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
    
    # _extract_likers_from_current_post, _extract_likers_from_regular_post,
    # _extract_likers_from_reel, _interact_with_user, _get_filter_criteria_from_config,
    # _is_valid_username, etc. are all inherited from LikersWorkflowBase / BaseBusinessAction.
