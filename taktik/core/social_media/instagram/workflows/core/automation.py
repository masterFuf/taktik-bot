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
from ...utils.filters import InstagramFilters, DefaultFilters
from ..management.session import SessionManager
from .....license import unified_license_manager

from ...actions.core.base_action import BaseAction
from ...actions.compatibility.modern_instagram_actions import ModernInstagramActions

from ...ui.selectors import POST_SELECTORS, POPUP_SELECTORS
from ..management.config import WorkflowConfigBuilder
from .workflow_runner import WorkflowRunner
from ..helpers.workflow_helpers import WorkflowHelpers
from ..helpers.license_helpers import LicenseHelpers
from ..helpers.filtering_helpers import FilteringHelpers


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
        self.limits = self.config.get('limits', {})
        if not self.limits:
            self.limits = DefaultFilters.get_safe_filters()
        self.filters = InstagramFilters(self.config.get('filters', {}))
        
        self.min_sleep = self.config.get('min_sleep_between_actions', 1.0)
        self.max_sleep = self.config.get('max_sleep_between_actions', 4.0)
        
        self.active_username = None
        self.active_account_id = None
        
        self.hashtag_interaction_manager = self.actions.hashtag_business
        self.story_liker = self.actions.story_business
        
        self.current_session_id = None
        
        self.workflow_runner = WorkflowRunner(self)
        self.helpers = WorkflowHelpers(self)
        self.license_helpers = LicenseHelpers(self)
        self.filtering_helpers = FilteringHelpers(self)
        
        from ..helpers.ui_helpers import UIHelpers
        self.ui_helpers = UIHelpers(self)
        
        self.helpers.setup_signal_handlers()
        
    def _get_license_key_from_config(self) -> str:
        return self.license_helpers.get_license_key_from_config()

    def _initialize_license_limits(self, api_key: str = None):
        result = self.license_helpers.initialize_license_limits(api_key)
        self.license_limits_enabled = self.license_helpers.license_limits_enabled
        return result
    
    def _check_action_limits(self, action_type: str, account_username: str = None) -> bool:
        return self.license_helpers.check_action_limits(action_type, account_username)
    
    def _record_action_performed(self, action_type: str, account_username: str = None):
        return self.license_helpers.record_action_performed(action_type, account_username)
    
    def load_config(self, config_path: str) -> bool:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            session_settings = self.config.get('session_settings', {})
            session_settings = self.config.get('session_settings', {})
            duration_minutes = session_settings.get('session_duration_minutes', 'NOT_DEFINED')
            print(f"[DEBUG Automation] Configuration loaded from {config_path}:")
            print(f"[DEBUG Automation] - session_duration_minutes: {duration_minutes}")
            print(f"[DEBUG Automation] - session_settings: {session_settings}")
            
            if hasattr(self, 'session_manager') and self.session_manager:
                self.session_manager.update_config(self.config)
            else:
                self.session_manager = SessionManager(self.config)
            
            if 'filters' in self.config:
                self.filters = InstagramFilters(self.config['filters'])
            
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
                           config: Dict[str, Any] = None,
                           use_direct_mode: bool = True) -> Dict[str, Any]:
        """
        Interagit avec les followers d'un ou plusieurs comptes cibles.
        
        Args:
            target_username: Username cible unique
            target_usernames: Liste de usernames cibles
            max_interactions: Nombre max d'interactions
            like_posts: Liker les posts
            max_likes_per_profile: Max likes par profil
            skip_processed: Ignorer les profils déjà traités
            config: Configuration additionnelle
            use_direct_mode: Si True, utilise le nouveau workflow direct (sans deep links)
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
        
        # 🆕 Utiliser le nouveau workflow direct si activé
        if use_direct_mode:
            self.logger.info("🚀 Using DIRECT mode (no deep links, natural navigation)")
            
            # Pour le mode direct, on traite un target à la fois
            all_results = {
                'processed': 0,
                'liked': 0,
                'followed': 0,
                'stories_viewed': 0,
                'errors': 0,
                'skipped': 0
            }
            
            remaining_interactions = max_interactions
            
            for target in target_usernames:
                if remaining_interactions <= 0:
                    break
                    
                self.logger.info(f"📍 Processing target: @{target}")
                
                result = self.actions.follower_business.interact_with_followers_direct(
                    target_username=target,
                    max_interactions=remaining_interactions,
                    config=config,
                    account_id=self.active_account_id
                )
                
                # Agréger les résultats
                all_results['processed'] += result.get('processed', 0)
                all_results['liked'] += result.get('liked', 0)
                all_results['followed'] += result.get('followed', 0)
                all_results['stories_viewed'] += result.get('stories_viewed', 0)
                all_results['errors'] += result.get('errors', 0)
                all_results['skipped'] += result.get('skipped', 0)
                
                remaining_interactions -= result.get('processed', 0)
            
            self.logger.debug(f"Workflow completed: {all_results['processed']} profiles processed, {all_results['liked']} likes, {all_results['followed']} follows")
            return all_results
        
        # Mode legacy (avec deep links)
        self.logger.info("⚠️ Using LEGACY mode (with deep links)")
        result = self.actions.follower_business.interact_with_target_followers(
            target_usernames=target_usernames,
            max_interactions=max_interactions,
            like_posts=like_posts,
            max_likes_per_profile=max_likes_per_profile,
            skip_processed=skip_processed,
            automation=self,
            account_id=self.active_account_id,
            config=config
        )
        
        if result:
            self.logger.debug(f"Workflow completed: {result.get('processed', 0)} profiles processed, {result.get('liked', 0)} likes, {result.get('followed', 0)} follows")
        
        return result
        
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
        
        session_settings = self.config.get('session_settings', {})
        duration_minutes = session_settings.get('session_duration_minutes', 'NOT_DEFINED')
        print(f"[DEBUG Automation] SessionManager config update:")
        print(f"[DEBUG Automation] - config keys: {list(self.config.keys())}")
        print(f"[DEBUG Automation] - session_duration_minutes: {duration_minutes}")
        print(f"[DEBUG Automation] - session_settings: {session_settings}")

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
                
                actions_executed = False
                
                for step in workflow_steps:
                    should_continue_step, stop_reason_step = self.session_manager.should_continue()
                    if not should_continue_step:
                        stop_reason = stop_reason_step
                        break
                    
                    action = step if 'type' in step else step
                    
                    try:
                        executed = self.workflow_runner.run_workflow_step(action)
                        if executed:
                            actions_executed = True
                        
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

    def handle_place_workflow(self, action: Dict[str, Any]) -> Dict[str, int]:
        return self.workflow_runner._run_place_workflow_impl(action)

    def _is_current_post_reel(self) -> bool:
        return self.ui_helpers.is_current_post_reel()

    def _has_likes_on_current_post(self) -> bool:
        return self.ui_helpers.has_likes_on_current_post()

    def _scroll_to_next_post(self) -> bool:
        return self.ui_helpers.scroll_to_next_post()

    def _open_likes_list(self) -> bool:
        return self.ui_helpers.open_likes_list()

    def _is_likes_popup_open(self) -> bool:
        return self.ui_helpers.is_likes_popup_open()

    def _interact_with_likers(self, max_interactions: int, like_percentage: float, 
                            follow_percentage: float, filters: dict) -> int:
        return self.ui_helpers.interact_with_likers(max_interactions, like_percentage, follow_percentage, filters)
    
    def _close_likes_popup(self) -> bool:
        return self.ui_helpers.close_likes_popup()
    
    def _should_interact_with_user(self, username: str, filters: Dict[str, Any]) -> bool:
        return self.filtering_helpers.should_interact_with_user(username, filters)
    
    def _like_current_post(self) -> bool:
        return self.filtering_helpers.like_current_post()
    
    def _visit_profile_from_post(self, username: str) -> bool:
        return self.filtering_helpers.visit_profile_from_post(username)
    
    def _follow_user(self, username: str) -> bool:
        return self.filtering_helpers.follow_user(username)

    def handle_post_url_workflow(self, action: Dict[str, Any]) -> Dict[str, Any]:
        return self.workflow_runner._run_post_url_workflow(action)
