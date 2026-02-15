#!/usr/bin/env python3
"""
DM Bridge for TAKTIK Desktop
Unified bridge for reading and sending Instagram DM messages.

Usage:
    python dm_bridge.py read <device_id> <limit>
    python dm_bridge.py send <device_id> <username> <message>
"""

import sys
import json
import os
import time
import random
import re

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.keyboard import KeyboardService
from bridges.instagram.base import logger, InstagramBridgeBase
from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS



class DMBridge(InstagramBridgeBase):
    """Bridge for DM operations between TAKTIK Desktop and Instagram."""
    
    def __init__(self, device_id: str):
        super().__init__(device_id)
        self._keyboard = KeyboardService(device_id)
    
    def navigate_to_dm_inbox(self) -> bool:
        """Navigate to DM inbox using multiple methods."""
        logger.info("Navigating to DM inbox...")
        
        # Method 1: Bottom tab bar direct_tab by resource-id (uiautomator2 selector)
        # In Instagram 410+, DM is in the bottom tab bar with resource-id="direct_tab" and content-desc="Message"
        logger.info("Trying method 1: direct_tab resource-id (uiautomator2)...")
        dm_tab = self.device(resourceId="com.instagram.android:id/direct_tab")
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            logger.info("Navigated via direct_tab (uiautomator2)")
            return True
        
        # Method 2: Bottom tab bar by content-desc "Message"
        logger.info("Trying method 2: content-desc 'Message'...")
        for desc in ["Message", "Messages", "Direct", "Messenger"]:
            btn = self.device(description=desc)
            if btn.exists:
                btn.click()
                time.sleep(2)
                logger.info(f"Navigated via content-desc: {desc}")
                return True
        
        # Method 3: DM_SELECTORS.direct_tab (xpath)
        logger.info("Trying method 3: direct_tab xpath...")
        dm_tab = self.device.xpath(DM_SELECTORS.direct_tab)
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            logger.info("Navigated via direct_tab xpath")
            return True
        
        # Method 4: content-desc xpath selectors from DM_SELECTORS
        logger.info("Trying method 4: DM_SELECTORS content-desc xpaths...")
        for selector in DM_SELECTORS.direct_tab_content_desc:
            dm_btn = self.device.xpath(selector)
            if dm_btn.exists:
                dm_btn.click()
                time.sleep(2)
                logger.info(f"Navigated via content-desc xpath: {selector}")
                return True
        
        # Method 5: Messenger icon in action bar (older Instagram versions)
        logger.info("Trying method 5: action_bar_inbox_button...")
        messenger = self.device(resourceId="com.instagram.android:id/action_bar_inbox_button")
        if messenger.exists:
            messenger.click()
            time.sleep(2)
            logger.info("Navigated via messenger icon")
            return True
        
        # Method 6: descriptionContains variations
        logger.info("Trying method 6: descriptionContains variations...")
        for desc in ["Message", "Messenger", "Inbox", "Boîte de réception", "Envoyer un message"]:
            btn = self.device(descriptionContains=desc)
            if btn.exists:
                btn.click()
                time.sleep(2)
                # Verify we actually reached DM inbox
                inbox = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
                if inbox.exists:
                    logger.info(f"Navigated via descriptionContains: {desc}")
                    return True
                else:
                    logger.warning(f"Clicked '{desc}' but did not reach DM inbox, pressing back")
                    self.device.press("back")
                    time.sleep(1)
        
        # Method 7: Try by class and position (ImageView in action bar) - OLD versions only
        logger.info("Trying method 7: ImageView in action bar...")
        action_bar = self.device(resourceId="com.instagram.android:id/action_bar_container")
        if action_bar.exists:
            images = action_bar.child(className="android.widget.ImageView", clickable=True)
            if images.count > 0:
                images[images.count - 1].click()
                time.sleep(2)
                inbox = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
                if inbox.exists:
                    logger.info("Navigated via action bar ImageView")
                    return True
                else:
                    logger.warning("Clicked action bar ImageView but did not reach DM inbox, pressing back")
                    self.device.press("back")
                    time.sleep(1)
        
        logger.error("Cannot find DM button - all methods failed")
        return False
    
    def _ensure_primary_tab(self):
        """Ensure we're on the Primary tab in DM inbox."""
        # Look for Primary tab and click it
        primary_tab = self.device(textContains="Primary")
        if primary_tab.exists:
            logger.info("Clicking Primary tab to ensure we're in the right section")
            primary_tab.click()
            time.sleep(1)
            return True
        
        # Alternative: look for tab with content-desc containing Primary
        primary_tab = self.device(descriptionContains="Primary")
        if primary_tab.exists:
            logger.info("Clicking Primary tab (via description)")
            primary_tab.click()
            time.sleep(1)
            return True
        
        logger.warning("Primary tab not found")
        return False
    
    def _scroll_to_top_of_inbox(self):
        """Scroll to the top of the inbox list and ensure we're on Primary tab."""
        logger.info("Scrolling to top of inbox...")
        
        # Ensure we're on Primary tab
        self._ensure_primary_tab()
        
        # Scroll up by swiping DOWN (pull down to reveal content above)
        # Use the lower part of the screen to avoid the tabs area
        for _ in range(3):
            self.device.swipe(
                self.screen_width // 2, int(self.screen_height * 0.55),
                self.screen_width // 2, int(self.screen_height * 0.85),
                duration=0.2
            )
            time.sleep(0.3)
        
        time.sleep(0.5)
    
    def _search_conversation_in_visible_list(self, username_lower: str) -> bool:
        """Search for a conversation in the currently visible inbox list."""
        inbox_items = self.device(resourceId="com.instagram.android:id/row_inbox_container")
        
        for i in range(min(inbox_items.count, 20)):
            try:
                item = inbox_items[i]
                username_elem = item.child(resourceId="com.instagram.android:id/row_inbox_username")
                if username_elem.exists:
                    item_username = username_elem.get_text()
                    if item_username:
                        item_username_lower = item_username.lower().strip()
                        # Exact match (case-insensitive) or partial match
                        if item_username_lower == username_lower or username_lower in item_username_lower or item_username_lower in username_lower:
                            logger.info(f"Found conversation: {item_username}")
                            item.click()
                            time.sleep(2)
                            return True
            except:
                continue
        return False
    
    def open_conversation(self, username: str) -> bool:
        """Open a specific conversation by username."""
        logger.info(f"Opening conversation with: {username}")
        
        # Normalize username for comparison (case-insensitive, strip whitespace)
        username_lower = username.lower().strip()
        
        # Method 1: Search in visible inbox items by row_inbox_username
        if self._search_conversation_in_visible_list(username_lower):
            return True
        
        # Method 2: Search all row_inbox_username elements directly
        logger.info("Trying direct search on all row_inbox_username elements...")
        username_elems = self.device(resourceId="com.instagram.android:id/row_inbox_username")
        for i in range(min(username_elems.count, 20)):
            try:
                elem = username_elems[i]
                item_username = elem.get_text()
                if item_username:
                    item_username_lower = item_username.lower().strip()
                    if item_username_lower == username_lower or username_lower in item_username_lower or item_username_lower in username_lower:
                        logger.info(f"Found via direct username element: {item_username}")
                        elem.click()
                        time.sleep(2)
                        return True
            except:
                continue
        
        # Method 3: Try textContains with original username (handles exact text)
        user_elem = self.device(textContains=username)
        if user_elem.exists:
            logger.info(f"Found via textContains: {username}")
            user_elem.click()
            time.sleep(2)
            return True
        
        # Method 4: Scroll down progressively and search (up to 5 scrolls)
        for scroll_attempt in range(5):
            logger.info(f"Scrolling down to find conversation (attempt {scroll_attempt + 1}/5)...")
            self.device.swipe(
                self.screen_width // 2, int(self.screen_height * 0.7),
                self.screen_width // 2, int(self.screen_height * 0.3),
                duration=0.3
            )
            time.sleep(1)
            
            if self._search_conversation_in_visible_list(username_lower):
                return True
        
        logger.error(f"Conversation with {username} not found after scrolling")
        return False
    
    def _simulate_typing_delay(self, text: str):
        """
        Simulate human typing time without actually typing char by char.
        This avoids issues with emojis and special characters while still
        appearing natural (not instant).
        """
        # Calculate realistic typing time: ~40-80ms per character for a fast typer
        # But cap it to avoid very long waits
        char_count = len(text)
        
        # Base time: 30-50ms per character
        base_time = char_count * random.uniform(0.03, 0.05)
        
        # Add some "thinking" time at the start (0.5-1.5s)
        thinking_time = random.uniform(0.5, 1.5)
        
        # Cap total time at 5 seconds max
        total_time = min(base_time + thinking_time, 5.0)
        
        logger.info(f"Simulating typing for {total_time:.1f}s ({char_count} chars)...")
        time.sleep(total_time)
    
    def send_message(self, message: str) -> bool:
        """Send a message in the current conversation with human-like timing."""
        logger.info("Sending message...")
        
        # Find message input - try multiple selectors
        msg_input = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
        if not msg_input.exists:
            logger.info("Trying alternative input selector...")
            msg_input = self.device(resourceId="com.instagram.android:id/message_content")
        if not msg_input.exists:
            logger.info("Trying EditText class...")
            msg_input = self.device(className="android.widget.EditText")
        if not msg_input.exists:
            logger.info("Trying hint text...")
            msg_input = self.device(textContains="Message")
        
        if not msg_input.exists:
            logger.error("Message input not found")
            return False
        
        logger.info(f"Found message input: {msg_input.info}")
        
        # Click on input field
        msg_input.click()
        time.sleep(random.uniform(0.5, 0.8))
        
        # Simulate typing delay (looks like we're typing)
        self._simulate_typing_delay(message)
        
        # Use Taktik Keyboard for reliable input (supports emojis, special chars, etc.)
        if self._keyboard.type_text(message):
            logger.info("Text set via Taktik Keyboard")
        else:
            # Fallback to set_text or send_keys
            logger.warning("Taktik Keyboard failed, trying fallback methods...")
            try:
                msg_input.set_text(message)
                logger.info("Text set via set_text")
            except Exception as e:
                logger.warning(f"set_text failed: {e}, trying send_keys...")
                try:
                    msg_input.send_keys(message)
                    logger.info("Text set via send_keys")
                except Exception as e2:
                    logger.error(f"send_keys also failed: {e2}")
                    return False
        
        time.sleep(random.uniform(0.3, 0.5))  # Brief pause before sending
        
        # Find send button - try multiple selectors
        send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button_container")
        logger.info(f"Send button (container): exists={send_btn.exists}")
        
        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button")
            logger.info(f"Send button (direct): exists={send_btn.exists}")
        
        if not send_btn.exists:
            send_btn = self.device(description="Envoyer")
            logger.info(f"Send button (Envoyer): exists={send_btn.exists}")
        
        if not send_btn.exists:
            send_btn = self.device(description="Send")
            logger.info(f"Send button (Send): exists={send_btn.exists}")
        
        if not send_btn.exists:
            send_btn = self.device(description="Send message")
            logger.info(f"Send button (Send message): exists={send_btn.exists}")
        
        if not send_btn.exists:
            # Try to find any clickable element near the input that could be send
            send_btn = self.device(resourceId="com.instagram.android:id/send_button")
            logger.info(f"Send button (send_button): exists={send_btn.exists}")
        
        if send_btn.exists:
            logger.info(f"Clicking send button: {send_btn.info}")
            send_btn.click()
            time.sleep(1)
            logger.info("Message sent!")
            return True
        
        logger.error("Send button not found - dumping UI elements for debugging")
        # Log all clickable elements for debugging
        try:
            clickables = self.device(clickable=True)
            for i in range(min(clickables.count, 20)):
                elem = clickables[i]
                info = elem.info
                logger.info(f"Clickable {i}: {info.get('resourceId', '')} - {info.get('contentDescription', '')} - {info.get('className', '')}")
        except:
            pass
        
        return False
    
    def read_conversations(self, limit: int) -> list:
        """Read DM conversations."""
        conversations = []
        processed_usernames = set()  # Track by inbox_username (lowercase)
        processed_real_usernames = set()  # Track by real_username (lowercase) to catch duplicates
        conversations_read = 0
        scroll_count = 0
        max_scrolls = 10
        
        while conversations_read < limit and scroll_count < max_scrolls:
            threads = self.device.xpath(DM_SELECTORS.thread_container).all()
            
            if not threads:
                logger.warning("No threads found")
                break
            
            # Trier les threads par position verticale (top) pour les traiter dans l'ordre
            threads_with_pos = []
            for thread in threads:
                try:
                    bounds = thread.info.get('bounds', {})
                    top = bounds.get('top', 0)
                    threads_with_pos.append((top, thread))
                except:
                    continue
            threads_with_pos.sort(key=lambda x: x[0])
            
            new_conversations_in_scroll = 0  # Track if we found new conversations in this scroll
            
            for thread_top, thread in threads_with_pos:
                if conversations_read >= limit:
                    break
                
                try:
                    thread_info = thread.info
                    content_desc = thread_info.get('contentDescription', '')
                    
                    # Extract username
                    username = "Unknown"
                    if content_desc:
                        parts = content_desc.split(',')
                        if parts:
                            username = parts[0].strip()
                    
                    # Try via resource-id
                    try:
                        username_elem = self.device(resourceId="com.instagram.android:id/row_inbox_username")
                        if username_elem.exists:
                            for idx in range(username_elem.count):
                                elem = username_elem[idx]
                                bounds = elem.info.get('bounds', {})
                                thread_bounds = thread_info.get('bounds', {})
                                if bounds and thread_bounds:
                                    if (bounds.get('top', 0) >= thread_bounds.get('top', 0) and 
                                        bounds.get('bottom', 0) <= thread_bounds.get('bottom', 0)):
                                        username = elem.get_text() or username
                                        break
                    except:
                        pass
                    
                    # Check if already processed (case-insensitive)
                    # Gérer les noms tronqués: "Here come the Grannies! ...." vs "Here come the Grannies! 💙🧡"
                    username_lower = username.lower().strip()
                    username_base = username_lower.rstrip('.').strip()  # Enlever les "..." de troncature
                    
                    already_processed = False
                    for processed in processed_usernames:
                        processed_base = processed.rstrip('.').strip()
                        # Match exact ou l'un est préfixe de l'autre (troncature)
                        if (username_base == processed_base or 
                            username_base.startswith(processed_base) or 
                            processed_base.startswith(username_base)):
                            already_processed = True
                            break
                    
                    if already_processed:
                        logger.debug(f"Skipping already processed: {username}")
                        continue
                    
                    logger.info(f"Opening conversation: {username}")
                    thread.click()
                    time.sleep(2)
                    
                    header_title = self.device(resourceId="com.instagram.android:id/header_title")
                    if not header_title.exists(timeout=3):
                        logger.warning(f"Could not open conversation with {username}")
                        # Vérifier si on est toujours dans l'inbox (pas besoin de back)
                        inbox_list = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
                        if not inbox_list.exists:
                            # On est quelque part d'autre, revenir à l'inbox
                            back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
                            if back_btn.exists:
                                back_btn.click()
                            else:
                                self.device.press("back")
                            time.sleep(1)
                        continue
                    
                    real_username = header_title.get_text() or username
                    real_username_lower = real_username.lower().strip()
                    
                    # Double-check: if real_username was already processed, skip
                    if real_username_lower in processed_real_usernames:
                        logger.info(f"Skipping duplicate (real_username already seen): {real_username}")
                        back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
                        if back_btn.exists:
                            back_btn.click()
                        else:
                            self.device.press("back")
                        time.sleep(1)
                        continue
                    
                    # Mark both as processed
                    processed_usernames.add(username_lower)
                    processed_real_usernames.add(real_username_lower)
                    
                    # Check if group or broadcast channel
                    is_group = False
                    can_reply = True
                    header_subtitle = self.device(resourceId="com.instagram.android:id/header_subtitle")
                    if header_subtitle.exists:
                        try:
                            subtitle_text = header_subtitle.get_text() or ''
                            # Récupérer aussi le contentDescription (content-desc dans le XML)
                            subtitle_info = header_subtitle.info
                            subtitle_desc = subtitle_info.get('contentDescription', '') or ''
                            combined = (subtitle_text + ' ' + subtitle_desc).lower()
                            
                            # Détecter les groupes: "X membres", "X members", "X.XK members", etc.
                            is_group_pattern = bool(re.search(r'\d+\.?\d*k?\s*(membres|members)', combined))
                            
                            if is_group_pattern or 'membres' in combined or 'members' in combined:
                                is_group = True
                                logger.info(f"Groupe détecté via subtitle: {combined[:50]}")
                        except Exception as e:
                            logger.debug(f"Erreur détection groupe via subtitle: {e}")
                    
                    # Vérifier si on peut répondre (composer présent)
                    composer = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
                    if not composer.exists:
                        # Pas de composer = on ne peut pas répondre (groupe broadcast, channel, etc.)
                        can_reply = False
                        if not is_group:
                            # Si pas détecté comme groupe mais pas de composer, c'est probablement un broadcast channel
                            is_group = True
                            logger.info(f"Broadcast channel détecté (pas de composer): {real_username}")
                    
                    # Collect messages
                    messages = self._collect_messages()
                    
                    # Vérifier si le dernier message vient de nous
                    # Si oui, on ne peut pas répondre (on se répondrait à nous-mêmes)
                    last_message_is_ours = False
                    if messages:
                        last_msg = messages[-1]  # Dernier message (le plus récent)
                        if last_msg.get('is_sent', False):
                            last_message_is_ours = True
                            logger.info(f"Dernier message de @{real_username} est de NOUS -> can_reply=False")
                    
                    # can_reply = False si:
                    # - C'est un groupe sans composer
                    # - Le dernier message vient de nous (on ne se répond pas)
                    if last_message_is_ours:
                        can_reply = False
                    
                    conv = {
                        'username': real_username,
                        'inbox_username': username,  # Original name from inbox for reliable matching
                        'messages': messages,
                        'is_group': is_group,
                        'can_reply': can_reply,
                        'last_message_is_ours': last_message_is_ours  # Info supplémentaire pour le front
                    }
                    conversations.append(conv)
                    conversations_read += 1
                    new_conversations_in_scroll += 1
                    
                    # Send real-time update
                    print(json.dumps({
                        "type": "conversation",
                        "current": conversations_read,
                        "total": limit,
                        "conversation": conv
                    }), flush=True)
                    
                    # Go back
                    back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
                    if back_btn.exists:
                        back_btn.click()
                    else:
                        self.device.press("back")
                    time.sleep(1.5)
                    
                except Exception as e:
                    logger.error(f"Error reading conversation: {e}")
                    # Vérifier si on est dans une conversation avant de faire back
                    inbox_list = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
                    if not inbox_list.exists:
                        back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
                        if back_btn.exists:
                            back_btn.click()
                        else:
                            self.device.press("back")
                        time.sleep(1)
                    continue
            
            if conversations_read >= limit:
                break
            
            # Scroll to load more
            scroll_count += 1
            self.device.swipe(
                self.screen_width // 2, int(self.screen_height * 0.7),
                self.screen_width // 2, int(self.screen_height * 0.3),
                duration=0.3
            )
            time.sleep(1.5)
        
        return conversations
    
    def _collect_messages(self) -> list:
        """Collect messages from current conversation."""
        all_items = []
        
        # Text messages
        msg_elements = self.device(resourceId="com.instagram.android:id/direct_text_message_text_view")
        for j in range(msg_elements.count):
            try:
                msg_elem = msg_elements[j]
                msg_bounds = msg_elem.info.get('bounds', {})
                text = msg_elem.get_text()
                if not text:
                    continue
                msg_left = msg_bounds.get('left', 0)
                msg_top = msg_bounds.get('top', 0)
                # Détection envoyé/reçu: les messages reçus sont à gauche (left < 25% de l'écran)
                # Les messages envoyés sont à droite (left >= 25% de l'écran)
                # Seuil de 25% car sur un écran de 576px: messages reçus ont left~84, envoyés ont left~172+
                is_received = msg_left < self.screen_width * 0.25
                all_items.append({
                    'type': 'text',
                    'text': text,
                    'is_sent': not is_received,
                    'top': msg_top
                })
            except:
                continue
        
        # Reels
        reel_shares = self.device(resourceId="com.instagram.android:id/reel_share_item_view")
        for j in range(reel_shares.count):
            try:
                reel = reel_shares[j]
                reel_bounds = reel.info.get('bounds', {})
                reel_left = reel_bounds.get('left', 0)
                reel_top = reel_bounds.get('top', 0)
                # Même logique pour les reels: 25% de l'écran comme seuil
                is_received = reel_left < self.screen_width * 0.25
                
                title_elem = self.device(resourceId="com.instagram.android:id/title_text")
                reel_author = ""
                for k in range(title_elem.count):
                    try:
                        t = title_elem[k]
                        t_bounds = t.info.get('bounds', {})
                        if (t_bounds.get('top', 0) >= reel_bounds.get('top', 0) and
                            t_bounds.get('bottom', 0) <= reel_bounds.get('bottom', 0)):
                            reel_author = t.get_text() or ""
                            break
                    except:
                        continue
                
                all_items.append({
                    'type': 'reel',
                    'text': f"[Reel de @{reel_author}]" if reel_author else "[Reel partagé]",
                    'is_sent': not is_received,
                    'top': reel_top
                })
            except:
                continue
        
        # Sort all messages by position (top to bottom = chronological order)
        all_items.sort(key=lambda x: x['top'])
        
        # Pas de déduplication - garder TOUS les messages
        # Un même texte peut apparaître plusieurs fois (ex: smileys, réponses courtes)
        messages = []
        for msg in all_items:
            messages.append({
                'type': msg['type'],
                'text': msg['text'],
                'is_sent': msg['is_sent']
            })
        
        return messages


