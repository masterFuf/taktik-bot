"""The Instagram unfollow: one engine that decides on data, acts on screen, checks on screen.

Rebuilt on 2026-09-24 (U1 to U8 of the unfollow plan). Until then the desktop ran a list loop that
tapped every "Following" button from the top of the list, in English only, counted every tap as
an unfollow, ignored the mode, the lists, the delay since the follow and "bot follows only",
stopped at no block and at no ceiling; a second loop that could decide had no caller, and a third
unfollowed a given list through the search. One engine is left:

1. sync the following list (and the followers list, for the modes that depend on reciprocity);
2. choose the candidates from the base, rule by rule (`candidates.py`); in doubt, nobody;
3. walk the following list; for each row of a candidate still followed: check its profile when a
   rule needs the screen (the "Follows you" badge, verified or business accounts), tap the row
   button, confirm a private account, read the row again (an unfollow counts only if the row now
   offers to follow), stop at the first sign of a block, count it in the session, the day and
   the warmup, pause the configured time.
"""

import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from loguru import logger

from ....core.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter
from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
from taktik.core.shared.telemetry import emit_step
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons

from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS
from taktik.core.shared.behavior.tap import tap_element_human
from .candidates import FollowersSnapshot, records_from_rows, select_candidates
from .list_proof import scrolls_for
from .mixins.decision import UnfollowDecisionMixin
from .mixins.actions import UnfollowActionsMixin
from .mixins.sync_following import SyncFollowingMixin
from .mixins.sync_followers import SyncFollowersMixin


