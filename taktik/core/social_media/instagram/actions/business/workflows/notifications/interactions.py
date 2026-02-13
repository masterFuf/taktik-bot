"""Notification user interactions: navigate to profile, interact, record to DB."""

import time
from typing import Dict, List, Any, Optional

from ...common.database_helpers import DatabaseHelpers


class NotificationInteractionsMixin:
    """Mixin: interact with user from notifications + record filtered/interacted to DB."""

    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """
        Interagir avec un utilisateur depuis les notifications.
        Navigation + filtering + delegated interactions via unified method.
        """
        try:
            # Naviguer vers le profil
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.warning(f"Cannot navigate to @{username}")
                return None
            
            time.sleep(2)
            
            # Récupérer les infos profil
            profile_data = self.profile_business.get_complete_profile_info(username, navigate_if_needed=False)
            if not profile_data:
                self.logger.warning(f"Cannot get profile info for @{username}")
                self._navigate_to_activity_tab()
                return None
            
            # Vérifier les filtres (uses same method as all other workflows)
            if hasattr(self, 'filtering_business'):
                filter_criteria = config.get('filter_criteria', {})
                filter_result = self.filtering_business.apply_comprehensive_filter(
                    profile_data, filter_criteria
                )
                if not filter_result.get('suitable', True):
                    reasons = filter_result.get('reasons', ['filtered'])
                    self.logger.info(f"Profile @{username} filtered: {', '.join(reasons)}")
                    self._record_filtered_profile(username, ', '.join(reasons), config.get('source', 'notifications'))
                    self._navigate_to_activity_tab()
                    return None
            
            # === INTERACTIONS (delegated to unified method) ===
            result = self._perform_interactions_on_profile(username, config, profile_data=profile_data)
            
            # Retourner à l'onglet activité pour continuer
            self._navigate_to_activity_tab()
            
            # Return in expected format (without actually_interacted key)
            if result.get('actually_interacted', False):
                return {
                    'likes': result.get('likes', 0),
                    'follows': result.get('follows', 0),
                    'comments': result.get('comments', 0),
                    'stories': result.get('stories', 0),
                    'stories_liked': result.get('stories_liked', 0)
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error interacting with @{username}: {e}")
            return None
    
    def _record_filtered_profile(self, username: str, reason: str, source: str):
        """Enregistrer un profil filtré."""
        try:
            account_id = self._get_account_id()
            session_id = self._get_session_id()
            
            DatabaseHelpers.record_filtered_profile(
                username=username,
                reason=reason,
                source_type='NOTIFICATIONS',
                source_name=source,
                account_id=account_id,
                session_id=session_id
            )
        except Exception as e:
            self.logger.debug(f"Error recording filtered profile: {e}")
