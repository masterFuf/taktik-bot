"""Unfollow actions, list extraction, scrolling, and sorting."""

import time
import random
from typing import Dict, List, Any, Optional

from taktik.core.clone import get_active_package
from taktik.core.shared.device.ui_dump import index_of_closest_row
from taktik.core.shared.behavior.gesture_primitives import human_drag_between_raw
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.social_media.instagram.actions.atomic.interaction.profile_interaction import (
    classify_follow_state,
)
from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from ..list_proof import parse_tab_count


# A row button that CONTRADICTS the tab it is read on: its row is not part of that list. A blank
# button says nothing and keeps its row. Deep in a long list Instagram 410 leaves most row buttons
# blank for good (Pixel 3, 2026-09-24: 1 or 2 filled of 9, the same after 30 s and five more
# drags); a read that waited for "Suivi(e)" on every row counted 1 or 2 rows a screen, then none,
# and stopped at about 150 of 1 928 followings as if the list had ended.
ROW_STATES_NOT_IN_TAB = {
    # We do not follow them, or not yet
    'following': frozenset({'follow', 'follow_back', 'requested'}),
    # Nobody who follows us is offered a plain "Follow" ("Follow back" is)
    'followers': frozenset({'follow'}),
}


def row_belongs_to_tab(state: Optional[str], tab: str) -> bool:
    """Does a row whose button reads `state` belong to the `tab` list? None: no such row read."""
    return state is not None and state not in ROW_STATES_NOT_IN_TAB[tab]


class LeftOutRows:
    """The names a list read saw but never counted, and why: what a read that falls short of the
    tab's count has to explain. On a phone (2026-09-24) a read ended at the suggestions with 1 873
    of 1 928 followings, and the log could not tell hidden accounts from rows the read refused."""

    def __init__(self):
        self.refused: Dict[str, str] = {}   # username -> state of its button when refused
        self.unpaired: set = set()          # names shown without a button paired to them

    def refuse(self, username: str, state: Optional[str]) -> None:
        self.refused.setdefault(username, state or 'no_row')

    def summary(self, read) -> Dict[str, int]:
        """Counts of names never read, by the last reason seen for each."""
        counts: Dict[str, int] = {}
        for username, state in self.refused.items():
            if username not in read:
                counts[state] = counts.get(state, 0) + 1
        never_paired = len(self.unpaired - set(read) - set(self.refused))
        if never_paired:
            counts['no_button'] = never_paired
        return counts


# Where one drag of a follow list starts and ends, as shares of the screen: about 45% of travel,
# which leaves about three rows of overlap between two reads.
FOLLOW_LIST_DRAG_X = (0.35, 0.65)
FOLLOW_LIST_DRAG_FROM = (0.76, 0.80)
FOLLOW_LIST_DRAG_TO = (0.31, 0.35)


def _closest_on_row(button_band, names) -> Optional[tuple]:
    """The (username, centre, element) of `names` on the same row as a button: the closest centre,
    no farther than the button's own height (rows are about twice that apart)."""
    if not names:
        return None
    centre, top, bottom = button_band
    index = index_of_closest_row(centre, [entry[1] for entry in names])
    if index is None or abs(names[index][1] - centre) > max(bottom - top, 1):
        return None
    return names[index]


