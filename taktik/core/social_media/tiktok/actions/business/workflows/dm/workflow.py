"""DM Workflow for TikTok automation.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

Ce workflow permet d'automatiser les messages directs:
- Lire les conversations
- Envoyer des réponses (manuel ou IA)
- Gérer les conversations de groupe
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from loguru import logger
import time

from .._internal import BaseTikTokWorkflow
from ....atomic.dm_actions import DMActions


@dataclass
class DMConfig:
    """Configuration pour le workflow DM."""
    
    # Nombre de conversations à lire
    max_conversations: int = 20
    
    # Filtres
    skip_notifications: bool = True  # Ignorer New followers, Activity, System
    skip_groups: bool = False  # Ignorer les conversations de groupe
    only_unread: bool = False  # Seulement les conversations non lues
    
    # Délais
    delay_between_conversations: float = 1.0
    delay_after_send: float = 0.5
    
    # Comportement
    mark_as_read: bool = True  # Marquer comme lu après lecture
    close_sticker_suggestions: bool = True  # Fermer les suggestions de stickers


@dataclass
class DMStats:
    """Statistiques du workflow DM."""
    
    conversations_read: int = 0
    messages_read: int = 0
    messages_sent: int = 0
    groups_skipped: int = 0
    notifications_skipped: int = 0
    errors: int = 0
    
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        elapsed = time.time() - self.start_time
        return {
            'conversations_read': self.conversations_read,
            'messages_read': self.messages_read,
            'messages_sent': self.messages_sent,
            'groups_skipped': self.groups_skipped,
            'notifications_skipped': self.notifications_skipped,
            'errors': self.errors,
            'elapsed_seconds': elapsed,
            'elapsed_formatted': f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
        }


@dataclass
class ConversationData:
    """Data for a single conversation."""
    
    name: str
    is_group: bool = False
    member_count: Optional[int] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    last_message: Optional[str] = None
    timestamp: Optional[str] = None
    unread_count: int = 0
    can_reply: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'is_group': self.is_group,
            'member_count': self.member_count,
            'messages': self.messages,
            'last_message': self.last_message,
            'timestamp': self.timestamp,
            'unread_count': self.unread_count,
            'can_reply': self.can_reply,
        }


class DMWorkflow(BaseTikTokWorkflow):
    """Workflow d'automatisation des DM TikTok.
    
    Inherits from BaseTikTokWorkflow:
        - atomic actions (click, navigation, scroll, detection)
        - popup handler + _handle_popups
        - lifecycle (stop/pause/resume/_wait_if_paused)
        - _send_stats_update, set_on_stats_callback
    
    Adds:
        - DMActions for DM-specific interactions
        - DM-specific callbacks and progress tracking
    """
    
    def __init__(self, device, config: Optional[DMConfig] = None):
        """Initialize the workflow.
        
        Args:
            device: Device facade for UI interactions
            config: Optional configuration, uses defaults if not provided
        """
        super().__init__(device, module_name="tiktok-dm-workflow")
        self.config = config or DMConfig()
        self.stats = DMStats()
        
        # DM-specific atomic actions
        self.dm = DMActions(device)
        
        # DM-specific callbacks
        self._on_conversation_callback: Optional[Callable] = None
        self._on_message_sent_callback: Optional[Callable] = None
        self._on_progress_callback: Optional[Callable] = None
        
        # DM-specific state
        self._conversations: List[ConversationData] = []
    
    def set_on_conversation_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called for each conversation read."""
        self._on_conversation_callback = callback
    
    def set_on_message_sent_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called when a message is sent."""
        self._on_message_sent_callback = callback
    
    def set_on_progress_callback(self, callback: Callable[[int, int, str], None]):
        """Set callback for progress updates (current, total, name)."""
        self._on_progress_callback = callback
    
    def _send_progress_update(self, current: int, total: int, name: str):
        """Send progress update via callback."""
        if self._on_progress_callback:
            try:
                self._on_progress_callback(current, total, name)
            except Exception as e:
                self.logger.warning(f"Error sending progress: {e}")
    
    # ==========================================================================
    # MAIN WORKFLOW: READ CONVERSATIONS
    # ==========================================================================
    
    def read_conversations(self) -> List[ConversationData]:
        """Read conversations from inbox.
        
        Reads AT LEAST the requested number of conversations by scrolling
        through the inbox to load more if needed.
        
        Returns:
            List of ConversationData objects
        """
        self._running = True
        self._conversations = []
        self.stats = DMStats()
        read_names = set()  # Track already read conversations to avoid duplicates
        
        self.logger.info("📥 Starting DM reading workflow")
        target_count = self.config.max_conversations
        self.logger.info(f"🎯 Target: read at least {target_count} conversations")
        
        try:
            # Navigate to inbox
            if not self._ensure_on_inbox():
                self.logger.error("Failed to navigate to inbox")
                return []
            
            max_scroll_attempts = 10  # Prevent infinite scrolling
            scroll_attempts = 0
            no_new_items_count = 0
            
            while self.stats.conversations_read < target_count and self._running:
                # Handle any popups that might block interaction
                self._handle_popups()
                
                # Get visible inbox items
                inbox_items = self.dm.get_inbox_items()
                self.logger.info(f"📋 Found {len(inbox_items)} visible items in inbox")
                
                # Filter items
                new_conversations = []
                for item in inbox_items:
                    name = item.get('name', '')
                    
                    # Skip already read
                    if name in read_names:
                        continue
                    
                    if item['type'] == 'notification':
                        if self.config.skip_notifications:
                            self.stats.notifications_skipped += 1
                            continue
                    
                    if item.get('is_group', False) and self.config.skip_groups:
                        self.stats.groups_skipped += 1
                        continue
                    
                    if self.config.only_unread and item.get('unread_count', 0) == 0:
                        continue
                    
                    new_conversations.append(item)
                
                if not new_conversations:
                    no_new_items_count += 1
                    if no_new_items_count >= 3:
                        self.logger.info("No more new conversations found after scrolling")
                        break
                    
                    # Scroll to load more
                    self.logger.debug("Scrolling to load more conversations...")
                    self.dm.scroll_inbox('down')
                    time.sleep(1)
                    scroll_attempts += 1
                    
                    if scroll_attempts >= max_scroll_attempts:
                        self.logger.warning("Max scroll attempts reached")
                        break
                    continue
                
                no_new_items_count = 0  # Reset counter when we find new items
                
                # Read new conversations
                for item in new_conversations:
                    if not self._running:
                        break
                    
                    if self.stats.conversations_read >= target_count:
                        break
                    
                    name = item.get('name', 'Unknown')
                    read_names.add(name)
                    
                    self._send_progress_update(
                        self.stats.conversations_read + 1, 
                        target_count, 
                        name
                    )
                    
                    conv_data = self._read_single_conversation(item)
                    if conv_data:
                        self._conversations.append(conv_data)
                        self.stats.conversations_read += 1
                        
                        # Send callback
                        if self._on_conversation_callback:
                            try:
                                self._on_conversation_callback(conv_data.to_dict())
                            except Exception as e:
                                self.logger.warning(f"Callback error: {e}")
                    
                    self._send_stats_update()
                    
                    # Delay between conversations
                    time.sleep(self.config.delay_between_conversations)
                
                # If we still need more, scroll
                if self.stats.conversations_read < target_count:
                    self.logger.debug(f"Read {self.stats.conversations_read}/{target_count}, scrolling for more...")
                    self.dm.scroll_inbox('down')
                    time.sleep(1)
                    scroll_attempts += 1
                    
                    if scroll_attempts >= max_scroll_attempts:
                        self.logger.warning("Max scroll attempts reached")
                        break
            
            self.logger.info(f"✅ Read {self.stats.conversations_read} conversations")
            
        except Exception as e:
            self.logger.error(f"Error in DM workflow: {e}")
            self.stats.errors += 1
        
        self._running = False
        return self._conversations
    
    def _ensure_on_inbox(self) -> bool:
        """Ensure we're on the inbox page."""
        if self.dm.is_on_inbox_page():
            return True
        
        return self.dm.navigate_to_inbox()
    
    def _read_single_conversation(self, item: Dict[str, Any]) -> Optional[ConversationData]:
        """Read a single conversation.
        
        Args:
            item: Inbox item data
            
        Returns:
            ConversationData or None if failed
        """
        name = item.get('name', 'Unknown')
        self.logger.debug(f"📖 Reading conversation: {name}")
        
        try:
            # Click on conversation
            if not self.dm.click_conversation(name):
                self.logger.warning(f"Failed to open conversation: {name}")
                return None
            
            # Wait for conversation to load
            time.sleep(0.5)
            
            # Close sticker suggestion if present
            if self.config.close_sticker_suggestions:
                self.dm.close_sticker_suggestion()
            
            # Get conversation info
            conv_info = self.dm.get_conversation_info()
            
            # Get messages
            messages = self.dm.get_messages(limit=20)
            self.stats.messages_read += len(messages)
            
            # Create conversation data
            conv_data = ConversationData(
                name=conv_info.get('name') or name,
                is_group=conv_info.get('is_group', item.get('is_group', False)),
                member_count=conv_info.get('member_count'),
                messages=messages,
                last_message=item.get('last_message'),
                timestamp=item.get('timestamp'),
                unread_count=item.get('unread_count', 0),
                can_reply=True,
            )
            
            # Go back to inbox
            self.dm.go_back_to_inbox()
            time.sleep(0.3)
            
            return conv_data
            
        except Exception as e:
            self.logger.error(f"Error reading conversation {name}: {e}")
            self.stats.errors += 1
            
            # Try to go back to inbox
            try:
                self.dm.go_back_to_inbox()
            except:
                pass
            
            return None
    
    # ==========================================================================
    # SEND MESSAGES
    # ==========================================================================
    
    def send_message(self, conversation_name: str, message: str) -> bool:
        """Send a message to a conversation.
        
        Args:
            conversation_name: Name of the conversation (username or group name)
            message: Message text to send
            
        Returns:
            True if message was sent successfully
        """
        self.logger.info(f"📤 Sending message to {conversation_name}")
        
        try:
            # Ensure on inbox
            if not self._ensure_on_inbox():
                self.logger.error("Failed to navigate to inbox")
                return False
            
            # Open conversation
            if not self.dm.click_conversation(conversation_name):
                self.logger.warning(f"Failed to open conversation: {conversation_name}")
                return False
            
            time.sleep(0.5)
            
            # Close sticker suggestion if present
            if self.config.close_sticker_suggestions:
                self.dm.close_sticker_suggestion()
            
            # Send message
            if not self.dm.send_text_message(message):
                self.logger.warning(f"Failed to send message to {conversation_name}")
                return False
            
            self.stats.messages_sent += 1
            self._send_stats_update()
            
            # Callback
            if self._on_message_sent_callback:
                try:
                    self._on_message_sent_callback({
                        'conversation': conversation_name,
                        'message': message,
                        'success': True,
                    })
                except Exception as e:
                    self.logger.warning(f"Callback error: {e}")
            
            time.sleep(self.config.delay_after_send)
            
            # Go back to inbox
            self.dm.go_back_to_inbox()
            
            self.logger.info(f"✅ Message sent to {conversation_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending message to {conversation_name}: {e}")
            self.stats.errors += 1
            
            # Try to go back to inbox
            try:
                self.dm.go_back_to_inbox()
            except:
                pass
            
            return False
    
    def send_bulk_messages(
        self, 
        messages: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Send multiple messages to different conversations.
        
        Args:
            messages: List of dicts with 'conversation' and 'message' keys
            
        Returns:
            List of results with 'conversation', 'success', and optional 'error'
        """
        results = []
        total = len(messages)
        
        self.logger.info(f"📤 Sending {total} messages")
        
        for idx, msg_data in enumerate(messages):
            conversation = msg_data.get('conversation', '')
            message = msg_data.get('message', '')
            
            if not conversation or not message:
                results.append({
                    'conversation': conversation,
                    'success': False,
                    'error': 'Missing conversation or message',
                })
                continue
            
            self._send_progress_update(idx + 1, total, conversation)
            
            success = self.send_message(conversation, message)
            results.append({
                'conversation': conversation,
                'success': success,
                'error': None if success else 'Failed to send',
            })
            
            # Delay between messages
            if idx < total - 1:
                time.sleep(self.config.delay_between_conversations)
        
        sent_count = sum(1 for r in results if r['success'])
        self.logger.info(f"✅ Sent {sent_count}/{total} messages")
        
        return results
    
    # ==========================================================================
    # GETTERS
    # ==========================================================================
    
    def get_conversations(self) -> List[ConversationData]:
        """Get the list of read conversations."""
        return self._conversations
    
    def get_stats(self) -> DMStats:
        """Get current stats."""
        return self.stats
