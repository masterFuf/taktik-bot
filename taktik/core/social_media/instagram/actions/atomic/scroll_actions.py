from typing import Optional, Dict, Any, Tuple
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import DETECTION_SELECTORS


class ScrollActions(BaseAction):
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-scroll-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        
        try:
            self.screen_width, self.screen_height = self.device.get_screen_size()
        except Exception as e:
            self.logger.warning(f"Cannot get screen dimensions: {e}")
            self.screen_width = 1080
            self.screen_height = 1920
                
    _SPEED_MAP = {'slow': 1.0, 'normal': 0.5, 'fast': 0.2}
    
    def _scroll(self, direction: str, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        """
        Generic scroll method.
        
        Args:
            direction: 'up', 'down', 'left', 'right'
            distance_ratio: Scroll distance as ratio of screen size
            speed: 'slow', 'normal', 'fast'
            
        Returns:
            True if scroll successful, False otherwise
        """
        try:
            duration = self._SPEED_MAP.get(speed, 0.5)
            center_x = self.screen_width // 2
            center_y = self.screen_height // 2
            
            if direction == 'down':
                start_x, start_y = center_x, int(self.screen_height * 0.7)
                end_x, end_y = center_x, int(start_y - (self.screen_height * distance_ratio))
            elif direction == 'up':
                start_x, start_y = center_x, int(self.screen_height * 0.3)
                end_x, end_y = center_x, int(start_y + (self.screen_height * distance_ratio))
            elif direction == 'left':
                start_x, start_y = int(self.screen_width * 0.7), center_y
                end_x, end_y = int(start_x - (self.screen_width * distance_ratio)), center_y
            elif direction == 'right':
                start_x, start_y = int(self.screen_width * 0.3), center_y
                end_x, end_y = int(start_x + (self.screen_width * distance_ratio)), center_y
            else:
                self.logger.error(f"Invalid scroll direction: {direction}")
                return False
            
            self.logger.debug(f"📱 Scrolling {direction}: ({start_x}, {start_y}) → ({end_x}, {end_y}) (speed: {speed})")
            self.device.swipe_coordinates(start_x, start_y, end_x, end_y, duration)
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling {direction}: {e}")
            return False
    
    def scroll_down(self, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        return self._scroll('down', distance_ratio, speed)
    
    def scroll_up(self, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        return self._scroll('up', distance_ratio, speed)
    
    def scroll_left(self, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        return self._scroll('left', distance_ratio, speed)
    
    def scroll_right(self, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        return self._scroll('right', distance_ratio, speed)
    
    def scroll_followers_list_down(self) -> bool:
        self.logger.debug("👥 Scrolling followers list down")
        
        try:
            center_x = self.screen_width // 2
            start_y = int(self.screen_height * 0.8)
            end_y = int(self.screen_height * 0.2)
            
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.5)
            
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling followers list: {e}")
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
    
    def scroll_to_top(self, max_attempts: int = 5) -> bool:
        self.logger.debug("⬆️ Scrolling to top")
        
        for attempt in range(max_attempts):
            if not self.scroll_up(distance_ratio=0.8, speed="fast"):
                return False
            
            self._random_sleep(0.5, 1.0)
        
        return True
    
    def scroll_to_bottom(self, max_attempts: int = 10) -> bool:
        self.logger.debug("⬇️ Scrolling to bottom")
        
        previous_content = None
        no_change_count = 0
        
        for attempt in range(max_attempts):
            try:
                current_content = str(self.device.device.dump_hierarchy()) if hasattr(self.device, 'device') else f"attempt_{attempt}"
            except Exception:
                current_content = f"attempt_{attempt}"
            
            if not self.scroll_down(distance_ratio=0.6, speed="normal"):
                return False
            
            if current_content == previous_content:
                no_change_count += 1
                if no_change_count >= 3:
                    self.logger.debug("End of content detected")
                    return True
            else:
                no_change_count = 0
            
            previous_content = current_content
            self._random_sleep(1.0, 2.0)
        
        return True
    
    def scroll_horizontally_in_carousel(self, direction: str = "right") -> bool:
        self.logger.debug(f"🔄 Scrolling carousel to {direction}")
        
        if direction == "right":
            return self.scroll_left(distance_ratio=0.8, speed="normal")
        elif direction == "left":
            return self.scroll_right(distance_ratio=0.8, speed="normal")
        else:
            self.logger.error(f"Invalid direction: {direction}")
            return False
    
    def scroll_with_momentum(self, direction: str = "down", intensity: str = "medium") -> bool:
        self.logger.debug(f"💨 Scrolling with momentum {direction} (intensity: {intensity})")
        
        intensity_params = {
            'light': {'distance': 0.3, 'duration': 300},
            'medium': {'distance': 0.5, 'duration': 200},
            'strong': {'distance': 0.7, 'duration': 100}
        }
        
        params = intensity_params.get(intensity, intensity_params['medium'])
        
        if direction == "down":
            return self.scroll_down(distance_ratio=params['distance'], speed="fast")
        elif direction == "up":
            return self.scroll_up(distance_ratio=params['distance'], speed="fast")
        elif direction == "left":
            return self.scroll_left(distance_ratio=params['distance'], speed="fast")
        elif direction == "right":
            return self.scroll_right(distance_ratio=params['distance'], speed="fast")
        else:
            self.logger.error(f"Invalid direction: {direction}")
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
    
    def get_scroll_position_info(self) -> Dict[str, Any]:
        return {
            'screen_width': self.screen_width,
            'screen_height': self.screen_height,
            'center_x': self.screen_width // 2,
            'center_y': self.screen_height // 2,
            'scroll_stats': self.get_method_stats()
        }
