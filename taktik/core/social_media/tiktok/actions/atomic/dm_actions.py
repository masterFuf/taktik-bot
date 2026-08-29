"""Atomic DM actions for TikTok.

Reading and sending TikTok direct messages.

Based on the UI dumps:
- ui_dump_20260107_231412.xml (Inbox)
- ui_dump_20260107_231514.xml (Conversation simple)
- ui_dump_20260107_231534.xml (Conversation groupe)
"""

import re
import time
from typing import Dict, Any, List
from loguru import logger

from ..core.base_action import BaseAction
from ..core.utils import extract_resource_id, first_matching
from ...ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from ...ui.selectors.surfaces.conversation import CONVERSATION_SELECTORS
from ...ui.selectors.surfaces.inbox import INBOX_SELECTORS


class _XPathCollection:
    """A uiautomator2 UiObject collection, backed by xpath matches.

    `_find_all_by_rid` promises `.exists` / `.count` / `[i].get_text()`; an xpath match is an
    XMLElement with `.text`. This adapts the second to the first so callers stay unchanged —
    the same difference that separated the working profile reader from the broken one.
    """

    def __init__(self, elements):
        self._elements = list(elements)

    @property
    def exists(self) -> bool:
        return bool(self._elements)

    @property
    def count(self) -> int:
        return len(self._elements)

    def __getitem__(self, index):
        return _XPathNode(self._elements[index])


class _XPathNode:
    """One xpath match, wearing the UiObject shape callers expect.

    A first version exposed `get_text()` and nothing else, so `click()` and the bounds lookup
    raised — and the callers swallow exceptions and move on, which turned "found it" into
    "conversation not found". Everything not named here forwards to the element itself.
    """

    def __init__(self, element):
        self._element = element

    def get_text(self) -> str:
        try:
            return self._element.text or ''
        except Exception:
            return ''

    def __getattr__(self, name):
        return getattr(self._element, name)


