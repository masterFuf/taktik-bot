#!/usr/bin/env python3
"""
TikTok DM Outreach Bridge - Cold DM workflow for TikTok
Sends DMs to a list of recipients (cold outreach)
"""

import sys
import json
import time
import random
import os
import sqlite3
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional

# Force UTF-8 encoding for stdout/stderr to support emojis on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger

# Configure loguru
logger.remove()
logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="DEBUG", colorize=False)


def send_message(msg_type: str, **kwargs):
    """Send a JSON message to stdout for Electron to parse."""
    message = {"type": msg_type, **kwargs}
    print(json.dumps(message), flush=True)


def send_status(status: str, message: str):
    """Send status update."""
    send_message("status", status=status, message=message)


def send_progress(current: int, total: int, username: str):
    """Send progress update."""
    send_message("progress", current=current, total=total, username=username)


def send_dm_result(username: str, success: bool, error: str = None):
    """Send DM result."""
    send_message("dm_result", username=username, success=success, error=error)


def send_stats(stats: dict):
    """Send stats update."""
    send_message("stats", stats=stats)


def send_error(error: str):
    """Send error message."""
    send_message("error", error=error)


def get_db_path() -> str:
    """Get the path to the local SQLite database."""
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        return os.path.join(appdata, 'taktik-desktop', 'taktik-data.db')
    elif sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Application Support/taktik-desktop/taktik-data.db')
    else:
        return os.path.expanduser('~/.config/taktik-desktop/taktik-data.db')


def check_dm_already_sent(account_id: int, recipient_username: str, platform: str = 'tiktok') -> bool:
    """Check if a DM was already sent to this recipient."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM sent_dms WHERE account_id = ? AND recipient_username = ? AND platform = ?",
            (account_id, recipient_username.lower(), platform)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logger.warning(f"Error checking sent DMs: {e}")
        return False


def record_sent_dm(account_id: int, recipient_username: str, message: str, success: bool, 
                   error_message: str = None, session_id: str = None, platform: str = 'tiktok'):
    """Record a sent DM in the database."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        logger.warning(f"Database not found at {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if not exists (add platform column)
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
                platform TEXT DEFAULT 'instagram',
                UNIQUE(account_id, recipient_username, platform)
            )
        """)
        
        message_hash = hashlib.md5(message.encode()).hexdigest() if message else None
        
        cursor.execute("""
            INSERT OR REPLACE INTO sent_dms (account_id, recipient_username, message_hash, success, error_message, session_id, platform)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (account_id, recipient_username.lower(), message_hash, 1 if success else 0, error_message, session_id, platform))
        
        conn.commit()
        conn.close()
        logger.info(f"Recorded DM to {recipient_username} in database")
    except Exception as e:
        logger.warning(f"Error recording sent DM: {e}")


