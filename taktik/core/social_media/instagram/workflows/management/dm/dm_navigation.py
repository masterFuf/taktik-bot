"""DM inbox navigation, thread extraction, and conversation open/close."""

import time
from typing import List, Optional
from datetime import datetime

from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS, NAVIGATION_SELECTORS
from .auto_reply_models import Conversation


class DMNavigationMixin:
    """Mixin: navigate to DM inbox, extract threads, open/close conversations."""

    def _navigate_to_dm_inbox(self) -> bool:
        """Naviguer vers la boîte de réception DM."""
        try:
            self.logger.debug("Navigating to DM inbox...")
            
            # Méthode 1: Cliquer sur l'onglet DM dans la tab bar (resource-id)
            direct_tab = self.device.xpath(self.dm_selectors.direct_tab)
            if direct_tab.exists:
                direct_tab.click()
                time.sleep(2)
                self.logger.debug("✅ Navigated to DM inbox via direct_tab")
                return True
            
            # Méthode 2: Essayer via content-desc
            for selector in self.dm_selectors.direct_tab_content_desc:
                dm_btn = self.device.xpath(selector)
                if dm_btn.exists:
                    dm_btn.click()
                    time.sleep(2)
                    self.logger.debug("✅ Navigated to DM inbox via content-desc")
                    return True
            
            # Méthode 3: Fallback avec uiautomator
            dm_button = self.device(contentDescription="Envoyer un message")
            if not dm_button.exists(timeout=3):
                dm_button = self.device(contentDescription="Direct")
            if not dm_button.exists(timeout=3):
                dm_button = self.device(contentDescription="Messages")
            
            if dm_button.exists(timeout=5):
                dm_button.click()
                time.sleep(2)
                self.logger.debug("✅ Navigated to DM inbox via fallback")
                return True
            
            self.logger.error("DM tab not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to DM inbox: {e}")
            return False

    def _get_unread_conversations(self) -> List[Conversation]:
        """
        Récupérer les conversations avec des messages non lus.
        
        Returns:
            Liste des conversations avec messages non lus
        """
        conversations = []
        
        try:
            self.logger.debug("Checking for unread messages...")
            
            # Naviguer vers les DM
            if not self._navigate_to_dm_inbox():
                return conversations
            
            time.sleep(2)
            
            # Chercher les indicateurs de messages non lus
            # Les conversations non lues ont généralement un point bleu ou un style différent
            thread_list = self.device.xpath(self.dm_selectors.thread_list)
            if not thread_list.exists:
                self.logger.debug("Thread list not found")
                return conversations
            
            # Parcourir les threads visibles avec le nouveau sélecteur
            threads = self.device.xpath(self.dm_selectors.thread_container).all()
            
            for thread in threads[:10]:  # Limiter aux 10 premiers
                try:
                    # Vérifier si non lu via content-desc
                    thread_info = thread.info
                    content_desc = thread_info.get('contentDescription', '')
                    has_unread = 'non lu' in content_desc.lower() or 'unread' in content_desc.lower()
                    
                    # Extraire le username du thread
                    username = self._extract_username_from_thread(thread)
                    if username:
                        conv = Conversation(
                            username=username,
                            has_unread=has_unread,
                            last_activity=datetime.now()
                        )
                        conversations.append(conv)
                        
                except Exception as e:
                    self.logger.debug(f"Error parsing thread: {e}")
                    continue
            
            self.session_stats['messages_checked'] += len(conversations)
            self.logger.debug(f"Found {len(conversations)} conversations to check")
            
        except Exception as e:
            self.logger.error(f"Error getting unread conversations: {e}")
        
        return conversations

    def _extract_username_from_thread(self, thread_element) -> Optional[str]:
        """Extraire le username d'un élément de thread."""
        try:
            # Méthode 1: Chercher via le resource-id spécifique
            username_elem = thread_element.child(
                resourceId=DM_SELECTORS.thread_username_resource_id
            )
            if username_elem.exists:
                username = username_elem.get_text()
                if username:
                    return username.strip()
            
            # Méthode 2: Extraire depuis le content-desc du conteneur
            # Format: "Username, non lu, Message preview, timestamp"
            thread_info = thread_element.info
            content_desc = thread_info.get('contentDescription', '')
            if content_desc:
                # Le username est généralement le premier élément avant la virgule
                parts = content_desc.split(',')
                if parts:
                    username = parts[0].strip()
                    if username and not username.startswith("Active"):
                        return username
            
            # Méthode 3: Fallback - chercher le premier TextView
            text_views = thread_element.child(className="android.widget.TextView")
            if text_views.exists:
                username = text_views.get_text()
                if username and not username.startswith("Active"):
                    return username.strip()
                    
        except Exception as e:
            self.logger.debug(f"Error extracting username: {e}")
        
        return None

    def _open_conversation(self, username: str) -> bool:
        """Ouvrir une conversation spécifique."""
        try:
            # Chercher le thread par username
            thread = self.device(textContains=username)
            if thread.exists(timeout=5):
                thread.click()
                time.sleep(2)
                return True
            
            self.logger.error(f"Conversation with @{username} not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening conversation: {e}")
            return False

    def _go_back_to_inbox(self):
        """
        Retourner à la liste des DM en utilisant le bouton UI Instagram.
        Évite d'utiliser device.press("back") qui peut causer des problèmes.
        """
        try:
            # Méthode 1: Bouton back dans le header (resource-id spécifique)
            back_btn = self.device(resourceId=DM_SELECTORS.conversation_back_button_resource_id)
            if back_btn.exists(timeout=2):
                back_btn.click()
                time.sleep(1)
                self.logger.debug("✅ Retour via header_left_button")
                return True
            
            # Méthode 2: Bouton avec content-desc "Back"
            back_btn = self.device(description="Back")
            if back_btn.exists(timeout=2):
                back_btn.click()
                time.sleep(1)
                self.logger.debug("✅ Retour via description Back")
                return True
            
            # Méthode 3: Bouton avec content-desc "Retour"
            back_btn = self.device(descriptionContains="Retour")
            if back_btn.exists(timeout=2):
                back_btn.click()
                time.sleep(1)
                self.logger.debug("✅ Retour via description Retour")
                return True
            
            # Fallback: utiliser press back si aucun bouton trouvé
            self.logger.warning("Aucun bouton back UI trouvé, utilisation de press back en fallback")
            self.device.press("back")
            time.sleep(1)
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors du retour: {e}")
            self.device.press("back")
            time.sleep(1)
            return False
