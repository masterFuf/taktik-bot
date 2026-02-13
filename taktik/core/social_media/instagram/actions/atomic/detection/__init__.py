"""Detection actions facade — backward-compatible DetectionActions class."""

from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, PROFILE_SELECTORS, POST_SELECTORS

from .screen_detection import ScreenDetectionMixin
from .profile_extraction import ProfileExtractionMixin
from .list_detection import ListDetectionMixin


class DetectionActions(
    ScreenDetectionMixin,
    ProfileExtractionMixin,
    ListDetectionMixin
):
    """
    Facade composing all detection mixins.
    
    Sub-modules:
    - screen_detection.py     — Screen state (home/search/profile/post), errors, rate limits, stories, popups
    - profile_extraction.py   — Profile flags, text extraction, enriched data (XML batch), bio more
    - list_detection.py       — Followers/following list detection, username extraction, click follower
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-detection-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        self.selectors = PROFILE_SELECTORS
        self.post_selectors = POST_SELECTORS


__all__ = ['DetectionActions']
