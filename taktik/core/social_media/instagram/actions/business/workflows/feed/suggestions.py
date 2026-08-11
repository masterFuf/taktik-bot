"""The suggestions-follow mode of the feed workflow.

The full path, one method per step so each stays unit-testable in isolation:

feed -> carousel netego "Suggested for you" -> CTA "See all" -> modale d'acces aux
contacts modal -> people discovery screen -> bulk follow -> back to the feed.

Regles metier :

- neither follow-back nor follow-request acceptance happens here: both belong to
  the notifications workflow. Only a button whose state is exactly 'follow' is
  tapped (see ``followable_rows``);
- NO profile is visited: this is a bulk follow from the list, not a qualified
  acquisition, so no profile or AI filter applies;
- the contacts modal is handled explicitly, never left to the
  pages problematiques generique.

Known limit of the surface: the @handle is not exposed in this list, only the
display label. Follows are therefore recorded under that label, with the
provenance in ``content``; reconciliation with the real handles happens later,
through the follow graph sync.
"""

import random
import time
from typing import Any, Dict, List, Optional

from lxml import etree

from taktik.core.shared.telemetry import emit_step
from ....atomic.interaction.profile_interaction import classify_follow_state
from ....core.ipc import IPCEmitter
from .suggestions_parsing import (
    followable_rows,
    is_discover_people_screen,
    parse_feed_suggestions_carousel,
    parse_suggestion_rows,
    read_screen_title,
)


