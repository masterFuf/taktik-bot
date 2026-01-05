"""
DM Auto Reply Workflow - Réponse automatique aux messages directs via LLM.

Ce workflow surveille les DM entrants et répond automatiquement en utilisant
un LLM (via fal.ai) pour générer des réponses contextuelles et naturelles.

Fonctionnalités:
- Surveillance continue des nouveaux DM
- Génération de réponses via LLM (fal.ai)
- Personnalisation du ton et du contexte
- Filtrage des conversations à ignorer
- Historique des conversations pour contexte
"""
import time
import random
import asyncio
import httpx
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

from ...ui.selectors import DM_SELECTORS, NAVIGATION_SELECTORS
from ...utils.taktik_keyboard import type_with_taktik_keyboard


@dataclass
class DMAutoReplyConfig:
    """Configuration pour le workflow de réponse automatique."""
    
    # === API Configuration ===
    fal_api_key: str = ""
    llm_model: str = "meta-llama/llama-3.2-3b-instruct"  # Modèle par défaut sur fal.ai
    
    # === Persona & Contexte ===
    persona_name: str = ""
    persona_description: str = ""
    business_context: str = ""
    
    # Prompt système pour le LLM
    system_prompt: str = """Tu es un assistant qui répond aux messages Instagram de manière naturelle et engageante.
Tu dois:
- Être amical et professionnel
- Répondre de manière concise (1-3 phrases max)
- Poser des questions pour engager la conversation
- Ne jamais révéler que tu es une IA
- Adapter ton ton au contexte de la conversation"""
    
    # === Comportement ===
    # Intervalle de vérification des nouveaux messages (secondes)
    check_interval_min: int = 30
    check_interval_max: int = 120
    
    # Délai avant de répondre (pour paraître humain)
    reply_delay_min: int = 5
    reply_delay_max: int = 30
    
    # Nombre max de messages à traiter par session
    max_replies_per_session: int = 50
    
    # Durée max de la session (minutes)
    session_duration_minutes: int = 60
    
    # === Filtres ===
    # Usernames à ignorer
    ignore_usernames: List[str] = field(default_factory=list)
    
    # Mots-clés pour ignorer certains messages
    ignore_keywords: List[str] = field(default_factory=list)
    
    # Ne répondre qu'aux messages contenant ces mots-clés (vide = tous)
    respond_only_keywords: List[str] = field(default_factory=list)
    
    # === Historique ===
    # Nombre de messages précédents à inclure pour le contexte
    context_messages_count: int = 5
    
    # === Callbacks ===
    # Callback optionnel appelé avant chaque réponse
    on_before_reply: Optional[Callable] = None
    # Callback optionnel appelé après chaque réponse
    on_after_reply: Optional[Callable] = None


@dataclass
class ConversationMessage:
    """Un message dans une conversation."""
    sender: str  # 'me' ou username
    content: str
    timestamp: datetime
    is_read: bool = False


@dataclass
class Conversation:
    """Une conversation DM."""
    username: str
    messages: List[ConversationMessage] = field(default_factory=list)
    has_unread: bool = False
    last_activity: Optional[datetime] = None


@dataclass
class AutoReplyResult:
    """Résultat d'une réponse automatique."""
    username: str
    incoming_message: str
    reply_sent: str
    success: bool
    error: str = ""
    timestamp: str = ""
    llm_latency_ms: int = 0


