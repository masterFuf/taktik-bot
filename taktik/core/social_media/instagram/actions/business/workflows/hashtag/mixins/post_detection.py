"""Post type detection, reel handling, grid detection for hashtag workflow."""

import time
from typing import Dict, Any, Optional


class HashtagPostDetectionMixin:
    """Mixin: detect post types (reel/post/carousel), reveal reel UI, check grid presence."""

    def _detect_opened_post_type(self) -> str:
        try:
            reel_player_indicators = self.post_selectors.reel_player_indicators
            
            for indicator in reel_player_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Reel player detected via: {indicator}")
                    return "reel_player"
            
            carousel_indicators = self.post_selectors.carousel_indicators
            
            for indicator in carousel_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Carousel detected via: {indicator}")
                    return "post_detail"
            
            post_detail_indicators = self.post_selectors.post_detail_indicators
            
            for indicator in post_detail_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Post detail detected via: {indicator}")
                    return "post_detail"
            
            self.logger.warning("No post indicator found")
            return "unknown"
            
        except Exception as e:
            self.logger.debug(f"Error detecting post type: {e}")
            return "unknown"
    
    def _reveal_reel_comments_section(self) -> bool:
        try:
            screen_info = self.device.info
            center_x = screen_info.get('displayWidth', 1080) // 2
            
            start_y = int(screen_info.get('displayHeight', 1920) * 0.80)
            end_y = int(screen_info.get('displayHeight', 1920) * 0.20)
            
            self.logger.debug(f"Swipe to reveal comments: ({center_x}, {start_y}) -> ({center_x}, {end_y})")
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.5)
            time.sleep(2)
            
            if self._are_like_comment_elements_visible():
                self.logger.debug("Like/comment elements detected after 1st swipe")
                return True
            
            self.logger.debug("Second swipe to finalize opening")
            start_y = int(screen_info.get('displayHeight', 1920) * 0.70)
            end_y = int(screen_info.get('displayHeight', 1920) * 0.30)
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.5)
            time.sleep(2)
            
            result = self._are_like_comment_elements_visible()
            if result:
                self.logger.debug("Like/comment elements detected after 2nd swipe")
            else:
                self.logger.debug("Like/comment elements not detected")
            return result
            
        except Exception as e:
            self.logger.error(f"Error swiping to reveal comments: {e}")
            return False
    
    def _are_like_comment_elements_visible(self) -> bool:
        try:
            like_indicators = self.post_selectors.like_button_indicators
            comment_indicators = self.post_selectors.comment_button_indicators
            
            for selector in like_indicators + comment_indicators:
                try:
                    if self.device.xpath(selector).exists:
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking elements: {e}")
            return False
    
    def _is_on_hashtag_grid(self) -> bool:
        """Vérifie si on est sur la grille de posts d'un hashtag."""
        try:
            # Vérifier si on voit des posts dans la grille
            for selector in self.post_selectors.hashtag_post_selectors:
                posts = self.device.xpath(selector).all()
                if posts and len(posts) >= 3:  # Au moins 3 posts visibles = grille
                    self.logger.debug(f"✅ Hashtag grid detected ({len(posts)} posts visible)")
                    return True
            
            # Vérifier si on voit le header du hashtag (depuis selectors.py)
            for selector in self._hashtag_sel.hashtag_header:
                if self.device.xpath(selector).exists:
                    self.logger.debug("✅ Hashtag page header detected")
                    return True
            
            self.logger.debug("❌ Not on hashtag grid")
            return False
        except Exception as e:
            self.logger.debug(f"Error checking hashtag grid: {e}")
            return False
    
    def _swipe_to_next_post(self):
        """Swipe vertical pour passer au post suivant."""
        try:
            width, height = self.device.get_screen_size()
            center_x = width // 2
            start_y = int(height * 0.75)
            end_y = int(height * 0.25)
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.4)
            self.logger.debug("📜 Swiped to next post")
        except Exception as e:
            self.logger.debug(f"Error swiping to next post: {e}")
