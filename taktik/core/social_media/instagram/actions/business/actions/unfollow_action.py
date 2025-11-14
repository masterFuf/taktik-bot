"""
Action business pour l'unfollow intelligent Instagram.
"""
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from loguru import logger
from taktik.core.social_media.instagram.actions.core.base_action import BaseAction
from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.click_actions import ClickActions
from taktik.core.social_media.instagram.actions.atomic.scroll_actions import ScrollActions
from taktik.core.database.api_database_service import APIBasedDatabaseService


class UnfollowAction(BaseAction):
    """Action business pour l'unfollow intelligent."""
    
    def __init__(self, device, db_service: Optional[APIBasedDatabaseService] = None):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-unfollow-business")
        self.nav = NavigationActions(device)
        self.click = ClickActions(device)
        self.scroll = ScrollActions(device)
        self.db = db_service
    
    def get_following_list(self, max_users: int = 100) -> List[str]:
        """
        Récupérer la liste des comptes suivis.
        
        Args:
            max_users: Nombre maximum d'utilisateurs à récupérer
            
        Returns:
            List[str]: Liste des noms d'utilisateur
        """
        self.logger.info(f"📋 Getting following list (max: {max_users})...")
        
        following_list = []
        
        # Naviguer vers notre profil
        if not self.nav.navigate_to_profile_tab():
            self.logger.error("❌ Failed to navigate to profile")
            return following_list
        
        # Cliquer sur "Following"
        following_selectors = [
            '//android.widget.Button[contains(@content-desc, "following")]',
            '//android.widget.Button[contains(@text, "following")]',
            '//android.widget.TextView[@text="following"]/..',
        ]
        
        if not self._find_and_click(following_selectors):
            self.logger.error("❌ Failed to click following button")
            return following_list
        
        self._human_like_delay()
        
        # Scroller et collecter les usernames
        previous_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 50
        
        while len(following_list) < max_users and scroll_attempts < max_scroll_attempts:
            # Chercher les usernames visibles
            username_selectors = [
                '//android.widget.TextView[@resource-id="com.instagram.android:id/follow_list_username"]',
                '//android.widget.TextView[contains(@resource-id, "username")]'
            ]
            
            for selector in username_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    for element in elements:
                        username = element.text
                        if username and username not in following_list and not username.startswith('Follow'):
                            following_list.append(username)
                            self.logger.debug(f"➕ Found: @{username}")
                except Exception:
                    continue
            
            # Vérifier si on a trouvé de nouveaux utilisateurs
            if len(following_list) == previous_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                previous_count = len(following_list)
            
            # Scroller vers le bas
            self.scroll.scroll_down()
            self._random_sleep(0.5, 1.0)
        
        self.logger.success(f"✅ Found {len(following_list)} following accounts")
        return following_list[:max_users]
    
    def unfollow_user(self, username: str) -> bool:
        """
        Unfollow un utilisateur spécifique.
        
        Args:
            username: Nom d'utilisateur à unfollow
            
        Returns:
            bool: True si succès, False sinon
        """
        self.logger.info(f"👋 Unfollowing @{username}...")
        
        # Naviguer vers le profil de l'utilisateur
        if not self.nav.navigate_to_user_profile(username):
            self.logger.error(f"❌ Failed to navigate to @{username}")
            return False
        
        # Cliquer sur le bouton "Following"
        following_button_selectors = [
            '//android.widget.Button[@content-desc="Following"]',
            '//android.widget.Button[contains(@content-desc, "Following")]',
            '//android.widget.Button[@text="Following"]',
        ]
        
        clicked = False
        for selector in following_button_selectors:
            if self._find_and_click(selector, "Following button"):
                clicked = True
                break
        
        if not clicked:
            self.logger.error(f"❌ Failed to click following button for @{username}")
            return False
        
        self._human_like_delay()
        
        # Confirmer l'unfollow dans le popup
        unfollow_confirm_selectors = [
            '//android.widget.Button[@text="Unfollow"]',
            '//android.widget.Button[contains(@text, "Unfollow")]',
            '//android.widget.TextView[@text="Unfollow"]/..',
        ]
        
        for selector in unfollow_confirm_selectors:
            if self._find_and_click(selector, "Unfollow confirm"):
                self._human_like_delay()
                self.logger.success(f"✅ Unfollowed @{username}")
                
                # Enregistrer dans la base de données
                if self.db:
                    try:
                        self.db.log_action(
                            action_type='unfollow',
                            target_username=username,
                            success=True
                        )
                    except Exception as e:
                        self.logger.warning(f"⚠️ Failed to log unfollow: {e}")
                
                return True
        
        self.logger.error(f"❌ Failed to confirm unfollow for @{username}")
        return False
    
    def intelligent_unfollow(
        self,
        max_unfollow: int = 50,
        min_days_followed: int = 3,
        skip_verified: bool = True,
        skip_followers: bool = True,
        whitelist: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        Unfollow intelligent avec filtres.
        
        Args:
            max_unfollow: Nombre maximum d'unfollow
            min_days_followed: Nombre minimum de jours depuis le follow
            skip_verified: Ne pas unfollow les comptes vérifiés
            skip_followers: Ne pas unfollow ceux qui nous suivent
            whitelist: Liste des usernames à ne jamais unfollow
            
        Returns:
            Dict: Statistiques de l'opération
        """
        self.logger.info(f"🧠 Starting intelligent unfollow (max: {max_unfollow})...")
        
        stats = {
            'total_following': 0,
            'unfollowed': 0,
            'skipped_verified': 0,
            'skipped_followers': 0,
            'skipped_whitelist': 0,
            'skipped_recent': 0,
            'errors': 0
        }
        
        whitelist = whitelist or []
        
        # Récupérer la liste des comptes suivis
        following_list = self.get_following_list(max_users=max_unfollow * 2)
        stats['total_following'] = len(following_list)
        
        if not following_list:
            self.logger.warning("⚠️ No following accounts found")
            return stats
        
        # Filtrer et unfollow
        for username in following_list:
            if stats['unfollowed'] >= max_unfollow:
                self.logger.info(f"✅ Reached max unfollow limit: {max_unfollow}")
                break
            
            # Vérifier la whitelist
            if username in whitelist:
                self.logger.info(f"⏭️ Skipping @{username} (whitelist)")
                stats['skipped_whitelist'] += 1
                continue
            
            # Vérifier la date de follow (si DB disponible)
            if self.db and min_days_followed > 0:
                try:
                    follow_date = self.db.get_follow_date(username)
                    if follow_date:
                        days_followed = (datetime.now() - follow_date).days
                        if days_followed < min_days_followed:
                            self.logger.info(f"⏭️ Skipping @{username} (followed {days_followed} days ago)")
                            stats['skipped_recent'] += 1
                            continue
                except Exception as e:
                    self.logger.debug(f"⚠️ Could not check follow date for @{username}: {e}")
            
            # Naviguer vers le profil pour vérifier les critères
            if not self.nav.navigate_to_user_profile(username):
                stats['errors'] += 1
                continue
            
            self._random_sleep(0.5, 1.0)
            
            # Vérifier si vérifié (si option activée)
            if skip_verified:
                verified_selectors = [
                    '//android.widget.ImageView[@content-desc="Verified"]',
                    '//android.widget.ImageView[contains(@content-desc, "Verified")]'
                ]
                
                is_verified = False
                for selector in verified_selectors:
                    if self.device.find_element(selector):
                        is_verified = True
                        break
                
                if is_verified:
                    self.logger.info(f"⏭️ Skipping @{username} (verified)")
                    stats['skipped_verified'] += 1
                    continue
            
            # Vérifier si nous suit (si option activée)
            if skip_followers:
                follows_back_selectors = [
                    '//android.widget.Button[@content-desc="Follow Back"]',
                    '//android.widget.Button[contains(@text, "Follow Back")]'
                ]
                
                follows_back = False
                for selector in follows_back_selectors:
                    if self.device.find_element(selector):
                        follows_back = True
                        break
                
                if follows_back:
                    self.logger.info(f"⏭️ Skipping @{username} (follows back)")
                    stats['skipped_followers'] += 1
                    continue
            
            # Unfollow
            if self.unfollow_user(username):
                stats['unfollowed'] += 1
                self.logger.success(f"✅ Progress: {stats['unfollowed']}/{max_unfollow}")
            else:
                stats['errors'] += 1
            
            # Délai entre chaque unfollow
            self._random_sleep(3.0, 7.0)
        
        self.logger.success(f"✅ Intelligent unfollow completed: {stats['unfollowed']} unfollowed")
        return stats
    
    def unfollow_non_followers(self, max_unfollow: int = 50) -> Dict[str, any]:
        """
        Unfollow les comptes qui ne nous suivent pas.
        
        Args:
            max_unfollow: Nombre maximum d'unfollow
            
        Returns:
            Dict: Statistiques de l'opération
        """
        self.logger.info(f"🔄 Unfollowing non-followers (max: {max_unfollow})...")
        
        return self.intelligent_unfollow(
            max_unfollow=max_unfollow,
            skip_verified=True,
            skip_followers=True,  # Ne pas unfollow ceux qui nous suivent
            min_days_followed=3
        )