class DMAutoReplyWorkflow:
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
    
    def _extract_username_from_thread(self, thread_element) -> Optional[str]:
        """Extraire le username d'un élément de thread."""
        try:
            # Méthode 1: Chercher via le resource-id spécifique
            username_elem = thread_element.child(
                resourceId="com.instagram.android:id/row_inbox_username"
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
    
    def _get_last_incoming_message(self) -> Optional[str]:
        """
        Récupérer le dernier message reçu dans la conversation.
        
        IMPORTANT: Vérifie que le dernier message ne provient PAS de nous-mêmes
        pour éviter de se répondre à soi-même.
        
        Returns:
            Le texte du dernier message reçu, ou None si le dernier message
            provient de nous ou si aucun message n'est trouvé.
        """
        try:
            # Récupérer la taille de l'écran pour déterminer si message envoyé/reçu
            screen_info = self.device.info
            screen_width = screen_info.get('displayWidth', 1080)
            
            # Chercher les messages texte via le resource-id spécifique
            msg_elements = self.device(resourceId="com.instagram.android:id/direct_text_message_text_view")
            
            if not msg_elements.exists:
                self.logger.debug("No text messages found in conversation")
                return None
            
            # Collecter tous les messages avec leur position
            all_messages = []
            for i in range(msg_elements.count):
                try:
                    msg = msg_elements[i]
                    text = msg.get_text()
                    if not text or len(text) < 2:
                        continue
                    
                    bounds = msg.info.get('bounds', {})
                    msg_left = bounds.get('left', 0)
                    msg_top = bounds.get('top', 0)
                    
                    # Déterminer si le message est reçu (à gauche) ou envoyé (à droite)
                    # Messages reçus: position left < 50% de l'écran
                    # Messages envoyés: position left >= 50% de l'écran
                    is_received = msg_left < screen_width * 0.5
                    
                    all_messages.append({
                        'text': text,
                        'is_received': is_received,
                        'top': msg_top
                    })
                except Exception as e:
                    self.logger.debug(f"Error parsing message {i}: {e}")
                    continue
            
            if not all_messages:
                self.logger.debug("No valid messages found")
                return None
            
            # Trier par position (top) pour avoir l'ordre chronologique
            # Le message le plus bas (top le plus grand) est le plus récent
            all_messages.sort(key=lambda x: x['top'], reverse=True)
            
            # Prendre le dernier message (le plus récent)
            last_message = all_messages[0]
            
            # VÉRIFICATION CRITIQUE: Si le dernier message vient de nous, ne pas répondre!
            if not last_message['is_received']:
                self.logger.warning(
                    f"⚠️ Le dernier message provient de NOUS, pas de l'interlocuteur. "
                    f"On ne répond pas pour éviter de se parler à soi-même. "
                    f"Message: '{last_message['text'][:50]}...'"
                )
                return None
            
            self.logger.debug(f"Dernier message reçu: '{last_message['text'][:50]}...'")
            return last_message['text']
            
        except Exception as e:
            self.logger.error(f"Error getting last message: {e}")
            return None
    
    def _message_matches_filters(self, message: str, config: DMAutoReplyConfig) -> bool:
        """Vérifier si le message passe les filtres."""
        message_lower = message.lower()
        
        # Ignorer si contient des mots-clés à ignorer
        for keyword in config.ignore_keywords:
            if keyword.lower() in message_lower:
                return False
        
        # Si des mots-clés de réponse sont définis, vérifier leur présence
        if config.respond_only_keywords:
            for keyword in config.respond_only_keywords:
                if keyword.lower() in message_lower:
                    return True
            return False
        
        return True
    
    def _build_conversation_context(self, username: str, config: DMAutoReplyConfig) -> str:
        """Construire le contexte de conversation pour le LLM."""
        context_parts = []
        
        # Ajouter le contexte business
        if config.business_context:
            context_parts.append(f"Business context: {config.business_context}")
        
        # Ajouter la persona
        if config.persona_name:
            context_parts.append(f"You are responding as: {config.persona_name}")
        if config.persona_description:
            context_parts.append(f"Persona: {config.persona_description}")
        
        # Ajouter l'historique de conversation
        if username in self.conversation_history:
            history = self.conversation_history[username][-config.context_messages_count:]
            if history:
                context_parts.append("Previous messages in this conversation:")
                for msg in history:
                    sender = "You" if msg.sender == "me" else msg.sender
                    context_parts.append(f"  {sender}: {msg.content}")
        
        return "\n".join(context_parts)
    
    async def _generate_reply_with_llm(
        self,
        message: str,
        context: str,
        config: DMAutoReplyConfig
    ) -> Optional[str]:
        """
        Générer une réponse via fal.ai LLM.
        
        Args:
            message: Message reçu
            context: Contexte de la conversation
            config: Configuration
            
        Returns:
            Réponse générée ou None
        """
        try:
            self.logger.debug(f"Generating reply with LLM for: {message[:50]}...")
            
            # Construire le prompt
            full_prompt = f"""{config.system_prompt}

{context}

User message: {message}

Your reply (keep it natural and concise):"""
            
            # Appel à fal.ai
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://fal.run/fal-ai/lora",
                    headers={
                        "Authorization": f"Key {config.fal_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model_name": config.llm_model,
                        "prompt": full_prompt,
                        "max_tokens": 150,
                        "temperature": 0.7
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    reply = result.get("output", "").strip()
                    
                    # Nettoyer la réponse
                    reply = self._clean_llm_response(reply)
                    
                    self.logger.debug(f"LLM generated: {reply[:50]}...")
                    return reply
                else:
                    self.logger.error(f"fal.ai API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error calling LLM: {e}")
            return None
    
    def _clean_llm_response(self, response: str) -> str:
        """Nettoyer la réponse du LLM."""
        # Supprimer les préfixes courants
        prefixes_to_remove = [
            "Your reply:",
            "Reply:",
            "Response:",
            "Assistant:",
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Supprimer les guillemets encadrants
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        
        return response.strip()
    
    def _send_reply(self, reply: str) -> bool:
        """Envoyer la réponse dans la conversation."""
        try:
            # Trouver le champ de saisie
            message_input = self.device(className="android.widget.EditText")
            if not message_input.exists(timeout=5):
                self.logger.error("Message input not found")
                return False
            
            # Saisir le message
            message_input.click()
            time.sleep(0.5)
            # Use Taktik Keyboard for reliable text input
            device_id = getattr(self.device_manager, 'device_id', None) or 'emulator-5554'
            if not type_with_taktik_keyboard(device_id, reply):
                self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                message_input.set_text(reply)
            time.sleep(0.5)
            
            # Envoyer
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
            self.logger.error(f"Error sending reply: {e}")
            return False
    
    def _go_back_to_inbox(self):
        """
        Retourner à la liste des DM en utilisant le bouton UI Instagram.
        Évite d'utiliser device.press("back") qui peut causer des problèmes.
        """
        try:
            # Méthode 1: Bouton back dans le header (resource-id spécifique)
            back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
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
    
    def _save_to_history(self, username: str, incoming: str, reply: str):
        """Sauvegarder les messages dans l'historique."""
        if username not in self.conversation_history:
            self.conversation_history[username] = []
        
        now = datetime.now()
        
        # Message reçu
        self.conversation_history[username].append(ConversationMessage(
            sender=username,
            content=incoming,
            timestamp=now
        ))
        
        # Notre réponse
        self.conversation_history[username].append(ConversationMessage(
            sender="me",
            content=reply,
            timestamp=now
        ))
        
        # Limiter l'historique
        if len(self.conversation_history[username]) > 50:
            self.conversation_history[username] = self.conversation_history[username][-50:]
    
    def _get_final_results(self, error: str = "") -> Dict[str, Any]:
        """Compiler les résultats finaux."""
        avg_latency = 0
        if self.session_stats['llm_calls'] > 0:
            avg_latency = self.session_stats['total_llm_latency_ms'] // self.session_stats['llm_calls']
        
        return {
            'success': error == "",
            'error': error,
            'stats': {
                **self.session_stats,
                'avg_llm_latency_ms': avg_latency
            },
            'results': [
                {
                    'username': r.username,
                    'incoming': r.incoming_message[:100] if r.incoming_message else "",
                    'reply': r.reply_sent[:100] if r.reply_sent else "",
                    'success': r.success,
                    'error': r.error,
                    'llm_latency_ms': r.llm_latency_ms,
                    'timestamp': r.timestamp
                }
                for r in self.results
            ],
            'summary': {
                'total_checked': self.session_stats['messages_checked'],
                'replies_sent': self.session_stats['replies_sent'],
                'replies_failed': self.session_stats['replies_failed'],
                'ignored': self.session_stats['messages_ignored'],
                'llm_calls': self.session_stats['llm_calls']
            }
        }
    
    def get_conversation_history(self, username: str) -> List[Dict]:
        """Récupérer l'historique d'une conversation."""
        if username not in self.conversation_history:
            return []
        
        return [
            {
                'sender': msg.sender,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat()
            }
            for msg in self.conversation_history[username]
        ]
