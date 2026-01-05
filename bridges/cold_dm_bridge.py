#!/usr/bin/env python3
"""
Cold DM Bridge - Interface between Electron and Cold DM Workflow
Sends DMs to a list of recipients (cold outreach)
"""

import sys
import json
import time
import random
import os
import sqlite3
import hashlib
import base64
import subprocess
from pathlib import Path

# Force UTF-8 encoding for stdout/stderr to support emojis on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.core.manager import InstagramManager
from loguru import logger

# Configure loguru
logger.remove()
logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="INFO", colorize=False)


# Taktik Keyboard constants
TAKTIK_KEYBOARD_IME = 'com.alexal1.adbkeyboard/.AdbIME'
IME_MESSAGE_B64 = 'ADB_INPUT_B64'


def type_with_taktik_keyboard(device_id: str, text: str, delay_mean: int = 80, delay_deviation: int = 30) -> bool:
    """
    Type text using Taktik Keyboard (ADB Keyboard) via broadcast.
    This is more reliable than uiautomator2's send_keys for special characters and emojis.
    """
    if not text:
        return True
    
    try:
        # Check if Taktik Keyboard is active
        result = subprocess.run(
            ['adb', '-s', device_id, 'shell', 'settings', 'get', 'secure', 'default_input_method'],
            capture_output=True, text=True, timeout=5
        )
        
        if TAKTIK_KEYBOARD_IME not in result.stdout:
            # Activate Taktik Keyboard
            subprocess.run(
                ['adb', '-s', device_id, 'shell', 'ime', 'enable', TAKTIK_KEYBOARD_IME],
                capture_output=True, text=True, timeout=5
            )
            result = subprocess.run(
                ['adb', '-s', device_id, 'shell', 'ime', 'set', TAKTIK_KEYBOARD_IME],
                capture_output=True, text=True, timeout=5
            )
            if 'selected' not in result.stdout.lower():
                logger.warning("Could not activate Taktik Keyboard")
                return False
        
        # Encode text as base64
        text_b64 = base64.b64encode(text.encode('utf-8')).decode('utf-8')
        
        # Send broadcast with text
        cmd = [
            'adb', '-s', device_id, 'shell', 'am', 'broadcast',
            '-a', IME_MESSAGE_B64,
            '--es', 'msg', text_b64,
            '--ei', 'delay_mean', str(delay_mean),
            '--ei', 'delay_deviation', str(delay_deviation)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            # Wait for typing to complete
            typing_time = (delay_mean * len(text) + delay_deviation) / 1000
            logger.debug(f"Taktik Keyboard typing '{text[:20]}...' ({typing_time:.1f}s)")
            time.sleep(typing_time + 0.5)
            return True
        else:
            logger.warning(f"Taktik Keyboard broadcast failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error using Taktik Keyboard: {e}")
        return False


def get_db_path() -> str:
    """Get the path to the local SQLite database."""
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        return os.path.join(appdata, 'taktik-desktop', 'taktik-data.db')
    elif sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Application Support/taktik-desktop/taktik-data.db')
    else:
        return os.path.expanduser('~/.config/taktik-desktop/taktik-data.db')


def check_dm_already_sent(account_id: int, recipient_username: str) -> bool:
    """Check if a DM was already sent to this recipient."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM sent_dms WHERE account_id = ? AND recipient_username = ?",
            (account_id, recipient_username.lower())
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logger.warning(f"Error checking sent DMs: {e}")
        return False


def record_sent_dm(account_id: int, recipient_username: str, message: str, success: bool, error_message: str = None, session_id: str = None):
    """Record a sent DM in the database."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        logger.warning(f"Database not found at {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if not exists (for safety)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_dms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                recipient_username TEXT NOT NULL,
                message_hash TEXT,
                sent_at TEXT DEFAULT (datetime('now')),
                success INTEGER DEFAULT 1,
                error_message TEXT,
                session_id TEXT,
                UNIQUE(account_id, recipient_username)
            )
        """)
        
        message_hash = hashlib.md5(message.encode()).hexdigest() if message else None
        
        cursor.execute("""
            INSERT OR REPLACE INTO sent_dms (account_id, recipient_username, message_hash, success, error_message, session_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (account_id, recipient_username.lower(), message_hash, 1 if success else 0, error_message, session_id))
        
        conn.commit()
        conn.close()
        logger.info(f"Recorded DM to {recipient_username} in database")
    except Exception as e:
        logger.warning(f"Error recording sent DM: {e}")


class ColdDMWorkflow:
    """Cold DM workflow - sends DMs to new users (cold outreach)."""
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.device_manager = None
        self.device = None
        self.screen_width = 1080
        self.screen_height = 2340
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.private_profiles = 0
    
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
    
    def navigate_to_search(self) -> bool:
        """Navigate to the search/explore tab."""
        logger.info("Navigating to search...")
        
        # Try search icon in bottom nav
        search_btn = self.device(resourceId="com.instagram.android:id/search_tab")
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True
        
        # Try by description
        search_btn = self.device(description="Search and explore")
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True
        
        search_btn = self.device(descriptionContains="Search")
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True
        
        logger.error("Could not find search button")
        return False
    
    def search_user(self, username: str) -> bool:
        """Search for a user by username."""
        logger.info(f"Searching for user: {username}")
        username_lower = username.lower().strip()
        
        # Click on search bar
        search_bar = self.device(resourceId="com.instagram.android:id/action_bar_search_edit_text")
        if not search_bar.exists:
            search_bar = self.device(text="Search")
        if not search_bar.exists:
            search_bar = self.device(className="android.widget.EditText")
        
        if not search_bar.exists:
            logger.error("Search bar not found")
            return False
        
        search_bar.click()
        time.sleep(0.5)
        search_bar.set_text(username)
        time.sleep(2)
        
        # Click on Accounts tab to filter results
        accounts_tab = self.device(text="Accounts")
        if accounts_tab.exists:
            logger.info("Clicking Accounts tab")
            accounts_tab.click()
            time.sleep(1.5)
        
        # Method 1: Find user containers and match by username text inside
        # The clickable container is row_search_user_container, username is inside row_search_user_username
        user_containers = self.device(resourceId="com.instagram.android:id/row_search_user_container")
        if user_containers.exists:
            logger.info(f"Found {user_containers.count} user containers")
            for i in range(min(user_containers.count, 10)):
                try:
                    container = user_containers[i]
                    # Find username text inside this container
                    username_elem = container.child(resourceId="com.instagram.android:id/row_search_user_username")
                    if username_elem.exists:
                        found_username = username_elem.get_text()
                        if found_username:
                            found_lower = found_username.lower().strip()
                            logger.info(f"Checking user {i}: '{found_username}'")
                            # Exact match or close match
                            if found_lower == username_lower or username_lower in found_lower or found_lower in username_lower:
                                logger.info(f"Found matching user: {found_username}, clicking container")
                                container.click()
                                time.sleep(2)
                                return True
                except Exception as e:
                    logger.warning(f"Error checking container {i}: {e}")
                    continue
        
        # Method 2: Try clicking first result if username matches closely
        first_username = self.device(resourceId="com.instagram.android:id/row_search_user_username")
        if first_username.exists:
            first_text = first_username.get_text()
            if first_text and username_lower in first_text.lower():
                logger.info(f"Clicking first matching result: {first_text}")
                # Click the parent container
                first_username.click()
                time.sleep(2)
                return True
        
        logger.error(f"User {username} not found in search results")
        return False
    
    def is_private_profile(self) -> bool:
        """Check if the current profile is private."""
        # Check for private profile indicator
        private_state = self.device(resourceId="com.instagram.android:id/private_profile_empty_state")
        if private_state.exists:
            logger.info("Detected private profile (empty state)")
            return True
        
        # Check for "This account is private" text
        private_text = self.device(textContains="account is private")
        if private_text.exists:
            logger.info("Detected private profile (text)")
            return True
        
        # Check for French version
        private_text_fr = self.device(textContains="compte est privé")
        if private_text_fr.exists:
            logger.info("Detected private profile (text FR)")
            return True
        
        return False
    
    def open_dm_from_profile(self) -> bool:
        """Open DM conversation from a user's profile."""
        logger.info("Opening DM from profile...")
        
        # First check if profile is private
        if self.is_private_profile():
            logger.warning("Cannot send DM - profile is private")
            return "private"  # Special return value
        
        # Find Message button on profile
        msg_btn = self.device(text="Message")
        if not msg_btn.exists:
            msg_btn = self.device(description="Message")
        if not msg_btn.exists:
            msg_btn = self.device(resourceId="com.instagram.android:id/profile_header_message_button")
        
        if msg_btn.exists:
            msg_btn.click()
            time.sleep(2)
            return True
        
        logger.error("Message button not found on profile")
        return False
    
    def send_message(self, message: str) -> bool:
        """Send a message in the current conversation."""
        logger.info("Sending message...")
        
        # Find message input
        msg_input = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
        if not msg_input.exists:
            msg_input = self.device(className="android.widget.EditText")
        if not msg_input.exists:
            msg_input = self.device(textContains="Message")
        
        if not msg_input.exists:
            # Check if invite was already sent
            if self.check_invite_already_sent():
                return "invite_sent"  # Special return value
            logger.error("Message input not found")
            return False
        
        msg_input.click()
        time.sleep(0.5)
        
        # Simulate typing delay
        typing_time = min(len(message) * random.uniform(0.03, 0.05) + random.uniform(0.5, 1.5), 5.0)
        time.sleep(typing_time)
        
        # Use Taktik Keyboard for reliable input (supports emojis, special chars, etc.)
        if type_with_taktik_keyboard(self.device_id, message):
            logger.info("Text set via Taktik Keyboard")
        else:
            # Fallback to set_text or send_keys
            logger.warning("Taktik Keyboard failed, trying fallback methods...")
            try:
                msg_input.set_text(message)
            except Exception as e:
                logger.warning(f"set_text failed: {e}, trying send_keys...")
                try:
                    msg_input.send_keys(message)
                except Exception as e2:
                    logger.error(f"send_keys also failed: {e2}")
                    return False
        
        time.sleep(0.5)
        
        # Find and click send button
        send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button_container")
        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button")
        if not send_btn.exists:
            send_btn = self.device(description="Send")
        if not send_btn.exists:
            send_btn = self.device(description="Envoyer")
        
        if send_btn.exists:
            send_btn.click()
            time.sleep(1)
            logger.info("Message sent!")
            return True
        
        logger.error("Send button not found")
        return False
    
    def go_back(self):
        """Go back to previous screen."""
        back_btn = self.device(resourceId="com.instagram.android:id/action_bar_button_back")
        if back_btn.exists:
            back_btn.click()
        else:
            self.device.press("back")
        time.sleep(1)
    
    def go_home(self):
        """Navigate to Instagram home screen."""
        logger.info("Navigating to home...")
        
        # First, press back to exit any conversation/profile we might be in
        # This ensures the bottom nav is visible
        self.device.press("back")
        time.sleep(1)
        
        # Try home tab in bottom nav
        home_btn = self.device(resourceId="com.instagram.android:id/feed_tab")
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True
        
        # Try by description
        home_btn = self.device(description="Home")
        if not home_btn.exists:
            home_btn = self.device(descriptionContains="Home")
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True
        
        # Still not found? Press back again and retry
        self.device.press("back")
        time.sleep(1)
        
        home_btn = self.device(resourceId="com.instagram.android:id/feed_tab")
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True
        
        # Fallback: press back multiple times to get to home
        for _ in range(2):
            self.device.press("back")
            time.sleep(0.5)
        time.sleep(1)
        return True
    
    def check_invite_already_sent(self) -> bool:
        """Check if we're on the 'Invite sent' screen."""
        invite_sent = self.device(textContains="Invite sent")
        if invite_sent.exists:
            logger.info("Invite already sent to this user")
            return True
        
        # Also check for "You can send more messages after your invite is accepted"
        invite_msg = self.device(textContains="invite is accepted")
        if invite_msg.exists:
            logger.info("Invite already sent (waiting for acceptance)")
            return True
        
        return False
    
    def run(self, recipients: list, messages: list, delay_min: int = 30, delay_max: int = 60, max_dms: int = 50, account_id: int = 1, session_id: str = None) -> dict:
        """Run the cold DM workflow."""
        logger.info(f"Starting Cold DM workflow: {len(recipients)} recipients, {len(messages)} messages")
        
        if not messages:
            return {'success': False, 'error': 'No messages provided'}
        
        if not recipients:
            return {'success': False, 'error': 'No recipients provided'}
        
        # Filter out recipients who already received a DM
        filtered_recipients = []
        skipped_count = 0
        for recipient in recipients:
            if check_dm_already_sent(account_id, recipient):
                logger.info(f"Skipping {recipient} - DM already sent")
                skipped_count += 1
            else:
                filtered_recipients.append(recipient)
        
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} recipients (DM already sent)")
        
        if not filtered_recipients:
            return {'success': True, 'dms_sent': 0, 'dms_success': 0, 'dms_failed': 0, 'error': 'All recipients already received a DM'}
        
        # Restart Instagram for clean state
        self.restart_instagram()
        
        for i, recipient in enumerate(filtered_recipients[:max_dms]):
            if self.dms_sent >= max_dms:
                logger.info(f"Reached max DMs limit: {max_dms}")
                break
            
            logger.info(f"[{i+1}/{min(len(filtered_recipients), max_dms)}] Sending DM to: {recipient}")
            
            # Emit progress to Electron
            print(json.dumps({
                "type": "progress",
                "current": i + 1,
                "total": min(len(filtered_recipients), max_dms),
                "username": recipient
            }), flush=True)
            
            try:
                # Navigate to search
                if not self.navigate_to_search():
                    logger.warning(f"Could not navigate to search for {recipient}")
                    self.dms_failed += 1
                    # DON'T record - this is a temporary error, we can retry later
                    self.go_home()  # Reset to home before next attempt
                    continue
                
                # Search for user
                if not self.search_user(recipient):
                    logger.warning(f"Could not find user: {recipient}")
                    self.dms_failed += 1
                    # DON'T record - user might exist, just search failed
                    self.go_home()  # Reset to home
                    continue
                
                # Open DM from profile
                open_result = self.open_dm_from_profile()
                if open_result == "private":
                    logger.warning(f"Skipping {recipient} - private profile")
                    # Only count as private, NOT as failed (avoid double counting)
                    self.private_profiles += 1
                    # DON'T record - we might want to retry if they become public
                    self.go_home()
                    continue
                elif not open_result:
                    logger.warning(f"Could not open DM for: {recipient}")
                    self.dms_failed += 1
                    # DON'T record - could be temporary UI issue
                    self.go_home()  # Reset to home
                    continue
                
                # Pick a random message
                message = random.choice(messages)
                
                # Send message
                send_result = self.send_message(message)
                
                if send_result == "invite_sent":
                    # Invite was already sent - record as success to avoid retry
                    logger.info(f"Invite already sent to {recipient} - marking as done")
                    record_sent_dm(account_id, recipient, "", True, "Invite already sent", session_id)
                    self.dms_sent += 1
                elif send_result:
                    self.dms_success += 1
                    logger.info(f"Successfully sent DM to {recipient}")
                    # ONLY record successful DMs - these should not be retried
                    record_sent_dm(account_id, recipient, message, True, None, session_id)
                    self.dms_sent += 1
                else:
                    self.dms_failed += 1
                    logger.warning(f"Failed to send DM to {recipient}")
                    # DON'T record failed sends - we can retry later
                
                # Go back to home before next user (more reliable than go_back twice)
                self.go_home()
                
                # Delay between DMs
                if i < len(filtered_recipients) - 1:
                    delay = random.uniform(delay_min, delay_max)
                    logger.info(f"Waiting {delay:.1f}s before next DM...")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error sending DM to {recipient}: {e}")
                self.dms_failed += 1
                self.go_home()  # Go home to reset state
        
        return {
            'success': True,
            'dms_sent': self.dms_sent,
            'dms_success': self.dms_success,
            'dms_failed': self.dms_failed,
            'private_profiles': self.private_profiles
        }


