"""Sync the operated account's own Following / Followers lists into the follow graph.

Prerequisite of the relationship model: interacting differently with someone who already follows
you, someone you follow, and a stranger means first knowing which of those they are. TikTok had
no such record at all -- `social_graph_sync` held 122 Instagram rows and zero TikTok ones.

Two things measured on device (2026-08-29) shape the whole design.

**The rows carry the relationship.** Each row has a button whose text IS the state: « Suivis »
(we follow them), « Ami(e)s » (mutual), « Suivre » (we do not), « Suivre en retour » (they follow
us and we do not). So one pass over a list yields both directions for the rows it names -- no
profile visit needed to learn reciprocity.

**The FOLLOWING list hides half the handles.** On the operated account, 39 rows showed 39 display
names and only 19 handles; the same field is present on every row of the FOLLOWERS list. It is
not lazy loading -- the count sat at 5 of 9 for fourteen seconds on a still screen. A display
name is not an identity (it is not unique and it changes), so those rows cannot be written.

They are therefore COUNTED, as `unidentified`, and reported. A sync that wrote what it could and
said nothing would look complete while half the list went unrecorded, which is worse than not
running it. `resolve_missing_handles` opens those profiles to read the handle properly; it is off
by default because it costs one visit per row.
"""

import random
import time
from typing import Any, Dict, List, Optional, Set

from taktik.core.database.tiktok_follow_graph import TikTokFollowGraphService
from taktik.core.social_media.tiktok.services.followers.stop_policy import normalize_username
from taktik.core.social_media.tiktok.services.profile.username import (
    UNKNOWN_USERNAME,
    get_current_profile_username,
)
from taktik.core.social_media.tiktok.ui.labels import is_following_button, is_friends_button

from .._internal import BaseTikTokWorkflow
from .models import SyncListsConfig, SyncListsStats
from .....ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from .....ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS

FOLLOWING = "following"
FOLLOWERS = "followers"


