"""Business logic for Instagram unfollow workflow.

Unfollows accounts automatically.
Utilisations typiques:
- clean up the following list
- unfollow the accounts that do not follow back
- unfollow the inactive accounts
"""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter
from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
from taktik.core.shared.telemetry import emit_step
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons

from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS
from taktik.core.shared.behavior.tap import tap_element_human
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

    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "unfollow", init_business_modules=False)
        
        from ...common.workflow_defaults import UNFOLLOW_DEFAULTS
        self.default_config = {**UNFOLLOW_DEFAULTS}
        
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
        }
    
    # ─── Workflow 1: run_unfollow_workflow (profile-visit based) ──────────

    def run_unfollow_workflow(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run the unfollow workflow.
        
        Args:
            config: workflow configuration
            
        Returns:
            Dict of statistics
        """
        effective_config = {**self.default_config, **(config or {})}
        
        stats = {
            'accounts_checked': 0,
            'unfollows_made': 0,
            'skipped_whitelisted': 0,
            'skipped_blacklisted_forced': 0,
            'skipped_not_bot_follow': 0,
            'skipped_verified': 0,
            'skipped_business': 0,
            'skipped_recent': 0,
            'skipped_followers': 0,
            'skipped_not_mutual': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            unfollow_mode = effective_config.get('unfollow_mode', 'non-followers')
            self.logger.info("🔄 Starting unfollow workflow")
            self.logger.info(f"Mode: {unfollow_mode} | Max: {effective_config['max_unfollows']} | Cooldown: {effective_config.get('min_days_since_follow', 0)}d | Bot-only: {effective_config.get('bot_follows_only', False)}")
            self.logger.info(f"Whitelist: {len(effective_config.get('whitelist', []))} | Blacklist: {len(effective_config.get('blacklist', []))}")
            
            # -- Incremental sync of the following list --
            sync_stats = self.sync_following_list(effective_config)
            self.logger.info(
                f"📊 Sync: {sync_stats['new_count']} new, "
                f"{sync_stats['updated_count']} updated, "
                f"stopped_early={sync_stats['stopped_early']}"
            )

            # -- Sync of the non-reciprocal accounts through the native category --
            if unfollow_mode in ('non-followers', 'mutual'):
                nf_stats = self.scrape_non_followers_category(effective_config)
                self.logger.info(
                    f"📊 Non-followers: {nf_stats['non_followers_count']} non-followers, "
                    f"{nf_stats['mutuals_count']} mutuals"
                )

            # Navigate to our own profile
            if not self.nav_actions.navigate_to_profile_tab():
                self.logger.error("Failed to navigate to own profile")
                stats['errors'] += 1
                return stats
            
            time.sleep(2)
            
            # Open the following list
            if not self.nav_actions.open_following_list():
                self.logger.error("Failed to open following list")
                stats['errors'] += 1
                return stats
            
            time.sleep(2)
            
            # Apply sorting based on unfollow mode
            unfollow_mode = effective_config.get('unfollow_mode', 'non-followers')
            if unfollow_mode == 'oldest':
                # Sort by "Date followed: Earliest" to unfollow oldest first
                self._set_following_list_sort('earliest')
                time.sleep(1.5)
            elif unfollow_mode == 'all':
                # Sort by "Date followed: Latest" for "all following" mode
                self._set_following_list_sort('latest')
                time.sleep(1.5)
            # For 'non-followers' mode, we keep default sorting
            
            # Extract the accounts that could be unfollowed
            accounts_to_check = self._extract_following_accounts(
                max_accounts=effective_config['max_unfollows'] * 3
            )
            
            if not accounts_to_check:
                self.logger.warning("No accounts found in following list")
                return stats
            
            self.logger.info(f"📋 {len(accounts_to_check)} accounts to check")
            
            unfollows_done = 0
            
            for username in accounts_to_check:
                if unfollows_done >= effective_config['max_unfollows']:
                    self.logger.info(f"✅ Reached max unfollows ({effective_config['max_unfollows']})")
                    break
                
                stats['accounts_checked'] += 1
                self.logger.info(f"[{stats['accounts_checked']}] Checking @{username}")
                
                # Vérifier si on doit unfollow ce compte
                should_unfollow, reason = self._should_unfollow_account(username, effective_config)
                
                if not should_unfollow:
                    self.logger.debug(f"Skipping @{username}: {reason}")
                    if 'whitelisted' in reason:
                        stats['skipped_whitelisted'] += 1
                    elif 'not_followed_by_bot' in reason:
                        stats['skipped_not_bot_follow'] += 1
                    elif 'verified' in reason:
                        stats['skipped_verified'] += 1
                    elif 'business' in reason:
                        stats['skipped_business'] += 1
                    elif 'recent' in reason:
                        stats['skipped_recent'] += 1
                    elif 'not_mutual' in reason:
                        stats['skipped_not_mutual'] += 1
                    elif 'follower' in reason:
                        stats['skipped_followers'] += 1
                    continue
                
                # Effectuer l'unfollow
                if self._unfollow_account(username):
                    stats['unfollows_made'] += 1
                    unfollows_done += 1
                    self.logger.info(f"✅ Unfollowed @{username} ({unfollows_done}/{effective_config['max_unfollows']})")
                    
                    # Enregistrer l'action
                    self._record_action(username, 'UNFOLLOW', 1)

                    # Mark as unfollowed in the sync table
                    try:
                        account_id = self._get_account_id()
                        if account_id:
                            InstagramFollowGraphService.mark_unfollowed(username, account_id)
                    except Exception:
                        pass
                    
                    # Délai entre unfollows
                    delay = random.randint(*effective_config['unfollow_delay_range'])
                    self.logger.debug(f"⏳ Waiting {delay}s before next unfollow")
                    time.sleep(delay)
                else:
                    stats['errors'] += 1
            
            stats['success'] = True
            self.logger.info(f"✅ Unfollow workflow completed: {stats['unfollows_made']} unfollows")
            
        except Exception as e:
            self.logger.error(f"Error in unfollow workflow: {e}")
            stats['errors'] += 1
        
        return stats
    
    # ─── Workflow 2: run_simple_unfollow_from_list (fast, no profile visit) ─

    def run_simple_unfollow_from_list(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        SIMPLE unfollow: tap the following buttons directly in the list.
        
        This is much faster than visiting each profile.
        The list of our own following must already be open.
        
        Args:
            config: workflow configuration
            
        Returns:
            Dict of statistics
        """
        effective_config = {**self.default_config, **(config or {})}
        max_unfollows = effective_config.get('max_unfollows', 50)
        
        stats = {
            'unfollows_made': 0,
            'unconfirmed': 0,
            'errors': 0,
            'scrolls': 0,
            'stop_reason': None,
            'success': False
        }

        try:
            self.logger.info("🔄 Starting SIMPLE unfollow workflow (direct button clicks)")
            self.logger.info(f"Max unfollows: {max_unfollows}")

            unfollows_done = 0
            max_scrolls = 50
            scroll_count = 0
            no_button_count = 0
            # Rows already tapped once. An unfollow the screen did not confirm is not retried: the
            # row keeps its "following" button, and tapping it again and again is exactly the
            # pattern Instagram answers with "Try again later".
            attempted = set()

            while unfollows_done < max_unfollows and scroll_count < max_scrolls:
                # Every visible row whose button says we follow the account, in any language
                # (the button text goes through the shared state classifier, never a literal).
                following_rows = [row for row in self._visible_follow_rows()
                                  if row['state'] == 'following' and row['username'] not in attempted]

                if not following_rows:
                    self.logger.debug("No 'following' row button found on screen")
                    no_button_count += 1
                    if no_button_count >= 3:
                        self.logger.info("No more Following buttons after 3 scrolls, stopping")
                        break
                    # Scroll to reveal more
                    self._scroll_following_list()
                    scroll_count += 1
                    stats['scrolls'] += 1
                    time.sleep(1)
                    continue
                
                no_button_count = 0  # Reset counter

                # The first row, named by the username paired with its button
                row = following_rows[0]
                username = row['username']
                attempted.add(username)

                # Try to tap the button
                try:
                    self.logger.info(f"[{unfollows_done + 1}/{max_unfollows}] Tapping the following button of @{username}")
                    if not tap_element_human(self.device, row['button'], logger=self.logger):
                        row['button'].click()
                    time.sleep(1)

                    # A confirmation dialog can appear (private account)
                    if self._tap_unfollow_confirm(timeout=self.confirm_dialog_timeout):
                        time.sleep(0.5)

                    # Read the row again: the unfollow happened only if it now offers to follow.
                    # Until 2026-09-24 every tap was counted, and 51 of the 298 unfollows in the
                    # base had not happened (the same account "unfollowed" again 17 min later).
                    row_state = self._wait_row_unfollowed(username)
                    if row_state not in ('follow', 'follow_back'):
                        stats['unconfirmed'] += 1
                        self.logger.warning(
                            f"⚠️ @{username}: the row still reads '{row_state}' after the tap — "
                            f"unfollow NOT counted"
                        )
                        IPCEmitter.emit_unfollow(username, success=False)
                        blocked = self._action_blocked_reason()
                        if blocked:
                            stats['stop_reason'] = blocked
                            break
                        self._pause_between_unfollows(effective_config)
                        continue

                    unfollows_done += 1
                    stats['unfollows_made'] += 1
                    self.logger.info(f"✅ Unfollowed @{username} ({unfollows_done}/{max_unfollows})")
                    # The session counts it: it is what caps the unfollows of this run
                    if self.session_manager is not None:
                        self.session_manager.record_action('unfollow', success=True)
                    
                    # Enregistrer l'action
                    self._record_action(username, 'UNFOLLOW', 1)
                    
                    # Envoyer l'événement en temps réel au frontend si un bridge l'a injecté.
                    IPCEmitter.emit_unfollow(username, success=True)
                    IPCEmitter.emit_stats(unfollows=unfollows_done)

                    # A block shows up right after the action it refuses. Acting again after
                    # "Try again later" is what turns a temporary limit into a lasting one.
                    blocked = self._action_blocked_reason()
                    if blocked:
                        stats['stop_reason'] = blocked
                        break
                    
                    self._pause_between_unfollows(effective_config)
                    
                except Exception as e:
                    self.logger.warning(f"Error clicking Following button: {e}")
                    stats['errors'] += 1
                    # Scroll on to further buttons
                    self._scroll_following_list()
                    scroll_count += 1
                    stats['scrolls'] += 1
                    time.sleep(1)
            
            stats['success'] = True
            self.logger.info(f"✅ Simple unfollow workflow completed: {stats['unfollows_made']} unfollows in {stats['scrolls']} scrolls")
            
        except Exception as e:
            self.logger.error(f"Error in simple unfollow workflow: {e}")
            stats['errors'] += 1
        
        return stats
    
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

    # ─── Workflow 3: unfollow_specific_accounts ──────────────────────────

    def unfollow_specific_accounts(self, usernames: List[str], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Unfollow a specific list of accounts.
        
        Args:
            usernames: usernames to unfollow
            config: Configuration
            
        Returns:
            Dict of statistics
        """
        effective_config = {**self.default_config, **(config or {})}
        
        stats = {
            'accounts_to_unfollow': len(usernames),
            'unfollows_made': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            self.logger.info(f"🔄 Unfollowing {len(usernames)} specific accounts")
            
            for i, username in enumerate(usernames, 1):
                self.logger.info(f"[{i}/{len(usernames)}] Unfollowing @{username}")
                
                if self._unfollow_account(username):
                    stats['unfollows_made'] += 1
                    self._record_action(username, 'UNFOLLOW', 1)
                    
                    # Délai entre unfollows
                    if i < len(usernames):
                        delay = random.randint(*effective_config['unfollow_delay_range'])
                        self.logger.debug(f"⏳ Waiting {delay}s before next unfollow")
                        time.sleep(delay)
                else:
                    stats['errors'] += 1
            
            stats['success'] = True
            self.logger.info(f"✅ Unfollowed {stats['unfollows_made']}/{len(usernames)} accounts")
            
        except Exception as e:
            self.logger.error(f"Error in specific unfollow: {e}")
            stats['errors'] += 1
        
        return stats
