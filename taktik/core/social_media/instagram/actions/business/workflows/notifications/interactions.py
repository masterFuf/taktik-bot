"""Notification user interactions: navigate to profile, interact, record to DB."""

import time
from typing import Dict, List, Any, Optional


class NotificationInteractionsMixin:
    """Mixin: interact with user from notifications + record filtered/interacted to DB."""

    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """
        Interagir avec un utilisateur depuis les notifications.
        Navigation + unified profile processing pipeline.
        """
        try:
            # Naviguer vers le profil
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.warning(f"Cannot navigate to @{username}")
                return None
            
            time.sleep(2)
            
            # === UNIFIED PROFILE PROCESSING ===
            result = self._process_profile_on_screen(
                username, config,
                source_type='NOTIFICATIONS',
                source_name=config.get('source', 'notifications'),
                account_id=self._get_account_id(),
                session_id=self._get_session_id()
            )
            
            # Retourner à l'onglet activité pour continuer
            self._navigate_to_activity_tab()
            
            if result.actually_interacted:
                return {
                    'likes': result.likes,
                    'follows': result.follows,
                    'comments': result.comments,
                    'stories': result.stories,
                    'stories_liked': result.stories_liked
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error interacting with @{username}: {e}")
            return None
