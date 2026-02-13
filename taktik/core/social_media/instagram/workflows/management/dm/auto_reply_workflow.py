"""
DM Auto Reply Workflow - Réponse automatique aux messages directs via LLM.

Internal structure (SRP split):
- auto_reply_models.py — Dataclasses (DMAutoReplyConfig, Conversation, etc.)
- dm_navigation.py     — DM inbox navigation, thread extraction, open/close
- llm_integration.py   — LLM context building, API call, response cleaning
- reply_actions.py     — Send reply, read messages, history, results
- auto_reply_workflow.py — Orchestrator (this file)
"""

import time
import random
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger

from ....ui.selectors import DM_SELECTORS, NAVIGATION_SELECTORS

# Re-export models for backward compatibility
from .auto_reply_models import (
    DMAutoReplyConfig, ConversationMessage, Conversation, AutoReplyResult
)
from .dm_navigation import DMNavigationMixin
from .llm_integration import DMLLMIntegrationMixin
from .reply_actions import DMReplyActionsMixin


class DMAutoReplyWorkflow(
    DMNavigationMixin,
    DMLLMIntegrationMixin,
    DMReplyActionsMixin
):
    """
    Workflow pour répondre automatiquement aux DM via LLM.
    
    Utilise fal.ai pour générer des réponses contextuelles et naturelles.
    """
    
    FAL_API_URL = "https://fal.run/fal-ai/lora"  # URL de base fal.ai
    
    def __init__(self, device_manager, nav_actions, detection_actions):
        """
        Initialize DM auto reply workflow.
        
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
        
        # État de la session
        self.is_running = False
        self.session_start: Optional[datetime] = None
        
        # Statistiques
        self.session_stats = {
            'messages_checked': 0,
            'replies_sent': 0,
            'replies_failed': 0,
            'messages_ignored': 0,
            'llm_calls': 0,
            'total_llm_latency_ms': 0
        }
        
        # Historique des conversations pour contexte
        self.conversation_history: Dict[str, List[ConversationMessage]] = {}
        
        # Résultats
        self.results: List[AutoReplyResult] = []
    
    async def run_async(self, config: DMAutoReplyConfig) -> Dict[str, Any]:
        """
        Exécuter le workflow de réponse automatique (version async).
        
        Args:
            config: Configuration du workflow
            
        Returns:
            Dict avec les statistiques et résultats
        """
        self.logger.info("🤖 Starting DM Auto Reply workflow")
        
        if not config.fal_api_key:
            self.logger.error("fal.ai API key is required")
            return self._get_final_results("fal.ai API key is required")
        
        self.is_running = True
        self.session_start = datetime.now()
        
        try:
            while self.is_running:
                # Vérifier les limites de session
                if not self._check_session_limits(config):
                    break
                
                # Vérifier les nouveaux messages
                unread_conversations = self._get_unread_conversations()
                
                for conv in unread_conversations:
                    if not self.is_running:
                        break
                    
                    # Filtrer les conversations à ignorer
                    if self._should_ignore_conversation(conv, config):
                        self.session_stats['messages_ignored'] += 1
                        continue
                    
                    # Traiter la conversation
                    result = await self._process_conversation(conv, config)
                    self.results.append(result)
                    
                    if result.success:
                        self.session_stats['replies_sent'] += 1
                    else:
                        self.session_stats['replies_failed'] += 1
                
                # Attendre avant la prochaine vérification
                wait_time = random.randint(config.check_interval_min, config.check_interval_max)
                self.logger.debug(f"⏳ Next check in {wait_time}s...")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            self.logger.error(f"Error in auto reply workflow: {e}")
            return self._get_final_results(f"Error: {str(e)}")
        
        return self._get_final_results()
    
    def run(self, config: DMAutoReplyConfig) -> Dict[str, Any]:
        """
        Exécuter le workflow de réponse automatique (version sync).
        
        Args:
            config: Configuration du workflow
            
        Returns:
            Dict avec les statistiques et résultats
        """
        return asyncio.run(self.run_async(config))
    
    def stop(self):
        """Arrêter le workflow."""
        self.logger.info("🛑 Stopping DM Auto Reply workflow...")
        self.is_running = False
    
    def _check_session_limits(self, config: DMAutoReplyConfig) -> bool:
        """Vérifier si la session peut continuer."""
        # Limite de réponses
        if self.session_stats['replies_sent'] >= config.max_replies_per_session:
            self.logger.info(f"🛑 Reply limit reached ({config.max_replies_per_session})")
            return False
        
        # Limite de durée
        if self.session_start:
            elapsed = (datetime.now() - self.session_start).total_seconds() / 60
            if elapsed >= config.session_duration_minutes:
                self.logger.info(f"🛑 Session duration limit reached ({config.session_duration_minutes} min)")
                return False
        
        return True
    
    def _should_ignore_conversation(self, conv: Conversation, config: DMAutoReplyConfig) -> bool:
        """Vérifier si une conversation doit être ignorée."""
        # Ignorer certains usernames
        if conv.username in config.ignore_usernames:
            self.logger.debug(f"Ignoring @{conv.username} (in ignore list)")
            return True
        
        return False
    
    async def _process_conversation(
        self, 
        conv: Conversation, 
        config: DMAutoReplyConfig
    ) -> AutoReplyResult:
        """
        Traiter une conversation et envoyer une réponse.
        
        Args:
            conv: Conversation à traiter
            config: Configuration
            
        Returns:
            AutoReplyResult
        """
        result = AutoReplyResult(
            username=conv.username,
            incoming_message="",
            reply_sent="",
            success=False,
            timestamp=datetime.now().isoformat()
        )
        
        try:
            # 1. Ouvrir la conversation
            if not self._open_conversation(conv.username):
                result.error = "Failed to open conversation"
                return result
            
            time.sleep(1.5)
            
            # 2. Lire le dernier message
            last_message = self._get_last_incoming_message()
            if not last_message:
                result.error = "No incoming message found"
                return result
            
            result.incoming_message = last_message
            
            # 3. Vérifier les filtres de mots-clés
            if not self._message_matches_filters(last_message, config):
                result.error = "Message filtered out by keywords"
                self.session_stats['messages_ignored'] += 1
                return result
            
            # 4. Callback avant réponse
            if config.on_before_reply:
                config.on_before_reply(conv.username, last_message)
            
            # 5. Générer la réponse via LLM
            context = self._build_conversation_context(conv.username, config)
            
            start_time = time.time()
            reply = await self._generate_reply_with_llm(
                message=last_message,
                context=context,
                config=config
            )
            llm_latency = int((time.time() - start_time) * 1000)
            
            result.llm_latency_ms = llm_latency
            self.session_stats['llm_calls'] += 1
            self.session_stats['total_llm_latency_ms'] += llm_latency
            
            if not reply:
                result.error = "LLM failed to generate reply"
                return result
            
            result.reply_sent = reply
            
            # 6. Délai humain avant de répondre
            delay = random.randint(config.reply_delay_min, config.reply_delay_max)
            self.logger.debug(f"⏳ Waiting {delay}s before replying (human-like delay)...")
            await asyncio.sleep(delay)
            
            # 7. Envoyer la réponse
            if not self._send_reply(reply):
                result.error = "Failed to send reply"
                return result
            
            result.success = True
            self.logger.success(f"✅ Replied to @{conv.username}")
            
            # 8. Sauvegarder dans l'historique
            self._save_to_history(conv.username, last_message, reply)
            
            # 9. Callback après réponse
            if config.on_after_reply:
                config.on_after_reply(conv.username, last_message, reply)
            
            # 10. Retourner à la liste des DM (utiliser le bouton UI Instagram, pas ui automator)
            self._go_back_to_inbox()
            
        except Exception as e:
            result.error = f"Exception: {str(e)}"
            self.logger.error(f"Error processing conversation with @{conv.username}: {e}")
        
        return result