def _pair_subtitles(names_by_y, subtitles) -> Dict[str, str]:
    """Each username's display name: the subtitle whose centre lies between its username's centre
    and the next username's. A row without a subtitle gets none (never its neighbour's)."""
    paired: Dict[str, str] = {}
    for index, (y, username) in enumerate(names_by_y):
        next_y = names_by_y[index + 1][0] if index + 1 < len(names_by_y) else float("inf")
        below = [(sy, text) for sy, text in subtitles if y < sy < next_y]
        if below:
            paired[username] = min(below)[1]
    return paired


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

    def _visible_follow_rows(self, require_username: bool = True,
                             with_display_names: bool = False) -> List[Dict[str, Any]]:
        """Every readable row of the open follow list: `username`, row `button`, and `state`.

        A row carries one username and one action button, paired by vertical position: the
        username whose centre is closest to the button's, within one button height -- the same
        pairing as `get_row_follow_state`. The button text goes through `classify_follow_state` and the
        locale labels, so a row reads 'following' in English ("Following") as in French
        ("Suivi(e)"), and 'follow_back' for "Follow back" / "Suivre en retour". With
        `require_username`, a button nobody can name at its height is left out: an unfollow is
        never tapped on an anonymous row (it used to be recorded on a profile called "unknown").
        `with_display_names` adds each row's `display_name` (the line under its username): the
        syncs used to make three device calls PER ROW for it.

        ONE dump answers for the usernames, the buttons and the names. Each `.all()` used to take its
        own: while the list was still moving, a username and its button came from two different
        positions of the list, the pairing failed, and rows were left out -- 85 of 232 on a phone
        (2026-09-24), which a list read then counted as never there.

        The suggestions Instagram shows under a list are not rows of it: nothing at or below their
        first sign is returned, and `suggestions_on_screen` then says the list ended on this screen.
        """
        rows: List[Dict[str, Any]] = []
        self.suggestions_on_screen = False
        # Names of this screen no button was paired to (see LeftOutRows)
        self.unpaired_on_screen = set()
        try:
            d = self.device.device
            package = get_active_package()
            screen = d.dump_hierarchy()
            suggestions_top = self._suggestions_top(d, screen)
            self.suggestions_on_screen = suggestions_top is not None

            def above_suggestions(band) -> bool:
                return suggestions_top is None or band[0] < suggestions_top

            names = []
            for el in d.xpath(UNFOLLOW_SELECTORS.follow_list_username_selector(package), screen).all():
                username = (el.text or '').strip().lstrip('@')
                band = _vertical_band(el)
                if username and band and above_suggestions(band) and self._is_valid_username(username):
                    names.append((username, band[0], el))
            for button in d.xpath(UNFOLLOW_SELECTORS.follow_list_row_button_selector(package), screen).all():
                band = _vertical_band(button)
                if band is None or not above_suggestions(band):
                    continue
                # Paired by the CLOSEST centre, within one button height: on Instagram 410 a row
                # with a display name lifts its username so that its centre sits a few pixels ABOVE
                # the button's top (measured on a Pixel 3, 2026-09-24). "The username's centre
                # inside the button's range" then failed for nearly every row; a list read skipped
                # them all and an unfollow could not read the row it had just changed.
                paired = _closest_on_row(band, names)
                username = paired[0] if paired else None
                if username is None and require_username:
                    continue
                rows.append({
                    'username': username,
                    'name_element': paired[2] if paired else None,
                    'button': button,
                    'state': classify_follow_state(button.text or '', PROFILE_SELECTORS) or 'unknown',
                })
            self.unpaired_on_screen = {entry[0] for entry in names} - {row['username'] for row in rows}
            if with_display_names:
                names_by_y = sorted((entry[1], entry[0]) for entry in names)
                subtitles = []
                for el in d.xpath(UNFOLLOW_SELECTORS.follow_list_subtitle_selector(package), screen).all():
                    band = _vertical_band(el)
                    if band:
                        subtitles.append((band[0], (el.text or '').strip()))
                display = _pair_subtitles(names_by_y, subtitles)
                for row in rows:
                    row['display_name'] = display.get(row['username'], '') if row['username'] else ''
        except Exception as e:
            self.logger.debug(f"Error reading the follow list rows: {e}")
        return rows

    @staticmethod
    def _suggestions_top(d, screen: str) -> Optional[int]:
        """Top of the first sign of the suggestions under a follow list on this dump (their own
        row ids, or their localized header), or None."""
        tops = []
        for selector in DETECTION_SELECTORS.suggestions_section_indicators:
            try:
                for element in d.xpath(selector, screen).all():
                    band = _vertical_band(element)
                    if band:
                        tops.append(band[1])
            except Exception:
                continue
        return min(tops) if tops else None

    def _session_stop_reason(self):
        """The session's stop reason when one of its limits is reached (its duration, the run's
        stop lock), else None. None without a session manager (the Lab)."""
        session = getattr(self, 'session_manager', None)
        if session is None or not hasattr(session, 'should_continue'):
            return None
        try:
            keep_going, reason = session.should_continue()
        except Exception:
            return None
        return None if keep_going else reason

    def _sync_should_stop(self) -> bool:
        """The session's limits during a list read. A read of a large list went on past the
        session's end (a 25-minute session, 2026-09-24)."""
        reason = self._session_stop_reason()
        if reason:
            self.logger.warning(f"List read stopped by the session: {reason}")
        return bool(reason)

    def _live_follow_entries(self, username_elements) -> List[tuple]:
        """(index, username, element) of each username element, read one by one: the enriched
        syncs tap into profiles and need live elements."""
        entries = []
        for i in range(username_elements.count):
            try:
                el = username_elements[i]
                username = (el.get_text() or '').strip().lstrip('@')
            except Exception:
                continue
            if username and self._is_valid_username(username):
                entries.append((i, username, el))
        return entries

    def _live_display_name(self, d, package: str, index: int) -> str:
        """The index-th display name of the list, read live (enriched syncs only)."""
        try:
            subtitle_els = d(resourceId=UNFOLLOW_SELECTORS.active_follow_list_subtitle_resource_id(package))
            if subtitle_els.exists and index < subtitle_els.count:
                return subtitle_els[index].get_text() or ''
        except Exception:
            pass
        return ''

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
        """Go back to the following list, one verified Back at a time."""
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
        """Advance the follow list by a known amount. False when the gesture failed: a read
        that could not scroll proves nothing about the end of the list."""
        return self._drag_follow_list()

    def _drag_follow_list(self) -> bool:
        """Press, carry the list up about 45% of the screen, release at near-zero velocity.

        Measured on a phone (2026-09-24): the sampled scroll curve is capped at 34% of the screen
        (about 3 rows of 9), and a fast drag released at speed let the list coast past rows nobody
        read. A drag that stops before lifting moves the list exactly where the finger went, leaving
        about three rows of overlap between two reads. Points vary with each gesture."""
        try:
            d = self.device.device
            width, height = d.window_size()
            x = int(width * random.uniform(*FOLLOW_LIST_DRAG_X))
            start = (x, int(height * random.uniform(*FOLLOW_LIST_DRAG_FROM)))
            end = (x + int(width * random.uniform(-0.03, 0.03)), int(height * random.uniform(*FOLLOW_LIST_DRAG_TO)))
            return human_drag_between_raw(d, start, end, duration=random.uniform(0.55, 0.8)) is not False
        except Exception as e:
            self.logger.debug(f"Error scrolling: {e}")
            return False

    # How long the list's sort header may take to name the option just tapped
    sort_confirm_timeout = 3.0

    def _sort_confirmed(self, option_text: str) -> bool:
        """Does the list's sort header now name `option_text` ("Trié par Date de suivi : plus
        récent")? Compared with the spaces normalized: Instagram puts a non-breaking space before
        the colon in French (Pixel 3, IG 410, 2026-09-24)."""
        def plain(text: str) -> str:
            return ' '.join((text or '').replace('\u00a0', ' ').split())

        wanted = plain(option_text)
        if not wanted:
            return False
        deadline = time.time() + self.sort_confirm_timeout
        while True:
            for selector in self._unfollow_selectors['sort_entry_label']:
                label = self.device.xpath(selector)
                if label.exists and wanted in plain(label.get_text()):
                    return True
            if time.time() >= deadline:
                return False
            time.sleep(0.3)

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
                    chosen = element.get_text() or ''
                    if not tap_element_human(self.device, element, logger=self.logger):
                        element.click()
                    # The early stop of the sync relies on this order: a tap is not enough, the
                    # list's header must now name the option.
                    if self._sort_confirmed(chosen):
                        self.logger.info(f"✅ Sort confirmed on screen: {sort_order}")
                        return True
                    self.logger.warning(f"Sort option '{sort_order}' tapped but not confirmed on screen")
                    if self.device.xpath(selector).exists:  # the sheet did not close
                        self.device.press_back()
                    return False
            
            self.logger.warning(f"Could not find sort option: {sort_order}")
            # Press back to close the modal if we couldn't select an option
            self.device.press_back()
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting sort order: {e}")
            return False
