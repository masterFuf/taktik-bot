"""Followers/following list detection, extraction, and interaction."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, PROFILE_SELECTORS


class ListDetectionMixin(BaseAction):
    """Mixin: followers/following list state detection, username extraction, click on follower."""

    def is_followers_list_open(self) -> bool:
        return self._detect_element(self.detection_selectors.followers_list_indicators, "Followers list")
    
    def is_following_list_open(self) -> bool:
        return self.is_followers_list_open()
    
    def is_followers_list_limited(self) -> bool:
        """
        Detect if the followers list is limited (Meta Verified / Business accounts).
        Instagram shows: "We limit the number of followers shown for certain Meta Verified and Business accounts."
        """
        return self._detect_element(self.detection_selectors.limited_followers_indicators, "Limited followers list", log_found=False)
    
    def is_followers_list_end_reached(self) -> bool:
        """
        Detect if we've reached the end of the followers list.
        Instagram shows: "And X others" when there are more followers but they're hidden.
        """
        return self._detect_element(self.detection_selectors.followers_list_end_indicators, "Followers list end", log_found=False)
    
    def is_suggestions_section_visible(self) -> bool:
        """
        Detect if the suggestions section is visible (indicates end of real followers).
        Instagram shows: "Suggested for you" header after the last real follower.
        """
        return self._detect_element(self.detection_selectors.suggestions_section_indicators, "Suggestions section", log_found=False)

    def is_in_suggestions_section(self) -> bool:
        """
        Détecte si on est dans la section suggestions (après la liste des vrais followers).
        Retourne True si on voit des éléments de suggestions.
        """
        return self._detect_element(
            self.detection_selectors.suggestions_section_indicators, 
            "Suggestions section"
        )

    # === Username extraction ===

    def extract_usernames_from_follow_list(self) -> List[str]:
        usernames = []
        
        for selector in self.detection_selectors.follow_list_username_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        username_text = element.text
                        if username_text:
                            clean_username = self._clean_username(username_text)
                            if self._is_valid_username(clean_username):
                                usernames.append(clean_username)
                    break
            except Exception as e:
                self.logger.debug(f"Error extracting usernames: {e}")
                continue
        
        unique_usernames = list(dict.fromkeys(usernames))
        self.logger.debug(f"{len(unique_usernames)} usernames extracted from list")
        return unique_usernames
    
    def get_visible_followers_with_elements(self) -> List[Dict[str, Any]]:
        """
        Récupère les followers visibles avec leurs éléments cliquables.
        Utilisé pour le nouveau workflow d'interaction directe.
        
        Returns:
            Liste de dicts avec 'username' et 'element' (élément cliquable)
        """
        followers = []
        
        for selector in self.detection_selectors.follow_list_username_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        username_text = element.text
                        if username_text:
                            clean_username = self._clean_username(username_text)
                            if self._is_valid_username(clean_username):
                                followers.append({
                                    'username': clean_username,
                                    'element': element
                                })
                    break
            except Exception as e:
                self.logger.debug(f"Error getting followers with elements: {e}")
                continue
        
        self.logger.debug(f"{len(followers)} clickable followers found")
        return followers
    
    def click_follower_in_list(self, username: str) -> bool:
        """
        Clique sur un follower spécifique dans la liste.
        
        Args:
            username: Le username du follower à cliquer
            
        Returns:
            True si le clic a réussi
        """
        try:
            # Chercher l'élément avec ce username
            for selector in self.detection_selectors.follow_list_username_selectors:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        element_text = element.text
                        if element_text:
                            clean_text = self._clean_username(element_text)
                            if clean_text == username:
                                element.click()
                                self.logger.debug(f"✅ Clicked on @{username} in list")
                                return True
            
            self.logger.warning(f"❌ Could not find @{username} in visible list")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking follower @{username}: {e}")
            return False
