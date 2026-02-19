"""Sync Followers mixin — full followers list scraping.

Strategy:
- Navigate to own profile → open Followers list
- Scroll through the entire list, extracting usernames
- Mode 'fast': only usernames (bulk insert)
- Mode 'enriched': visit each profile for full info (reuses scraping logic)
- Upsert each follower into followers_sync table
- Cross-reference with following_sync to determine mutuals/fans

This complements SyncFollowingMixin which handles the following list.
"""

import json
import time
from typing import Dict, Any, List, Set

from ....common.database_helpers import DatabaseHelpers


class SyncFollowersMixin:
    """Mixin: scrape the full followers list and sync to DB."""

    # ─── Public entry point ────────────────────────────────────────────────────

    def sync_followers_list(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Full scrape of the followers list.

        1. Navigate to own profile → open Followers list
        2. Scroll + extract usernames (+ display names)
        3. Upsert each into followers_sync
        4. Cross-reference with following_sync for mutual detection

        Args:
            config: Configuration dict with optional keys:
                - mode: 'fast' or 'enriched' (default: 'fast')
                - max_scrolls: max scroll attempts (default: 100)

        Returns:
            Dict with new_count, updated_count, total_seen, success
        """
        config = config or {}
        mode = config.get('mode', 'fast')
        max_scrolls = config.get('max_scrolls', 100)

        stats = {
            'new_count': 0,
            'updated_count': 0,
            'total_seen': 0,
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
            time.sleep(2)

            # Get known following usernames for mutual detection
            known_followings = DatabaseHelpers.get_following_sync_usernames(account_id)
            self.logger.info(f"📋 {len(known_followings)} known followings for mutual detection")

            # For enriched mode, create a ProfileExtraction instance
            profile_extractor = None
            if mode == 'enriched':
                from ....management.profile.extraction import ProfileExtraction
                profile_extractor = ProfileExtraction(self.device, getattr(self, 'session_manager', None))

            seen_on_screen: Set[str] = set()
            enriched_queue: list = []  # usernames to enrich after each scroll batch
            scroll_attempts = 0
            no_new_count = 0  # consecutive scrolls with no new usernames

            while scroll_attempts < max_scrolls:
                visible = self._get_visible_follower_usernames_with_display()

                new_found = False
                for username, display_name in visible:
                    if username in seen_on_screen:
                        continue
                    seen_on_screen.add(username)
                    stats['total_seen'] += 1
                    new_found = True

                    # Determine if we follow this person back
                    is_following_back = username.lower() in known_followings

                    # Upsert into followers_sync
                    result = DatabaseHelpers.sync_follower_upsert(
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

                    # Emit per-username IPC for real-time activity
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

                    # Queue for enrichment if in enriched mode (tous les comptes, même connus)
                    if mode == 'enriched':
                        enriched_queue.append(username)

                # Emit progress IPC every scroll
                if stats['total_seen'] > 0 and stats['total_seen'] % 10 == 0:
                    self._emit_sync_progress('followers', stats)

                # ── Enriched mode: visit queued profiles ──
                if mode == 'enriched' and enriched_queue and profile_extractor:
                    self._enrich_followers_batch(
                        enriched_queue, profile_extractor, stats
                    )
                    enriched_queue.clear()

                if not new_found:
                    no_new_count += 1
                    # En mode enrichi : on parcourt toute la liste (pas de tri possible sur followers)
                    # On s'arrête seulement quand il n'y a vraiment plus rien de nouveau à l'écran
                    max_no_new = 3 if mode != 'enriched' else 5
                    if no_new_count >= max_no_new:
                        self.logger.info(f"No new followers after {max_no_new} consecutive scrolls — end of list")
                        break
                else:
                    no_new_count = 0

                # Scroll
                self._scroll_followers_list()
                time.sleep(1.2)
                scroll_attempts += 1

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
            username_resource_id = 'com.instagram.android:id/follow_list_username'
            subtitle_resource_id = 'com.instagram.android:id/follow_list_subtitle'

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

    def _scroll_followers_list(self):
        """Scroll the followers list down."""
        try:
            d = self.device.device
            screen_width = d.info.get('displayWidth', 576)
            screen_height = d.info.get('displayHeight', 1280)

            start_y = int(screen_height * 0.7)
            end_y = int(screen_height * 0.3)
            x = screen_width // 2

            d.swipe(x, start_y, x, end_y, duration=0.3)
        except Exception as e:
            self.logger.debug(f"Error scrolling followers list: {e}")

    def _enrich_followers_batch(self, usernames: list, profile_extractor, stats: Dict[str, Any]):
        """
        Visit each follower's profile to extract full info (enriched mode).

        For each username:
        1. Click on the username element in the followers list
        2. Wait for profile to load
        3. Extract full profile info (photo, bio, stats)
        4. Press back to return to the followers list
        """
        import random

        d = self.device.device
        username_resource_id = 'com.instagram.android:id/follow_list_username'

        for username in usernames:
            try:
                # Find and click the username element in the list
                username_el = d(resourceId=username_resource_id, text=username)
                if not username_el.exists:
                    # Try partial match (Instagram sometimes trims)
                    username_el = d(resourceId=username_resource_id, textContains=username[:10])

                if not username_el.exists:
                    self.logger.debug(f"⚠️ Could not find @{username} in list for enrichment, skipping")
                    continue

                self.logger.debug(f"🔍 Enriching @{username}...")
                username_el.click()
                time.sleep(random.uniform(1.5, 2.5))

                # Extract full profile info (already on profile screen)
                profile_info = profile_extractor.get_complete_profile_info(
                    username=None,  # Already navigated
                    navigate_if_needed=False,
                    enrich=False,  # Basic extraction is enough (photo + stats)
                )

                if profile_info:
                    self.logger.debug(
                        f"✅ Enriched @{username}: "
                        f"{profile_info.get('followers_count', '?')} followers, "
                        f"pic={'yes' if profile_info.get('profile_pic_base64') else 'no'}"
                    )
                    # Emit enriched IPC event
                    try:
                        print(json.dumps({
                            "type": "sync_user_enriched",
                            "list_type": "followers",
                            "username": username,
                            "followers_count": profile_info.get('followers_count', 0),
                            "following_count": profile_info.get('following_count', 0),
                            "posts_count": profile_info.get('posts_count', 0),
                            "is_private": profile_info.get('is_private', False),
                        }), flush=True)
                    except Exception:
                        pass
                else:
                    self.logger.debug(f"⚠️ Failed to extract profile for @{username}")

                # Go back to followers list
                d.press('back')
                time.sleep(random.uniform(1.0, 1.5))

            except Exception as e:
                self.logger.debug(f"Error enriching @{username}: {e}")
                # Try to recover by pressing back
                try:
                    d.press('back')
                    time.sleep(1)
                except Exception:
                    pass

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