def cmd_read(device_id: str, limit: int):
    """Read DM conversations."""
    bridge = DMBridge(device_id)
    
    if not bridge.connect():
        print(json.dumps({"success": False, "error": "Failed to connect to device"}))
        sys.exit(1)
    
    bridge.restart_instagram()
    
    if not bridge.navigate_to_dm_inbox():
        print(json.dumps({"success": False, "error": "Cannot navigate to DM inbox"}))
        sys.exit(1)
    
    time.sleep(2)
    conversations = bridge.read_conversations(limit)
    
    print(json.dumps({
        "type": "result",
        "success": True,
        "conversations": conversations,
        "total": len(conversations)
    }))


def _ensure_dm_inbox(bridge: DMBridge) -> bool:
    """
    Ensure Instagram is open and we're in the DM inbox.
    Handles the case where the user left Instagram or navigated away.
    Returns True if we're in the inbox, False if navigation failed.
    """
    # Check if we're already in the DM inbox
    inbox = bridge.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
    if inbox.exists(timeout=2):
        logger.info("Already in DM inbox")
        bridge._ensure_primary_tab()
        return True
    
    # Check if Instagram is open at all (look for any Instagram UI element)
    ig_elements = [
        bridge.device(resourceId="com.instagram.android:id/action_bar_container"),
        bridge.device(resourceId="com.instagram.android:id/tab_bar"),
        bridge.device(resourceId="com.instagram.android:id/bottom_navigation"),
    ]
    ig_is_open = any(e.exists(timeout=1) for e in ig_elements)
    
    if ig_is_open:
        # Instagram is open but not in DM inbox — navigate there
        logger.info("Instagram is open but not in DM inbox, navigating...")
        if bridge.navigate_to_dm_inbox():
            time.sleep(2)
            bridge._ensure_primary_tab()
            bridge._scroll_to_top_of_inbox()
            return True
    
    # Instagram is not open or navigation failed — restart and navigate
    logger.info("Instagram not in DM inbox, restarting app...")
    bridge.restart_instagram()
    time.sleep(3)
    
    if not bridge.navigate_to_dm_inbox():
        logger.error("Failed to navigate to DM inbox after restart")
        return False
    
    time.sleep(2)
    bridge._ensure_primary_tab()
    bridge._scroll_to_top_of_inbox()
    return True


