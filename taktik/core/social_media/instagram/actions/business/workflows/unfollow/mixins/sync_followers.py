"""Sync Followers mixin — full followers list scraping.

Strategy:
- Navigate to own profile → open Followers list
- Scroll through the entire list, extracting usernames
- Mode 'fast': only usernames (bulk insert)
- Mode 'enriched': visit each profile for full info (reuses scraping logic)
- Upsert each follower into the unified follow graph
- Cross-reference with the known followings to determine mutuals/fans

This complements SyncFollowingMixin which handles the following list.
"""

import json
import time
import random
from typing import Dict, Any, List, Set

from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw
from taktik.core.clone import get_active_package
from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS
from taktik.core.shared.behavior.tap import tap_element_human
from ..list_proof import read_is_complete, scrolls_for
from .actions import FOLLOW_LIST_SCROLL_RATIO

# Row states of a real follower: the button offers to follow back, says we follow, or that we
# asked to. A plain "Follow" row is a suggestion under the list, not a follower.
FOLLOWER_ROW_STATES = frozenset({'following', 'follow_back', 'requested'})


class SyncFollowersMixin:
    """Mixin: scrape the full followers list and sync to DB."""

    # ─── Public entry point ────────────────────────────────────────────────────

    def sync_followers_list(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Full scrape of the followers list.

        1. Navigate to own profile → open Followers list
        2. Scroll + extract usernames (+ display names)
        3. Upsert each into the follow graph, as a follower
        4. Cross-reference with the known followings for mutual detection

        Args:
            config: Configuration dict with optional keys:
                - mode: 'fast' or 'enriched' (default: 'fast')
                - max_scrolls: max scroll attempts (default: 100)

        Returns:
            Dict with new_count, updated_count, total_seen, success
        """
        config = config or {}
        mode = config.get('mode', 'fast')

        stats = {
            'new_count': 0,
            'updated_count': 0,
            'total_seen': 0,
            # True only when the read reached the list's exact count (unfollow/list_proof.py): the
            # unfollow trusts the ABSENCE of an account from this list only then (candidates.py).
            'complete': False,
            'expected': None,
            'end_reached': False,
            'usernames': set(),
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

            # Wait for the list items to be actually loaded
            d = self.device.device
            active_package = get_active_package()
            username_resource_id = UNFOLLOW_SELECTORS.active_follow_list_username_resource_id(active_package)
            wait_attempts = 0
            while wait_attempts < 10:
                if d(resourceId=username_resource_id).exists:
                    self.logger.debug("✅ Followers list elements loaded")
                    break
                self.logger.debug(f"⏳ Waiting for followers list to load... ({wait_attempts + 1}/10)")
                time.sleep(1)
                wait_attempts += 1
            else:
                self.logger.error("sync_followers_list: followers list elements never appeared")
                return stats

            # Get known following usernames for mutual detection
            known_followings = InstagramFollowGraphService.get_active_following_usernames(account_id)
            self.logger.info(f"📋 {len(known_followings)} known followings for mutual detection")

            # For enriched mode, create a ProfileExtraction instance
            profile_extractor = None
            if mode == 'enriched':
                from ....management.profile.extraction import ProfileExtraction
                profile_extractor = ProfileExtraction(self.device, getattr(self, 'session_manager', None))

            d = self.device.device
            active_package = get_active_package()
            username_resource_id = UNFOLLOW_SELECTORS.active_follow_list_username_resource_id(active_package)

            seen_on_screen: Set[str] = set()
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
                # The state of each row's button: a suggestion row ("Follow") is not a follower,
                # and a row whose button cannot be read yet is read again after the next scroll.
                row_states = {row['username'].lower(): row['state'] for row in rows}
                display_names = {row['username'].lower(): row.get('display_name', '') for row in rows}

                new_found = False
                for i, username, el in entries:
                    if username in seen_on_screen:
                        continue
                    if row_states.get(username.lower()) not in FOLLOWER_ROW_STATES:
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
                    try:
                        print(json.dumps({
                            "type": "sync_user_discovered",
                            "list_type": "followers",
                            "username": username,
                            "display_name": display_name,
                            "is_new": result == 'new',
                        }), flush=True)
                    except Exception:
                        pass

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

                            if info:
                                self.logger.debug(
                                    f"✅ Enriched @{username}: "
                                    f"{info.get('followers_count', '?')} followers"
                                )
                                try:
                                    print(json.dumps({
                                        "type": "sync_user_enriched",
                                        "list_type": "followers",
                                        "username": username,
                                        "followers_count": info.get('followers_count', 0),
                                        "following_count": info.get('following_count', 0),
                                        "posts_count": info.get('posts_count', 0),
                                        "is_private": info.get('is_private', False),
                                    }), flush=True)
                                except Exception:
                                    pass

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

                # Emit progress IPC
                if stats['total_seen'] > 0 and stats['total_seen'] % 10 == 0:
                    self._emit_sync_progress('followers', stats)

                if not new_found:
                    no_new_count += 1
                    max_no_new = 3 if mode != 'enriched' else 5
                    if no_new_count >= max_no_new:
                        stats['end_reached'] = True
                        stats['complete'] = read_is_complete(len(seen_on_screen), expected, scroll_failed)
                        self.logger.info(
                            f"No new followers after {max_no_new} consecutive scrolls: "
                            f"{len(seen_on_screen)} read of {expected if expected is not None else '?'} "
                            f"({'complete' if stats['complete'] else 'NOT proven complete'})"
                        )
                        break
                else:
                    no_new_count = 0

                # Scroll only outside enriched mode, or when nothing unseen is left
                if mode != 'enriched':
                    if self._scroll_followers_list() is False:
                        scroll_failed = True
                    time.sleep(random.uniform(0.6, 1.1))  # the list settles; the next read is a dump
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

            stats['usernames'] = set(seen_on_screen)
            if stats['complete']:
                stats['reciprocity_written'] = InstagramFollowGraphService.set_followings_reciprocity(
                    account_id, seen_on_screen)
            stats['success'] = True
            self.logger.info(
                f"✅ Followers sync complete: {stats['new_count']} new, "
                f"{stats['updated_count']} updated, {stats['total_seen']} seen"
            )

        except Exception as e:
            self.logger.error(f"Error in sync_followers_list: {e}")

        return stats

    # ─── Internal helpers ──────────────────────────────────────────────────────

    def _get_visible_follower_usernames_with_display(self) -> List[tuple]:
        """
        Extract (username, display_name) tuples from the visible followers list.

        Returns:
            List of (username, display_name) tuples
        """
        results = []
        try:
            d = self.device.device
            active_package = get_active_package()
            username_resource_id = UNFOLLOW_SELECTORS.active_follow_list_username_resource_id(active_package)
            subtitle_resource_id = UNFOLLOW_SELECTORS.active_follow_list_subtitle_resource_id(active_package)

            username_elements = d(resourceId=username_resource_id)
            subtitle_elements = d(resourceId=subtitle_resource_id)

            if not username_elements.exists:
                return results

            count = username_elements.count
            for i in range(count):
                try:
                    username = username_elements[i].get_text() or ''
                    username = username.strip().lstrip('@')
                    if not username or not self._is_valid_username(username):
                        continue

                    display_name = ''
                    try:
                        if subtitle_elements.exists and i < subtitle_elements.count:
                            display_name = subtitle_elements[i].get_text() or ''
                    except Exception:
                        pass

                    results.append((username, display_name))
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting visible follower accounts: {e}")

        return results

    def _scroll_followers_list(self) -> bool:
        """Scroll the followers list down (humanized controlled scroll). False when it failed."""
        try:
            return human_scroll_raw(self.device.device, "down", distance_ratio=FOLLOW_LIST_SCROLL_RATIO) is not False
        except Exception as e:
            self.logger.debug(f"Error scrolling followers list: {e}")
            return False

    def _emit_sync_progress(self, list_type: str, stats: Dict[str, Any]):
        """Emit IPC progress message for the frontend."""
        try:
            msg = {
                "type": "sync_progress",
                "list_type": list_type,
                "new_count": stats['new_count'],
                "updated_count": stats['updated_count'],
                "total_seen": stats['total_seen'],
            }
            print(json.dumps(msg), flush=True)
        except Exception:
            pass
