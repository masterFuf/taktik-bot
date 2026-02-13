"""Scroll actions facade - backward-compatible ScrollActions class."""

from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, POST_SELECTORS

from .base_scroll import BaseScrollMixin
from .context_scroll import ContextScrollMixin


class ScrollActions(
    BaseScrollMixin,
    ContextScrollMixin
):
    """
    Facade composing all scroll mixins.
    
    Sub-modules:
    - base_scroll.py      - Generic directional scrolls, scroll-to-top/bottom, momentum, carousel, info
    - context_scroll.py   - Context-specific scrolls (followers, comments, feed, grid) + load more + smart scroll
    """
    
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


__all__ = ['ScrollActions']
