"""Notification extraction: navigate to activity tab, extract users from notifications."""

import time
from typing import Dict, List, Any, Optional


class NotificationExtractionMixin:
    """Mixin: navigate to activity tab + extract usernames from notifications."""

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
        return self._is_element_present(self._notif_sel.activity_screen_indicators)
    
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
