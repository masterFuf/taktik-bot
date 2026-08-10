"""Reply sending, history management, and results for the DM Auto Reply workflow."""

import time
from typing import Dict, List, Optional
from datetime import datetime

from taktik.core.social_media.instagram.actions.atomic.text import dm_composer
from ....ui.selectors.surfaces.direct_messages import DM_SELECTORS
from .auto_reply_models import ConversationMessage


class DMReplyActionsMixin:
    """Mixin: send reply, read messages, save history, compile results."""

    def _get_last_incoming_message(self) -> Optional[str]:
        """
        Read the last message RECEIVED in the conversation.
        
        IMPORTANT: checks the last message does NOT come from us, so the bot
        never replies to itself.
        
        Returns:
                The text of the last received message, or None when the last one
                comes from us or no message was found.
        """
        try:
            # Screen size, used to tell a sent message from a received one
            screen_info = self.device.info
            screen_width = screen_info.get('displayWidth', 1080)
            
            # Find the text messages by their specific resource-id
            msg_elements = self.device(resourceId=DM_SELECTORS.message_item_resource_id)
            
            if not msg_elements.exists:
                self.logger.debug("No text messages found in conversation")
                return None
            
            # Collect every message with its position
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
                    
                    # Received (left) or sent (right) is decided by the horizontal position
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
            
            # Sort by top position to get chronological order:
            # the lowest message (greatest top) is the most recent
            all_messages.sort(key=lambda x: x['top'], reverse=True)
            
            # Take the last message
            last_message = all_messages[0]
            
            # CRITICAL: when the last message is ours, do not reply
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
        """Send the reply in the conversation."""
        try:
            # Locate, type and send through the shared composer primitive (humanized tap,
            # dedicated keyboard, then set_text and send_keys). The device_id is resolved
            # from the device itself, never defaulted.
            return dm_composer.send_message(
                self.device,
                getattr(self.device_manager, 'device_id', None),
                reply,
                logger=self.logger,
            )

        except Exception as e:
            self.logger.error(f"Error sending reply: {e}")
            return False

    def _save_to_history(self, username: str, incoming: str, reply: str):
        """Save the messages to the history."""
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
        """Compile the final results."""
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
        """Conversation history."""
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
