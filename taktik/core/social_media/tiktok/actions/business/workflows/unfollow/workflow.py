"""Unfollow Workflow for TikTok automation.

Navigates to the bot's profile, opens the Following list, and unfollows users one by one with
human-like delays.

Each row goes through the same three steps, which the Cartography Lab runs too
(`tt.unfollow.preview_rows`, `tt.unfollow.unfollow_one`):
1. the decision (`row_refusal`): mutual follows, a row without a handle, the minimum follow age,
   an unknown follow date;
2. the tap, then the proof (`unfollow_row`): the row must offer to follow again, read through the
   catalogue and the language layer; a confirmation sheet is tapped only if one shows up;
3. the record: a confirmed unfollow is written to the base, an unconfirmed tap is not counted.
"""

from typing import Optional, Callable, Dict, Any, List
from loguru import logger
import time
import random

from ....atomic.navigation.navigation_actions import NavigationActions
from ....atomic.scroll.scroll_actions import ScrollActions
from ....core.base_action import BaseAction
from ....core.utils import first_matching
from .....ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from .....ui.labels import is_friends_button
from .....services.followers.listing import (
    find_username_for_bounds,
    get_element_bounds,
    row_follow_state,
)
from .....services.followers.stop_policy import normalize_username
from taktik.core.database.tiktok_follow_graph import TikTokFollowGraphService
from taktik.core.shared.diagnostics import run_halt
from taktik.core.shared.diagnostics.action_block import look_for_action_block
from .models import (
    SKIP_FOLLOW_DATE_UNKNOWN,
    SKIP_FOLLOWED_TOO_RECENTLY,
    SKIP_FRIENDS,
    SKIP_HANDLE_UNKNOWN,
    STOP_ACTION_BLOCKED,
    STOP_UNFOLLOW_UNCONFIRMED,
    UnfollowConfig,
    UnfollowStats,
)

#: Pause between two reads of the tapped row while waiting for it to change.
_ROW_POLL_INTERVAL = 0.3


