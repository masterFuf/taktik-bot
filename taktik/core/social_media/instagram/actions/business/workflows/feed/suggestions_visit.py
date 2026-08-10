"""Qualified visit of the people discovery screen.

Why this screen on top of the zone at the bottom of the activity feed: that zone is
**served by the algorithm** and changes identity from one pass to the next, so an
acquisition cannot rest on it. The discovery screen is a dedicated, whole screen.

The sequencing is not rewritten here: it comes from the shared
``common/suggestion_visit`` service, exactly like the notifications zone. This module
owns only the navigation specific to this screen.

Notable difference with the notifications zone: here the row carries a username field.
When that label has the shape of a real handle, the profile can be known as already
processed BEFORE opening it, sparing both the visit and the AI call. When it does not
have that shape, the profile is visited: being wrong there would cost a target, which
is worse than paying twice.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from ..common.suggestion_visit import SuggestionSurface, visit_suggestions
from .suggestions_parsing import followable_rows

# An Instagram handle: letters, digits, dot, underscore. A label that does not fit
# this mould is a display name, not a key, and is never used to query the database.
_HANDLE_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")


class DiscoverSuggestionsVisitMixin:
    """Mixin: qualified visit of the people discovery screen rows."""

    def open_discover_profile(self, row: Dict[str, Any], load_timeout_s: float = 8.0) -> bool:
        """Open a row profile, and PROVE it.

        Taps the NAME, not the centre of the row: the follow button occupies the right
        side, and aiming at the middle would follow from the list — which is exactly what
        this visit replaces. Without the name bounds, it aims at the left third of the row,
        derived from its live bounds.
        """
        bounds = row.get("name_bounds")
        if not bounds:
            row_bounds = row.get("row_bounds")
            if not row_bounds:
                self.logger.warning(f"Suggestion '{row.get('label') or '?'}': aucune geometrie a taper")
                return False
            x1, y1, x2, y2 = row_bounds
            bounds = (x1, y1, x1 + (x2 - x1) // 3, y2)

        if not self.device.human_tap(tuple(bounds)):
            self.logger.debug(f"Tap d'ouverture en echec pour '{row.get('label') or '?'}'")
            return False
        self._human_like_delay('navigation')
        return bool(self.detection_actions.wait_for_profile_screen(timeout=load_timeout_s))

    def leave_discover_profile(self, attempts: int = 6) -> bool:
        """Come back from the profile to the suggestions list.

        The pipeline may have scrolled into the posts or opened a story, so several back
        presses can be needed. The action-bar ARROW is tapped when present: this screen
        has been seen ignoring the hardware back key.
        """
        from taktik.core.social_media.instagram.ui.selectors import NAVIGATION_SELECTORS

        for _ in range(max(int(attempts), 1)):
            if self.is_on_discover_people_screen():
                return True
            if not self._tap_first_present(NAVIGATION_SELECTORS.back_buttons):
                try:
                    self.device.press('back')
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug(f"Touche back en echec: {exc}")
                    break
            self._human_like_delay('navigation')
        return self.is_on_discover_people_screen()

    def visit_discover_suggestions(self, config: Dict[str, Any],
                                   max_profiles: int = 5, max_scrolls: int = 15,
                                   delay_range: tuple = (4, 12)) -> Dict[str, Any]:
        """Visit and qualify the accounts of the already-open screen.

        Each profile walks the per-profile production pipeline — the same one the target
        and hashtag runs use — through ``_process_profile_on_screen``, which this class
        already carries. Nothing has to be injected here, unlike the notifications
        workflow, which is not a ``BaseBusinessAction``.
        """
        return visit_suggestions(
            _DiscoverSuggestionSurface(self, config),
            max_profiles=max_profiles, max_scrolls=max_scrolls,
            delay_range=delay_range,
        )

    def run_discover_visit_pass(self, config: Dict[str, Any], max_profiles: int = 5,
                                max_carousel_scrolls: int = 12,
                                max_scrolls: int = 15,
                                delay_range: tuple = (4, 12)) -> Dict[str, Any]:
        """Full pass: home -> carousel -> discovery screen -> visits -> back.

        Same entry path as the bulk follow, contacts modal included, since it is already
        proven. What happens once on the screen is the qualified visit rather than a
        follow from the list.

        Known and accepted limit: the entry goes through the feed carousel, itself served
        by the algorithm. Until a deterministic entry is wired, this pass can come back
        empty-handed, and it says so through its stop reason rather than
        de laisser croire qu'il n'y avait personne a suivre.
        """
        result = {
            'entered': False, 'visited': 0, 'processed': 0, 'follows': 0,
            'filtered': 0, 'skipped_known': 0, 'errors': 0,
            'contacts_dialog': 'absent', 'profiles': [],
            'stop_reason': 'carousel_not_found', 'returned_to_feed': False,
        }

        try:
            if not self.nav_actions.navigate_to_home():
                result['stop_reason'] = 'home_not_reached'
                return result
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"Retour a l'accueil impossible: {exc}")
            result['stop_reason'] = 'home_not_reached'
            return result

        if not self.find_feed_suggestions_carousel(max_carousel_scrolls).get('found'):
            return result

        if not self.open_suggestions_see_all():
            result['stop_reason'] = 'cta_tap_failed'
            return result

        result['contacts_dialog'] = self.handle_contacts_access_dialog(
            config.get('suggestions_contacts_choice', 'deny')
        )
        if result['contacts_dialog'] == 'other_dialog':
            # Another Instagram alert (restriction, update): not handled here,
            # and certainly not visited past.
            result['stop_reason'] = 'blocked_by_dialog'
            result['returned_to_feed'] = self._return_to_feed()
            return result

        if not self._wait_for_discover_screen():
            result['stop_reason'] = 'discover_screen_not_reached'
            result['returned_to_feed'] = self._return_to_feed()
            return result

        result['entered'] = True
        visit = self.visit_discover_suggestions(
            config, max_profiles=max_profiles, max_scrolls=max_scrolls,
            delay_range=delay_range,
        )
        result.update({k: visit[k] for k in
                       ('visited', 'processed', 'follows', 'filtered', 'skipped_known',
                        'errors', 'profiles', 'stop_reason')})
        result['returned_to_feed'] = self._return_to_feed()
        return result


class _DiscoverSuggestionSurface(SuggestionSurface):
    """Adapter: the navigation specific to the people discovery screen."""

    name = "discover_people"

    # Provenance written for every profile handled by this path.
    SOURCE_TYPE = "SUGGESTIONS"
    SOURCE_NAME = "discover_people"

    def __init__(self, business, config: Dict[str, Any]):
        self._biz = business
        self._config = config
        self.reach_failure_reason = "discover_screen_lost"

    def reach(self) -> bool:
        # The screen is already open, so this only checks we did not leave it between
        # two profiles (one back too many, a modal).
        return self._biz.is_on_discover_people_screen()

    def scan(self) -> List[Dict[str, Any]]:
        return self._biz.scan_discover_suggestions()

    def followable(self, rows):
        return followable_rows(rows)

    def row_key(self, row):
        return self._biz._row_key(row)

    def already_known(self, row) -> bool:
        """Does the label designate a profile already handled for this account?

        Only when it has the shape of a handle: a full name is often put in that field,
        and querying the database with it would answer nothing useful. Fail-open: the
        slightest doubt makes the profile visited.
        """
        label = (row.get("label") or "").strip().lstrip("@")
        if not label or not _HANDLE_RE.match(label):
            return False
        try:
            skippable, _reason = InstagramWorkflowStateService.is_profile_skippable(
                label, self._biz._get_account_id(),
            )
            return bool(skippable)
        except Exception as exc:  # noqa: BLE001 — never fatal
            self._biz.logger.debug(f"Could not read the already-handled flag for @{label}: {exc}")
            return False

    def open_profile(self, row) -> bool:
        return self._biz.open_discover_profile(row)

    def read_username(self) -> Optional[str]:
        return self._biz.detection_actions.get_username_from_profile()

    def process(self, username: str):
        return self._biz._process_profile_on_screen(
            username, self._config,
            source_type=self.SOURCE_TYPE, source_name=self.SOURCE_NAME,
            account_id=self._biz._get_account_id(),
            session_id=self._biz._get_session_id(),
        )

    def leave(self) -> bool:
        return self._biz.leave_discover_profile()

    def scroll(self) -> None:
        self._biz.scroll_discover_suggestions()

    def log_info(self, message: str) -> None:
        self._biz.logger.info(f"Discover {message}")

    def log_warning(self, message: str) -> None:
        self._biz.logger.warning(f"Discover {message}")


__all__ = ["DiscoverSuggestionsVisitMixin"]
