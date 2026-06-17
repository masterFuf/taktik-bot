"""DM Workflow for TikTok automation.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

Ce workflow permet d'automatiser les messages directs:
- Lire les conversations
- Envoyer des réponses (manuel ou IA)
- Gérer les conversations de groupe
"""

from typing import Optional, Dict, Any, List, Callable
from loguru import logger
import time

from .._internal import BaseTikTokWorkflow
from ....atomic.dm_actions import DMActions
from .models import DMConfig, DMStats, ConversationData


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
        # Inbox v2 (nouveaux followers) callbacks
        self._on_new_follower_callback: Optional[Callable] = None
        self._on_follow_back_result_callback: Optional[Callable] = None
        # Inbox v2 (conversations non-répondues) callback
        self._on_unreplied_callback: Optional[Callable] = None
        # Inbox v2 (demandes de messages) callbacks
        self._on_message_request_callback: Optional[Callable] = None
        self._on_request_result_callback: Optional[Callable] = None
        # Inbox v2 (activité / notifs système, lecture) callback
        self._on_notification_callback: Optional[Callable] = None
        
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
                # Handle any popups that might block interaction — mais NE PAS quitter l'Inbox :
                # c'est la cible du DM read (sinon close_all la fuit -> 0 conversation lue).
                self._handle_popups(skip_inbox_escape=True)
                
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
            except Exception:
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
            except Exception:
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
    
    def get_stats(self) -> DMStats:
        """Get current stats."""
        return self.stats

    # ==========================================================================
    # NEW FOLLOWERS (Phase 1 inbox v2) — scrape liste + follow-back sélectionnés
    # ==========================================================================

    def set_on_new_follower_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Callback appelé pour chaque nouveau follower scrapé (streaming front)."""
        self._on_new_follower_callback = callback

    def set_on_follow_back_result_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Callback appelé pour chaque résultat de follow-back."""
        self._on_follow_back_result_callback = callback

    def read_new_followers(self, max_items: int = 50) -> List[Dict[str, Any]]:
        """Ouvre la page « Nouveaux followers » et scrape la liste SANS agir.

        Scrolle pour charger davantage jusqu'à `max_items` (ou épuisement). Émet chaque
        follower via le callback.

        Returns:
            Liste de {username, activity, can_follow_back}
        """
        self._running = True
        self.logger.info("👥 Lecture des nouveaux followers")

        try:
            self._handle_popups(skip_inbox_escape=True)

            if not self.dm.open_new_followers_page():
                self.logger.error("Impossible d'ouvrir la page des nouveaux followers")
                return []

            seen: set = set()
            collected: List[Dict[str, Any]] = []
            scroll_budget = 10
            no_new = 0

            while len(collected) < max_items and self._running:
                added_this_pass = 0
                for fol in self.dm.get_new_followers(max_items):
                    name = fol.get('username', '')
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    collected.append(fol)
                    added_this_pass += 1
                    if self._on_new_follower_callback:
                        try:
                            self._on_new_follower_callback(fol)
                        except Exception as e:
                            self.logger.warning(f"Callback new_follower erreur: {e}")
                    if len(collected) >= max_items:
                        break

                if added_this_pass == 0:
                    no_new += 1
                    if no_new >= 3:
                        break
                else:
                    no_new = 0

                if len(collected) < max_items:
                    self.dm.scroll_inbox('down')
                    time.sleep(1)
                    scroll_budget -= 1
                    if scroll_budget <= 0:
                        break

            self.logger.info(f"✅ {len(collected)} nouveaux followers listés")
            return collected

        except Exception as e:
            self.logger.error(f"Erreur lecture nouveaux followers: {e}")
            return []

    def follow_back_users(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Suit en retour les followers sélectionnés (par username).

        Ré-ouvre la page dédiée puis tape « Suivre en retour » pour chaque username.
        Émet un résultat par username via le callback.

        Returns:
            Liste de {username, success}
        """
        self._running = True
        results: List[Dict[str, Any]] = []

        if not usernames:
            return results

        self.logger.info(f"➕ Follow-back de {len(usernames)} follower(s)")

        try:
            self._handle_popups(skip_inbox_escape=True)
            if not self.dm.open_new_followers_page():
                self.logger.error("Impossible d'ouvrir la page des nouveaux followers")
                for name in usernames:
                    res = {'username': name, 'success': False, 'error': 'page_unavailable'}
                    results.append(res)
                    self._emit_follow_back_result(res)
                return results

            for name in usernames:
                if not self._running:
                    break
                ok = False
                try:
                    ok = self.dm.follow_back(name)
                except Exception as e:
                    self.logger.warning(f"Follow-back {name} erreur: {e}")
                res = {'username': name, 'success': bool(ok)}
                results.append(res)
                self._emit_follow_back_result(res)
                time.sleep(self.config.delay_between_conversations)

            done = sum(1 for r in results if r.get('success'))
            self.logger.info(f"✅ Follow-back: {done}/{len(usernames)} réussis")
            return results

        except Exception as e:
            self.logger.error(f"Erreur follow-back: {e}")
            return results

    def _emit_follow_back_result(self, result: Dict[str, Any]):
        if self._on_follow_back_result_callback:
            try:
                self._on_follow_back_result_callback(result)
            except Exception as e:
                self.logger.warning(f"Callback follow_back_result erreur: {e}")

    # ==========================================================================
    # CONVERSATIONS NON-RÉPONDUES (Phase 2 inbox v2) — scrape + classer
    # ==========================================================================

    def set_on_unreplied_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Callback appelé pour chaque conversation listée (avec l'indice `unreplied`)."""
        self._on_unreplied_callback = callback

    def read_unreplied_conversations(
        self, max_items: int = 30, only_unreplied: bool = True
    ) -> List[Dict[str, Any]]:
        """Liste les conversations de l'inbox en marquant celles non-répondues (dernier message
        = eux), SANS répondre. La réponse aux sélectionnées réutilise `send_bulk_messages`.

        Args:
            max_items: nombre max de conversations à parcourir.
            only_unreplied: ne remonter/émettre que les non-répondues (sinon toutes, avec le flag).

        Returns:
            Liste de {username, preview, unreplied}
        """
        self._running = True
        self.logger.info("📨 Lecture des conversations (non-répondues)")

        try:
            self._handle_popups(skip_inbox_escape=True)
            if not self._ensure_on_inbox():
                self.logger.error("Inbox inatteignable -> non-répondus")
                return []

            seen: set = set()
            collected: List[Dict[str, Any]] = []
            scroll_budget = 10
            no_new = 0

            while len(collected) < max_items and self._running:
                added = 0
                for convo in self.dm.get_inbox_conversations(max_items):
                    name = convo.get('username', '')
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    if only_unreplied and not convo.get('unreplied'):
                        continue
                    collected.append(convo)
                    added += 1
                    if self._on_unreplied_callback:
                        try:
                            self._on_unreplied_callback(convo)
                        except Exception as e:
                            self.logger.warning(f"Callback unreplied erreur: {e}")
                    if len(collected) >= max_items:
                        break

                if added == 0:
                    no_new += 1
                    if no_new >= 3:
                        break
                else:
                    no_new = 0

                if len(collected) < max_items:
                    self.dm.scroll_inbox('down')
                    time.sleep(1)
                    scroll_budget -= 1
                    if scroll_budget <= 0:
                        break

            self.logger.info(f"✅ {len(collected)} conversation(s) listée(s)")
            return collected

        except Exception as e:
            self.logger.error(f"Erreur lecture non-répondus: {e}")
            return []

    # ==========================================================================
    # DEMANDES DE MESSAGES (Phase 3 inbox v2) — scrape + accepter/refuser/répondre
    # ==========================================================================

    def set_on_message_request_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Callback appelé pour chaque demande de message scrapée."""
        self._on_message_request_callback = callback

    def set_on_request_result_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Callback appelé pour chaque résultat (accept/decline/reply)."""
        self._on_request_result_callback = callback

    def read_message_requests(self, max_items: int = 30) -> List[Dict[str, Any]]:
        """Ouvre la page « Demandes de messages » et liste les demandes SANS agir.

        Returns:
            Liste de {username, preview, timestamp}
        """
        self._running = True
        self.logger.info("📥 Lecture des demandes de messages")
        try:
            self._handle_popups(skip_inbox_escape=True)
            if not self.dm.open_message_requests_page():
                self.logger.error("Impossible d'ouvrir la page des demandes")
                return []

            requests = self.dm.get_message_requests(max_items)
            for req in requests:
                if self._on_message_request_callback:
                    try:
                        self._on_message_request_callback(req)
                    except Exception as e:
                        self.logger.warning(f"Callback message_request erreur: {e}")

            self.logger.info(f"✅ {len(requests)} demande(s) listée(s)")
            return requests
        except Exception as e:
            self.logger.error(f"Erreur lecture demandes: {e}")
            return []

    def process_message_requests(self, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Exécute les décisions sur les demandes sélectionnées.

        Args:
            decisions: liste de {username, action: 'accept'|'decline', message?: str}.
                'accept' + message non vide → accepte puis répond (flux conversation).

        Returns:
            Liste de {username, action, success, replied}
        """
        self._running = True
        results: List[Dict[str, Any]] = []
        if not decisions:
            return results

        self.logger.info(f"📥 Traitement de {len(decisions)} demande(s)")
        for decision in decisions:
            if not self._running:
                break
            username = decision.get('username', '')
            action = decision.get('action', 'accept')
            message = (decision.get('message') or '').strip()
            success = False
            replied = False
            try:
                # Ré-ouvre la liste avant chaque demande (état UI propre)
                if not self.dm.open_message_requests_page():
                    raise RuntimeError('requests_page_unavailable')
                if not self.dm.open_request(username):
                    raise RuntimeError('request_not_found')

                if action == 'decline':
                    success = self.dm.decline_request()
                else:  # accept (+ éventuelle réponse)
                    success = self.dm.accept_request()
                    if success and message:
                        # Après acceptation, on est dans la conversation → répondre
                        if self.dm.is_in_conversation():
                            replied = self.dm.send_text_message(message)
                        else:
                            self.logger.warning(f"Pas dans la conversation après accept: {username}")
            except Exception as e:
                self.logger.warning(f"Demande {username} erreur: {e}")

            res = {'username': username, 'action': action, 'success': bool(success), 'replied': bool(replied)}
            results.append(res)
            if self._on_request_result_callback:
                try:
                    self._on_request_result_callback(res)
                except Exception as e:
                    self.logger.warning(f"Callback request_result erreur: {e}")
            time.sleep(self.config.delay_between_conversations)

        done = sum(1 for r in results if r.get('success'))
        self.logger.info(f"✅ Demandes traitées: {done}/{len(decisions)}")
        return results

    # ==========================================================================
    # ACTIVITÉ / NOTIFICATIONS SYSTÈME (Phase 4 inbox v2) — lecture seule
    # ==========================================================================

    def set_on_notification_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Callback appelé pour chaque section de notification (activité/système) lue."""
        self._on_notification_callback = callback

    def read_notifications(self, max_items: int = 20) -> List[Dict[str, Any]]:
        """Lit les sections Activité / Notifications système de l'inbox (LECTURE SEULE).

        Returns:
            Liste de {title, preview, category}
        """
        self._running = True
        self.logger.info("🔔 Lecture activité / notifications système")
        try:
            self._handle_popups(skip_inbox_escape=True)
            if not self._ensure_on_inbox():
                self.logger.error("Inbox inatteignable -> notifications")
                return []

            notifications = self.dm.get_inbox_notifications(max_items)
            for notif in notifications:
                if self._on_notification_callback:
                    try:
                        self._on_notification_callback(notif)
                    except Exception as e:
                        self.logger.warning(f"Callback notification erreur: {e}")

            self.logger.info(f"✅ {len(notifications)} notification(s) lue(s)")
            return notifications
        except Exception as e:
            self.logger.error(f"Erreur lecture notifications: {e}")
            return []