def main():
    if len(sys.argv) < 2:
        logger.error("Usage: cold_dm_bridge.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        # Load configuration
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        device_id = config['deviceId']
        logger.info(f"Starting Cold DM workflow for device: {device_id}")
        
        # Initialize workflow
        workflow = ColdDMWorkflow(device_id)
        
        if not workflow.connect():
            logger.error(f"Failed to connect to device {device_id}")
            print(json.dumps({"success": False, "error": "Failed to connect to device"}))
            sys.exit(1)
        
        # Get config
        recipients = config.get('recipients', [])
        messages = config.get('messages', [])
        delay_min = config.get('delayMin', 30)
        delay_max = config.get('delayMax', 60)
        max_dms = config.get('maxDmsPerSession', 50)
        account_id = config.get('accountId', 1)  # Default to account 1
        session_id = config.get('sessionId', device_id)  # Use device_id as session identifier
        
        logger.info(f"Cold DM config: {len(recipients)} recipients, {len(messages)} messages")
        
        # Run workflow with duplicate checking
        result = workflow.run(recipients, messages, delay_min, delay_max, max_dms, account_id, session_id)
        
        # Output result as JSON for Electron to parse
        print(json.dumps({
            "success": result.get('success', False),
            "dmsSent": result.get('dms_sent', 0),
            "dmsSuccess": result.get('dms_success', 0),
            "dmsFailed": result.get('dms_failed', 0),
            "error": result.get('error')
        }))
        
    except Exception as e:
        logger.error(f"Cold DM workflow error: {e}", exc_info=True)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
