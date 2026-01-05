"""
DM Outreach Workflow - Envoi de messages directs en masse.

Ce workflow permet d'envoyer des messages personnalisés à une liste de comptes Instagram.
Utilisations typiques:
- Prospection commerciale
- Outreach influenceurs
- Campagnes marketing
"""
import time
import random
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from loguru import logger

from ...ui.selectors import DM_SELECTORS, NAVIGATION_SELECTORS, PROFILE_SELECTORS
from ...utils.taktik_keyboard import type_with_taktik_keyboard


@dataclass
class DMOutreachConfig:
    """Configuration pour le workflow d'outreach DM."""
    
    # Liste des destinataires (usernames)
    recipients: List[str] = field(default_factory=list)
    
    # Message à envoyer (peut contenir des variables: {username}, {name})
    message_template: str = ""
    
    # Messages alternatifs pour A/B testing
    message_variants: List[str] = field(default_factory=list)
    
    # Délais entre les messages (en secondes)
    delay_min: int = 30
    delay_max: int = 120
    
    # Limite de messages par session
    max_messages_per_session: int = 20
    
    # Pause longue après X messages
    pause_after_messages: int = 10
    pause_duration_min: int = 300  # 5 minutes
    pause_duration_max: int = 600  # 10 minutes
    
    # Vérifier si déjà en conversation avant d'envoyer
    skip_existing_conversations: bool = True
    
    # Suivre avant d'envoyer le message (optionnel)
    follow_before_dm: bool = False


@dataclass
class DMOutreachResult:
    """Résultat d'un envoi de DM."""
    username: str
    success: bool
    message_sent: str = ""
    error: str = ""
    timestamp: str = ""


