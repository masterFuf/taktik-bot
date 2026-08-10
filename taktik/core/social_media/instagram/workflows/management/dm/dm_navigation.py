"""DM inbox navigation, thread extraction, and conversation open/close."""

import time
from typing import List, Optional
from datetime import datetime

from taktik.core.shared.text import normalize_ui_label
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from .auto_reply_models import Conversation


class DMNavigationMixin:
    """Mixin: navigate to DM inbox, extract threads, open/close conversations."""

    def _navigate_to_dm_inbox(self) -> bool:
        """Navigate to the DM inbox."""
        try:
            self.logger.debug("Navigating to DM inbox...")
            
            # Way 1: tap the DM tab in the tab bar (resource-id)
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
            
            # Way 3: uiautomator fallback
            dm_button = None
            for description in self.dm_selectors.direct_tab_content_descriptions:
                candidate = self.device(contentDescription=description)
                if candidate.exists(timeout=3):
                    dm_button = candidate
                    break

            if dm_button and dm_button.exists(timeout=5):
                dm_button.click()
                time.sleep(2)
                self.logger.debug("✅ Navigated to DM inbox via fallback")
                return True
            
            self.logger.error("DM tab not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to DM inbox: {e}")
            return False

    def _get_unread_conversations(self) -> List[Conversation]:
        """
        Collect the conversations carrying unread messages.
        
        Returns:
                List of conversations with unread messages
        """
        conversations = []
        
        try:
            self.logger.debug("Checking for unread messages...")
            
            # Navigate to the DM screen
            if not self._navigate_to_dm_inbox():
                return conversations
            
            time.sleep(2)
            
            # Look for the unread indicators
            # Unread conversations usually carry a blue dot or a different style
            thread_list = self.device.xpath(self.dm_selectors.thread_list)
            if not thread_list.exists:
                self.logger.debug("Thread list not found")
                return conversations
            
            # Walk the visible threads
            threads = self.device.xpath(self.dm_selectors.thread_container).all()
            
            for i, thread in enumerate(threads[:10]):  # Keep the first ten only
                try:
                    # Vérifier si non lu via content-desc
                    thread_info = thread.info
                    content_desc = thread_info.get('contentDescription', '')
                    has_unread = 'non lu' in content_desc.lower() or 'unread' in content_desc.lower()
                    
                    # Extract the thread username
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

    def _is_presence_status(self, value: str) -> bool:
        """Is the text a presence STATUS ("En ligne", "Active now") rather than a handle?

        The guard used to test an English prefix in hardcoded form, so on a device in
        another language it recognised nothing and the status was returned as the
        conversation name. The labels now live in the locale layer, and both sides are
        """
        normalized = normalize_ui_label(value)
        if not normalized:
            return False
        return any(normalized.startswith(normalize_ui_label(prefix))
                   for prefix in DM_SELECTORS.presence_prefixes if prefix and prefix.strip())

    def _extract_username_from_thread(self, thread_element) -> Optional[str]:
        """Extract the username from a thread element."""
        try:
            # Way 1: look it up by its specific resource-id
            username_elem = thread_element.child(
                resourceId=DM_SELECTORS.thread_username_resource_id
            )
            if username_elem.exists:
                username = username_elem.get_text()
                if username:
                    return username.strip()
            
            # Way 2: read it from the container content-desc
            # Format: "Username, unread, Message preview, timestamp"
            thread_info = thread_element.info
            content_desc = thread_info.get('contentDescription', '')
            if content_desc:
                # The username is the first element before the comma
                parts = content_desc.split(',')
                if parts:
                    username = parts[0].strip()
                    if username and not self._is_presence_status(username):
                        return username
            
            # Way 3: fallback, take the first TextView
            text_views = thread_element.child(**DM_SELECTORS.text_view_class_selector)
            if text_views.exists:
                username = text_views.get_text()
                if username and not self._is_presence_status(username):
                    return username.strip()
                    
        except Exception as e:
            self.logger.debug(f"Error extracting username: {e}")
        
        return None

    def _open_conversation(self, username: str) -> bool:
        """Open one conversation."""
        try:
            # Find the thread by username
            thread = self.device(**DM_SELECTORS.thread_selector_for_username(username))
            if thread.exists(timeout=5):
                thread.click()
                time.sleep(2)
                return True
            
            self.logger.error(f"Conversation with @{username} not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening conversation: {e}")
            return False

    def _go_back_to_inbox(self):
        """
        Go back to the DM list through the Instagram button.
        Avoids device.press("back"), which leaves unpredictable states.
        """
        try:
            # Way 1: back button in the header (specific resource-id)
            back_btn = self.device(resourceId=DM_SELECTORS.conversation_back_button_resource_id)
            if back_btn.exists(timeout=2):
                back_btn.click()
                time.sleep(1)
                self.logger.debug("✅ Retour via header_left_button")
                return True
            
            # Way 2: button with content-desc "Back"
            for description in DM_SELECTORS.conversation_back_descriptions:
                back_btn = self.device(description=description)
                if back_btn.exists(timeout=2):
                    back_btn.click()
                    time.sleep(1)
                    self.logger.debug("✅ Retour via description Back")
                    return True
            
            # Way 3: button with content-desc "Retour"
            for description in DM_SELECTORS.conversation_back_description_contains:
                back_btn = self.device(descriptionContains=description)
                if back_btn.exists(timeout=2):
                    back_btn.click()
                    time.sleep(1)
                    self.logger.debug("✅ Retour via description Retour")
                    return True
            
            # Last resort: press back when no button was found
            self.logger.warning("Aucun bouton back UI trouvé, utilisation de press back en fallback")
            self.device.press("back")
            time.sleep(1)
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors du retour: {e}")
            self.device.press("back")
            time.sleep(1)
            return False
