"""Decision logic for whether to unfollow an account.

Priority order:
1. Whitelist → always SKIP (never unfollow)
2. Blacklist → always UNFOLLOW (force)
3. Bot-follows-only → skip if not followed by bot
4. Cooldown → skip if followed too recently
5. Mode-based logic (non-followers / mutual / oldest / all)
6. Safety checks (verified, business)
"""

import time
from typing import Dict, Any, Optional, List

from ....common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service


class UnfollowDecisionMixin:
    """Mixin: determine whether an account should be unfollowed."""
    
    def _should_unfollow_account(self, username: str, config: Dict[str, Any]) -> tuple:
        """
        Déterminer si on doit unfollow un compte.
        
        Priority:
        1. Whitelist check (always skip)
        2. Blacklist check (always unfollow)
        3. Bot-follows-only check
        4. Cooldown period check
        5. Mode-based filtering (non-followers/mutual/oldest/all)
        6. Safety checks (verified, business)
        
        Args:
            username: Nom d'utilisateur
            config: Configuration
            
        Returns:
            Tuple (should_unfollow: bool, reason: str)
        """
        try:
            # ── 1. WHITELIST (highest priority — never unfollow) ──
            whitelist: List[str] = config.get('whitelist', [])
            if username.lower() in [w.lower() for w in whitelist]:
                self.logger.info(f"⬜ @{username} is whitelisted, skipping")
                return False, "whitelisted"
            
            # ── 2. BLACKLIST (force unfollow, skip all other checks) ──
            blacklist: List[str] = config.get('blacklist', [])
            if username.lower() in [b.lower() for b in blacklist]:
                self.logger.info(f"⬛ @{username} is blacklisted, forcing unfollow")
                return True, "blacklisted"
            
            # ── 3. BOT-FOLLOWS-ONLY (skip if not followed by bot) ──
            if config.get('bot_follows_only', False):
                if not self._was_followed_by_bot(username):
                    return False, "not_followed_by_bot"
            
            # ── 4. COOLDOWN (skip if followed too recently) ──
            min_days = config.get('min_days_since_follow', 0)
            if min_days > 0:
                days_since_follow = self._get_days_since_follow(username)
                if days_since_follow is not None and days_since_follow < min_days:
                    return False, f"recent_follow_{days_since_follow}d"
            
            # ── 5. Navigate to profile for on-screen checks ──
            unfollow_mode = config.get('unfollow_mode', 'non-followers')
            
            # For 'all' mode, skip profile visit if no safety checks needed
            needs_profile_visit = (
                unfollow_mode in ('non-followers', 'mutual')
                or config.get('skip_verified', True)
                or config.get('skip_business', False)
            )
            
            if needs_profile_visit:
                if not self.nav_actions.navigate_to_profile(username):
                    return False, "cannot_navigate"
                time.sleep(1.5)
            
            # ── 6. SAFETY CHECKS (verified, business) ──
            if config.get('skip_verified', True) and needs_profile_visit:
                if self.detection_actions.is_verified_account():
                    self._go_back_to_following_list()
                    return False, "verified_account"
            
            if config.get('skip_business', False) and needs_profile_visit:
                if self.detection_actions.is_business_account():
                    self._go_back_to_following_list()
                    return False, "business_account"
            
            # ── 7. MODE-BASED FILTERING ──
            if unfollow_mode == 'non-followers':
                # Only unfollow if user does NOT follow back
                if self._does_user_follow_back(username):
                    self._go_back_to_following_list()
                    return False, "is_follower"
            elif unfollow_mode == 'mutual':
                # Only unfollow mutual followers (users who DO follow back)
                if not self._does_user_follow_back(username):
                    self._go_back_to_following_list()
                    return False, "not_mutual"
            # 'oldest' and 'all' modes: unfollow regardless of follow-back status
            
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
    
    def _was_followed_by_bot(self, username: str) -> bool:
        """Check if this user was originally followed by the bot (exists in interaction_history as FOLLOW)."""
        try:
            account_id = self._get_account_id()
            if not account_id:
                return False
            
            db_service = get_db_service()
            if not db_service:
                return False
            
            # Query interaction_history for a FOLLOW action targeting this username
            return DatabaseHelpers.has_bot_follow_record(username, account_id)
            
        except Exception as e:
            self.logger.debug(f"Error checking bot follow record for @{username}: {e}")
            return False  # Safety: if we can't check, skip
    
    def _get_days_since_follow(self, username: str) -> Optional[int]:
        """Récupérer le nombre de jours depuis le follow (depuis la BDD)."""
        try:
            account_id = self._get_account_id()
            if not account_id:
                return None
            
            # Chercher dans l'historique des interactions
            db_service = get_db_service()
            if db_service:
                return DatabaseHelpers.get_days_since_follow(username, account_id)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting days since follow for @{username}: {e}")
            return None
