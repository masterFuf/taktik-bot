"""Atomic detection actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

Ce module permet de détecter l'état actuel de l'UI TikTok:
- Page courante (For You, Profile, Inbox, etc.)
- État des éléments (vidéo likée, utilisateur suivi, etc.)
- Popups et erreurs
"""

from typing import Optional, Dict, Any, Tuple
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import (
    NAVIGATION_SELECTORS,
    VIDEO_SELECTORS,
    PROFILE_SELECTORS,
    INBOX_SELECTORS,
    POPUP_SELECTORS,
    DETECTION_SELECTORS,
)


class DetectionActions(BaseAction):
    """Low-level detection actions for TikTok UI state.
    
    Permet de détecter la page courante, l'état des éléments,
    et les conditions d'erreur.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-detection-atomic")
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.video_selectors = VIDEO_SELECTORS
        self.profile_selectors = PROFILE_SELECTORS
        self.inbox_selectors = INBOX_SELECTORS
        self.popup_selectors = POPUP_SELECTORS
        self.detection_selectors = DETECTION_SELECTORS
    
    # === Page Detection ===
    
    def is_on_for_you_page(self) -> bool:
        """Check if currently on For You feed.
        
        Détecte via:
        - Tab "For You" sélectionné dans le header
        - Présence des boutons d'interaction vidéo
        """
        # Check if For You tab is visible and selected
        if self._element_exists(self.navigation_selectors.for_you_tab, timeout=2):
            # Also check for video interaction buttons
            if self._element_exists(self.video_selectors.like_button, timeout=1):
                return True
        
        # Fallback: check for home tab selected
        home_selected = [
            '//*[@resource-id="com.zhiliaoapp.musically:id/mkq"][@selected="true"]',
            '//android.widget.FrameLayout[@content-desc="Home"][@selected="true"]',
        ]
        return self._element_exists(home_selected, timeout=1)
    
    def is_on_profile_page(self) -> bool:
        """Check if currently on a profile page.
        
        Détecte via:
        - Présence du display name (qf8) ou username (qh5)
        - Présence des compteurs (following/followers/likes)
        """
        # Check for profile-specific elements
        if self._element_exists(self.profile_selectors.display_name, timeout=2):
            return True
        
        if self._element_exists(self.profile_selectors.username, timeout=2):
            return True
        
        # Check for profile tab selected
        profile_selected = [
            '//*[@resource-id="com.zhiliaoapp.musically:id/mks"][@selected="true"]',
            '//android.widget.FrameLayout[@content-desc="Profile"][@selected="true"]',
        ]
        return self._element_exists(profile_selected, timeout=1)
    
    def is_on_inbox_page(self) -> bool:
        """Check if currently on Inbox page.
        
        Détecte via:
        - Titre "Inbox"
        - Présence des sections de notification
        """
        if self._element_exists(self.inbox_selectors.inbox_title, timeout=2):
            return True
        
        # Check for inbox tab selected
        inbox_selected = [
            '//*[@resource-id="com.zhiliaoapp.musically:id/mkr"][@selected="true"]',
            '//android.widget.FrameLayout[@content-desc="Inbox"][@selected="true"]',
        ]
        return self._element_exists(inbox_selected, timeout=1)
    
    def is_on_friends_page(self) -> bool:
        """Check if currently on Friends page."""
        friends_selected = [
            '//*[@resource-id="com.zhiliaoapp.musically:id/mkp"][@selected="true"]',
            '//android.widget.FrameLayout[@content-desc="Friends"][@selected="true"]',
        ]
        return self._element_exists(friends_selected, timeout=1)
    
    def get_current_page(self) -> str:
        """Detect current page.
        
        Returns:
            str: 'for_you', 'following', 'profile', 'inbox', 'friends', 'search', 'unknown'
        """
        if self.is_on_for_you_page():
            return 'for_you'
        
        if self.is_on_profile_page():
            return 'profile'
        
        if self.is_on_inbox_page():
            return 'inbox'
        
        if self.is_on_friends_page():
            return 'friends'
        
        # Check for Following feed
        following_tab = [
            '//*[@content-desc="Following"][@selected="true"]',
            '//*[@text="Following"][@selected="true"]',
        ]
        if self._element_exists(following_tab, timeout=1):
            return 'following'
        
        # Check for search page
        if self._element_exists(['//*[contains(@resource-id, "search")]'], timeout=1):
            return 'search'
        
        return 'unknown'
    
    # === Video State Detection ===
    
    def is_video_liked(self) -> bool:
        """Check if current video is liked.
        
        Détecte via le content-desc qui change de "Like" à "Unlike".
        """
        unlike_indicators = [
            '//*[contains(@content-desc, "Unlike")]',
            '//*[contains(@content-desc, "Liked")]',
            '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Unlike")]',
        ]
        return self._element_exists(unlike_indicators, timeout=1)
    
    def is_video_favorited(self) -> bool:
        """Check if current video is in favorites."""
        favorited_indicators = [
            '//*[contains(@content-desc, "Remove from Favourites")]',
            '//*[contains(@content-desc, "Retirer des favoris")]',
        ]
        return self._element_exists(favorited_indicators, timeout=1)
    
    def is_user_followed(self) -> bool:
        """Check if current user is followed.
        
        Détecte via le texte du bouton qui change de "Follow" à "Following" ou "Friends".
        """
        following_indicators = [
            '//android.widget.Button[@text="Following"]',
            '//android.widget.Button[@text="Abonné"]',
            '//android.widget.Button[contains(@text, "Friends")]',
            '//*[contains(@content-desc, "Unfollow")]',
        ]
        return self._element_exists(following_indicators, timeout=1)
    
    # === Video Info Extraction ===
    
    def get_video_author(self) -> Optional[str]:
        """Get current video author username."""
        return self._get_element_text(self.video_selectors.author_username, timeout=1)
    
    def get_video_description(self) -> Optional[str]:
        """Get current video description."""
        return self._get_element_text(self.video_selectors.video_description, timeout=1)
    
    def get_video_like_count(self) -> Optional[str]:
        """Get current video like count."""
        return self._get_element_text(self.video_selectors.like_count, timeout=1)
    
    def get_video_comment_count(self) -> Optional[str]:
        """Get current video comment count."""
        return self._get_element_text(self.video_selectors.comment_count, timeout=1)
    
    def get_video_info(self, include_comment_count: bool = False) -> Dict[str, Any]:
        """Get all available info about current video.
        
        Args:
            include_comment_count: If True, also fetch comment count (slower).
        """
        info = {
            'author': self.get_video_author(),
            'description': self.get_video_description(),
            'like_count': self.get_video_like_count(),
            'is_liked': self.is_video_liked(),
            'is_favorited': self.is_video_favorited(),
            'is_ad': self.is_ad_video(),
        }
        if include_comment_count:
            info['comment_count'] = self.get_video_comment_count()
        return info
    
    # === Profile Info Extraction ===
    
    def get_profile_display_name(self) -> Optional[str]:
        """Get profile display name."""
        return self._get_element_text(self.profile_selectors.display_name, timeout=2)
    
    def get_profile_username(self) -> Optional[str]:
        """Get profile @username."""
        return self._get_element_text(self.profile_selectors.username, timeout=2)
    
    def get_profile_stats(self) -> Dict[str, Optional[str]]:
        """Get profile statistics (following, followers, likes)."""
        # Get all stat values
        stat_values = []
        stat_elements = self.profile_selectors.stat_value
        
        # Try to get the three values
        for i in range(3):
            selector = f'(//*[@resource-id="com.zhiliaoapp.musically:id/qfw"])[{i+1}]'
            value = self._get_element_text([selector], timeout=1)
            stat_values.append(value)
        
        return {
            'following': stat_values[0] if len(stat_values) > 0 else None,
            'followers': stat_values[1] if len(stat_values) > 1 else None,
            'likes': stat_values[2] if len(stat_values) > 2 else None,
        }
    
    def get_profile_info(self) -> Dict[str, Any]:
        """Get all available info about current profile."""
        stats = self.get_profile_stats()
        return {
            'display_name': self.get_profile_display_name(),
            'username': self.get_profile_username(),
            'following': stats.get('following'),
            'followers': stats.get('followers'),
            'likes': stats.get('likes'),
            'is_followed': self.is_user_followed(),
        }
    
    # === Ad Detection ===
    
    def is_ad_video(self) -> bool:
        """Check if current video is an advertisement.
        
        Détecte via le label "Ad" visible sur les vidéos sponsorisées.
        Resource-id: com.zhiliaoapp.musically:id/ru3
        """
        return self._element_exists(self.video_selectors.ad_label, timeout=1)
    
    # === Error & Popup Detection ===
    
    def has_popup(self) -> bool:
        """Check if there's a popup on screen."""
        if self._element_exists(self.popup_selectors.close_button, timeout=1):
            return True
        if self._element_exists(self.popup_selectors.dismiss_button, timeout=1):
            return True
        if self._element_exists(self.popup_selectors.promo_banner, timeout=1):
            return True
        # Check for collections popup
        if self._element_exists(self.popup_selectors.collections_popup, timeout=1):
            return True
        # Check for "Follow your friends" popup
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
    
    def has_notification_banner(self) -> bool:
        """Check if a notification banner is visible (e.g., 'X sent you new messages')."""
        return self._element_exists(self.popup_selectors.notification_banner, timeout=1)
    
    def is_on_inbox_page(self) -> bool:
        """Check if currently on the Inbox page (accidentally navigated there)."""
        return self._element_exists(self.popup_selectors.inbox_page_indicator, timeout=1)
    
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
    
    def has_error(self) -> bool:
        """Check if there's an error message on screen."""
        return self._element_exists(self.detection_selectors.error_message, timeout=1)
    
    def has_network_error(self) -> bool:
        """Check if there's a network error."""
        return self._element_exists(self.detection_selectors.network_error, timeout=1)
    
    def has_rate_limit(self) -> bool:
        """Check if rate limited (soft ban indicator)."""
        return self._element_exists(self.detection_selectors.rate_limit, timeout=1)
    
    def detect_problematic_state(self) -> Tuple[bool, str]:
        """Detect if in a problematic state.
        
        Returns:
            Tuple[bool, str]: (is_problematic, reason)
        """
        if self.has_rate_limit():
            return True, "rate_limit"
        
        if self.has_network_error():
            return True, "network_error"
        
        if self.has_error():
            return True, "error"
        
        return False, "ok"
    
    # === TikTok App State ===
    
    def is_tiktok_running(self) -> bool:
        """Check if TikTok app is running and visible."""
        # Check for any TikTok-specific element
        tiktok_indicators = [
            '//*[@package="com.zhiliaoapp.musically"]',
            '//*[@resource-id="com.zhiliaoapp.musically:id/mky"]',  # Bottom nav
        ]
        return self._element_exists(tiktok_indicators, timeout=2)
    
    def is_logged_in(self) -> bool:
        """Check if user is logged in.
        
        If on profile page and can see profile info, user is logged in.
        """
        # Navigate to profile and check
        if self._element_exists(self.navigation_selectors.profile_tab, timeout=2):
            # Profile tab exists, likely logged in
            return True
        return False