class DMActions(BaseAction):
    """Low-level DM actions for TikTok.
    
    Handles reading conversations and sending messages.
    Every action uses resource-id or content-desc based selectors.
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

    # Invisible bidi and formatting marks TikTok wraps usernames with:
    # LRM/RLM, isolats FSI/PDI/LRI/RLI, embeddings/overrides, word-joiner.
    _BIDI_FORMAT_CHARS = dict.fromkeys(
        [0x200E, 0x200F, 0x2060, 0x2066, 0x2067, 0x2068, 0x2069,
         0x202A, 0x202B, 0x202C, 0x202D, 0x202E],
        None,
    )

    @staticmethod
    def _clean_username(text: str) -> str:
        """Strip the invisible bidi and formatting marks from a TikTok username.

        Needed both for display AND so the containment selector used by the follow-back
        matches: the node text KEEPS those marks, so the match is done by containment on
        the cleaned name.
        """
        return (text or '').translate(DMActions._BIDI_FORMAT_CHARS).strip()

    @staticmethod
    def _resource_id_pattern(selectors: List[str]) -> str:
        """Build a `resourceIdMatches` regex from a centralized resource-id selector.

        The inbox and conversation selectors are written as an xpath containment on a partial
        token, without the package, so an EXACT resource-id match fails. The token is extracted
        and turned into a full-match regular expression:
        - forme exacte `@resource-id="com...:id/x"` → `com\\.\\.\\.:id/x` (échappé)
        - containment form -> a pattern that replicates the containment
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

        Robust to the containment form (see _resource_id_pattern). It replaces the old naive
        extraction, which returned an empty resource-id, and therefore zero matches, for the
        sélecteurs en forme contains. API UiObject identique (.exists/.count/[i]/.get_text()).
        """
        raw_device = self.device._device if hasattr(self.device, '_device') else self.device

        pattern = self._resource_id_pattern(selectors)
        if pattern:
            found = raw_device(resourceIdMatches=pattern)
            if found.exists:
                return found

        # No resource-id in the list, or the one there is dead on this version: walk the
        # selectors as xpaths instead. Every A2 anchor is structural or text-based and carries no
        # id at all, so without this fallback a repaired catalogue entry stays invisible to every
        # caller of this function — which is most of the inbox.
        elements = first_matching(raw_device, selectors)
        if not elements:
            return None
        return _XPathCollection(elements)
    
    # ==========================================================================
    # INBOX NAVIGATION
    # ==========================================================================
    
    def is_on_inbox_page(self) -> bool:
        """Check if currently on the Inbox page."""
        return self._element_exists(self.inbox_selectors.inbox_title, timeout=2)
    
    def is_showing_people_suggestions(self) -> bool:
        """Is the Messages tab rendering follow suggestions instead of the conversation list?

        The title says "Messages" either way, so `is_on_inbox_page` cannot tell them apart, and a
        reader landing here finds no conversation and reports an EMPTY INBOX -- a lie the operator
        has no way to question. A cold app restart brought the real list back, which is why the
        bridges, which always restart, never showed it.
        """
        return self._element_exists(self.inbox_selectors.people_suggestions, timeout=1)

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

        Uses the language-aware selectors rather than hardcoded titles: otherwise the
        detection fails as soon as the app is not in English.
        """
        notifications = []

        # (language-aware selectors, notification type, stable label)
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
            # (pattern match: robust to the containment form, see _find_all_by_rid)
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
        """Open the dedicated new-followers page from the messages tab.

        Navigates to the inbox, then taps the new-followers section or its see-all entry.
        Language-aware selectors, filtered at startup.
        """
        if not self.navigate_to_inbox():
            self.logger.warning("Inbox inatteignable -> nouveaux followers")
            return False

        # The section and its see-all entry lead to the same dedicated page
        if self._find_and_click(self.inbox_selectors.new_followers_section, timeout=3):
            time.sleep(1)
            return self._is_on_new_followers_page()

        if self._find_and_click(self.inbox_selectors.see_all_button, timeout=2):
            time.sleep(1)
            return self._is_on_new_followers_page()

        self.logger.warning("Section « Nouveaux followers » introuvable")
        return False

    def _is_on_new_followers_page(self) -> bool:
        """Heuristic: the dedicated page is up when follower items are rendered."""
        return self._element_exists(self.inbox_selectors.new_followers_page_item, timeout=2)

    def get_new_followers(self, max_items: int = 50) -> List[Dict[str, Any]]:
        """Scrape the new-followers list from its dedicated page, WITHOUT acting.

        Returns:
            List of {username, activity, can_follow_back}
        """
        followers: List[Dict[str, Any]] = []

        try:
            # Pattern match: robust to the containment form of the selectors
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

                    # The follow-back button exists only when we do not already follow them
                    can_follow_back = self._element_exists(
                        self.inbox_selectors.follow_back_for_username(name), timeout=1
                    )

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
        """Tap the follow-back button on the item of `username`.

        The selector is built dynamically and scoped to that item, so it never taps another
        follower's button.
        """
        username = self._clean_username(username)
        if not username:
            return False

        selectors = self.inbox_selectors.follow_back_for_username(username)
        if not self._find_and_click(selectors, timeout=3):
            self.logger.warning(f"« Suivre en retour » introuvable pour {username}")
            return False

        # Having clicked is not having followed. Measured on device: the tap landed on the right
        # button, this function returned True, and the button was still there after a COLD
        # RELOAD of the page -- the follow had not happened. A caller that records a follow on
        # that word writes a fact no screen supports, and the next pass then skips the profile
        # as already handled.
        time.sleep(1.5)
        if self._element_exists(selectors, timeout=2):
            self.logger.warning(
                f"« Suivre en retour » toujours present pour {username} — suivi NON confirme"
            )
            return False

        self.logger.info(f"Suivi en retour : {username}")
        return True

    # ==========================================================================
    # CONVERSATIONS NON-RÉPONDUES (Phase 2 inbox v2)
    # ==========================================================================

    def get_inbox_conversations(self, max_items: int = 30) -> List[Dict[str, Any]]:
        """Scrape the inbox conversations, flagging the unanswered ones.

        Reads the username and the last-message preview, paired by index, and classifies
        `unreplied=True` quand l'aperçu n'indique PAS qu'on a parlé en dernier (préfixes
        them. The message-requests row is excluded.

        Returns:
            List of {username, preview, unreplied}
        """
        conversations: List[Dict[str, Any]] = []

        try:
            username_elements = self._find_all_by_rid(self.inbox_selectors.conversation_username)
            if username_elements is None or not username_elements.exists:
                self.logger.debug("Aucune conversation trouvée")
                return conversations

            preview_elements = self._find_all_by_rid(self.inbox_selectors.conversation_last_message)
            preview_count = (
                preview_elements.count if preview_elements is not None and preview_elements.exists else 0
            )

            sent_markers = self.inbox_selectors.we_sent_last_markers
            request_markers = self.inbox_selectors.message_requests_row_markers
            count = min(username_elements.count, max_items)

            for i in range(count):
                try:
                    name = self._clean_username(username_elements[i].get_text())
                    if not name:
                        continue

                    # Exclude the message-requests row
                    low_name = name.lower()
                    if any(m in low_name for m in request_markers):
                        continue

                    preview = ''
                    if i < preview_count:
                        try:
                            preview = self._clean_username(preview_elements[i].get_text())
                        except Exception:
                            preview = ''

                    we_sent_last = any(preview.startswith(m) for m in sent_markers)
                    conversations.append({
                        'username': name,
                        'preview': preview,
                        'unreplied': not we_sent_last,
                    })
                except Exception as e:
                    self.logger.debug(f"Erreur parsing conversation {i}: {e}")
                    continue

        except Exception as e:
            self.logger.warning(f"Erreur scrape conversations: {e}")

        return conversations

    # ==========================================================================
    # DEMANDES DE MESSAGES (Phase 3 inbox v2)
    # ==========================================================================

    def open_message_requests_page(self) -> bool:
        """Open the dedicated message-requests page from the messages tab."""
        if not self.navigate_to_inbox():
            self.logger.warning("Inbox inatteignable -> demandes de messages")
            return False

        if self._find_and_click(self.inbox_selectors.message_requests_section, timeout=3):
            time.sleep(1)
            return self._is_on_message_requests_page()

        self.logger.warning("Entrée « Demandes de messages » introuvable")
        return False

    def _is_on_message_requests_page(self) -> bool:
        """Heuristic: the requests page is up when its title OR request items are present."""
        return (
            self._element_exists(self.inbox_selectors.message_requests_page_title, timeout=2)
            or self._element_exists(self.inbox_selectors.message_request_item, timeout=1)
        )

    def get_message_requests(self, max_items: int = 30) -> List[Dict[str, Any]]:
        """Scrape the message requests from their dedicated page, WITHOUT acting.

        Returns:
            List of {username, preview, timestamp}
        """
        requests: List[Dict[str, Any]] = []
        try:
            username_elements = self._find_all_by_rid(self.inbox_selectors.message_request_username)
            if username_elements is None or not username_elements.exists:
                self.logger.debug("Aucune demande de message trouvée")
                return requests

            preview_elements = self._find_all_by_rid(self.inbox_selectors.message_request_preview)
            preview_count = (
                preview_elements.count if preview_elements is not None and preview_elements.exists else 0
            )
            ts_elements = self._find_all_by_rid(self.inbox_selectors.message_request_timestamp)
            ts_count = ts_elements.count if ts_elements is not None and ts_elements.exists else 0

            count = min(username_elements.count, max_items)
            for i in range(count):
                try:
                    name = self._clean_username(username_elements[i].get_text())
                    if not name:
                        continue
                    preview = self._clean_username(preview_elements[i].get_text()) if i < preview_count else ''
                    timestamp = self._clean_username(ts_elements[i].get_text()) if i < ts_count else ''
                    requests.append({'username': name, 'preview': preview, 'timestamp': timestamp})
                except Exception as e:
                    self.logger.debug(f"Erreur parsing demande {i}: {e}")
                    continue
        except Exception as e:
            self.logger.warning(f"Erreur scrape demandes: {e}")
        return requests

    def open_request(self, username: str) -> bool:
        """Open the message request of `username`, tapping the item scoped to that name."""
        username = self._clean_username(username)
        if not username:
            return False
        selectors = self.inbox_selectors.message_request_by_username(username)
        if self._find_and_click(selectors, timeout=3):
            time.sleep(1)
            return True
        self.logger.warning(f"Demande introuvable pour {username}")
        return False

    def accept_request(self) -> bool:
        """Accept the open request, and check the acceptance actually went through.

        Reporting the click is not reporting the outcome — the same shape that made
        `send_message` and `follow_back` claim work they had not done. Accepting replaces the
        Accept/Delete pair with the conversation composer, so the pair must be GONE afterwards.
        """
        if not self._find_and_click(self.inbox_selectors.accept_request_button, timeout=3):
            self.logger.warning("Bouton « Accepter » introuvable")
            return False

        time.sleep(1.5)
        if self._element_exists(self.inbox_selectors.accept_request_button, timeout=2):
            self.logger.warning("Le bouton « Accepter » est toujours la — acceptation NON confirmee")
            return False

        self.logger.info("Demande acceptée")
        return True

    def decline_request(self) -> bool:
        """Decline and delete the open request, and check it is gone.

        TikTok may raise a confirmation over the delete; if the pair is still on screen the
        request has NOT been declined, whatever the click reported.
        """
        if not self._find_and_click(self.inbox_selectors.decline_request_button, timeout=3):
            self.logger.warning("Bouton « Supprimer/Refuser » introuvable")
            return False

        # TikTok asks again ("Supprimer ce message ?"). Measured on device: without confirming,
        # the request stays AND the dialog blocks every later navigation.
        time.sleep(1.0)
        if self._find_and_click(self.inbox_selectors.decline_request_confirm_button, timeout=2):
            self.logger.debug("Confirmation de suppression validee")

        time.sleep(1.5)
        if self._element_exists(self.inbox_selectors.decline_request_button, timeout=2):
            self.logger.warning("Le bouton « Supprimer » est toujours la — refus NON confirme")
            return False

        self.logger.info("Demande refusée")
        return True

    # ==========================================================================
    # ACTIVITÉ / NOTIFICATIONS SYSTÈME (Phase 4 inbox v2) — lecture seule
    # ==========================================================================

    def get_inbox_notifications(self, max_items: int = 20) -> List[Dict[str, Any]]:
        """Scrape the activity and system-notification sections of the inbox (READ ONLY).

        Each section is one item carrying a title and a preview. The new-followers section is
        excluded. No device action.

        Returns:
            List of {title, preview, category}
        """
        notifications: List[Dict[str, Any]] = []
        try:
            title_elements = self._find_all_by_rid(self.inbox_selectors.section_title)
            if title_elements is None or not title_elements.exists:
                self.logger.debug("Aucune section de notification trouvée")
                return notifications

            preview_elements = self._find_all_by_rid(self.inbox_selectors.notification_subtitle)
            preview_count = (
                preview_elements.count if preview_elements is not None and preview_elements.exists else 0
            )

            nf_markers = self.inbox_selectors.new_followers_title_markers
            act_markers = self.inbox_selectors.activity_title_markers
            sys_markers = self.inbox_selectors.system_title_markers
            count = min(title_elements.count, max_items)

            for i in range(count):
                try:
                    title = self._clean_username(title_elements[i].get_text())
                    if not title:
                        continue
                    low = title.lower()
                    if any(m in low for m in nf_markers):
                        continue  # nouveaux followers -> phase 1
                    if any(m in low for m in act_markers):
                        category = 'activity'
                    elif any(m in low for m in sys_markers):
                        category = 'system'
                    else:
                        category = 'other'
                    preview = self._clean_username(preview_elements[i].get_text()) if i < preview_count else ''
                    notifications.append({'title': title, 'preview': preview, 'category': category})
                except Exception as e:
                    self.logger.debug(f"Erreur parsing notification {i}: {e}")
                    continue
        except Exception as e:
            self.logger.warning(f"Erreur scrape notifications: {e}")
        return notifications

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
            # (pattern match: robust to the containment form, see _find_all_by_rid)
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
                            if not self._human_tap_bounds(elem):
                                elem.click()
                            time.sleep(1)
                            return self._settled_in_conversation()
                    except Exception as e:
                        self.logger.debug(f"Error checking element {i}: {e}")
                        continue
            
            # Fallback: try XPath with exact match
            selector = self.inbox_selectors.conversation_username_by_text(name)
            if self._find_and_click([selector], timeout=2):
                time.sleep(1)
                return self._settled_in_conversation()
                
        except Exception as e:
            self.logger.warning(f"Error clicking conversation: {e}")
        
        self.logger.warning(f"Conversation not found: {name}")
        return False
    
    def scroll_inbox_to_top(self, max_swipes: int = 5) -> bool:
        """Bring the inbox back to its top, where the notification sections live.

        Measured on device: `read_notifications` returned an EMPTY list whenever another inbox
        workflow had run first. Nothing was broken -- the sections had simply scrolled off, and
        `_ensure_on_inbox` answers yes as soon as the title is present, whatever the scroll
        position. The caller then reported "no activity" for an account that had some.

        Stops as soon as the sections are visible, so a first read costs nothing.
        """
        for _ in range(max_swipes):
            if self._element_exists(self.inbox_selectors.section_title, timeout=1):
                return True
            self._scroll_up()
            time.sleep(0.6)
        return self._element_exists(self.inbox_selectors.section_title, timeout=1)

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

    def _settled_in_conversation(self) -> bool:
        """Are we in the conversation, once whatever TikTok raised on top is gone?

        Measured on device (43.1.4): opening a conversation raised a MODAL "read status" sheet
        that replaced the whole hierarchy. `is_in_conversation` looks for the composer, the sheet
        covered it, and `click_conversation` reported a failure for an open that had SUCCEEDED —
        the same shape as the message-requests page that had landed and said it had not. Nothing
        downstream could recover: the conversation was simply declared unreachable.
        """
        if self.is_in_conversation():
            return True
        if not self.close_conversation_interstitial():
            return False
        time.sleep(1)
        return self.is_in_conversation()
    
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
    
    def _bubble_is_ours(self, element) -> bool:
        """Did WE write this bubble? Read from where it sits, not from who it says wrote it.

        TikTok's conversation gives no sender: for months every message came back
        `is_sent: False`, so any table built on the reader stated we had never answered anybody.
        The alignment is the answer, and it was measured rather than assumed — the SAME two
        messages captured from BOTH phones, on 43.1.4 and 46.6.3, landed on opposite sides:

            43.1.4 (screen 1440)  ours cx=1043 (right) · theirs cx=337 (left)
            46.6.3 (screen 1080)  ours cx= 921 (right) · theirs cx=398 (left)

        Same resource-id for both directions on each version, so there is no per-direction id to
        key on; the geometry survives the version bump that the id does not.

        Unreadable bounds return False. That is the safe way round: a message wrongly called
        theirs costs a duplicate read, one wrongly called ours would claim an answer we never
        sent.
        """
        try:
            bounds = element.info.get('bounds') or {}
            left, right = bounds.get('left'), bounds.get('right')
            if left is None or right is None:
                return False
            width = self.device.get_screen_size()[0] if hasattr(self.device, 'get_screen_size') else 0
            if not width:
                raw = self.device._device if hasattr(self.device, '_device') else self.device
                width = raw.window_size()[0]
            return bool(width) and ((left + right) / 2) > (width / 2)
        except Exception as e:
            self.logger.debug(f"Bubble side unreadable: {e}")
            return False

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
            # (pattern match: robust to the containment form, see _find_all_by_rid)
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
                                'is_sent': self._bubble_is_ours(elem),
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
        self.logger.debug(f"⌨️ Typing message ({len(text)} chars)...")
        
        # Click on input field first
        if not self._find_and_click(self.conversation_selectors.message_input_field, timeout=3):
            self.logger.warning("Message input field not found")
            return False
        
        time.sleep(0.3)
        
        # Clear, then type, both through the Taktik keyboard.
        #
        # The clear used to go through `device.clear_text()`, which on Android 14+ raises: the
        # uiautomator2 agent implements it with `InputManager.getInstance`, a method Android
        # removed. Measured on both lab phones (Android 16) — the call raised, this function
        # returned False, and no TikTok DM could be sent at all.
        #
        # Dropping the clear was tried and is wrong: a failed send leaves its text in the
        # composer, so the next attempt CONCATENATES. Measured too — "Test TAKTIKTest TAKTIK"
        # went out. `_clear_text_with_taktik_keyboard` broadcasts to our own IME and touches none
        # of the removed API, which is what the search path has been using all along.
        self._clear_text_with_taktik_keyboard()
        time.sleep(0.2)

        device_id = getattr(self.device, "device_id", None) or getattr(self.device, "serial", None)
        if device_id:
            try:
                from taktik.core.shared.input.taktik_keyboard import type_text_human

                if type_text_human(str(device_id), text):
                    time.sleep(0.3)
                    return True
                self.logger.warning("Taktik Keyboard failed, falling back to send_keys")
            except Exception as exc:
                self.logger.warning(f"Taktik Keyboard unavailable ({exc}), falling back")

        try:
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
        
        # What the composer holds BEFORE, so "did it leave" is answerable afterwards.
        pending = self._composer_text()

        clicked = self._find_and_click(self.conversation_selectors.send_button, timeout=2)
        if not clicked:
            try:
                self.device.press("enter")
                clicked = True
            except Exception as e:
                self.logger.warning(f"Failed to send message: {e}")
                return False
        self._human_like_delay('click')

        # A send is confirmed by the composer EMPTYING, not by the click landing. This used to
        # return True on either path, so a message still sitting on screen was recorded as sent —
        # measured on device: True returned, text still in the field.
        if pending:
            for _ in range(6):
                if self._composer_text() != pending:
                    return True
                time.sleep(0.5)
            self.logger.warning(
                "Send reported no error but the composer still holds the message — not sent")
            return False

        # Nothing was in the composer to begin with: nothing to confirm, and nothing to claim.
        return clicked

    def _composer_text(self) -> str:
        """Whatever the message field currently holds, or '' when it cannot be read."""
        try:
            for selector in self.conversation_selectors.message_input_field:
                element = self.device.xpath(selector)
                if element.exists:
                    return (element.get_text() or "").strip()
        except Exception:
            pass
        return ""
    
    def is_conversation_with(self, username: str) -> bool:
        """Is the open conversation the one with `username`?

        A send answers "did it leave", never "did it reach the right person" — and a navigation
        that drifts one row is enough to write into someone else's thread. That happened during
        this survey: a request list shifted between two runs and a reply went to a stranger.

        Compared on the conversation HEADER, loosely: TikTok shows the display name there, and a
        caller usually holds the handle. Returns False when the header cannot be read, so an
        unverifiable conversation is never treated as verified.
        """
        wanted = self._clean_username(username).lower()
        if not wanted:
            return False
        header = (self.get_conversation_info().get("name") or "").lower()
        header = self._clean_username(header)
        if not header:
            return False
        return wanted in header or header in wanted

    def send_text_message_to(self, username: str, text: str) -> bool:
        """Send `text`, but only into the conversation with `username`.

        The guarded form of `send_text_message`. Any workflow that navigates before writing
        should use this one: the unguarded version cannot tell whose thread it is in.
        """
        if not self.is_conversation_with(username):
            info = self.get_conversation_info().get("name")
            self.logger.error(
                f"Refusing to send: conversation header is {info!r}, expected @{username}")
            return False
        return self.send_text_message(text)

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
    
    def close_conversation_interstitial(self) -> bool:
        """Dismiss whatever TikTok raised ON TOP of the conversation.

        The sticker popup is one of several. Opening a conversation can also raise a MODAL
        bottom sheet (read receipts) that replaces the entire hierarchy — back button, header
        and composer all gone — so nothing downstream can tell it is there.
        """
        return self._find_and_click(
            self.conversation_selectors.close_interstitial,
            timeout=1
        )

    def close_sticker_suggestion(self) -> bool:
        """Close the sticker suggestion popup in new conversations."""
        return self.close_conversation_interstitial()
    