class UnfollowBusiness(
    SyncFollowersMixin,
    SyncFollowingMixin,
    UnfollowDecisionMixin,
    UnfollowActionsMixin,
    BaseBusinessAction
):
    """Business logic for unfollowing Instagram accounts."""

    # Bounded waits on the screen, in seconds (class attributes so a test can shorten them).
    confirm_dialog_timeout = 2.0
    row_state_timeout = 3.0
    # Walking the following list: the most scrolls, and the scrolls in a row that show no new
    # username before the end of the list is assumed.
    max_list_scrolls = 150
    end_of_list_scrolls = 3
    # Candidates targeted per run beyond the unfollows allowed, to absorb the ones the list does
    # not show (unfollowed elsewhere since the sync, or refused on their profile).
    candidate_margin = 10
    # Unfollows the screen did not confirm, in a row, before the run stops: a refusal that
    # leaves no dialog, or a row that cannot be read, must not turn into an endless tapping.
    max_unconfirmed_in_a_row = 3

    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "unfollow", init_business_modules=False)

        from ...common.workflow_defaults import UNFOLLOW_DEFAULTS
        self.default_config = {**UNFOLLOW_DEFAULTS}
        # Rows handled once in this SESSION (the runner keeps this instance for the session):
        # an unfollow the screen did not confirm, or a refused one, is never tapped again by a
        # later batch.
        self._handled: Set[str] = set()
        self._unconfirmed_in_a_row = 0
        # The syncs run once per SESSION: a later batch decides again on the base (which our own
        # unfollows keep up to date) instead of scrolling both lists again for minutes.
        self._synced = False
        self._followers: Optional[FollowersSnapshot] = None
        # How far the walk may scroll the following list: set from the list's count.
        self._walk_scroll_limit = self.max_list_scrolls

        # Sélecteurs centralisés (depuis selectors.py)
        self._unfollow_sel = UNFOLLOW_SELECTORS
        # Backward-compatible dict wrapper for existing code
        self._unfollow_selectors = {
            'following_button': self._unfollow_sel.following_button,
            'unfollow_confirm': self._unfollow_sel.unfollow_confirm,
            'following_list_item': self._unfollow_sel.following_list_item,
            'following_tab': self._unfollow_sel.following_tab,
            'sort_button': self._unfollow_sel.sort_button,
            'sort_option_default': self._unfollow_sel.sort_option_default,
            'sort_option_latest': self._unfollow_sel.sort_option_latest,
            'sort_option_earliest': self._unfollow_sel.sort_option_earliest,
            'sort_entry_label': self._unfollow_sel.sort_entry_label,
        }

    # ─── The engine ────────────────────────────────────────────────────────────

    def run_unfollow_workflow(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the unfollow: sync, choose on data, act and check on screen.

        `config` carries the whole page (and scheduler) setting: `max_unfollows`, `unfollow_mode`,
        `bot_follows_only`, `min_days_since_follow`, `whitelist`, `blacklist`, `skip_verified`,
        `skip_business`, `unfollow_delay_range`. Returns the statistics, with `stop_reason` set when
        the run must end the session (a block).
        """
        cfg = {**self.default_config, **(config or {})}
        mode = cfg.get('unfollow_mode', 'non-followers')
        stats = self._new_stats()

        try:
            account_id = self._get_account_id()
            if not account_id:
                self.logger.error("Unfollow: no active account, nothing can be decided")
                stats['errors'] += 1
                stats['stop_reason'] = stop_reasons.no_account()
                return stats
            self.logger.info(
                f"🔄 Unfollow: mode={mode} | max={cfg.get('max_unfollows')} | "
                f"bot follows only={cfg.get('bot_follows_only')} | "
                f"min days since follow={cfg.get('min_days_since_follow')} | "
                f"whitelist={len(cfg.get('whitelist') or [])} | blacklist={len(cfg.get('blacklist') or [])}"
            )

            # 1. What the base knows: the following list, and the followers when it matters.
            # Once per session (see __init__).
            if not self._synced:
                following_sync = self.sync_following_list(cfg)
                stats['following_sync'] = {k: following_sync.get(k) for k in
                                           ('new_count', 'updated_count', 'total_seen', 'expected',
                                            'complete', 'departures', 'departures_withheld')}
                if mode in ('non-followers', 'mutual'):
                    followers_sync = self.sync_followers_list({'mode': 'fast'})
                    self._followers = FollowersSnapshot(
                        usernames=frozenset(followers_sync.get('usernames') or ()),
                        complete=bool(followers_sync.get('complete')),
                    )
                    stats['followers_sync'] = {'total_seen': followers_sync.get('total_seen'),
                                               'expected': followers_sync.get('expected'),
                                               'complete': self._followers.complete}
                self._synced = True
            followers = self._followers

            # 2. The decision, on data.
            selection = select_candidates(
                records_from_rows(InstagramFollowGraphService.list_active_followings(account_id)),
                cfg, followers, datetime.now(timezone.utc).replace(tzinfo=None),
            )
            stats['candidates'] = len(selection.candidates)
            stats['refusals'] = dict(selection.refusals)
            self.logger.info(
                f"📋 {len(selection.candidates)} candidate(s); refused: {selection.refusals or 'none'}"
            )
            IPCEmitter.emit_unfollow_plan(mode=mode, candidates=len(selection.candidates),
                                          refusals=dict(selection.refusals))
            # The accounts a batch of this session handled already are out of the window BEFORE it
            # is cut: a window of the oldest candidates held only the ones refused on their profile
            # by the previous batch, and the session ended under its maximum (review 2026-09-24).
            remaining = [name for name in selection.candidates if name.lower() not in self._handled]
            stats['candidates_left'] = len(remaining)
            if not remaining:
                stats['success'] = True
                stats['stop_reason'] = stop_reasons.no_unfollow_candidates(
                    len(self._handled), sum(selection.refusals.values()))
                return stats

            # 3. On screen: open our following list and act on the candidates it shows.
            max_unfollows = int(cfg.get('max_unfollows') or 0)
            window = remaining[:max_unfollows + self.candidate_margin] if max_unfollows else remaining
            if self._open_list_and_walk(cfg, window, selection.forced, stats):
                stats['success'] = True
            stats['candidates_left'] = sum(1 for name in selection.candidates
                                           if name.lower() not in self._handled)
            # What the profiles refused goes to the page with what the data refused.
            refused = dict(selection.refusals)
            for reason, count in stats['profile_refusals'].items():
                refused[reason] = refused.get(reason, 0) + count
            if stats['not_in_list']:
                refused['not_in_list'] = refused.get('not_in_list', 0) + stats['not_in_list']
            IPCEmitter.emit_unfollow_plan(mode=mode, candidates=len(selection.candidates), refusals=refused)
            self.logger.info(
                f"✅ Unfollow done: {stats['unfollows_made']} unfollowed, "
                f"{stats['unconfirmed']} not confirmed, refused on profile: {stats['profile_refusals'] or 'none'}, "
                f"{stats['candidates_left']} candidate(s) left"
            )
        except Exception as e:
            self.logger.error(f"Error in the unfollow workflow: {e}")
            stats['errors'] += 1
            stats['stop_reason'] = stats['stop_reason'] or stop_reasons.navigation_lost()
        return stats

    def _open_list_and_walk(self, cfg: Dict[str, Any], targets: List[str], forced: Set[str],
                            stats: Dict[str, Any]) -> bool:
        """Step 3 of the engine: open OUR following list on its tab, oldest follows first, and act
        on the rows of `targets`. Shared by the engine and the Lab's unitary unfollow, so the Lab
        runs exactly the production step. False (with a failure stop reason) when the list could
        not be opened: that is not "nothing to unfollow"."""
        if not self.nav_actions.navigate_to_profile_tab():
            self.logger.error("Unfollow: could not open our profile")
            stats['errors'] += 1
            stats['stop_reason'] = stop_reasons.navigation_lost()
            return False
        time.sleep(2)
        if not self.nav_actions.open_following_list():
            self.logger.error("Unfollow: could not open our following list")
            stats['errors'] += 1
            stats['stop_reason'] = stop_reasons.list_unavailable()
            return False
        time.sleep(2)
        if not self._ensure_following_tab():
            stats['errors'] += 1
            stats['stop_reason'] = stop_reasons.list_unavailable()
            return False
        # The candidates come oldest follow first: so should the list, or on a big account the
        # walk stops (its scroll bound) long before the oldest ones. Where the language has no
        # known sort label (French today), the list stays in its own order.
        if not self._set_following_list_sort('earliest'):
            self.logger.info("Unfollow: 'earliest' sort not applied, walking the list in its own order")
        self._walk_scroll_limit = scrolls_for(self._list_tab_count('following'), self.max_list_scrolls)
        self._unfollow_in_open_list(cfg, targets, forced, stats)
        return True

    def unfollow_listed_accounts(self, usernames: List[str], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Unfollow these accounts from our following list, with every screen check of the engine.

        The production act-and-check path without the base's decision: what the Lab's unitary
        unfollow calls (the accounts are the tester's choice). The mode's profile checks apply.
        """
        cfg = {**self.default_config, **(config or {})}
        stats = self._new_stats()
        targets = [u.strip().lstrip('@') for u in usernames if u and u.strip().lstrip('@')]
        stats['candidates'] = len(targets)
        if not targets:
            return stats
        # The tester names the accounts: an earlier attempt in this Lab session does not silently
        # skip them (the engine never retries a handled row within a run session).
        self._handled -= {name.lower() for name in targets}
        self._unconfirmed_in_a_row = 0
        if self._open_list_and_walk(cfg, targets, set(), stats):
            stats['success'] = True
        return stats

    # ─── Walking the open following list ───────────────────────────────────────

    @staticmethod
    def _new_stats() -> Dict[str, Any]:
        return {
            'candidates': 0,
            'unfollows_made': 0,
            'unconfirmed': 0,
            'refusals': {},
            'profile_refusals': {},
            'errors': 0,
            'scrolls': 0,
            'not_in_list': 0,
            'candidates_left': 0,
            'stop_reason': None,
            'success': False,
        }

    def _unfollow_in_open_list(self, cfg: Dict[str, Any], targets: List[str], forced: Set[str],
                               stats: Dict[str, Any]) -> None:
        """Act on the rows of `targets` that the open following list shows, top to bottom."""
        mode = cfg.get('unfollow_mode', 'non-followers')
        max_unfollows = int(cfg.get('max_unfollows') or 0)
        pending = {name.lower() for name in targets}
        # A row is handled once per session: an unfollow the screen did not confirm is not retried
        # (tapping again and again is what Instagram answers with "Try again later"), a refused
        # one neither.
        handled = self._handled
        pending -= handled
        seen: Set[str] = set()
        quiet_scrolls = 0

        while pending and stats['scrolls'] < self._walk_scroll_limit:
            if max_unfollows and stats['unfollows_made'] >= max_unfollows:
                break
            rows = self._visible_follow_rows()
            new_names = {row['username'].lower() for row in rows} - seen
            seen |= new_names
            row = next((r for r in rows if r['state'] == 'following'
                        and r['username'].lower() in pending
                        and r['username'].lower() not in handled), None)
            if row is None:
                quiet_scrolls = 0 if new_names else quiet_scrolls + 1
                if quiet_scrolls >= self.end_of_list_scrolls:
                    # The whole list was walked: a candidate it never showed is not followed any
                    # more (unfollowed elsewhere, a follow request never accepted, a name the base
                    # got wrong). Handled for this session, so the next batch takes the next ones.
                    stats['not_in_list'] += len(pending)
                    handled |= pending
                    self.logger.info(f"End of the following list; {len(pending)} candidate(s) not in it")
                    break
                self._scroll_following_list()
                stats['scrolls'] += 1
                time.sleep(1)
                continue

            username = row['username']
            key = username.lower()
            handled.add(key)
            pending.discard(key)

            refusal = self._profile_refusal(row, mode, key in forced, cfg)
            if refusal:
                stats['profile_refusals'][refusal] = stats['profile_refusals'].get(refusal, 0) + 1
                self.logger.info(f"⏭ @{username} kept: {refusal}")
                emit_step('unfollow_decision', action='skip', target=username, reason=refusal)
                continue
            if row.get('name_element') is not None and self._profile_was_opened(mode, key in forced, cfg):
                # Back from the profile: the rows were redrawn, read the candidate's row again.
                row = next((r for r in self._visible_follow_rows()
                            if r['username'].lower() == key and r['state'] == 'following'), None)
                if row is None:
                    stats['profile_refusals']['row_lost'] = stats['profile_refusals'].get('row_lost', 0) + 1
                    self.logger.info(f"⏭ @{username}: its row is no longer on screen after the profile")
                    continue

            if not self._unfollow_row(row, cfg, stats):
                break

    def _profile_was_opened(self, mode: str, forced: bool, cfg: Dict[str, Any]) -> bool:
        """Did `_profile_refusal` open the profile for this row (so the list was redrawn)?"""
        if forced:
            return False
        return (mode in ('non-followers', 'mutual')
                or bool(cfg.get('skip_verified', True))
                or bool(cfg.get('skip_business', False)))

    def _unfollow_row(self, row: Dict[str, Any], cfg: Dict[str, Any], stats: Dict[str, Any]) -> bool:
        """Tap the row button, confirm, check the row, check for a block, count, pause.

        Returns False when the walk must stop (a block).
        """
        username = row['username']
        max_unfollows = int(cfg.get('max_unfollows') or 0)
        try:
            self.logger.info(
                f"[{stats['unfollows_made'] + 1}/{max_unfollows or '∞'}] Tapping the following button of @{username}"
            )
            if not tap_element_human(self.device, row['button'], logger=self.logger):
                row['button'].click()
            time.sleep(1)
            # A confirmation dialog can appear (private account)
            if self._tap_unfollow_confirm(timeout=self.confirm_dialog_timeout):
                time.sleep(0.5)

            # Read the row again: the unfollow happened only if it now offers to follow.
            # Until 2026-09-24 every tap was counted, and 51 of the 298 unfollows in the base
            # had not happened (the same account "unfollowed" again 17 min later).
            row_state = self._wait_row_unfollowed(username)
            if row_state in ('follow', 'follow_back'):
                self._unconfirmed_in_a_row = 0
                stats['unfollows_made'] += 1
                self.logger.info(f"✅ Unfollowed @{username} ({stats['unfollows_made']}/{max_unfollows or '∞'})")
                # The session counts it: it is what caps the unfollows of this run
                if self.session_manager is not None:
                    self.session_manager.record_action('unfollow', success=True)
                # Base: the interaction, the day's totals, and the follow graph (closed)
                self._record_action(username, 'UNFOLLOW', 1)
                IPCEmitter.emit_unfollow(username, success=True)
                IPCEmitter.emit_stats(unfollows=stats['unfollows_made'])
            else:
                stats['unconfirmed'] += 1
                self._unconfirmed_in_a_row += 1
                self.logger.warning(
                    f"⚠️ @{username}: the row still reads '{row_state}' after the tap — unfollow NOT counted"
                )
                IPCEmitter.emit_unfollow(username, success=False)
        except Exception as e:
            self.logger.warning(f"Error unfollowing @{username}: {e}")
            stats['errors'] += 1

        # A block shows up right after the action it refuses. Acting again after "Try again
        # later" is what turns a temporary limit into a lasting one.
        blocked = self._action_blocked_reason()
        if blocked:
            stats['stop_reason'] = blocked
            return False
        if self._unconfirmed_in_a_row >= self.max_unconfirmed_in_a_row:
            self.logger.error(
                f"🛑 {self._unconfirmed_in_a_row} unfollows in a row not confirmed by the screen — stopping"
            )
            stats['stop_reason'] = stop_reasons.unfollow_unconfirmed(self._unconfirmed_in_a_row)
            return False
        self._pause_between_unfollows(cfg)
        return True

    def _pause_between_unfollows(self, config: Dict[str, Any]) -> None:
        """The pause between two unfollows, drawn from the configured range.

        The range comes from the page and the scheduler (`minDelay`/`maxDelay`, 2 to 5 s when
        absent). It used to be a hardcoded 2-5 s whatever the settings said.
        """
        low, high = config.get('unfollow_delay_range') or (2, 5)
        low, high = float(low), float(high)
        if high < low:
            low, high = high, low
        delay = random.uniform(low, high)
        self.logger.debug(f"⏳ Pause before the next unfollow: {delay:.1f}s")
        time.sleep(delay)

    def _action_blocked_reason(self):
        """The stop reason when Instagram shows its rate-limit dialog now, else None.

        The same read and the same reason as the followers workflow when it loses its list
        (`is_action_blocked`, `stop_reasons.action_blocked`): one detection, one rule, the first
        sign stops the session. The signal is also stored with the account's restriction
        history. Reading only: the dialog is left on screen, closing it would be acting again.
        """
        detector = getattr(getattr(self, 'nav_actions', None), 'problematic_page_detector', None)
        if detector is None or not hasattr(detector, 'is_action_blocked'):
            return None
        try:
            if not detector.is_action_blocked():
                return None
        except Exception as exc:  # noqa: BLE001 - a diagnosis must never end a run itself
            self.logger.debug(f"Could not read the screen for a block: {exc}")
            return None

        account_username = getattr(getattr(self, 'automation', None), 'active_username', None)
        self.logger.error(
            "🛑 Instagram is rate-limiting this account (\"Try again later\") after an unfollow — "
            "stopping the session"
        )
        emit_step('account_restriction', action='action_blocked', target=account_username or '')
        if account_username and account_username != 'unknown':
            try:
                from taktik.core.database.local.service import get_local_database

                get_local_database().account_restrictions.record_signal(
                    account_username,
                    platform="instagram",
                    signal="action_blocked",
                    source_type="UNFOLLOW",
                    source_name=None,
                    source_followers=None,
                    streak=None,
                    encounter_order=None,
                    jump_index=None,
                    gestures=None,
                    session_id=self._get_session_id(),
                )
            except Exception as exc:  # noqa: BLE001 - losing a measurement must not lose the run
                self.logger.debug(f"Could not persist the restriction signal: {exc}")
        return stop_reasons.action_blocked()

    def _wait_row_unfollowed(self, username: str, timeout: Optional[float] = None) -> str:
        """The row state of @username, read until it offers to follow or `timeout` elapses.

        A bounded wait on the state, not a fixed delay: the button flips in a few hundred ms on a
        good connection and much later on a slow one. Returns the last state read
        ('follow' / 'follow_back' on success; 'following', 'requested' or 'unknown' otherwise).
        Reads through `get_row_follow_state`, the production read the Lab exposes as
        `scraping.get_row_follow_state`.
        """
        deadline = time.time() + (self.row_state_timeout if timeout is None else timeout)
        while True:
            state = self.detection_actions.get_row_follow_state(username)
            if state in ('follow', 'follow_back') or time.time() >= deadline:
                return state
            time.sleep(0.5)
