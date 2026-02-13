"""Navigation, follow, DM conversation, message sending for the Outreach workflow."""

import time
from typing import Optional

from ....utils.taktik_keyboard import type_with_taktik_keyboard


class OutreachActionsMixin:
    """Mixin: profile navigation, follow, DM open, message send, back to home."""

    def _navigate_to_dm_inbox(self) -> bool:
        """Naviguer vers la boîte de réception DM."""
        try:
            self.logger.debug("Navigating to DM inbox...")
            
            # Méthode 1: Cliquer sur l'onglet DM dans la tab bar
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
            
            self.logger.error("DM tab not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to DM inbox: {e}")
            return False

    def _navigate_to_profile(self, username: str) -> bool:
        """Naviguer vers le profil d'un utilisateur."""
        try:
            self.logger.debug(f"Navigating to profile: @{username}")
            
            # Utiliser la recherche pour trouver le profil
            # Cliquer sur l'onglet recherche
            for selector in self.nav_selectors.search_tab:
                search_tab = self.device.xpath(selector)
                if search_tab.exists:
                    search_tab.click()
                    time.sleep(2)
                    break
            else:
                self.logger.error("Search tab not found")
                return False
            
            # Cliquer sur la barre de recherche
            search_field = self.device(className="android.widget.EditText")
            if search_field.exists(timeout=5):
                search_field.click()
                time.sleep(1)
                # Use Taktik Keyboard for reliable text input
                device_id = getattr(self.device_manager, 'device_id', None) or 'emulator-5554'
                if not type_with_taktik_keyboard(device_id, username):
                    self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                    search_field.set_text(username)
                time.sleep(2)
            else:
                self.logger.error("Search field not found")
                return False
            
            # Cliquer sur le premier résultat (compte)
            # Chercher le compte dans les résultats
            account_result = self.device(textContains=username, className="android.widget.TextView")
            if account_result.exists(timeout=5):
                account_result.click()
                time.sleep(2)
                self.logger.debug(f"✅ Navigated to @{username}")
                return True
            
            self.logger.error(f"Profile @{username} not found in search results")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to profile: {e}")
            return False

    def _follow_user(self) -> bool:
        """Suivre l'utilisateur si pas déjà suivi."""
        try:
            for selector in self.profile_selectors.follow_button:
                follow_btn = self.device.xpath(selector)
                if follow_btn.exists:
                    follow_btn.click()
                    time.sleep(1)
                    self.logger.debug("✅ User followed")
                    return True
            
            self.logger.debug("Follow button not found (might already be following)")
            return False
            
        except Exception as e:
            self.logger.error(f"Error following user: {e}")
            return False

    def _has_existing_conversation(self) -> bool:
        """Vérifier si une conversation existe déjà."""
        # Cette méthode peut être améliorée en vérifiant l'historique des DM
        # Pour l'instant, on retourne False (pas de vérification)
        return False

    def _open_dm_conversation(self) -> bool:
        """Ouvrir la conversation DM depuis le profil."""
        try:
            self.logger.debug("Opening DM conversation...")
            
            # Chercher le bouton Message sur le profil
            for selector in self.profile_selectors.message_button:
                message_btn = self.device.xpath(selector)
                if message_btn.exists:
                    message_btn.click()
                    time.sleep(2)
                    self.logger.debug("✅ DM conversation opened")
                    return True
            
            # Fallback: chercher par texte
            message_btn = self.device(text="Message")
            if message_btn.exists(timeout=3):
                message_btn.click()
                time.sleep(2)
                return True
            
            message_btn = self.device(text="Envoyer un message")
            if message_btn.exists(timeout=3):
                message_btn.click()
                time.sleep(2)
                return True
            
            self.logger.error("Message button not found on profile")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening DM conversation: {e}")
            return False

    def _send_message(self, message: str) -> bool:
        """
        Envoyer le message dans la conversation.
        
        Args:
            message: Texte du message à envoyer
            
        Returns:
            True si envoyé avec succès
        """
        try:
            self.logger.debug(f"Sending message: {message[:50]}...")
            
            # Trouver le champ de saisie avec les nouveaux sélecteurs
            message_input = None
            for selector in self.dm_selectors.message_input:
                msg_input = self.device.xpath(selector)
                if msg_input.exists:
                    message_input = msg_input
                    break
            
            if not message_input:
                # Fallback générique
                message_input = self.device(className="android.widget.EditText")
                if not message_input.exists(timeout=5):
                    self.logger.error("Message input field not found")
                    return False
            
            # Saisir le message
            message_input.click()
            time.sleep(0.5)
            # Use Taktik Keyboard for reliable text input
            device_id = getattr(self.device_manager, 'device_id', None) or 'emulator-5554'
            if not type_with_taktik_keyboard(device_id, message):
                self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                message_input.set_text(message)
            time.sleep(1)
            
            # Envoyer le message avec les nouveaux sélecteurs
            for selector in self.dm_selectors.send_button:
                send_btn = self.device.xpath(selector)
                if send_btn.exists:
                    send_btn.click()
                    time.sleep(1)
                    self.logger.debug("✅ Message sent")
                    return True
            
            # Fallback: chercher par content-desc
            send_btn = self.device(contentDescription="Send")
            if not send_btn.exists(timeout=3):
                send_btn = self.device(contentDescription="Envoyer")
            
            if send_btn.exists(timeout=3):
                send_btn.click()
                time.sleep(1)
                return True
            
            self.logger.error("Send button not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return False

    def _go_back_to_home(self):
        """Retourner à l'écran d'accueil."""
        try:
            # Appuyer sur back plusieurs fois
            for _ in range(3):
                self.device.press("back")
                time.sleep(0.5)
            
            # Cliquer sur l'onglet Home
            for selector in self.nav_selectors.home_tab:
                home_tab = self.device.xpath(selector)
                if home_tab.exists:
                    home_tab.click()
                    break
                    
        except Exception as e:
            self.logger.warning(f"Error going back to home: {e}")
