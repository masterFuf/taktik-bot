"""Followers/following list detection, extraction, and interaction."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ...core.base_action import BaseAction


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
        Are we in the suggestions section, past the real followers?
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
        Read the visible followers with their clickable elements.
        Used by the direct-interaction workflow.
        
        Returns:
            List of dicts with the username and its clickable element
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

    def get_row_follow_state(self, username: str) -> str:
        """Relationship shown by the ROW button of this follower, read WITHOUT opening the profile.

        Returns: 'follow' | 'follow_back' | 'following' | 'requested' | 'unknown'.
        Unknown when the row is unreadable or partially scrolled, and the caller then falls back
        on the profile-level guard. Each row carries exactly one username and one button, paired
        by vertical position: the centre of the username falls inside the vertical range of the
        button of the same row. No label is hardcoded: the text is classified through the
        shared classifier, using the locale labels, the same ones as the header.
        """
        try:
            from ..interaction.profile_interaction import classify_follow_state
            from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS

            def _yband(el):
                try:
                    b = tuple(el.bounds)  # (left, top, right, bottom)
                    if len(b) == 4 and b[3] > b[1]:
                        return (b[1] + b[3]) // 2, b[1], b[3]
                except Exception:
                    pass
                return None

            # vertical centre of the target username
            target_yc = None
            for selector in self.detection_selectors.follow_list_username_selectors:
                els = self.device.xpath(selector)
                if not els.exists:
                    continue
                for el in els.all():
                    t = el.text
                    if t and self._clean_username(t) == username:
                        band = _yband(el)
                        if band:
                            target_yc = band[0]
                        break
                if target_yc is not None:
                    break
            if target_yc is None:
                return 'unknown'

            # the row button whose vertical range holds that centre is on the same row
            for selector in PROFILE_SELECTORS.follow_list_row_buttons:
                els = self.device.xpath(selector)
                if not els.exists:
                    continue
                for el in els.all():
                    band = _yband(el)
                    if band and band[1] <= target_yc <= band[2]:
                        return classify_follow_state(el.text or '', PROFILE_SELECTORS) or 'unknown'
            return 'unknown'
        except Exception as exc:
            self.logger.debug(f"get_row_follow_state(@{username}) error: {exc}")
            return 'unknown'

    def click_follower_in_list(self, username: str) -> bool:
        """
        Tap a specific follower of the list.
        
        Args:
            username: the follower to tap
            
        Returns:
            True si le clic a réussi
        """
        try:
            # Look for the element carrying that username
            for selector in self.detection_selectors.follow_list_username_selectors:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        element_text = element.text
                        if element_text:
                            clean_text = self._clean_username(element_text)
                            if clean_text == username:
                                # Humanized tap (random point within bounds) instead of the exact
                                # centre — this is the most frequent tap of target/hashtag/post-likers
                                # (shared profile-open in followers/likers lists). Falls back to a
                                # centre click if the bounds are unreadable.
                                if not self._human_tap_bounds(element):
                                    element.click()
                                self.logger.debug(f"✅ Clicked on @{username} in list")
                                return True
            
            self.logger.warning(f"❌ Could not find @{username} in visible list")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking follower @{username}: {e}")
            return False
