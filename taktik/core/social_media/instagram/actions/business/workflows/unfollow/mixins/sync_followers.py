"""Sync Followers mixin: our followers list, read into the base, from its top.

Strategy:
- Navigate to own profile → open Followers list
- Read the rows from the top, extracting usernames; upsert each into the follow graph, as a
  follower, cross-referenced with the known followings (mutuals / fans)
- Stop early when the base already knows our followers: the list shows the newest follower first,
  so after a run of followers the base knows, and when the base plus the new ones match the tab's
  count, the rest is what the base holds (`list_proof.PROOF_BY_BASE_COUNT`)
- Otherwise read the whole list; its end proves who follows us, and the followers the base held
  that it did not show are marked gone
- Mode 'enriched': visit each profile for full info (reuses scraping logic), whole list

This complements SyncFollowingMixin which handles the following list.
"""

import time
import random
from typing import Dict, Any, Set

from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
from taktik.core.clone import get_active_package
from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS
from taktik.core.shared.behavior.tap import tap_element_human
from ..list_proof import (
    KNOWN_IN_A_ROW_TO_STOP, PROOF_BY_BASE_COUNT, READ_TO_THE_END, base_matches_count, describe_proof,
    proof_of_read, scrolls_for,
)
from .actions import LeftOutRows, UnfollowActionsMixin, row_belongs_to_tab
from .sync_events import emit_sync_progress, emit_sync_user_discovered


