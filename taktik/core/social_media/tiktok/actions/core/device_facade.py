import time
from loguru import logger

from taktik.core.shared.device.facade import BaseDeviceFacade


class DeviceFacade(BaseDeviceFacade):
    """TikTok-specific device facade.
    
    Inherits common functionality from BaseDeviceFacade.
    Overrides swipe methods for TikTok's video-based UI (adaptive coordinates).
    Adds TikTok-specific: click(x,y), double_click, long_click.
    """
    
    app_id = 'com.zhiliaoapp.musically'
    _facade_name = 'TikTokDeviceFacade'
    
    def __init__(self, device):
        super().__init__(device, module_name="tiktok-device-facade")
    
    # =========================================================================
    # TikTok-specific: swipe overrides for video UI
    # =========================================================================
    
    def swipe_up(self, scale: float = 0.8):
        """Swipe up (scroll down content).
        
        Adaptive swipe for TikTok video scrolling that works on all screen resolutions:
        - Uses percentage-based coordinates to adapt to any screen size
        - Swipes on LEFT side of screen to avoid interaction buttons on the right
        - Avoids bottom ~20% (navigation bar + interaction buttons area)
        - Avoids top ~15% (search bar/status bar area)
        - Results in ~65% screen distance swipe for reliable video switching
        """
        width, height = self.get_screen_size()
        
        # Use LEFT side of screen (30% from left) to avoid interaction buttons on right
        # Interaction buttons (like, comment, share) are on the right side (x > 80%)
        x = int(width * 0.30)
        
        # Percentage-based swipe that adapts to any resolution
        # Start at 80% from top (avoids bottom nav + buttons area ~20%)
        # End at 15% from top (avoids search bar + header)
        y_start = int(height * 0.80)
        y_end = int(height * 0.15)
        
        self.logger.debug(f"Swipe up: screen={width}x{height}, y={y_start}->{y_end}")
        self.swipe_coordinates(x, y_start, x, y_end, duration=0.35)
    
    def swipe_down(self, scale: float = 0.8):
        """Swipe down (scroll up content)."""
        width, height = self.get_screen_size()
        x = width // 2
        y_start = int(height * 0.2)
        y_end = int(height * 0.8)
        
        self.swipe_coordinates(x, y_start, x, y_end, duration=0.3)
    
    def swipe_left(self, scale: float = 0.8):
        """Swipe left."""
        width, height = self.get_screen_size()
        y = height // 2
        x_start = int(width * 0.8)
        x_end = int(width * 0.2)
        
        self.swipe_coordinates(x_start, y, x_end, y, duration=0.3)
    
    def swipe_right(self, scale: float = 0.8):
        """Swipe right."""
        width, height = self.get_screen_size()
        y = height // 2
        x_start = int(width * 0.2)
        x_end = int(width * 0.8)
        
        self.swipe_coordinates(x_start, y, x_end, y, duration=0.3)
    
    # =========================================================================
    # TikTok-specific: click at coordinates (different signature from base)
    # =========================================================================
    
    def click(self, x: int, y: int):
        """Click at coordinates."""
        try:
            self._device.click(x, y)
            time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error clicking at ({x}, {y}): {e}")
            raise
