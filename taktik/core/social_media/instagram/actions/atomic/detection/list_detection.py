"""Followers/following list detection, extraction, and interaction.

The rows of a list (their usernames, a row's button, the tap on a row) are read on ONE photo of
the screen per call (`_turn_photo`, step 3 of the one-photo spec): `d.xpath()` took a dump for
each `.exists` and each `.all()`, so a row's state cost four dumps and the rows two. The photo
answers as `d.xpath()` does, through the proxy's selector rewrite; its elements carry text and
bounds, and a row is tapped from its bounds.
"""

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
        """The usernames of the visible rows, each once, in screen order."""
        unique_usernames = list(dict.fromkeys(
            row['username'] for row in self.get_visible_followers_with_elements()))
        self.logger.debug(f"{len(unique_usernames)} usernames extracted from list")
        return unique_usernames
    
    def get_visible_followers_with_elements(self) -> List[Dict[str, Any]]:
        """
        Read the visible followers with their elements, on one photo of the screen.
        Used by the direct-interaction workflow.
        
        Returns:
            List of dicts with the username and its element: the photo's, which gives the
            row's text and bounds (tap it with `tap_element_human`, never `.click()`)
        """
        followers = []
        photo = self._turn_photo()
        if photo is None:
            return followers

        for selector in self.detection_selectors.follow_list_username_selectors:
            try:
                elements = photo.elements(selector)
                if elements:
                    for element in elements:
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
        by vertical position: the button whose centre is closest to the username's, within one
        button height (on IG 410 a username with a display name sits above its button's top). No label is hardcoded: the text is classified through the
        shared classifier, using the locale labels, the same ones as the header.

        The username and the buttons come from the same photo: read from successive dumps, a
        list still moving could pair a username with the button of another row.
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

            photo = self._turn_photo()
            if photo is None:
                return 'unknown'

            # vertical centre of the target username
            target_yc = None
            for selector in self.detection_selectors.follow_list_username_selectors:
                els = photo.elements(selector)
                if not els:
                    continue
                for el in els:
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

            # The row button whose centre is closest to that username's, within one button height,
            # is on the same row ("the centre inside the button's range" missed nearly every row
            # of an IG 410 list, where a username with a display name sits above its button).
            from taktik.core.shared.device.ui_dump import index_of_closest_row

            for selector in PROFILE_SELECTORS.follow_list_row_buttons:
                els = photo.elements(selector)
                if not els:
                    continue
                buttons = [(el, _yband(el)) for el in els]
                buttons = [(el, band) for el, band in buttons if band]
                index = index_of_closest_row(target_yc, [band[0] for _el, band in buttons])
                if index is None:
                    continue
                el, band = buttons[index]
                if abs(band[0] - target_yc) <= max(band[2] - band[1], 1):
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
            # Look for the element carrying that username, on one photo of the screen
            photo = self._turn_photo()
            selectors = self.detection_selectors.follow_list_username_selectors if photo is not None else []
            for selector in selectors:
                for element in photo.elements(selector):
                    element_text = element.text
                    if element_text:
                        clean_text = self._clean_username(element_text)
                        if clean_text == username:
                            # Humanized tap (random point within bounds) instead of the exact
                            # centre — this is the most frequent tap of target/hashtag/post-likers
                            # (shared profile-open in followers/likers lists). A photo's element
                            # carries no device: without usable bounds there is nothing to tap.
                            if not self._human_tap_bounds(element):
                                self.logger.warning(f"❌ @{username} found but not tapped (bounds unusable or tap failed)")
                                return False
                            self.logger.debug(f"✅ Clicked on @{username} in list")
                            return True
            
            self.logger.warning(f"❌ Could not find @{username} in visible list")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking follower @{username}: {e}")
            return False