class TikTokDMOutreachWorkflow:
    """TikTok DM Outreach workflow - sends DMs to new users (cold outreach)."""
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.device = None
        self.manager = None
        self.navigation = None
        self.dm_actions = None
        self.base_action = None
        
        # Stats
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.privacy_blocked = 0
        self.not_found = 0
    
    def connect(self) -> bool:
        """Connect to the device and initialize TikTok actions."""
        logger.info(f"Connecting to device: {self.device_id}")
        
        try:
            from taktik.core.social_media.tiktok import TikTokManager
            from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
            from taktik.core.social_media.tiktok.actions.atomic.dm_actions import DMActions
            from taktik.core.social_media.tiktok.actions.core.base_action import BaseAction
            
            self.manager = TikTokManager(device_id=self.device_id)
            
            # Must call connect() before accessing device
            if not self.manager.device_manager.connect():
                logger.error("Failed to connect to device via device_manager")
                return False
            
            self.device = self.manager.device_manager.device
            
            # Initialize actions
            self.navigation = NavigationActions(self.manager.device_manager)
            self.dm_actions = DMActions(self.manager.device_manager)
            self.base_action = BaseAction(self.manager.device_manager)
            
            logger.info("Connected to device successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def restart_tiktok(self):
        """Restart TikTok for clean state."""
        logger.info("Restarting TikTok...")
        send_status("restarting", "Restarting TikTok app")
        
        if self.manager:
            self.manager.stop()
            time.sleep(1)
            self.manager.launch()
            time.sleep(4)
    
    def navigate_to_user_profile(self, username: str) -> bool:
        """Navigate to a user's profile via search."""
        logger.info(f"Navigating to @{username}'s profile")
        
        # Use the existing navigation action
        return self.navigation.navigate_to_user_profile(username)
    
    def click_message_button(self) -> bool:
        """Click the Message button on a user's profile."""
        logger.info("Clicking Message button on profile")
        
        from taktik.core.social_media.tiktok.ui.selectors import PROFILE_SELECTORS
        
        # Try clicking the message button
        if self.base_action._find_and_click(PROFILE_SELECTORS.message_button, timeout=5):
            time.sleep(2)
            return True
        
        # Fallback: try finding by text "Message" in a clickable parent
        try:
            raw_device = self.device._device if hasattr(self.device, '_device') else self.device
            message_elem = raw_device(text="Message")
            if message_elem.exists:
                # Click the parent which should be clickable
                message_elem.click()
                time.sleep(2)
                return True
        except Exception as e:
            logger.warning(f"Fallback click failed: {e}")
        
        logger.warning("Message button not found on profile")
        return False
    
    def is_privacy_blocked(self) -> bool:
        """Check if the conversation is blocked due to privacy settings."""
        from taktik.core.social_media.tiktok.ui.selectors import PROFILE_SELECTORS
        
        # Check for "Unable to send message" text
        if self.base_action._element_exists(PROFILE_SELECTORS.unable_to_send_message, timeout=2):
            logger.info("Detected privacy blocked conversation (unable to send)")
            return True
        
        # Check for privacy settings message
        if self.base_action._element_exists(PROFILE_SELECTORS.privacy_blocked_message, timeout=2):
            logger.info("Detected privacy blocked conversation (privacy settings)")
            return True
        
        return False
    
    def can_send_message(self) -> bool:
        """Check if we can send a message (message input is visible)."""
        # Check if message input field exists
        return self.dm_actions.is_in_conversation()
    
    def send_dm(self, message: str) -> bool:
        """Send a DM in the current conversation."""
        logger.info("Sending DM...")
        
        # First check if privacy blocked
        if self.is_privacy_blocked():
            logger.warning("Cannot send DM - privacy blocked")
            return "privacy_blocked"
        
        # Check if we can send
        if not self.can_send_message():
            logger.warning("Message input not found")
            return False
        
        # Send the message
        if self.dm_actions.send_text_message(message):
            logger.info("DM sent successfully")
            return True
        
        logger.warning("Failed to send DM")
        return False
    
    def go_back(self):
        """Go back to previous screen."""
        self.navigation.go_back()
    
    def go_home(self):
        """Navigate to TikTok home screen."""
        logger.info("Navigating to home...")
        self.navigation.navigate_to_home()
        time.sleep(1)
    
    def run(self, recipients: List[str], messages: List[str], delay_min: int = 30, 
            delay_max: int = 60, max_dms: int = 50, account_id: int = 1, 
            session_id: str = None) -> dict:
        """Run the DM outreach workflow."""
        logger.info(f"Starting TikTok DM Outreach: {len(recipients)} recipients, {len(messages)} messages")
        
        if not messages:
            return {'success': False, 'error': 'No messages provided'}
        
        if not recipients:
            return {'success': False, 'error': 'No recipients provided'}
        
        # Filter out recipients who already received a DM
        filtered_recipients = []
        skipped_count = 0
        for recipient in recipients:
            if check_dm_already_sent(account_id, recipient, 'tiktok'):
                logger.info(f"Skipping {recipient} - DM already sent")
                skipped_count += 1
            else:
                filtered_recipients.append(recipient)
        
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} recipients (DM already sent)")
            send_status("filtering", f"Skipped {skipped_count} already contacted")
        
        if not filtered_recipients:
            return {
                'success': True, 
                'dms_sent': 0, 
                'dms_success': 0, 
                'dms_failed': 0,
                'error': 'All recipients already received a DM'
            }
        
        # Restart TikTok for clean state
        self.restart_tiktok()
        
        total_to_process = min(len(filtered_recipients), max_dms)
        
        for i, recipient in enumerate(filtered_recipients[:max_dms]):
            if self.dms_sent >= max_dms:
                logger.info(f"Reached max DMs limit: {max_dms}")
                break
            
            logger.info(f"[{i+1}/{total_to_process}] Sending DM to: @{recipient}")
            send_progress(i + 1, total_to_process, recipient)
            send_status("processing", f"Processing @{recipient}")
            
            try:
                # Navigate to user's profile
                if not self.navigate_to_user_profile(recipient):
                    logger.warning(f"Could not find user: @{recipient}")
                    self.not_found += 1
                    self.dms_failed += 1
                    send_dm_result(recipient, False, "User not found")
                    self.go_home()
                    continue
                
                # Click Message button on profile
                if not self.click_message_button():
                    logger.warning(f"Could not click Message button for @{recipient}")
                    self.dms_failed += 1
                    send_dm_result(recipient, False, "Message button not found")
                    self.go_home()
                    continue
                
                # Pick a random message
                message = random.choice(messages)
                
                # Send the DM
                send_result = self.send_dm(message)
                
                if send_result == "privacy_blocked":
                    logger.warning(f"Privacy blocked for @{recipient}")
                    self.privacy_blocked += 1
                    self.dms_failed += 1
                    send_dm_result(recipient, False, "Privacy settings blocked")
                    # Record as failed due to privacy
                    record_sent_dm(account_id, recipient, "", False, "Privacy blocked", session_id, 'tiktok')
                elif send_result:
                    self.dms_success += 1
                    self.dms_sent += 1
                    logger.info(f"Successfully sent DM to @{recipient}")
                    send_dm_result(recipient, True)
                    # Record successful DM
                    record_sent_dm(account_id, recipient, message, True, None, session_id, 'tiktok')
                else:
                    self.dms_failed += 1
                    logger.warning(f"Failed to send DM to @{recipient}")
                    send_dm_result(recipient, False, "Send failed")
                
                # Send stats update
                send_stats({
                    'sent': self.dms_sent,
                    'success': self.dms_success,
                    'failed': self.dms_failed,
                    'privacy_blocked': self.privacy_blocked,
                    'not_found': self.not_found
                })
                
                # Go back to home before next user
                self.go_home()
                
                # Delay between DMs
                if i < total_to_process - 1:
                    delay = random.uniform(delay_min, delay_max)
                    logger.info(f"Waiting {delay:.1f}s before next DM...")
                    send_status("waiting", f"Waiting {delay:.0f}s...")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error sending DM to @{recipient}: {e}")
                self.dms_failed += 1
                send_dm_result(recipient, False, str(e))
                self.go_home()
        
        return {
            'success': True,
            'dms_sent': self.dms_sent,
            'dms_success': self.dms_success,
            'dms_failed': self.dms_failed,
            'privacy_blocked': self.privacy_blocked,
            'not_found': self.not_found
        }