class DMOutreachWorkflow:
    """
    Workflow pour envoyer des DM en masse à une liste de comptes.
    
    Fonctionnalités:
    - Envoi de messages personnalisés avec variables
    - A/B testing de messages
    - Gestion des délais humains
    - Skip des conversations existantes
    - Suivi optionnel avant DM
    - Logging détaillé des résultats
    """
    
    def __init__(self, device_manager, nav_actions, detection_actions):
        """
        Initialize DM outreach workflow.
        
        Args:
            device_manager: Device manager instance
            nav_actions: Navigation actions instance
            detection_actions: Detection actions instance
        """
        self.device_manager = device_manager
        self.nav_actions = nav_actions
        self.detection_actions = detection_actions
        self.device = device_manager.device
        self.logger = logger
        self.dm_selectors = DM_SELECTORS
        self.nav_selectors = NAVIGATION_SELECTORS
        self.profile_selectors = PROFILE_SELECTORS
        
        # Statistiques de session
        self.session_stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'skipped_existing': 0,
            'follows_performed': 0
        }
        
        # Historique des résultats
        self.results: List[DMOutreachResult] = []
    
    def run(self, config: DMOutreachConfig) -> Dict[str, Any]:
        """
        Exécuter le workflow d'outreach DM.
        
        Args:
            config: Configuration du workflow
            
        Returns:
            Dict avec les statistiques et résultats
        """
        self.logger.info(f"📨 Starting DM Outreach workflow for {len(config.recipients)} recipients")
        
        if not config.recipients:
            self.logger.error("No recipients provided")
            return self._get_final_results("No recipients provided")
        
        if not config.message_template and not config.message_variants:
            self.logger.error("No message template provided")
            return self._get_final_results("No message template provided")
        
        for i, username in enumerate(config.recipients):
            # Vérifier les limites
            if self.session_stats['messages_sent'] >= config.max_messages_per_session:
                self.logger.info(f"🛑 Session limit reached ({config.max_messages_per_session} messages)")
                break
            
            self.logger.info(f"[{i+1}/{len(config.recipients)}] Processing: @{username}")
            
            # Pause longue périodique
            if (self.session_stats['messages_sent'] > 0 and 
                self.session_stats['messages_sent'] % config.pause_after_messages == 0):
                pause_duration = random.randint(config.pause_duration_min, config.pause_duration_max)
                self.logger.info(f"⏸️ Taking a break for {pause_duration}s...")
                time.sleep(pause_duration)
            
            # Envoyer le DM
            result = self._send_dm_to_user(username, config)
            self.results.append(result)
            
            if result.success:
                self.session_stats['messages_sent'] += 1
                self.logger.success(f"✅ Message sent to @{username}")
            else:
                self.session_stats['messages_failed'] += 1
                self.logger.warning(f"❌ Failed to send to @{username}: {result.error}")
            
            # Délai entre les messages
            if i < len(config.recipients) - 1:
                delay = random.randint(config.delay_min, config.delay_max)
                self.logger.debug(f"⏳ Waiting {delay}s before next message...")
                time.sleep(delay)
        
        return self._get_final_results()
    
    def _send_dm_to_user(self, username: str, config: DMOutreachConfig) -> DMOutreachResult:
        """
        Envoyer un DM à un utilisateur spécifique.
        
        Args:
            username: Nom d'utilisateur cible
            config: Configuration du workflow
            
        Returns:
            DMOutreachResult avec le statut
        """
        from datetime import datetime
        
        result = DMOutreachResult(
            username=username,
            success=False,
            timestamp=datetime.now().isoformat()
        )
        
        try:
            # 1. Naviguer vers le profil
            if not self._navigate_to_profile(username):
                result.error = "Failed to navigate to profile"
                return result
            
            time.sleep(2)
            
            # 2. Optionnel: Follow avant DM
            if config.follow_before_dm:
                if self._follow_user():
                    self.session_stats['follows_performed'] += 1
                    time.sleep(random.uniform(1, 3))
            
            # 3. Vérifier conversation existante si configuré
            if config.skip_existing_conversations:
                if self._has_existing_conversation():
                    result.error = "Existing conversation found, skipping"
                    self.session_stats['skipped_existing'] += 1
                    return result
            
            # 4. Ouvrir la conversation DM
            if not self._open_dm_conversation():
                result.error = "Failed to open DM conversation"
                return result
            
            time.sleep(1.5)
            
            # 5. Préparer le message personnalisé
            message = self._prepare_message(username, config)
            result.message_sent = message
            
            # 6. Envoyer le message
            if not self._send_message(message):
                result.error = "Failed to send message"
                return result
            
            result.success = True
            
            # 7. Retourner à l'écran principal
            self._go_back_to_home()
            
        except Exception as e:
            result.error = f"Exception: {str(e)}"
            self.logger.error(f"Error sending DM to @{username}: {e}")
        
        return result
    
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
    
    def _prepare_message(self, username: str, config: DMOutreachConfig) -> str:
        """
        Préparer le message personnalisé.
        
        Args:
            username: Nom d'utilisateur pour personnalisation
            config: Configuration avec templates
            
        Returns:
            Message formaté
        """
        # Choisir le template (A/B testing si variants disponibles)
        if config.message_variants:
            template = random.choice(config.message_variants)
        else:
            template = config.message_template
        
        # Remplacer les variables
        message = template.replace("{username}", username)
        message = message.replace("{name}", username)  # Fallback si pas de nom
        
        return message
    
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
    
    def _get_final_results(self, error: str = "") -> Dict[str, Any]:
        """
        Compiler les résultats finaux du workflow.
        
        Args:
            error: Message d'erreur optionnel
            
        Returns:
            Dict avec toutes les statistiques
        """
        return {
            'success': error == "",
            'error': error,
            'stats': self.session_stats,
            'results': [
                {
                    'username': r.username,
                    'success': r.success,
                    'message': r.message_sent[:50] + "..." if len(r.message_sent) > 50 else r.message_sent,
                    'error': r.error,
                    'timestamp': r.timestamp
                }
                for r in self.results
            ],
            'summary': {
                'total_recipients': len(self.results),
                'successful': self.session_stats['messages_sent'],
                'failed': self.session_stats['messages_failed'],
                'skipped': self.session_stats['skipped_existing'],
                'follows': self.session_stats['follows_performed']
            }
        }
    
    def get_session_stats(self) -> Dict[str, int]:
        """Retourner les statistiques de session."""
        return self.session_stats.copy()
