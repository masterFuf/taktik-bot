"""Context-specific scroll actions (followers list, comments, feed, post grid, smart scroll)."""

from typing import Optional, Dict, Any
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, POST_COMMENTS_SELECTORS


class ContextScrollMixin(BaseAction):
    """Mixin: context-specific scrolls (followers, comments, feed, grid) + load more + smart scroll."""

    def scroll_followers_list_down(self, duration: float = 0.8, distance_ratio: float = 0.30) -> bool:
        self.logger.debug("👥 Scrolling followers list down")
        
        try:
            center_x = self.screen_width // 2
            start_y = int(self.screen_height * 0.70)
            end_y = int(start_y - self.screen_height * distance_ratio)
            
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration)
            
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling followers list: {e}")
            return False
    
    def scroll_comments_down(self) -> bool:
        """Scroll down in the comments bottom sheet view."""
        self.logger.debug("💬 Scrolling comments list down")
        
        try:
            # Try to scroll within the comments RecyclerView (sticky_header_list)
            # The comments view is a bottom sheet that covers most of the screen
            # We need to scroll within its bounds, not the full screen
            comments_list = self.device.xpath(f'//*[@resource-id="{POST_COMMENTS_SELECTORS.comments_list_resource_id}"]')
            
            if comments_list.exists:
                # Get the bounds of the comments list
                try:
                    info = comments_list.info
                    bounds = info.get('bounds', {})
                    if bounds:
                        left = bounds.get('left', 0)
                        top = bounds.get('top', 162)
                        right = bounds.get('right', self.screen_width)
                        bottom = bounds.get('bottom', int(self.screen_height * 0.83))
                        
                        # Scroll within the comments list bounds
                        center_x = (left + right) // 2
                        start_y = top + int((bottom - top) * 0.75)
                        end_y = top + int((bottom - top) * 0.25)
                        
                        self.logger.debug(f"💬 Scrolling in comments bounds: ({center_x}, {start_y}) → ({center_x}, {end_y})")
                        self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.6)
                        self._human_like_delay('scroll')
                        return True
                except Exception as e:
                    self.logger.debug(f"Could not get comments list bounds: {e}")
            
            # Fallback: scroll in the bottom sheet area (typically y=200 to y=1200)
            center_x = self.screen_width // 2
            # Comments bottom sheet typically starts around y=160 and ends around y=1260
            start_y = int(self.screen_height * 0.75)  # ~1140 on 1520 screen
            end_y = int(self.screen_height * 0.30)    # ~456 on 1520 screen
            
            self.logger.debug(f"💬 Fallback scroll: ({center_x}, {start_y}) → ({center_x}, {end_y})")
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.6)
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling comments list: {e}")
            return False
    
    def scroll_post_grid_down(self) -> bool:
        self.logger.debug("📸 Scrolling post grid down")
        
        try:
            center_x = self.screen_width // 2
            start_y = int(self.screen_height * 0.75)
            end_y = int(self.screen_height * 0.25)
            
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.5)
            
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling post grid: {e}")
            return False
    
    def scroll_feed_down(self) -> bool:
        self.logger.debug("📱 Scrolling feed down")
        
        try:
            center_x = self.screen_width // 2
            start_y = int(self.screen_height * 0.7)
            end_y = int(self.screen_height * 0.3)
            
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.5)
            
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling feed: {e}")
            return False

    def check_and_click_load_more(self) -> bool:
        try:
            for selector in self.detection_selectors.load_more_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        self.logger.info(f"🔍 'Load more' button found with: {selector}")
                        element.click()
                        self.logger.success("✅ 'Load more' button clicked - loading 25 new followers")
                        
                        self._human_like_delay('load_more')
                        return True
                        
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            for selector in self.detection_selectors.end_of_list_indicators:
                try:
                    if self.device.xpath(selector).exists:
                        self.logger.info(f"🏁 End of list detected with: {selector}")
                        return False
                except Exception:
                    continue
            
            self.logger.debug("🔍 No 'Voir plus' button found on screen")
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking 'Load more' button: {e}")
            return False

    def smart_scroll_to_load_content(self, content_type: str = "posts", max_scrolls: int = 5) -> int:
        self.logger.debug(f"🧠 Smart scrolling to load {content_type}")
        
        scroll_count = 0
        
        for i in range(max_scrolls):
            if content_type == "posts":
                success = self.scroll_post_grid_down()
            elif content_type == "followers":
                success = self.scroll_followers_list_down()
            elif content_type == "feed":
                success = self.scroll_feed_down()
            else:
                success = self.scroll_down()
            
            if success:
                scroll_count += 1
                self._random_sleep(2.0, 3.0)
            else:
                break
        
        self.logger.debug(f"✅ {scroll_count} scrolls performed for {content_type}")
        return scroll_count
