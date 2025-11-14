"""
Action business pour l'envoi de DM en masse Instagram.
"""
from typing import Optional, List, Dict
import random
from loguru import logger
from taktik.core.social_media.instagram.actions.core.base_action import BaseAction
from taktik.core.social_media.instagram.actions.atomic.dm_actions import DMActions
from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
from taktik.core.database.api_database_service import APIBasedDatabaseService


class MassDMAction(BaseAction):
    """Action business pour l'envoi de DM en masse."""
    
    def __init__(self, device, db_service: Optional[APIBasedDatabaseService] = None):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-mass-dm-business")
        self.dm = DMActions(device)
        self.nav = NavigationActions(device)
        self.db = db_service
    
    def send_mass_dm(
        self,
        usernames: List[str],
        message_template: str,
        max_dm: int = 20,
        personalize: bool = True,
        delay_range: tuple = (5, 15)
    ) -> Dict[str, any]:
        """
        Envoyer des DM en masse à une liste d'utilisateurs.
        
        Args:
            usernames: Liste des noms d'utilisateur
            message_template: Template du message (peut contenir {username})
            max_dm: Nombre maximum de DM à envoyer
            personalize: Personnaliser le message avec le username
            delay_range: Délai entre chaque DM (min, max) en secondes
            
        Returns:
            Dict: Statistiques de l'opération
        """
        self.logger.info(f"📤 Starting mass DM (max: {max_dm})...")
        
        stats = {
            'total_targets': len(usernames),
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for i, username in enumerate(usernames[:max_dm], 1):
            self.logger.info(f"📨 Sending DM {i}/{min(max_dm, len(usernames))} to @{username}")
            
            # Personnaliser le message
            if personalize and '{username}' in message_template:
                message = message_template.format(username=username)
            else:
                message = message_template
            
            # Vérifier si déjà envoyé (si DB disponible)
            if self.db:
                try:
                    if self.db.has_sent_dm(username):
                        self.logger.info(f"⏭️ Skipping @{username} (already sent)")
                        stats['skipped'] += 1
                        continue
                except Exception as e:
                    self.logger.debug(f"⚠️ Could not check DM history: {e}")
            
            # Envoyer le DM
            success = self.dm.send_dm_to_user(username, message)
            
            if success:
                stats['sent'] += 1
                self.logger.success(f"✅ DM sent to @{username} ({stats['sent']}/{max_dm})")
                
                # Enregistrer dans la base de données
                if self.db:
                    try:
                        self.db.log_action(
                            action_type='dm_sent',
                            target_username=username,
                            success=True,
                            metadata={'message': message[:100]}
                        )
                    except Exception as e:
                        self.logger.warning(f"⚠️ Failed to log DM: {e}")
            else:
                stats['failed'] += 1
                self.logger.error(f"❌ Failed to send DM to @{username}")
                
                if self.db:
                    try:
                        self.db.log_action(
                            action_type='dm_sent',
                            target_username=username,
                            success=False
                        )
                    except Exception as e:
                        self.logger.warning(f"⚠️ Failed to log failed DM: {e}")
            
            # Retourner à l'inbox pour le prochain DM
            self.dm.go_back_from_dm()
            self._random_sleep(0.5, 1.0)
            
            # Délai humain entre chaque DM
            if i < min(max_dm, len(usernames)):
                delay = random.uniform(delay_range[0], delay_range[1])
                self.logger.info(f"⏳ Waiting {delay:.1f}s before next DM...")
                self._random_sleep(delay, delay + 1)
        
        self.logger.success(
            f"✅ Mass DM completed: {stats['sent']} sent, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )
        return stats
    
    def send_dm_to_followers(
        self,
        message_template: str,
        max_dm: int = 20,
        min_followers: int = 0,
        max_followers: int = 999999,
        personalize: bool = True
    ) -> Dict[str, any]:
        """
        Envoyer des DM à ses propres followers.
        
        Args:
            message_template: Template du message
            max_dm: Nombre maximum de DM
            min_followers: Nombre minimum de followers du compte cible
            max_followers: Nombre maximum de followers du compte cible
            personalize: Personnaliser le message
            
        Returns:
            Dict: Statistiques de l'opération
        """
        self.logger.info(f"📤 Sending DM to followers (max: {max_dm})...")
        
        # Naviguer vers notre profil
        if not self.nav.navigate_to_profile_tab():
            self.logger.error("❌ Failed to navigate to profile")
            return {'sent': 0, 'failed': 0, 'skipped': 0}
        
        # Cliquer sur "Followers"
        followers_selectors = [
            '//android.widget.Button[contains(@content-desc, "followers")]',
            '//android.widget.Button[contains(@text, "followers")]',
            '//android.widget.TextView[@text="followers"]/..',
        ]
        
        if not self._find_and_click(followers_selectors):
            self.logger.error("❌ Failed to click followers button")
            return {'sent': 0, 'failed': 0, 'skipped': 0}
        
        self._human_like_delay()
        
        # Récupérer les usernames des followers
        followers = []
        scroll_attempts = 0
        max_scroll_attempts = 20
        
        while len(followers) < max_dm * 2 and scroll_attempts < max_scroll_attempts:
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
                        if username and username not in followers and not username.startswith('Follow'):
                            followers.append(username)
                            self.logger.debug(f"➕ Found follower: @{username}")
                except Exception:
                    continue
            
            # Scroller
            from taktik.core.social_media.instagram.actions.atomic.scroll_actions import ScrollActions
            scroll = ScrollActions(self.device)
            scroll.scroll_down()
            self._random_sleep(0.5, 1.0)
            scroll_attempts += 1
        
        self.logger.info(f"📋 Found {len(followers)} followers")
        
        # Retourner en arrière
        self.nav.go_back()
        self._human_like_delay()
        
        # Envoyer les DM
        return self.send_mass_dm(
            usernames=followers[:max_dm],
            message_template=message_template,
            max_dm=max_dm,
            personalize=personalize
        )
    
    def send_dm_to_hashtag_users(
        self,
        hashtag: str,
        message_template: str,
        max_dm: int = 20,
        personalize: bool = True
    ) -> Dict[str, any]:
        """
        Envoyer des DM aux utilisateurs d'un hashtag.
        
        Args:
            hashtag: Hashtag à cibler (sans #)
            message_template: Template du message
            max_dm: Nombre maximum de DM
            personalize: Personnaliser le message
            
        Returns:
            Dict: Statistiques de l'opération
        """
        self.logger.info(f"📤 Sending DM to #{hashtag} users (max: {max_dm})...")
        
        # Rechercher le hashtag
        if not self.nav.search_hashtag(hashtag):
            self.logger.error(f"❌ Failed to search hashtag #{hashtag}")
            return {'sent': 0, 'failed': 0, 'skipped': 0}
        
        self._human_like_delay()
        
        # Récupérer les usernames des posts récents
        usernames = []
        scroll_attempts = 0
        max_scroll_attempts = 10
        
        while len(usernames) < max_dm * 2 and scroll_attempts < max_scroll_attempts:
            # Chercher les usernames dans les posts
            username_selectors = [
                '//android.widget.TextView[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
                '//android.widget.TextView[contains(@resource-id, "profile_name")]'
            ]
            
            for selector in username_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    for element in elements:
                        username = element.text
                        if username and username not in usernames and not username.startswith('Follow'):
                            usernames.append(username)
                            self.logger.debug(f"➕ Found user from #{hashtag}: @{username}")
                except Exception:
                    continue
            
            # Scroller
            from taktik.core.social_media.instagram.actions.atomic.scroll_actions import ScrollActions
            scroll = ScrollActions(self.device)
            scroll.scroll_down()
            self._random_sleep(0.5, 1.0)
            scroll_attempts += 1
        
        self.logger.info(f"📋 Found {len(usernames)} users from #{hashtag}")
        
        # Retourner en arrière
        self.nav.go_back()
        self._human_like_delay()
        
        # Envoyer les DM
        return self.send_mass_dm(
            usernames=usernames[:max_dm],
            message_template=message_template,
            max_dm=max_dm,
            personalize=personalize
        )
