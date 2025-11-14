"""
Actions atomiques pour la gestion des messages directs (DM) Instagram.
"""
from typing import Optional, List, Dict
from loguru import logger
from taktik.core.social_media.instagram.actions.core.base_action import BaseAction
from taktik.core.social_media.instagram.ui.selectors import (
    NAVIGATION_SELECTORS,
    BUTTON_SELECTORS,
    TEXT_INPUT_SELECTORS
)


class DMActions(BaseAction):
    """Actions atomiques pour les messages directs Instagram."""
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-dm-atomic")
        self.nav_selectors = NAVIGATION_SELECTORS
        self.button_selectors = BUTTON_SELECTORS
        self.text_selectors = TEXT_INPUT_SELECTORS
    
    def open_dm_inbox(self) -> bool:
        """
        Ouvrir la boîte de réception des messages directs.
        
        Returns:
            bool: True si succès, False sinon
        """
        self.logger.info("📬 Opening DM inbox...")
        
        # Sélecteurs pour le bouton DM (icône messenger)
        dm_button_selectors = [
            '//android.widget.Button[@content-desc="Direct"]',
            '//android.widget.Button[contains(@content-desc, "Direct")]',
            '//android.widget.ImageView[@content-desc="Direct"]',
            '//android.view.ViewGroup[contains(@content-desc, "Direct")]',
            # Fallback par position (en haut à droite)
            '(//android.widget.ImageView[@clickable="true"])[2]'
        ]
        
        for selector in dm_button_selectors:
            if self._find_and_click(selector, "DM inbox button"):
                self._human_like_delay()
                self.logger.success("✅ DM inbox opened")
                return True
        
        self.logger.error("❌ Failed to open DM inbox")
        return False
    
    def search_user_in_dm(self, username: str) -> bool:
        """
        Rechercher un utilisateur dans les DM.
        
        Args:
            username: Nom d'utilisateur à rechercher
            
        Returns:
            bool: True si succès, False sinon
        """
        self.logger.info(f"🔍 Searching for user in DM: @{username}")
        
        # Cliquer sur le bouton "New message" / "Nouveau message"
        new_message_selectors = [
            '//android.widget.ImageView[@content-desc="New message"]',
            '//android.widget.ImageView[contains(@content-desc, "Nouveau message")]',
            '//android.widget.Button[@content-desc="New message"]',
            '//android.widget.ImageView[@clickable="true" and contains(@bounds, ",0]")]'
        ]
        
        clicked = False
        for selector in new_message_selectors:
            if self._find_and_click(selector, "New message button"):
                clicked = True
                break
        
        if not clicked:
            self.logger.error("❌ Failed to click new message button")
            return False
        
        self._human_like_delay()
        
        # Chercher le champ de recherche
        search_field_selectors = [
            '//android.widget.EditText[@content-desc="Search"]',
            '//android.widget.EditText[contains(@content-desc, "Rechercher")]',
            '//android.widget.EditText[@text="Search..."]',
            '//android.widget.EditText[@clickable="true"]'
        ]
        
        for selector in search_field_selectors:
            element = self.device.find_element(selector)
            if element:
                element.click()
                self._random_sleep(0.3, 0.7)
                
                # Taper le nom d'utilisateur
                element.set_text(username)
                self._human_like_delay()
                
                self.logger.success(f"✅ Searched for @{username}")
                return True
        
        self.logger.error("❌ Failed to find search field")
        return False
    
    def select_user_from_search(self, username: str) -> bool:
        """
        Sélectionner un utilisateur dans les résultats de recherche.
        
        Args:
            username: Nom d'utilisateur à sélectionner
            
        Returns:
            bool: True si succès, False sinon
        """
        self.logger.info(f"👆 Selecting user from search: @{username}")
        
        # Attendre que les résultats apparaissent
        self._random_sleep(1.0, 2.0)
        
        # Sélecteurs pour le premier résultat
        user_result_selectors = [
            f'//android.widget.TextView[@text="{username}"]',
            f'//android.widget.TextView[contains(@text, "{username}")]',
            '(//android.widget.TextView[@clickable="true"])[1]',
            '(//android.view.ViewGroup[@clickable="true"])[1]'
        ]
        
        for selector in user_result_selectors:
            if self._find_and_click(selector, f"User @{username}"):
                self._human_like_delay()
                self.logger.success(f"✅ Selected @{username}")
                return True
        
        self.logger.error(f"❌ Failed to select @{username}")
        return False
    
    def send_message(self, message: str) -> bool:
        """
        Envoyer un message dans la conversation active.
        
        Args:
            message: Texte du message à envoyer
            
        Returns:
            bool: True si succès, False sinon
        """
        self.logger.info(f"💬 Sending message: {message[:50]}...")
        
        # Trouver le champ de saisie du message
        message_field_selectors = [
            '//android.widget.EditText[@content-desc="Message"]',
            '//android.widget.EditText[contains(@content-desc, "Message")]',
            '//android.widget.EditText[@text="Message..."]',
            '//android.widget.EditText[@clickable="true"]'
        ]
        
        for selector in message_field_selectors:
            element = self.device.find_element(selector)
            if element:
                element.click()
                self._random_sleep(0.3, 0.7)
                
                # Taper le message
                element.set_text(message)
                self._human_like_delay()
                
                # Cliquer sur le bouton d'envoi
                send_button_selectors = [
                    '//android.widget.ImageView[@content-desc="Send"]',
                    '//android.widget.Button[@content-desc="Send"]',
                    '//android.widget.ImageView[contains(@content-desc, "Envoyer")]',
                    '//android.widget.Button[@clickable="true" and @enabled="true"]'
                ]
                
                for send_selector in send_button_selectors:
                    if self._find_and_click(send_selector, "Send button"):
                        self._human_like_delay()
                        self.logger.success(f"✅ Message sent: {message[:50]}...")
                        return True
                
                self.logger.error("❌ Failed to click send button")
                return False
        
        self.logger.error("❌ Failed to find message field")
        return False
    
    def send_dm_to_user(self, username: str, message: str) -> bool:
        """
        Envoyer un DM à un utilisateur (workflow complet).
        
        Args:
            username: Nom d'utilisateur
            message: Message à envoyer
            
        Returns:
            bool: True si succès, False sinon
        """
        self.logger.info(f"📤 Sending DM to @{username}")
        
        # 1. Ouvrir la boîte DM
        if not self.open_dm_inbox():
            return False
        
        # 2. Rechercher l'utilisateur
        if not self.search_user_in_dm(username):
            return False
        
        # 3. Sélectionner l'utilisateur
        if not self.select_user_from_search(username):
            return False
        
        # 4. Envoyer le message
        if not self.send_message(message):
            return False
        
        self.logger.success(f"✅ DM sent to @{username}")
        return True
    
    def get_unread_conversations(self) -> List[Dict[str, str]]:
        """
        Récupérer la liste des conversations non lues.
        
        Returns:
            List[Dict]: Liste des conversations avec username et preview
        """
        self.logger.info("📋 Getting unread conversations...")
        
        conversations = []
        
        # Ouvrir la boîte DM
        if not self.open_dm_inbox():
            return conversations
        
        # Chercher les conversations non lues (avec badge bleu)
        unread_selectors = [
            '//android.view.ViewGroup[contains(@content-desc, "unread")]',
            '//android.widget.TextView[@text and @clickable="true"]'
        ]
        
        # TODO: Implémenter la logique de parsing des conversations
        # Pour l'instant, retourne une liste vide
        
        self.logger.info(f"📊 Found {len(conversations)} unread conversations")
        return conversations
    
    def reply_to_conversation(self, conversation_index: int, message: str) -> bool:
        """
        Répondre à une conversation par son index.
        
        Args:
            conversation_index: Index de la conversation (0-based)
            message: Message à envoyer
            
        Returns:
            bool: True si succès, False sinon
        """
        self.logger.info(f"💬 Replying to conversation #{conversation_index}")
        
        # Ouvrir la boîte DM
        if not self.open_dm_inbox():
            return False
        
        # Cliquer sur la conversation
        conversation_selector = f'(//android.view.ViewGroup[@clickable="true"])[{conversation_index + 1}]'
        
        if not self._find_and_click(conversation_selector, f"Conversation #{conversation_index}"):
            self.logger.error(f"❌ Failed to open conversation #{conversation_index}")
            return False
        
        self._human_like_delay()
        
        # Envoyer le message
        return self.send_message(message)
    
    def go_back_from_dm(self) -> bool:
        """
        Retourner en arrière depuis les DM.
        
        Returns:
            bool: True si succès, False sinon
        """
        self.logger.info("⬅️ Going back from DM...")
        
        back_button_selectors = [
            '//android.widget.ImageView[@content-desc="Back"]',
            '//android.widget.Button[@content-desc="Back"]',
            '//android.widget.ImageView[contains(@content-desc, "Retour")]'
        ]
        
        for selector in back_button_selectors:
            if self._find_and_click(selector, "Back button"):
                self._human_like_delay()
                self.logger.success("✅ Went back")
                return True
        
        self.logger.error("❌ Failed to go back")
        return False
