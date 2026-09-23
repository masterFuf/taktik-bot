"""Unfollow actions, list extraction, scrolling, and sorting."""

import time
import random
from typing import Dict, List, Any, Optional

from taktik.core.clone import get_active_package
from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.social_media.instagram.actions.atomic.interaction.profile_interaction import (
    classify_follow_state,
)
from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS


def _vertical_band(element) -> Optional[tuple]:
    """(centre, top, bottom) of an element's bounds, or None when they are unreadable."""
    try:
        bounds = tuple(element.bounds)  # (left, top, right, bottom)
        if len(bounds) == 4 and bounds[3] > bounds[1]:
            return (bounds[1] + bounds[3]) // 2, bounds[1], bounds[3]
    except Exception:
        pass
    return None


class UnfollowActionsMixin:
    """Mixin: perform unfollow, extract accounts, scroll & sort the following list."""

    # ─── Rows of an open follow list ──────────────────────────────────────────

    def _visible_follow_rows(self, require_username: bool = True) -> List[Dict[str, Any]]:
        """Every readable row of the open follow list: `username`, row `button`, and `state`.

        A row carries one username and one action button, paired by vertical position: the
        centre of the username falls inside the vertical range of the button, the same pairing
        as `get_row_follow_state`. The button text goes through `classify_follow_state` and the
        locale labels, so a row reads 'following' in English ("Following") as in French
        ("Suivi(e)"), and 'follow_back' for "Follow back" / "Suivre en retour". With
        `require_username`, a button nobody can name at its height is left out: an unfollow is
        never tapped on an anonymous row (it used to be recorded on a profile called "unknown").
        """
        rows: List[Dict[str, Any]] = []
        try:
            d = self.device.device
            package = get_active_package()
            names = []
            for el in d.xpath(UNFOLLOW_SELECTORS.follow_list_username_selector(package)).all():
                username = (el.text or '').strip().lstrip('@')
                band = _vertical_band(el)
                if username and band and self._is_valid_username(username):
                    names.append((username, band[0]))
            for button in d.xpath(UNFOLLOW_SELECTORS.follow_list_row_button_selector(package)).all():
                band = _vertical_band(button)
                if band is None:
                    continue
                username = next((name for name, centre in names if band[1] <= centre <= band[2]), None)
                if username is None and require_username:
                    continue
                rows.append({
                    'username': username,
                    'button': button,
                    'state': classify_follow_state(button.text or '', PROFILE_SELECTORS) or 'unknown',
                })
        except Exception as e:
            self.logger.debug(f"Error reading the follow list rows: {e}")
        return rows

    def _tap_unfollow_confirm(self, timeout: float = 2.0) -> bool:
        """Tap the confirmation dialog's unfollow button if it shows up within `timeout` seconds.

        Instagram asks for it on private accounts. The button is found by the dialog id and the
        localized unfollow label ("Unfollow", "Ne plus suivre"); returns False when no dialog came.
        """
        d = self.device.device
        selectors = UNFOLLOW_SELECTORS.unfollow_confirm_selectors(get_active_package())
        deadline = time.time() + timeout
        while True:
            for selector in selectors:
                el = d.xpath(selector)
                if el.exists:
                    self.logger.debug("Confirmation dialog detected, confirming the unfollow")
                    if not tap_element_human(self.device, el, logger=self.logger):
                        el.click()
                    return True
            if time.time() >= deadline:
                return False
            time.sleep(0.3)

    def _unfollow_account(self, username: str) -> bool:
        """
        Unfollow one account.
        
        Args:
            username: Nom d'utilisateur à unfollow
            
        Returns:
            True si l'unfollow a réussi
        """
        try:
            # Make sure we are on the profile
            if not self.detection_actions.is_on_profile_screen():
                if not self.nav_actions.navigate_to_profile(username):
                    return False
                time.sleep(1.5)
            
            # Tap the following button
            clicked = self._find_and_click(self._unfollow_selectors['following_button'], timeout=3)
            if clicked:
                self._human_like_delay('click')

            if not clicked:
                self.logger.warning(f"Cannot find Following button for @{username}")
                return False
            
            time.sleep(1)
            
            # Confirmer l'unfollow
            if self._find_and_click(self._unfollow_selectors['unfollow_confirm'], timeout=3):
                self._human_like_delay('click')
                self.logger.debug(f"✅ Unfollow confirmed for @{username}")

                # Back to the list
                self._go_back_to_following_list()
                return True
            
            # With no confirmation dialog the unfollow may have been immediate:
            # check whether the button now offers to follow again
            follow_button_indicators = self._unfollow_sel.follow_button_after_unfollow
            
            if self._is_element_present(follow_button_indicators):
                self.logger.debug(f"✅ Unfollow successful for @{username} (no confirmation needed)")
                self._go_back_to_following_list()
                return True
            
            self.logger.warning(f"Cannot confirm unfollow for @{username}")
            self._go_back_to_following_list()
            return False
            
        except Exception as e:
            self.logger.error(f"Error unfollowing @{username}: {e}")
            return False
    
    def _go_back_to_following_list(self):
        """Go back to the following list."""
        try:
            # Press back several times if needed
            for _ in range(3):
                if self.detection_actions.is_following_list_open():
                    return
                self.device.press('back')
                time.sleep(0.5)
        except Exception as e:
            self.logger.debug(f"Error going back to following list: {e}")
    
    def _extract_following_accounts(self, max_accounts: int = 100) -> List[str]:
        """
        Extract the accounts from the following list.
        
        Args:
            max_accounts: Nombre max de comptes à extraire
            
        Returns:
            List of usernames
        """
        accounts = []
        seen_accounts = set()
        scroll_attempts = 0
        max_scroll_attempts = 15
        
        self.logger.info(f"📋 Extracting following accounts (max: {max_accounts})")
        
        while len(accounts) < max_accounts and scroll_attempts < max_scroll_attempts:
            # Extract the visible accounts
            new_accounts = self._get_visible_following_accounts()
            
            for username in new_accounts:
                if username not in seen_accounts and len(accounts) < max_accounts:
                    seen_accounts.add(username)
                    accounts.append(username)
            
            if len(accounts) >= max_accounts:
                break
            
            # Scroll to reveal more accounts
            previous_count = len(accounts)
            self.scroll_actions.scroll_down()
            time.sleep(1.5)
            scroll_attempts += 1
            
            # No new account after the scroll
            if len(accounts) == previous_count:
                self.logger.debug("No new accounts found after scroll")
                break
        
        self.logger.info(f"✅ Extracted {len(accounts)} following accounts")
        return accounts
    
    def _get_visible_following_accounts(self) -> List[str]:
        """Read the usernames visible in the following list."""
        accounts = []
        
        try:
            for selector in self._unfollow_selectors['following_list_item']:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        try:
                            username = element.text
                            if username and self._is_valid_username(username):
                                accounts.append(self._clean_username(username))
                        except Exception:
                            continue
                    break
        except Exception as e:
            self.logger.debug(f"Error extracting following accounts: {e}")
        
        return accounts
    
    def _scroll_following_list(self):
        """Scroll the following list down (humanized controlled scroll, was fixed-centre swipe)."""
        try:
            human_scroll_raw(self.device.device, "down", distance_ratio=0.4)
        except Exception as e:
            self.logger.debug(f"Error scrolling: {e}")
    
    def _set_following_list_sort(self, sort_order: str = 'default') -> bool:
        """
        Set the sorting order for the following list.
        
        Args:
            sort_order: 'default', 'latest', or 'earliest'
            
        Returns:
            True if sorting was changed successfully, False otherwise
        """
        try:
            self.logger.info(f"📊 Setting following list sort order to: {sort_order}")
            
            # Click on the sort button to open the sort modal
            sort_button_clicked = False
            for selector in self._unfollow_selectors['sort_button']:
                element = self.device.xpath(selector)
                if element.exists:
                    if not tap_element_human(self.device, element, logger=self.logger):
                        element.click()
                    sort_button_clicked = True
                    self.logger.debug("Clicked sort button")
                    break
            
            if not sort_button_clicked:
                self.logger.warning("Could not find sort button")
                return False
            
            time.sleep(1)  # Wait for modal to appear
            
            # Select the appropriate sort option
            sort_selector_key = f'sort_option_{sort_order}'
            if sort_selector_key not in self._unfollow_selectors:
                self.logger.warning(f"Unknown sort order: {sort_order}")
                return False
            
            for selector in self._unfollow_selectors[sort_selector_key]:
                element = self.device.xpath(selector)
                if element.exists:
                    if not tap_element_human(self.device, element, logger=self.logger):
                        element.click()
                    self.logger.info(f"✅ Selected sort option: {sort_order}")
                    time.sleep(0.5)
                    return True
            
            self.logger.warning(f"Could not find sort option: {sort_order}")
            # Press back to close the modal if we couldn't select an option
            self.device.press('back')
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting sort order: {e}")
            return False