def run_dm_outreach_workflow(config: Dict[str, Any]):
    """Run the TikTok DM outreach workflow."""
    device_id = config.get('device_id') or config.get('deviceId')
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    logger.info(f"Starting TikTok DM Outreach on device: {device_id}")
    send_status("starting", "Initializing DM Outreach workflow")
    
    # Initialize workflow
    workflow = TikTokDMOutreachWorkflow(device_id)
    
    if not workflow.connect():
        send_error("Failed to connect to device")
        return False
    
    # Get config
    recipients = config.get('recipients', [])
    messages = config.get('messages', [])
    delay_min = config.get('delayMin', config.get('delay_min', 30))
    delay_max = config.get('delayMax', config.get('delay_max', 60))
    max_dms = config.get('maxDms', config.get('max_dms', 50))
    account_id = config.get('accountId', config.get('account_id', 1))
    session_id = config.get('sessionId', config.get('session_id', device_id))
    
    logger.info(f"Config: {len(recipients)} recipients, {len(messages)} messages, max {max_dms} DMs")
    
    # Run workflow
    result = workflow.run(recipients, messages, delay_min, delay_max, max_dms, account_id, session_id)
    
    # Send final result
    send_status("completed", f"Completed: {result.get('dms_success', 0)} sent, {result.get('dms_failed', 0)} failed")
    
    return result.get('success', False)


def main():
    """Main entry point - reads config from stdin."""
    logger.info("TikTok DM Outreach Bridge started")
    
    try:
        # Read config from stdin
        config_line = sys.stdin.readline()
        if not config_line:
            send_error("No configuration received")
            sys.exit(1)
        
        config = json.loads(config_line)
        logger.info(f"Received config: {json.dumps(config, indent=2)[:500]}...")
        
        # Run workflow
        success = run_dm_outreach_workflow(config)
        
        if not success:
            sys.exit(1)
            
    except json.JSONDecodeError as e:
        send_error(f"Invalid JSON config: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"DM Outreach error: {e}", exc_info=True)
        send_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
