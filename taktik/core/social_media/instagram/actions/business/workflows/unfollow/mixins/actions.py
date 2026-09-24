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
from ..list_proof import parse_tab_count


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
                    names.append((username, band[0], el))
            for button in d.xpath(UNFOLLOW_SELECTORS.follow_list_row_button_selector(package)).all():
                band = _vertical_band(button)
                if band is None:
                    continue
                paired = next((entry for entry in names if band[1] <= entry[1] <= band[2]), None)
                username = paired[0] if paired else None
                if username is None and require_username:
                    continue
                rows.append({
                    'username': username,
                    'name_element': paired[2] if paired else None,
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

    following_tab_timeout = 2.0
    # After a tab switch the new list loads: its first rows are awaited this long.
    list_load_timeout = 3.0

    def _ensure_following_tab(self) -> bool:
        """Make sure the open list is OUR FOLLOWING tab, not the followers one.

        Since Instagram 410 the followers and following lists are one screen with tabs ("673
        followers", "1 287 suivi(e)s", "0 abonnements", "À vérifier"), opened on the tab of the
        counter tapped. A complete read of the wrong tab would record our followers as accounts we
        follow, and mark every following it did not see as unfollowed elsewhere: the tab is
        checked, tapped when another one is shown, and the list refused when the following tab
        cannot be confirmed. A screen without the tab layout (one list per screen) is taken as is.
        """
        return self._ensure_list_tab("following")

    def _ensure_followers_tab(self) -> bool:
        """The same guard for OUR FOLLOWERS tab: read on the following tab, the followers sync would
        take every account we follow for a follower, and the mutual mode would unfollow them all."""
        return self._ensure_list_tab("followers")

    def _ensure_list_tab(self, kind: str) -> bool:
        d = self.device.device
        package = get_active_package()
        if not d.xpath(UNFOLLOW_SELECTORS.unified_follow_list_tab_layout_selector(package)).exists:
            return True
        if self._list_tab_selected(package, kind):
            return True
        tab = next((element for element in (d.xpath(selector) for selector
                                            in UNFOLLOW_SELECTORS.unified_tab_selectors(package, kind))
                    if element.exists), None)
        if tab is None:
            self.logger.error(f"Unified follow list without a {kind} tab we can read: list refused")
            return False
        self.logger.info(f"Unified follow list opened on another tab: switching to the {kind} tab")
        if not tap_element_human(self.device, tab, logger=self.logger):
            tab.click()
        deadline = time.time() + self.following_tab_timeout
        while not self._list_tab_selected(package, kind):
            if time.time() >= deadline:
                self.logger.error(f"{kind.capitalize()} tab tapped but not shown: list refused")
                return False
            time.sleep(0.3)
        # The rows of the new tab load after the tab is shown: a read before them finds an empty
        # list and concludes it ended (review of 2026-09-24).
        self._wait_for_list_rows()
        return True

    def _list_tab_selected(self, package: str, kind: str) -> bool:
        d = self.device.device
        return any(d.xpath(selector).exists
                   for selector in UNFOLLOW_SELECTORS.unified_tab_selectors(package, kind, selected=True))

    def _following_tab_selected(self, package: str) -> bool:
        return self._list_tab_selected(package, "following")

    def _wait_for_list_rows(self) -> bool:
        """Wait, bounded, for the first username of the open list."""
        d = self.device.device
        selector = UNFOLLOW_SELECTORS.follow_list_username_selector(get_active_package())
        deadline = time.time() + self.list_load_timeout
        while not d.xpath(selector).exists:
            if time.time() >= deadline:
                return False
            time.sleep(0.3)
        return True

    def _list_tab_count(self, kind: str) -> Optional[int]:
        """The exact count the unified list shows on the `kind` tab ("1 287 suivi(e)s"), or None
        (no tabs, or an abbreviated count): what a complete read must reach (`list_proof`)."""
        d = self.device.device
        package = get_active_package()
        labels = UNFOLLOW_SELECTORS.tab_labels(kind)
        for selector in UNFOLLOW_SELECTORS.unified_tab_selectors(package, kind):
            try:
                for element in d.xpath(selector).all():
                    count = parse_tab_count(element.text, labels)
                    if count is not None:
                        return count
            except Exception as exc:
                self.logger.debug(f"Tab count not read ({kind}): {exc}")
        return None

    def _go_back_to_following_list(self):
        """Go back to the following list.

        With `press_back()` of the shared facade, which sends uiautomator2 the key NAME 'back'.
        The Instagram facade's `press('back')` sends 'KEYCODE_BACK', a name the uiautomator2 server
        does not know: the press is ignored without an error (12 presses out of 12 on the 4 phones
        of C2, 2026-09-23), and the engine stayed on the profile it had opened.
        """
        try:
            # Press back several times if needed
            for _ in range(3):
                if self.detection_actions.is_following_list_open():
                    return
                self.device.press_back()
                time.sleep(0.5)
        except Exception as e:
            self.logger.debug(f"Error going back to following list: {e}")
    
    def _scroll_following_list(self) -> bool:
        """Scroll the follow list down (humanized controlled scroll). False when the gesture
        failed: a read that could not scroll proves nothing about the end of the list."""
        try:
            return human_scroll_raw(self.device.device, "down", distance_ratio=0.4) is not False
        except Exception as e:
            self.logger.debug(f"Error scrolling: {e}")
            return False
    
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

            # No known label for that option in this language (French, as of 2026-09-24): do not
            # open the sheet at all. Opening it only to press back could, if the sheet had not
            # opened yet, leave the list instead.
            sort_selector_key = f'sort_option_{sort_order}'
            if not self._unfollow_selectors.get(sort_selector_key):
                self.logger.warning(f"No '{sort_order}' sort option known in this language — list left as is")
                return False
            
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
            self.device.press_back()
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting sort order: {e}")
            return False
