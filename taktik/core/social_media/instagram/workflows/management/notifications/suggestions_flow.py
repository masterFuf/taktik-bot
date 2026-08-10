"""The "Suggestions" zone at the bottom of the notifications screen, end to end.

    reach the zone -> open the suggestion's PROFILE -> run the per-profile pipeline
    on it -> come back to the notifications -> scroll down again -> next.

The surface exposes only a display label, never the @handle, and a suggestion is an
unknown profile: the record has to be produced, not reconciled. Hence the visit, and
hence the cost of a target run rather than a scan.

The pipeline is injected (``profile_pipeline``), not reimplemented here; this module
owns only the navigation specific to this surface and the loop sequencing.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from ....actions.business.workflows.common.suggestion_visit import (
    SuggestionSurface,
    visit_suggestions,
)
from .suggestions_parsing import (
    find_suggestions_header_y,
    followable_suggestions,
    iter_text_nodes,
    parse_notification_suggestions,
)


class NotificationSuggestionsMixin:
    """Mixin: read the suggestions zone and run a qualified visit on its profiles."""

    # Two consecutive empty dumps end the list. One proves nothing: a render in
    # progress looks exactly like a finished list.
    _SUGGESTIONS_EMPTY_DUMP_RUNS = 2

    # Why the last descent stopped: 'reached' | 'no_suggestions_offered' | 'cap_hit'.
    # Set by reach_suggestions_zone, read by visit_suggestions so the reason is
    # reported verbatim.
    descent_outcome = "reached"

    # ------------------------------------------------------------------
    # Live screen geometry
    # ------------------------------------------------------------------
    def _screen_height(self) -> int:
        """Live screen height — the step between two rows derives from it."""
        try:
            return int(self.device.info.get("displayHeight", 2400))
        except Exception:
            return 2400

    def _screen_width(self) -> int:
        try:
            return int(self.device.info.get("displayWidth", 1080))
        except Exception:
            return 1080

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def scan_suggestions(self, root=None) -> List[Dict[str, Any]]:
        """Visible suggestion rows at the bottom of the screen, with their state."""
        from ....actions.atomic.interaction.profile_interaction import classify_follow_state
        from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS

        root = root if root is not None else self._dump_root()
        return parse_notification_suggestions(
            root,
            self.selectors.suggestions_header_texts,
            PROFILE_SELECTORS,
            classify_follow_state,
            screen_height=self._screen_height(),
            screen_width=self._screen_width(),
            header_resource_id=self.selectors.notification_section_header_resource_id,
            row_resource_id=self.selectors.suggestion_row_resource_id,
            button_resource_id=self.selectors.suggestion_button_resource_id,
        )

    @staticmethod
    def _row_key(row: Dict[str, Any]) -> str:
        """Dedup key for a row across two dumps.

        The label is enough in almost every case. Without one, the row's vertical band
        is used: imperfect after a scroll, but an empty string would make every
        label-less row look like the same one and silently skip all but the first.
        """
        label = (row.get("label") or "").strip()
        if label:
            return label.lower()
        top = row.get("row_top")
        return f"row@{int(top) // 50}" if top is not None else "row@?"

    def _report_unreadable_rows(self, rows: List[Dict[str, Any]]) -> None:
        """Report once that some button labels could not be read.

        An unreadable button label is a locale gap, not an uninteresting row, and a
        screen full of them looks exactly like a screen with no suggestions. Staying
        silent would turn a failure into "nothing to do".
        """
        unreadable = [row for row in rows if row.get("state") is None]
        if not unreadable or getattr(self, "_reported_unreadable_suggestions", False):
            return
        self._reported_unreadable_suggestions = True
        samples = ", ".join(repr(row.get("state_label", "")) for row in unreadable[:3])
        self.logger.warning(f"{len(unreadable)} suggestion row(s) unreadable "
                            f"(locale gap?): {samples}")

    # ------------------------------------------------------------------
    # Navigation specific to this zone
    # ------------------------------------------------------------------
    def _feed_signature(self, root) -> str:
        """Fingerprint of what is displayed, to tell whether the list moved.

        Two identical dumps mean the list is stuck: either the bottom is reached or the
        gesture did not take. Insisting helps in neither case.
        """
        if root is None:
            return ""
        return "|".join(f"{text}@{bounds[1]}" for _node, text, bounds in iter_text_nodes(root))

    def refresh_notifications_screen(self) -> bool:
        """Leave and re-open the activity screen to COLLAPSE the list.

        On a freshly opened screen the people section sits one or two screens from the
        top. Each "See more" tap taken by the preceding scan inserts a page of older
        notifications between us and that section, which is what turned the descent
        into dozens of scrolls. Leaving and coming back restores the original distance.
        """
        for _ in range(3):
            if not self._on_notifications_screen():
                break
            try:
                self.device.press("back")
            except Exception as exc:  # noqa: BLE001
                self.logger.debug(f"back before re-entering notifications failed: {exc}")
                break
            time.sleep(1.0)
        if self._tap_activity_and_check():
            return True
        return self.ensure_notifications_screen()

    def reach_suggestions_zone(self, max_scrolls: int = 60) -> bool:
        """Scroll down until the "Suggestions" header is on screen.

        The distance to the zone depends on the account, not on us: an active account
        stacks dozens of screens of notifications before it. A fixed scroll budget is
        therefore the wrong stop criterion. The descent stops on PROGRESS instead — it
        keeps going while the screen changes, and two identical screens in a row mean
        the bottom. ``max_scrolls`` is only an anti-loop guard.

        "See more" is never tapped here: it loads OLDER notifications, which insert
        themselves between us and the zone.

        On exit, ``descent_outcome`` says why the descent stopped: 'reached',
        'no_suggestions_offered' (bottom reached, and the people section served right
        now is not the suggestions one) or 'cap_hit' (guard hit while the list was
        still moving).
        """
        from .dump_parsing import parse_section_headers

        previous = None
        stale = 0
        seen_sections: List[str] = []
        for index in range(max(int(max_scrolls), 0) + 1):
            root = self._dump_root()
            if find_suggestions_header_y(
                root, self.selectors.suggestions_header_texts,
                self.selectors.notification_section_header_resource_id,
            ) is not None:
                self.descent_outcome = "reached"
                self.logger.info(f"Suggestions zone reached after {index} scroll(s)")
                return True
            for header in parse_section_headers(
                root, self.selectors.notification_section_header_resource_id
            ):
                if header not in seen_sections:
                    seen_sections.append(header)
            signature = self._feed_signature(root)
            stale = stale + 1 if signature and signature == previous else 0
            if stale >= 2:
                self.descent_outcome = "no_suggestions_offered"
                # Name the sections walked through: the people section served at the
                # bottom of this screen changes identity from one pass to the next, and
                # without those names in the logs "no suggestions" is indistinguishable
                # from a failure.
                sections = ", ".join(repr(s) for s in seen_sections[-4:]) or "none"
                self.logger.info(
                    f"Bottom of the notifications list reached after {index} scroll(s): "
                    f"Instagram is not serving a suggestions section right now "
                    f"(sections seen: {sections})"
                )
                return False
            previous = signature
            self._scroll_down(1)
        self.descent_outcome = "cap_hit"
        self.logger.warning(f"Suggestions zone not reached: the {max_scrolls}-scroll safety "
                            f"cap was hit while the list was still moving")
        return False

    def open_suggestion_profile(self, row: Dict[str, Any],
                                load_timeout_s: float = 8.0) -> bool:
        """Open a suggestion row's profile, and PROVE it.

        Taps the row body (``row_point``), not its button: the label is not clickable
        but its ancestor cell is and receives the event. The button is a separate
        target that would follow blindly without ever opening the profile.

        Success is not "the tap was sent" but "we are on a profile", which the injected
        pipeline proves using the signatures specific to the profile surface.
        """
        pipeline = getattr(self, "profile_pipeline", None)
        if pipeline is None:
            self.logger.error("Cannot open a suggestion profile: no profile pipeline injected")
            return False
        point = row.get("row_point")
        if not point:
            self.logger.warning(f"Suggestion '{row.get('label') or '?'}' has no row point to tap")
            return False
        if not self._tap_point(point, f"Open suggestion '{row.get('label') or '?'}'"):
            return False
        return pipeline.wait_for_profile(timeout=load_timeout_s)

    def leave_suggestion_profile(self) -> bool:
        """Come back from the profile to the notifications screen.

        The pipeline may have scrolled into the posts or opened a story, so several
        back presses can be needed. If the screen still does not come back,
        ``ensure_notifications_screen`` restarts Instagram and re-navigates.
        """
        if self._return_to_notifications(attempts=6):
            return True
        self.logger.info("Back presses did not restore the notifications screen — recovering")
        return self.ensure_notifications_screen()

    # ------------------------------------------------------------------
    # Boucle complete
    # ------------------------------------------------------------------
    def visit_suggestions(self, max_profiles: int = 5, max_scrolls: int = 8,
                          max_descent_scrolls: int = 60,
                          refresh_first: bool = True,
                          delay_range: tuple = (4, 12),
                          on_profile: Optional[Callable[[Dict[str, Any]], None]] = None,
                          ) -> Dict[str, Any]:
        """Visit and qualify the accounts offered at the bottom of the screen.

        The sequencing (read, open, qualify, come back, next) belongs to the shared
        ``common/suggestion_visit`` service, which the dedicated people screen uses
        too; duplicating it would let the two surfaces drift on the fine rules —
        identity dedup, errors reported rather than skipped, pacing between profiles.
        This module keeps only the navigation, exposed through the adapter below.
        """
        if max_profiles > 0 and getattr(self, "profile_pipeline", None) is None:
            # Hard refusal: without a pipeline only the blind follow from the list
            # would remain, which is exactly what this mode replaces.
            self.logger.error("Suggestions visit skipped: no per-profile pipeline injected")
            self._notify("suggestions", "failed", "Profile pipeline unavailable")
            return {"visited": 0, "processed": 0, "follows": 0, "filtered": 0,
                    "skipped_known": 0, "errors": 0, "attempts": 0, "scrolls": 0,
                    "skipped_follow_back": 0, "profiles": [], "stop_reason": "no_pipeline"}

        self._optimize_locale()  # the zone header and the buttons are TEXT
        if refresh_first:
            # The preceding scan expanded the list with "See more", pushing the people
            # section dozens of screens down. Leaving and coming back collapses it.
            self.refresh_notifications_screen()
        self._reported_unreadable_suggestions = False

        return visit_suggestions(
            _NotificationsSuggestionSurface(self, max_descent_scrolls),
            max_profiles=max_profiles, max_scrolls=max_scrolls,
            delay_range=delay_range, on_profile=on_profile,
        )


class _NotificationsSuggestionSurface(SuggestionSurface):
    """Adapter: what is specific to this zone, and nothing else.

    Its one specificity is the DESCENT — the zone sits at the bottom of a list whose
    length depends on the account, and it is not always served.
    """

    name = "notifications"

    def __init__(self, workflow, max_descent_scrolls: int):
        self._wf = workflow
        self._max_descent_scrolls = max_descent_scrolls
        self.reach_failure_reason = "zone_not_reached"

    def reach(self) -> bool:
        if self._wf.reach_suggestions_zone(self._max_descent_scrolls):
            return True
        # 'no_suggestions_offered' is not a failure: no suggestions section is being
        # served right now. Reading it as a navigation problem would send someone
        # looking for a bug that does not exist.
        self.reach_failure_reason = self._wf.descent_outcome
        return False

    def scan(self) -> List[Dict[str, Any]]:
        rows = self._wf.scan_suggestions()
        self._wf._report_unreadable_rows(rows)
        return rows

    def followable(self, rows):
        return followable_suggestions(rows)

    def row_key(self, row):
        return self._wf._row_key(row)

    def open_profile(self, row) -> bool:
        return self._wf.open_suggestion_profile(row)

    def read_username(self):
        return self._wf.profile_pipeline.read_username()

    def process(self, username):
        return self._wf.profile_pipeline.process(username)

    def leave(self) -> bool:
        return self._wf.leave_suggestion_profile()

    def scroll(self) -> None:
        self._wf._scroll_down(1)

    def log_info(self, message: str) -> None:
        self._wf.logger.info(f"Suggestion {message}")

    def log_warning(self, message: str) -> None:
        self._wf.logger.warning(f"Suggestion {message}")

    def notify(self, step: str, status: str, message: str = "", **extra) -> None:
        self._wf._notify(step, status, message, **extra)

__all__ = ["NotificationSuggestionsMixin"]
