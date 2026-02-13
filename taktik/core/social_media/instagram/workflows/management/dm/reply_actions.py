"""Reply sending, history management, and results for the DM Auto Reply workflow."""

import time
from typing import Dict, List, Optional
from datetime import datetime

from ....utils.input.keyboard import type_with_taktik_keyboard
from ....ui.selectors import DM_SELECTORS
from .auto_reply_models import ConversationMessage


class DMReplyActionsMixin:
    """Mixin: send reply, read messages, save history, compile results."""

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
            msg_elements = self.device(resourceId=DM_SELECTORS.message_item_resource_id)
            
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

    def _get_final_results(self, error: str = "") -> Dict[str, any]:
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
