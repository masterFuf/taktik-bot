import time
import random
import json
import os
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from loguru import logger

from .....database import InstagramProfile, get_db_service
from ..management.session import SessionManager
from ...actions.core.base_action import BaseAction
from ...actions.compatibility.modern_instagram_actions import ModernInstagramActions

from ...ui.selectors.shell.popups import POPUP_SELECTORS
from ...ui.selectors.surfaces.post import POST_SELECTORS
from ..management.config import WorkflowConfigBuilder
from .workflow_runner import WorkflowRunner
from ..support.workflow_helpers import WorkflowHelpers
from ...actions.business.workflows.common.distribution import (
    ipc_source_progress,
    normalize_distribution,
    run_distributed,
)


class InstagramAutomation:

    def __init__(self, device_manager, config: Optional[Dict[str, Any]] = None, session_name: Optional[str] = None):

        if device_manager is None:
            raise ValueError("device_manager cannot be None")
            
        self.device_manager = device_manager
        
        if hasattr(device_manager, 'device') and device_manager.device is not None:
            self.device = device_manager.device
        else:
            raise ValueError("Cannot initialize device: device_manager.device is None or invalid")
            
        self.logger = logger.bind(module="instagram-automation")
        self.config = config or {}
        
        session_settings = self.config.get('session_settings', {})
        duration_minutes = session_settings.get('session_duration_minutes', 'NOT_DEFINED')
        
        self.session_manager = SessionManager(self.config)
        
        self.actions = ModernInstagramActions(self.device, self.session_manager, self)
        
        self.nav_actions = self.actions.profile_business.nav_actions
        self.profile_actions = self.actions.profile_business
        self.like_actions = self.actions.like_business
        self.follow_actions = self.actions.follower_business
        
        self.session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.stats = {
            'likes': 0,
            'follows': 0,
            'unfollows': 0,
            'comments': 0,
            'interactions': 0,
            'skipped': 0,
            'stories_viewed': 0,
            'stories_liked': 0,
            'start_time': time.time()
        }
        self.min_sleep = self.config.get('min_sleep_between_actions', 1.0)
        self.max_sleep = self.config.get('max_sleep_between_actions', 4.0)
        
        self.active_username = None
        self.active_account_id = None
        
        self.hashtag_interaction_manager = self.actions.hashtag_business
        self.story_liker = self.actions.story_business
        
        self.current_session_id = None
        
        self.workflow_runner = WorkflowRunner(self)
        self.helpers = WorkflowHelpers(self)
        
        from ..support.ui_helpers import UIHelpers
        self.ui_helpers = UIHelpers(self)
        
        self.helpers.setup_signal_handlers()
        
    def load_config(self, config_path: str) -> bool:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            session_settings = self.config.get('session_settings', {})
            duration_minutes = session_settings.get('session_duration_minutes', 'NOT_DEFINED')
            self.logger.debug(f"Configuration loaded from {config_path}: duration={duration_minutes}min, settings={session_settings}")
            
            if hasattr(self, 'session_manager') and self.session_manager:
                self.session_manager.update_config(self.config)
            else:
                self.session_manager = SessionManager(self.config)
            
            self.logger.info(f"Configuration loaded from {config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return False
    
    def like_profile_posts(self, username: str, max_posts: int = 9, like_posts: bool = True, 
                         max_likes: int = 3, scroll_attempts: int = 3) -> Dict[str, int]:
        self.logger.info(f"Starting post liking for @{username} via LikeProfilePostsManager")
        
        stats = self.like_actions.like_profile_posts(
            username=username,
            max_posts=max_posts,
            like_posts=like_posts,
            max_likes=max_likes,
            scroll_attempts=scroll_attempts
        )
        
        return stats

    def interact_with_followers(self, target_username: str = None, target_usernames: List[str] = None,
                           max_interactions: int = 100, like_posts: bool = True,
                           max_likes_per_profile: int = 2, skip_processed: bool = True,
                           config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Interact with the followers of one or several target accounts, through the direct
        workflow, tapping in the list with no deep-link navigation. With several targets,
        the budget is split according to the configured distribution.
        """
        if not self.active_account_id:
            self.logger.info("Active account not detected, retrieving current profile...")
            self.get_profile_info(username=None, save_to_db=True)

        if not self.active_account_id:
            self.logger.error("Cannot get or create active Instagram account")
            return {}

        # Support both single and multi-target
        if target_usernames is None:
            target_usernames = [target_username] if target_username else []

        if not target_usernames:
            self.logger.error("No target username(s) provided")
            return {}

        all_results = {
            'processed': 0,
            'liked': 0,
            'followed': 0,
            'stories_viewed': 0,
            'errors': 0,
            'skipped': 0
        }
        last_stop_reason = ''

        def run_one_target(target: str, quota: int):
            nonlocal last_stop_reason
            self.logger.info(f"📍 Processing target: @{target} (quota: {quota})")
            # finalize=False: the driver finalises ONCE below — the per-target runner
            # finalising would end the session (and tell the front) after target 1.
            result = self.actions.follower_business.interact_with_followers_direct(
                target_username=target,
                max_interactions=quota,
                config=config,
                account_id=self.active_account_id,
                finalize=False
            )
            for key in all_results:
                all_results[key] += result.get(key, 0)
            stop_reason = result.get('stop_reason') or ''
            if stop_reason:
                last_stop_reason = stop_reason
            return result.get('processed', 0), bool(stop_reason)

        distribution = normalize_distribution((config or {}).get('distribution'))
        if len(target_usernames) > 1:
            self.logger.info(f"🎯 {len(target_usernames)} targets, distribution: {distribution}")
        outcome = run_distributed(
            target_usernames, max_interactions, distribution, run_one_target,
            on_progress=ipc_source_progress('target'),
        )

        if not getattr(self, 'session_finalized', False):
            reason = last_stop_reason or f"Workflow completed ({outcome['processed']} interactions)"
            self._finalize_session(status='COMPLETED', reason=reason)

        self.logger.debug(f"Workflow completed: {all_results['processed']} profiles processed, {all_results['liked']} likes, {all_results['followed']} follows")
        return all_results
        
    def get_profile_info(self, username: Optional[str] = None, save_to_db: bool = False, log_result: bool = True) -> Dict[str, Any]:
        from taktik.core.database import get_db_service
        
        profile_manager = self.actions.profile_business
        
        profile_info = profile_manager.get_complete_profile_info(username, navigate_if_needed=True)
        
        if profile_info and profile_info.get('username'):
            self.active_username = profile_info['username']
            
            if username is None and save_to_db:
                try:
                    self.active_account_id, created = get_db_service().get_or_create_account(self.active_username, is_bot=True)
                    
                    if created:
                        self.logger.info(f"New Instagram account created: {self.active_username} (ID: {self.active_account_id})")
                    else:
                        self.logger.info(f"Active Instagram account identified: {self.active_username} (ID: {self.active_account_id})")
                    
                    self.logger.info(f"Active account configured: {self.active_username} (ID: {self.active_account_id})")
                        
                except Exception as e:
                    self.logger.error(f"Error retrieving/creating active account: {e}")
                    self.active_account_id = 1
                    self.logger.warning(f"Using default account ID: 1 for {self.active_username}")
            
        return profile_info
    
    def update_session_manager_config(self):
        if hasattr(self, 'session_manager') and self.session_manager:
            self.session_manager.update_config(self.config)
        else:
            self.session_manager = SessionManager(self.config)

        # Warmup daily-budget provider: give the SessionManager a way to read TODAY's totals for the
        # active account, so its in-session cap sees this session's own live writes. Bound to a
        # method (not a captured id) so it self-heals — before the account is identified it returns
        # empty totals (cap no-op), and starts reading real numbers the moment active_account_id is
        # set. No-op end to end when the desktop injected no warmup caps.
        self.session_manager.set_daily_usage_provider(self._today_usage_for_warmup)

        session_settings = self.config.get('session_settings', {})
        duration_minutes = session_settings.get('session_duration_minutes', 'NOT_DEFINED')
        self.logger.debug(f"SessionManager config update: duration={duration_minutes}min, keys={list(self.config.keys())}")

    def _today_usage_for_warmup(self) -> Dict[str, int]:
        """Today's action totals for the active account, for the warmup daily-budget stop.

        Returns empty totals (never trips the cap) when no account is resolved yet or the read
        fails — the front launch gate remains the primary guard; the bot cap is defense in depth.
        """
        account_id = getattr(self, 'active_account_id', None)
        if not account_id:
            return {}
        try:
            return get_db_service().get_today_totals(account_id)
        except Exception as exc:
            self.logger.warning(f"Warmup daily-usage read failed (continuing without cap): {exc}")
            return {}

    def _create_workflow_session(self, action_override: Dict[str, Any] = None) -> Optional[int]:
        return self.helpers.create_workflow_session(action_override)

    def _update_workflow_session(self, session_id: int, status: str = 'COMPLETED') -> bool:
        return self.helpers.update_workflow_session(session_id, status)


    def display_session_stats(self, profile_username: str = None) -> None:
        self.helpers.display_session_stats(profile_username)

    def run_workflow(self) -> None:
        if not self.config:
            self.logger.error("No configuration loaded. Use load_config() first.")
            return
            
        self.update_session_manager_config()
        self.session_finalized = False  # Reset flag at start
        self.logger.info("=== Starting Instagram automation session ===")
        
        session_id = self.helpers.initialize_session()
        if not session_id:
            return
        
        try:
            should_continue, stop_reason = self.session_manager.should_continue()
            while should_continue:
                if 'steps' in self.config:
                    workflow_steps = self.config['steps']
                elif 'actions' in self.config:
                    workflow_steps = self.config['actions']
                else:
                    self.logger.error("No action or step found in configuration")
                    break
                
                iteration_made_progress = False
                for step in workflow_steps:
                    should_continue_step, stop_reason_step = self.session_manager.should_continue()
                    if not should_continue_step:
                        stop_reason = stop_reason_step
                        break

                    action = step if 'type' in step else step

                    try:
                        step_made_progress = self.workflow_runner.run_workflow_step(action)
                        if step_made_progress:
                            iteration_made_progress = True

                        # Check if session was finalized by the workflow itself
                        if self.session_finalized:
                            self.logger.info("Session was finalized by workflow, exiting run_workflow")
                            return

                        delay = self.session_manager.get_delay_between_actions()
                        if delay > 0:
                            time.sleep(delay)

                    except Exception as e:
                        self.logger.error(f"Error executing action: {str(e)[:200]}", exc_info=True)
                        time.sleep(5)

                should_continue, stop_reason = self.session_manager.should_continue()
                if not should_continue:
                    self._finalize_session(status='COMPLETED', reason=stop_reason)
                    return

                # The loop exists to retry while there is still potential (session limits not
                # reached). An iteration where EVERY step reported no progress means the sources
                # are dry — looping again would re-search the same exhausted lists until the
                # session duration ran out, doing nothing but navigation.
                if not iteration_made_progress:
                    self.logger.info("Full iteration made no progress — sources exhausted, ending session")
                    self._finalize_session(status='COMPLETED', reason='Sources exhausted (no further progress)')
                    return

                self.logger.info("End of complete workflow iteration")
                time.sleep(random.uniform(10, 30))

                should_continue, stop_reason = self.session_manager.should_continue()
                
        except Exception as e:
            self.logger.error(f"Critical error executing workflow: {str(e)[:200]}", exc_info=True)
            if hasattr(self, 'current_session_id') and self.current_session_id:
                self._update_workflow_session(self.current_session_id, status='ERROR')

    def _finalize_session(self, status='COMPLETED', reason='Limits reached'):
        self.helpers.finalize_session(status, reason)

    def _setup_signal_handlers(self):
        self.helpers.setup_signal_handlers()
