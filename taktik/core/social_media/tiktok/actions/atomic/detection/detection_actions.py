"""Atomic detection actions for TikTok.


This module aggregates VideoDetector and PopupDetector and adds
page-detection, error/state detection, and app-state helpers.
Existing code can continue to ``from ....atomic.detection_actions import DetectionActions``
and get every method via a single class.
"""

from loguru import logger

from .video_detector import VideoDetector
from .popup_detector import PopupDetector
from .screen_reading import ScreenReading, note_action_block
from taktik.core.shared.device.ui_dump import parse_ui_dump
from ....ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from ....ui.selectors.surfaces.inbox import INBOX_SELECTORS


class DetectionActions(ScreenReading, VideoDetector, PopupDetector):
    """Backward-compatible aggregate of all atomic detection actions.

    Inherits video + popup detectors and adds page/error/app-state detection, and
    `read_screen()`: these questions answered on one photo.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-detection-atomic")
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.inbox_selectors = INBOX_SELECTORS
    
    # === Page Detection ===
    
    def is_on_for_you_page(self, screen=None) -> bool:
        """Check if currently on For You feed.
        
        Détecte via:
        - the For You tab selected in the header
        - the video interaction buttons present

        `screen`: the photo this decision is read on (`read_screen()`), answered without a wait.
        """
        # Check if For You tab is visible and selected
        if self._element_exists(self.navigation_selectors.for_you_tab, timeout=2, screen=screen):
            # Also check for video interaction buttons
            if self._element_exists(self.video_selectors.like_button, timeout=1, screen=screen):
                return True
        
        # Fallback: check for home tab selected
        return self._element_exists(self.navigation_selectors.home_tab_selected, timeout=1,
                                    screen=screen)

    def is_action_blocked(self) -> bool:
        """Is TikTok refusing the account's actions right now? One dump, closes nothing.

        Seeing it sets the run's stop latch (`run_halt.ACTION_BLOCKED`), whoever asked: every
        loop that decides to continue reads it. A screen that cannot be read is not a block.
        """
        try:
            tree = parse_ui_dump(self.device.dump_hierarchy(compressed=False))
        except Exception as exc:  # noqa: BLE001
            self.logger.debug(f"Block check: no dump ({exc})")
            return False
        return note_action_block(tree)

    def is_on_inbox_page(self, screen=None) -> bool:
        """Check if currently on Inbox page.
        
        Détecte via:
        - Titre "Inbox"
        - the notification sections present

        `screen`: the photo this decision is read on (`read_screen()`), answered without a wait.
        """
        if self._element_exists(self.inbox_selectors.inbox_title, timeout=2, screen=screen):
            return True
        
        # Check for inbox tab selected
        return self._element_exists(self.navigation_selectors.inbox_tab_selected, timeout=1,
                                    screen=screen)
