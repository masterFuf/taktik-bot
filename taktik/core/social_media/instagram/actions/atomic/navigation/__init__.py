"""Navigation actions facade — backward-compatible NavigationActions class."""

from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, NAVIGATION_SELECTORS, PROFILE_SELECTORS
from ....ui.detectors.problematic_page import ProblematicPageDetector

from .tab_navigation import TabNavigationMixin
from .deep_link_navigation import DeepLinkNavigationMixin
from .search_navigation import SearchNavigationMixin


class NavigationActions(
    TabNavigationMixin,
    DeepLinkNavigationMixin,
    SearchNavigationMixin
):
    """
    Facade composing all navigation mixins.
    
    Sub-modules:
    - tab_navigation.py        — Tab clicks (home, search, profile) + screen detection + popup handling
    - deep_link_navigation.py  — ADB deep links (profile + post URLs)
    - search_navigation.py     — Search-based nav (profile search, hashtag) + content nav (lists, posts, stories)
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-navigation-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        self.selectors = NAVIGATION_SELECTORS
        self.profile_selectors = PROFILE_SELECTORS
        self.problematic_page_detector = ProblematicPageDetector(device, debug_mode=False)


__all__ = ['NavigationActions']
