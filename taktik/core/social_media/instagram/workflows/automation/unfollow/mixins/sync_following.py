"""Sync Following mixin — incremental following list sync + non-follower detection.

Strategy:
- Following list: sort by "Date followed: Latest", scroll until we hit a known username → STOP
- Non-followers: click the native "People you don't follow back" category in the Followers tab
  → gives us the list directly without visiting each profile

This avoids:
- Full follower list rescroll (no sort available on followers)
- Visiting each profile to check follow-back status
"""

import time
import random
from typing import Dict, Any, List, Set

from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
from taktik.core.clone import get_active_package
from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.social_media.instagram.workflows.automation.unfollow.list_proof import (
    PROOF_BY_KNOWN_ACCOUNT, describe_proof, incremental_stop_allowed, proof_of_read, scrolls_for,
)
from taktik.core.social_media.instagram.workflows.automation.unfollow.mixins.actions import LeftOutRows, UnfollowActionsMixin, row_belongs_to_tab
from taktik.core.social_media.instagram.workflows.automation.unfollow.mixins.sync_events import emit_sync_progress, emit_sync_user_discovered


class FansCategoryUnreadable(Exception):
    """The fans category is open and its rows could not be read: a failed read, never « 0 fans »."""


class SyncFollowingMixin(UnfollowActionsMixin):
    """Mixin: sync the following list incrementally and detect non-followers via native category."""

    # ─── Public entry points ──────────────────────────────────────────────────

    def sync_following_list(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Incremental sync of the following list.

        1. Ouvrir Following → trier "Date followed: Latest"
        2. scroll and extract the usernames
        3. for each username:
           - Si déjà en BDD (vu récemment) → STOP
           - otherwise, upsert into the sync table

        Args:
            config: Configuration (optionnel)

        Returns:
            Dict with new_count, total_count, stopped_early
        """
        config = config or {}
        mode = config.get('mode', 'fast')
        stats = {
            'new_count': 0,
            'updated_count': 0,
            'total_seen': 0,
            'stopped_early': False,
            # True only when the read reached the list's exact count, without an early stop
            # (workflows/automation/unfollow/list_proof.py): only then can an account missing from it be taken as
            # unfollowed elsewhere.
            'complete': False,
            # The rule that proved it (list_proof.PROOF_BY_*), None when none did
            'proof': None,
            'expected': None,
            'end_reached': False,
            'departures': 0,
            'departures_withheld': 0,
            'success': False,
        }

        try:
            account_id = self._get_account_id()
            if not account_id:
                self.logger.warning("sync_following_list: no account_id, skipping sync")
                return stats

            self.logger.info("🔄 Starting incremental following sync")

            # Navigate to our own profile
            if not self.nav_actions.navigate_to_profile_tab():
                self.logger.error("sync_following_list: failed to navigate to profile tab")
                return stats
            time.sleep(2)

            # Open the following list
            if not self.nav_actions.open_following_list():
                self.logger.error("sync_following_list: failed to open following list")
                return stats
            time.sleep(1.5)
            if not self._ensure_following_tab():
                return stats
            expected = self._list_tab_count('following')
            stats['expected'] = expected

            # Sort by most recently followed so the new ones come first. The early stop on the
            # first known account is only valid in that order: in the default order a known
            # account can sit on the first row, and the sync used to stop there (1 row read out of
            # 1 949 on a French phone, 2026-09-10, where no French sort option was known).
            sorted_by_latest = self._set_following_list_sort('latest')
            if not sorted_by_latest:
                self.logger.warning(
                    "sync_following_list: 'latest' sort not applied — reading the whole list "
                    "instead of stopping at the first known account"
                )
            time.sleep(1.5)

            # Read the already-known usernames to find the stop point
            known_usernames = InstagramFollowGraphService.get_active_following_usernames(account_id)
            self.logger.info(f"📋 {len(known_usernames)} known followings in DB")
            # The first known account is a stop point only when the list is sorted by follow date
            # AND the base knows at least half of the tab's count (list_proof).
            stop_at_first_known = sorted_by_latest and incremental_stop_allowed(len(known_usernames), expected)
            if sorted_by_latest and not stop_at_first_known:
                self.logger.info(
                    f"sync_following_list: the base knows {len(known_usernames)} of {expected} "
                    f"followings — reading the whole list instead of stopping at the first known account"
                )
            stats['incremental'] = stop_at_first_known
            # The bot's follows, read once: one query per row used to follow every read
            bot_follows = InstagramFollowGraphService.bot_followed_usernames(account_id)

            # For enriched mode, create a ProfileExtraction instance
            profile_extractor = None
            if mode == 'enriched':
                from taktik.core.social_media.instagram.services.profile.extraction import ProfileExtraction
                profile_extractor = ProfileExtraction(self.device, getattr(self, 'session_manager', None))

            d = self.device.device
            active_package = get_active_package()
            username_resource_id = UNFOLLOW_SELECTORS.active_follow_list_username_resource_id(active_package)

            seen_on_screen: Set[str] = set()
            left_out = LeftOutRows()
            emit_sync_progress('following', stats)
            scroll_attempts = 0
            # A fixed 60 scrolls read about 270 accounts: the bound follows the tab's count.
            max_scrolls = scrolls_for(expected, 60)
            stop_signal = False
            scroll_failed = False
            quiet_rounds = 0
            end_rounds = getattr(self, 'end_of_list_scrolls', 3)

            while scroll_attempts < max_scrolls and not stop_signal:
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
                # Every row but those whose button says we do not follow them. A blank button keeps
                # its row: deep in a long list Instagram leaves most of them blank (see
                # ROW_STATES_NOT_IN_TAB); the suggestions under the list are left out by position.
                left_out.unpaired |= self.unpaired_on_screen
                row_states = {row['username'].lower(): row['state'] for row in rows}
                display_names = {row['username'].lower(): row.get('display_name', '') for row in rows}

                new_found = False
                for i, username, el in entries:
                    if username in seen_on_screen:
                        continue
                    if not row_belongs_to_tab(row_states.get(username.lower()), 'following'):
                        left_out.refuse(username, row_states.get(username.lower()))
                        continue
                    seen_on_screen.add(username)
                    stats['total_seen'] += 1
                    new_found = True

                    # The display name, paired to its row by position (it used to be taken by
                    # index, and one row without a subtitle shifted every name after it)
                    display_name = display_names.get(username.lower(), '')
                    if mode == 'enriched' and not display_name:
                        display_name = self._live_display_name(d, active_package, i)

                    # Si on rencontre un username déjà connu
                    if username in known_usernames:
                        # Fast mode stops at the first known account, but only when the list is
                        # sorted by follow date: otherwise that account says nothing about the rest
                        if mode != 'enriched' and stop_at_first_known:
                            emit_sync_user_discovered("following", username, display_name, False)
                            self.logger.info(
                                f"⏹ Found known username @{username} — stopping sync "
                                f"({stats['new_count']} new accounts added)"
                            )
                            stop_signal = True
                            stats['stopped_early'] = True
                            stats['proof'] = PROOF_BY_KNOWN_ACCOUNT
                            break
                        self.logger.debug(f"Known @{username} — processing anyway (enriched mode)")

                    # Following → upsert en BDD
                    is_bot_follow = username.lower() in bot_follows
                    result = InstagramFollowGraphService.upsert_following(
                        username=username,
                        display_name=display_name,
                        account_id=account_id,
                        followed_by_bot=is_bot_follow,
                    )
                    if result == 'new':
                        stats['new_count'] += 1
                        self.logger.debug(f"➕ New following: @{username}")
                    else:
                        stats['updated_count'] += 1

                    # Emit per-username IPC
                    emit_sync_user_discovered("following", username, display_name, result == 'new')

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
                        # Do not carry on with the loop after enrichment
                        continue

                if new_found:
                    emit_sync_progress('following', stats)
                if stop_signal:
                    break

                # The end of the list is the suggestions under it, or several reads in a row
                # without a new name (one used to be enough: a slow page looked like the end); it
                # counts only if the names read reach the tab's exact count.
                quiet_rounds = 0 if new_found else quiet_rounds + 1
                if self.suggestions_on_screen or quiet_rounds >= end_rounds:
                    stats['end_reached'] = True
                    stats['proof'] = proof_of_read(
                        len(seen_on_screen), expected, scroll_failed,
                        suggestions_reached=self.suggestions_on_screen,
                        left_out=left_out.summary(seen_on_screen))
                    stats['complete'] = stats['proof'] is not None
                    self.logger.info(
                        f"End of the following list"
                        f"{' (suggestions under it)' if self.suggestions_on_screen else ''}: "
                        f"{describe_proof(stats['proof'], len(seen_on_screen), expected)}"
                    )
                    break
                if quiet_rounds:
                    # A screen without a new name: the next page may still be loading
                    time.sleep(random.uniform(1.0, 2.0))

                # Scroll only outside enriched mode, which re-scans first
                if mode != 'enriched':
                    if self._scroll_following_list() is False:
                        scroll_failed = True
                    time.sleep(random.uniform(0.5, 0.9))  # released still; the next read is ONE dump
                    scroll_attempts += 1
                else:
                    # En mode enrichi, on a break après chaque profil enrichi
                    # Any unseen item left on the current screen?
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
                        if self._scroll_following_list() is False:
                            scroll_failed = True
                        time.sleep(1.5)
                        scroll_attempts += 1

            if stats['complete'] and stats['total_seen'] > 0:
                stats['departures'] = self._record_departures(
                    'following', account_id, known_usernames, seen_on_screen | left_out.unpaired, stats)

            # What the read saw and did not count: a read short of the tab's count says why
            stats['left_out'] = left_out.summary(seen_on_screen)
            if stats['left_out']:
                self.logger.info(f"Following names seen but not read: {stats['left_out']}")
            self._close_list_read('following', stats, len(seen_on_screen))

        except Exception as e:
            self.logger.error(f"Error in sync_following_list: {e}")

        return stats

    def scrape_non_followers_category(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Scrape the native "people who do not follow you back" category of the followers view.

        Instagram serves that filtered list directly, so there is no need to visit
        each profile to check the reciprocity.

        1. navigate to the followers view
        2. tap the dedicated category
        3. scroll and extract every username
        4. mark those usernames as non-reciprocal
        5. the followings ABSENT from that list are reciprocal, with no visit

        Args:
            config: Configuration (optionnel)

        Returns:
            Dict with non_followers_count, mutuals_count, success. The counts stay None until the
            category is read: a category not read (not served, not found, unreadable: `read_failed`)
            has no count, never 0.
        """
        config = config or {}
        stats = {
            'fans_count': None,
            # Legacy keys the desktop reads: `non_followers_count` has always been the size of
            # this category, i.e. the fans; `mutuals_count` was a deduction that no longer exists.
            'non_followers_count': None,
            'mutuals_count': 0,
            'success': False,
        }

        try:
            account_id = self._get_account_id()
            if not account_id:
                self.logger.warning("scrape_non_followers_category: no account_id")
                return stats

            self.logger.info("🔍 Scraping 'People you don't follow back' category")

            # Are we already in the unified view?
            d = self.device.device
            active_package = get_active_package()
            unified_layout = d.xpath(
                UNFOLLOW_SELECTORS.unified_follow_list_tab_layout_selector(active_package)
            )

            if unified_layout.exists:
                # Unified view open: tap the followers tab
                self.logger.debug("Already in unified follow list view, switching to Followers tab")
                followers_tab = next(
                    (tab for tab in (d.xpath(selector) for selector
                                     in UNFOLLOW_SELECTORS.unified_followers_tab_selectors(active_package))
                     if tab.exists),
                    None,
                )
                if followers_tab is not None:
                    if not tap_element_human(self.device, followers_tab, logger=self.logger):
                        followers_tab.click()
                else:
                    self.logger.error("scrape_non_followers_category: Followers tab not found in unified view")
                    return stats
            else:
                # Not in the unified view: navigate from the profile
                self.logger.debug("Not in unified view, navigating from profile")
                if not self.nav_actions.navigate_to_profile_tab():
                    self.logger.error("scrape_non_followers_category: failed to navigate to profile")
                    return stats
                time.sleep(1)
                if not self.nav_actions.open_followers_list():
                    self.logger.error("scrape_non_followers_category: failed to open followers list")
                    return stats
            time.sleep(1.5)

            # Tap the non-reciprocal category
            if not self._click_non_followers_category():
                if self._fans_category_not_served():
                    stats['category_not_served'] = True
                    self.logger.info(
                        "scrape_non_followers_category: our followers list opens on its accounts, "
                        "Instagram serves it no category now: no fans to read"
                    )
                else:
                    self.logger.warning(
                        "scrape_non_followers_category: fans category not found, and the list does "
                        "not open on its accounts (a category label no locale knows, or another screen)"
                    )
                return stats

            # Wait for the non-reciprocal view to load (its follow-back button visible)
            follow_back_visible = False
            for wait in range(5):
                time.sleep(1)
                if self._has_follow_back_row():
                    follow_back_visible = True
                    self.logger.debug(f"Non-followers view loaded after {wait + 1}s")
                    break
            if not follow_back_visible:
                self.logger.warning("scrape_non_followers_category: non-followers view did not load (no 'Follow back' buttons)")
                return stats

            # Extract every non-reciprocal account
            try:
                non_follower_usernames = self._extract_all_non_followers()
            except FansCategoryUnreadable as exc:
                stats['read_failed'] = True
                self.logger.error(
                    f"scrape_non_followers_category: the fans category could not be read ({exc}): "
                    "no count, nothing recorded"
                )
                return stats
            stats['non_followers_count'] = len(non_follower_usernames)  # the fans, see above

            self.logger.info(f"📋 Found {len(non_follower_usernames)} non-followers")

            # These are FANS: they follow us and we do not follow them. That is all the category
            # says. Until 2026-09-24 this block also wrote each fan as a FOLLOWING marked
            # "does not follow back" (a following row for an account we do not follow), and marked
            # every stored following absent from the category as a mutual: absent from the fans says
            # nothing about whether an account WE follow follows us. Reciprocity now comes from the
            # full followers sync of the run and the "Follows you" badge read on the profile.
            for username in non_follower_usernames:
                InstagramFollowGraphService.upsert_follower(
                    username=username,
                    account_id=account_id,
                    is_following_back=False,
                    source='fans_category',
                )
            stats['fans_count'] = len(non_follower_usernames)
            stats['success'] = True
            self.logger.info(
                f"✅ Fans category read: {stats['fans_count']} followers you do not follow back "
                f"(no reciprocity deduced for your followings)"
            )

            # Close the view to come back to a clean state
            self.logger.debug("Closing non-followers view (back press)")
            self.device.device.press('back')
            time.sleep(1)

        except Exception as e:
            self.logger.error(f"Error in scrape_non_followers_category: {e}")

        return stats

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _click_non_followers_category(self) -> bool:
        """
        Tap the non-reciprocal category.

        From the dump, it is a button with:
        - content-desc="People you don't follow back"
        - resource-id="{pkg}:id/container"
        """
        try:
            d = self.device.device
            pkg = get_active_package()
            xpaths = UNFOLLOW_SELECTORS.fans_category_selectors(pkg)
            for i, xpath in enumerate(xpaths):
                el = d.xpath(xpath)
                if el.exists:
                    self.logger.debug(f"_click_non_followers_category: matched xpath #{i+1}: {xpath}")
                    if not tap_element_human(self.device, el, logger=self.logger):
                        el.click()
                    return True
            self.logger.debug("_click_non_followers_category: no xpath matched")
            return False

        except Exception as e:
            self.logger.debug(f"Error clicking non-followers category: {e}")
            return False

    def _fans_category_not_served(self) -> bool:
        """Is it proven that Instagram serves our followers list no category now (it does on some
        days only, to the same account)?

        Read on one dump: the followers tab is the one shown, when the list has tabs, and the list,
        at its top, opens on its accounts under its search box and its sort row. Anything else
        there (a category whose label no locale knows, a header, a list scrolled off its top)
        proves nothing. The list is taken for ours, as the category tap above takes it: opened
        from our profile, or found open.
        """
        d = self.device.device
        package = get_active_package()
        screen = d.dump_hierarchy()
        has_tabs = d.xpath(UNFOLLOW_SELECTORS.unified_follow_list_tab_layout_selector(package), screen).exists
        if has_tabs and not self._list_tab_selected(package, "followers", screen):
            return False
        return d.xpath(UNFOLLOW_SELECTORS.list_opens_on_accounts_selector(package), screen).exists

    def _extract_all_non_followers(self) -> List[str]:
        """
        Extract every username of the non-reciprocal list.

        The list has no ordering, so it is scrolled to the end.
        Each item carries a follow-back button, which confirms they do not follow us.

        The category's view was seen loaded (a row offering to follow back): a first screen without
        one fan read is a read that failed, never an empty category. Raises `FansCategoryUnreadable`
        then, and on any screen that could not be read: a list read in part is no list of the fans.

        Returns:
            Full list of the non-reciprocal usernames
        """
        usernames = []
        seen: Set[str] = set()
        scroll_attempts = 0
        max_scrolls = 30

        while scroll_attempts < max_scrolls:
            visible = self._get_visible_non_follower_usernames()
            if not usernames and not visible:
                raise FansCategoryUnreadable("the first screen of the open category gave no fan")

            new_found = False
            for username in visible:
                if username not in seen:
                    seen.add(username)
                    usernames.append(username)
                    new_found = True

            if not new_found:
                self.logger.debug("No new non-followers after scroll — end of list")
                break

            self._scroll_following_list()
            time.sleep(1.2)
            scroll_attempts += 1

        return usernames

    def _get_visible_non_follower_usernames(self) -> List[str]:
        """The fans on this screen of the open category: the names of its rows offering to follow
        back, read by the list's row reader (`_visible_follow_rows`, one dump, the one of the unfollow
        and the syncs). [] when no row offers it: the list ended above this screen.

        Raises `FansCategoryUnreadable` when the screen could not be read, or when rows offer to
        follow back and none of their names could be read: an unread screen is not an empty one.
        """
        rows = self._visible_follow_rows(require_username=False)
        if not self.rows_read:
            raise FansCategoryUnreadable("the rows of the list could not be read")
        offering = [row for row in rows if row['state'] == 'follow_back']
        names = [row['username'] for row in offering if row['username']]
        if offering and not names:
            raise FansCategoryUnreadable(f"{len(offering)} row(s) offer to follow back, no name read")
        return names

    def _has_follow_back_row(self) -> bool:
        """Does a row of the open list offer to follow back ("Follow back", "Suivre en retour")?

        Read through the shared state classifier, never a literal label.
        """
        return any(row['state'] == 'follow_back'
                   for row in self._visible_follow_rows(require_username=False))

    def _is_valid_username(self, username: str) -> bool:
        """Is this string a valid Instagram username?"""
        if not username or len(username) < 1 or len(username) > 30:
            return False
        # Exclude the texts that are not usernames
        excluded = {
            'search', 'categories', 'all followers', 'following', 'followers',
            'subscriptions', 'flagged', 'most shown in feed', 'sorted by',
            'date followed', 'default', 'sync contacts', 'find people you know',
            'sync', 'dismiss', 'follow back', 'following', 'new posts',
        }
        if username.lower() in excluded:
            return False
        # An Instagram username holds only letters, digits, dots and underscores
        import re
        return bool(re.match(r'^[a-zA-Z0-9._]+$', username))
