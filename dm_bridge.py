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

# Force UTF-8 encoding for stdout/stderr to support emojis on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.core.manager import InstagramManager
from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS
from loguru import logger

# Configure loguru for UTF-8 output
logger.remove()
logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="DEBUG", colorize=False)


class DMBridge:
    """Bridge for DM operations between TAKTIK Desktop and Instagram."""
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.device_manager = None
        self.device = None
        self.screen_width = 1080
        self.screen_height = 2340
    
    def connect(self) -> bool:
        """Connect to the device."""
        logger.info(f"Connecting to device: {self.device_id}")
        self.device_manager = DeviceManager(device_id=self.device_id)
        
        if not self.device_manager.connect():
            return False
        
        self.device = self.device_manager.device
        screen_info = self.device.info
        self.screen_width = screen_info.get('displayWidth', 1080)
        self.screen_height = screen_info.get('displayHeight', 2340)
        return True
    
    def restart_instagram(self):
        """Restart Instagram for clean state."""
        instagram_manager = InstagramManager(self.device_id)
        logger.info("Restarting Instagram...")
        instagram_manager.stop()
        time.sleep(1)
        instagram_manager.launch()
        time.sleep(4)
    
    def navigate_to_dm_inbox(self) -> bool:
        """Navigate to DM inbox using multiple methods."""
        logger.info("Navigating to DM inbox...")
        
        # Method 1: DM_SELECTORS.direct_tab (xpath)
        logger.info("Trying method 1: direct_tab resource-id...")
        dm_tab = self.device.xpath(DM_SELECTORS.direct_tab)
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            logger.info("Navigated via direct_tab")
            return True
        
        # Method 2: content-desc selectors
        logger.info("Trying method 2: content-desc selectors...")
        for selector in DM_SELECTORS.direct_tab_content_desc:
            dm_btn = self.device.xpath(selector)
            if dm_btn.exists:
                dm_btn.click()
                time.sleep(2)
                logger.info(f"Navigated via content-desc: {selector}")
                return True
        
        # Method 3: Direct icon by description
        logger.info("Trying method 3: Direct icon description...")
        direct_icon = self.device(description="Direct")
        if direct_icon.exists:
            direct_icon.click()
            time.sleep(2)
            logger.info("Navigated via Direct icon")
            return True
        
        # Method 4: Messenger icon (action bar)
        logger.info("Trying method 4: action_bar_inbox_button...")
        messenger = self.device(resourceId="com.instagram.android:id/action_bar_inbox_button")
        if messenger.exists:
            messenger.click()
            time.sleep(2)
            logger.info("Navigated via messenger icon")
            return True
        
        # Method 5: Try clicking on top-right corner where DM icon usually is
        logger.info("Trying method 5: tap on DM icon position (top-right)...")
        try:
            # DM icon is typically in top-right corner of the screen
            self.device.click(self.screen_width - 80, 150)
            time.sleep(2)
            # Check if we're in DM inbox
            inbox = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
            if inbox.exists:
                logger.info("Navigated via tap on top-right")
                return True
        except:
            pass
        
        # Method 6: Try messenger description variations
        logger.info("Trying method 6: messenger description variations...")
        for desc in ["Messenger", "Messages", "Inbox", "Boîte de réception"]:
            btn = self.device(descriptionContains=desc)
            if btn.exists:
                btn.click()
                time.sleep(2)
                logger.info(f"Navigated via description: {desc}")
                return True
        
        # Method 7: Try by class and position (ImageView in action bar)
        logger.info("Trying method 7: ImageView in action bar...")
        action_bar = self.device(resourceId="com.instagram.android:id/action_bar_container")
        if action_bar.exists:
            # Find clickable ImageViews in action bar
            images = action_bar.child(className="android.widget.ImageView", clickable=True)
            if images.count > 0:
                # Usually the last one is the DM icon
                images[images.count - 1].click()
                time.sleep(2)
                inbox = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
                if inbox.exists:
                    logger.info("Navigated via action bar ImageView")
                    return True
        
        logger.error("Cannot find DM button - all methods failed")
        return False
    
    def open_conversation(self, username: str) -> bool:
        """Open a specific conversation by username."""
        logger.info(f"Opening conversation with: {username}")
        
        # First, try to find in visible inbox
        inbox_items = self.device(resourceId="com.instagram.android:id/row_inbox_container")
        
        for i in range(min(inbox_items.count, 20)):
            try:
                item = inbox_items[i]
                username_elem = item.child(resourceId="com.instagram.android:id/row_inbox_username")
                if username_elem.exists:
                    item_username = username_elem.get_text()
                    if item_username and username.lower() in item_username.lower():
                        item.click()
                        time.sleep(2)
                        return True
            except:
                continue
        
        # Try clicking on any element containing the username
        user_elem = self.device(textContains=username)
        if user_elem.exists:
            user_elem.click()
            time.sleep(2)
            return True
        
        logger.error(f"Conversation with {username} not found")
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
        
        # Use set_text for reliable input (supports emojis, special chars, etc.)
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
        processed_usernames = set()
        conversations_read = 0
        scroll_count = 0
        max_scrolls = 10
        
        while conversations_read < limit and scroll_count < max_scrolls:
            threads = self.device.xpath(DM_SELECTORS.thread_container).all()
            
            if not threads:
                logger.warning("No threads found")
                break
            
            for thread in threads:
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
                    
                    if username in processed_usernames:
                        continue
                    processed_usernames.add(username)
                    
                    logger.info(f"Opening conversation: {username}")
                    thread.click()
                    time.sleep(2)
                    
                    header_title = self.device(resourceId="com.instagram.android:id/header_title")
                    if not header_title.exists(timeout=3):
                        logger.warning(f"Could not open conversation with {username}")
                        self.device.press("back")
                        time.sleep(1)
                        continue
                    
                    real_username = header_title.get_text() or username
                    
                    # Check if group
                    is_group = False
                    can_reply = True
                    header_subtitle = self.device(resourceId="com.instagram.android:id/header_subtitle")
                    if header_subtitle.exists:
                        try:
                            subtitle_text = header_subtitle.get_text() or ''
                            subtitle_desc = header_subtitle.info.get('contentDescription', '')
                            combined = (subtitle_text + subtitle_desc).lower()
                            if 'membres' in combined or 'members' in combined:
                                is_group = True
                                composer = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
                                if not composer.exists:
                                    can_reply = False
                        except:
                            pass
                    
                    # Collect messages
                    messages = self._collect_messages()
                    
                    conv = {
                        'username': real_username,
                        'messages': messages,
                        'is_group': is_group,
                        'can_reply': can_reply
                    }
                    conversations.append(conv)
                    conversations_read += 1
                    
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
                is_received = msg_left < self.screen_width * 0.5
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
                is_received = reel_left < self.screen_width * 0.5
                
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
        
        # Deduplicate while keeping all messages (sent and received)
        seen_texts = set()
        messages = []
        for msg in all_items:
            if msg['text'] not in seen_texts:
                seen_texts.add(msg['text'])
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


def cmd_send(device_id: str, username: str, message: str):
    """Send a DM message."""
    bridge = DMBridge(device_id)
    
    if not bridge.connect():
        print(json.dumps({"success": False, "error": "Failed to connect to device"}))
        sys.exit(1)
    
    if not bridge.navigate_to_dm_inbox():
        print(json.dumps({"success": False, "error": "Cannot navigate to DM inbox"}))
        sys.exit(1)
    
    time.sleep(2)
    
    if not bridge.open_conversation(username):
        print(json.dumps({"success": False, "error": f"Cannot find conversation with {username}"}))
        sys.exit(1)
    
    if bridge.send_message(message):
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