class FeedSuggestionsMixin:
    """Mixin: suggestions carousel detection and the bulk follow that goes with it."""

    # Consecutive scroll passes with no new followable row before the list is
    # considered exhausted (same spirit as the stop policy of the other workflows
    # target : on raisonne en comptes rencontres, pas en nombre de scrolls).
    _SUGGESTIONS_EMPTY_SCROLL_RUNS = 2

    # ------------------------------------------------------------------
    # Screen reading
    # ------------------------------------------------------------------

    def _suggestions_dump_root(self):
        """Dump complet (non compresse) parse en racine lxml, ou None."""
        xml = None
        try:
            xml = self.device.dump_hierarchy(compressed=False)
        except TypeError:
            try:
                xml = self.device.dump_hierarchy()
            except Exception as exc:
                self.logger.debug(f"dump_hierarchy failed: {exc}")
        except Exception as exc:
            self.logger.debug(f"dump_hierarchy failed: {exc}")
        if not xml:
            return None
        try:
            return etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
        except Exception as exc:
            self.logger.debug(f"XML parse failed: {exc}")
            return None

    def has_feed_suggestions_carousel(self) -> bool:
        """LIGHT carousel probe: one device access, no full dump.

        Called on every post of the feed loop, so it must stay cheap; the full dump is
        only paid once the carousel is confirmed.
        """
        from taktik.core.social_media.instagram.ui.selectors import FEED_SUGGESTIONS_SELECTORS
        try:
            for selector in FEED_SUGGESTIONS_SELECTORS.carousel_see_all:
                if self.device.xpath(selector).exists:
                    return True
        except Exception as exc:
            self.logger.debug(f"Suggestions carousel probe failed: {exc}")
        return False

    def detect_feed_suggestions_carousel(self, root=None) -> Dict[str, Any]:
        """State of the suggestions carousel in the current feed."""
        from taktik.core.social_media.instagram.ui.selectors import FEED_SUGGESTIONS_SELECTORS
        root = root if root is not None else self._suggestions_dump_root()
        return parse_feed_suggestions_carousel(root, FEED_SUGGESTIONS_SELECTORS)

    def is_on_discover_people_screen(self, root=None) -> bool:
        """True when the people discovery screen is shown."""
        from taktik.core.social_media.instagram.ui.selectors import DISCOVER_PEOPLE_SELECTORS
        root = root if root is not None else self._suggestions_dump_root()
        return is_discover_people_screen(root, DISCOVER_PEOPLE_SELECTORS)

    def scan_discover_suggestions(self, root=None) -> List[Dict[str, Any]]:
        """Visible suggestion rows, with their relationship state."""
        from taktik.core.social_media.instagram.ui.selectors import (
            DISCOVER_PEOPLE_SELECTORS,
            PROFILE_SELECTORS,
        )
        root = root if root is not None else self._suggestions_dump_root()
        return parse_suggestion_rows(
            root, DISCOVER_PEOPLE_SELECTORS, PROFILE_SELECTORS, classify_follow_state
        )

    # ------------------------------------------------------------------
    # Navigation d'entree
    # ------------------------------------------------------------------

    def open_suggestions_see_all(self, root=None) -> bool:
        """Tap the carousel "See all" CTA to open the people discovery screen.

        The CTA is targeted by resource-id, so language-neutral, and tapped on its real
        bounds — never on a hardcoded coordinate.
        """
        carousel = self.detect_feed_suggestions_carousel(root)
        if not carousel.get("cta_bounds"):
            self.logger.debug("Suggestions carousel CTA not visible")
            return False
        if not self.device.human_tap(carousel["cta_bounds"]):
            self.logger.debug("Suggestions CTA tap failed")
            return False
        self.logger.info(f"Opened suggestions list from feed carousel "
                         f"('{carousel.get('title') or 'Suggested for you'}')")
        emit_step("tap", action="suggestions_see_all")
        self._human_like_delay('navigation')
        return True

    def handle_contacts_access_dialog(self, choice: str = 'deny') -> str:
        """Handle the "allow access to contacts" modal.

        Returns ``'denied'`` | ``'allowed'`` | ``'absent'`` | ``'other_dialog'``.

        The modal carries the GENERIC Instagram alert resource-ids, which the
        restriction alert carries too. The HEADLINE must therefore match the
        ``contacts_access_headline_texts`` fragments before anything is tapped.
        Otherwise this returns ``'other_dialog'`` without touching the screen, and the
        alert is left to the problematic-page detector.
        """
        from taktik.core.social_media.instagram.ui.selectors import POPUP_SELECTORS

        headline = None
        for selector in POPUP_SELECTORS.contacts_access_dialog:
            element = self.device.xpath(selector)
            if element.exists:
                headline = (element.get_text() or '').strip()
                break
        if headline is None:
            return 'absent'

        lowered = headline.lower()
        fragments = [f.strip().lower() for f in POPUP_SELECTORS.contacts_access_headline_texts
                     if f and f.strip()]
        if not any(fragment in lowered for fragment in fragments):
            self.logger.warning(f"Alert dialog is not the contacts request "
                                f"('{headline[:60]}') - leaving it untouched")
            return 'other_dialog'

        allow = str(choice).lower() in ('allow', 'allowed', 'accept', 'true', '1')
        selectors = (POPUP_SELECTORS.contacts_access_allow_button if allow
                     else POPUP_SELECTORS.contacts_access_deny_button)
        label = 'allowed' if allow else 'denied'

        for selector in selectors:
            element = self.device.xpath(selector)
            if element.exists:
                if not self._human_tap_element(element):
                    element.click()
                self.logger.info(f"Contacts access dialog: {label}")
                emit_step("tap", action=f"contacts_access_{label}")
                self._human_like_delay('navigation')
                return label

        self.logger.warning("Contacts access dialog visible but its buttons were not found")
        return 'other_dialog'

    def scroll_discover_suggestions(self) -> bool:
        """Scroll one screen down in the suggestions list (humanized)."""
        try:
            self.device.human_scroll("down", distance_ratio=0.55)
            self._human_like_delay('scroll')
            return True
        except Exception as exc:
            self.logger.debug(f"Suggestions scroll failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # Follow
    # ------------------------------------------------------------------

    def _record_suggestion_follow(self, label: str, social_context: str,
                                  section: str) -> None:
        """Record a suggestion follow exactly as the interaction engine does.

        Same sequence as ``_do_follow``: the live counter moves ON THE GESTURE, then the
        DB write, then the session counter that carries the follow cap, then telemetry
        d'etape et event IPC.
        """
        self._count_live('follows')
        provenance = f"Suggestion Instagram ({section})" if section else "Suggestion Instagram"
        if social_context:
            provenance = f"{provenance} - {social_context}"
        self._record_action(label, 'FOLLOW', 1, content=provenance)
        try:
            session = getattr(self, 'session_manager', None)
            if session:
                session.record_action('follow_user', success=True, source=label)
        except Exception as exc:
            self.logger.debug(f"Follow session counter increment failed: {exc}")
        emit_step("follow", action="suggestion_row", target=label)
        IPCEmitter.emit_follow(label, success=True)

    @staticmethod
    def _row_key(row: Dict[str, Any]) -> str:
        """Dedup key for a row across two dumps.

        The label is enough in almost every case; when it is empty the row falls back on
        its vertical band, which stays stable as long as
        n'a pas scrolle.
        """
        label = (row.get("label") or "").strip()
        if label:
            return label.lower()
        bounds = row.get("row_bounds")
        return f"row@{bounds[1] // 50}" if bounds else "row@?"

    def _follow_verified(self, root, row: Dict[str, Any]) -> bool:
        """Did the row button flip after the tap?

        Success when the row now shows a following or requested state, or when it has
        disappeared — a followed suggestion is sometimes removed from the list. Failure
        when it is still offered.
        """
        key = self._row_key(row)
        for candidate in self.scan_discover_suggestions(root):
            if self._row_key(candidate) != key:
                continue
            state = candidate.get("state")
            if state in ('following', 'requested'):
                return True
            if state == 'follow':
                return False
            return True
        return True

    def follow_discover_suggestions(self, max_follows: int = 20,
                                    delay_range: tuple = (4, 12),
                                    max_scrolls: int = 15) -> Dict[str, Any]:
        """Bulk follow from the already-open people discovery screen.

        A single dump per follow serves both as the verification of the previous tap and
        as the source for the next one. The loop stops on the requested cap, on the
        session limit, or when the list offers no new followable row after several
        scrolls.
        """
        result = {
            'follows': 0, 'attempts': 0, 'scrolls': 0,
            'skipped_follow_back': 0, 'stop_reason': 'max_reached',
        }
        if max_follows <= 0:
            result['stop_reason'] = 'disabled'
            return result

        low, high = (delay_range if delay_range and len(delay_range) == 2 else (4, 12))
        attempted = set()
        self._reported_unreadable = False
        # Follow-back rows are counted by IDENTITY, not per screen: the same row stays
        # visible across several successive dumps and a plain sum would count it
        # autant de fois qu'on la voit.
        seen_follow_back = set()
        empty_dump_streak = 0
        max_attempts = max(max_follows * 3, max_follows + 5)
        root = self._suggestions_dump_root()

        while result['follows'] < max_follows and result['attempts'] < max_attempts:
            if not self._suggestions_session_allows():
                result['stop_reason'] = 'session_limit'
                break

            rows = self.scan_discover_suggestions(root)
            seen_follow_back.update(self._row_key(row) for row in rows
                                    if row.get('state') == 'follow_back')
            result['skipped_follow_back'] = len(seen_follow_back)
            candidates = [row for row in followable_rows(rows)
                          if self._row_key(row) not in attempted]

            # A row whose button we cannot READ is skipped in silence, and a screenful of them
            # looks exactly like a screenful of legitimate 'Follow back' — the run comes back with
            # zero follows and no reason why. That is how a missing locale label (Instagram FR
            # says "S'abonner", our catalogue only had "Suivre") stayed invisible. Say it once.
            unreadable = [row for row in rows if row.get('state') is None]
            if unreadable and not self._reported_unreadable:
                self._reported_unreadable = True
                samples = ', '.join(repr(row.get('state_label', '')) for row in unreadable[:3])
                self.logger.warning(
                    f"{len(unreadable)} suggestion row(s) with an unreadable button state "
                    f"(locale gap?): {samples}"
                )

            if not candidates:
                # A list can stack whole screens of non-followable rows before the
                # next section, so finding no candidate does NOT prove the end. Only
                # a run of dumps with NO row at all does; the rest is bounded by the
                # scroll cap.
                empty_dump_streak = empty_dump_streak + 1 if not rows else 0
                if empty_dump_streak >= self._SUGGESTIONS_EMPTY_SCROLL_RUNS:
                    result['stop_reason'] = 'list_exhausted'
                    break
                if result['scrolls'] >= max_scrolls:
                    result['stop_reason'] = 'max_scrolls'
                    break
                if not self.scroll_discover_suggestions():
                    result['stop_reason'] = 'scroll_failed'
                    break
                result['scrolls'] += 1
                root = self._suggestions_dump_root()
                continue

            empty_dump_streak = 0
            row = candidates[0]
            attempted.add(self._row_key(row))
            result['attempts'] += 1

            label = row.get('label') or '(sans libelle)'
            if not self.device.human_tap(row['follow_bounds']):
                self.logger.debug(f"Follow tap failed for '{label}'")
                continue

            # Human pace BETWEEN two follows: this is the most watched gesture,
            # and it is never chained at machine speed.
            time.sleep(random.uniform(min(low, high), max(low, high)))

            root = self._suggestions_dump_root()
            if self._follow_verified(root, row):
                result['follows'] += 1
                self._record_suggestion_follow(
                    label, row.get('social_context', ''), row.get('section', '')
                )
                self.logger.info(f"Followed suggestion '{label}' "
                                 f"({result['follows']}/{max_follows})")
            else:
                self.logger.debug(f"Follow did not register for '{label}'")

        return result

    def _suggestions_session_allows(self) -> bool:
        """Does the session still allow ONE follow?

        Two distinct guards, and both are needed:

        - ``should_continue()`` carries the duration, the session caps and the daily
          action budget;
        - the daily follow sub-quota is deliberately NOT a session-stop reason: it
          disables its own intent for the rest of the day through
          ``exhausted_daily_quotas()``. The interaction engine reads it to remove the
          follow from each per-profile plan — a path this mode never walks, since it
          visits no profile. Without reading it here, a suggestions pass would spend a
          ramping account's daily follow budget without ever seeing it.

        Fail-open like the rest of the guard: a read error must not kill the run.
        """
        session = getattr(self, 'session_manager', None)
        if not session:
            return True

        if hasattr(session, 'should_continue'):
            try:
                should_continue, reason = session.should_continue()
                if not should_continue:
                    self.logger.info(f"Suggestions follow stopped by session: {reason}")
                    return False
            except Exception as exc:
                self.logger.debug(f"Session limit check failed: {exc}")

        if hasattr(session, 'exhausted_daily_quotas'):
            try:
                if 'follow' in (session.exhausted_daily_quotas() or set()):
                    self.logger.info("Suggestions follow stopped: daily follow quota spent")
                    return False
            except Exception as exc:
                self.logger.debug(f"Daily quota read failed: {exc}")

        return True

    # ------------------------------------------------------------------
    # Orchestration complete
    # ------------------------------------------------------------------

    def run_feed_suggestions_pass(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Full pass: feed carousel -> discovery screen -> follows -> back to the feed.

        Does nothing, and says so, when the carousel is not on screen: the caller — the
        feed loop — decides when to retry.
        """
        result = {
            'entered': False, 'follows': 0, 'attempts': 0, 'scrolls': 0,
            'skipped_follow_back': 0, 'contacts_dialog': 'absent',
            'stop_reason': 'carousel_absent', 'returned_to_feed': False,
        }

        carousel = self.detect_feed_suggestions_carousel()
        if not carousel.get('present'):
            return result

        if not self.open_suggestions_see_all():
            result['stop_reason'] = 'cta_tap_failed'
            return result

        result['contacts_dialog'] = self.handle_contacts_access_dialog(
            config.get('suggestions_contacts_choice', 'deny')
        )
        if result['contacts_dialog'] == 'other_dialog':
            # Another Instagram alert (restriction, update): not handled here,
            # and certainly not followed by a follow.
            result['stop_reason'] = 'blocked_by_dialog'
            self._return_to_feed()
            result['returned_to_feed'] = True
            return result

        if not self._wait_for_discover_screen():
            result['stop_reason'] = 'discover_screen_not_reached'
            self._return_to_feed()
            result['returned_to_feed'] = True
            return result

        result['entered'] = True
        title = read_screen_title(self._suggestions_dump_root())
        self.logger.info(f"On suggestions screen '{title or 'Discover people'}' - mass follow")

        follow_result = self.follow_discover_suggestions(
            max_follows=int(config.get('max_suggestion_follows', 20) or 0),
            delay_range=config.get('suggestion_follow_delay_range', (4, 12)),
            max_scrolls=int(config.get('max_suggestion_scrolls', 15) or 0),
        )
        result.update({k: follow_result[k] for k in
                       ('follows', 'attempts', 'scrolls', 'skipped_follow_back', 'stop_reason')})

        result['returned_to_feed'] = self._return_to_feed()
        return result

    def find_feed_suggestions_carousel(self, max_scrolls: int = 12) -> Dict[str, Any]:
        """Scroll the feed until the suggestions carousel appears.

        Deliberately a plain humanized scroll rather than the crawl's "advance to the
        next real post": that one skips over non-organic blocks by design, so it would
        skip the very carousel being looked for. Nothing is read or liked here.
        """
        result = {'found': False, 'scrolls': 0}
        if self.has_feed_suggestions_carousel():
            result['found'] = True
            return result

        for _ in range(max(int(max_scrolls), 0)):
            try:
                self.device.human_scroll("down", distance_ratio=0.7)
            except Exception as exc:
                self.logger.debug(f"Feed scroll failed while looking for suggestions: {exc}")
                break
            self._human_like_delay('scroll')
            result['scrolls'] += 1
            if self.has_feed_suggestions_carousel():
                result['found'] = True
                break

        if not result['found']:
            self.logger.info(f"No suggestions carousel after {result['scrolls']} scroll(s)")
        return result

    def run_suggestions_only(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Suggestions-only run: find the carousel, follow, stop.

        No interaction with the feed itself — no like, no comment, no story. This is the
        mode to use when the only goal is to collect accounts from the
        suggestions; the feed is then only a corridor to the carousel.
        """
        result = {'follows': 0, 'passes': 0, 'carousel_scrolls': 0,
                  'skipped_follow_back': 0, 'stop_reason': 'carousel_not_found',
                  'returned_to_feed': True}
        passes_left = max(int(config.get('max_suggestion_passes', 1) or 0), 0)
        max_scrolls = int(config.get('max_carousel_scrolls', 12) or 0)

        while passes_left > 0:
            search = self.find_feed_suggestions_carousel(max_scrolls)
            result['carousel_scrolls'] += search['scrolls']
            if not search['found']:
                break

            pass_result = self.run_feed_suggestions_pass(config)
            result['passes'] += 1
            passes_left -= 1
            result['follows'] += pass_result.get('follows', 0)
            result['skipped_follow_back'] += pass_result.get('skipped_follow_back', 0)
            # The stop reason stays the one from the FOLLOW loop. Do not overwrite
            # it with a navigation problem: a perfectly successful run would then
            # read as a failure.
            result['stop_reason'] = pass_result.get('stop_reason', 'unknown')
            result['returned_to_feed'] = bool(pass_result.get('returned_to_feed'))

            if not pass_result.get('entered') or not result['returned_to_feed']:
                break

        return result

    def _wait_for_discover_screen(self, timeout: float = 8.0) -> bool:
        """Wait for the people discovery screen (conditional wait, never a fixed sleep)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_on_discover_people_screen():
                return True
            time.sleep(0.5)
        self.logger.warning("Discover people screen never appeared")
        return False

    def _return_to_feed(self) -> bool:
        """Come back to the feed after the suggestions pass.

        Taps the action-bar ARROW, not the hardware back key: the discovery screen
        d'onglets, et il n'a repondu ni a notre `press('back')` ni aux backs
        exposes no navigation bar, so the incremental backs of `navigate_to_home()`
        had nothing to hold on to and the run ended stuck on the list. The arrow is a
        real element: targeted by resource-id, so language-neutral, and tapped on its
        live bounds.
        """
        from taktik.core.social_media.instagram.ui.selectors import NAVIGATION_SELECTORS

        for _ in range(3):
            if not self.is_on_discover_people_screen():
                break
            if not self._tap_first_present(NAVIGATION_SELECTORS.back_buttons):
                # No arrow left on screen: the back key becomes the best remaining try.
                try:
                    self.device.press('back')
                except Exception as exc:
                    self.logger.debug(f"Back key failed: {exc}")
                    break
            self._human_like_delay('navigation')

        if self.is_on_discover_people_screen():
            self.logger.warning("Still on the suggestions screen after the back attempts")
            return False

        try:
            return bool(self.nav_actions.navigate_to_home())
        except Exception as exc:
            self.logger.debug(f"Return to feed failed: {exc}")
            return False

    def _tap_first_present(self, selectors) -> bool:
        """Tap the first element present among ``selectors`` (humanized tap)."""
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if not element.exists:
                    continue
                if not self._human_tap_element(element):
                    element.click()
                return True
            except Exception as exc:
                self.logger.debug(f"Tap on {selector} failed: {exc}")
        return False