class SyncFollowersMixin(UnfollowActionsMixin):
    """Mixin: read our followers list into the base, from its top."""

    # Followers the base knows, in a row, after which a read may stop (see list_proof).
    known_in_a_row_to_stop = KNOWN_IN_A_ROW_TO_STOP

    # ─── Public entry point ────────────────────────────────────────────────────

    def sync_followers_list(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Read our followers list into the base, and say what the read proves.

        1. Navigate to own profile → open Followers list
        2. Read the rows from the top (+ display names), upsert each into the follow graph, as a
           follower, cross-referenced with the known followings for mutual detection
        3. Stop after `known_in_a_row_to_stop` followers the base knows, in a row, when the base
           plus the new ones match the tab's count (`list_proof.base_matches_count`): proof
           `base_count`, the base holds the rest. Only where the list shows the newest follower
           first (no sort control on the tab: Instagram 410), in fast mode. Otherwise, or when the
           base does not match the count, read the whole list: proof `count` or
           `suggestions_end`, and the followers the base held that it did not show are marked gone.

        Args:
            config: Configuration dict with optional keys:
                - mode: 'fast' or 'enriched' (default: 'fast')
                - max_scrolls: max scroll attempts (default: from the tab's count)

        Returns:
            Dict with new_count, updated_count, total_seen, expected, proof, complete, usernames
            (with `complete`, EVERY follower: absence means "does not follow us"), incremental,
            known_before, known_after, departures, departures_withheld, scrolls, read_seconds,
            success
        """
        config = config or {}
        mode = config.get('mode', 'fast')

        stats = {
            'new_count': 0,
            'updated_count': 0,
            'total_seen': 0,
            # True when `usernames` holds every follower (unfollow/list_proof.py): the read reached
            # the list's exact count, or stopped at the followers the base knows with the base
            # matching the count. The unfollow trusts the ABSENCE of an account only then.
            'complete': False,
            # The rule that proved it (list_proof.PROOF_BY_*), None when none did
            'proof': None,
            'expected': None,
            'end_reached': False,
            'usernames': set(),
            # The read stopped at the followers the base knows (proof `base_count`)
            'incremental': False,
            'known_before': 0,
            # With proof `base_count`: the followers the base knows, plus the new ones seen
            'known_after': None,
            'departures': 0,
            'departures_withheld': 0,
            'scrolls': 0,
            'read_seconds': 0.0,
            'success': False,
        }

        try:
            account_id = self._get_account_id()
            if not account_id:
                self.logger.warning("sync_followers_list: no account_id, skipping")
                return stats

            self.logger.info(f"🔄 Starting followers sync (mode={mode})")

            # Navigate to own profile
            if not self.nav_actions.navigate_to_profile_tab():
                self.logger.error("sync_followers_list: failed to navigate to profile tab")
                return stats
            time.sleep(2)

            # Open Followers list
            if not self.nav_actions.open_followers_list():
                self.logger.error("sync_followers_list: failed to open followers list")
                return stats
            time.sleep(3)
            if not self._ensure_followers_tab():
                return stats
            expected = self._list_tab_count('followers')
            stats['expected'] = expected
            # 100 scrolls read about 450 accounts: a bigger list could never end (review of
            # 2026-09-24). The bound follows the count when the tab gives it.
            max_scrolls = config.get('max_scrolls') or scrolls_for(expected, 100)
            scroll_failed = False

            if not self._wait_for_list_rows():
                self.logger.error("sync_followers_list: followers list elements never appeared")
                return stats
            self.logger.debug("✅ Followers list elements loaded")
            started = time.monotonic()

            # Get known following usernames for mutual detection
            known_followings = InstagramFollowGraphService.get_active_following_usernames(account_id)
            self.logger.info(f"📋 {len(known_followings)} known followings for mutual detection")
            # The followers the base knows: the last complete read, and the new ones seen since
            known_followers = InstagramFollowGraphService.get_follower_usernames(account_id)
            stats['known_before'] = len(known_followers)
            may_stop_early = self._followers_read_may_stop_early(mode, known_followers, expected)
            known_in_a_row = 0
            stop_signal = False

            # For enriched mode, create a ProfileExtraction instance
            profile_extractor = None
            if mode == 'enriched':
                from ....management.profile.extraction import ProfileExtraction
                profile_extractor = ProfileExtraction(self.device, getattr(self, 'session_manager', None))

            d = self.device.device
            active_package = get_active_package()
            username_resource_id = UNFOLLOW_SELECTORS.active_follow_list_username_resource_id(active_package)

            seen_on_screen: Set[str] = set()
            left_out = LeftOutRows()
            emit_sync_progress('followers', stats)
            scroll_attempts = 0
            no_new_count = 0

            while scroll_attempts < max_scrolls:
                if self._sync_should_stop():
                    stats['stopped_by_session'] = True
                    break
                # One read of the screen outside enriched mode: usernames, display names and the
                # state of each row's button together. The per-element reads cost three device
                # calls per row, and a sync of 1 928 followings took an hour (2026-09-24).
                if mode == 'enriched':
                    username_elements = d(resourceId=username_resource_id)
                    if not username_elements.exists:
                        break
                    rows = self._visible_follow_rows()
                    entries = self._live_follow_entries(username_elements)
                else:
                    rows = self._visible_follow_rows(with_display_names=True)
                    if not rows and not d(resourceId=username_resource_id).exists:
                        break
                    entries = [(i, row['username'], row['name_element']) for i, row in enumerate(rows)]
                # Every row but those whose button contradicts the tab (a plain "Follow"). A blank
                # button keeps its row: deep in a long list Instagram leaves most of them blank (see
                # ROW_STATES_NOT_IN_TAB); the suggestions under the list are left out by position.
                left_out.unpaired |= self.unpaired_on_screen
                row_states = {row['username'].lower(): row['state'] for row in rows}
                display_names = {row['username'].lower(): row.get('display_name', '') for row in rows}

                new_found = False
                for i, username, el in entries:
                    if username in seen_on_screen:
                        continue
                    if not row_belongs_to_tab(row_states.get(username.lower()), 'followers'):
                        left_out.refuse(username, row_states.get(username.lower()))
                        continue
                    seen_on_screen.add(username)
                    stats['total_seen'] += 1
                    new_found = True

                    # The display name, paired to its row by position (see sync_following)
                    display_name = display_names.get(username.lower(), '')
                    if mode == 'enriched' and not display_name:
                        display_name = self._live_display_name(d, active_package, i)

                    # Determine if we follow this person back
                    is_following_back = username.lower() in known_followings

                    # Record it in the follow graph, on the follower side
                    result = InstagramFollowGraphService.upsert_follower(
                        username=username,
                        account_id=account_id,
                        display_name=display_name,
                        is_following_back=is_following_back,
                        source='full_sync',
                    )
                    if result == 'new':
                        stats['new_count'] += 1
                    elif result == 'updated':
                        stats['updated_count'] += 1

                    # Emit per-username IPC
                    emit_sync_user_discovered("followers", username, display_name, result == 'new')

                    # A follower the base knows extends the run of known ones; a new one (or one
                    # back after leaving us) ends it.
                    known_in_a_row = known_in_a_row + 1 if username.lower() in known_followers else 0
                    if may_stop_early and known_in_a_row >= self.known_in_a_row_to_stop:
                        known_after = len(known_followers | {name.lower() for name in seen_on_screen})
                        if base_matches_count(known_after, expected):
                            stats['proof'] = PROOF_BY_BASE_COUNT
                            stats['incremental'] = True
                            stats['known_after'] = known_after
                            stop_signal = True
                            self.logger.info(
                                f"⏹ {known_in_a_row} known followers in a row after "
                                f"{stats['new_count']} new one(s): the base plus the new ones "
                                f"({known_after}) match the count ({expected}), stopping"
                            )
                            break
                        self.logger.info(
                            f"The base plus the new followers ({known_after}) do not match the "
                            f"count ({expected}): reading the whole list"
                        )
                        may_stop_early = False

                    # ── Enrichissement inline (comme likers_scraping) ──
                    if mode == 'enriched' and profile_extractor:
                        try:
                            self.logger.debug(f"🔍 Enriching @{username}...")
                            if not tap_element_human(self.device, el, logger=self.logger):
                                el.click()
                            time.sleep(random.uniform(1.5, 2.5))

                            info = profile_extractor.get_complete_profile_info(
                                username=username,
                                navigate_if_needed=False,
                                enrich=True,
                            )

                            # The extraction saves the profile and emits its `profile_captured`.
                            if info:
                                self.logger.debug(
                                    f"✅ Enriched @{username}: "
                                    f"{info.get('followers_count', '?')} followers"
                                )

                            # Back to the list
                            d.press('back')
                            time.sleep(random.uniform(1.0, 1.5))

                            # After a back the UI elements are invalidated: read them again
                            break

                        except Exception as e:
                            self.logger.debug(f"Error enriching @{username}: {e}")
                            try:
                                d.press('back')
                                time.sleep(1)
                            except Exception:
                                pass
                            break  # Re-read the UI elements
                        continue

                if new_found:
                    emit_sync_progress('followers', stats)
                if stop_signal:
                    break

                # The end of the list: the suggestions under it, or several reads in a row without
                # a new name; it counts only if the names read reach the tab's exact count.
                no_new_count = 0 if new_found else no_new_count + 1
                max_no_new = 3 if mode != 'enriched' else 5
                if self.suggestions_on_screen or no_new_count >= max_no_new:
                    stats['end_reached'] = True
                    stats['proof'] = proof_of_read(
                        len(seen_on_screen), expected, scroll_failed,
                        suggestions_reached=self.suggestions_on_screen,
                        left_out=left_out.summary(seen_on_screen))
                    self.logger.info(
                        f"End of the followers list"
                        f"{' (suggestions under it)' if self.suggestions_on_screen else f' ({max_no_new} reads without a new name)'}: "
                        f"{describe_proof(stats['proof'], len(seen_on_screen), expected)}"
                    )
                    break
                if no_new_count:
                    # A screen without a new name: the next page may still be loading
                    time.sleep(random.uniform(1.0, 2.0))

                # Scroll only outside enriched mode, or when nothing unseen is left
                if mode != 'enriched':
                    if self._scroll_followers_list() is False:
                        scroll_failed = True
                    time.sleep(random.uniform(0.5, 0.9))  # released still; the next read is ONE dump
                    scroll_attempts += 1
                else:
                    remaining = d(resourceId=username_resource_id)
                    has_unseen = False
                    if remaining.exists:
                        for j in range(remaining.count):
                            try:
                                u = (remaining[j].get_text() or '').strip().lstrip('@')
                                if u and u not in seen_on_screen:
                                    has_unseen = True
                                    break
                            except Exception:
                                continue
                    if not has_unseen:
                        if self._scroll_followers_list() is False:
                            scroll_failed = True
                        time.sleep(1.2)
                        scroll_attempts += 1

            stats['scrolls'] = scroll_attempts
            stats['read_seconds'] = round(time.monotonic() - started, 1)
            # Every follower when a rule proved it: the whole list read, or the base's followers
            # plus the new ones the read saw above them.
            stats['complete'] = stats['proof'] is not None
            if stats['proof'] == PROOF_BY_BASE_COUNT:
                stats['usernames'] = known_followers | {name.lower() for name in seen_on_screen}
            else:
                stats['usernames'] = set(seen_on_screen)
            if stats['proof'] in READ_TO_THE_END and stats['total_seen'] > 0:
                stats['departures'] = self._record_departures(
                    'followers', account_id, known_followers, seen_on_screen | left_out.unpaired, stats)
            if stats['complete']:
                stats['reciprocity_written'] = InstagramFollowGraphService.set_followings_reciprocity(
                    account_id, stats['usernames'])
            # What the read saw and did not count: a read short of the tab's count says why
            stats['left_out'] = left_out.summary(seen_on_screen)
            if stats['left_out']:
                self.logger.info(f"Followers names seen but not read: {stats['left_out']}")
            self._close_list_read('followers', stats, len(seen_on_screen))

        except Exception as e:
            self.logger.error(f"Error in sync_followers_list: {e}")

        return stats

    # ─── Internal helpers ──────────────────────────────────────────────────────

    def _followers_read_may_stop_early(self, mode: str, known: Set[str], expected) -> bool:
        """May this read stop at the followers the base knows? Only in fast mode, when the base
        knows followers and the tab gives an exact count to check it against, and when the list
        shows the newest follower first: a tab with a sort control is not in follow order."""
        if mode == 'enriched' or not known:
            return False
        if expected is None:
            self.logger.info("Followers tab without an exact count: reading the whole list")
            return False
        if self._list_shows_sort_control():
            self.logger.info("The followers tab shows a sort control, its order is not the follow date: "
                             "reading the whole list")
            return False
        return True

    def _scroll_followers_list(self) -> bool:
        """Scroll the followers list down (humanized controlled scroll). False when it failed."""
        try:
            return self._drag_follow_list()
        except Exception as e:
            self.logger.debug(f"Error scrolling followers list: {e}")
            return False
