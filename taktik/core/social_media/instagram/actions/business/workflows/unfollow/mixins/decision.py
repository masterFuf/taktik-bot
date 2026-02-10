"""Decision logic for whether to unfollow an account."""

import time
from typing import Dict, Any, Optional

from ....common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service


class UnfollowDecisionMixin:
    """Mixin: determine whether an account should be unfollowed."""
    
    def _should_unfollow_account(self, username: str, config: Dict[str, Any]) -> tuple:
        """
        Déterminer si on doit unfollow un compte.
        
        Args:
            username: Nom d'utilisateur
            config: Configuration
            
        Returns:
            Tuple (should_unfollow: bool, reason: str)
        """
        try:
            # Naviguer vers le profil pour vérifier
            if not self.nav_actions.navigate_to_profile(username):
                return False, "cannot_navigate"
            
            time.sleep(1.5)
            
            # Vérifier si c'est un compte vérifié
            if config.get('skip_verified', True):
                if self.detection_actions.is_verified_account():
                    self._go_back_to_following_list()
                    return False, "verified_account"
            
            # Vérifier si c'est un compte business
            if config.get('skip_business', False):
                if self.detection_actions.is_business_account():
                    self._go_back_to_following_list()
                    return False, "business_account"
            
            # Vérifier si le compte nous follow en retour
            if config.get('unfollow_non_followers', True):
                if self._does_user_follow_back(username):
                    self._go_back_to_following_list()
                    return False, "is_follower"
            
            # Vérifier la date du follow (si disponible en BDD)
            if config.get('min_days_since_follow', 0) > 0:
                days_since_follow = self._get_days_since_follow(username)
                if days_since_follow is not None and days_since_follow < config['min_days_since_follow']:
                    self._go_back_to_following_list()
                    return False, f"recent_follow_{days_since_follow}d"
            
            return True, "should_unfollow"
            
        except Exception as e:
            self.logger.debug(f"Error checking if should unfollow @{username}: {e}")
            return False, f"error: {e}"
    
    def _does_user_follow_back(self, username: str) -> bool:
        """Vérifier si un utilisateur nous follow en retour."""
        try:
            return self._is_element_present(self._unfollow_sel.follows_back_indicators)
            
        except Exception as e:
            self.logger.debug(f"Error checking if @{username} follows back: {e}")
            return False  # En cas de doute, on considère qu'il ne follow pas
    
    def _get_days_since_follow(self, username: str) -> Optional[int]:
        """Récupérer le nombre de jours depuis le follow (depuis la BDD)."""
        try:
            account_id = self._get_account_id()
            if not account_id:
                return None
            
            # Chercher dans l'historique des interactions
            db_service = get_db_service()
            if db_service:
                # Cette méthode devrait être implémentée dans DatabaseHelpers
                return DatabaseHelpers.get_days_since_follow(username, account_id)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting days since follow for @{username}: {e}")
            return None
