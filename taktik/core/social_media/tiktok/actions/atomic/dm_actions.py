"""Atomic DM actions for TikTok.

Actions pour la lecture et l'envoi de messages directs TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps:
- ui_dump_20260107_231412.xml (Inbox)
- ui_dump_20260107_231514.xml (Conversation simple)
- ui_dump_20260107_231534.xml (Conversation groupe)
"""

import re
import time
from typing import Dict, Any, List
from loguru import logger

from ..core.base_action import BaseAction
from ..core.utils import extract_resource_id
from ...ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from ...ui.selectors.surfaces.conversation import CONVERSATION_SELECTORS
from ...ui.selectors.surfaces.inbox import INBOX_SELECTORS


class DMActions(BaseAction):
    """Low-level DM actions for TikTok.
    
    Gère la lecture des conversations et l'envoi de messages.
    Toutes les actions utilisent des sélecteurs basés sur resource-id/content-desc.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-dm-atomic")
        self.inbox_selectors = INBOX_SELECTORS
        self.conversation_selectors = CONVERSATION_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
    
    @staticmethod
    def _extract_resource_id(selectors: List[str]) -> str:
        """Extract resource-id value from the first xpath selector.

        e.g. '//*[@resource-id="com.zhiliaoapp.musically:id/z05"]' → 'com.zhiliaoapp.musically:id/z05'
        """
        return extract_resource_id(selectors)

    # Marques bidi / format invisibles dont TikTok entoure les usernames (o0f) :
    # LRM/RLM, isolats FSI/PDI/LRI/RLI, embeddings/overrides, word-joiner.
    _BIDI_FORMAT_CHARS = dict.fromkeys(
        [0x200E, 0x200F, 0x2060, 0x2066, 0x2067, 0x2068, 0x2069,
         0x202A, 0x202B, 0x202C, 0x202D, 0x202E],
        None,
    )

    @staticmethod
    def _clean_username(text: str) -> str:
        """Retire les marques bidi/format invisibles d'un username TikTok (o0f).

        Ex. '\\u200e\\u2068NK19\\u2069' -> 'NK19'. Indispensable pour l'affichage front ET pour
        que le sélecteur `contains(@text, name)` (follow_back) matche (le texte du noeud garde
        ces marques, donc on matche par `contains` sur le nom nettoyé).
        """
        return (text or '').translate(DMActions._BIDI_FORMAT_CHARS).strip()

    @staticmethod
    def _resource_id_pattern(selectors: List[str]) -> str:
        """Build a `resourceIdMatches` regex from a centralized resource-id selector.

        Les sélecteurs inbox/conversation sont en forme xpath `contains(@resource-id, ":id/xxx")`
        (token partiel, sans le package) → un match EXACT `resourceId="..."` échoue. On extrait le
        token et on construit une regex full-match pour `resourceIdMatches` :
        - forme exacte `@resource-id="com...:id/x"` → `com\\.\\.\\.:id/x` (échappé)
        - forme contains `contains(@resource-id, ":id/x")` → `.*:id/x.*` (réplique le « contains »)
        """
        for sel in selectors:
            m = re.search(r'@resource-id\s*=\s*"([^"]+)"', sel)
            if m:
                return re.escape(m.group(1))
            m = re.search(r'@resource-id\s*,\s*"([^"]+)"', sel)
            if m:
                return '.*' + re.escape(m.group(1)) + '.*'
        return ''

    def _find_all_by_rid(self, selectors: List[str]):
        """Return the uiautomator2 UiObject collection for a centralized resource-id selector.

        Robuste à la forme `contains(...)` (cf. _resource_id_pattern) — remplace l'ancien
        `raw_device(resourceId=extract(...))` qui renvoyait `resourceId=''` (0 match) pour les
        sélecteurs en forme contains. API UiObject identique (.exists/.count/[i]/.get_text()).
        """
        pattern = self._resource_id_pattern(selectors)
        if not pattern:
            return None
        raw_device = self.device._device if hasattr(self.device, '_device') else self.device
        return raw_device(resourceIdMatches=pattern)
    
    # ==========================================================================
    # INBOX NAVIGATION
    # ==========================================================================
    
    def is_on_inbox_page(self) -> bool:
        """Check if currently on the Inbox page."""
        return self._element_exists(self.inbox_selectors.inbox_title, timeout=2)
    
    def navigate_to_inbox(self) -> bool:
        """Navigate to the Inbox page."""
        self.logger.debug("📥 Navigating to Inbox")
        
        # Check if already on inbox
        if self.is_on_inbox_page():
            self.logger.debug("Already on Inbox page")
            return True
        
        # Try clicking inbox tab
        if self._find_and_click(self.navigation_selectors.inbox_tab, timeout=3):
            time.sleep(1)
            if self.is_on_inbox_page():
                return True
        
        # Fallback: check if we can see conversations (might be on inbox without title)
        if self._element_exists(self.inbox_selectors.conversation_username, timeout=1):
            self.logger.debug("Found conversations, assuming on Inbox")
            return True
        
        self.logger.warning("Failed to navigate to Inbox")
        return False
    
    # ==========================================================================
    # INBOX READING
    # ==========================================================================
    
    def get_inbox_items(self) -> List[Dict[str, Any]]:
        """Get all visible items in the inbox (notifications + conversations).
        
        Returns:
            List of items with type, name, last_message, timestamp, unread_count, is_group
        """
        items = []
        
        # Get notification sections first
        notifications = self._get_notification_sections()
        items.extend(notifications)
        
        # Get conversations
        conversations = self._get_conversations()
        items.extend(conversations)
        
        return items
    
    def _get_notification_sections(self) -> List[Dict[str, Any]]:
        """Get notification sections (New followers, Activity, System).

        Utilise les sélecteurs langue-aware (FR/EN filtrés par detect_and_optimize) plutôt que
        des titres en dur — sinon la détection échoue quand l'app n'est pas en anglais.
        """
        notifications = []

        # (sélecteurs langue-aware, notification_type, libellé stable)
        notification_types = [
            (self.inbox_selectors.new_followers_section, 'new_followers'),
            (self.inbox_selectors.activity_section, 'activity'),
            (self.inbox_selectors.system_notifications_section, 'system'),
        ]

        for selectors, notif_type in notification_types:
            try:
                if self._element_exists(selectors, timeout=1):
                    notifications.append({
                        'type': 'notification',
                        'notification_type': notif_type,
                        'name': notif_type,
                        'subtitle': '',
                        'timestamp': '',
                        'is_group': False,
                        'unread_count': 0,
                    })
            except Exception as e:
                self.logger.debug(f"Error checking notification {notif_type}: {e}")
                continue

        return notifications
    
    def _get_conversations(self) -> List[Dict[str, Any]]:
        """Get conversation items from inbox."""
        conversations = []
        
        try:
            # Find all username elements via centralized conversation_username resource-id
            # (resourceIdMatches : robuste à la forme contains, cf. _find_all_by_rid)
            username_elements = self._find_all_by_rid(self.inbox_selectors.conversation_username)

            if username_elements is None or not username_elements.exists:
                self.logger.debug("No conversation usernames found")
                return conversations
            
            count = username_elements.count
            self.logger.debug(f"Found {count} conversation usernames")
            
            for i in range(count):  # No limit here, workflow handles max_conversations
                try:
                    elem = username_elements[i]
                    name = elem.get_text()
                    
                    if not name:
                        continue
                    
                    # For now, we can't easily get last_message and timestamp
                    # without complex parent/sibling navigation
                    # We'll get basic info and read details when opening the conversation
                    
                    conversations.append({
                        'type': 'conversation',
                        'name': name,
                        'last_message': '',
                        'timestamp': '',
                        'is_group': False,  # Will detect when opening
                        'unread_count': 0,
                    })
                except Exception as e:
                    self.logger.debug(f"Error parsing conversation {i}: {e}")
                    continue
            
        except Exception as e:
            self.logger.warning(f"Error getting conversations: {e}")

        return conversations

    # ==========================================================================
    # NEW FOLLOWERS (page dédiée — onglet Messages -> « Nouveaux followers »)
    # ==========================================================================

    def open_new_followers_page(self) -> bool:
        """Ouvre la page dédiée « Nouveaux followers » depuis l'onglet Messages.

        Navigue vers l'inbox, puis tape la section « Nouveaux followers » (ou « Tout voir »).
        Sélecteurs langue-aware (FR/EN filtrés au démarrage par detect_and_optimize).
        """
        if not self.navigate_to_inbox():
            self.logger.warning("Inbox inatteignable -> nouveaux followers")
            return False

        # La section et le « Tout voir » mènent à la même page dédiée
        if self._find_and_click(self.inbox_selectors.new_followers_section, timeout=3):
            time.sleep(1)
            return self._is_on_new_followers_page()

        if self._find_and_click(self.inbox_selectors.see_all_button, timeout=2):
            time.sleep(1)
            return self._is_on_new_followers_page()

        self.logger.warning("Section « Nouveaux followers » introuvable")
        return False

    def _is_on_new_followers_page(self) -> bool:
        """Heuristique : page dédiée présente si des items de followers sont rendus."""
        return self._element_exists(self.inbox_selectors.new_followers_page_item, timeout=2)

    def get_new_followers(self, max_items: int = 50) -> List[Dict[str, Any]]:
        """Scrape la liste des nouveaux followers (page dédiée) SANS agir.

        Returns:
            Liste de {username, activity, can_follow_back}
        """
        followers: List[Dict[str, Any]] = []

        try:
            # resourceIdMatches : robuste à la forme contains des sélecteurs (cf. _find_all_by_rid)
            username_elements = self._find_all_by_rid(self.inbox_selectors.new_followers_page_username)
            if username_elements is None or not username_elements.exists:
                self.logger.debug("Aucun nouveau follower trouvé")
                return followers

            count = min(username_elements.count, max_items)
            activity_elements = self._find_all_by_rid(self.inbox_selectors.new_followers_page_activity)
            activity_count = (
                activity_elements.count if activity_elements is not None and activity_elements.exists else 0
            )

            for i in range(count):
                try:
                    name = self._clean_username(username_elements[i].get_text())
                    if not name:
                        continue

                    activity = ''
                    if i < activity_count:
                        try:
                            activity = self._clean_username(activity_elements[i].get_text())
                        except Exception:
                            activity = ''

                    # Le bouton « Suivre en retour » n'existe que si on ne le suit pas déjà
                    can_follow_back = self.device.xpath(
                        self.inbox_selectors.follow_back_for_username(name)
                    ).exists

                    followers.append({
                        'username': name,
                        'activity': activity,
                        'can_follow_back': bool(can_follow_back),
                    })
                except Exception as e:
                    self.logger.debug(f"Erreur parsing nouveau follower {i}: {e}")
                    continue

        except Exception as e:
            self.logger.warning(f"Erreur scrape nouveaux followers: {e}")

        return followers

    def follow_back(self, username: str) -> bool:
        """Tape « Suivre en retour » sur l'item du follower `username`.

        Sélecteur dynamique scopé à l'item (follow_back_for_username) -> ne tape jamais le
        bouton d'un autre follower.
        """
        username = self._clean_username(username)
        if not username:
            return False

        selector = self.inbox_selectors.follow_back_for_username(username)
        if self._find_and_click([selector], timeout=3):
            self.logger.info(f"Suivi en retour : {username}")
            time.sleep(0.5)
            return True

        self.logger.warning(f"« Suivre en retour » introuvable pour {username}")
        return False

    def click_conversation(self, name: str) -> bool:
        """Click on a conversation by name.
        
        Args:
            name: Username or group name to click
            
        Returns:
            True if conversation was clicked successfully
        """
        self.logger.debug(f"💬 Opening conversation: {name}")
        
        try:
            # Find all username elements and match by text
            # (resourceIdMatches : robuste à la forme contains, cf. _find_all_by_rid)
            username_elements = self._find_all_by_rid(self.inbox_selectors.conversation_username)

            if username_elements is not None and username_elements.exists:
                count = username_elements.count
                for i in range(count):
                    try:
                        elem = username_elements[i]
                        elem_text = elem.get_text()
                        
                        # Normalize both strings for comparison (strip invisible chars)
                        name_clean = name.strip().replace('\u200e', '').replace('\u200f', '')
                        elem_clean = (elem_text or '').strip().replace('\u200e', '').replace('\u200f', '')
                        
                        if elem_clean == name_clean or name_clean in elem_clean or elem_clean in name_clean:
                            self.logger.debug(f"Found matching conversation at index {i}")
                            elem.click()
                            time.sleep(1)
                            return self.is_in_conversation()
                    except Exception as e:
                        self.logger.debug(f"Error checking element {i}: {e}")
                        continue
            
            # Fallback: try XPath with exact match
            selector = self.inbox_selectors.conversation_username_by_text(name)
            if self._find_and_click([selector], timeout=2):
                time.sleep(1)
                return self.is_in_conversation()
                
        except Exception as e:
            self.logger.warning(f"Error clicking conversation: {e}")
        
        self.logger.warning(f"Conversation not found: {name}")
        return False
    
    def scroll_inbox(self, direction: str = 'down') -> bool:
        """Scroll the inbox list.
        
        Args:
            direction: 'down' or 'up'
        """
        try:
            if direction == 'down':
                self._scroll_down()
            else:
                self._scroll_up()
            time.sleep(0.5)
            return True
        except Exception as e:
            self.logger.warning(f"Failed to scroll inbox: {e}")
            return False
    
    # ==========================================================================
    # CONVERSATION READING
    # ==========================================================================
    
    def is_in_conversation(self) -> bool:
        """Check if currently in a conversation view."""
        # Check for message input field
        return self._element_exists(self.conversation_selectors.message_input_field, timeout=2)
    
    def get_conversation_info(self) -> Dict[str, Any]:
        """Get info about the current conversation.
        
        Returns:
            Dict with name, is_group, member_count (for groups)
        """
        info = {
            'name': None,
            'is_group': False,
            'member_count': None,
        }
        
        # Get conversation name
        name = self._get_element_text(self.conversation_selectors.conversation_name, timeout=2)
        info['name'] = name
        
        # Check if group
        member_count_text = self._get_element_text(
            self.conversation_selectors.group_member_count, 
            timeout=1
        )
        if member_count_text:
            info['is_group'] = True
            # Extract number from text like "29"
            try:
                info['member_count'] = int(''.join(filter(str.isdigit, member_count_text)))
            except Exception:
                info['member_count'] = None
        
        return info
    
    def get_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get messages from current conversation.
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of messages with sender, text, type, timestamp
        """
        messages = []
        
        try:
            # Find all text message elements via centralized message_text resource-id
            # (resourceIdMatches : robuste à la forme contains, cf. _find_all_by_rid)
            text_elements = self._find_all_by_rid(self.conversation_selectors.message_text)

            if text_elements is not None and text_elements.exists:
                count = min(text_elements.count, limit)
                self.logger.debug(f"Found {count} text messages")
                
                for i in range(count):
                    try:
                        elem = text_elements[i]
                        text = elem.get_text()
                        
                        if text:
                            messages.append({
                                'sender': None,  # Would need parent navigation
                                'text': text,
                                'type': 'text',
                                'is_sent': False,  # Can't easily determine
                            })
                    except Exception as e:
                        self.logger.debug(f"Error parsing message {i}: {e}")
                        continue
            
            # Also check for stickers/GIFs
            sticker_elements = self._find_all_by_rid(self.conversation_selectors.message_sticker)

            if sticker_elements is not None and sticker_elements.exists:
                sticker_count = min(sticker_elements.count, limit - len(messages))
                for i in range(sticker_count):
                    messages.append({
                        'sender': None,
                        'text': None,
                        'type': 'sticker',
                        'is_sent': False,
                    })
            
        except Exception as e:
            self.logger.warning(f"Error getting messages: {e}")
        
        return messages
    
    # ==========================================================================
    # MESSAGE SENDING
    # ==========================================================================
    
    def type_message(self, text: str) -> bool:
        """Type a message in the input field.
        
        Args:
            text: Message text to type
            
        Returns:
            True if text was entered successfully
        """
        self.logger.debug(f"⌨️ Typing message: {text[:50]}...")
        
        # Click on input field first
        if not self._find_and_click(self.conversation_selectors.message_input_field, timeout=3):
            self.logger.warning("Message input field not found")
            return False
        
        time.sleep(0.3)
        
        # Type the message using ADB
        try:
            # Clear any existing text first
            self.device.clear_text()
            time.sleep(0.2)
            
            # Type new text
            self.device.send_keys(text)
            time.sleep(0.3)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to type message: {e}")
            return False
    
    def send_message(self) -> bool:
        """Send the typed message by clicking send button.
        
        Returns:
            True if message was sent successfully
        """
        self.logger.debug("📤 Sending message")
        
        # Try send button
        if self._find_and_click(self.conversation_selectors.send_button, timeout=2):
            self._human_like_delay('click')
            return True
        
        # Fallback: press Enter key
        try:
            self.device.press("enter")
            self._human_like_delay('click')
            return True
        except Exception as e:
            self.logger.warning(f"Failed to send message: {e}")
            return False
    
    def send_text_message(self, text: str) -> bool:
        """Type and send a text message.
        
        Args:
            text: Message to send
            
        Returns:
            True if message was sent successfully
        """
        if not self.type_message(text):
            return False
        
        return self.send_message()
    
    # ==========================================================================
    # NAVIGATION
    # ==========================================================================
    
    def go_back_to_inbox(self) -> bool:
        """Go back from conversation to inbox."""
        self.logger.debug("⬅️ Going back to inbox")
        
        # Try back button in conversation header
        if self._find_and_click(self.conversation_selectors.back_button, timeout=2):
            time.sleep(0.5)
            return self.is_on_inbox_page()
        
        # Fallback: press back key
        try:
            self.device.press("back")
            time.sleep(0.5)
            return self.is_on_inbox_page()
        except Exception as e:
            self.logger.warning(f"Failed to go back: {e}")
            return False
    
    def close_sticker_suggestion(self) -> bool:
        """Close the sticker suggestion popup in new conversations."""
        return self._find_and_click(
            self.conversation_selectors.close_sticker_suggestion, 
            timeout=1
        )
    