class SyncListsWorkflow(BaseTikTokWorkflow):
    """Read the operated account's own follow lists and record them."""

    MODULE_NAME = "tiktok-sync-lists-workflow"

    def __init__(self, device, config: SyncListsConfig):
        super().__init__(device, module_name=self.MODULE_NAME)
        self.config = config
        self.stats = SyncListsStats()
        self.selectors = FOLLOWERS_SELECTORS

        self._account_id: Optional[int] = None
        self._graph = TikTokFollowGraphService
        self._on_row_callback = None

    def set_on_row_callback(self, callback) -> None:
        """Called with each recorded row, for live reporting."""
        self._on_row_callback = callback

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, bot_username: str = None) -> SyncListsStats:
        self._running = True
        self.stats = SyncListsStats()

        if not self._resolve_account(bot_username):
            self.stats.completion_reason = "no_account"
            self.logger.error("❌ No account to sync for — nothing recorded")
            return self.stats

        wanted = self._lists_to_sync()
        self.logger.info(f"🔄 Syncing {' + '.join(wanted)} for @{bot_username}")

        try:
            for list_type in wanted:
                if not self._running:
                    self.stats.completion_reason = "stopped_by_user"
                    break
                if not self._sync_one_list(list_type):
                    self.stats.errors += 1
                    self.stats.completion_reason = "list_unreachable"

            if not self.stats.completion_reason:
                self.stats.completion_reason = "completed"

            self.logger.info(
                f"✅ Sync done: {self.stats.rows_seen} rows, {self.stats.new_count} new, "
                f"{self.stats.updated_count} updated, {self.stats.unidentified} unidentified"
            )
            if self.stats.unidentified:
                self.logger.warning(
                    f"⚠️ {self.stats.unidentified} row(s) had no handle on screen and were NOT "
                    f"recorded. Enable resolve_missing_handles to open those profiles."
                )
        except Exception as e:
            self.logger.error(f"❌ Error during sync: {e}")
            self.stats.errors += 1
            self.stats.completion_reason = "error"

        return self.stats

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _lists_to_sync(self) -> List[str]:
        if self.config.list_type == "both":
            return [FOLLOWING, FOLLOWERS]
        return [FOLLOWING if self.config.list_type == FOLLOWING else FOLLOWERS]

    def _resolve_account(self, bot_username: Optional[str]) -> bool:
        if not bot_username:
            return False
        try:
            from taktik.core.database.local.service import get_local_database

            account_id, _ = get_local_database().get_or_create_tiktok_account(bot_username)
            self._account_id = account_id
            return bool(account_id)
        except Exception as e:
            self.logger.error(f"Could not resolve the acting account: {e}")
            return False

    def _sync_one_list(self, list_type: str) -> bool:
        """Open one list and walk it."""
        if not self._open_list(list_type):
            self.logger.error(f"❌ Could not open the {list_type} list")
            return False

        known = (self._graph.get_active_following_usernames(self._account_id)
                 if list_type == FOLLOWING
                 else self._graph.get_follower_usernames(self._account_id))
        self.logger.info(f"📋 {len(known)} {list_type} already known in the database")

        seen: Set[str] = set()
        unnamed_rows: List[Dict[str, Any]] = []
        scrolls = 0
        idle_screens = 0
        reached_end = False

        while scrolls < self.config.max_scrolls and self._running:
            rows = self._read_visible_rows()
            fresh = 0

            for row in rows:
                handle = row.get("username") or ""
                key = normalize_username(handle)

                if not key:
                    # A row the list showed but did not name.
                    marker = row.get("display_name") or ""
                    if marker and marker not in [r.get("display_name") for r in unnamed_rows]:
                        unnamed_rows.append(row)
                        fresh += 1
                    continue

                if key in seen:
                    continue
                seen.add(key)
                fresh += 1
                self.stats.rows_seen += 1

                if self.config.incremental and key in known:
                    self.logger.info(
                        f"⏹ Met a known handle (@{handle}) — stopping this list "
                        f"({self.stats.new_count} new)"
                    )
                    self.stats.stopped_early = True
                    self.stats.completion_reason = "known_reached"
                    self._record(list_type, row)
                    self.stats.unidentified += len(unnamed_rows)
                    return True

                self._record(list_type, row)

            if fresh == 0:
                idle_screens += 1
                if idle_screens >= 2:
                    self.logger.info(f"🏁 End of the {list_type} list ({len(seen)} named rows)")
                    reached_end = True
                    break
            else:
                idle_screens = 0

            self.scroll.scroll_search_results(direction="down")
            self._human_delay()
            scrolls += 1

        if reached_end:
            self.stats.completion_reason = "list_exhausted"
        else:
            # Bounded, not finished — and said so. A run that stops at its scroll cap and
            # reports "completed" reads as a full sync of a list it only saw the top of.
            self.stats.completion_reason = "max_scrolls_reached"
            self.stats.stopped_early = True
            self.logger.warning(
                f"⚠️ Stopped at the {self.config.max_scrolls}-scroll cap with {len(seen)} row(s) "
                f"read — the rest of the {list_type} list was NOT seen"
            )

        self.stats.unidentified += len(unnamed_rows)
        if unnamed_rows and self.config.resolve_missing_handles:
            self._resolve_unnamed(list_type, unnamed_rows, seen)
        return True

    def _return_to_shell(self) -> None:
        """Back out until the bottom bar is there again.

        A follow list is a full-screen page with NO bottom navigation, so asking to go to the
        own profile from inside it taps nothing — which is how the resolution pass reported
        "could not reopen the list" after successfully walking that very list.
        """
        for _ in range(5):
            if self.detection._element_exists(NAVIGATION_SELECTORS.profile_tab, timeout=1):
                return
            self.device.press("back")
            time.sleep(1.2)

    def _open_list(self, list_type: str) -> bool:
        """From the operated account's own profile, open one of its two lists."""
        from taktik.core.social_media.tiktok.actions.business.actions.profile_actions import (
            ProfileActions,
        )

        self._return_to_shell()
        profile = ProfileActions(self.device)
        if not profile.navigate_to_own_profile():
            return False
        time.sleep(1.5)

        openers = (self.selectors.following_list_opener if list_type == FOLLOWING
                   else self.selectors.followers_counter)
        if not self.click._find_and_click(openers, timeout=5):
            return False
        time.sleep(2.0)
        return True

    def _read_visible_rows(self) -> List[Dict[str, Any]]:
        """Read the rows on screen: display name, handle when shown, relationship.

        Fields are paired by vertical position rather than by index: the handle is missing on
        some rows, so pairing two lists by index would attach one person's handle to the next
        person's name as soon as a row is skipped.
        """
        names = self._nodes_with_y(self.selectors.follower_display_name)
        handles = self._nodes_with_y(self.selectors.follower_username)
        buttons = self._nodes_with_y(self.selectors.follower_any_button)

        rows: List[Dict[str, Any]] = []
        for y, display_name in names:
            handle = next((text for hy, text in handles if 0 < hy - y < 110), "")
            state = next((text for by, text in buttons if abs(by - y) < 130), "")
            rows.append({
                "display_name": display_name,
                "username": handle,
                "relationship": state,
            })
        return rows

    def _nodes_with_y(self, selectors) -> List[tuple]:
        """(top, text) for every node one of `selectors` resolves, ignoring the empty ones."""
        found: List[tuple] = []
        for selector in selectors:
            try:
                elements = self.device.xpath(selector).all()
            except Exception:
                continue
            for element in elements:
                text = (getattr(element, "text", "") or "").strip()
                if not text:
                    continue
                try:
                    top = element.bounds[1]
                except Exception:
                    continue
                found.append((top, text))
            if found:
                break
        return sorted(found)

    def _record(self, list_type: str, row: Dict[str, Any]) -> None:
        """Write one row, in the direction of the list it came from."""
        handle = row.get("username") or ""
        display_name = row.get("display_name") or ""
        state = row.get("relationship") or ""
        mutual = is_friends_button(state)
        follows_them = mutual or is_following_button(state)

        if mutual:
            self.stats.reciprocal_seen += 1

        if list_type == FOLLOWING:
            self.stats.following_seen += 1
            result = self._graph.upsert_following(
                username=handle,
                display_name=display_name,
                account_id=self._account_id,
                is_reciprocal=mutual if state else None,
            )
        else:
            self.stats.followers_seen += 1
            result = self._graph.upsert_follower(
                username=handle,
                account_id=self._account_id,
                display_name=display_name,
                is_following_back=follows_them if state else None,
            )

        if result == "new":
            self.stats.new_count += 1
        elif result == "updated":
            self.stats.updated_count += 1
        else:
            self.stats.errors += 1

        if self._on_row_callback:
            try:
                self._on_row_callback({
                    "list_type": list_type,
                    "username": handle,
                    "display_name": display_name,
                    "relationship": state,
                    "is_new": result == "new",
                })
            except Exception as e:
                self.logger.debug(f"Row callback error: {e}")

    def _resolve_unnamed(self, list_type: str, rows: List[Dict[str, Any]], seen: Set[str]) -> None:
        """Open the profile of rows the list did not name, to read the handle there.

        ONE descent through the list, resolving whatever is on screen before scrolling — not one
        re-navigation per row. Re-opening the list each time would land back at the top, so only
        the rows of the first screen would ever be reachable and every deeper one would look
        unresolvable.

        Each resolution is verified: the handle comes from the profile screen itself, so a tap
        that lands somewhere else records nothing.
        """
        pending = {row.get("display_name"): row for row in rows if row.get("display_name")}
        self.logger.info(f"🔍 Resolving {len(pending)} unnamed row(s) by opening their profiles")

        if not self._open_list(list_type):
            self.logger.warning("Could not reopen the list to resolve the unnamed rows")
            return

        scrolls = 0
        while pending and scrolls < self.config.max_scrolls and self._running:
            if self.stats.resolved >= self.config.max_resolutions:
                self.logger.warning(
                    f"⚠️ Resolution cap reached ({self.config.max_resolutions}) — "
                    f"{len(pending)} row(s) left unidentified"
                )
                break

            on_screen = [row.get("display_name") for row in self._read_visible_rows()]
            progressed = False

            for display_name in on_screen:
                if display_name not in pending:
                    continue
                if self.stats.resolved >= self.config.max_resolutions:
                    break
                row = pending.pop(display_name)
                progressed = True
                if not self._tap_row_by_display_name(display_name):
                    continue

                time.sleep(1.5)
                handle = get_current_profile_username(self.device)
                if handle and handle != UNKNOWN_USERNAME:
                    key = normalize_username(handle)
                    if key and key not in seen:
                        seen.add(key)
                        row["username"] = handle
                        self.stats.rows_seen += 1
                        self._record(list_type, row)
                        self.stats.resolved += 1
                        self.stats.unidentified -= 1
                else:
                    self.logger.debug(f"Could not read a handle for «{display_name}»")

                self._go_back_to_list()
                self._human_delay()

            if not progressed:
                self.scroll.scroll_search_results(direction="down")
                self._human_delay()
            scrolls += 1

    def _go_back_to_list(self) -> None:
        """Return from a resolved profile to the list, without leaving the app."""
        for _ in range(3):
            self.device.press("back")
            time.sleep(1.0)
            if self._nodes_with_y(self.selectors.follower_display_name):
                return

    def _tap_row_by_display_name(self, display_name: str) -> bool:
        """Tap the row whose display name is exactly this one."""
        if not display_name:
            return False
        try:
            return bool(self.click._find_and_click(
                self.selectors.row_selectors_for_display_name(display_name), timeout=3
            ))
        except Exception as e:
            self.logger.debug(f"Could not tap row «{display_name}»: {e}")
        return False

    def _human_delay(self) -> None:
        time.sleep(random.uniform(self.config.min_delay, self.config.max_delay))


__all__ = ["SyncListsWorkflow", "SyncListsConfig", "SyncListsStats", "FOLLOWING", "FOLLOWERS"]