class UnfollowWorkflow:
    """Core unfollow logic — no IPC, no bridge dependencies."""

    def __init__(self, device, config: UnfollowConfig):
        self.device = device
        self.config = config
        self.stats = UnfollowStats()
        self.stopped = False
        self._account_id: Optional[int] = None
        self._account_resolved = False
        self._unconfirmed_in_a_row = 0
        #: Rows already kept, so a row still on screen is not counted again at the next pass.
        self._kept: set = set()

        # Action helpers
        self._nav = NavigationActions(device)
        self._scroll = ScrollActions(device)
        self._base = BaseAction(device)
        self._selectors = FOLLOWERS_SELECTORS

        # Callbacks (set by bridge)
        self._on_unfollow: Optional[Callable] = None
        self._on_skip: Optional[Callable] = None
        self._on_unconfirmed: Optional[Callable] = None
        self._on_stats: Optional[Callable] = None

    # ── public setters ──────────────────────────────────────────────

    def set_on_unfollow_callback(self, cb: Callable):
        self._on_unfollow = cb

    def set_on_skip_callback(self, cb: Callable):
        """`cb(username, reason)`: a row left alone, and why (friends, followed_too_recently...)."""
        self._on_skip = cb

    def set_on_unconfirmed_callback(self, cb: Callable):
        """`cb(username, state)`: a tap after which the row still did not offer to follow."""
        self._on_unconfirmed = cb

    def set_on_stats_callback(self, cb: Callable):
        self._on_stats = cb

    def stop(self):
        self.stopped = True

    # ── run ──────────────────────────────────────────────────────────

    def run(self) -> UnfollowStats:
        """Navigate to profile → Following list → unfollow loop.

        Returns the final stats.
        """
        # 1. Navigate to profile tab
        logger.info("👤 Navigating to profile...")
        if not self._nav.navigate_to_profile():
            raise RuntimeError("Failed to navigate to profile")
        time.sleep(2)

        # 2. Open Following list
        logger.info("📋 Opening following list...")
        if not self._base._find_and_click(self._selectors.following_list_opener, timeout=5):
            raise RuntimeError("Failed to open following list")
        time.sleep(2)

        if self.config.min_follow_age_days > 0 and not self._acting_account_id():
            logger.warning(
                "Minimum follow age set but the acting account is unknown: no follow can be "
                "dated, every account will be kept (follow_date_unknown)"
            )

        # 3. Unfollow loop
        scroll_attempts = 0

        while self._may_continue():
            buttons = self.visible_row_buttons()

            if not buttons:
                scroll_attempts += 1
                if scroll_attempts >= self.config.max_scroll_attempts:
                    logger.info("No more users to unfollow (no buttons found)")
                    break
                logger.info("No buttons found, scrolling...")
                self._scroll_list()
                continue

            unfollowed_this_round = self.process_rows(buttons)
            if self.stats.stop_reason:
                break

            if unfollowed_this_round == 0:
                scroll_attempts += 1
                if scroll_attempts >= self.config.max_scroll_attempts:
                    logger.info("No more users to unfollow (only kept rows remaining)")
                    break
                self._scroll_list()
            else:
                scroll_attempts = 0

        self._log_refusals()
        return self.stats

    # ── the three steps, shared with the Lab ────────────────────────

    def visible_row_buttons(self) -> List[Any]:
        """The "Following" / "Friends" buttons of the visible rows (catalogue, active language)."""
        return first_matching(self.device, self._selectors.following_or_friends_button)

    def process_rows(self, buttons: List[Any]) -> int:
        """Decide, tap and prove each visible row, in order. Returns how many were unfollowed."""
        unfollowed = 0
        for elem in buttons:
            if not self._may_continue():
                break
            try:
                username = self._resolve_username(elem)
                key = normalize_username(username) or f"@y{get_element_bounds(elem).get('top', 0)}"
                if key in self._kept:
                    continue
                refusal = self.row_refusal(getattr(elem, "text", "") or "", username)
                if refusal:
                    self._kept.add(key)
                    self._skip(username, refusal)
                    continue

                if self.unfollow_row(elem, username):
                    unfollowed += 1

                # Human-like delay after every tap, confirmed or not
                delay = random.uniform(self.config.min_delay, self.config.max_delay)
                time.sleep(delay)

            except Exception as e:
                self.stats.errors += 1
                logger.warning(f"Failed to unfollow: {e}")
                continue
        return unfollowed

    def row_refusal(self, button_text: str, username: Optional[str]) -> Optional[str]:
        """Why this row must be left alone, or None when it may be unfollowed. Reads no screen."""
        # Mutual follows ("Friends" / "Ami(e)s"), unless the run includes them. The label was
        # hardcoded English, so on a French phone the option silently did nothing.
        if is_friends_button(button_text) and not self.config.include_friends:
            return SKIP_FRIENDS
        # With no handle the account can be neither dated nor recorded: never unfollowed, age or not.
        handle = normalize_username(username)
        if not handle:
            return SKIP_HANDLE_UNKNOWN
        return self._follow_age_refusal(handle)

    def unfollow_row(self, elem: Any, username: Optional[str]) -> bool:
        """Tap one row's button and PROVE the unfollow. True only when the row confirmed it.

        The row is read again until it offers to follow (bounded wait), a confirmation sheet is
        tapped only if it appears, and only a confirmed unfollow is counted and written.
        """
        bounds = get_element_bounds(elem)
        # Humanized tap; centre-click fallback
        if not self._base._human_tap_bounds(elem):
            elem.click()

        state = self._wait_row_unfollowed(bounds)
        handle = f"@{username}" if username else "(row without a handle)"
        # The one look after a write: refused, nothing is counted and the run stops here.
        if look_for_action_block(self._block_detector(), after="unfollow", target=username or ""):
            self.stats.stop_reason = STOP_ACTION_BLOCKED
            self._emit_stats()
            return False
        if state == "follow":
            self._unconfirmed_in_a_row = 0
            self.stats.unfollowed += 1
            logger.info(f"✅ Unfollowed {handle} ({self.stats.unfollowed}/{self.config.max_unfollows})")
            self._record_unfollow(username)
            if self._on_unfollow:
                self._on_unfollow(username, self.stats.unfollowed)
            self._emit_stats()
            return True

        self.stats.unconfirmed += 1
        self._unconfirmed_in_a_row += 1
        logger.warning(f"⚠️ {handle}: the row still reads '{state}' after the tap — unfollow NOT counted")
        if self._on_unconfirmed:
            self._on_unconfirmed(username, state)
        if self._unconfirmed_in_a_row >= self.config.max_unconfirmed_in_a_row:
            self.stats.stop_reason = STOP_UNFOLLOW_UNCONFIRMED
            logger.error(
                f"🛑 {self._unconfirmed_in_a_row} unfollows in a row not confirmed by the screen — stopping"
            )
        self._emit_stats()
        return False

    # ── helpers ──────────────────────────────────────────────────────

    def _scroll_list(self) -> None:
        self._scroll.scroll_profile_videos(direction='down')
        # A row without a handle is only known by its place on screen, which the scroll changes.
        self._kept = {key for key in self._kept if not key.startswith("@y")}
        time.sleep(1)

    def _may_continue(self) -> bool:
        halt = run_halt.arret_demande()
        if halt and not self.stats.stop_reason:
            self.stats.stop_reason = halt.get("code") or STOP_ACTION_BLOCKED
        return (self.stats.unfollowed < self.config.max_unfollows
                and not self.stopped
                and not self.stats.stop_reason)

    def _block_detector(self):
        """The production block detector on this run's device, built once."""
        if getattr(self, "_detection", None) is None:
            from ....atomic.detection.detection_actions import DetectionActions

            self._detection = DetectionActions(self.device)
        return self._detection

    def _wait_row_unfollowed(self, row_bounds: Dict[str, int]) -> str:
        """The tapped row's state, read until it offers to follow or the wait runs out.

        A confirmation sheet is tapped once, and only if it is on screen: the following list
        shows none (measured on 46.6.3), a profile does. No fixed delay anywhere; the last state
        read is returned ('follow' on success; 'following', 'friends' or 'unknown' otherwise).
        """
        deadline = time.monotonic() + max(0.0, float(self.config.confirm_timeout))
        sheet_confirmed = False
        while True:
            state = row_follow_state(self.device, row_bounds, self._selectors)
            if state == "follow":
                return state
            if not sheet_confirmed and self._confirm_sheet_if_shown():
                sheet_confirmed = True
                continue
            if time.monotonic() >= deadline:
                return state
            time.sleep(_ROW_POLL_INTERVAL)

    def _confirm_sheet_if_shown(self) -> bool:
        """Tap the unfollow confirmation if a sheet shows one right now. Never waits for it."""
        found = first_matching(self.device, self._selectors.unfollow_confirm_button)
        if not found:
            return False
        if not self._base._human_tap_bounds(found[0]):
            found[0].click()
        logger.info("Unfollow confirmation sheet shown and confirmed")
        return True

    def _skip(self, username: Optional[str], reason: str) -> None:
        if reason == SKIP_FRIENDS:
            self.stats.skipped_friends += 1
        elif reason == SKIP_HANDLE_UNKNOWN:
            self.stats.skipped_handle_unknown += 1
        elif reason == SKIP_FOLLOWED_TOO_RECENTLY:
            self.stats.skipped_recent_follows += 1
        elif reason == SKIP_FOLLOW_DATE_UNKNOWN:
            self.stats.skipped_follow_date_unknown += 1
        self.stats.refusals[reason] = self.stats.refusals.get(reason, 0) + 1
        if self._on_skip:
            self._on_skip(username, reason)
        handle = f"@{username}" if username else "(row without a handle)"
        logger.info(f"⏭️ Kept {handle}: {reason}")
        self._emit_stats()

    def _follow_age_refusal(self, handle: str) -> Optional[str]:
        """The minimum follow age: `followed_too_recently`, `follow_date_unknown`, or None.

        In doubt, protect, as the Instagram unfollow does: an account whose follow nothing dates
        (no acting account, no FOLLOW by the bot and no sighting by a sync) is KEPT.
        """
        min_days = self.config.min_follow_age_days
        if min_days <= 0:
            return None
        account_id = self._acting_account_id()
        if not account_id:
            return SKIP_FOLLOW_DATE_UNKNOWN
        days = TikTokFollowGraphService.get_follow_age_days(handle, account_id)
        if days is None:
            return SKIP_FOLLOW_DATE_UNKNOWN
        return SKIP_FOLLOWED_TOO_RECENTLY if days < min_days else None

    def _record_unfollow(self, username: Optional[str]) -> None:
        """Write a CONFIRMED unfollow: the interaction, the day's total, the closed following row."""
        if not normalize_username(username):
            logger.warning("Confirmed unfollow of a row without a handle: not written to the base")
            return
        handle = username.strip().lstrip("@")
        account_id = self._acting_account_id()
        if not account_id:
            logger.warning(f"Confirmed unfollow of @{handle} not written: the acting account is unknown")
            return
        if TikTokFollowGraphService.record_unfollow(handle, account_id):
            self.stats.recorded += 1
        else:
            logger.warning(f"Confirmed unfollow of @{handle} could not be written to the base")

    def _acting_account_id(self) -> Optional[int]:
        """The acting account's id, resolved once, the way the list sync resolves it."""
        if self._account_resolved:
            return self._account_id
        self._account_resolved = True
        username = normalize_username(self.config.bot_username)
        if not username:
            logger.warning("The acting account is unknown: follows cannot be dated nor unfollows written")
            return None
        try:
            from taktik.core.database.local.service import get_local_database

            self._account_id, _ = get_local_database().get_or_create_tiktok_account(username)
        except Exception as e:
            logger.warning(f"Could not resolve the acting account @{username} ({e})")
            self._account_id = None
        return self._account_id

    def _resolve_username(self, button_elem) -> Optional[str]:
        """The handle on the same row as a Following/Friends button, or None.

        Paired by vertical overlap, as `find_follower_rows` pairs them. The old test (tops less
        than 50 px apart) failed on 43.1.4, where the handle sits 58 px below the button's top.
        The following list does not show a handle on every row: those rows get None.
        """
        try:
            bounds = get_element_bounds(button_elem)
            if not bounds:
                return None
            username_elems = first_matching(self.device, self._selectors.follower_username)
            return find_username_for_bounds(username_elems, bounds) or None
        except Exception:
            return None

    def _log_refusals(self) -> None:
        if self.stats.refusals:
            logger.info(f"Kept rows by motive: {self.stats.refusals}")
        if self.stats.unconfirmed:
            logger.warning(f"{self.stats.unconfirmed} tap(s) not confirmed by the row (not counted)")

    def _emit_stats(self):
        if self._on_stats:
            self._on_stats(self.stats.to_dict())
