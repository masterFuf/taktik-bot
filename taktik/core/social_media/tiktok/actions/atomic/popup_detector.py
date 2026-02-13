"""Atomic popup/overlay detection for TikTok.

Extracted from detection_actions.py — contains only popup-presence checks.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import POPUP_SELECTORS


class PopupDetector(BaseAction):
    """Detects popups, banners, suggestion pages, and comment overlays."""

    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-popup-detector")
        self.popup_selectors = POPUP_SELECTORS

    def has_popup(self) -> bool:
        """Check if there's a popup on screen."""
        if self._element_exists(self.popup_selectors.close_button, timeout=1):
            return True
        if self._element_exists(self.popup_selectors.dismiss_button, timeout=1):
            return True
        if self._element_exists(self.popup_selectors.promo_banner, timeout=1):
            return True
        if self._element_exists(self.popup_selectors.collections_popup, timeout=1):
            return True
        if self._element_exists(self.popup_selectors.follow_friends_popup, timeout=1):
            return True
        return False

    def has_collections_popup(self) -> bool:
        """Check if the 'Create shared collections' popup is visible."""
        return self._element_exists(self.popup_selectors.collections_popup, timeout=1)

    def has_follow_friends_popup(self) -> bool:
        """Check if the 'Follow your friends' popup is visible."""
        return self._element_exists(self.popup_selectors.follow_friends_popup, timeout=1)

    def has_link_email_popup(self) -> bool:
        """Check if the 'Link email' popup is visible."""
        return self._element_exists(self.popup_selectors.link_email_popup, timeout=1)

    def has_suggestion_page(self) -> bool:
        """Check if on a suggestion page (Follow back / Not interested).
        
        This page appears in the For You feed suggesting users to follow back.
        """
        return self._element_exists(self.popup_selectors.suggestion_page_indicator, timeout=1)

    def has_comments_section_open(self) -> bool:
        """Check if the comments section is open.
        
        This can happen accidentally when scrolling and clicking on the comment input area.
        """
        return self._element_exists(self.popup_selectors.comments_section_indicator, timeout=1)
