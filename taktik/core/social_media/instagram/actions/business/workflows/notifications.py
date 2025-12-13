"""Business logic for Instagram notifications interactions.

Ce workflow permet d'interagir avec les utilisateurs depuis l'onglet Activité/Notifications.
Utilisations typiques:
- Interagir avec les personnes qui ont liké vos posts
- Interagir avec les nouveaux followers
- Interagir avec les personnes qui ont commenté
"""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ...core.base_business_action import BaseBusinessAction
from ..common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service


class NotificationsBusiness(BaseBusinessAction):
    """Business logic for interacting with users from notifications/activity tab."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "notifications", init_business_modules=True)
        
        self.default_config = {
            'max_interactions': 20,
            'interaction_delay_range': (20, 40),
            'like_percentage': 70,
            'follow_percentage': 15,
            'comment_percentage': 5,
            'story_watch_percentage': 10,
            'max_likes_per_profile': 3,
            'notification_types': ['likes', 'follows', 'comments']  # Types to process
        }
        
        # Sélecteurs spécifiques aux notifications
        self._notification_selectors = {
            'activity_tab': [
                '//*[contains(@content-desc, "Activité")]',
                '//*[contains(@content-desc, "Activity")]',
                '//*[contains(@content-desc, "Notifications")]'
            ],
            'notification_item': [
                '//*[@resource-id="com.instagram.android:id/row_news_text"]',
                '//*[@resource-id="com.instagram.android:id/row_news_container"]',
                '//android.widget.LinearLayout[contains(@resource-id, "news")]'
            ],
            'notification_username': [
                '//*[@resource-id="com.instagram.android:id/row_news_text"]//android.widget.TextView[1]',
                '//android.widget.TextView[contains(@text, "@")]'
            ],
            'notification_action_text': [
                '//*[@resource-id="com.instagram.android:id/row_news_text"]',
                '//android.widget.TextView[contains(@text, "liked") or contains(@text, "aimé")]',
                '//android.widget.TextView[contains(@text, "started following") or contains(@text, "a commencé")]',
                '//android.widget.TextView[contains(@text, "commented") or contains(@text, "commenté")]'
            ],
            'follow_requests_section': [
                '//*[contains(@text, "Follow requests")]',
                '//*[contains(@text, "Demandes d\'abonnement")]'
            ]
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
    
    def _navigate_to_activity_tab(self) -> bool:
        """Naviguer vers l'onglet Activité/Notifications."""
        try:
            self.logger.debug("🔔 Navigating to activity tab")
            
            for selector in self._notification_selectors['activity_tab']:
                if self._find_and_click(selector, timeout=3):
                    self._human_like_delay('navigation')
                    time.sleep(2)
                    
                    # Vérifier qu'on est bien sur l'onglet activité
                    if self._is_on_activity_screen():
                        self.logger.debug("✅ Successfully navigated to activity tab")
                        return True
            
            # Fallback: utiliser les sélecteurs de navigation
            if self._find_and_click(self.navigation_selectors.activity_tab, timeout=5):
                self._human_like_delay('navigation')
                time.sleep(2)
                return self._is_on_activity_screen()
            
            self.logger.error("Cannot navigate to activity tab")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to activity tab: {e}")
            return False
    
    def _is_on_activity_screen(self) -> bool:
        """Vérifier si on est sur l'écran d'activité."""
        indicators = [
            '//*[contains(@text, "Activité")]',
            '//*[contains(@text, "Activity")]',
            '//*[contains(@resource-id, "news")]',
            '//*[contains(@resource-id, "activity")]'
        ]
        return self._is_element_present(indicators)
    
    def _extract_users_from_notifications(self, max_users: int = 50, 
                                          notification_types: List[str] = None) -> List[str]:
        """
        Extraire les usernames depuis les notifications.
        
        Args:
            max_users: Nombre max d'utilisateurs à extraire
            notification_types: Types de notifications à traiter
            
        Returns:
            Liste de usernames
        """
        users = []
        seen_users = set()
        scroll_attempts = 0
        max_scroll_attempts = 10
        
        notification_types = notification_types or ['likes', 'follows', 'comments']
        
        self.logger.info(f"📋 Extracting users from notifications (types: {notification_types})")
        
        while len(users) < max_users and scroll_attempts < max_scroll_attempts:
            # Extraire les notifications visibles
            new_users = self._get_visible_notification_users(notification_types)
            
            for username in new_users:
                if username not in seen_users and len(users) < max_users:
                    seen_users.add(username)
                    users.append(username)
                    self.logger.debug(f"Found user: @{username}")
            
            if len(users) >= max_users:
                break
            
            # Scroll pour voir plus de notifications
            previous_count = len(users)
            self.scroll_actions.scroll_down()
            time.sleep(1.5)
            scroll_attempts += 1
            
            # Si pas de nouveaux utilisateurs après scroll, on arrête
            if len(users) == previous_count:
                self.logger.debug("No new users found after scroll")
                break
        
        self.logger.info(f"✅ Extracted {len(users)} users from notifications")
        return users
    
    def _get_visible_notification_users(self, notification_types: List[str]) -> List[str]:
        """Récupérer les usernames des notifications visibles."""
        users = []
        
        try:
            # Chercher les éléments de notification
            for selector in self._notification_selectors['notification_item']:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        try:
                            # Extraire le texte de la notification
                            text = element.get_text() or ''
                            content_desc = element.attrib.get('content-desc', '')
                            
                            full_text = f"{text} {content_desc}".lower()
                            
                            # Filtrer par type de notification
                            should_process = False
                            if 'likes' in notification_types and ('liked' in full_text or 'aimé' in full_text):
                                should_process = True
                            if 'follows' in notification_types and ('following' in full_text or 'abonné' in full_text or 'started' in full_text):
                                should_process = True
                            if 'comments' in notification_types and ('commented' in full_text or 'commenté' in full_text):
                                should_process = True
                            
                            if should_process:
                                # Extraire le username (généralement le premier mot ou avant "liked/commented")
                                username = self._extract_username_from_notification_text(text or content_desc)
                                if username and self._is_valid_username(username):
                                    users.append(username)
                        except Exception:
                            continue
                    break
        except Exception as e:
            self.logger.debug(f"Error extracting notification users: {e}")
        
        return users
    
    def _extract_username_from_notification_text(self, text: str) -> Optional[str]:
        """Extraire le username depuis le texte d'une notification."""
        if not text:
            return None
        
        # Le username est généralement le premier mot (avant "liked", "commented", etc.)
        words = text.split()
        if words:
            username = words[0].strip()
            # Nettoyer le username
            username = username.replace('@', '').replace(',', '').strip()
            if self._is_valid_username(username):
                return username
        
        return None
    
    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """
        Interagir avec un utilisateur.
        Réutilise la logique existante de BaseBusinessAction.
        """
        try:
            # Naviguer vers le profil
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.warning(f"Cannot navigate to @{username}")
                return None
            
            time.sleep(2)
            
            # Vérifier les filtres
            if hasattr(self, 'filtering_business'):
                filter_result = self.filtering_business.should_interact_with_profile(config.get('filter_criteria', {}))
                if not filter_result.get('should_interact', True):
                    self.logger.info(f"Profile @{username} filtered: {filter_result.get('reason', 'unknown')}")
                    self._record_filtered_profile(username, filter_result.get('reason', 'filtered'), config.get('source', 'notifications'))
                    return None
            
            result = {
                'likes': 0,
                'follows': 0,
                'comments': 0,
                'stories': 0,
                'stories_liked': 0
            }
            
            # Like posts
            if random.randint(1, 100) <= config.get('like_percentage', 70):
                likes = self._like_user_posts(username, config.get('max_likes_per_profile', 3))
                result['likes'] = likes
            
            # Follow
            if random.randint(1, 100) <= config.get('follow_percentage', 15):
                if self._follow_user(username):
                    result['follows'] = 1
            
            # Watch stories
            if random.randint(1, 100) <= config.get('story_watch_percentage', 10):
                stories_result = self._watch_user_stories(username, config)
                result['stories'] = stories_result.get('watched', 0)
                result['stories_liked'] = stories_result.get('liked', 0)
            
            # Enregistrer l'interaction
            self._record_interaction(username, result, config.get('source', 'notifications'))
            
            # Retourner à l'onglet activité pour continuer
            self._navigate_to_activity_tab()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error interacting with @{username}: {e}")
            return None
    
    def _like_user_posts(self, username: str, max_likes: int) -> int:
        """Liker les posts d'un utilisateur."""
        likes = 0
        try:
            if hasattr(self, 'like_business'):
                likes = self.like_business.like_posts_on_profile(max_likes=max_likes)
                if likes > 0:
                    self._record_action(username, 'LIKE', likes)
        except Exception as e:
            self.logger.debug(f"Error liking posts: {e}")
        return likes
    
    def _follow_user(self, username: str) -> bool:
        """Suivre un utilisateur."""
        try:
            for selector in self.profile_selectors.follow_button:
                if self._find_and_click(selector, timeout=2):
                    self._human_like_delay('click')
                    self._record_action(username, 'FOLLOW', 1)
                    self.logger.info(f"✅ Followed @{username}")
                    return True
        except Exception as e:
            self.logger.debug(f"Error following user: {e}")
        return False
    
    def _watch_user_stories(self, username: str, config: Dict[str, Any]) -> Dict[str, int]:
        """Regarder les stories d'un utilisateur."""
        result = {'watched': 0, 'liked': 0}
        try:
            if hasattr(self, 'content_business'):
                stories_result = self.content_business.watch_stories(
                    like_probability=config.get('story_like_percentage', 5)
                )
                result['watched'] = stories_result.get('watched', 0)
                result['liked'] = stories_result.get('liked', 0)
                
                if result['watched'] > 0:
                    self._record_action(username, 'STORY_WATCH', result['watched'])
                if result['liked'] > 0:
                    self._record_action(username, 'STORY_LIKE', result['liked'])
        except Exception as e:
            self.logger.debug(f"Error watching stories: {e}")
        return result
    
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
    
    def _record_interaction(self, username: str, result: Dict[str, int], source: str):
        """Enregistrer une interaction complète."""
        try:
            account_id = self._get_account_id()
            session_id = self._get_session_id()
            
            DatabaseHelpers.record_profile_interaction(
                username=username,
                source_type='NOTIFICATIONS',
                source_name=source,
                likes=result.get('likes', 0),
                follows=result.get('follows', 0),
                comments=result.get('comments', 0),
                stories_watched=result.get('stories', 0),
                stories_liked=result.get('stories_liked', 0),
                account_id=account_id,
                session_id=session_id
            )
        except Exception as e:
            self.logger.debug(f"Error recording interaction: {e}")