def cmd_send(device_id: str, username: str, message: str):
    """Send a DM message. Ensures Instagram is open and we're in DM inbox before sending."""
    bridge = DMBridge(device_id)
    
    if not bridge.connect():
        print(json.dumps({"success": False, "error": "Failed to connect to device"}))
        sys.exit(1)
    
    # Ensure Instagram is open and we're in the DM inbox
    if not _ensure_dm_inbox(bridge):
        print(json.dumps({"success": False, "error": "Cannot navigate to DM inbox"}))
        sys.exit(1)
    
    # D'abord essayer de trouver l'utilisateur à l'écran actuel (sans scroller)
    if bridge.open_conversation(username):
        pass  # Trouvé directement à l'écran
    else:
        # Pas trouvé à l'écran actuel, scroller en haut et réessayer
        logger.info(f"Utilisateur {username} non visible, scroll en haut et réessai...")
        bridge._ensure_primary_tab()
        bridge._scroll_to_top_of_inbox()
        
        if not bridge.open_conversation(username):
            print(json.dumps({"success": False, "error": f"Cannot find conversation with {username}"}))
            sys.exit(1)
    
    if bridge.send_message(message):
        # Retourner à l'inbox en cliquant sur le bouton back du header
        time.sleep(0.5)
        back_btn = bridge.device(resourceId="com.instagram.android:id/header_left_button")
        if back_btn.exists(timeout=2):
            back_btn.click()
            logger.info("Retour à l'inbox via header_left_button")
            time.sleep(1)
        else:
            # Fallback: essayer avec description "Back"
            back_btn = bridge.device(description="Back")
            if back_btn.exists(timeout=2):
                back_btn.click()
                logger.info("Retour à l'inbox via description Back")
                time.sleep(1)
            else:
                logger.warning("Bouton back non trouvé, tentative press back")
                bridge.device.press("back")
                time.sleep(1)
        
        print(json.dumps({
            "success": True,
            "username": username,
            "message": message
        }))
    else:
        print(json.dumps({"success": False, "error": "Failed to send message"}))
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False, 
            "error": "Usage: dm_bridge.py <command> [args]\n  read <device_id> <limit>\n  send <device_id> <username> <message>"
        }))
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        # Support both old format (device_id, limit) and new format (read, device_id, limit)
        if command == "read":
            if len(sys.argv) < 4:
                print(json.dumps({"success": False, "error": "Usage: dm_bridge.py read <device_id> <limit>"}))
                sys.exit(1)
            cmd_read(sys.argv[2], int(sys.argv[3]))
        
        elif command == "send":
            if len(sys.argv) < 5:
                print(json.dumps({"success": False, "error": "Usage: dm_bridge.py send <device_id> <username> <message>"}))
                sys.exit(1)
            cmd_send(sys.argv[2], sys.argv[3], sys.argv[4])
        
        elif command not in ["read", "send"] and len(sys.argv) >= 2:
            # Legacy format: dm_bridge.py <device_id> <limit>
            # Assume first arg is device_id if it's not a command
            try:
                limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
                cmd_read(command, limit)  # command is actually device_id
            except ValueError:
                print(json.dumps({"success": False, "error": f"Unknown command: {command}"}))
                sys.exit(1)
        
        else:
            print(json.dumps({"success": False, "error": f"Unknown command: {command}"}))
            sys.exit(1)
    
    except Exception as e:
        import traceback
        print(json.dumps({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
