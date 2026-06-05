"""Scroll actions facade - backward-compatible ScrollActions class."""

from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors.shell.screen_state import DETECTION_SELECTORS

from .base_scroll import BaseScrollMixin
from .feed_scroll import FeedScrollMixin
from .context_scroll import ContextScrollMixin


class ScrollActions(
    BaseScrollMixin,
    FeedScrollMixin,
    ContextScrollMixin
):
    """
    Facade composing all scroll mixins.

    Sub-modules:
    - base_scroll.py      - Generic directional scrolls + the shared humanized gesture primitives
                            (GestureMixin: real-fling flick / 1:1 drag) via inheritance.
    - feed_scroll.py      - Intelligent feed scroll: advance-to-next-post, framing, stop-on-metadata,
                            reading (caption/carousel), ad/suggested skip, browse session.
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
