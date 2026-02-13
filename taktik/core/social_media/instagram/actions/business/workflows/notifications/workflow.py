"""Notifications workflow orchestration.

Internal structure:
- extraction.py    — Navigate to activity tab + extract users from notifications
- interactions.py  — Interact with user from notifications + record to DB
"""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.base_business_action import BaseBusinessAction
from ...common.database_helpers import DatabaseHelpers
from .extraction import NotificationExtractionMixin
from .interactions import NotificationInteractionsMixin


class NotificationsBusiness(NotificationExtractionMixin, NotificationInteractionsMixin, BaseBusinessAction):
    """Business logic for interacting with users from notifications/activity tab."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "notifications", init_business_modules=True)
        
        from ...common.workflow_defaults import NOTIFICATIONS_DEFAULTS
        from .....ui.selectors import NOTIFICATION_SELECTORS
        self.default_config = {**NOTIFICATIONS_DEFAULTS}
        
        # Sélecteurs centralisés (depuis selectors.py)
        self._notif_sel = NOTIFICATION_SELECTORS
        # Backward-compatible dict wrapper for existing code
        self._notification_selectors = {
            'activity_tab': self._notif_sel.activity_tab,
            'notification_item': self._notif_sel.notification_item,
            'notification_username': self._notif_sel.notification_username,
            'notification_action_text': self._notif_sel.notification_action_text,
            'follow_requests_section': self._notif_sel.follow_requests_section,
        }
    
    def interact_with_notifications(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Interagir avec les utilisateurs depuis l'onglet notifications.
        
        Args:
            config: Configuration du workflow
            
        Returns:
            Dict avec les statistiques
        """
        effective_config = {**self.default_config, **(config or {})}
        
        stats = {
            'notifications_processed': 0,
            'users_found': 0,
            'users_interacted': 0,
            'likes_made': 0,
            'follows_made': 0,
            'comments_made': 0,
            'stories_watched': 0,
            'stories_liked': 0,
            'profiles_filtered': 0,
            'skipped': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            self.logger.info("🔔 Starting notifications workflow")
            self.logger.info(f"Max interactions: {effective_config['max_interactions']}")
            
            # Naviguer vers l'onglet Activité
            if not self._navigate_to_activity_tab():
                self.logger.error("Failed to navigate to activity tab")
                stats['errors'] += 1
                return stats
            
            time.sleep(2)
            
            # Démarrer la phase de scraping
            if self.session_manager:
                self.session_manager.start_scraping_phase()
            
            # Extraire les utilisateurs des notifications
            users = self._extract_users_from_notifications(
                max_users=effective_config['max_interactions'] * 2,
                notification_types=effective_config.get('notification_types', ['likes', 'follows', 'comments'])
            )
            stats['users_found'] = len(users)
            
            # Terminer le scraping et démarrer les interactions
            if self.session_manager:
                self.session_manager.end_scraping_phase()
                self.session_manager.start_interaction_phase()
            
            if not users:
                self.logger.warning("No users found in notifications")
                return stats
            
            users_to_process = users[:effective_config['max_interactions']]
            self.logger.info(f"📋 {len(users_to_process)} users to process from notifications")
            
            effective_config['source'] = "notifications"
            
            for i, username in enumerate(users_to_process, 1):
                self.logger.info(f"[{i}/{len(users_to_process)}] Processing @{username}")
                
                account_id = getattr(self.automation, 'active_account_id', None) if self.automation else None
                if DatabaseHelpers.is_profile_already_processed(username, account_id):
                    self.logger.info(f"Profile @{username} already processed, skipped")
                    stats['skipped'] += 1
                    self.stats_manager.increment('skipped')
                    continue
                
                interaction_result = self._interact_with_user(username, effective_config)
                
                if interaction_result:
                    stats['users_interacted'] += 1
                    stats['likes_made'] += interaction_result.get('likes', 0)
                    stats['follows_made'] += interaction_result.get('follows', 0)
                    stats['comments_made'] += interaction_result.get('comments', 0)
                    stats['stories_watched'] += interaction_result.get('stories', 0)
                    stats['stories_liked'] += interaction_result.get('stories_liked', 0)
                    
                    self.stats_manager.increment('interactions')
                    self.stats_manager.increment('likes', interaction_result.get('likes', 0))
                    self.stats_manager.increment('follows', interaction_result.get('follows', 0))
                else:
                    stats['profiles_filtered'] += 1
                
                stats['notifications_processed'] += 1
                
                # Délai entre interactions
                delay = random.randint(*effective_config['interaction_delay_range'])
                self.logger.debug(f"⏳ Waiting {delay}s before next interaction")
                time.sleep(delay)
            
            stats['success'] = True
            self.logger.info(f"✅ Notifications workflow completed: {stats['users_interacted']} interactions")
            
        except Exception as e:
            self.logger.error(f"Error in notifications workflow: {e}")
            stats['errors'] += 1
        
        return stats
