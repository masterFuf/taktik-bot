"""Instagram-specific scroll with human-like variance and random offsets."""

import random


class ScrollMixin:
    """Mixin: scroll IG-specific (_scroll_down, _scroll_up) avec variance naturelle."""

    def _scroll_down(self, distance: int = 500) -> None:
        """Scroll vers le bas avec variance naturelle."""
        screen_info = self.device.info
        screen_height = screen_info['displayHeight']
        screen_width = screen_info['displayWidth']
        
        # Position X avec variance (pas toujours au centre)
        center_x = screen_width // 2
        offset_x, offset_y = self.human.get_random_offset(30)
        start_x = center_x + offset_x
        end_x = center_x + random.randint(-20, 20)  # Légère courbe
        
        start_y = int(screen_height * random.uniform(0.65, 0.75))
        end_y = int(screen_height * random.uniform(0.25, 0.35))
        
        # Durée variable du swipe
        duration = random.uniform(0.2, 0.4)
        
        self.device.swipe(start_x, start_y, end_x, end_y, duration=duration)
        self._human_like_delay('scroll')
    
    def _scroll_up(self, distance: int = 500) -> None:
        """Scroll vers le haut avec variance naturelle."""
        screen_info = self.device.info
        screen_height = screen_info['displayHeight']
        screen_width = screen_info['displayWidth']
        
        center_x = screen_width // 2
        offset_x, _ = self.human.get_random_offset(30)
        start_x = center_x + offset_x
        end_x = center_x + random.randint(-20, 20)
        
        start_y = int(screen_height * random.uniform(0.25, 0.35))
        end_y = int(screen_height * random.uniform(0.65, 0.75))
        
        duration = random.uniform(0.2, 0.4)
        
        self.device.swipe(start_x, start_y, end_x, end_y, duration=duration)
        self._human_like_delay('scroll')
