"""
DM Outreach Workflow - Envoi de messages directs en masse.

Internal structure (SRP split):
- outreach_models.py  — Dataclasses (DMOutreachConfig, DMOutreachResult)
- outreach_actions.py  — Navigation, follow, DM conversation, message sending
- outreach_workflow.py — Orchestrator (this file)
"""
import time
import random
from typing import Dict, List, Any
from datetime import datetime
from loguru import logger

from ....ui.selectors import DM_SELECTORS, NAVIGATION_SELECTORS, PROFILE_SELECTORS

# Re-export models for backward compatibility
from .outreach_models import DMOutreachConfig, DMOutreachResult
from .outreach_actions import OutreachActionsMixin


class DMOutreachWorkflow(OutreachActionsMixin):
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
